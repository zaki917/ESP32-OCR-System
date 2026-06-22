#!/usr/bin/env python3
"""
ESP32-CAM OCR System - Motion Detection + Text-to-Speech

What this does:
- Connects to ESP32-CAM over serial (USB)
- Captures images and detects motion
- Runs OCR on motion-detected frames
- Speaks the text aloud using TTS
- Saves images only when motion is detected

Dependencies: see requirements.txt
Author: Rana Zakaria Samad Khan
"""

import serial
import time
import struct
import cv2
import numpy as np
from PIL import Image
import io
import pytesseract
import os
from datetime import datetime
import pyttsx3
import threading

# ============================================================================
# TESSERACT CONFIGURATION
# ============================================================================
# Update these paths if your Tesseract is installed elsewhere

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\zakis\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
TESSDATA_DIR = r'C:\Users\zakis\AppData\Local\Programs\Tesseract-OCR\tessdata'


class ESP32CameraOCR:
    """Main class that handles everything from serial to TTS"""
    
    def __init__(self, port='COM3', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.image_count = 0
        self.output_dir = "captured_images"
        
        # Motion detection settings
        self.prev_frame = None
        self.motion_threshold = 3000   # Higher = less sensitive
        self.min_motion_area = 300     # Minimum pixels that changed
        
        # TTS stuff
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        self.tts_queue = []
        self.tts_running = False
        
        # Performance tracking
        self.processing_times = []
        self.motion_detected_count = 0
        
        # Create output folder
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    # ========================================================================
    # TEXT-TO-SPEECH (with queue so it doesn't block the main loop)
    # ========================================================================
    
    def init_tts(self):
        with self.tts_lock:
            if self.tts_engine is None:
                try:
                    self.tts_engine = pyttsx3.init()
                    self.tts_engine.setProperty('rate', 160)
                    self.tts_engine.setProperty('volume', 0.9)
                    print("[TTS] Ready")
                except Exception as e:
                    print(f"[ERROR] TTS init failed: {e}")
    
    def speak_text(self, text):
        """Add text to speech queue (non-blocking)"""
        if not text or len(text.strip()) == 0:
            return
        
        if self.tts_engine is None:
            self.init_tts()
            if self.tts_engine is None:
                return
        
        with self.tts_lock:
            self.tts_queue.append(text)
        
        if not self.tts_running:
            self._process_tts_queue()
    
    def _process_tts_queue(self):
        """Background thread that actually speaks the queued text"""
        if self.tts_running or self.tts_engine is None:
            return
        
        def worker():
            self.tts_running = True
            while True:
                with self.tts_lock:
                    if not self.tts_queue:
                        self.tts_running = False
                        break
                    text = self.tts_queue.pop(0)
                
                try:
                    # Clean up the text a bit
                    clean_text = ' '.join(text.split())
                    if len(clean_text) > 100:
                        clean_text = clean_text[:100] + "..."
                    
                    print(f"[TTS] Speaking: {clean_text[:50]}...")
                    self.tts_engine.stop()
                    self.tts_engine.say(clean_text)
                    self.tts_engine.runAndWait()
                    time.sleep(0.5)  # Pause between speeches
                except Exception as e:
                    print(f"[ERROR] TTS failed: {e}")
                    time.sleep(1)
        
        tts_thread = threading.Thread(target=worker, daemon=True)
        tts_thread.start()
    
    # ========================================================================
    # MOTION DETECTION
    # ========================================================================
    
    def detect_motion(self, current_frame):
        """
        Compare current frame to previous one.
        Returns: (motion_detected, number_of_pixels_changed)
        """
        if self.prev_frame is None:
            self.prev_frame = current_frame
            return False, 0
        
        # Convert to grayscale for faster comparison
        prev_gray = cv2.cvtColor(self.prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        
        # Difference between frames
        frame_diff = cv2.absdiff(prev_gray, curr_gray)
        _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
        
        # Count how many pixels changed
        motion_pixels = cv2.countNonZero(thresh)
        
        # Store current frame for next comparison
        self.prev_frame = current_frame.copy()
        
        return motion_pixels > self.motion_threshold, motion_pixels
    
    # ========================================================================
    # SERIAL COMMUNICATION
    # ========================================================================
    
    def connect(self):
        """Connect to ESP32 and wait for 'READY' signal"""
        print(f"[INFO] Connecting to {self.port}...")
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=5)
            time.sleep(2)
            self.ser.reset_input_buffer()
            
            print("[INFO] Waiting for ESP32...")
            start_time = time.time()
            while time.time() - start_time < 10:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"[ESP32] {line}")
                    if "READY" in line:
                        print("[INFO] ESP32 ready!")
                        return True
            return False
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False
    
    def capture_image(self):
        """Read one image from ESP32 over serial"""
        try:
            # Wait for IMG_START marker
            while True:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line == "IMG_START":
                        break
                    elif line and "IMG_ERROR" not in line:
                        if "READY" in line or "ERROR" in line:
                            print(f"[ESP32] {line}")
            
            # Read 4 bytes = image size (little-endian)
            size_bytes = self.ser.read(4)
            if len(size_bytes) != 4:
                print("[ERROR] Failed to read image size")
                return None
            
            img_size = struct.unpack('<I', size_bytes)[0]
            
            # Sanity check
            if img_size < 500 or img_size > 50000:
                print(f"[ERROR] Invalid image size: {img_size}")
                return None
            
            # Read the actual JPEG bytes
            img_data = b''
            bytes_read = 0
            read_start = time.time()
            
            while bytes_read < img_size:
                if time.time() - read_start > 5:
                    print("[ERROR] Timeout reading image")
                    return None
                chunk = self.ser.read(min(4096, img_size - bytes_read))
                if not chunk:
                    continue
                img_data += chunk
                bytes_read += len(chunk)
            
            # Read the IMG_END marker (non-blocking)
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line != "IMG_END":
                    print(f"[WARNING] Expected IMG_END, got: {line}")
            
            return img_data
            
        except Exception as e:
            print(f"[ERROR] Capture failed: {e}")
            return None
    
    # ========================================================================
    # IMAGE PROCESSING + OCR
    # ========================================================================
    
    def process_image(self, img_data, save=False):
        """
        Convert bytes to image, check motion, run OCR if motion detected.
        Returns: (image, text, motion_detected, processing_time_ms)
        """
        start_time = time.time()
        
        try:
            # Decode JPEG
            img = Image.open(io.BytesIO(img_data))
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            # Check for motion
            motion_detected, motion_pixels = self.detect_motion(img_cv)
            
            if not motion_detected:
                elapsed = (time.time() - start_time) * 1000
                print(f"[INFO] No motion ({motion_pixels}px, {elapsed:.1f}ms)")
                return img_cv, "", False, elapsed
            
            self.motion_detected_count += 1
            print(f"[MOTION] Detected! Pixels changed: {motion_pixels}")
            
            # Save image if motion detected
            if save:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{self.output_dir}/motion_{timestamp}_{self.image_count}.jpg"
                cv2.imwrite(filename, img_cv)
                print(f"[INFO] Saved: {filename}")
            
            # Prep for OCR
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            
            # OCR config
            tessdata_config = f'--tessdata-dir {TESSDATA_DIR}'
            config = f'--psm 7 {tessdata_config}'  # psm 7 = single line
            
            text = pytesseract.image_to_string(thresh, config=config).strip()
            
            elapsed = (time.time() - start_time) * 1000
            return img_cv, text, True, elapsed
            
        except Exception as e:
            print(f"[ERROR] Process failed: {e}")
            return None, "", False, 0
    
    # ========================================================================
    # MAIN LOOP
    # ========================================================================
    
    def run(self, max_images=None):
        """Main loop - captures images, detects motion, runs OCR + TTS"""
        self.init_tts()
        
        if not self.connect():
            return
        
        print("\n" + "="*50)
        print("ESP32-CAM OCR System - Motion + TTS")
        print("="*50)
        print("- Captures images via USB serial")
        print("- Motion detection triggers OCR")
        print("- Text-to-speech reads results")
        print("- No video display = faster")
        print("="*50)
        print("Press Ctrl+C to stop")
        print("="*50 + "\n")
        
        start_time = time.time()
        last_text = ""  # Avoid repeating same text
        
        try:
            while True:
                if max_images and self.image_count >= max_images:
                    break
                
                print(f"\n[CAPTURE #{self.image_count + 1}] Waiting...")
                
                # Capture from ESP32
                capture_start = time.time()
                img_data = self.capture_image()
                capture_time = (time.time() - capture_start) * 1000
                
                if img_data is None:
                    print("[ERROR] No image received")
                    time.sleep(1)
                    continue
                
                print(f"[CAPTURE] Received {len(img_data)} bytes in {capture_time:.1f}ms")
                
                # Process image (save only if motion detected)
                img_cv, text, motion_detected, process_time = self.process_image(
                    img_data, 
                    save=motion_detected
                )
                
                if img_cv is not None and motion_detected:
                    if text:
                        print(f"[OCR] '{text}' (Processing: {process_time:.1f}ms)")
                        if text != last_text:
                            self.speak_text(text)
                            last_text = text
                    else:
                        print(f"[OCR] No text found (Processing: {process_time:.1f}ms)")
                        self.speak_text("Motion detected but no text found")
                        last_text = ""
                    
                    # Performance stats
                    total_time = capture_time + process_time
                    self.processing_times.append(total_time)
                    
                    if len(self.processing_times) % 10 == 0:
                        avg = sum(self.processing_times[-10:]) / 10
                        print(f"[PERF] Avg processing time: {avg:.1f}ms")
                
                self.image_count += 1
                time.sleep(0.1)  # Prevent CPU overload
                
        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user")
        finally:
            self.cleanup(start_time)
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def cleanup(self, start_time=None):
        """Close serial, stop TTS, print summary"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Serial port closed")
        
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        if start_time:
            total_time = time.time() - start_time
            avg_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
            
            print("\n" + "="*50)
            print("PERFORMANCE SUMMARY")
            print("="*50)
            print(f"Runtime: {total_time:.1f} seconds")
            print(f"Images processed: {self.image_count}")
            print(f"Motion events: {self.motion_detected_count}")
            print(f"Avg processing time: {avg_time:.1f}ms")
            if self.image_count > 0:
                print(f"Images/sec: {self.image_count / total_time:.2f}")
                print(f"Motion rate: {(self.motion_detected_count / self.image_count) * 100:.1f}%")
            print("="*50)
        
        print("[INFO] Done")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Change COM port if needed
    PORT = 'COM3'
    MAX_IMAGES = None  # Set to a number to limit captures
    
    ocr = ESP32CameraOCR(port=PORT)
    ocr.run(max_images=MAX_IMAGES)