from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
import io
import atexit
import numpy as np
from PIL import Image, ImageOps
import os
from datetime import datetime
import threading
import time

app = Flask(__name__)

# =============================================================================
# CONFIGURATION - Optimized for LOGO DETECTION
# =============================================================================
# 
# LOGO DETECTION OPTIMIZATION RATIONALE:
# ======================================
# 1. HIGHER RESOLUTION: Logos are often small objects; more pixels = more detail
# 2. ENHANCED SHARPNESS: Logo edges, text, and symbols require crisp definition
# 3. ACCURATE COLORS: Brand colors are distinctive features for logo recognition
# 4. CONTROLLED CONTRAST: Too much contrast loses subtle logo gradients
# 5. PROPER EXPOSURE: Avoid blown highlights (white logos) or crushed blacks
# 6. LOW NOISE: Noise interferes with edge detection in small logo features
#
class Config:
    # ==========================================================================
    # RESOLUTION SETTINGS - Higher resolution captures more logo detail
    # ==========================================================================
    # Using 1920x1080 (Full HD) for maximum detail capture
    # Logos are often small - more pixels means better feature extraction
    # Trade-off: More processing, but critical for small logo detection
    SENSOR_SIZE = (1920, 1080)  # Full HD for maximum logo detail
    
    # YOLO inference size - 640x640 is standard, but consider 1280 for small logos
    # For logo detection, larger inference size significantly improves small object detection
    YOLO_SIZE = (640, 640)      # Standard (use 1280,1280 if GPU allows)

    # ==========================================================================
    # FRAME RATE - Lower for better image quality
    # ==========================================================================
    # For data collection: Lower FPS = longer exposure possible = better quality
    # For real-time: 30 FPS sufficient
    FRAME_RATE = 30
    
    # ==========================================================================
    # QUALITY SETTINGS - Maximum quality for logo detail preservation
    # ==========================================================================
    JPEG_QUALITY = 95           # High quality - logos need sharp edges
    SAVE_FOLDER = "/home/ali/captured_images"

    # ==========================================================================
    # MANUAL CAMERA TUNING - Critical for consistent logo detection
    # ==========================================================================
    USE_MANUAL_TUNING = True
    
    # EXPOSURE: Slightly shorter to prevent highlight blowout
    # Many logos contain white/bright elements that blow out easily
    # Range: 8000-15000µs for indoor, adjust based on your lighting
    EXPOSURE_TIME_US = 10000    # 0.010s - faster to preserve bright logo details
    
    # ANALOG GAIN: Keep low to minimize noise (logos need clean edges)
    # Noise destroys fine text and edge details in logos
    # Compensate with better lighting rather than high gain
    ANALOG_GAIN = 1.5           # Low gain = less noise = cleaner logo edges
    
    # WHITE BALANCE: Neutral for accurate brand color reproduction
    # Logo colors are distinctive features - must be accurate
    # (R, B) gains - tune these with a white reference card
    COLOUR_GAINS = (1.45, 1.05) # Tuned for neutral whites - adjust per environment

    # ==========================================================================
    # ISP (Image Signal Processor) - Logo-optimized settings
    # ==========================================================================
    # SHARPNESS: Increased for crisp logo edges and text
    # Logos have defined boundaries - sharpness helps edge detection
    # Too high causes artifacts; 1.3-1.5 is sweet spot
    ISP_SHARPNESS = 1.4         # Enhanced for logo edge definition
    
    # CONTRAST: Moderate - too high loses subtle logo gradients
    # Many logos have gradients or subtle color transitions
    ISP_CONTRAST = 1.05         # Slight boost, preserve gradients
    
    # SATURATION: Accurate colors, slight boost for brand color distinction
    # Brand colors are key features - make them pop but stay accurate
    ISP_SATURATION = 1.1        # Slight boost for brand color visibility
    
    # NOISE REDUCTION: Higher to clean up fine details
    # 0=off, 1=fast, 2=high quality
    # Logos need clean edges - noise reduction helps
    NOISE_REDUCTION_MODE = 2    # High quality denoising
    
    # AUTOFOCUS: Enable for sharp logo capture
    # AfMode: 0=Manual, 1=Auto (single shot), 2=Continuous
    AUTOFOCUS_ENABLED = True
    AUTOFOCUS_MODE = 2          # Continuous autofocus for real-time

    # ==========================================================================
    # NORMALIZATION - Standard ImageNet (most pretrained backbones)
    # ==========================================================================
    # If training custom model: compute your dataset's mean/std
    NORMALIZE_MEAN = (0.485, 0.456, 0.406)
    NORMALIZE_STD = (0.229, 0.224, 0.225)
    
    # ==========================================================================
    # LOGO-SPECIFIC: Contrast stretch parameters
    # ==========================================================================
    # For logos, we want LESS aggressive stretching to preserve true colors
    # Standard percentile stretch can shift brand colors
    CONTRAST_STRETCH_ENABLED = True  # Set False for color-critical logos
    CONTRAST_PERCENTILE_LOW = 1      # Less aggressive (was 2)
    CONTRAST_PERCENTILE_HIGH = 99    # Less aggressive (was 98)
    
config = Config()

# --- Create folder for saved images ---
os.makedirs(config.SAVE_FOLDER, exist_ok=True)

# =============================================================================
# CAMERA CLASS - Well-structured for YOLO integration
# =============================================================================
class CameraStream:
    def __init__(self):
        self.picam2 = Picamera2()
        self.frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self._configure_camera()
        
    def _configure_camera(self):
        """Configure camera with YOLO-optimized settings"""
        # Capture full sensor FOV, then letterbox for YOLO in software
        cam_config = self.picam2.create_video_configuration(
            main={
                "size": config.SENSOR_SIZE,
                "format": "BGR888"  # BGR888 gives correct colors on this camera
            },
            controls={
                "FrameRate": config.FRAME_RATE,
                "AeEnable": config.USE_MANUAL_TUNING is False,
                "AwbEnable": config.USE_MANUAL_TUNING is False,
                "NoiseReductionMode": config.NOISE_REDUCTION_MODE,
            },
            buffer_count=4  # Buffer for smooth streaming
        )
        self.picam2.configure(cam_config)

    def _apply_runtime_controls(self):
        """Apply ISP/exposure controls after camera start"""
        controls = {
            "Sharpness": config.ISP_SHARPNESS,
            "Contrast": config.ISP_CONTRAST,
            "Saturation": config.ISP_SATURATION,
            "NoiseReductionMode": config.NOISE_REDUCTION_MODE,
        }
        
        # Add autofocus if enabled
        if config.AUTOFOCUS_ENABLED:
            controls["AfMode"] = config.AUTOFOCUS_MODE
            controls["AfSpeed"] = 1  # Fast autofocus

        if config.USE_MANUAL_TUNING:
            controls.update({
                "AeEnable": False,
                "AwbEnable": False,
                "ExposureTime": config.EXPOSURE_TIME_US,
                "AnalogueGain": config.ANALOG_GAIN,
                "ColourGains": config.COLOUR_GAINS,
            })
        else:
            controls.update({
                "AeEnable": True,
                "AwbEnable": True,
            })

        try:
            self.picam2.set_controls(controls)
        except Exception as exc:
            print(f"Control warning: {exc}")
        
    def start(self):
        """Start camera and frame capture thread"""
        self.picam2.start()
        self._apply_runtime_controls()
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        print(f"✅ Camera started at {config.SENSOR_SIZE[0]}x{config.SENSOR_SIZE[1]}")
        
    def _capture_loop(self):
        """Continuous frame capture for low latency"""
        while self.running:
            try:
                frame = self.picam2.capture_array()
                
                # Frame is already in correct RGB format from BGR888 config
                with self.frame_lock:
                    self.frame = frame
            except Exception as e:
                print(f"Capture error: {e}")
                time.sleep(0.01)

    @staticmethod
    def _contrast_stretch(frame: np.ndarray) -> np.ndarray:
        """
        Per-channel percentile stretch - LOGO-OPTIMIZED
        
        For logo detection, we use LESS aggressive stretching to preserve
        true brand colors. Aggressive stretching can shift distinctive
        brand colors that are key features for logo recognition.
        
        Set CONTRAST_STRETCH_ENABLED=False for color-critical logo applications.
        """
        if not config.CONTRAST_STRETCH_ENABLED:
            return frame  # Return original for color-critical logos
            
        frame_f = frame.astype(np.float32)
        low_pct = config.CONTRAST_PERCENTILE_LOW    # Default: 1
        high_pct = config.CONTRAST_PERCENTILE_HIGH  # Default: 99
        
        lows = np.percentile(frame_f, low_pct, axis=(0, 1)).reshape(1, 1, 3)
        highs = np.percentile(frame_f, high_pct, axis=(0, 1)).reshape(1, 1, 3)
        stretched = (frame_f - lows) / (highs - lows + 1e-3)
        stretched = np.clip(stretched, 0.0, 1.0)
        return (stretched * 255.0).astype(np.uint8)

    @staticmethod
    def _letterbox(frame: np.ndarray, target_size: tuple[int, int]) -> tuple[np.ndarray, dict]:
        """Resize with aspect-ratio preservation and black padding"""
        target_w, target_h = target_size
        image = Image.fromarray(frame)
        contained = ImageOps.contain(image, (target_w, target_h), method=Image.BICUBIC)
        canvas = Image.new("RGB", (target_w, target_h), color=(0, 0, 0))
        offset = ((target_w - contained.width) // 2, (target_h - contained.height) // 2)
        canvas.paste(contained, offset)
        meta = {
            "scale": contained.width / image.width,
            "pad": offset,
            "original_size": image.size,
        }
        return np.array(canvas), meta

    @staticmethod
    def _normalize(frame: np.ndarray) -> np.ndarray:
        """Normalize frame to CHW float32 tensor using ImageNet stats"""
        mean = np.array(config.NORMALIZE_MEAN, dtype=np.float32)
        std = np.array(config.NORMALIZE_STD, dtype=np.float32)
        tensor = frame.astype(np.float32) / 255.0
        tensor = (tensor - mean) / std
        return np.transpose(tensor, (2, 0, 1))  # CHW
                
    def get_frame(self):
        """Get latest frame (thread-safe)"""
        with self.frame_lock:
            return self.frame.copy() if self.frame is not None else None
    
    def get_frame_for_yolo(self, normalize: bool = False):
        """Return preprocessed frame (and metadata) ready for YOLO"""
        frame = self.get_frame()
        if frame is None:
            return None, None

        balanced = self._contrast_stretch(frame)
        yolo_frame, meta = self._letterbox(balanced, config.YOLO_SIZE)

        if normalize:
            return self._normalize(yolo_frame), meta
        return yolo_frame, meta
    
    def get_frame_jpeg(self, quality=None):
        """Get frame as JPEG bytes"""
        frame = self.get_frame()
        if frame is None:
            return None
        img = Image.fromarray(frame)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality or config.JPEG_QUALITY)
        return buffer.getvalue()

    def get_yolo_frame_jpeg(self):
        """Get letterboxed/preprocessed frame as JPEG"""
        frame, meta = self.get_frame_for_yolo()
        if frame is None:
            return None, None
        img = Image.fromarray(frame)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=config.JPEG_QUALITY)
        return buffer.getvalue(), meta

    def get_yolo_tensor(self):
        """Get normalized CHW tensor for direct YOLO inference"""
        tensor, meta = self.get_frame_for_yolo(normalize=True)
        return tensor, meta
    
    def save_frame(self, filename=None):
        """Save current frame to disk"""
        frame = self.get_frame()
        if frame is None:
            return None, "No frame available"
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"capture_{timestamp}.jpg"
        
        filepath = os.path.join(config.SAVE_FOLDER, filename)
        img = Image.fromarray(frame)
        img.save(filepath, format='JPEG', quality=95)
        return filename, None
        
    def stop(self):
        """Stop camera"""
        self.running = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=1.0)
        self.picam2.stop()
        self.picam2.close()

# Initialize camera
camera = CameraStream()
camera.start()

print(f"📁 Save folder: {config.SAVE_FOLDER}")
print(f"🎯 YOLO input size: {config.YOLO_SIZE}")

def cleanup():
    camera.stop()

atexit.register(cleanup)

# =============================================================================
# VIDEO STREAMING
# =============================================================================
def generate_frames():
    """Generate MJPEG stream for web browser"""
    while True:
        try:
            jpeg_bytes = camera.get_frame_jpeg(quality=70)
            if jpeg_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
            else:
                time.sleep(0.01)
        except Exception as e:
            print(f"Stream error: {e}")
            continue

# =============================================================================
# API ROUTES
# =============================================================================
@app.route('/save_picture', methods=['POST'])
def save_picture():
    """Save current frame to disk"""
    try:
        filename, error = camera.save_frame()
        if error:
            return jsonify({"success": False, "error": error})
        print(f"📸 Saved: {filename}")
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/')
def index():
    """Web interface with live stream"""
    return '''<!DOCTYPE html>
<html><head><title>YOLO Camera</title>
<style>
body{background:#0a0a0a;color:#fff;font-family:'Segoe UI',sans-serif;text-align:center;padding:20px;margin:0}
.container{max-width:800px;margin:0 auto}
h2{color:#4a9eff;margin-bottom:5px}
.subtitle{color:#888;font-size:14px;margin-bottom:20px}
img{max-width:100%;border:3px solid #4a9eff;border-radius:12px;box-shadow:0 4px 20px rgba(74,158,255,0.3)}
.controls{margin:20px 0}
button{margin:8px;padding:12px 24px;font-size:16px;cursor:pointer;background:linear-gradient(135deg,#00c853,#00a844);color:#fff;border:none;border-radius:8px;transition:all 0.3s}
button:hover{transform:scale(1.05);box-shadow:0 4px 15px rgba(0,200,83,0.4)}
button.secondary{background:linear-gradient(135deg,#4a9eff,#2979ff)}
#msg{margin:15px;padding:10px;border-radius:8px;min-height:20px}
.info{background:#1a1a2e;padding:15px;border-radius:10px;margin-top:20px;text-align:left}
.info h3{color:#4a9eff;margin:0 0 10px 0}
.info code{background:#2a2a4a;padding:3px 8px;border-radius:4px;color:#00c853}
.endpoint{margin:5px 0}
</style></head><body>
<div class="container">
<h2>🎯 YOLO Camera Stream</h2>
<p class="subtitle">Optimized for object detection</p>
<img src="/video_feed" alt="Live Stream">
<div class="controls">
<button onclick="save()">📸 Capture (S)</button>
<button class="secondary" onclick="window.open('/frame','_blank')">🖼️ Get Frame</button>
</div>
<div id="msg"></div>
<div class="info">
<h3>📡 API Endpoints</h3>
<div class="endpoint"><code>GET /frame</code> - Raw JPEG frame (browser friendly)</div>
<div class="endpoint"><code>GET /frame/yolo</code> - Letterboxed + color balanced JPEG</div>
<div class="endpoint"><code>GET /frame/yolo/tensor</code> - Normalized CHW tensor (.npy)</div>
<div class="endpoint"><code>GET /frame/raw</code> - Sensor capture as NumPy array</div>
<div class="endpoint"><code>GET /frame/numpy</code> - Frame/meta info</div>
<div class="endpoint"><code>GET /video_feed</code> - MJPEG stream</div>
<div class="endpoint"><code>POST /save_picture</code> - Save to disk</div>
<div class="endpoint"><code>GET /status</code> - Camera status</div>
</div>
</div>
<script>
function save(){
  fetch('/save_picture',{method:'POST'}).then(r=>r.json()).then(d=>{
    let msg=document.getElementById('msg');
    msg.innerHTML=d.success?'<span style="color:#00c853">✅ Saved: '+d.filename+'</span>':'<span style="color:#ff5252">❌ '+d.error+'</span>';
    setTimeout(()=>msg.innerHTML='',3000);
  });
}
document.onkeydown=e=>{if(e.key.toLowerCase()=='s')save()};
</script></body></html>'''

@app.route('/video_feed')
def video_feed():
    """MJPEG video stream"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# =============================================================================
# YOLO-OPTIMIZED ENDPOINTS
# =============================================================================
@app.route('/frame')
def get_frame():
    """
    Get current frame as JPEG - optimized for YOLO
    
    Usage with YOLO:
        import requests
        from PIL import Image
        import io
        
        resp = requests.get('http://localhost:5000/frame')
        img = Image.open(io.BytesIO(resp.content))
        results = model(img)
    """
    jpeg_bytes = camera.get_frame_jpeg()
    if jpeg_bytes is None:
        return jsonify({"error": "No frame available"}), 503
    return Response(jpeg_bytes, mimetype='image/jpeg')

@app.route('/frame/raw')
def get_frame_raw():
    """Download raw sensor frame as NumPy array"""
    frame = camera.get_frame()
    if frame is None:
        return jsonify({"error": "No frame available"}), 503
    buffer = io.BytesIO()
    np.save(buffer, frame, allow_pickle=False)
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype='application/octet-stream',
        headers={'Content-Disposition': 'attachment; filename="sensor_frame.npy"'}
    )

@app.route('/frame/yolo')
def get_frame_yolo():
    """Get preprocessed, letterboxed frame tailored to YOLO"""
    jpeg_bytes, meta = camera.get_yolo_frame_jpeg()
    if jpeg_bytes is None:
        return jsonify({"error": "No frame available"}), 503
    response = Response(jpeg_bytes, mimetype='image/jpeg')
    if meta:
        response.headers['X-YOLO-Scale'] = str(meta['scale'])
        response.headers['X-YOLO-Pad'] = str(meta['pad'])
    return response

@app.route('/frame/yolo/tensor')
def get_frame_yolo_tensor():
    """Get normalized CHW tensor encoded as NumPy .npy"""
    tensor, meta = camera.get_yolo_tensor()
    if tensor is None:
        return jsonify({"error": "No frame available"}), 503
    buffer = io.BytesIO()
    payload = {
        "tensor": tensor,
        "meta": meta,
        "normalize_mean": config.NORMALIZE_MEAN,
        "normalize_std": config.NORMALIZE_STD,
    }
    np.save(buffer, payload, allow_pickle=True)
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype='application/octet-stream',
        headers={'Content-Disposition': 'attachment; filename="yolo_tensor.npy"'}
    )

@app.route('/frame/numpy')
def get_frame_info():
    """
    Get frame metadata for YOLO integration
    
    Returns frame info - use /frame to get actual image data
    """
    frame, meta = camera.get_frame_for_yolo()
    if frame is None:
        return jsonify({"error": "No frame available"}), 503
    
    return jsonify({
        "shape": list(frame.shape),  # [H, W, C]
        "dtype": str(frame.dtype),
        "size": config.YOLO_SIZE,
        "format": "RGB",
        "endpoint": "/frame",
        "scale": meta["scale"] if meta else 1.0,
        "padding": meta["pad"] if meta else (0, 0),
        "original_size": meta["original_size"] if meta else config.SENSOR_SIZE,
    })

@app.route('/status')
def get_status():
    """Camera and server status"""
    frame = camera.get_frame()
    return jsonify({
        "camera_running": camera.running,
        "frame_available": frame is not None,
        "sensor_resolution": config.SENSOR_SIZE,
        "yolo_resolution": config.YOLO_SIZE,
        "frame_rate": config.FRAME_RATE,
        "save_folder": config.SAVE_FOLDER,
        "manual_tuning": config.USE_MANUAL_TUNING,
        "exposure_us": config.EXPOSURE_TIME_US,
        "analog_gain": config.ANALOG_GAIN,
    })

# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("🏷️  LOGO DETECTION - Optimized Camera Server")
    print("=" * 60)
    print(f"   Sensor Capture: {config.SENSOR_SIZE[0]}x{config.SENSOR_SIZE[1]} (Full HD)")
    print(f"   YOLO Output: {config.YOLO_SIZE[0]}x{config.YOLO_SIZE[1]}")
    print(f"   Frame Rate: {config.FRAME_RATE} fps")
    print("")
    print("   📸 Logo Optimization Settings:")
    print(f"   → Exposure: {config.EXPOSURE_TIME_US}µs (fast for sharp edges)")
    print(f"   → Gain: {config.ANALOG_GAIN} (low noise for clean details)")
    print(f"   → Sharpness: {config.ISP_SHARPNESS} (enhanced for text/edges)")
    print(f"   → Saturation: {config.ISP_SATURATION} (brand color boost)")
    print(f"   → Contrast Stretch: {'ON' if config.CONTRAST_STRETCH_ENABLED else 'OFF'}")
    print("")
    print("   🌐 Web Interface:")
    print("   → http://localhost:5000")
    print("")
    print("   📡 API Endpoints:")
    print("   → GET /frame/yolo        - Preprocessed JPEG")
    print("   → GET /frame/yolo/tensor - Normalized tensor (.npy)")
    print("   → GET /frame/raw         - Sensor capture (.npy)")
    print("   → POST /save_picture     - Save for training data")
    print("   → GET /status            - Camera status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)