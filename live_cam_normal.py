from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder, Quality
from picamera2.outputs import FileOutput, FfmpegOutput
import io
import atexit
import numpy as np
from PIL import Image
import os
from datetime import datetime
import threading
import time
import subprocess

app = Flask(__name__)

# =============================================================================
# CONFIGURATION - Normal Display Mode (Auto Settings)
# =============================================================================
class Config:
    # Standard resolution for general viewing
    SENSOR_SIZE = (1280, 720)   # 720p - balanced quality and performance
    
    # VIDEO RECORDING - Highest Quality Settings
    VIDEO_SIZE = (1920, 1080)   # Full HD for recording
    VIDEO_BITRATE = 15000000    # 15 Mbps for high quality (adjust: 10-25 Mbps)
    VIDEO_FPS = 30              # Frame rate for video
    
    FRAME_RATE = 30
    JPEG_QUALITY = 80           # Good quality for streaming
    SAVE_FOLDER = "/home/ali/CAMERA_NORMAL"
    VIDEO_FOLDER = "/home/ali/CAMERA_NORMAL/videos"

    # AUTO MODE - Let camera handle exposure and white balance
    USE_MANUAL_TUNING = False   # Automatic exposure and white balance
    
config = Config()

# --- Create folders for saved images and videos ---
os.makedirs(config.SAVE_FOLDER, exist_ok=True)
os.makedirs(config.VIDEO_FOLDER, exist_ok=True)

# =============================================================================
# CAMERA CLASS - Simple streaming with VIDEO RECORDING
# =============================================================================
class CameraStream:
    def __init__(self):
        self.picam2 = Picamera2()
        self.frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        
        # Video recording state
        self.is_recording = False
        self.recording_lock = threading.Lock()
        self.current_video_file = None
        self.encoder = None
        self.output = None
        self.recording_start_time = None
        
        self._configure_camera()
        
    def _configure_camera(self):
        """Configure camera with automatic settings"""
        cam_config = self.picam2.create_video_configuration(
            main={
                "size": config.SENSOR_SIZE,
                "format": "BGR888"  # BGR888 gives correct colors on this camera
            },
            controls={
                "FrameRate": config.FRAME_RATE,
            },
            buffer_count=4
        )
        self.picam2.configure(cam_config)
        
    def start(self):
        """Start camera and frame capture thread"""
        self.picam2.start()
        
        # Enable auto exposure, auto white balance, and autofocus
        self.picam2.set_controls({
            "AeEnable": True,
            "AwbEnable": True,
            "AfMode": 2,      # Continuous autofocus
            "AfSpeed": 1,     # Normal AF speed (0=normal, 1=fast)
        })
        
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        print(f"✅ Camera started at {config.SENSOR_SIZE[0]}x{config.SENSOR_SIZE[1]}")
        print(f"📷 Mode: Normal Display (Auto Exposure, Auto White Balance)")
        
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
                
    def get_frame(self):
        """Get latest frame (thread-safe)"""
        with self.frame_lock:
            return self.frame.copy() if self.frame is not None else None
    
    def get_frame_jpeg(self, quality=None):
        """Get frame as JPEG bytes"""
        frame = self.get_frame()
        if frame is None:
            return None
        img = Image.fromarray(frame)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality or config.JPEG_QUALITY)
        return buffer.getvalue()
    
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
        img.save(filepath, format='JPEG', quality=90)
        return filename, None
    
    # =========================================================================
    # VIDEO RECORDING METHODS
    # =========================================================================
    def start_recording(self, filename=None):
        """
        Start recording video at highest quality
        Uses H.264 hardware encoder with high bitrate
        Records to .h264 file, then converts to MP4 on stop
        """
        with self.recording_lock:
            if self.is_recording:
                return None, "Already recording"
            
            try:
                # Generate filename with timestamp
                if filename is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"video_{timestamp}.mp4"
                
                # Use .h264 extension for raw recording, convert to MP4 on stop
                h264_filename = filename.replace('.mp4', '.h264')
                self.h264_path = os.path.join(config.VIDEO_FOLDER, h264_filename)
                self.current_video_path = os.path.join(config.VIDEO_FOLDER, filename)
                
                # Create H.264 encoder with highest quality
                self.encoder = H264Encoder(
                    bitrate=config.VIDEO_BITRATE,
                )
                
                # Use FileOutput for raw H.264 stream
                self.output = FileOutput(self.h264_path)
                
                # Start recording on the main stream
                self.picam2.start_encoder(self.encoder, self.output, name="main")
                
                self.is_recording = True
                self.current_video_file = filename
                self.recording_start_time = time.time()
                
                print(f"🎬 Recording started: {filename}")
                print(f"   Temp file: {self.h264_path}")
                print(f"   Bitrate: {config.VIDEO_BITRATE // 1000000} Mbps")
                
                return filename, None
                
            except Exception as e:
                self.is_recording = False
                print(f"❌ Recording error: {e}")
                import traceback
                traceback.print_exc()
                return None, str(e)
                return None, str(e)
    
    def stop_recording(self):
        """Stop video recording, convert to MP4, and finalize file"""
        with self.recording_lock:
            if not self.is_recording:
                return None, "Not recording"
            
            try:
                # Stop encoder
                self.picam2.stop_encoder()
                
                duration = time.time() - self.recording_start_time
                filename = self.current_video_file
                h264_path = self.h264_path
                mp4_path = self.current_video_path
                
                self.is_recording = False
                self.current_video_file = None
                self.current_video_path = None
                self.h264_path = None
                self.encoder = None
                self.output = None
                self.recording_start_time = None
                
                # Give encoder a moment to finalize
                time.sleep(0.3)
                
                # Convert H.264 to MP4 using FFmpeg
                if os.path.exists(h264_path):
                    print(f"📦 Converting to MP4...")
                    try:
                        # Use FFmpeg to wrap H.264 in MP4 container
                        cmd = [
                            'ffmpeg', '-y',
                            '-framerate', str(config.VIDEO_FPS),
                            '-i', h264_path,
                            '-c', 'copy',  # No re-encoding, just wrap
                            mp4_path
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        
                        if result.returncode == 0 and os.path.exists(mp4_path):
                            # Remove temp h264 file
                            os.remove(h264_path)
                            file_size = os.path.getsize(mp4_path)
                            print(f"⏹️ Recording stopped: {filename}")
                            print(f"   Duration: {duration:.1f} seconds")
                            print(f"   File size: {file_size / 1024 / 1024:.1f} MB")
                        else:
                            print(f"⚠️ FFmpeg conversion failed: {result.stderr}")
                            # Keep h264 file as fallback
                            mp4_path = h264_path
                            filename = filename.replace('.mp4', '.h264')
                            
                    except subprocess.TimeoutExpired:
                        print(f"⚠️ FFmpeg timeout, keeping raw h264")
                        mp4_path = h264_path
                        filename = filename.replace('.mp4', '.h264')
                else:
                    print(f"⚠️ Warning: H264 file not found at {h264_path}")
                
                return {
                    "filename": filename,
                    "duration": round(duration, 1),
                    "path": mp4_path
                }, None
                
            except Exception as e:
                self.is_recording = False
                print(f"❌ Stop recording error: {e}")
                import traceback
                traceback.print_exc()
                return None, str(e)
    
    def get_recording_status(self):
        """Get current recording status"""
        with self.recording_lock:
            if self.is_recording:
                duration = time.time() - self.recording_start_time
                return {
                    "recording": True,
                    "filename": self.current_video_file,
                    "duration": round(duration, 1),
                    "resolution": f"{config.VIDEO_SIZE[0]}x{config.VIDEO_SIZE[1]}",
                    "bitrate_mbps": config.VIDEO_BITRATE // 1000000,
                }
            return {"recording": False}
        
    def stop(self):
        """Stop camera and any active recording"""
        # Stop recording if active
        if self.is_recording:
            self.stop_recording()
            
        self.running = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=1.0)
        self.picam2.stop()
        self.picam2.close()

# Initialize camera
camera = CameraStream()
camera.start()

print(f"📁 Save folder: {config.SAVE_FOLDER}")

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
    """Web interface with live stream and video recording"""
    return '''<!DOCTYPE html>
<html><head><title>Camera Stream</title>
<style>
body{background:#1a1a1a;color:#fff;font-family:'Segoe UI',sans-serif;text-align:center;padding:20px;margin:0}
.container{max-width:900px;margin:0 auto}
h2{color:#fff;margin-bottom:5px}
.subtitle{color:#888;font-size:14px;margin-bottom:20px}
img{max-width:100%;border:3px solid #444;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.5)}
.controls{margin:20px 0;display:flex;flex-wrap:wrap;justify-content:center;gap:10px}
button{padding:12px 24px;font-size:16px;cursor:pointer;background:#444;color:#fff;border:none;border-radius:8px;transition:all 0.3s}
button:hover{background:#666;transform:scale(1.05)}
button.record{background:#c41e3a}
button.record:hover{background:#ff2d55}
button.record.recording{background:#ff2d55;animation:pulse 1s infinite}
button.stop{background:#ff6b35}
button.stop:hover{background:#ff8c5a}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}
#msg{margin:15px;padding:10px;border-radius:8px;min-height:20px}
#recordStatus{background:#2a2a2a;padding:10px 20px;border-radius:8px;margin:10px 0;display:none}
#recordStatus.active{display:block;background:#3a1a1a;border:1px solid #c41e3a}
.info{background:#252525;padding:15px;border-radius:10px;margin-top:20px;text-align:left}
.info h3{color:#aaa;margin:0 0 10px 0}
.info code{background:#333;padding:3px 8px;border-radius:4px;color:#8f8}
.endpoint{margin:5px 0}
.duration{font-family:monospace;font-size:24px;color:#ff2d55}
</style></head><body>
<div class="container">
<h2>📷 Camera Stream</h2>
<p class="subtitle">Normal Display Mode - Auto Settings</p>
<div id="recordStatus">
  <span>🔴 Recording: </span><span id="recFilename"></span>
  <div class="duration" id="recDuration">00:00</div>
</div>
<img src="/video_feed" alt="Live Stream">
<div class="controls">
<button onclick="save()">📸 Capture (S)</button>
<button onclick="window.open('/frame','_blank')">🖼️ Get Frame</button>
<button id="recordBtn" class="record" onclick="toggleRecord()">🎬 Record (R)</button>
</div>
<div id="msg"></div>
<div class="info">
<h3>📡 API Endpoints</h3>
<div class="endpoint"><code>GET /frame</code> - Current frame as JPEG</div>
<div class="endpoint"><code>GET /video_feed</code> - MJPEG stream</div>
<div class="endpoint"><code>POST /save_picture</code> - Save photo to disk</div>
<div class="endpoint"><code>POST /record/start</code> - Start video recording</div>
<div class="endpoint"><code>POST /record/stop</code> - Stop video recording</div>
<div class="endpoint"><code>GET /record/status</code> - Recording status</div>
<div class="endpoint"><code>GET /status</code> - Camera status</div>
</div>
</div>
<script>
let isRecording = false;
let recordTimer = null;
let recordStart = 0;

function save(){
  fetch('/save_picture',{method:'POST'}).then(r=>r.json()).then(d=>{
    let msg=document.getElementById('msg');
    msg.innerHTML=d.success?'<span style="color:#8f8">✅ Saved: '+d.filename+'</span>':'<span style="color:#f88">❌ '+d.error+'</span>';
    setTimeout(()=>msg.innerHTML='',3000);
  });
}

function toggleRecord(){
  if(isRecording){
    stopRecording();
  }else{
    startRecording();
  }
}

function startRecording(){
  fetch('/record/start',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.success){
      isRecording = true;
      recordStart = Date.now();
      document.getElementById('recordBtn').textContent = '⏹️ Stop (R)';
      document.getElementById('recordBtn').classList.add('recording');
      document.getElementById('recordBtn').classList.remove('record');
      document.getElementById('recordBtn').classList.add('stop');
      document.getElementById('recordStatus').classList.add('active');
      document.getElementById('recFilename').textContent = d.filename;
      recordTimer = setInterval(updateDuration, 1000);
      showMsg('🎬 Recording started: ' + d.filename, '#8f8');
    }else{
      showMsg('❌ ' + d.error, '#f88');
    }
  });
}

function stopRecording(){
  fetch('/record/stop',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.success){
      isRecording = false;
      clearInterval(recordTimer);
      document.getElementById('recordBtn').textContent = '🎬 Record (R)';
      document.getElementById('recordBtn').classList.remove('recording','stop');
      document.getElementById('recordBtn').classList.add('record');
      document.getElementById('recordStatus').classList.remove('active');
      showMsg('✅ Video saved: ' + d.filename + ' (' + d.duration + 's)', '#8f8');
    }else{
      showMsg('❌ ' + d.error, '#f88');
    }
  });
}

function updateDuration(){
  let elapsed = Math.floor((Date.now() - recordStart) / 1000);
  let mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
  let secs = String(elapsed % 60).padStart(2, '0');
  document.getElementById('recDuration').textContent = mins + ':' + secs;
}

function showMsg(text, color){
  let msg = document.getElementById('msg');
  msg.innerHTML = '<span style="color:'+color+'">'+text+'</span>';
  setTimeout(()=>msg.innerHTML='',5000);
}

// Check recording status on page load
fetch('/record/status').then(r=>r.json()).then(d=>{
  if(d.recording){
    isRecording = true;
    recordStart = Date.now() - (d.duration * 1000);
    document.getElementById('recordBtn').textContent = '⏹️ Stop (R)';
    document.getElementById('recordBtn').classList.add('recording','stop');
    document.getElementById('recordBtn').classList.remove('record');
    document.getElementById('recordStatus').classList.add('active');
    document.getElementById('recFilename').textContent = d.filename;
    recordTimer = setInterval(updateDuration, 1000);
    updateDuration();
  }
});

document.onkeydown=e=>{
  if(e.key.toLowerCase()=='s')save();
  if(e.key.toLowerCase()=='r')toggleRecord();
};
</script></body></html>'''

@app.route('/video_feed')
def video_feed():
    """MJPEG video stream"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/frame')
def get_frame():
    """Get current frame as JPEG"""
    jpeg_bytes = camera.get_frame_jpeg()
    if jpeg_bytes is None:
        return jsonify({"error": "No frame available"}), 503
    return Response(jpeg_bytes, mimetype='image/jpeg')

@app.route('/status')
def get_status():
    """Camera and server status"""
    frame = camera.get_frame()
    recording_status = camera.get_recording_status()
    return jsonify({
        "camera_running": camera.running,
        "frame_available": frame is not None,
        "resolution": config.SENSOR_SIZE,
        "video_resolution": config.VIDEO_SIZE,
        "video_bitrate_mbps": config.VIDEO_BITRATE // 1000000,
        "frame_rate": config.FRAME_RATE,
        "save_folder": config.SAVE_FOLDER,
        "video_folder": config.VIDEO_FOLDER,
        "mode": "Normal Display (Auto)",
        "recording": recording_status,
    })

# =============================================================================
# VIDEO RECORDING ROUTES
# =============================================================================
@app.route('/record/start', methods=['POST'])
def start_recording():
    """Start video recording"""
    try:
        filename, error = camera.start_recording()
        if error:
            return jsonify({"success": False, "error": error})
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/record/stop', methods=['POST'])
def stop_recording():
    """Stop video recording"""
    try:
        result, error = camera.stop_recording()
        if error:
            return jsonify({"success": False, "error": error})
        return jsonify({
            "success": True,
            "filename": result["filename"],
            "duration": result["duration"],
            "path": result["path"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/record/status')
def recording_status():
    """Get recording status"""
    return jsonify(camera.get_recording_status())

# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("📷 Camera Stream with VIDEO RECORDING")
    print("=" * 60)
    print(f"   Stream Resolution: {config.SENSOR_SIZE[0]}x{config.SENSOR_SIZE[1]}")
    print(f"   Video Resolution:  {config.VIDEO_SIZE[0]}x{config.VIDEO_SIZE[1]} (Full HD)")
    print(f"   Video Bitrate:     {config.VIDEO_BITRATE // 1000000} Mbps")
    print(f"   Frame Rate:        {config.FRAME_RATE} fps")
    print(f"   Mode: Auto Exposure, Auto White Balance, Autofocus")
    print("")
    print(f"   📁 Photos: {config.SAVE_FOLDER}")
    print(f"   🎬 Videos: {config.VIDEO_FOLDER}")
    print("")
    print("   🌐 Web Interface:")
    print("   → http://localhost:5000")
    print("")
    print("   ⌨️ Keyboard Shortcuts:")
    print("   → S = Capture photo")
    print("   → R = Start/Stop recording")
    print("")
    print("   📡 API Endpoints:")
    print("   → GET  /frame          - JPEG frame")
    print("   → GET  /video_feed     - MJPEG stream")
    print("   → POST /save_picture   - Save photo")
    print("   → POST /record/start   - Start recording")
    print("   → POST /record/stop    - Stop recording")
    print("   → GET  /record/status  - Recording status")
    print("   → GET  /status         - Camera status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
