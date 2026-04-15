# Hướng dẫn Deploy lên Raspberry Pi 4

## 📦 Files cần thiết

Chỉ cần copy 4 files/thư mục sau sang Raspberry Pi:

```
final_project/
├── raspberry_integrated_system.py    # Code chính (22 KB)
├── requirements_rpi.txt               # Dependencies
└── models/
    ├── eye_model_best.tflite         # AI model (0.62 MB) ⭐
    └── face_landmarker.task          # MediaPipe model (3.6 MB)
```

**Tổng dung lượng**: ~4.3 MB

---

## 🔌 Kết nối phần cứng

### Cảm biến siêu âm HC-SR04 (4 cái)

| Hướng  | TRIG | ECHO | Ngưỡng cảnh báo |
|--------|------|------|-----------------|
| Trước  | GPIO 17 | GPIO 27 | 50 cm |
| Sau    | GPIO 22 | GPIO 23 | 30 cm |
| Trái   | GPIO 5  | GPIO 6  | 40 cm |
| Phải   | GPIO 24 | GPIO 25 | 40 cm |

### Buzzer

- **GPIO 12** (hoặc bất kỳ GPIO PWM nào)
- GND → GND

### Camera USB DV20

- Cắm vào cổng USB bất kỳ
- Raspberry Pi sẽ tự nhận là `/dev/video0`

---

## 🚀 Cài đặt trên Raspberry Pi

### Bước 1: Chuẩn bị Raspberry Pi

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt Python dependencies hệ thống
sudo apt install -y python3-pip python3-opencv

# Tạo thư mục project
mkdir -p ~/final_project/models
cd ~/final_project
```

### Bước 2: Copy files từ Mac sang Raspberry Pi

**Cách 1: Dùng SCP (qua mạng WiFi/Ethernet)**

```bash
# Trên Mac, chạy lệnh này (thay PI_IP bằng IP của Raspberry Pi)
scp raspberry_integrated_system.py pi@PI_IP:~/final_project/
scp requirements_rpi.txt pi@PI_IP:~/final_project/
scp models/eye_model_best.tflite pi@PI_IP:~/final_project/models/
scp models/face_landmarker.task pi@PI_IP:~/final_project/models/

# Ví dụ:
# scp raspberry_integrated_system.py pi@192.168.1.100:~/final_project/
```

**Cách 2: Dùng USB hoặc thẻ nhớ SD**

- Copy 4 files vào USB
- Cắm USB vào Raspberry Pi
- Copy vào thư mục `~/final_project/`

### Bước 3: Cài đặt Python packages

```bash
cd ~/final_project

# Cài đặt dependencies (mất khoảng 5-10 phút)
pip3 install -r requirements_rpi.txt

# Hoặc cài thủ công từng package:
pip3 install tflite-runtime opencv-python mediapipe numpy RPi.GPIO
```

### Bước 4: Kiểm tra camera

```bash
# Kiểm tra camera có được nhận diện không
ls /dev/video*

# Output mong đợi:
# /dev/video0
```

### Bước 5: Chạy hệ thống

```bash
cd ~/final_project
python3 raspberry_integrated_system.py
```

---

## ✅ Kiểm tra hệ thống hoạt động

Khi chạy thành công, bạn sẽ thấy output như sau:

```
======================================================================
HỆ THỐNG CẢNH BÁO TÍCH HỢP CHO XE - RASPBERRY PI
======================================================================
Tính năng:
  1. Cảm biến siêu âm (4 hướng): Cảnh báo va chạm
  2. Camera AI: Phát hiện ngủ gật
  3. Buzzer thống nhất: Cảnh báo ưu tiên
======================================================================

[Buzzer] Khởi tạo tại GPIO 12
[Ultrasonic] Đã khởi tạo 4 cảm biến siêu âm
[Model] Using tflite_runtime (lightweight)
[Model] ✓ Loaded: models/eye_model_best.tflite
[Model] Input shape: [1 32 32 3]
[MediaPipe] ✓ FaceLandmarker khởi tạo
[Drowsiness] Khởi tạo (threshold=25 frames)

[Main] Khởi động hệ thống...

[Ultrasonic] Đã bắt đầu monitoring
[Drowsiness] ✓ Camera opened: 640x480
[Drowsiness] Đã bắt đầu monitoring

✓ HỆ THỐNG HOẠT ĐỘNG
Nhấn Ctrl+C để dừng
----------------------------------------------------------------------
```

---

## 🎯 Hành vi hệ thống

### 1. Cảnh báo va chạm (Cảm biến siêu âm)

- **Cảnh báo thông thường** (< ngưỡng cảnh báo): Beep ngắn
- **Nguy hiểm** (< 50% ngưỡng): Beep dài 3 lần

### 2. Cảnh báo ngủ gật (Camera AI)

- Phát hiện khi tài xế nhắm mắt liên tục **25 frames** (~1 giây)
- Beep liên tục nhanh (0.2s on / 0.1s off)
- **Ưu tiên cao nhất** - sẽ override cảnh báo va chạm

### 3. Ưu tiên cảnh báo

```
DROWSY (ngủ gật)  →  Ưu tiên 1 (cao nhất)
    ↓
DANGER (va chạm nguy hiểm)  →  Ưu tiên 2
    ↓
WARNING (va chạm cảnh báo)  →  Ưu tiên 3 (thấp nhất)
```

---

## 🛠 Troubleshooting

### Lỗi: "No module named 'tflite_runtime'"

```bash
# Cài tflite_runtime thủ công
pip3 install tflite-runtime
```

### Lỗi: "Cannot open camera device 0"

```bash
# Kiểm tra camera
ls /dev/video*

# Nếu là /dev/video1, sửa trong code:
# CAMERA_DEVICE = 1
```

### Lỗi: "No module named 'cv2'"

```bash
# Cài OpenCV
sudo apt install python3-opencv
pip3 install opencv-python
```

### Lỗi GPIO

```bash
# Đảm bảo chạy với quyền GPIO
sudo python3 raspberry_integrated_system.py

# Hoặc thêm user vào group gpio
sudo usermod -a -G gpio pi
```

### Camera chậm / FPS thấp

- Giảm resolution trong code (dòng 311):
  ```python
  cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)   # Thay vì 640
  cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # Thay vì 480
  ```

---

## 🔧 Tùy chỉnh cấu hình

### Thay đổi ngưỡng cảnh báo ngủ gật

Trong file `raspberry_integrated_system.py`, dòng 30:

```python
DROWSY_THRESHOLD = 25  # Giảm = nhạy hơn, tăng = chậm hơn
```

### Thay đổi ngưỡng cảm biến

Trong file `raspberry_integrated_system.py`, dòng 18-23:

```python
SENSORS = {
    "Trước": {"trig": 17, "echo": 27, "warn_dist": 50},  # ← Thay đổi warn_dist
    "Sau":   {"trig": 22, "echo": 23, "warn_dist": 30},
    # ...
}
```

### Thay đổi pattern buzzer

Trong class `UnifiedBuzzerController`, dòng 110-132

---

## 🚗 Chạy tự động khi khởi động

### Tạo systemd service

```bash
sudo nano /etc/systemd/system/car-warning.service
```

Nội dung file:

```ini
[Unit]
Description=Car Warning System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/final_project
ExecStart=/usr/bin/python3 /home/pi/final_project/raspberry_integrated_system.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable car-warning.service
sudo systemctl start car-warning.service

# Kiểm tra status
sudo systemctl status car-warning.service

# Xem log
sudo journalctl -u car-warning.service -f
```

---

## 📊 Thông số kỹ thuật

| Thông số | Giá trị |
|----------|---------|
| **Model size** | 0.62 MB (TFLite) |
| **RAM usage** | ~150-200 MB |
| **CPU usage** | 30-40% (1 core) |
| **FPS camera** | 15-20 FPS |
| **Độ trễ phát hiện** | ~50-100ms |
| **Tần số đọc cảm biến** | 5 Hz (200ms/lần) |

---

## 📝 Ghi chú

- **KHÔNG CÓ GUI**: Hệ thống chạy hoàn toàn background, không hiển thị cửa sổ
- **Log terminal**: Tất cả thông tin được in ra terminal để debug
- **Thoát an toàn**: Nhấn `Ctrl+C` để dừng, hệ thống sẽ tự động cleanup GPIO

---

## 🎓 Tài liệu tham khảo

- TensorFlow Lite: https://www.tensorflow.org/lite
- MediaPipe: https://developers.google.com/mediapipe
- RPi.GPIO: https://pypi.org/project/RPi.GPIO/
