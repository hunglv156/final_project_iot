# 🚗 Hệ thống cảnh báo tích hợp cho xe - Raspberry Pi

Hệ thống AI phát hiện ngủ gật kết hợp cảm biến siêu âm phát hiện va chạm.

## 📋 Tổng quan

### Tính năng

1. **🎯 Phát hiện ngủ gật bằng AI**
   - Camera USB DV20 + TensorFlow Lite
   - Model AI nhẹ (0.62 MB) tối ưu cho Raspberry Pi
   - Phát hiện real-time khi tài xế nhắm mắt

2. **📡 Cảnh báo va chạm 4 hướng**
   - 4 cảm biến siêu âm HC-SR04
   - Phát hiện vật cản: Trước, Sau, Trái, Phải
   - 2 mức: Cảnh báo & Nguy hiểm

3. **🔔 Buzzer thông minh**
   - Tự động ưu tiên cảnh báo ngủ gật
   - 3 pattern khác nhau cho từng mức độ

## 🎯 Files quan trọng

```
final_project/
├── raspberry_integrated_system.py    # Code chính - chạy file này
├── requirements_rpi.txt               # Dependencies cho Raspberry Pi
├── models/
│   ├── eye_model_best.tflite         # AI model (0.62 MB) ⭐
│   └── face_landmarker.task          # MediaPipe (3.6 MB)
├── DEPLOY_RASPBERRY_PI.md            # Hướng dẫn deploy chi tiết
└── check_deployment.sh                # Script kiểm tra files
```

## 🚀 Quick Start

### Trên máy tính (Mac)

```bash
# Kiểm tra files đã đủ chưa
./check_deployment.sh
```

### Trên Raspberry Pi

```bash
# 1. Tạo thư mục
mkdir -p ~/final_project/models

# 2. Copy files từ Mac (SCP)
# Xem chi tiết trong DEPLOY_RASPBERRY_PI.md

# 3. Cài đặt dependencies
pip3 install -r requirements_rpi.txt

# 4. Chạy hệ thống
python3 raspberry_integrated_system.py
```

## 📊 So sánh model

| Model | Kích thước | RAM | Tốc độ | Khuyên dùng |
|-------|-----------|-----|--------|-------------|
| **eye_model_best.tflite** | 0.62 MB | ~150MB | Nhanh | ✅ Raspberry Pi |
| eye_model_best.h5 | 2.86 MB | ~500MB | Chậm | ❌ Không khuyên dùng |

**Lợi ích .tflite:**
- Nhỏ hơn **78.2%**
- Nhanh hơn **2-3 lần**
- Chỉ cần cài `tflite-runtime` (~10MB) thay vì `tensorflow` (~2GB)

## 🔌 Sơ đồ kết nối phần cứng

### Raspberry Pi GPIO

```
Cảm biến Trước:  TRIG=GPIO17  ECHO=GPIO27
Cảm biến Sau:    TRIG=GPIO22  ECHO=GPIO23
Cảm biến Trái:   TRIG=GPIO5   ECHO=GPIO6
Cảm biến Phải:   TRIG=GPIO24  ECHO=GPIO25
Buzzer:          GPIO12
Camera:          USB port (any)
```

## 🎛 Cấu hình mặc định

```python
DROWSY_THRESHOLD = 25        # Frames (khoảng 1 giây)
CAMERA_DEVICE = 0            # /dev/video0
BUZZER_PIN = 12              # GPIO 12

# Ngưỡng cảnh báo cảm biến
"Trước": 50 cm
"Sau":   30 cm
"Trái":  40 cm
"Phải":  40 cm
```

## 📖 Tài liệu

- **DEPLOY_RASPBERRY_PI.md**: Hướng dẫn chi tiết deploy
- **check_deployment.sh**: Kiểm tra files trước khi deploy

## 🔧 Troubleshooting nhanh

### Camera không hoạt động
```bash
ls /dev/video*  # Kiểm tra camera
```

### GPIO error
```bash
sudo python3 raspberry_integrated_system.py  # Chạy với sudo
```

### TFLite không tìm thấy
```bash
pip3 install tflite-runtime
```

## 📈 Hiệu năng

- **FPS**: 15-20 FPS
- **CPU**: 30-40% (1 core)
- **RAM**: ~150-200 MB
- **Độ trễ**: 50-100ms

## 🎓 Tech Stack

- **Python 3.7+**
- **TensorFlow Lite**: AI inference
- **MediaPipe**: Face detection
- **OpenCV**: Camera processing
- **RPi.GPIO**: Hardware control

## 📝 Lưu ý

- ✅ Không cần màn hình, chạy hoàn toàn background
- ✅ Log ra terminal để debug
- ✅ Tự động cleanup GPIO khi thoát (Ctrl+C)
- ✅ Model đã được tối ưu cho Raspberry Pi

---

**Tác giả**: Hung Le  
**Ngày**: 2026-04-15  
**Platform**: Raspberry Pi 4
