# AI Arm Tracker (Raspberry Pi)

This project is building an **AI-powered arm/servo tracker** on a **Raspberry Pi**.

Right now the repo contains:
- A **Picamera2 + Flask** camera server for **real-time streaming**, **frame capture**, and **YOLO-ready preprocessing**.
- A **pigpio-based servo controller** (tested with MG90S-style servos) plus a small CLI demo.

The typical “arm tracker” loop is:
1. Capture a frame from the Pi camera.
2. Run AI inference (e.g., YOLO) to find a target (object/person/logo/etc.).
3. Convert the target position (e.g., bounding-box center) into servo angles.
4. Drive the servo(s) to keep the target centered.

> Note: The inference + tracking logic can be built on top of the provided camera and servo modules.

---

## Hardware

- Raspberry Pi (tested on Pi 4/5)
- Raspberry Pi Camera Module or ArduCAM Pivariety
- Servo(s) (e.g., MG90S)
- **External 5V supply for servos** (recommended)

### Servo wiring reminders
- Servo signal → Pi GPIO (BCM numbering)
- Servo V+ → external 5V (recommended)
- Servo GND → external GND **and** Pi GND (common ground)

---

## Software / OS

- Debian-based Raspberry Pi OS (this repo references Debian “Trixie” setups)
- Python 3
- `picamera2` (camera)
- `flask` (web server)
- `numpy`, `Pillow`
- `pigpio` + `pigpiod` (servo control)

---

## Install

### 1) (If using ArduCAM Pivariety) install libcamera packages

This repo includes ArduCAM’s installer script:

```bash
chmod +x install_pivariety_pkgs.sh

# Examples (these package names match the documentation)
./install_pivariety_pkgs.sh -p libcamera_trixie
./install_pivariety_pkgs.sh -p libcamera_apps_trixie
```

If the installer updates `/boot/config.txt`, reboot when prompted.

### 2) Python dependencies

If you don’t already have the Python deps installed:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install flask picamera2 pillow numpy
```

### 3) Servo dependencies (pigpio)

```bash
sudo apt-get update
sudo apt-get install -y pigpio python3-pigpio
sudo systemctl enable --now pigpiod
```

---

## Run

### Camera server (YOLO-optimized)

Runs a Flask server with MJPEG streaming, frame capture endpoints, and YOLO-friendly preprocessing (letterbox + optional normalization):

```bash
python3 live_cam.py
```

Open:
- http://<pi-ip>:5000

Key endpoints:
- `GET /video_feed` – MJPEG stream
- `GET /frame` – current frame as JPEG
- `GET /frame/yolo` – letterboxed/color-balanced JPEG
- `GET /frame/yolo/tensor` – normalized CHW tensor as `.npy`
- `POST /save_picture` – saves an image into `/home/ali/captured_images`
- `GET /status` – current camera settings/status

### Camera server (normal auto mode + video recording)

```bash
python3 live_cam_normal.py
```

This variant uses auto exposure / auto white balance and also supports video recording to `/home/ali/CAMERA_NORMAL/videos`.

### Servo quick test

```bash
# Center servo
python3 servo_demo.py --gpio 18

# Move to a specific angle
python3 servo_demo.py --gpio 18 --angle 45

# Sweep
python3 servo_demo.py --gpio 18 --sweep
```

---

## How to build the “AI Arm Tracker” on top of this repo

A simple approach:

1. Run the camera server (`live_cam.py`).
2. In your tracking script:
   - Fetch `GET /frame` (or `/frame/yolo`) periodically.
   - Run your model (YOLO, etc.) to get a bounding box.
   - Compute the target center `(cx, cy)`.
   - Convert `(cx, cy)` into yaw/pitch servo commands.
   - Drive the servo(s) using `MG90SServo` from `servo_control.py`.

If you want, I can add a minimal `arm_tracker.py` that:
- reads frames from `live_cam.py`,
- uses a placeholder “detector” interface (so you can plug in YOLO later), and
- moves the servo to center the target.

---

## Repo files (high level)

- `live_cam.py` – YOLO-optimized camera streaming + capture API
- `live_cam_normal.py` – normal streaming + high-quality video recording
- `servo_control.py` – pigpio-based MG90S servo control
- `servo_demo.py` – CLI tool to test servo movement
- `PROJECT_DOCUMENTATION.md` – detailed documentation on the camera pipeline and design

---

## Troubleshooting

- **No servo movement / runtime error about pigpio**:
  - Ensure daemon is running: `sudo systemctl enable --now pigpiod`
- **Camera not found**:
  - Verify `picamera2`/libcamera install, and reboot after camera driver changes.
- **Wrong colors**:
  - `live_cam.py` config uses `BGR888` for correct colors on the tested setup.

---

## License

Add a license if/when you’re ready (MIT/Apache-2.0/etc.).
