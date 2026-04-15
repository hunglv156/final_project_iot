# Hướng Dẫn Cài Đặt Trên Raspberry Pi 4

## Vấn Đề

MediaPipe **không hỗ trợ** kiến trúc ARM64 (aarch64) của Raspberry Pi 4. Khi chạy:
```bash
pip install mediapipe
```

Bạn sẽ gặp lỗi:
```
ERROR: Could not find a version that satisfies the requirement mediapipe
ERROR: No matching distribution found for mediapipe
```

## Giải Pháp

Có **3 phương án** để giải quyết:

### 📌 Phương Án 1: Sử Dụng OpenCV Thay Thế (KHUYẾN NGHỊ)

**Ưu điểm:**
- ✅ Dễ cài đặt (5-10 phút)
- ✅ Performance tốt trên Raspberry Pi
- ✅ Không cần build từ source
- ✅ OpenCV DNN face detection rất chính xác

**Nhược điểm:**
- ⚠️ Không có facial landmarks chi tiết như MediaPipe (468 điểm)
- ⚠️ Chỉ có face bounding box + eye detection

**Cách thực hiện:**

```bash
# 1. Chạy script cài đặt
chmod +x install_rpi.sh
./install_rpi.sh

# 2. Sử dụng phiên bản OpenCV (đã được tạo sẵn)
python3 raspberry_integrated_system_opencv.py
```

---

### 📌 Phương Án 2: Build MediaPipe Từ Source

**Ưu điểm:**
- ✅ Có đầy đủ tính năng MediaPipe
- ✅ 468 facial landmarks chính xác

**Nhược điểm:**
- ❌ Rất phức tạp (cần Bazel, dependencies nhiều)
- ❌ Mất 1-3 giờ để build
- ❌ Có thể build lỗi
- ❌ Cần swap memory lớn (>2GB)

**Cách thực hiện:**

```bash
# Tăng swap memory
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Đổi CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Install dependencies
sudo apt-get install -y build-essential cmake git

# Clone MediaPipe
git clone https://github.com/google/mediapipe.git
cd mediapipe

# Follow hướng dẫn build:
# https://google.github.io/mediapipe/getting_started/install.html
```

**⚠️ Cảnh báo:** Build có thể mất rất lâu và dễ gặp lỗi!

---

### 📌 Phương Án 3: Sử Dụng Pre-built Wheel (Nếu Có)

Một số cộng đồng đã build sẵn MediaPipe wheel cho ARM64:

```bash
# Thử tìm wheel trên piwheels hoặc GitHub
pip3 install mediapipe --extra-index-url https://www.piwheels.org/simple

# Hoặc tải wheel từ:
# https://github.com/PINTO0309/mediapipe-bin
```

**⚠️ Lưu ý:** Không phải lúc nào cũng có wheel phù hợp với Python version của bạn.

---

## Chi Tiết Cài Đặt - Phương Án 1 (OpenCV)

### Bước 1: Cài Đặt Dependencies

```bash
# Chạy script tự động
chmod +x install_rpi.sh
./install_rpi.sh
```

Script sẽ:
1. Cài đặt system dependencies (libopencv, codecs, etc.)
2. Cài đặt Python packages (opencv-contrib-python, tflite-runtime, numpy)
3. Tải OpenCV face detection models
4. Tải Haar Cascade eye detection model

### Bước 2: Kiểm Tra Cài Đặt

```bash
python3 -c "import cv2; import tflite_runtime.interpreter; print('✓ OK')"
```

Nếu không có lỗi, bạn đã cài đặt thành công!

### Bước 3: Copy Model File

Đảm bảo file `eye_model_best.tflite` (model phát hiện mắt của bạn) có trong thư mục `models/`:

```bash
ls -lh models/
# Phải có:
# - eye_model_best.tflite
# - opencv_face_detector.pbtxt
# - opencv_face_detector_uint8.pb
# - haarcascade_eye.xml
```

### Bước 4: Chạy Hệ Thống

```bash
# Phiên bản OpenCV (không cần MediaPipe)
python3 raspberry_integrated_system_opencv.py
```

---

## So Sánh MediaPipe vs OpenCV

| Tính năng | MediaPipe | OpenCV DNN |
|-----------|-----------|------------|
| Face Detection | ✅ Rất chính xác | ✅ Chính xác |
| Facial Landmarks | ✅ 468 điểm | ❌ Không có |
| Eye Detection | ✅ Từ landmarks | ✅ Haar Cascade |
| Performance trên RPi4 | ⚠️ Nặng (nếu build được) | ✅ Nhẹ, nhanh |
| Dễ cài đặt | ❌ Rất khó | ✅ Dễ |
| Phù hợp cho project này | ⚠️ Overkill | ✅ Đủ dùng |

---

## Troubleshooting

### Lỗi: `ImportError: libopencv_*.so: cannot open shared object file`

```bash
sudo apt-get install -y libopencv-dev python3-opencv
```

### Lỗi: `numpy version conflict`

```bash
pip3 uninstall numpy
pip3 install "numpy>=1.23.0,<2.0.0"
```

### Camera không hoạt động

```bash
# Kiểm tra camera
ls /dev/video*

# Test camera
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL')"
```

### Performance thấp

```bash
# Giảm resolution camera trong code
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Hoặc giảm FPS
cap.set(cv2.CAP_PROP_FPS, 15)
```

---

## Tóm Tắt

**✅ KHUYẾN NGHỊ: Dùng Phương Án 1 (OpenCV)**

Lý do:
1. Cài đặt nhanh (5-10 phút)
2. Performance tốt trên Raspberry Pi 4
3. Đủ chính xác cho drowsiness detection
4. Không cần build phức tạp

Chỉ cần chạy:
```bash
./install_rpi.sh
python3 raspberry_integrated_system_opencv.py
```

---

## Liên Hệ & Hỗ Trợ

Nếu gặp vấn đề, vui lòng cung cấp:
1. Output của `python3 --version`
2. Output của `uname -a`
3. Full error log
