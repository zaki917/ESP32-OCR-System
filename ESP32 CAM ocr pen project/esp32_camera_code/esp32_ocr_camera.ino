/*
 * ESP32-CAM OCR System
 * 
 * This code runs on the ESP32-CAM module.
 * It captures JPEG images and sends them over serial (USB).
 * 
 * Hardware: ESP32-CAM with OV2640 camera
 * Baud rate: 115200
 * 
 * Protocol:
 * - Sends "IMG_START" marker before each image
 * - Sends 4-byte image size (little-endian)
 * - Sends raw JPEG bytes
 * - Sends "IMG_END" marker after each image
 */

#include "esp_camera.h"

// Camera pin definitions for ESP32-CAM
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // Camera configuration
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Smaller resolution = faster transmission
  config.frame_size = FRAMESIZE_CIF;     // 400x296
  config.jpeg_quality = 15;              // Higher = more compression
  config.fb_count = 1;
  
  // Init camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    delay(1000);
    ESP.restart();
  }
  
  // Ready signal
  Serial.println("READY");
}

void loop() {
  static unsigned long last_capture = 0;
  
  // Capture image every 3 seconds
  if (millis() - last_capture > 3000) {
    Serial.println("IMG_START");
    
    camera_fb_t *fb = esp_camera_fb_get();
    
    if (fb) {
      // Send image size (4 bytes, little-endian)
      uint32_t img_size = fb->len;
      Serial.write((uint8_t*)&img_size, 4);
      Serial.flush();
      
      // Send image data in 1KB chunks
      size_t sent = 0;
      while (sent < fb->len) {
        size_t chunk_size = min((size_t)1024, fb->len - sent);
        size_t written = Serial.write(fb->buf + sent, chunk_size);
        sent += written;
        Serial.flush();
        delay(1);  // Small delay to prevent buffer overflow
      }
      
      Serial.println("IMG_END");
      esp_camera_fb_return(fb);
    } else {
      Serial.println("IMG_ERROR");
    }
    
    last_capture = millis();
  }
  
  delay(100);
}