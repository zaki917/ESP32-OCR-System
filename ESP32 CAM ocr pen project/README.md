# ESP32-CAM OCR System

Motion-activated text reading system using ESP32-CAM and Python.

## What This Does
- ESP32-CAM captures images and sends them over USB serial
- Python detects motion in the frames
- When motion is detected, it runs OCR (Tesseract)
- Recognized text is spoken aloud (Text-to-Speech)
- Images are saved only when motion is detected

## Hardware
- ESP32-CAM module (with OV2640 camera)
- FTDI programmer (for USB connection)
- USB cable

## Setup

### 1. ESP32
1. Open `esp32_camera_code/esp32_ocr_camera.ino` in Arduino IDE
2. Install ESP32 board package if you haven't
3. Select board: AI Thinker ESP32-CAM
4. Upload to ESP32-CAM

### 2. Python Client
```bash
# Install dependencies
pip install -r requirements.txt

# Update Tesseract path in ocr_system.py if needed
# Run the system
python ocr_system.py