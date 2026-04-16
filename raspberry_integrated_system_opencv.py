#!/usr/bin/env python3
"""
=============================================================
HỆ THỐNG CẢNH BÁO TÍCH HỢP CHO XE - RASPBERRY PI (OpenCV)
=============================================================
Phiên bản này sử dụng OpenCV thay cho MediaPipe.

Tích hợp:
  1. Cảm biến siêu âm HC-SR04 (4 hướng: trước, sau, trái, phải)
  2. Camera USB DV20 + AI phát hiện ngủ gật
  3. Cảnh báo thống nhất qua buzzer GPIO

Cách chạy:
  python3 raspberry_integrated_system_opencv.py

Yêu cầu:
  pip install -r requirements_rpi_opencv.txt
  
Phần cứng:
  - 4x HC-SR04 (Trước, Sau, Trái, Phải)
  - 1x Buzzer (GPIO 12)
  - 1x USB Camera DV20
  - Raspberry Pi 4 (ARM64)

Model files cần thiết:
  - models/eye_model_best.tflite (model phân loại mắt - TFLite format)
  - models/opencv_face_detector.pbtxt (OpenCV DNN config)
  - models/opencv_face_detector_uint8.pb (OpenCV DNN weights)
  - models/haarcascade_eye.xml (Haar Cascade cho mắt)
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
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite

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
IMG_SIZE = 32
DROWSY_THRESHOLD = 25  # Số frame mắt nhắm liên tục để cảnh báo (khoảng 1 giây)

# OpenCV Models
FACE_MODEL_PROTO = "models/opencv_face_detector.pbtxt"
FACE_MODEL_WEIGHTS = "models/opencv_face_detector_uint8.pb"
EYE_CASCADE_PATH = "models/haarcascade_eye.xml"

# Eye Classifier Model (TensorFlow Lite) - Compatible với Raspberry Pi
EYE_CLASSIFIER_MODEL = "models/eye_model_best_rpi.tflite"

# Face detection thresholds
FACE_CONFIDENCE_THRESHOLD = 0.5
EYE_CASCADE_SCALE_FACTOR = 1.1
EYE_CASCADE_MIN_NEIGHBORS = 5


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
        """Cảnh báo va chạm nguy hiểm (ưu tiên cao)."""
        with self._lock:
            if self.mode not in ('drowsy', 'danger'):
                self._stop_current()
                self.mode = 'danger'
                self._start_beep_pattern()
    
    def set_collision_warning(self):
        """Cảnh báo va chạm (ưu tiên thấp)."""
        with self._lock:
            if self.mode is None:
                self.mode = 'warning'
                self._start_beep_pattern()
    
    def clear_alert(self, alert_type: str):
        """Xóa cảnh báo."""
        with self._lock:
            if alert_type == 'drowsy' and self.mode == 'drowsy':
                self._stop_current()
            elif alert_type in ('danger', 'warning') and self.mode in ('danger', 'warning'):
                self._stop_current()
    
    def _start_beep_pattern(self):
        """Bắt đầu pattern beep tương ứng."""
        self._stop_event.clear()
        self._buzzer_thread = threading.Thread(target=self._beep_loop, daemon=True)
        self._buzzer_thread.start()
    
    def _stop_current(self):
        """Dừng pattern hiện tại."""
        self._stop_event.set()
        if self._buzzer_thread:
            self._buzzer_thread.join(timeout=1.0)
        GPIO.output(self.pin, GPIO.LOW)
        self.mode = None
    
    def _beep_loop(self):
        """Loop beep pattern."""
        try:
            while not self._stop_event.is_set():
                if self.mode == 'drowsy':
                    # Beep nhanh liên tục: 0.15s ON, 0.15s OFF
                    GPIO.output(self.pin, GPIO.HIGH)
                    if self._stop_event.wait(0.15):
                        break
                    GPIO.output(self.pin, GPIO.LOW)
                    if self._stop_event.wait(0.15):
                        break
                
                elif self.mode == 'danger':
                    # Beep dài: 0.5s ON, 0.3s OFF
                    GPIO.output(self.pin, GPIO.HIGH)
                    if self._stop_event.wait(0.5):
                        break
                    GPIO.output(self.pin, GPIO.LOW)
                    if self._stop_event.wait(0.3):
                        break
                
                elif self.mode == 'warning':
                    # Beep ngắn: 0.2s ON, 0.5s OFF
                    GPIO.output(self.pin, GPIO.HIGH)
                    if self._stop_event.wait(0.2):
                        break
                    GPIO.output(self.pin, GPIO.LOW)
                    if self._stop_event.wait(0.5):
                        break
                else:
                    break
        finally:
            GPIO.output(self.pin, GPIO.LOW)
    
    def cleanup(self):
        """Dọn dẹp GPIO."""
        self._stop_current()
        GPIO.cleanup(self.pin)
        print("[Buzzer] Đã cleanup")


# ============================================================
# CẢM BIẾN SIÊU ÂM
# ============================================================

class UltrasonicSensor:
    """Cảm biến siêu âm HC-SR04."""
    
    def __init__(self, name: str, trig: int, echo: int, warn_dist: int):
        self.name = name
        self.trig = trig
        self.echo = echo
        self.warn_dist = warn_dist
        
        GPIO.setup(self.trig, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.echo, GPIO.IN)
        print(f"[{self.name}] Cảm biến siêu âm khởi tạo (TRIG={trig}, ECHO={echo}, WARN={warn_dist}cm)")
    
    def get_distance(self) -> float:
        """Đo khoảng cách (cm). Trả về -1 nếu lỗi."""
        try:
            GPIO.output(self.trig, GPIO.HIGH)
            time.sleep(0.00001)  # 10µs pulse
            GPIO.output(self.trig, GPIO.LOW)
            
            timeout = time.time() + 0.05  # 50ms timeout
            
            # Chờ echo HIGH
            while GPIO.input(self.echo) == GPIO.LOW:
                if time.time() > timeout:
                    return -1
                pulse_start = time.time()
            
            # Chờ echo LOW
            timeout = time.time() + 0.05
            while GPIO.input(self.echo) == GPIO.HIGH:
                if time.time() > timeout:
                    return -1
                pulse_end = time.time()
            
            pulse_duration = pulse_end - pulse_start
            distance = (pulse_duration * 34300) / 2  # cm
            
            return distance if 2 <= distance <= 400 else -1
        except Exception as e:
            print(f"[{self.name}] Lỗi đo khoảng cách: {e}")
            return -1


class CollisionWarningSystem:
    """Hệ thống cảnh báo va chạm từ 4 cảm biến."""
    
    def __init__(self, sensors_config: dict, buzzer: UnifiedBuzzerController):
        self.sensors = {
            name: UltrasonicSensor(name, cfg['trig'], cfg['echo'], cfg['warn_dist'])
            for name, cfg in sensors_config.items()
        }
        self.buzzer = buzzer
        self.running = False
        self._threads = []
        self._current_warnings = {}  # {sensor_name: 'danger'/'warning'}
        self._lock = threading.Lock()
    
    def start(self):
        """Bắt đầu monitoring."""
        self.running = True
        for sensor in self.sensors.values():
            t = threading.Thread(target=self._monitor_sensor, args=(sensor,), daemon=True)
            t.start()
            self._threads.append(t)
        print("[CollisionWarning] Bắt đầu monitoring 4 cảm biến")
    
    def stop(self):
        """Dừng monitoring."""
        self.running = False
        for t in self._threads:
            t.join(timeout=2.0)
        print("[CollisionWarning] Đã dừng")
    
    def _monitor_sensor(self, sensor: UltrasonicSensor):
        """Monitor một cảm biến."""
        while self.running:
            dist = sensor.get_distance()
            
            if dist < 0:
                time.sleep(0.1)
                continue
            
            # Phân loại mức độ nguy hiểm
            if dist <= sensor.warn_dist * 0.5:  # Rất nguy hiểm (<50% warn_dist)
                level = 'danger'
                self._update_warning(sensor.name, level)
                print(f"[{sensor.name}] ⚠️  NGUY HIỂM: {dist:.1f}cm")
            elif dist <= sensor.warn_dist:  # Cảnh báo
                level = 'warning'
                self._update_warning(sensor.name, level)
                print(f"[{sensor.name}] ⚠  Cảnh báo: {dist:.1f}cm")
            else:  # An toàn
                self._clear_warning(sensor.name)
            
            time.sleep(0.1)  # 10Hz
    
    def _update_warning(self, sensor_name: str, level: str):
        """Cập nhật cảnh báo."""
        with self._lock:
            self._current_warnings[sensor_name] = level
            self._update_buzzer()
    
    def _clear_warning(self, sensor_name: str):
        """Xóa cảnh báo."""
        with self._lock:
            if sensor_name in self._current_warnings:
                del self._current_warnings[sensor_name]
                self._update_buzzer()
    
    def _update_buzzer(self):
        """Cập nhật trạng thái buzzer dựa trên các cảnh báo hiện tại."""
        if not self._current_warnings:
            self.buzzer.clear_alert('danger')
            self.buzzer.clear_alert('warning')
        elif 'danger' in self._current_warnings.values():
            self.buzzer.set_collision_danger()
        else:
            self.buzzer.set_collision_warning()


# ============================================================
# PHÁT HIỆN NGỦ GẬT - OpenCV VERSION
# ============================================================

class EyeStateClassifier:
    """Phân loại trạng thái mắt bằng TensorFlow Lite model."""
    
    def __init__(self, model_path: str):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model không tồn tại: {model_path}")
        
        # Load TFLite model
        print(f"[EyeClassifier] Đang tải TFLite model: {model_path}")
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        print(f"[EyeClassifier] ✓ Model tải thành công")
        
        # Get input/output details
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # Get input shape
        self.input_shape = self.input_details[0]['shape']
        print(f"[EyeClassifier] Input shape: {self.input_shape}")
        print(f"[EyeClassifier] Output shape: {self.output_details[0]['shape']}")
    
    def predict(self, eye_roi: np.ndarray) -> tuple:
        """
        Dự đoán trạng thái mắt.
        Returns: (class_id, confidence) - 0=closed, 1=open
        """
        # Preprocess
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


class EyeDetectorOpenCV:
    """Phát hiện mắt bằng OpenCV DNN + Haar Cascade."""
    
    def __init__(self, face_proto: str, face_weights: str, eye_cascade: str):
        # Load OpenCV DNN face detector
        if not Path(face_proto).exists() or not Path(face_weights).exists():
            raise FileNotFoundError(
                f"Face detection model không tồn tại:\n"
                f"  {face_proto}\n"
                f"  {face_weights}\n"
                f"Chạy install_rpi.sh để tải models."
            )
        
        self.face_net = cv2.dnn.readNetFromTensorflow(face_weights, face_proto)
        print("[OpenCV] ✓ Face detector (DNN) tải thành công")
        
        # Load Haar Cascade eye detector
        if not Path(eye_cascade).exists():
            raise FileNotFoundError(
                f"Eye cascade không tồn tại: {eye_cascade}\n"
                f"Chạy install_rpi.sh để tải models."
            )
        
        self.eye_cascade = cv2.CascadeClassifier(eye_cascade)
        print("[OpenCV] ✓ Eye detector (Haar Cascade) tải thành công")
    
    def detect_face(self, frame: np.ndarray) -> tuple:
        """
        Phát hiện khuôn mặt.
        Returns: (x, y, w, h) hoặc None
        """
        h, w = frame.shape[:2]
        
        # Prepare input blob
        blob = cv2.dnn.blobFromImage(
            frame, 1.0, (300, 300), [104, 117, 123], False, False
        )
        
        self.face_net.setInput(blob)
        detections = self.face_net.forward()
        
        # Tìm detection có confidence cao nhất
        best_confidence = 0
        best_box = None
        
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > FACE_CONFIDENCE_THRESHOLD and confidence > best_confidence:
                best_confidence = confidence
                
                x1 = int(detections[0, 0, i, 3] * w)
                y1 = int(detections[0, 0, i, 4] * h)
                x2 = int(detections[0, 0, i, 5] * w)
                y2 = int(detections[0, 0, i, 6] * h)
                
                best_box = (x1, y1, x2 - x1, y2 - y1)
        
        return best_box
    
    def detect_eyes_in_face(self, face_roi: np.ndarray) -> tuple:
        """
        Phát hiện mắt trong vùng khuôn mặt.
        Returns: (left_eye_roi, right_eye_roi)
        """
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        
        # Detect eyes
        eyes = self.eye_cascade.detectMultiScale(
            gray,
            scaleFactor=EYE_CASCADE_SCALE_FACTOR,
            minNeighbors=EYE_CASCADE_MIN_NEIGHBORS,
            minSize=(20, 20)
        )
        
        if len(eyes) < 2:
            return None, None
        
        # Sắp xếp eyes theo x-coordinate (trái sang phải)
        eyes_sorted = sorted(eyes, key=lambda e: e[0])
        
        # Lấy 2 mắt (giả định: mắt trái = x nhỏ, mắt phải = x lớn)
        left_x, left_y, left_w, left_h = eyes_sorted[0]
        right_x, right_y, right_w, right_h = eyes_sorted[1] if len(eyes_sorted) > 1 else eyes_sorted[0]
        
        # Crop eye ROIs
        left_eye = face_roi[left_y:left_y+left_h, left_x:left_x+left_w]
        right_eye = face_roi[right_y:right_y+right_h, right_x:right_x+right_w]
        
        # Convert to RGB
        left_eye = cv2.cvtColor(left_eye, cv2.COLOR_BGR2RGB) if left_eye.size > 0 else None
        right_eye = cv2.cvtColor(right_eye, cv2.COLOR_BGR2RGB) if right_eye.size > 0 else None
        
        return left_eye, right_eye
    
    def detect_eyes(self, frame: np.ndarray) -> tuple:
        """
        Phát hiện mắt trong frame.
        Returns: (left_eye_roi, right_eye_roi)
        """
        # Step 1: Detect face
        face_box = self.detect_face(frame)
        
        if face_box is None:
            return None, None
        
        x, y, w, h = face_box
        
        # Step 2: Extract face ROI
        face_roi = frame[y:y+h, x:x+w]
        
        if face_roi.size == 0:
            return None, None
        
        # Step 3: Detect eyes in face
        return self.detect_eyes_in_face(face_roi)


class DrowsinessDetectionSystem:
    """Hệ thống phát hiện ngủ gật qua camera (OpenCV + TFLite version)."""
    
    def __init__(self, model_path: str, camera_device: int, 
                 threshold: int, buzzer: UnifiedBuzzerController):
        self.classifier = EyeStateClassifier(model_path)
        self.eye_detector = EyeDetectorOpenCV(
            FACE_MODEL_PROTO, FACE_MODEL_WEIGHTS, EYE_CASCADE_PATH
        )
        self.buzzer = buzzer
        self.threshold = threshold
        self.camera_device = camera_device
        
        self.closed_counter = 0
        self.is_drowsy = False
        self.running = False
        self._thread = None
    
    def start(self):
        """Bắt đầu detection."""
        self.running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        print("[DrowsinessDetection] Bắt đầu detection")
    
    def stop(self):
        """Dừng detection."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        print("[DrowsinessDetection] Đã dừng")
    
    def _detection_loop(self):
        """Loop detection."""
        cap = cv2.VideoCapture(self.camera_device)
        
        if not cap.isOpened():
            print("[DrowsinessDetection] ❌ Không thể mở camera")
            return
        
        # Giảm resolution để tăng performance
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print("[DrowsinessDetection] ✓ Camera khởi tạo thành công")
        
        frame_count = 0
        
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print("[DrowsinessDetection] ⚠ Không đọc được frame")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # Phát hiện mắt
                left_eye, right_eye = self.eye_detector.detect_eyes(frame)
                
                if left_eye is None or right_eye is None:
                    # Không phát hiện được mắt - reset counter
                    if self.closed_counter > 0:
                        self.closed_counter = 0
                    continue
                
                # Phân loại trạng thái mắt
                left_state, left_conf = self.classifier.predict(left_eye)
                right_state, right_conf = self.classifier.predict(right_eye)
                
                # Cả 2 mắt nhắm (class_id = 0)
                both_closed = (left_state == 0 and right_state == 0)
                
                if both_closed:
                    self.closed_counter += 1
                else:
                    self.closed_counter = 0
                
                # Cảnh báo nếu mắt nhắm quá lâu
                if self.closed_counter >= self.threshold:
                    if not self.is_drowsy:
                        self.is_drowsy = True
                        self.buzzer.set_drowsy_alert()
                        print(f"[DrowsinessDetection] ⚠️  CẢNH BÁO NGỦ GẬT! (frames={self.closed_counter})")
                else:
                    if self.is_drowsy:
                        self.is_drowsy = False
                        self.buzzer.clear_alert('drowsy')
                        print(f"[DrowsinessDetection] ✓ Tỉnh táo trở lại")
                
                # Log mỗi 30 frames
                if frame_count % 30 == 0:
                    status = "CLOSED" if both_closed else "OPEN"
                    print(f"[DrowsinessDetection] Eyes: {status} | Counter: {self.closed_counter}/{self.threshold}")
                
                time.sleep(0.03)  # ~30 FPS
        
        finally:
            cap.release()
            print("[DrowsinessDetection] Camera released")


# ============================================================
# MAIN SYSTEM
# ============================================================

class IntegratedSafetySystem:
    """Hệ thống an toàn tích hợp."""
    
    def __init__(self):
        print("=" * 60)
        print("HỆ THỐNG CẢNH BÁO TÍCH HỢP CHO XE - OpenCV + TFLite Version")
        print("=" * 60)
        
        # Khởi tạo buzzer controller
        self.buzzer = UnifiedBuzzerController(BUZZER_PIN)
        
        # Khởi tạo collision warning system
        self.collision_system = CollisionWarningSystem(SENSORS, self.buzzer)
        
        # Khởi tạo drowsiness detection system
        self.drowsiness_system = DrowsinessDetectionSystem(
            EYE_CLASSIFIER_MODEL,
            CAMERA_DEVICE,
            DROWSY_THRESHOLD,
            self.buzzer
        )
    
    def start(self):
        """Bắt đầu hệ thống."""
        print("\n[System] Bắt đầu hệ thống...")
        
        self.collision_system.start()
        time.sleep(1)
        
        self.drowsiness_system.start()
        
        print("[System] ✓ Hệ thống đang chạy")
        print("\nNhấn Ctrl+C để dừng...")
    
    def stop(self):
        """Dừng hệ thống."""
        print("\n[System] Đang dừng hệ thống...")
        
        self.drowsiness_system.stop()
        self.collision_system.stop()
        self.buzzer.cleanup()
        
        GPIO.cleanup()
        
        print("[System] ✓ Đã dừng hoàn toàn")
    
    def run(self):
        """Chạy hệ thống (blocking)."""
        self.start()
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[System] Nhận tín hiệu dừng...")
        finally:
            self.stop()


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Main function."""
    # Check model files
    print("[System] Kiểm tra model files...")
    
    # Check OpenCV models (required)
    required_files = [
        FACE_MODEL_PROTO,
        FACE_MODEL_WEIGHTS,
        EYE_CASCADE_PATH,
    ]
    
    missing_files = [f for f in required_files if not Path(f).exists()]
    
    if missing_files:
        print("❌ Thiếu các file OpenCV models:")
        for f in missing_files:
            print(f"   - {f}")
        print("\nVui lòng chạy: ./install_rpi.sh")
        sys.exit(1)
    
    # Check eye classifier model (TFLite format)
    if not Path(EYE_CLASSIFIER_MODEL).exists():
        print(f"❌ Không tìm thấy eye classifier model: {EYE_CLASSIFIER_MODEL}")
        print(f"\nVui lòng copy model TFLite vào thư mục models/")
        sys.exit(1)
    
    print(f"✓ Tìm thấy eye classifier model: {EYE_CLASSIFIER_MODEL}")
    
    # Run system
    system = IntegratedSafetySystem()
    system.run()


if __name__ == "__main__":
    main()
