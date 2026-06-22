## 📝 README.md

```markdown
# ESP32-CAM OCR System

A motion-activated text reading system that captures images with an ESP32-CAM, detects motion, extracts text using OCR, and reads it aloud.


## What This Does

- ESP32-CAM captures JPEG images over USB serial
- Python client detects motion by comparing frames
- When motion is detected, it runs OCR (Tesseract)
- Recognized text is spoken aloud using text-to-speech
- Images are saved only when motion is detected

---

##  Hardware

- ESP32-CAM module (with OV2640 camera)
- FTDI programmer (for USB connection)
- USB cable
- Windows PC (or any computer with Python)

---

## 📂 Project Structure

```
ESP32-OCR-System/
├── esp32_camera_code/
│   └── esp32_ocr_camera.ino   # Arduino code for ESP32-CAM
├── python_client/
│   ├── ocr_system.py          # Main Python script
│   └── requirements.txt       # Python dependencies
└── README.md
```

---

## Getting Started

### 1. ESP32 Setup

1. Open `esp32_camera_code/esp32_ocr_camera.ino` in Arduino IDE
2. Install ESP32 board package (if not already)
3. Select board: **AI Thinker ESP32-CAM**
4. Upload the code to your ESP32-CAM

### 2. Python Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Update Tesseract paths in ocr_system.py if needed
# Then run:
python ocr_system.py
```

### 3. Tesseract OCR

- Download and install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki
- Make sure `eng.traineddata` is in your `tessdata` folder
- Update the paths in `ocr_system.py` to match your installation

---

##  How It Works

1. ESP32 captures a JPEG every 3 seconds
2. Sends over serial: `IMG_START` + size + data + `IMG_END`
3. Python receives and decodes the image
4. Motion detection compares current frame to previous
5. If motion detected → OCR → Text-to-Speech
6. Images are saved to `captured_images/` folder

---

## Controls

| Key | Action |
|-----|--------|
| `Ctrl+C` | Stop the program |
| `q` (if display enabled) | Quit |

---

##  Performance

- Headless mode = no video display = faster processing
- Images saved only when motion detected
- TTS runs in separate thread = doesn't block capture

---

## Author

**Zaki** (zaki917)

Built as a Computer Engineering project to explore embedded systems, computer vision, and machine learning integration.

---

##  License

MIT - Free to use, modify, and distribute.

---

##  Credits

- Built with: ESP32-CAM, Python, OpenCV, Tesseract, pyttsx3
```

