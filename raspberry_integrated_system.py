#!/usr/bin/env python3
"""
=============================================================
HỆ THỐNG CẢNH BÁO TÍCH HỢP CHO XE - RASPBERRY PI
=============================================================
Tích hợp:
  1. Cảm biến siêu âm HC-SR04 (4 hướng: trước, sau, trái, phải)
  2. Camera USB DV20 + AI phát hiện ngủ gật
  3. Cảnh báo thống nhất qua buzzer GPIO

Cách chạy:
  python3 raspberry_integrated_system.py

Yêu cầu:
  pip install opencv-python mediapipe numpy tensorflow
  
Phần cứng:
  - 4x HC-SR04 (Trước, Sau, Trái, Phải)
  - 1x Buzzer (GPIO 12)
  - 1x USB Camera DV20
  - Raspberry Pi 4
=============================================================
"""

import RPi.GPIO as GPIO
import time
import threading
import sys
import signal
from pathlib import Path
from collections import deque

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# ============================================================
# CẤU HÌNH CHUNG
# ============================================================

# Cảm biến siêu âm
SENSORS = {
    "Trước": {"trig": 17, "echo": 27, "warn_dist": 50},
    "Sau":   {"trig": 22, "echo": 23, "warn_dist": 30},
    "Trái":  {"trig": 5,  "echo": 6,  "warn_dist": 40},
    "Phải":  {"trig": 24, "echo": 25, "warn_dist": 40},
}

BUZZER_PIN = 12

# Camera và AI
CAMERA_DEVICE = 0  # USB Camera DV20
MODEL_PATH = "models/eye_model_best.tflite"
IMG_SIZE = 32
DROWSY_THRESHOLD = 25  # Số frame mắt nhắm liên tục để cảnh báo (khoảng 1 giây)

# MediaPipe Face Landmarks
MP_FACE_MODEL_PATH = "models/face_landmarker.task"
MP_FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

LEFT_EYE_LANDMARKS  = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
RIGHT_EYE_LANDMARKS = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]


# ============================================================
# QUẢN LÝ BUZZER THỐNG NHẤT
# ============================================================

class UnifiedBuzzerController:
    """
    Điều khiển buzzer với các mức độ ưu tiên:
    1. DROWSY (nguy hiểm nhất) - beep liên tục nhanh
    2. COLLISION_DANGER (va chạm nguy hiểm) - beep dài
    3. COLLISION_WARNING (va chạm cảnh báo) - beep ngắn
    """
    
    def __init__(self, pin: int):
        self.pin = pin
        self.mode = None  # None, 'drowsy', 'danger', 'warning'
        self._stop_event = threading.Event()
        self._buzzer_thread = None
        self._lock = threading.Lock()
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
        print(f"[Buzzer] Khởi tạo tại GPIO {self.pin}")
    
    def set_drowsy_alert(self):
        """Cảnh báo ngủ gật (ưu tiên cao nhất)."""
        with self._lock:
            if self.mode != 'drowsy':
                self._stop_current()
                self.mode = 'drowsy'
                self._start_beep_pattern()
    
    def set_collision_danger(self):
        """Cảnh báo va chạm nguy hiểm (ưu tiên vừa)."""
        with self._lock:
            if self.mode not in ['drowsy']:  # Không override drowsy
                if self.mode != 'danger':
                    self._stop_current()
                    self.mode = 'danger'
                    self._start_beep_pattern()
    
    def set_collision_warning(self):
        """Cảnh báo va chạm thông thường (ưu tiên thấp)."""
        with self._lock:
            if self.mode is None:  # Chỉ bật nếu không có alert nào khác
                self.mode = 'warning'
                self._start_beep_pattern()
    
    def clear_drowsy(self):
        """Xóa cảnh báo ngủ gật."""
        with self._lock:
            if self.mode == 'drowsy':
                self._stop_current()
    
    def clear_collision(self):
        """Xóa tất cả cảnh báo va chạm."""
        with self._lock:
            if self.mode in ['danger', 'warning']:
                self._stop_current()
    
    def _stop_current(self):
        """Dừng pattern hiện tại."""
        if self._buzzer_thread and self._buzzer_thread.is_alive():
            self._stop_event.set()
            self._buzzer_thread.join(timeout=1.0)
        GPIO.output(self.pin, GPIO.LOW)
        self.mode = None
    
    def _start_beep_pattern(self):
        """Bắt đầu thread beep theo mode."""
        self._stop_event.clear()
        self._buzzer_thread = threading.Thread(target=self._beep_loop, daemon=True)
        self._buzzer_thread.start()
    
    def _beep_loop(self):
        """Vòng lặp beep theo pattern của mode hiện tại."""
        while not self._stop_event.is_set():
            current_mode = self.mode
            
            if current_mode == 'drowsy':
                # Beep liên tục nhanh: 0.2s on, 0.1s off
                GPIO.output(self.pin, GPIO.HIGH)
                if self._stop_event.wait(0.2): break
                GPIO.output(self.pin, GPIO.LOW)
                if self._stop_event.wait(0.1): break
                
            elif current_mode == 'danger':
                # Beep dài 3 lần: 0.3s on, 0.1s off
                for _ in range(3):
                    if self._stop_event.is_set(): break
                    GPIO.output(self.pin, GPIO.HIGH)
                    if self._stop_event.wait(0.3): break
                    GPIO.output(self.pin, GPIO.LOW)
                    if self._stop_event.wait(0.1): break
                if self._stop_event.wait(0.3): break
                
            elif current_mode == 'warning':
                # Beep ngắn 1 lần: 0.1s on
                GPIO.output(self.pin, GPIO.HIGH)
                if self._stop_event.wait(0.1): break
                GPIO.output(self.pin, GPIO.LOW)
                if self._stop_event.wait(0.5): break
            else:
                break
    
    def cleanup(self):
        """Dọn dẹp GPIO."""
        with self._lock:
            self._stop_current()
        GPIO.cleanup()
        print("[Buzzer] Đã cleanup GPIO")


# ============================================================
# HỆ THỐNG CẢM BIẾN SIÊU ÂM
# ============================================================

class UltrasonicSensorSystem:
    """Quản lý 4 cảm biến siêu âm và phát hiện nguy hiểm va chạm."""
    
    def __init__(self, sensors_config: dict, buzzer: UnifiedBuzzerController):
        self.sensors = sensors_config
        self.buzzer = buzzer
        self.running = False
        self._thread = None
        
        # Setup GPIO cho cảm biến
        for name, cfg in self.sensors.items():
            GPIO.setup(cfg["trig"], GPIO.OUT)
            GPIO.setup(cfg["echo"], GPIO.IN)
            GPIO.output(cfg["trig"], False)
        
        time.sleep(0.5)
        print("[Ultrasonic] Đã khởi tạo 4 cảm biến siêu âm")
    
    def get_distance(self, trig: int, echo: int) -> float:
        """Đo khoảng cách (cm) bằng HC-SR04."""
        GPIO.output(trig, True)
        time.sleep(0.00001)
        GPIO.output(trig, False)
        
        timeout = time.time() + 0.1
        start = time.time()
        while GPIO.input(echo) == 0:
            start = time.time()
            if time.time() > timeout:
                return None
        
        timeout = time.time() + 0.1
        stop = time.time()
        while GPIO.input(echo) == 1:
            stop = time.time()
            if time.time() > timeout:
                return None
        
        elapsed = stop - start
        distance = (elapsed * 34300) / 2
        return round(distance, 1)
    
    def start(self):
        """Bắt đầu monitor cảm biến trong thread riêng."""
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[Ultrasonic] Đã bắt đầu monitoring")
    
    def stop(self):
        """Dừng monitor."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[Ultrasonic] Đã dừng monitoring")
    
    def _monitor_loop(self):
        """Vòng lặp đọc cảm biến và cảnh báo."""
        while self.running:
            has_danger = False
            has_warning = False
            
            for name, cfg in self.sensors.items():
                dist = self.get_distance(cfg["trig"], cfg["echo"])
                
                if dist is None:
                    continue
                
                # Phân loại mức độ nguy hiểm
                if dist < cfg["warn_dist"] * 0.5:
                    has_danger = True
                    print(f"[{name:5s}] {dist:6.1f} cm — ⛔ NGUY HIỂM")
                elif dist < cfg["warn_dist"]:
                    has_warning = True
                    print(f"[{name:5s}] {dist:6.1f} cm — ⚠️  CẢNH BÁO")
            
            # Cập nhật buzzer (không override drowsy alert)
            if has_danger:
                self.buzzer.set_collision_danger()
            elif has_warning:
                self.buzzer.set_collision_warning()
            else:
                self.buzzer.clear_collision()
            
            time.sleep(0.2)  # Đọc 5 Hz


# ============================================================
# AI PHÁT HIỆN NGỦ GẬT
# ============================================================

def download_face_model(model_path: str, url: str):
    """Tải model MediaPipe nếu chưa có."""
    import urllib.request
    path = Path(model_path)
    if path.exists():
        return
    
    print(f"[MediaPipe] Đang tải model (~30MB)...")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, str(path))
        print(f"[MediaPipe] ✓ Đã tải xong")
    except Exception as e:
        raise RuntimeError(f"Không thể tải model: {e}")


class EyeStateClassifier:
    """Phân loại trạng thái mắt bằng TFLite model (tối ưu cho Raspberry Pi)."""
    
    def __init__(self, model_path: str):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Không tìm thấy model: {model_path}")
        
        # Load TFLite interpreter (nhẹ hơn nhiều so với TensorFlow đầy đủ)
        try:
            import tflite_runtime.interpreter as tflite
            print("[Model] Using tflite_runtime (lightweight)")
        except ImportError:
            import tensorflow as tf
            tflite = tf.lite
            print("[Model] Using tensorflow.lite (fallback)")
        
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        print(f"[Model] ✓ Loaded: {model_path}")
        print(f"[Model] Input shape: {self.input_details[0]['shape']}")
    
    def predict(self, eye_roi: np.ndarray) -> tuple:
        """
        Dự đoán trạng thái mắt.
        Returns: (class_id, confidence) - 0=closed, 1=open
        """
        resized = cv2.resize(eye_roi, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        input_batch = np.expand_dims(normalized, axis=0)
        
        # TFLite inference
        self.interpreter.set_tensor(self.input_details[0]['index'], input_batch)
        self.interpreter.invoke()
        probs = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        
        class_id = int(np.argmax(probs))
        confidence = float(probs[class_id])
        return class_id, confidence


class EyeDetector:
    """Phát hiện mắt bằng MediaPipe FaceLandmarker."""
    
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
        print("[MediaPipe] ✓ FaceLandmarker khởi tạo")
    
    def get_eye_roi(self, frame: np.ndarray, landmarks, eye_indices: list) -> np.ndarray:
        """Crop vùng mắt từ frame."""
        h, w = frame.shape[:2]
        xs = [int(landmarks[i].x * w) for i in eye_indices]
        ys = [int(landmarks[i].y * h) for i in eye_indices]
        
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        padding = 0.2
        pw = int((x_max - x_min) * padding)
        ph = int((y_max - y_min) * padding)
        
        x1 = max(0, x_min - pw)
        y1 = max(0, y_min - ph)
        x2 = min(w, x_max + pw)
        y2 = min(h, y_max + ph)
        
        if x2 <= x1 or y2 <= y1:
            return None
        
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        
        return cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    
    def detect_eyes(self, frame: np.ndarray) -> tuple:
        """
        Phát hiện mắt trong frame.
        Returns: (left_eye_roi, right_eye_roi)
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self.detector.detect(mp_image)
        
        if not result.face_landmarks:
            return None, None
        
        landmarks = result.face_landmarks[0]
        left_eye = self.get_eye_roi(frame, landmarks, LEFT_EYE_LANDMARKS)
        right_eye = self.get_eye_roi(frame, landmarks, RIGHT_EYE_LANDMARKS)
        
        return left_eye, right_eye
    
    def close(self):
        """Giải phóng detector."""
        self.detector.close()


class DrowsinessDetectionSystem:
    """Hệ thống phát hiện ngủ gật qua camera."""
    
    def __init__(self, model_path: str, camera_device: int, 
                 threshold: int, buzzer: UnifiedBuzzerController):
        self.classifier = EyeStateClassifier(model_path)
        self.eye_detector = EyeDetector()
        self.buzzer = buzzer
        self.threshold = threshold
        self.camera_device = camera_device
        
        self.closed_counter = 0
        self.is_drowsy = False
        self.running = False
        self._thread = None
        
        print(f"[Drowsiness] Khởi tạo (threshold={threshold} frames)")
    
    def start(self):
        """Bắt đầu monitor camera trong thread riêng."""
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[Drowsiness] Đã bắt đầu monitoring")
    
    def stop(self):
        """Dừng monitor."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.eye_detector.close()
        print("[Drowsiness] Đã dừng monitoring")
    
    def _monitor_loop(self):
        """Vòng lặp đọc camera và phát hiện ngủ gật."""
        # Mở camera
        cap = cv2.VideoCapture(self.camera_device)
        if not cap.isOpened():
            print(f"[Drowsiness] ❌ KHÔNG THỂ MỞ CAMERA {self.camera_device}!")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        print(f"[Drowsiness] ✓ Camera opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        
        frame_count = 0
        fps_deque = deque(maxlen=30)
        
        while self.running:
            t_start = time.time()
            
            ret, frame = cap.read()
            if not ret:
                print("[Drowsiness] Không đọc được frame, thử lại...")
                time.sleep(0.1)
                continue
            
            frame_count += 1
            
            # Phát hiện mắt
            left_eye_roi, right_eye_roi = self.eye_detector.detect_eyes(frame)
            
            left_open = None
            right_open = None
            
            # Phân loại mắt trái
            if left_eye_roi is not None:
                try:
                    class_id, conf = self.classifier.predict(left_eye_roi)
                    left_open = (class_id == 1)
                except Exception as e:
                    pass
            
            # Phân loại mắt phải
            if right_eye_roi is not None:
                try:
                    class_id, conf = self.classifier.predict(right_eye_roi)
                    right_open = (class_id == 1)
                except Exception as e:
                    pass
            
            # Logic phát hiện ngủ gật
            if left_open is not None or right_open is not None:
                both_closed = True
                if left_open is True: both_closed = False
                if right_open is True: both_closed = False
                
                if both_closed:
                    self.closed_counter += 1
                else:
                    self.closed_counter = 0
            
            # Kiểm tra ngưỡng
            was_drowsy = self.is_drowsy
            self.is_drowsy = self.closed_counter >= self.threshold
            
            # Cập nhật buzzer
            if self.is_drowsy:
                self.buzzer.set_drowsy_alert()
                if not was_drowsy:
                    print(f"\n⚠️⚠️⚠️  TÀI XẾ NGỦ GẬT PHÁT HIỆN!  ⚠️⚠️⚠️\n")
            else:
                self.buzzer.clear_drowsy()
                if was_drowsy:
                    print("[Drowsiness] Tài xế đã tỉnh táo trở lại")
            
            # Tính FPS
            elapsed_ms = (time.time() - t_start) * 1000
            fps_deque.append(elapsed_ms)
            
            # Log định kỳ
            if frame_count % 100 == 0:
                avg_ms = sum(fps_deque) / len(fps_deque)
                fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
                status = "😴 DROWSY" if self.is_drowsy else "✓ ALERT"
                l_state = "OPEN" if left_open else ("CLOSED" if left_open is False else "N/A")
                r_state = "OPEN" if right_open else ("CLOSED" if right_open is False else "N/A")
                print(f"[{frame_count:6d}] FPS:{fps:.1f} | L:{l_state:6s} R:{r_state:6s} | "
                      f"Counter:{self.closed_counter:2d}/{self.threshold} | {status}")
            
            time.sleep(0.01)  # Giảm tải CPU
        
        cap.release()


# ============================================================
# HÀM MAIN
# ============================================================

def main():
    print("\n" + "="*70)
    print("HỆ THỐNG CẢNH BÁO TÍCH HỢP CHO XE - RASPBERRY PI")
    print("="*70)
    print("Tính năng:")
    print("  1. Cảm biến siêu âm (4 hướng): Cảnh báo va chạm")
    print("  2. Camera AI: Phát hiện ngủ gật")
    print("  3. Buzzer thống nhất: Cảnh báo ưu tiên")
    print("="*70)
    
    # Kiểm tra model
    model_path = Path(MODEL_PATH)
    if not model_path.exists():
        print(f"\n❌ KHÔNG TÌM THẤY MODEL: {MODEL_PATH}")
        print("Vui lòng đảm bảo file model tồn tại trước khi chạy!")
        sys.exit(1)
    
    # Khởi tạo hệ thống
    buzzer = UnifiedBuzzerController(BUZZER_PIN)
    ultrasonic = UltrasonicSensorSystem(SENSORS, buzzer)
    drowsiness = DrowsinessDetectionSystem(
        MODEL_PATH, CAMERA_DEVICE, DROWSY_THRESHOLD, buzzer
    )
    
    # Handler Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n[Main] Đang dừng hệ thống...")
        ultrasonic.stop()
        drowsiness.stop()
        buzzer.cleanup()
        print("[Main] ✓ Đã thoát an toàn")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Bắt đầu cả hai hệ thống
    print("\n[Main] Khởi động hệ thống...\n")
    ultrasonic.start()
    time.sleep(1)  # Đợi ultrasonic ổn định
    drowsiness.start()
    
    print("\n✓ HỆ THỐNG HOẠT ĐỘNG")
    print("Nhấn Ctrl+C để dừng\n")
    print("-"*70)
    
    # Giữ chương trình chạy
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
