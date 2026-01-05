# �️ LOGO Detection - Optimized Raspberry Pi Camera System

## Project Documentation for AI Training & Knowledge Transfer

> **Purpose**: This document serves as a comprehensive guide for AI models to understand, replicate, and extend the camera streaming and data collection system built for **LOGO detection** using YOLO on Raspberry Pi.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Hardware Requirements](#hardware-requirements)
3. [System Architecture](#system-architecture)
4. [Installation & Setup](#installation--setup)
5. [Core Algorithms & Design Decisions](#core-algorithms--design-decisions)
6. [API Reference](#api-reference)
7. [Image Preprocessing Pipeline](#image-preprocessing-pipeline)
8. [Configuration Parameters](#configuration-parameters)
9. [Logo Detection Optimization Strategy](#logo-detection-optimization-strategy)
10. [Video Recording System](#video-recording-system)
11. [Key Learnings & Iterations](#key-learnings--iterations)
12. [Future Improvements](#future-improvements)

---

## 1. Project Overview

### 1.1 Problem Statement
Build a real-time camera streaming system on Raspberry Pi that:
- Captures video frames optimized for **LOGO detection** using YOLO
- Provides multiple endpoints for different use cases (browser viewing, inference, data collection)
- Maintains consistent image quality through manual camera tuning
- Implements proper preprocessing (letterboxing, normalization) for neural network input
- **Preserves brand colors and sharp logo edges critical for detection**

### 1.2 Solution Summary
A Flask-based web server (`live_cam.py`) that:
- Uses `picamera2` library for Raspberry Pi camera control
- Implements threaded frame capture for low-latency streaming
- Provides YOLO-ready preprocessing with proper letterboxing
- Exposes RESTful API endpoints for various output formats
- **Optimized camera ISP settings specifically for logo feature preservation**

### 1.3 Target Platform
- **Hardware**: Raspberry Pi (tested on Pi 4/5)
- **OS**: Debian Trixie (ARM64)
- **Camera**: ArduCAM Pivariety / Raspberry Pi Camera Module
- **Python Version**: 3.x

---

## 2. Hardware Requirements

| Component | Specification | Purpose |
|-----------|--------------|---------|
| Raspberry Pi | Pi 4/5 (ARM64) | Main compute unit |
| Camera Module | ArduCAM Pivariety / Pi Camera | Image capture |
| Storage | SD Card with sufficient space | Image storage in `/home/ali/captured_images` |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SYSTEM ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌───────────────────────────────────────┐ │
│  │   Camera     │───▶│        CameraStream Class            │ │
│  │  (Picamera2) │    │  ┌─────────────────────────────────┐ │ │
│  └──────────────┘    │  │  Threaded Capture Loop          │ │ │
│                      │  │  - Continuous frame grab        │ │ │
│                      │  │  - Thread-safe frame storage    │ │ │
│                      │  └─────────────────────────────────┘ │ │
│                      │  ┌─────────────────────────────────┐ │ │
│                      │  │  Preprocessing Pipeline         │ │ │
│                      │  │  - Contrast stretch             │ │ │
│                      │  │  - Letterboxing                 │ │ │
│                      │  │  - Normalization                │ │ │
│                      │  └─────────────────────────────────┘ │ │
│                      └───────────────────────────────────────┘ │
│                                    │                            │
│                                    ▼                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Flask Web Server                       │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │  /         │  │ /video_feed│  │ /frame/yolo/tensor │  │  │
│  │  │  Web UI    │  │ MJPEG      │  │ Normalized NPY     │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ /frame     │  │ /frame/yolo│  │ /save_picture      │  │  │
│  │  │ Raw JPEG   │  │ Letterboxed│  │ Disk Storage       │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Installation & Setup

### 4.1 ArduCAM Pivariety Driver Installation

The project uses the ArduCAM Pivariety driver installation script (`install_pivariety_pkgs.sh`):

```bash
# Run the installer
chmod +x install_pivariety_pkgs.sh
./install_pivariety_pkgs.sh -p libcamera_trixie
./install_pivariety_pkgs.sh -p libcamera_apps_trixie
```

**What the script does:**
1. Detects hardware revision and OS codename
2. Configures I2C for camera communication
3. Downloads and installs appropriate libcamera packages
4. Sets up kernel drivers for specific camera sensors

### 4.2 Package Dependencies

Key packages installed (from `packages.txt` configuration):
- `libcamera0.5` - Core camera library for Trixie
- `rpicam-apps` - Camera applications package

### 4.3 Python Dependencies

```bash
pip install flask picamera2 pillow numpy
```

### 4.4 Boot Configuration

The installer modifies `/boot/config.txt`:
```
dtparam=i2c_vc=on
dtparam=i2c_arm=on
dtoverlay=arducam  # or specific camera overlay
```

---

## 5. Core Algorithms & Design Decisions

### 5.1 Threaded Frame Capture

**Problem**: Blocking camera reads cause high latency in web responses.

**Solution**: Separate capture thread continuously reads frames into a shared buffer.

```python
def _capture_loop(self):
    """Continuous frame capture for low latency"""
    while self.running:
        try:
            frame = self.picam2.capture_array()
            with self.frame_lock:
                self.frame = frame
        except Exception as e:
            print(f"Capture error: {e}")
            time.sleep(0.01)
```

**Key Design Decisions**:
- **Thread Lock**: `threading.Lock()` ensures thread-safe frame access
- **Daemon Thread**: `daemon=True` ensures clean shutdown
- **Buffer Count**: `buffer_count=4` in camera config for smooth streaming

### 5.2 Contrast Stretching Algorithm

**Problem**: Variable lighting conditions cause inconsistent YOLO detections.

**Solution**: Per-channel percentile-based contrast normalization.

```python
@staticmethod
def _contrast_stretch(frame: np.ndarray) -> np.ndarray:
    """Simple per-channel percentile stretch to stabilize lighting"""
    frame_f = frame.astype(np.float32)
    lows = np.percentile(frame_f, 2, axis=(0, 1)).reshape(1, 1, 3)
    highs = np.percentile(frame_f, 98, axis=(0, 1)).reshape(1, 1, 3)
    stretched = (frame_f - lows) / (highs - lows + 1e-3)
    stretched = np.clip(stretched, 0.0, 1.0)
    return (stretched * 255.0).astype(np.uint8)
```

**Algorithm Breakdown**:
1. Convert to float32 for precision
2. Calculate 2nd and 98th percentiles per channel (R, G, B)
3. Stretch values to fill 0-255 range
4. Clip outliers and convert back to uint8

**Why 2% and 98%**: Ignores extreme outliers (highlights/shadows) that would skew normalization.

### 5.3 Letterboxing for YOLO

**Problem**: YOLO requires square input (640×640), but camera captures 16:9 (1280×720).

**Solution**: Aspect-ratio preserving resize with black padding.

```python
@staticmethod
def _letterbox(frame: np.ndarray, target_size: tuple[int, int]) -> tuple[np.ndarray, dict]:
    """Resize with aspect-ratio preservation and black padding"""
    target_w, target_h = target_size
    image = Image.fromarray(frame)
    
    # Resize to fit within target while preserving aspect ratio
    contained = ImageOps.contain(image, (target_w, target_h), method=Image.BICUBIC)
    
    # Create black canvas and center the resized image
    canvas = Image.new("RGB", (target_w, target_h), color=(0, 0, 0))
    offset = ((target_w - contained.width) // 2, (target_h - contained.height) // 2)
    canvas.paste(contained, offset)
    
    # Return metadata for bounding box coordinate reversal
    meta = {
        "scale": contained.width / image.width,
        "pad": offset,
        "original_size": image.size,
    }
    return np.array(canvas), meta
```

**Critical Metadata**:
- `scale`: Ratio for converting YOLO bbox coordinates back to original
- `pad`: Pixel offset to subtract from YOLO coordinates
- `original_size`: Original dimensions for validation

**Visual Representation**:
```
Input (1280×720, 16:9):          Output (640×640, square):
┌────────────────────────┐       ┌──────────────────────┐
│                        │       │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│ ← Black pad
│      Camera Frame      │  ───▶ │                      │
│                        │       │   Resized Frame      │
│                        │       │                      │
└────────────────────────┘       │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│ ← Black pad
                                 └──────────────────────┘
```

### 5.4 ImageNet Normalization

**Problem**: YOLO models trained on ImageNet expect specific input normalization.

**Solution**: Apply ImageNet mean/std normalization and convert to CHW format.

```python
@staticmethod
def _normalize(frame: np.ndarray) -> np.ndarray:
    """Normalize frame to CHW float32 tensor using ImageNet stats"""
    mean = np.array(config.NORMALIZE_MEAN, dtype=np.float32)  # (0.485, 0.456, 0.406)
    std = np.array(config.NORMALIZE_STD, dtype=np.float32)    # (0.229, 0.224, 0.225)
    
    tensor = frame.astype(np.float32) / 255.0  # Scale to [0, 1]
    tensor = (tensor - mean) / std              # Apply normalization
    return np.transpose(tensor, (2, 0, 1))      # HWC → CHW
```

**Why ImageNet Stats**: Most pretrained YOLO backbones use these values.

---

## 6. API Reference

### 6.1 Endpoints Summary

| Endpoint | Method | Returns | Use Case |
|----------|--------|---------|----------|
| `/` | GET | HTML | Web interface with live preview |
| `/video_feed` | GET | MJPEG Stream | Real-time browser viewing |
| `/frame` | GET | JPEG | Simple frame grab |
| `/frame/raw` | GET | NumPy .npy | Raw sensor data |
| `/frame/yolo` | GET | JPEG + Headers | Preprocessed frame for YOLO |
| `/frame/yolo/tensor` | GET | NumPy .npy | Ready-to-infer tensor |
| `/frame/numpy` | GET | JSON | Frame metadata |
| `/save_picture` | POST | JSON | Save to disk |
| `/status` | GET | JSON | Camera status |
| `/record/start` | POST | JSON | Start video recording (live_cam_normal.py) |
| `/record/stop` | POST | JSON | Stop video recording |
| `/record/status` | GET | JSON | Get recording status |

### 6.2 YOLO Integration Examples

**Simple Detection (Using /frame)**:
```python
import requests
from PIL import Image
import io

resp = requests.get('http://raspberry-pi:5000/frame')
img = Image.open(io.BytesIO(resp.content))
results = model(img)
```

**Optimized Detection (Using /frame/yolo/tensor)**:
```python
import requests
import numpy as np

resp = requests.get('http://raspberry-pi:5000/frame/yolo/tensor')
data = np.load(io.BytesIO(resp.content), allow_pickle=True).item()
tensor = data['tensor']  # Shape: (3, 640, 640)
meta = data['meta']      # Contains scale and padding info

# Add batch dimension and run inference
input_tensor = np.expand_dims(tensor, axis=0)
results = model(input_tensor)

# Reverse letterbox to get original coordinates
# bbox_original = (bbox_yolo - meta['pad']) / meta['scale']
```

---

## 7. Image Preprocessing Pipeline

### 7.1 Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PREPROCESSING PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Step 1: Capture                    Step 2: Contrast Stretch            │
│  ┌─────────────────────┐            ┌─────────────────────┐             │
│  │ BGR888 @ 1920×1080  │ ────────▶  │ Percentile-based    │             │
│  │ From sensor         │            │ per-channel stretch │             │
│  └─────────────────────┘            └─────────────────────┘             │
│                                              │                          │
│                                              ▼                          │
│  Step 3: Letterbox                  Step 4: Normalize (optional)        │
│  ┌─────────────────────┐            ┌─────────────────────┐             │
│  │ Resize + black pad  │ ────────▶  │ ImageNet mean/std   │             │
│  │ → 640×640 square    │            │ HWC → CHW format    │             │
│  └─────────────────────┘            └─────────────────────┘             │
│                                              │                          │
│                                              ▼                          │
│                                     ┌─────────────────────┐             │
│                                     │ Output: float32     │             │
│                                     │ Shape: (3, 640, 640)│             │
│                                     │ Ready for YOLO      │             │
│                                     └─────────────────────┘             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Method Selection Guide

| Method | When to Use |
|--------|-------------|
| `get_frame()` | Raw viewing, debugging |
| `get_frame_jpeg()` | Browser streaming, quick preview |
| `get_frame_for_yolo()` | YOLO inference (returns numpy + metadata) |
| `get_yolo_tensor()` | Direct inference with normalized tensor |

---

## 8. Configuration Parameters

### 8.1 Camera Configuration (Logo-Optimized)

```python
class Config:
    # Resolution Settings - Higher for logo detail
    SENSOR_SIZE = (1920, 1080)  # Full HD for maximum logo detail
    YOLO_SIZE = (640, 640)      # Standard (1280×1280 for better small object detection)
    FRAME_RATE = 30             # Frames per second
    
    # Quality Settings - Maximum for logo preservation
    JPEG_QUALITY = 95           # High quality for sharp edges
    
    # Storage
    SAVE_FOLDER = "/home/ali/captured_images"
```

### 8.2 Manual Camera Tuning (Logo-Optimized)

**Why Manual Tuning**: Auto exposure/white balance causes frame-to-frame variation, hurting detection consistency. For logos, color accuracy is critical for brand recognition.

```python
# Manual exposure control - fast shutter for sharp logo edges
USE_MANUAL_TUNING = True
EXPOSURE_TIME_US = 10000    # 0.010s shutter (fast for motion)
ANALOG_GAIN = 1.5           # Low gain = less noise = cleaner logo details

# White balance (manual color gains) - neutral for accurate brand colors
COLOUR_GAINS = (1.45, 1.05) # (Red multiplier, Blue multiplier)
                             # Tuned for neutral whites under your lighting

# ISP (Image Signal Processor) - Logo-optimized enhancements
ISP_SHARPNESS = 1.4         # Enhanced for logo edge definition and text
ISP_CONTRAST = 1.05         # Slight boost, preserve logo gradients
ISP_SATURATION = 1.1        # Brand color visibility boost
NOISE_REDUCTION_MODE = 2    # High quality denoising for clean details
```

### 8.3 Contrast Stretch Configuration

```python
# Logo-specific contrast stretch settings
# Less aggressive to preserve true brand colors
CONTRAST_STRETCH_ENABLED = True   # Set False for color-critical logos
CONTRAST_PERCENTILE_LOW = 1       # Less aggressive (standard: 2)
CONTRAST_PERCENTILE_HIGH = 99     # Less aggressive (standard: 98)
```

**Tuning Process for Logos**:
1. Start with `CONTRAST_STRETCH_ENABLED = False` to see true colors
2. If lighting varies significantly, enable with 1%-99% settings
3. Adjust `COLOUR_GAINS` until white objects appear neutral
4. Verify brand colors match expected values
5. Fine-tune `ISP_SHARPNESS` until logo text is crisp (watch for halos)

### 8.4 Normalization Constants

```python
# ImageNet defaults - used by most pretrained YOLO models
NORMALIZE_MEAN = (0.485, 0.456, 0.406)  # Per-channel mean
NORMALIZE_STD = (0.229, 0.224, 0.225)   # Per-channel std
```

**Note**: If using a custom-trained model, replace with your dataset's statistics.

---

## 9. Logo Detection Optimization Strategy

### 9.1 Why Logos Are Challenging for Detection

| Challenge | Impact | Our Solution |
|-----------|--------|--------------|
| **Small Object Size** | Logos often occupy <5% of frame | Higher capture resolution (1920×1080) |
| **Fine Text/Details** | Text in logos needs pixel-level clarity | Enhanced sharpness (1.4), low noise |
| **Brand Colors** | Distinctive colors are key features | Accurate white balance, controlled saturation |
| **Sharp Edges** | Logo boundaries define shape | Fast shutter, high sharpness |
| **Variable Lighting** | Real-world deployment varies | Manual exposure control |
| **Reflective Surfaces** | Logos on shiny materials glare | Controlled exposure to prevent blowout |

### 9.2 Camera Parameter Optimization Rationale

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 LOGO DETECTION OPTIMIZATION MATRIX                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PARAMETER          │ VALUE    │ RATIONALE                              │
│  ───────────────────┼──────────┼────────────────────────────────────────│
│  SENSOR_SIZE        │ 1920×1080│ More pixels = more logo detail         │
│  EXPOSURE_TIME_US   │ 10000    │ Fast shutter prevents motion blur      │
│  ANALOG_GAIN        │ 1.5      │ Low gain = less noise = cleaner edges  │
│  ISP_SHARPNESS      │ 1.4      │ Crisp logo edges and text              │
│  ISP_CONTRAST       │ 1.05     │ Slight boost, preserve gradients       │
│  ISP_SATURATION     │ 1.1      │ Brand colors pop without distortion    │
│  COLOUR_GAINS       │ (1.45,   │ Neutral whites for accurate colors     │
│                     │  1.05)   │                                        │
│  NOISE_REDUCTION    │ 2 (High) │ Clean details for small text           │
│  JPEG_QUALITY       │ 95       │ Maximum detail preservation            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Why These Specific Values?

#### Resolution: 1920×1080 (Full HD)
```
Logo at 100px in 720p frame  →  Logo occupies ~1.3% of pixels
Logo at 100px in 1080p frame →  Same logo occupies ~0.9% BUT more detail captured

After letterboxing to 640×640:
- 720p source:  Logo effective size ≈ 88px in YOLO input
- 1080p source: Logo effective size ≈ 59px BUT sharper due to better downsampling

Higher source resolution = better feature quality after resize
```

#### Sharpness: 1.4 (40% boost)
```
Before sharpening:          After sharpening (1.4):
┌─────────────┐             ┌─────────────┐
│   LOGO      │             │   LOGO      │
│  (blurry)   │      →      │  (CRISP)    │
│  edges fade │             │  edges POP  │
└─────────────┘             └─────────────┘

Critical for: Text in logos, geometric shapes, brand symbols
Caution: >1.6 creates halo artifacts
```

#### Exposure: 10000µs (10ms)
```
Problem: Motion blur destroys logo edges
         ┌───────────┐
         │ L O G O   │  ← Readable
         └───────────┘
         
         ┌───────────┐
         │ ████████  │  ← Blurred (unusable)
         └───────────┘

Solution: Fast shutter (10ms) freezes motion
          Compensate with controlled gain (1.5) and good lighting
```

#### Saturation: 1.1 (10% boost)
```
Brand colors are FEATURES for logo detection!

Example - Coca-Cola Red:
  Raw capture:     rgb(200, 35, 30)  ← Slightly muted
  With sat=1.1:    rgb(220, 30, 25)  ← Distinct red, matches brand

Why not higher?
  sat=1.3+:        rgb(255, 20, 15)  ← Over-saturated, color clipping
                   Loses accuracy, creates artifacts
```

### 9.4 Contrast Stretch Consideration for Logos

**Important Trade-off**:

```
Standard Contrast Stretch (2%-98% percentile):
┌─────────────────────────────────────────────────────────┐
│ PROS                    │ CONS                          │
├─────────────────────────┼───────────────────────────────┤
│ ✓ Normalizes lighting   │ ✗ Shifts brand colors         │
│ ✓ Consistent input      │ ✗ Blue logo may become cyan   │
│ ✓ Handles shadows       │ ✗ Per-frame variation         │
└─────────────────────────┴───────────────────────────────┘

For Logo Detection:
→ Use LESS aggressive stretching (1%-99%)
→ OR disable entirely (CONTRAST_STRETCH_ENABLED = False)
→ Rely on camera ISP for consistent exposure instead
```

### 9.5 Data Collection Best Practices for Logo Training

#### Capture Diversity Checklist:
```
□ Multiple distances (close-up, medium, far)
□ Various angles (0°, 15°, 30°, 45°)
□ Different lighting (daylight, indoor, mixed)
□ Partial occlusion (logo partially covered)
□ Multiple backgrounds (cluttered, plain)
□ Various logo scales in frame (5%, 10%, 20%, 50%)
□ Real-world blur (slight motion, out of focus edges)
```

#### Recommended Dataset Structure:
```
captured_images/
├── close_up/           # Logo fills >30% of frame
├── medium_distance/    # Logo fills 10-30% of frame
├── far_distance/       # Logo fills <10% of frame
├── angled/             # Non-frontal views
├── partial_occlusion/  # Partially visible logos
├── various_lighting/   # Different light conditions
└── negatives/          # Images WITHOUT logos (hard negatives)
```

### 9.6 Comparison: General YOLO vs Logo-Optimized Settings

| Parameter | General YOLO | Logo-Optimized | Why Different |
|-----------|--------------|----------------|---------------|
| Resolution | 1280×720 | 1920×1080 | Logos are small, need detail |
| Sharpness | 1.0 | 1.4 | Text and edges critical |
| Contrast | 1.15 | 1.05 | Preserve logo gradients |
| Saturation | 1.05 | 1.1 | Brand colors are features |
| Exposure | 12000µs | 10000µs | Freeze motion for sharp edges |
| Gain | 1.8 | 1.5 | Less noise in fine details |
| Contrast Stretch | 2%-98% | 1%-99% or OFF | Preserve true colors |
| JPEG Quality | 85 | 95 | Maximum detail retention |

---

## 10. Video Recording System

### 10.1 Overview

The `live_cam_normal.py` includes a high-quality video recording system using the Raspberry Pi's hardware H.264 encoder.

**Key Features:**
- Hardware-accelerated H.264 encoding
- Full HD resolution (1920×1080)
- High bitrate (15 Mbps) for maximum quality
- Automatic MP4 container wrapping via FFmpeg
- Thread-safe recording controls
- Web interface with recording controls (press R)

### 10.2 Video Recording Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     VIDEO RECORDING PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────────────┐  │
│  │   Camera     │───▶│  H264Encoder   │───▶│  FileOutput (.h264)     │  │
│  │  Main Stream │    │  15 Mbps HW    │    │  Raw H.264 stream       │  │
│  └──────────────┘    └────────────────┘    └─────────────────────────┘  │
│                                                       │                 │
│                                                       ▼                 │
│                                            ┌─────────────────────────┐  │
│                                            │  FFmpeg (on stop)       │  │
│                                            │  Wrap in MP4 container  │  │
│                                            │  -c copy (no re-encode) │  │
│                                            └─────────────────────────┘  │
│                                                       │                 │
│                                                       ▼                 │
│                                            ┌─────────────────────────┐  │
│                                            │  Final .mp4 file        │  │
│                                            │  /home/ali/CAMERA_NORMAL│  │
│                                            │  /videos/               │  │
│                                            └─────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Why This Approach?

| Design Decision | Rationale |
|-----------------|------------|
| **H.264 Hardware Encoder** | Uses Pi's VideoCore GPU, minimal CPU usage |
| **Raw .h264 + FFmpeg** | More reliable than direct MP4 output |
| **15 Mbps Bitrate** | High quality without excessive file size |
| **1920×1080 Resolution** | Full HD for maximum detail |
| **FileOutput** | Simple, reliable file writing |
| **Post-processing Conversion** | FFmpeg wraps H.264 in MP4 container without re-encoding |

### 10.4 Recording Configuration

```python
class Config:
    # Video Recording Settings
    VIDEO_SIZE = (1920, 1080)    # Full HD resolution
    VIDEO_BITRATE = 15000000     # 15 Mbps (range: 10-25 Mbps)
    VIDEO_FPS = 30               # Frames per second
    VIDEO_FOLDER = "/home/ali/CAMERA_NORMAL/videos"
```

**Bitrate Guidelines:**
| Quality Level | Bitrate | Use Case |
|---------------|---------|----------|
| Standard | 5-8 Mbps | General surveillance |
| High | 10-15 Mbps | Detail preservation |
| Maximum | 20-25 Mbps | Critical recording |

### 10.5 API Usage

**Start Recording:**
```bash
curl -X POST http://localhost:5000/record/start
# Response: {"success": true, "filename": "video_20260105_143022.mp4"}
```

**Stop Recording:**
```bash
curl -X POST http://localhost:5000/record/stop
# Response: {"success": true, "filename": "video_20260105_143022.mp4", "duration": 45.2}
```

**Check Status:**
```bash
curl http://localhost:5000/record/status
# Response: {"recording": true, "filename": "...", "duration": 12.5, "resolution": "1920x1080"}
```

### 10.6 Web Interface Controls

The web interface at `http://localhost:5000` provides:
- **Press R** or click 🎬 Record button to start/stop recording
- Visual recording indicator with duration timer
- Recording status display (filename, duration)

### 10.7 Recording Code Flow

```python
# Start Recording
def start_recording(self, filename=None):
    # 1. Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"video_{timestamp}.mp4"
    
    # 2. Create H.264 encoder with high bitrate
    self.encoder = H264Encoder(bitrate=config.VIDEO_BITRATE)
    
    # 3. Output raw H.264 to temp file
    self.output = FileOutput(self.h264_path)
    
    # 4. Start encoding from main camera stream
    self.picam2.start_encoder(self.encoder, self.output, name="main")

# Stop Recording
def stop_recording(self):
    # 1. Stop the encoder
    self.picam2.stop_encoder()
    
    # 2. Convert H.264 to MP4 using FFmpeg
    cmd = ['ffmpeg', '-y', '-framerate', '30',
           '-i', h264_path, '-c', 'copy', mp4_path]
    subprocess.run(cmd)
    
    # 3. Remove temp .h264 file
    os.remove(h264_path)
```

### 10.8 Dependencies

- **FFmpeg**: Required for H.264 to MP4 conversion
  ```bash
  sudo apt install ffmpeg
  ```

---

## 11. Key Learnings & Iterations

### 11.1 Problem: Frame Drops During Stream

**Initial Approach**: Direct capture in request handler
**Issue**: Each request blocked on camera read (40-100ms)
**Solution**: Background capture thread + frame buffer
```python
# Before: Blocking (high latency)
@app.route('/frame')
def get_frame():
    frame = camera.capture_array()  # BLOCKS
    return Response(frame_to_jpeg(frame))

# After: Non-blocking (low latency)
# Capture loop runs independently
# Handler just reads latest frame from buffer
```

### 10.2 Problem: Distorted Aspect Ratio

**Initial Approach**: Simple resize to 640×640
**Issue**: Objects appeared stretched, harming detection accuracy
**Solution**: Letterboxing with metadata for coordinate reversal

### 10.3 Problem: Color Shift Between Frames

**Initial Approach**: Auto white balance (AWB)
**Issue**: AWB continuously adjusted, causing color flicker
**Solution**: Manual color gains tuned to environment
```python
"ColourGains": (1.55, 1.0)  # Fixed R/B multipliers
```

### 10.4 Problem: Low-Light Performance

**Initial Approach**: Auto exposure
**Issue**: Long exposures caused motion blur
**Solution**: Fixed exposure + increased analog gain
```python
"ExposureTime": 12000,   # Fast shutter
"AnalogueGain": 1.8,     # Compensate with gain
```

### 10.5 Problem: High Dynamic Range Scenes

**Initial Approach**: No preprocessing
**Issue**: Shadows/highlights clipped, poor detection in mixed lighting
**Solution**: Percentile-based contrast stretch normalizes dynamic range

---

## 12. Future Improvements

### 12.1 Recommended Enhancements

1. **GPU Acceleration**: Move preprocessing to GPU using OpenCV CUDA or TensorRT
2. ~~**Hardware Encoding**: Use Pi's hardware H.264 encoder for efficient streaming~~ ✅ DONE
3. **Multiple Camera Support**: Extend `CameraStream` class for synchronized capture
4. **Detection Overlay**: Add real-time bounding box overlay on video stream
5. ~~**Recording Mode**: Add video recording with timestamps~~ ✅ DONE
6. **Dynamic Tuning API**: Expose camera parameters via REST endpoints
7. **Recording to live_cam.py**: Port video recording feature to logo-optimized camera

### 12.2 Alternative Approaches Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| OpenCV VideoCapture | Familiar API | Less control on Pi | Rejected - Picamera2 better |
| GStreamer Pipeline | Hardware accel | Complex setup | Future consideration |
| libcamera direct | Low-level control | No Python binding | Use picamera2 wrapper |
| Multi-process | True parallelism | IPC overhead | Threads sufficient |

---

## 13. Code Structure Reference

### 13.1 File Layout

```
/home/ali/
├── live_cam.py                    # Main camera server - LOGO optimized (Flask + Picamera2)
├── live_cam_normal.py             # Normal display mode - Auto settings + VIDEO RECORDING
├── test_color_config.py           # Color format diagnostic tool (RGB vs BGR testing)
├── data_collector.py              # Data collection utility (empty/WIP)
├── PROJECT_DOCUMENTATION.md       # This documentation file
├── install_pivariety_pkgs.sh      # ArduCAM driver installer
├── packages.txt                   # Package configuration
├── libcamera_trixie_links.txt     # libcamera package URLs
├── libcamera_apps_trixie_links.txt # rpicam-apps package URLs
├── captured_images/               # Stored captures (from live_cam.py)
├── CAMERA_NORMAL/                 # Stored captures (from live_cam_normal.py)
│   └── videos/                    # Recorded videos (.mp4 files)
├── color_test/                    # Color format test images
└── rpicam-apps_1.9.1-2_arm64_trixie/  # Installed camera apps
```

### 13.2 Class Hierarchy

```
CameraStream (live_cam.py - Logo Optimized)
├── __init__()           # Initialize Picamera2
├── _configure_camera()  # Set resolution, format, buffers
├── _apply_runtime_controls()  # ISP and exposure settings
├── start()              # Begin capture thread
├── _capture_loop()      # Background frame grabber
├── get_frame()          # Raw frame access (thread-safe)
├── get_frame_jpeg()     # JPEG encoding
├── get_frame_for_yolo() # Contrast stretch + letterbox
├── get_yolo_tensor()    # Full normalization pipeline
├── save_frame()         # Disk persistence
└── stop()               # Cleanup

CameraStream (live_cam_normal.py - Normal Mode + Recording)
├── __init__()           # Initialize Picamera2 + recording state
├── _configure_camera()  # Auto settings configuration
├── start()              # Begin capture with autofocus
├── _capture_loop()      # Background frame grabber
├── get_frame()          # Raw frame access (thread-safe)
├── get_frame_jpeg()     # JPEG encoding
├── save_frame()         # Photo capture to disk
├── start_recording()    # Begin H.264 video recording
├── stop_recording()     # Stop recording + FFmpeg conversion
├── get_recording_status()  # Current recording state
└── stop()               # Cleanup (stops recording if active)
```

---

## 14. Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Camera not found" | I2C not enabled | Run `sudo dtparam i2c_arm=on` |
| Green tint | Wrong color gains | Adjust `COLOUR_GAINS` |
| Motion blur | Exposure too long | Reduce `EXPOSURE_TIME_US` |
| Dark images | Low gain | Increase `ANALOG_GAIN` |
| High latency | No buffer | Increase `buffer_count` |
| **Colors inverted (blue/red swap)** | Wrong pixel format | Use `BGR888` instead of `RGB888` |
| **Blurry images** | No autofocus | Enable `AfMode: 2` (continuous) |
| **Camera busy error** | Another process using camera | Run `pkill -f python3` first |
| **Video recording no file** | FFmpeg not installed | Install: `sudo apt install ffmpeg` |
| **Recording stuck** | Encoder not stopped | Restart camera script |
| **MP4 not playing** | Corrupted stream | Check if .h264 file exists as fallback |

### Color Format Diagnosis

If colors appear wrong, run the diagnostic script:
```bash
python3 test_color_config.py
```
This creates test images in `/home/ali/color_test/` with different format interpretations.

---

## 15. Summary for AI Models

### Quick Start Checklist

1. **Platform**: Raspberry Pi 4/5, Debian Trixie, ARM64
2. **Camera**: ArduCAM Pivariety with custom libcamera drivers
3. **Core Library**: `picamera2` for camera control
4. **Web Framework**: Flask with threaded mode
5. **Key Innovation**: Threaded capture + LOGO-optimized preprocessing pipeline
6. **Preprocessing**: Optional contrast stretch → Letterbox → ImageNet normalize
7. **Output Formats**: JPEG, NumPy arrays, normalized tensors

### Logo Detection Key Settings

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Resolution | 1920×1080 | Maximum logo detail |
| Sharpness | 1.4 | Crisp edges and text |
| Saturation | 1.1 | Brand color visibility |
| Exposure | 10000µs | Freeze motion |
| Gain | 1.5 | Low noise |
| Contrast Stretch | 1%-99% | Preserve true colors |

### Replication Steps

1. Install ArduCAM drivers via `install_pivariety_pkgs.sh`
2. Install Python deps: `flask`, `picamera2`, `pillow`, `numpy`
3. Copy `live_cam.py` to target
4. **Tune Config for your logo use case:**
   - Adjust `COLOUR_GAINS` with white reference card
   - Set `CONTRAST_STRETCH_ENABLED = False` for color-critical logos
   - Increase `YOLO_SIZE` to 1280×1280 if GPU allows
5. Run `python3 live_cam.py`
6. Access at `http://localhost:5000`
7. Collect diverse training data (angles, distances, lighting)

### Critical Understanding for Logo Detection

```
LOGO DETECTION = Small Object Detection + Color Accuracy + Edge Sharpness

Key insight: Logos are NOT like general objects
- They're often SMALL (< 10% of frame)
- They have DISTINCTIVE COLORS (brand identity)
- They contain FINE DETAILS (text, symbols)
- They require SHARP EDGES (geometric shapes)

Therefore:
✓ Higher resolution capture (more pixels for small objects)
✓ Enhanced sharpness (edge detection critical)
✓ Accurate colors (saturation boost, proper white balance)
✓ Low noise (fine details preserved)
✓ Less aggressive preprocessing (preserve true colors)
```

---

## 16. Changelog

### Version 2.2 (January 5, 2026)

#### 🎬 Video Recording Feature
- **Added**: Full video recording capability to `live_cam_normal.py`
- **Encoder**: Hardware-accelerated H.264 via Raspberry Pi VideoCore
- **Quality**: Full HD 1920×1080 at 15 Mbps bitrate
- **Format**: Records to .h264, auto-converts to .mp4 via FFmpeg
- **Storage**: Videos saved to `/home/ali/CAMERA_NORMAL/videos/`

#### 📡 New API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|--------|
| `/record/start` | POST | Start video recording |
| `/record/stop` | POST | Stop recording, returns file info |
| `/record/status` | GET | Current recording status |

#### 🖥️ Web Interface Updates
- Added recording button (🎬 Record) with keyboard shortcut (R)
- Recording status indicator with live duration timer
- Visual feedback (pulsing red) when recording active

#### 🔧 Technical Implementation
```python
# Recording Flow:
1. H264Encoder(bitrate=15000000)  # 15 Mbps HW encoder
2. FileOutput(path.h264)          # Raw H.264 stream
3. picam2.start_encoder()         # Begin recording
4. ... recording ...
5. picam2.stop_encoder()          # Stop recording
6. FFmpeg: .h264 → .mp4           # Container conversion
7. Remove temp .h264 file
```

#### 📦 Dependencies Added
- **FFmpeg**: Required for H.264 to MP4 conversion
  ```bash
  sudo apt install ffmpeg
  ```

---

### Version 2.1 (January 5, 2026)

#### 🎨 Color Format Fix
- **Changed**: Pixel format from `RGB888` → `BGR888`
- **Reason**: IMX519 sensor on this ArduCAM outputs BGR order
- **Diagnosis**: Created `test_color_config.py` to test all format combinations
- **Result**: Correct natural colors (skin tones, brand colors accurate)

#### 🔍 Autofocus Support Added
- **Added**: Continuous autofocus (`AfMode: 2`)
- **Added**: Fast autofocus speed (`AfSpeed: 1`)
- **Applies to**: Both `live_cam.py` and `live_cam_normal.py`
- **Benefit**: Sharp logos at varying distances without manual focus

#### 📁 New Files Created
| File | Purpose |
|------|--------|
| `live_cam_normal.py` | Simple camera stream with auto settings (no preprocessing) |
| `test_color_config.py` | Diagnostic tool to find correct color format |

#### 📂 Storage Locations
| Script | Save Folder |
|--------|------------|
| `live_cam.py` | `/home/ali/captured_images/` |
| `live_cam_normal.py` | `/home/ali/CAMERA_NORMAL/` |

#### 🔧 Configuration Updates
```python
# Camera format (both files)
format = "BGR888"  # Changed from RGB888

# Autofocus settings (both files)
AfMode = 2         # Continuous autofocus
AfSpeed = 1        # Fast response

# live_cam.py additions
AUTOFOCUS_ENABLED = True
AUTOFOCUS_MODE = 2
```

### Version 2.0 (January 5, 2026)
- Initial logo detection optimization
- Higher resolution (1920×1080)
- Enhanced sharpness, saturation
- Configurable contrast stretch

---

*Document Version: 2.2 - Video Recording Feature*  
*Last Updated: January 5, 2026*  
*Author: AI-Generated Documentation*
