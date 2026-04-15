#!/usr/bin/env python3
"""
Script kiểm tra cài đặt trên Raspberry Pi.
Chạy: python3 test_installation.py
"""

import sys
from pathlib import Path

def test_import(module_name, package_name=None):
    """Test import một module."""
    try:
        __import__(module_name)
        print(f"✅ {package_name or module_name}")
        return True
    except ImportError as e:
        print(f"❌ {package_name or module_name}: {e}")
        return False

def test_file(filepath):
    """Test xem file có tồn tại không."""
    if Path(filepath).exists():
        size = Path(filepath).stat().st_size
        print(f"✅ {filepath} ({size / 1024:.1f} KB)")
        return True
    else:
        print(f"❌ {filepath} (không tồn tại)")
        return False

def main():
    print("=" * 60)
    print("KIỂM TRA CÀI ĐẶT - RASPBERRY PI")
    print("=" * 60)
    
    # Python version
    print(f"\nPython version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    
    # Test Python packages
    print("\n[1/3] Kiểm tra Python packages:")
    print("-" * 60)
    
    packages_ok = True
    packages_ok &= test_import("cv2", "opencv-python")
    packages_ok &= test_import("numpy", "numpy")
    packages_ok &= test_import("RPi.GPIO", "RPi.GPIO")
    
    # Test TFLite
    tflite_ok = False
    if test_import("tflite_runtime.interpreter", "tflite-runtime"):
        tflite_ok = True
    elif test_import("tensorflow.lite", "tensorflow (fallback)"):
        print("  ⚠️  Đang dùng TensorFlow thay vì tflite-runtime (nặng hơn)")
        tflite_ok = True
    else:
        packages_ok = False
    
    # Test OpenCV modules
    print("\n[2/3] Kiểm tra OpenCV modules:")
    print("-" * 60)
    
    try:
        import cv2
        print(f"✅ OpenCV version: {cv2.__version__}")
        
        # Test DNN module
        try:
            net = cv2.dnn.readNetFromTensorflow
            print("✅ OpenCV DNN module")
        except AttributeError:
            print("❌ OpenCV DNN module không có (cần opencv-contrib-python)")
            packages_ok = False
        
        # Test Cascade Classifier
        try:
            cascade = cv2.CascadeClassifier
            print("✅ OpenCV CascadeClassifier")
        except AttributeError:
            print("❌ OpenCV CascadeClassifier không có")
            packages_ok = False
        
    except ImportError:
        print("❌ Không thể import OpenCV")
        packages_ok = False
    
    # Test model files
    print("\n[3/3] Kiểm tra model files:")
    print("-" * 60)
    
    models_ok = True
    models_ok &= test_file("models/opencv_face_detector.pbtxt")
    models_ok &= test_file("models/opencv_face_detector_uint8.pb")
    models_ok &= test_file("models/haarcascade_eye.xml")
    models_ok &= test_file("models/eye_model_best.tflite")
    
    # Test camera (optional)
    print("\n[BONUS] Kiểm tra camera:")
    print("-" * 60)
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                print(f"✅ Camera hoạt động ({w}x{h})")
            else:
                print("⚠️  Camera mở được nhưng không đọc được frame")
            cap.release()
        else:
            print("⚠️  Không thể mở camera (kiểm tra kết nối)")
    except Exception as e:
        print(f"⚠️  Lỗi khi test camera: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("KẾT QUẢ:")
    print("=" * 60)
    
    if packages_ok and models_ok:
        print("✅ CÀI ĐẶT HOÀN TẤT! Bạn có thể chạy:")
        print("   python3 raspberry_integrated_system_opencv.py")
    else:
        print("❌ CÒN THIẾU MỘT SỐ COMPONENTS:")
        
        if not packages_ok:
            print("\n   Packages chưa đủ. Chạy:")
            print("   ./install_rpi.sh")
        
        if not models_ok:
            print("\n   Model files chưa đủ:")
            
            if not Path("models/opencv_face_detector.pbtxt").exists():
                print("   - Chạy ./install_rpi.sh để tải OpenCV models")
            
            if not Path("models/eye_model_best.tflite").exists():
                print("   - Copy eye_model_best.tflite vào thư mục models/")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
