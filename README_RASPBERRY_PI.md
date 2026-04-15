# Hướng Dẫn Nhanh - Raspberry Pi 4

## ⚠️ Lưu Ý Quan Trọng - TFLite Runtime

**Package `tflite-runtime` đã DEPRECATED từ TensorFlow 2.16+**

Khi chạy `pip install tflite-runtime` bạn sẽ gặp lỗi:
```
ERROR: No matching distribution found for tflite-runtime
```

**Giải pháp (script `install_rpi.sh` tự động xử lý):**
1. **Cách 1 (Khuyến nghị):** Cài từ system package
   ```bash
   sudo apt install python3-tflite-runtime
   ```
2. **Cách 2:** Dùng `tensorflow` (nặng hơn)
   ```bash
   pip install tensorflow
   ```
3. Code tự động fallback: `tflite_runtime` → `tensorflow.lite`

---

## TL;DR - Cài Đặt Nhanh

```bash
# 1. Clone hoặc copy project vào Raspberry Pi
cd ~/Downloads
unzip final_project_iot-main.zip
cd final_project_iot-main

# 2. Tạo virtual environment (khuyến nghị)
python3 -m venv venv
source venv/bin/activate

# 3. Chạy script cài đặt (tự động cài tất cả)
chmod +x install_rpi.sh
./install_rpi.sh

# 4. Copy model file eye_model_best.tflite vào thư mục models/
# (Nếu chưa có, bạn cần train hoặc lấy từ nơi khác)

# 5. Chạy hệ thống
python3 raspberry_integrated_system_opencv.py
```

## Lỗi MediaPipe - Giải Pháp

**Vấn đề:** MediaPipe không hỗ trợ ARM64 (Raspberry Pi 4).

**Giải pháp:** Sử dụng phiên bản OpenCV thay thế:
- File gốc (MediaPipe): `raspberry_integrated_system.py` ❌
- File thay thế (OpenCV): `raspberry_integrated_system_opencv.py` ✅

## So Sánh 2 Phiên Bản

| Tính năng | MediaPipe Version | OpenCV Version |
|-----------|-------------------|----------------|
| Face Detection | MediaPipe FaceLandmarker | OpenCV DNN |
| Eye Detection | 468 facial landmarks | Haar Cascade |
| Cài đặt | ❌ Không cài được | ✅ Dễ dàng |
| Performance | ⚠️ Nặng | ✅ Nhẹ, nhanh |
| Độ chính xác | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Khuyến nghị** | Không khả thi | **✅ Dùng cái này** |

## Model Files Cần Thiết

Sau khi chạy `install_rpi.sh`, kiểm tra thư mục `models/`:

```bash
ls -lh models/
```

Phải có:
- ✅ `opencv_face_detector.pbtxt` (tự động tải)
- ✅ `opencv_face_detector_uint8.pb` (tự động tải)
- ✅ `haarcascade_eye.xml` (tự động tải)
- ⚠️ `eye_model_best.tflite` (bạn cần cung cấp)

## Kiểm Tra Camera

```bash
# Test camera
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('✓ OK' if cap.isOpened() else '❌ FAIL'); cap.release()"

# Hoặc
v4l2-ctl --list-devices
```

## Troubleshooting

### Lỗi: `ImportError: cannot import name 'tflite_runtime'`

```bash
pip3 install tflite-runtime
```

### Lỗi: `cv2.error: opencv_face_detector.pbtxt not found`

```bash
# Chạy lại script cài đặt
./install_rpi.sh
```

### Camera không hoạt động

```bash
# Kiểm tra quyền
sudo usermod -a -G video $USER

# Reboot
sudo reboot
```

### Performance thấp

Giảm resolution camera trong code:

```python
# Trong file raspberry_integrated_system_opencv.py
# Dòng ~609, thay đổi:
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)   # Giảm từ 640
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # Giảm từ 480
cap.set(cv2.CAP_PROP_FPS, 15)            # Giảm từ 30
```

## Phần Cứng

### GPIO Pinout

```
Cảm biến siêu âm HC-SR04:
  - Trước: TRIG=17, ECHO=27
  - Sau:   TRIG=22, ECHO=23
  - Trái:  TRIG=5,  ECHO=6
  - Phải:  TRIG=24, ECHO=25

Buzzer:
  - Pin: GPIO 12
  - Ground: GND

Camera:
  - USB port (auto-detect /dev/video0)
```

### Sơ Đồ Kết Nối

```
Raspberry Pi 4
├── USB Camera DV20 (Port USB)
├── HC-SR04 x 4 (GPIO)
│   ├── Trước: GPIO 17(TRIG), 27(ECHO)
│   ├── Sau:   GPIO 22(TRIG), 23(ECHO)
│   ├── Trái:  GPIO 5(TRIG),  6(ECHO)
│   └── Phải:  GPIO 24(TRIG), 25(ECHO)
└── Buzzer: GPIO 12
```

## Tài Liệu Chi Tiết

Xem thêm: [`RASPBERRY_PI_SETUP.md`](./RASPBERRY_PI_SETUP.md)

## Liên Hệ

Nếu gặp vấn đề, cung cấp:
1. `python3 --version`
2. `uname -a`
3. Full error log
