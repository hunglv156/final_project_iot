#!/bin/bash
# ============================================================
# SCRIPT CÀI ĐẶT CHO RASPBERRY PI 4 (Không cần MediaPipe)
# ============================================================
# Chạy script này trên Raspberry Pi 4 với:
#   chmod +x install_rpi.sh
#   ./install_rpi.sh
#
# Script này cài đặt OpenCV thay thế cho MediaPipe
# ============================================================

set -e  # Dừng nếu có lỗi

echo "============================================================"
echo "CÀI ĐẶT DEPENDENCIES CHO RASPBERRY PI 4"
echo "Phiên bản: OpenCV (thay thế MediaPipe)"
echo "============================================================"

# Kiểm tra Python version
PYTHON_VERSION=$(python3 --version)
echo "Python version: $PYTHON_VERSION"
echo ""

# Cập nhật system packages
echo "[1/6] Cập nhật system packages..."
sudo apt-get update

echo ""
echo "[2/6] Cài đặt system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    libopenblas-dev \
    libhdf5-dev \
    libharfbuzz0b \
    libwebp-dev \
    libopenexr-dev \
    libgstreamer1.0-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libcanberra-gtk3-0 \
    libcanberra-gtk3-module \
    libqt5gui5t64 \
    libqt5test5t64 \
    libtiff-dev \
    libjpeg-dev \
    libpng-dev

# Upgrade pip
echo ""
echo "[3/6] Upgrade pip..."
python3 -m pip install --upgrade pip setuptools wheel

# Cài đặt numpy trước (dependency của nhiều package khác)
echo ""
echo "[4/6] Cài đặt numpy..."
pip3 install "numpy>=1.23.0,<2.0.0"

# Cài đặt TensorFlow
echo ""
echo "[5/6] Cài đặt TensorFlow..."
echo "Đang cài TensorFlow cho Keras model inference..."

# Cài tensorflow
pip3 install --no-cache-dir tensorflow 2>/dev/null || {
    echo "⚠ Không cài được tensorflow, thử tensorflow-cpu..."
    pip3 install --no-cache-dir tensorflow-cpu 2>/dev/null || {
        echo "❌ CẢNH BÁO: Không cài được TensorFlow!"
        echo "Vui lòng cài thủ công: pip3 install tensorflow"
        exit 1
    }
}

# Cài đặt các packages còn lại
echo ""
echo "[6/6] Cài đặt OpenCV và các packages còn lại..."

# Thử cài opencv-contrib-python trước (có DNN module)
pip3 install --no-cache-dir opencv-contrib-python || {
    echo "Không thể cài opencv-contrib-python, thử opencv-python..."
    pip3 install --no-cache-dir opencv-python
}

pip3 install --no-cache-dir RPi.GPIO Pillow

# Tải các model files cần thiết
echo ""
echo "Tải model files cho OpenCV Face Detection..."
mkdir -p models

# Download OpenCV DNN face detection model (nếu chưa có)
if [ ! -f "models/opencv_face_detector.pbtxt" ]; then
    wget -O models/opencv_face_detector.pbtxt \
        https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/opencv_face_detector.pbtxt
fi

if [ ! -f "models/opencv_face_detector_uint8.pb" ]; then
    wget -O models/opencv_face_detector_uint8.pb \
        https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/opencv_face_detector_uint8.pb
fi

# Download eye detection model (Haar Cascade)
if [ ! -f "models/haarcascade_eye.xml" ]; then
    wget -O models/haarcascade_eye.xml \
        https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml
fi

echo ""
echo "============================================================"
echo "✓ CÀI ĐẶT THÀNH CÔNG!"
echo "============================================================"
echo ""
echo "Các packages đã cài:"
echo "  ✓ TensorFlow (Keras model inference)"
echo "  ✓ OpenCV (thay cho MediaPipe)"
echo "  ✓ RPi.GPIO"
echo "  ✓ NumPy"
echo "  ✓ Pillow"
echo ""
echo "Model files đã tải:"
echo "  ✓ models/opencv_face_detector.pbtxt"
echo "  ✓ models/opencv_face_detector_uint8.pb"
echo "  ✓ models/haarcascade_eye.xml"
echo ""
echo "Kiểm tra cài đặt:"
echo "  python3 test_installation.py"
echo ""
echo "Tiếp theo:"
echo "  1. Copy model eye_model_best.h5 (hoặc .keras) vào thư mục models/"
echo "     Hoặc convert từ .tflite nếu chỉ có file đó"
echo "  2. Chạy: python3 raspberry_integrated_system_opencv.py"
echo ""
echo "============================================================"
