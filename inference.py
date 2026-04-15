"""
=============================================================
PHẦN 6: INFERENCE REAL-TIME TRÊN RASPBERRY PI 4
=============================================================
Chức năng:
  - Nhận video stream từ Mac qua WiFi (socket TCP port 9999)
  - Dùng MediaPipe FaceMesh để detect và crop vùng mắt
  - Dùng TFLite model để phân loại mắt Open/Closed
  - Kích hoạt buzzer GPIO pin 17 khi phát hiện ngủ gật
  - Hiển thị FPS, trạng thái, counter trên màn hình

Cách chạy:
  python inference.py --model models/eye_model.tflite --port 9999

Yêu cầu trên Raspberry Pi:
  pip install opencv-python mediapipe numpy RPi.GPIO
=============================================================
"""

import argparse
import socket
import struct
import time
import threading
import signal
import sys
import io
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# Import TFLite runtime (nhẹ hơn TensorFlow đầy đủ)
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_RUNTIME = True
except ImportError:
    # Fallback sang TensorFlow nếu không có tflite_runtime
    import tensorflow as tf
    tflite = tf.lite
    TFLITE_RUNTIME = False

# Import GPIO (chỉ chạy trên Raspberry Pi)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("[CẢNH BÁO] RPi.GPIO không khả dụng - chạy ở chế độ không có GPIO")


# ============================================================
# CẤU HÌNH
# ============================================================
DEFAULT_MODEL_PATH  = "models/eye_model.tflite"
DEFAULT_PORT        = 9999
IMG_SIZE            = 32          # Kích thước input model
DROWSY_THRESHOLD    = 20          # Số frame mắt nhắm liên tục để cảnh báo
GPIO_BUZZER_PIN     = 17          # GPIO pin cho buzzer
BUFFER_SIZE         = 65536       # Socket buffer size

# Màu sắc hiển thị (BGR)
COLOR_GREEN  = (0, 255, 0)
COLOR_RED    = (0, 0, 255)
COLOR_YELLOW = (0, 255, 255)
COLOR_WHITE  = (255, 255, 255)
COLOR_BLACK  = (0, 0, 0)
COLOR_CYAN   = (255, 255, 0)

# Chỉ số landmarks MediaPipe FaceMesh cho mắt trái và phải
# Dựa trên MediaPipe Face Mesh topology
LEFT_EYE_LANDMARKS  = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
RIGHT_EYE_LANDMARKS = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]


# ============================================================
# QUẢN LÝ GPIO BUZZER
# ============================================================

class BuzzerController:
    """Điều khiển buzzer qua GPIO với chế độ beep."""

    def __init__(self, pin: int):
        self.pin = pin
        self.active = False
        self._buzzer_thread = None
        self._stop_event = threading.Event()

        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"[GPIO] Buzzer khởi tạo tại pin {self.pin}")
        else:
            print(f"[GPIO] Chế độ mô phỏng (pin {self.pin})")

    def start_alarm(self):
        """Bắt đầu beep báo động liên tục."""
        if not self.active:
            self.active = True
            self._stop_event.clear()
            self._buzzer_thread = threading.Thread(
                target=self._beep_loop, daemon=True
            )
            self._buzzer_thread.start()

    def stop_alarm(self):
        """Dừng báo động."""
        if self.active:
            self.active = False
            self._stop_event.set()
            if GPIO_AVAILABLE:
                GPIO.output(self.pin, GPIO.LOW)

    def _beep_loop(self):
        """Vòng lặp beep: bật 0.3s - tắt 0.2s."""
        while not self._stop_event.is_set():
            if GPIO_AVAILABLE:
                GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(0.3)
            if GPIO_AVAILABLE:
                GPIO.output(self.pin, GPIO.LOW)
            time.sleep(0.2)

    def cleanup(self):
        """Giải phóng GPIO khi thoát."""
        self.stop_alarm()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
            print("[GPIO] Đã cleanup GPIO")


# ============================================================
# TFLite MODEL WRAPPER
# ============================================================

class EyeStateClassifier:
    """
    Wrapper cho TFLite interpreter.
    Phân loại trạng thái mắt: 0=closed, 1=open
    """

    def __init__(self, model_path: str):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Không tìm thấy model: {model_path}")

        # Load TFLite interpreter
        if TFLITE_RUNTIME:
            self.interpreter = tflite.Interpreter(model_path=model_path)
        else:
            self.interpreter = tflite.Interpreter(model_path=model_path)

        self.interpreter.allocate_tensors()

        # Lấy thông tin input/output tensors
        self.input_details  = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        self.input_shape = self.input_details[0]['shape']  # [1, 32, 32, 3]
        print(f"[Model] TFLite loaded: {model_path}")
        print(f"[Model] Input shape: {self.input_shape}")

    def preprocess(self, eye_roi: np.ndarray) -> np.ndarray:
        """
        Tiền xử lý vùng mắt:
        1. Resize về IMG_SIZE x IMG_SIZE
        2. Normalize về [0, 1]
        3. Thêm batch dimension
        """
        resized = cv2.resize(eye_roi, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        return np.expand_dims(normalized, axis=0)

    def predict(self, eye_roi: np.ndarray) -> tuple:
        """
        Dự đoán trạng thái mắt.
        
        Returns:
            (class_id, confidence): class 0=closed, 1=open
        """
        input_data = self.preprocess(eye_roi)

        # Chạy inference
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()

        # Lấy kết quả output
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        probabilities = output_data[0]  # Shape: [2]

        class_id    = int(np.argmax(probabilities))
        confidence  = float(probabilities[class_id])

        return class_id, confidence


# ============================================================
# MEDIAPIPE FACE MESH - DETECT MẮT
# ============================================================

MP_FACE_MODEL_PATH = "models/face_landmarker.task"
MP_FACE_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)


def download_face_model(model_path: str, url: str):
    """Tải model MediaPipe FaceLandmarker nếu chưa có."""
    import urllib.request
    path = Path(model_path)
    if path.exists():
        return
    print(f"[MediaPipe] Đang tải model (~30MB)...")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, str(path))
        print(f"[MediaPipe] ✓ Đã tải: {model_path}")
    except Exception as e:
        raise RuntimeError(f"Không thể tải model: {e}")


class EyeDetector:
    """
    Sử dụng MediaPipe FaceLandmarker (Tasks API, mediapipe>=0.10)
    để xác định và crop vùng mắt.
    """

    def __init__(self, model_path: str = MP_FACE_MODEL_PATH):
        download_face_model(model_path, MP_FACE_MODEL_URL)
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.detector = mp_vision.FaceLandmarker.create_from_options(options)
        print("[MediaPipe] FaceLandmarker (Tasks API) khởi tạo thành công")

    def get_eye_roi(self, frame: np.ndarray, landmarks, eye_indices: list,
                   padding: float = 0.15) -> np.ndarray | None:
        """
        Crop vùng mắt từ frame dựa trên landmarks.
        
        Args:
            frame      : Frame BGR từ camera
            landmarks  : MediaPipe face landmarks
            eye_indices: Danh sách index landmarks của mắt
            padding    : Padding thêm xung quanh vùng mắt (tỷ lệ)
        
        Returns:
            Ảnh RGB của vùng mắt, hoặc None nếu thất bại
        """
        h, w = frame.shape[:2]

        # Lấy tọa độ pixel của các landmarks mắt
        xs = [int(landmarks[i].x * w) for i in eye_indices]
        ys = [int(landmarks[i].y * h) for i in eye_indices]

        # Bounding box của vùng mắt
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # Thêm padding xung quanh
        eye_w = x_max - x_min
        eye_h = y_max - y_min
        pad_x = int(eye_w * padding)
        pad_y = int(eye_h * padding)

        x1 = max(0, x_min - pad_x)
        y1 = max(0, y_min - pad_y)
        x2 = min(w, x_max + pad_x)
        y2 = min(h, y_max + pad_y)

        # Kiểm tra vùng ROI hợp lệ
        if x2 <= x1 or y2 <= y1:
            return None

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        # Chuyển BGR → RGB cho model
        return cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)

    def detect_eyes(self, frame: np.ndarray) -> tuple:
        """
        Phát hiện mắt trong frame BGR.
        
        Returns:
            (left_eye_roi, right_eye_roi, face_landmarks)
            Trả về (None, None, None) nếu không tìm thấy mặt
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result    = self.detector.detect(mp_image)

        if not result.face_landmarks:
            return None, None, None

        face_landmarks = result.face_landmarks[0]

        left_eye  = self.get_eye_roi(frame, face_landmarks, LEFT_EYE_LANDMARKS)
        right_eye = self.get_eye_roi(frame, face_landmarks, RIGHT_EYE_LANDMARKS)

        return left_eye, right_eye, face_landmarks

    def draw_eye_landmarks(self, frame: np.ndarray, landmarks):
        """Vẽ các điểm landmark của mắt lên frame để debug."""
        h, w = frame.shape[:2]
        for idx in LEFT_EYE_LANDMARKS + RIGHT_EYE_LANDMARKS:
            lm = landmarks[idx]
            x  = int(lm.x * w)
            y  = int(lm.y * h)
            cv2.circle(frame, (x, y), 1, COLOR_CYAN, -1)

    def close(self):
        """Giải phóng tài nguyên MediaPipe."""
        self.detector.close()


# ============================================================
# SOCKET SERVER - NHẬN STREAM TỪ MAC
# ============================================================

class VideoStreamServer:
    """
    TCP server nhận video stream từ Mac.
    
    Protocol:
        - Client gửi: [4 bytes độ dài frame][N bytes JPEG data]
        - Server nhận và decode thành numpy array
    """

    def __init__(self, port: int):
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.connected = False

    def start(self) -> bool:
        """Khởi động server và chờ client kết nối."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Cho phép tái sử dụng port ngay sau khi tắt
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(30)  # Timeout 30s chờ kết nối

            # Lấy IP của Raspberry Pi để hiển thị
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"\n[Server] Đang lắng nghe tại {local_ip}:{self.port}")
            print(f"[Server] Hãy chạy stream_client.py trên Mac với IP: {local_ip}")
            print("[Server] Đang chờ kết nối...")

            self.client_socket, client_addr = self.server_socket.accept()
            # Tăng buffer size để giảm độ trễ
            self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
            self.connected = True
            print(f"[Server] ✓ Đã kết nối với client: {client_addr}")
            return True

        except socket.timeout:
            print("[Server] Timeout! Không có client nào kết nối trong 30 giây.")
            return False
        except Exception as e:
            print(f"[Server] Lỗi khởi động: {e}")
            return False

    def receive_frame(self) -> np.ndarray | None:
        """
        Nhận một frame từ client.
        
        Protocol: [4 bytes big-endian uint32 = độ dài][JPEG bytes]
        
        Returns:
            Frame numpy array BGR, hoặc None nếu lỗi
        """
        try:
            # Nhận header (4 bytes chứa độ dài dữ liệu)
            header = self._recv_exact(4)
            if header is None:
                return None

            # Giải mã độ dài frame
            frame_size = struct.unpack('>I', header)[0]

            # Kiểm tra độ dài hợp lý (tránh tấn công/lỗi)
            if frame_size <= 0 or frame_size > 10 * 1024 * 1024:  # Max 10MB
                print(f"[Server] Frame size bất thường: {frame_size}")
                return None

            # Nhận đúng frame_size bytes dữ liệu JPEG
            frame_data = self._recv_exact(frame_size)
            if frame_data is None:
                return None

            # Decode JPEG bytes thành numpy array
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame

        except (ConnectionResetError, BrokenPipeError):
            print("[Server] Client đã ngắt kết nối.")
            self.connected = False
            return None
        except Exception as e:
            print(f"[Server] Lỗi nhận frame: {e}")
            return None

    def _recv_exact(self, n: int) -> bytes | None:
        """Nhận đúng n bytes từ socket (blocking)."""
        data = b''
        while len(data) < n:
            try:
                chunk = self.client_socket.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except Exception:
                return None
        return data

    def close(self):
        """Đóng tất cả kết nối socket."""
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.connected = False
        print("[Server] Đã đóng kết nối")


# ============================================================
# LOGIC PHÁT HIỆN NGỦ GẬT
# ============================================================

class DrowsinessDetector:
    """
    Bộ phát hiện ngủ gật dựa trên đếm frame mắt nhắm liên tục.
    
    Logic:
        - Mỗi frame phân loại mắt là Open (1) hoặc Closed (0)
        - Nếu CẢ HAI mắt đều Closed: tăng counter
        - Nếu ít nhất một mắt Open: reset counter về 0
        - Counter > DROWSY_THRESHOLD: kích hoạt cảnh báo
    """

    def __init__(self, threshold: int = DROWSY_THRESHOLD):
        self.threshold     = threshold
        self.closed_counter = 0
        self.is_drowsy     = False
        self.fps_deque     = deque(maxlen=30)  # Lưu thời gian 30 frame gần nhất

    def update(self, left_eye_open: bool | None, right_eye_open: bool | None) -> bool:
        """
        Cập nhật trạng thái dựa trên kết quả phân loại mắt.
        
        Args:
            left_eye_open : True=mở, False=nhắm, None=không detect được
            right_eye_open: True=mở, False=nhắm, None=không detect được
        
        Returns:
            True nếu đang ngủ gật, False nếu tỉnh táo
        """
        # Chỉ tính khi detect được ít nhất 1 mắt
        if left_eye_open is None and right_eye_open is None:
            return self.is_drowsy

        # Xác định trạng thái: cả hai mắt nhắm → buồn ngủ
        both_closed = True
        detected_count = 0

        if left_eye_open is not None:
            detected_count += 1
            if left_eye_open:
                both_closed = False

        if right_eye_open is not None:
            detected_count += 1
            if right_eye_open:
                both_closed = False

        # Cập nhật counter
        if both_closed and detected_count > 0:
            self.closed_counter += 1
        else:
            self.closed_counter = 0

        # Kiểm tra ngưỡng cảnh báo
        self.is_drowsy = self.closed_counter >= self.threshold
        return self.is_drowsy

    def add_frame_time(self, elapsed_ms: float):
        """Thêm thời gian xử lý frame để tính FPS."""
        self.fps_deque.append(elapsed_ms)

    def get_fps(self) -> float:
        """Tính FPS trung bình dựa trên 30 frame gần nhất."""
        if len(self.fps_deque) < 2:
            return 0.0
        avg_ms = sum(self.fps_deque) / len(self.fps_deque)
        return 1000.0 / avg_ms if avg_ms > 0 else 0.0

    def reset(self):
        """Reset toàn bộ trạng thái detector."""
        self.closed_counter = 0
        self.is_drowsy = False


# ============================================================
# HÀM VẼ HUD (HEADS-UP DISPLAY)
# ============================================================

def draw_hud(frame: np.ndarray, fps: float, is_drowsy: bool,
             closed_counter: int, threshold: int,
             left_state: str, right_state: str):
    """
    Vẽ thông tin lên màn hình:
    - Trạng thái DROWSY/ALERT
    - FPS
    - Counter mắt nhắm
    - Trạng thái từng mắt
    """
    h, w = frame.shape[:2]

    # --- Panel nền bán trong suốt ở góc trên trái ---
    overlay = frame.copy()
    panel_w, panel_h = 280, 160
    cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), COLOR_BLACK, -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # FPS
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_WHITE, 2)

    # Trạng thái từng mắt
    left_color  = COLOR_GREEN if left_state == "OPEN" else COLOR_RED
    right_color = COLOR_GREEN if right_state == "OPEN" else COLOR_RED
    cv2.putText(frame, f"Left : {left_state}", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, left_color, 2)
    cv2.putText(frame, f"Right: {right_state}", (10, 95),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, right_color, 2)

    # Counter đếm ngược
    counter_color = COLOR_YELLOW if closed_counter > threshold // 2 else COLOR_WHITE
    cv2.putText(frame, f"Counter: {closed_counter}/{threshold}", (10, 125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, counter_color, 2)

    # --- Trạng thái chính DROWSY/ALERT ở giữa màn hình ---
    if is_drowsy:
        status_text = "!!! DROWSY !!!"
        status_color = COLOR_RED
        # Hiệu ứng nhấp nháy - vẽ background đỏ
        cv2.rectangle(frame, (0, h//2 - 50), (w, h//2 + 50), (0, 0, 200), -1)
    else:
        status_text = "ALERT"
        status_color = COLOR_GREEN

    # Tính vị trí text để căn giữa
    font_scale = 2.0
    thickness = 3
    (text_w, text_h), _ = cv2.getTextSize(
        status_text, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness
    )
    text_x = (w - text_w) // 2
    text_y = h // 2 + text_h // 2

    # Viền đen cho dễ đọc
    cv2.putText(frame, status_text, (text_x, text_y),
                cv2.FONT_HERSHEY_DUPLEX, font_scale, COLOR_BLACK, thickness + 2)
    cv2.putText(frame, status_text, (text_x, text_y),
                cv2.FONT_HERSHEY_DUPLEX, font_scale, status_color, thickness)

    # --- Thanh progress bar cho counter ---
    bar_x, bar_y = 10, 155
    bar_w, bar_h = 260, 15
    progress = min(closed_counter / threshold, 1.0)

    # Nền xám
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), -1)

    # Màu thanh progress: xanh → vàng → đỏ theo progress
    if progress < 0.5:
        bar_color = COLOR_GREEN
    elif progress < 0.8:
        bar_color = COLOR_YELLOW
    else:
        bar_color = COLOR_RED

    filled_w = int(bar_w * progress)
    if filled_w > 0:
        cv2.rectangle(frame, (bar_x, bar_y),
                      (bar_x + filled_w, bar_y + bar_h), bar_color, -1)

    # Viền thanh
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), COLOR_WHITE, 1)


# ============================================================
# HÀM MAIN INFERENCE
# ============================================================

def run_inference(model_path: str, port: int):
    """
    Vòng lặp inference chính:
    1. Nhận frame từ socket
    2. Detect mắt bằng MediaPipe
    3. Phân loại Open/Closed bằng TFLite
    4. Cập nhật logic cảnh báo
    5. Điều khiển GPIO buzzer
    6. Hiển thị HUD
    """
    print("\n" + "="*60)
    print("PHẦN 6: INFERENCE REAL-TIME - RASPBERRY PI 4")
    print("="*60)

    # Khởi tạo các components
    classifier  = EyeStateClassifier(model_path)
    eye_detector = EyeDetector()
    drowsiness  = DrowsinessDetector(threshold=DROWSY_THRESHOLD)
    buzzer      = BuzzerController(GPIO_BUZZER_PIN)
    server      = VideoStreamServer(port)

    # Handler khi nhấn Ctrl+C
    def signal_handler(sig, frame_):
        print("\n[Main] Nhận tín hiệu dừng, đang cleanup...")
        buzzer.cleanup()
        eye_detector.close()
        server.close()
        cv2.destroyAllWindows()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Chờ client kết nối
    if not server.start():
        print("[Main] Không thể khởi động server!")
        return

    print(f"\n[Main] Bắt đầu xử lý video...")
    print(f"[Main] Ngưỡng cảnh báo: {DROWSY_THRESHOLD} frames mắt nhắm liên tục")

    frame_count = 0
    prev_time   = time.time()

    while server.connected:
        frame_start = time.time()

        # --- Nhận frame từ Mac ---
        frame = server.receive_frame()
        if frame is None:
            if not server.connected:
                print("[Main] Mất kết nối với client")
                break
            continue

        frame_count += 1

        # --- Detect mắt bằng MediaPipe ---
        left_eye_roi, right_eye_roi, landmarks = eye_detector.detect_eyes(frame)

        left_state_str  = "N/A"
        right_state_str = "N/A"
        left_open       = None
        right_open      = None

        # --- Phân loại mắt trái ---
        if left_eye_roi is not None:
            try:
                class_id, confidence = classifier.predict(left_eye_roi)
                left_open      = (class_id == 1)  # 1 = open
                left_state_str = f"OPEN ({confidence:.0%})" if left_open else f"CLOSED ({confidence:.0%})"
            except Exception as e:
                print(f"[Model] Lỗi phân loại mắt trái: {e}")

        # --- Phân loại mắt phải ---
        if right_eye_roi is not None:
            try:
                class_id, confidence = classifier.predict(right_eye_roi)
                right_open      = (class_id == 1)
                right_state_str = f"OPEN ({confidence:.0%})" if right_open else f"CLOSED ({confidence:.0%})"
            except Exception as e:
                print(f"[Model] Lỗi phân loại mắt phải: {e}")

        # --- Cập nhật logic buồn ngủ ---
        is_drowsy = drowsiness.update(left_open, right_open)

        # --- Điều khiển buzzer ---
        if is_drowsy:
            buzzer.start_alarm()
        else:
            buzzer.stop_alarm()

        # --- Tính FPS ---
        frame_elapsed_ms = (time.time() - frame_start) * 1000
        drowsiness.add_frame_time(frame_elapsed_ms)
        fps = drowsiness.get_fps()

        # Vẽ landmarks mắt (chế độ debug)
        if landmarks is not None:
            eye_detector.draw_eye_landmarks(frame, landmarks)

        # --- Vẽ HUD lên frame ---
        draw_hud(
            frame, fps, is_drowsy,
            drowsiness.closed_counter, DROWSY_THRESHOLD,
            left_state_str, right_state_str
        )

        # --- Hiển thị frame ---
        cv2.imshow("Driver Drowsiness Detection - Raspberry Pi", frame)

        # Log định kỳ mỗi 100 frame
        if frame_count % 100 == 0:
            print(f"[{frame_count:6d}] FPS: {fps:.1f} | "
                  f"L: {left_state_str:20s} | R: {right_state_str:20s} | "
                  f"Counter: {drowsiness.closed_counter}/{DROWSY_THRESHOLD} | "
                  f"{'DROWSY' if is_drowsy else 'ALERT'}")

        # Nhấn 'q' để thoát
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[Main] Người dùng nhấn 'q', đang thoát...")
            break

    # --- Cleanup ---
    print(f"\n[Main] Tổng số frame đã xử lý: {frame_count}")
    buzzer.cleanup()
    eye_detector.close()
    server.close()
    cv2.destroyAllWindows()
    print("[Main] ✓ Đã thoát sạch sẽ")


# ============================================================
# ENTRY POINT
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Driver Drowsiness Detection - Raspberry Pi Inference Server"
    )
    parser.add_argument(
        '--model', type=str, default=DEFAULT_MODEL_PATH,
        help=f'Đường dẫn tới file .tflite (mặc định: {DEFAULT_MODEL_PATH})'
    )
    parser.add_argument(
        '--port', type=int, default=DEFAULT_PORT,
        help=f'Port lắng nghe kết nối từ Mac (mặc định: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '--threshold', type=int, default=DROWSY_THRESHOLD,
        help=f'Số frame mắt nhắm để kích hoạt cảnh báo (mặc định: {DROWSY_THRESHOLD})'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Cập nhật ngưỡng từ argument
    DROWSY_THRESHOLD = args.threshold

    print("="*60)
    print("DRIVER DROWSINESS DETECTION - RASPBERRY PI 4")
    print(f"Model   : {args.model}")
    print(f"Port    : {args.port}")
    print(f"Ngưỡng  : {DROWSY_THRESHOLD} frames")
    print(f"GPIO    : {'Có' if GPIO_AVAILABLE else 'Không (chế độ mô phỏng)'}")
    print("="*60)

    run_inference(args.model, args.port)
