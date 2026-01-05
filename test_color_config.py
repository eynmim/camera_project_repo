#!/usr/bin/env python3
"""
Camera Color Configuration Test Script
=======================================
This script tests different color format configurations to find
the correct setup for your camera.

Run this to diagnose color issues (RGB vs BGR, etc.)
"""

from picamera2 import Picamera2
from PIL import Image
import numpy as np
import os
import time

# Create test output folder
TEST_FOLDER = "/home/ali/color_test"
os.makedirs(TEST_FOLDER, exist_ok=True)

print("=" * 60)
print("🎨 Camera Color Configuration Test")
print("=" * 60)

# Initialize camera
picam2 = Picamera2()

# Test different format configurations
FORMATS_TO_TEST = [
    "RGB888",
    "BGR888",
    "XRGB8888",
    "XBGR8888",
]

print("\n📷 Testing different pixel formats...\n")

for fmt in FORMATS_TO_TEST:
    try:
        print(f"Testing format: {fmt}")
        
        # Configure camera with this format
        config = picam2.create_video_configuration(
            main={
                "size": (640, 480),
                "format": fmt
            }
        )
        picam2.configure(config)
        picam2.start()
        
        # Wait for camera to stabilize
        time.sleep(1)
        
        # Capture frame
        frame = picam2.capture_array()
        
        picam2.stop()
        
        # Save as-is (no conversion)
        img_raw = Image.fromarray(frame)
        img_raw.save(f"{TEST_FOLDER}/{fmt}_raw.jpg")
        
        # If format has 4 channels (XRGB/XBGR), handle it
        if frame.shape[2] == 4:
            # Remove alpha channel
            frame = frame[:, :, :3]
        
        # Save with different interpretations
        # As RGB (direct)
        img_rgb = Image.fromarray(frame, mode='RGB')
        img_rgb.save(f"{TEST_FOLDER}/{fmt}_as_RGB.jpg")
        
        # As BGR (swapped)
        frame_swapped = frame[:, :, ::-1]  # Reverse channel order
        img_bgr = Image.fromarray(frame_swapped, mode='RGB')
        img_bgr.save(f"{TEST_FOLDER}/{fmt}_swapped.jpg")
        
        print(f"  ✅ Saved: {fmt}_raw.jpg, {fmt}_as_RGB.jpg, {fmt}_swapped.jpg")
        print(f"     Shape: {frame.shape}, dtype: {frame.dtype}")
        
        # Print sample pixel values for debugging
        center_y, center_x = frame.shape[0] // 2, frame.shape[1] // 2
        pixel = frame[center_y, center_x]
        print(f"     Center pixel (raw): R/Ch0={pixel[0]}, G/Ch1={pixel[1]}, B/Ch2={pixel[2]}")
        
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        try:
            picam2.stop()
        except:
            pass

print("\n" + "=" * 60)
print("📁 Test images saved to:", TEST_FOLDER)
print("=" * 60)

print("""
🔍 HOW TO INTERPRET RESULTS:
============================

1. Open the test images in: /home/ali/color_test/

2. Look at each image and find which one shows CORRECT colors:
   - If skin looks orange/blue → wrong channel order
   - If colors look natural → correct format found

3. For each format, we saved:
   - *_raw.jpg      → Direct from camera
   - *_as_RGB.jpg   → Interpreted as RGB
   - *_swapped.jpg  → Channels reversed (BGR↔RGB)

4. Once you find the correct combination, update your config:

   If "RGB888_as_RGB.jpg" looks correct:
       format = "RGB888"
       # No swap needed
   
   If "RGB888_swapped.jpg" looks correct:
       format = "RGB888"  
       frame = frame[:, :, ::-1]  # Add this line after capture
   
   If "BGR888_as_RGB.jpg" looks correct:
       format = "BGR888"
       frame = frame[:, :, ::-1]  # Swap to RGB

COMMON FIXES:
=============
- Picamera2 with "RGB888" usually gives correct RGB order
- If colors are inverted (blue faces, etc.), add channel swap:
  
  frame = frame[:, :, ::-1]  # BGR to RGB
  
  OR use "BGR888" format and swap to RGB
""")

# Cleanup
picam2.close()
print("\n✅ Test complete! Check the images in", TEST_FOLDER)
