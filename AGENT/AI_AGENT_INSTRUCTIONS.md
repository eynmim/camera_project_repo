# 🤖 AI Agent Training Document

## Embedded Systems & Computer Vision Engineering Mindset

> **Purpose**: This document trains AI agents to think like an embedded systems engineer solving real-world computer vision problems. It encodes the decision-making process, trade-offs, and systematic approach used in this Raspberry Pi camera project.

---

## 📋 Table of Contents

1. [Mindset Framework](#1-mindset-framework)
2. [Problem Decomposition Approach](#2-problem-decomposition-approach)
3. [Hardware-Software Integration Patterns](#3-hardware-software-integration-patterns)
4. [Threading & Concurrency Principles](#4-threading--concurrency-principles)
5. [Image Processing Pipeline Design](#5-image-processing-pipeline-design)
6. [Camera Tuning Methodology](#6-camera-tuning-methodology)
7. [API Design Philosophy](#7-api-design-philosophy)
8. [Debugging & Iteration Strategy](#8-debugging--iteration-strategy)
9. [Servo Control Integration](#9-servo-control-integration)
10. [Code Architecture Principles](#10-code-architecture-principles)
11. [Decision Matrix Templates](#11-decision-matrix-templates)
12. [Common Pitfalls & Solutions](#12-common-pitfalls--solutions)

---

## 1. Mindset Framework

### 1.1 The Embedded Engineer's Mental Model

**Core Principle**: Every decision involves trade-offs. Your job is to identify them, evaluate them, and choose wisely.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THE TRADE-OFF TRIANGLE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         PERFORMANCE                                     │
│                            ▲                                            │
│                           /│\                                           │
│                          / │ \                                          │
│                         /  │  \                                         │
│                        /   │   \                                        │
│                       /    │    \                                       │
│                      /     │     \                                      │
│                     /      │      \                                     │
│                    /       │       \                                    │
│                   /        │        \                                   │
│                  ◀─────────┼─────────▶                                  │
│           QUALITY          │       SIMPLICITY                           │
│                                                                         │
│  Every feature sits somewhere in this triangle.                         │
│  Moving toward one corner moves away from others.                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Mental Models

#### Model 1: "What Could Go Wrong?"
Always ask this BEFORE writing code:
- What if the camera isn't available?
- What if frames drop?
- What if the user sends 100 requests/second?
- What if the SD card fills up?
- What if the network is slow?

#### Model 2: "Resource Awareness"
Embedded systems have finite resources:
```
┌────────────────────┬────────────────────┬────────────────────┐
│     RESOURCE       │   RASPBERRY PI 4   │    YOUR DUTY       │
├────────────────────┼────────────────────┼────────────────────┤
│ CPU Cores          │ 4 (ARM Cortex-A72) │ Don't block main   │
│ RAM                │ 1-8 GB             │ Buffer wisely      │
│ GPU (VideoCore)    │ Yes (H.264 enc)    │ Offload when can   │
│ I/O Bandwidth      │ USB 3.0 + CSI      │ Don't saturate     │
│ SD Card Write      │ ~40 MB/s typical   │ Batch writes       │
│ Network            │ Gigabit            │ Compress wisely    │
└────────────────────┴────────────────────┴────────────────────┘
```

#### Model 3: "Data Flow First"
Before writing ANY code, draw the data flow:
```
[Camera Sensor] 
    → [Raw Bytes] 
    → [Frame Buffer] 
    → [Preprocessing] 
    → [Output Format] 
    → [Network/Disk]
```

### 1.3 The Iteration Mindset

**NEVER** try to build the perfect solution first. Follow this cycle:

```
1. BUILD: Minimum viable implementation
2. MEASURE: Does it work? How fast? What breaks?
3. LEARN: What's the bottleneck? What's the weakness?
4. REPEAT: Improve the specific weakness

Example from this project:
┌──────────────┬─────────────────────────┬──────────────────────┐
│  ITERATION   │   WHAT WE TRIED         │   WHAT WE LEARNED    │
├──────────────┼─────────────────────────┼──────────────────────┤
│ 1            │ Blocking camera read    │ High latency (100ms) │
│ 2            │ Threaded capture        │ Much better (~10ms)  │
│ 3            │ Auto exposure           │ Color flicker        │
│ 4            │ Manual tuning           │ Stable colors        │
│ 5            │ RGB888 format           │ Colors inverted!     │
│ 6            │ BGR888 format           │ Correct colors       │
└──────────────┴─────────────────────────┴──────────────────────┘
```

---

## 2. Problem Decomposition Approach

### 2.1 The Layered Decomposition Method

When facing a complex problem, decompose into layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LAYER DECOMPOSITION                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LAYER 5: USER INTERFACE          │ Web UI, API responses              │
│  ────────────────────────────────────────────────────────────────────── │
│  LAYER 4: APPLICATION LOGIC       │ Save, record, stream               │
│  ────────────────────────────────────────────────────────────────────── │
│  LAYER 3: PREPROCESSING           │ Letterbox, normalize, contrast     │
│  ────────────────────────────────────────────────────────────────────── │
│  LAYER 2: CAPTURE ABSTRACTION     │ CameraStream class                 │
│  ────────────────────────────────────────────────────────────────────── │
│  LAYER 1: HARDWARE INTERFACE      │ picamera2, pigpio                  │
│  ────────────────────────────────────────────────────────────────────── │
│  LAYER 0: HARDWARE                │ Camera sensor, GPIO, servo         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Rule: Each layer should ONLY talk to adjacent layers.
      Web UI should NEVER directly access the camera sensor.
```

### 2.2 The "What Do I Need?" Analysis

For any feature request, ask:

```
1. WHAT is the desired output?
   → Example: "YOLO-ready tensor"

2. WHAT inputs do I have?
   → Example: "Raw BGR frames from camera"

3. WHAT transformations are needed?
   → Contrast stretch → Letterbox → Normalize → CHW format

4. WHAT could fail at each step?
   → No frame available, wrong color format, memory issues

5. WHAT metadata must I preserve?
   → Scale factor, padding offset, original size
```

### 2.3 The Requirements Matrix

Before implementing, fill this matrix:

```
┌──────────────────┬────────────────┬────────────────┬────────────────┐
│   REQUIREMENT    │   MANDATORY?   │   TRADE-OFF    │   SOLUTION     │
├──────────────────┼────────────────┼────────────────┼────────────────┤
│ Low latency      │ Yes            │ Quality        │ Threading      │
│ High quality     │ Yes for logos  │ Performance    │ 1920×1080      │
│ Accurate colors  │ Yes for logos  │ Simplicity     │ Manual tuning  │
│ Easy API         │ Yes            │ Flexibility    │ REST endpoints │
│ Video recording  │ Nice-to-have   │ Complexity     │ H.264 encoder  │
└──────────────────┴────────────────┴────────────────┴────────────────┘
```

---

## 3. Hardware-Software Integration Patterns

### 3.1 The Hardware Abstraction Pattern

**Principle**: Wrap hardware interactions in clean interfaces.

```python
# BAD: Hardware calls scattered everywhere
@app.route('/frame')
def get_frame():
    picam2.set_controls({"ExposureTime": 10000})  # Direct hardware!
    frame = picam2.capture_array()                 # Direct hardware!
    return Response(frame_to_jpeg(frame))

# GOOD: Hardware abstracted behind class
class CameraStream:
    def __init__(self):
        self._configure_camera()  # Hardware setup isolated
    
    def get_frame(self) -> np.ndarray:
        with self.frame_lock:
            return self.frame.copy()  # Clean interface

@app.route('/frame')
def get_frame():
    frame = camera.get_frame()  # No hardware knowledge needed
    return Response(frame_to_jpeg(frame))
```

### 3.2 The Graceful Degradation Pattern

**Principle**: Handle missing hardware gracefully.

```python
# From servo_control.py - EXCELLENT pattern:
try:
    import pigpio
except Exception:
    pigpio = None  # Mark as unavailable

class MG90SServo:
    def __init__(self, config: ServoConfig):
        if pigpio is None:
            raise RuntimeError(
                "pigpio is required. Install with: sudo apt-get install pigpio python3-pigpio\n"
                "Then start the daemon: sudo systemctl enable --now pigpiod"
            )
        # Clear error message with solution!
```

### 3.3 The Configuration Pattern

**Principle**: All tunables in one place, with documentation.

```python
class Config:
    # ==========================================================================
    # RESOLUTION SETTINGS - Higher resolution captures more logo detail
    # ==========================================================================
    # Using 1920x1080 (Full HD) for maximum detail capture
    # Logos are often small - more pixels means better feature extraction
    # Trade-off: More processing, but critical for small logo detection
    SENSOR_SIZE = (1920, 1080)  # Full HD for maximum logo detail
    
    # Each parameter has:
    # 1. Section header explaining category
    # 2. Comment explaining WHY this value
    # 3. Trade-off mentioned
    # 4. The value itself
```

---

## 4. Threading & Concurrency Principles

### 4.1 The Producer-Consumer Pattern

**Problem**: Camera capture is slow; web requests need fast responses.

**Solution**: Separate producer (capture) from consumer (requests).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PRODUCER-CONSUMER PATTERN                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PRODUCER THREAD                      SHARED STATE                      │
│  (runs continuously)                  (protected by lock)               │
│  ┌────────────────────┐              ┌────────────────────┐            │
│  │                    │              │                    │            │
│  │  while running:    │   WRITE     │   self.frame       │            │
│  │    frame = capture │ ──────────▶ │   (latest frame)   │            │
│  │    lock.acquire()  │              │                    │            │
│  │    self.frame=frame│              │   protected by     │            │
│  │    lock.release()  │              │   threading.Lock() │            │
│  │                    │              │                    │            │
│  └────────────────────┘              └────────────────────┘            │
│                                              │                          │
│                                              │ READ                     │
│                                              ▼                          │
│                                      ┌────────────────────┐            │
│                                      │  CONSUMER THREADS  │            │
│                                      │  (web requests)    │            │
│                                      │                    │            │
│                                      │  def get_frame():  │            │
│                                      │    lock.acquire()  │            │
│                                      │    return frame    │            │
│                                      │    lock.release()  │            │
│                                      └────────────────────┘            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Thread Safety Rules

```python
# RULE 1: Always use lock for shared state
def get_frame(self):
    with self.frame_lock:  # Context manager ensures release
        return self.frame.copy() if self.frame is not None else None
        #                  ^^^^^^ RULE 2: Return copy, not reference

# RULE 3: Keep critical sections SHORT
# BAD:
with self.lock:
    frame = self.frame
    jpeg = self._encode_jpeg(frame)  # Slow operation inside lock!
    return jpeg

# GOOD:
with self.lock:
    frame = self.frame.copy()  # Fast copy
# Slow operations OUTSIDE lock
jpeg = self._encode_jpeg(frame)
return jpeg

# RULE 4: Use daemon threads for cleanup
self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
#                                                                  ^^^^^^^^^^^
# daemon=True means: "When main thread dies, kill this thread too"
```

### 4.3 When to Use Threading vs Processing

```
┌────────────────────┬────────────────────┬────────────────────┐
│     USE CASE       │   THREADING        │   MULTIPROCESSING  │
├────────────────────┼────────────────────┼────────────────────┤
│ I/O bound work     │ ✅ PREFERRED       │ Overkill           │
│ Camera capture     │ ✅ YES             │ Not needed         │
│ Network requests   │ ✅ YES             │ Not needed         │
│ CPU-heavy compute  │ ❌ GIL limits      │ ✅ PREFERRED       │
│ YOLO inference     │ Maybe              │ ✅ Better          │
│ Simple Flask app   │ ✅ threaded=True   │ Gunicorn workers   │
└────────────────────┴────────────────────┴────────────────────┘

This project: Threading is sufficient because:
- Camera I/O is the bottleneck, not CPU
- Flask with threaded=True handles concurrent requests
- Preprocessing is fast enough single-threaded
```

---

## 5. Image Processing Pipeline Design

### 5.1 The Pipeline Pattern

**Principle**: Each step is independent, testable, and composable.

```python
# Each function:
# 1. Takes clear input
# 2. Does ONE thing
# 3. Returns clear output
# 4. Is stateless (no side effects)

def _contrast_stretch(frame: np.ndarray) -> np.ndarray:
    """Input: RGB frame, Output: Contrast-normalized frame"""
    ...

def _letterbox(frame: np.ndarray, target_size: tuple) -> tuple[np.ndarray, dict]:
    """Input: Any size frame, Output: Square frame + metadata"""
    ...

def _normalize(frame: np.ndarray) -> np.ndarray:
    """Input: uint8 HWC, Output: float32 CHW normalized"""
    ...

# Compose them:
def get_frame_for_yolo(self, normalize: bool = False):
    frame = self.get_frame()
    balanced = self._contrast_stretch(frame)
    yolo_frame, meta = self._letterbox(balanced, config.YOLO_SIZE)
    if normalize:
        return self._normalize(yolo_frame), meta
    return yolo_frame, meta
```

### 5.2 The Metadata Preservation Pattern

**Problem**: Preprocessing transforms coordinates. How to reverse?

**Solution**: Return metadata with every transformation.

```python
def _letterbox(frame, target_size):
    # ... do letterboxing ...
    
    # CRITICAL: Return everything needed to reverse transformation
    meta = {
        "scale": contained.width / image.width,  # To reverse scaling
        "pad": offset,                            # To reverse padding
        "original_size": image.size,              # For validation
    }
    return np.array(canvas), meta

# Usage: Reverse YOLO coordinates to original
def yolo_to_original(bbox_yolo, meta):
    x, y, w, h = bbox_yolo
    x = (x - meta['pad'][0]) / meta['scale']
    y = (y - meta['pad'][1]) / meta['scale']
    w = w / meta['scale']
    h = h / meta['scale']
    return (x, y, w, h)
```

### 5.3 The Contrast Stretch Algorithm - Deep Dive

**Why this specific algorithm?**

```python
def _contrast_stretch(frame: np.ndarray) -> np.ndarray:
    # Step 1: Float for precision (uint8 would lose information)
    frame_f = frame.astype(np.float32)
    
    # Step 2: Find the "dark" and "bright" reference points
    # Why 1% and 99%? (not min/max)
    #   - min/max would be affected by single dead pixels or specular highlights
    #   - 1%/99% ignores outliers, finds "typical" dark and bright
    #   - For logos: Use 1%/99% (less aggressive) to preserve true colors
    #   - For general: Use 2%/98% (more aggressive) for dynamic range
    lows = np.percentile(frame_f, 1, axis=(0, 1)).reshape(1, 1, 3)
    highs = np.percentile(frame_f, 99, axis=(0, 1)).reshape(1, 1, 3)
    
    # Step 3: Stretch to fill 0-1 range
    #   Original range: [lows, highs]
    #   Target range: [0, 1]
    #   Formula: (value - lows) / (highs - lows)
    stretched = (frame_f - lows) / (highs - lows + 1e-3)  # +1e-3 prevents /0
    
    # Step 4: Clip and convert back
    stretched = np.clip(stretched, 0.0, 1.0)
    return (stretched * 255.0).astype(np.uint8)
```

**Visual explanation:**
```
Before stretch (low contrast):     After stretch (full range):
Histogram:                         Histogram:
     ▄▄█████▄                            ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
   ▄███████████▄                        ▄████████████████▄
─┴──────────────┴─                 ─┴────────────────────┴─
0              255                 0                    255
   ^      ^                        ^                      ^
  30%    70%                       0%                   100%
(values clustered)                (values spread out)
```

---

## 6. Camera Tuning Methodology

### 6.1 The Systematic Tuning Process

**NEVER tune randomly. Follow this process:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CAMERA TUNING FLOWCHART                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  START                                                                  │
│    │                                                                    │
│    ▼                                                                    │
│  ┌─────────────────┐                                                    │
│  │ 1. SET BASELINE │  All auto: AeEnable=True, AwbEnable=True          │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 2. CHECK COLORS │  Are colors correct? White looks white?           │
│  └────────┬────────┘                                                    │
│           │                                                             │
│     ┌─────┴─────┐                                                       │
│     │ Inverted? │  YES → Try BGR888 instead of RGB888                  │
│     └─────┬─────┘                                                       │
│           │ NO                                                          │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 3. FIX EXPOSURE │  Too dark/bright? Adjust ExposureTime + Gain      │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 4. WHITE BAL.   │  Use white card, adjust ColourGains (R, B)        │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 5. SHARPNESS    │  Start at 1.0, increase until halos appear        │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 6. SATURATION   │  Fine-tune for your use case                      │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 7. TEST IN      │  Verify with actual target objects                │
│  │    REAL SCENE   │                                                    │
│  └─────────────────┘                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Parameter Interaction Matrix

**Understanding how parameters affect each other:**

```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│                 │ EXPOSURE UP     │ GAIN UP         │ SHARPNESS UP    │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ BRIGHTNESS      │ ↑ Brighter      │ ↑ Brighter      │ - No change     │
│ NOISE           │ - No change     │ ↑ MORE noise    │ ↑ Amplifies     │
│ MOTION BLUR     │ ↑ More blur     │ - No change     │ - No change     │
│ EDGE SHARPNESS  │ ↓ Softer edges  │ - No change     │ ↑ Sharper       │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘

KEY INSIGHT: Exposure and Gain both increase brightness, but:
- Exposure = longer collection time = motion blur risk
- Gain = electronic amplification = noise increase

For logos (need sharp edges + low noise):
→ Prefer shorter exposure + moderate gain
→ Ensure good lighting
```

### 6.3 Logo-Specific Tuning Rationale

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 WHY THESE SPECIFIC VALUES FOR LOGOS?                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PARAMETER: EXPOSURE_TIME_US = 10000 (10ms)                             │
│  ───────────────────────────────────────────────────────────────────    │
│  WHY: Logos need sharp edges. Motion blur destroys them.                │
│       At 10ms, even moderate movement won't blur.                       │
│  TRADE-OFF: Need more light or higher gain to compensate.               │
│                                                                         │
│  PARAMETER: ANALOG_GAIN = 1.5                                           │
│  ───────────────────────────────────────────────────────────────────    │
│  WHY: Low gain = less noise = cleaner fine details.                     │
│       Logos have text and thin lines that noise destroys.               │
│  TRADE-OFF: Need good lighting (can't shoot in darkness).               │
│                                                                         │
│  PARAMETER: ISP_SHARPNESS = 1.4                                         │
│  ───────────────────────────────────────────────────────────────────    │
│  WHY: Logo edges and text need to be crisp for detection.               │
│       40% boost makes edges pop without creating halos.                 │
│  TRADE-OFF: >1.6 creates visible halo artifacts.                        │
│                                                                         │
│  PARAMETER: ISP_SATURATION = 1.1                                        │
│  ───────────────────────────────────────────────────────────────────    │
│  WHY: Brand colors are FEATURES. Coca-Cola red is distinctive.          │
│       10% boost makes colors more distinguishable.                      │
│  TRADE-OFF: >1.3 causes color clipping and distortion.                  │
│                                                                         │
│  PARAMETER: CONTRAST_STRETCH = 1%-99% (not 2%-98%)                      │
│  ───────────────────────────────────────────────────────────────────    │
│  WHY: Aggressive stretching shifts colors.                              │
│       Logo blue might become cyan. That hurts detection.                │
│  ALTERNATIVE: Disable entirely for color-critical logos.                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. API Design Philosophy

### 7.1 The REST API Design Principles

**Principle 1: One endpoint = One purpose**
```
/frame           → Raw JPEG (simple, browser-friendly)
/frame/yolo      → Preprocessed JPEG (ready for detection)
/frame/yolo/tensor → Normalized tensor (direct inference)
/frame/raw       → NumPy array (maximum flexibility)

DON'T: /frame?format=jpeg&preprocess=true&normalize=true
DO: /frame/yolo/tensor
```

**Principle 2: Progressive complexity**
```
Simple needs → Simple endpoint:
  GET /frame  # Just works, returns JPEG

Advanced needs → Specific endpoint:
  GET /frame/yolo/tensor  # Returns normalized CHW tensor with metadata
```

**Principle 3: Include metadata in response**
```python
@app.route('/frame/yolo')
def get_frame_yolo():
    jpeg_bytes, meta = camera.get_yolo_frame_jpeg()
    response = Response(jpeg_bytes, mimetype='image/jpeg')
    # Include metadata needed to reverse transformations
    response.headers['X-YOLO-Scale'] = str(meta['scale'])
    response.headers['X-YOLO-Pad'] = str(meta['pad'])
    return response
```

### 7.2 Error Handling Pattern

```python
# PATTERN: Return appropriate HTTP codes with JSON errors

@app.route('/frame')
def get_frame():
    jpeg_bytes = camera.get_frame_jpeg()
    
    # 503 = Service Unavailable (camera not ready)
    if jpeg_bytes is None:
        return jsonify({"error": "No frame available"}), 503
    
    return Response(jpeg_bytes, mimetype='image/jpeg')

@app.route('/save_picture', methods=['POST'])
def save_picture():
    try:
        filename, error = camera.save_frame()
        if error:
            # 500 = Internal error (save failed)
            return jsonify({"success": False, "error": error}), 500
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        # Catch-all for unexpected errors
        return jsonify({"success": False, "error": str(e)}), 500
```

---

## 8. Debugging & Iteration Strategy

### 8.1 The Diagnostic Approach

**When something doesn't work, DON'T guess. Diagnose.**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THE DEBUGGING FLOWCHART                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  SYMPTOM: "Colors look wrong"                                           │
│    │                                                                    │
│    ▼                                                                    │
│  ┌─────────────────┐                                                    │
│  │ Is it inverted? │  Red ↔ Blue swapped?                              │
│  │ (R and B swap)  │                                                    │
│  └────────┬────────┘                                                    │
│     YES   │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ Change format:  │  RGB888 ↔ BGR888                                  │
│  │ or add cv2.cvt  │                                                    │
│  └─────────────────┘                                                    │
│                                                                         │
│  SYMPTOM: "High latency (>100ms)"                                       │
│    │                                                                    │
│    ▼                                                                    │
│  ┌─────────────────┐                                                    │
│  │ Where is time   │  Add timing to each step                          │
│  │ being spent?    │  t1 = time(); capture(); t2 = time(); etc.        │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ FOUND: Camera   │  → Implement threaded capture                     │
│  │ capture blocks  │                                                    │
│  └─────────────────┘                                                    │
│                                                                         │
│  SYMPTOM: "Recording creates empty file"                                │
│    │                                                                    │
│    ▼                                                                    │
│  ┌─────────────────┐                                                    │
│  │ Check each step:│  1. Is encoder started? 2. Is .h264 created?      │
│  │                 │  3. Does FFmpeg run? 4. Check FFmpeg output       │
│  └─────────────────┘                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 The Test Isolation Pattern

**Create minimal test scripts to isolate issues:**

```python
# test_color_config.py - Example from this project
# Tests ONLY color format, nothing else

from picamera2 import Picamera2
from PIL import Image
import os

os.makedirs("/home/ali/color_test", exist_ok=True)

# Test each format independently
for fmt in ["RGB888", "BGR888"]:
    picam2 = Picamera2()
    config = picam2.create_still_configuration(main={"format": fmt})
    picam2.configure(config)
    picam2.start()
    frame = picam2.capture_array()
    Image.fromarray(frame).save(f"/home/ali/color_test/{fmt}.jpg")
    picam2.stop()
    print(f"Saved {fmt}.jpg - check colors visually")
```

### 8.3 Iteration Documentation

**Document every iteration. Your future self will thank you.**

```markdown
### Version 2.1 - Color Format Fix

**Problem**: Colors appeared inverted (blue skin, red sky)

**Diagnosis**:
1. Created test script capturing with both RGB888 and BGR888
2. Compared output images
3. BGR888 showed correct colors

**Root Cause**: IMX519 sensor outputs BGR order, not RGB

**Solution**: Changed format from "RGB888" to "BGR888"

**Verification**: Tested with known color targets
```

---

## 9. Servo Control Integration

### 9.1 The Clean Hardware Abstraction

**From servo_control.py - A model of good design:**

```python
@dataclass(frozen=True)
class ServoConfig:
    """Immutable configuration - can't be changed after creation"""
    gpio: int               # BCM GPIO pin number
    min_us: int = 500       # Minimum pulse width
    max_us: int = 2500      # Maximum pulse width
    min_angle: float = 0.0  # Minimum angle
    max_angle: float = 180.0  # Maximum angle

    # Config handles its own validation
    def clamp_pulse_us(self, pulse_us: int) -> int:
        return max(self.min_us, min(self.max_us, int(pulse_us)))

    def clamp_angle(self, angle: float) -> float:
        return max(self.min_angle, min(self.max_angle, float(angle)))
```

**Why this is good design:**
1. **Frozen dataclass**: Configuration can't be accidentally modified
2. **Sensible defaults**: Works out of the box for common servos
3. **Self-contained validation**: Config knows how to validate itself
4. **Documentation via types**: Type hints explain expected values

### 9.2 The Context Manager Pattern

**For resources that need cleanup (connections, files, hardware):**

```python
class MG90SServo:
    def __enter__(self) -> "MG90SServo":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.off()  # Stop sending pulses
        finally:
            if self._owns_pi and self._pi is not None:
                self._pi.stop()  # Disconnect from pigpio
                self._pi = None

# Usage - automatically cleans up:
with MG90SServo(config) as servo:
    servo.set_angle(90)
# Servo is automatically closed here, even if exception occurs
```

### 9.3 The Angle-to-Pulse Conversion

**Understanding PWM servo control:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SERVO PWM EXPLANATION                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PWM Signal (50 Hz = 20ms period):                                      │
│                                                                         │
│  0°:    ┌──┐                                                            │
│         │  │                                                            │
│  ───────┘  └────────────────────────────── (500µs high, 19.5ms low)    │
│                                                                         │
│  90°:   ┌─────┐                                                         │
│         │     │                                                         │
│  ───────┘     └─────────────────────────── (1500µs high, 18.5ms low)   │
│                                                                         │
│  180°:  ┌────────┐                                                      │
│         │        │                                                      │
│  ───────┘        └──────────────────────── (2500µs high, 17.5ms low)   │
│                                                                         │
│                                                                         │
│  FORMULA:                                                               │
│  pulse_us = min_us + (angle / 180) * (max_us - min_us)                 │
│                                                                         │
│  Example: angle=90, min_us=500, max_us=2500                            │
│  pulse_us = 500 + (90/180) * (2500-500) = 500 + 0.5 * 2000 = 1500µs   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**The code implements this:**
```python
def set_angle(self, angle: float) -> float:
    angle = self.config.clamp_angle(angle)  # Safety first
    
    span_angle = self.config.max_angle - self.config.min_angle
    t = (angle - self.config.min_angle) / span_angle  # Normalize to 0-1
    
    pulse = int(self.config.min_us + t * (self.config.max_us - self.config.min_us))
    self.set_pulse_us(pulse)
    return angle
```

---

## 10. Code Architecture Principles

### 10.1 The Single Responsibility Principle

**Each class/function does ONE thing:**

```python
# CameraStream: Manages camera capture and preprocessing
# - Does NOT handle web routing
# - Does NOT handle file I/O directly
# - Does NOT know about Flask

class CameraStream:
    # Core responsibility: Frame capture and preprocessing
    def get_frame(self): ...
    def get_frame_jpeg(self): ...
    def get_frame_for_yolo(self): ...

# Flask routes: Handle HTTP
# - Do NOT know about camera internals
# - Just call camera methods and format responses

@app.route('/frame')
def get_frame():
    jpeg_bytes = camera.get_frame_jpeg()  # Delegate to camera
    return Response(jpeg_bytes)           # Handle HTTP response
```

### 10.2 The Dependency Injection Pattern

**From servo_control.py:**

```python
class MG90SServo:
    def __init__(self, config: ServoConfig, *, pi: Optional["pigpio.pi"] = None):
        self.config = config
        self._pi = pi  # Allow injecting pi instance
        
        if self._pi is None:
            self._pi = pigpio.pi()  # Create if not provided
            self._owns_pi = True    # Track that we own it
        else:
            self._owns_pi = False   # Someone else owns it

# Benefits:
# 1. Testable: Can inject mock pigpio
# 2. Flexible: Can share pigpio instance between servos
# 3. Clear ownership: Knows when to cleanup
```

### 10.3 The Defensive Programming Pattern

**Assume everything can fail:**

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
            time.sleep(0.01)  # Prevent tight error loop
            # DON'T crash - continue trying

def get_frame(self):
    with self.frame_lock:
        # Defensive: Check for None before copy
        return self.frame.copy() if self.frame is not None else None
```

---

## 11. Decision Matrix Templates

### 11.1 Technology Selection Matrix

Use this template when choosing technologies:

```
┌────────────────┬───────────┬───────────┬───────────┬───────────┬─────────┐
│  OPTION        │ PERF.     │ SIMPLE    │ MAINTAIN  │ COMMUNITY │ CHOICE  │
├────────────────┼───────────┼───────────┼───────────┼───────────┼─────────┤
│ picamera2      │ ★★★★★    │ ★★★★☆    │ ★★★★★    │ ★★★★☆    │ ✅      │
│ OpenCV         │ ★★★★☆    │ ★★★★☆    │ ★★★☆☆    │ ★★★★★    │ ❌      │
│ GStreamer      │ ★★★★★    │ ★★☆☆☆    │ ★★☆☆☆    │ ★★★☆☆    │ ❌      │
│ libcamera raw  │ ★★★★★    │ ★☆☆☆☆    │ ★★☆☆☆    │ ★★☆☆☆    │ ❌      │
└────────────────┴───────────┴───────────┴───────────┴───────────┴─────────┘

Winner: picamera2 - Best balance for Raspberry Pi camera control
```

### 11.2 Feature Trade-off Matrix

Use when deciding on feature implementation:

```
┌────────────────┬───────────┬───────────┬───────────┬─────────────────────┐
│  FEATURE       │ VALUE     │ EFFORT    │ RISK      │ DECISION            │
├────────────────┼───────────┼───────────┼───────────┼─────────────────────┤
│ Threading      │ HIGH      │ MEDIUM    │ LOW       │ ✅ Implement        │
│ GPU preprocess │ MEDIUM    │ HIGH      │ MEDIUM    │ ⏳ Future           │
│ Video record   │ HIGH      │ MEDIUM    │ LOW       │ ✅ Implement        │
│ Multi-camera   │ LOW       │ HIGH      │ HIGH      │ ❌ Skip             │
└────────────────┴───────────┴───────────┴───────────┴─────────────────────┘
```

---

## 12. Common Pitfalls & Solutions

### 12.1 Pitfall Catalog

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PITFALL CATALOG                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PITFALL 1: Blocking camera reads                                       │
│  SYMPTOM: High latency, dropped frames                                  │
│  SOLUTION: Threaded capture with shared buffer                          │
│                                                                         │
│  PITFALL 2: Wrong color format                                          │
│  SYMPTOM: Red/blue swapped, unnatural colors                            │
│  SOLUTION: Test both RGB888 and BGR888, use diagnostic script           │
│                                                                         │
│  PITFALL 3: Auto exposure/white balance                                 │
│  SYMPTOM: Color flicker, brightness changes between frames              │
│  SOLUTION: Use manual controls with fixed values                        │
│                                                                         │
│  PITFALL 4: Aggressive contrast stretch                                 │
│  SYMPTOM: Brand colors shift (blue→cyan, red→orange)                   │
│  SOLUTION: Use 1%-99% percentile or disable for logos                   │
│                                                                         │
│  PITFALL 5: No metadata with transformations                            │
│  SYMPTOM: Can't reverse YOLO coordinates to original                    │
│  SOLUTION: Always return scale and padding info                         │
│                                                                         │
│  PITFALL 6: Shared state without locks                                  │
│  SYMPTOM: Corrupted frames, random crashes                              │
│  SOLUTION: Always use threading.Lock() for shared data                  │
│                                                                         │
│  PITFALL 7: Not returning copies from shared state                      │
│  SYMPTOM: Frame changes while processing, weird artifacts               │
│  SOLUTION: return self.frame.copy() not self.frame                      │
│                                                                         │
│  PITFALL 8: pigpiod not running                                         │
│  SYMPTOM: "Cannot connect to pigpio daemon"                             │
│  SOLUTION: sudo systemctl enable --now pigpiod                          │
│                                                                         │
│  PITFALL 9: Camera already in use                                       │
│  SYMPTOM: "Camera is busy" or "Failed to open camera"                   │
│  SOLUTION: pkill -f python3, then restart                               │
│                                                                         │
│  PITFALL 10: Recording but no MP4 file                                  │
│  SYMPTOM: .h264 exists but no .mp4                                      │
│  SOLUTION: Install ffmpeg: sudo apt install ffmpeg                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 The Debugging Checklist

When something doesn't work, go through this checklist:

```
□ 1. Is the hardware connected and powered?
     - Camera ribbon cable seated properly?
     - Servo powered from 5V supply, not just GPIO?
     - Common ground between Pi and external supply?

□ 2. Are the drivers/daemons running?
     - pigpiod: sudo systemctl status pigpiod
     - libcamera: libcamera-hello (should show preview)

□ 3. Is the configuration correct?
     - Check GPIO pin numbers (BCM numbering)
     - Check camera format (BGR888 for this camera)

□ 4. Are there any other processes using the resource?
     - Camera: pkill -f python3
     - GPIO: Other scripts using same pins?

□ 5. Are there error messages?
     - Check terminal output carefully
     - Enable verbose logging if available

□ 6. Can you isolate the problem?
     - Create minimal test script
     - Test ONE thing at a time
```

---

## 13. Summary: The AI Agent Mindset

### The Core Principles

```
┌─────────────────────────────────────────────────────────────────────────┐
│               THE EMBEDDED SYSTEMS AI AGENT MINDSET                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. TRADE-OFFS ARE EVERYWHERE                                           │
│     Every decision favors something at the expense of something else.   │
│     Know what you're trading.                                           │
│                                                                         │
│  2. HARDWARE IS UNFORGIVING                                             │
│     Wrong pin = nothing works. Wrong format = wrong colors.             │
│     Test systematically, not randomly.                                  │
│                                                                         │
│  3. RESOURCES ARE FINITE                                                │
│     CPU, RAM, bandwidth, disk. Always be aware of limits.               │
│                                                                         │
│  4. THREADING IS ESSENTIAL BUT DANGEROUS                                │
│     Use it for I/O. Protect shared state. Use daemon threads.           │
│                                                                         │
│  5. PREPROCESSING MUST BE REVERSIBLE                                    │
│     Always preserve metadata to reverse transformations.                │
│                                                                         │
│  6. CONFIGURATION BELONGS IN ONE PLACE                                  │
│     Single Config class. Well documented. Easy to tune.                 │
│                                                                         │
│  7. ABSTRACT HARDWARE BEHIND CLEAN INTERFACES                           │
│     Web routes don't know about GPIO pins.                              │
│     Application logic doesn't know about camera registers.              │
│                                                                         │
│  8. ITERATE, DON'T PERFECT                                              │
│     Build → Measure → Learn → Repeat                                    │
│     Document what you learned.                                          │
│                                                                         │
│  9. ERRORS WILL HAPPEN                                                  │
│     Handle them gracefully. Don't crash the whole system.               │
│     Log helpful error messages with solutions.                          │
│                                                                         │
│  10. DOMAIN KNOWLEDGE MATTERS                                           │
│      For logos: colors and edges are critical.                          │
│      For general objects: different trade-offs apply.                   │
│      Know your use case.                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    QUICK REFERENCE CARD                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  CAMERA SETTINGS FOR LOGOS:                                             │
│    Resolution: 1920×1080 (detail)    Sharpness: 1.4 (edges)            │
│    Exposure: 10000µs (no blur)       Saturation: 1.1 (colors)          │
│    Gain: 1.5 (low noise)             Format: BGR888                    │
│                                                                         │
│  THREADING:                                                             │
│    Lock for shared state             Daemon for cleanup                 │
│    Copy before returning             Short critical sections            │
│                                                                         │
│  API DESIGN:                                                            │
│    One endpoint = One purpose        Include metadata                   │
│    Proper HTTP codes                 JSON for errors                    │
│                                                                         │
│  SERVO (MG90S):                                                         │
│    GPIO: BCM numbering               PWM: 50Hz, 500-2500µs             │
│    Power: External 5V                Daemon: pigpiod                    │
│                                                                         │
│  DEBUG:                                                                 │
│    Isolate problems                  Test systematically                │
│    Check daemons/drivers             Document findings                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

*Document Version: 1.0*  
*Created: January 5, 2026*  
*Purpose: AI Agent Training for Embedded Systems & Computer Vision*
