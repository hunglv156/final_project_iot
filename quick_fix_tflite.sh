#!/bin/bash
# ============================================================
# QUICK FIX - TFLite Runtime Error
# ============================================================
# Chạy script này nếu gặp lỗi:
#   ERROR: No matching distribution found for tflite-runtime
#
# Usage:
#   chmod +x quick_fix_tflite.sh
#   ./quick_fix_tflite.sh
# ============================================================

set -e

echo "============================================================"
echo "FIX TFLITE RUNTIME ERROR"
echo "============================================================"
echo ""

# Kiểm tra nếu đang trong virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    echo "⚠️  Bạn đang trong virtual environment: $VIRTUAL_ENV"
    echo ""
    echo "Lựa chọn:"
    echo "  1. Thoát venv và cài python3-tflite-runtime từ apt (khuyến nghị)"
    echo "  2. Cài tensorflow trong venv này (nặng hơn)"
    echo ""
    read -p "Chọn (1 hoặc 2): " choice
    
    if [ "$choice" = "1" ]; then
        echo ""
        echo "Vui lòng chạy các lệnh sau:"
        echo ""
        echo "  deactivate"
        echo "  sudo apt update"
        echo "  sudo apt install python3-tflite-runtime"
        echo "  source venv/bin/activate"
        echo "  pip install opencv-contrib-python numpy RPi.GPIO Pillow"
        echo ""
        exit 0
    fi
fi

# Option 1: Thử cài python3-tflite-runtime từ apt
echo "[1/2] Thử cài python3-tflite-runtime từ apt..."
if sudo apt-get update && sudo apt-get install -y python3-tflite-runtime 2>/dev/null; then
    echo "✓ Đã cài python3-tflite-runtime thành công!"
    
    # Test
    if python3 -c "import tflite_runtime.interpreter" 2>/dev/null; then
        echo "✓ Import tflite_runtime thành công!"
    else
        echo "⚠️ Cài đặt OK nhưng import lỗi (có thể do đang trong venv)"
        echo "   Thử: deactivate && python3 -c 'import tflite_runtime.interpreter'"
    fi
else
    echo "⚠️ Không tìm thấy python3-tflite-runtime trong apt"
    echo ""
    
    # Option 2: Cài tensorflow
    echo "[2/2] Cài tensorflow-cpu (fallback)..."
    
    if [ -n "$VIRTUAL_ENV" ]; then
        # Trong venv, dùng pip
        pip install tensorflow-cpu || pip install tensorflow
    else
        # Ngoài venv, dùng pip3
        pip3 install tensorflow-cpu || pip3 install tensorflow
    fi
    
    echo "✓ Đã cài tensorflow"
fi

echo ""
echo "============================================================"
echo "KIỂM TRA CÀI ĐẶT"
echo "============================================================"

# Test tflite_runtime
if python3 -c "import tflite_runtime.interpreter as tflite; print('✓ tflite_runtime OK')" 2>/dev/null; then
    echo "✓ tflite_runtime: OK"
elif python3 -c "import tensorflow.lite as tflite; print('✓ tensorflow.lite OK')" 2>/dev/null; then
    echo "✓ tensorflow.lite: OK (fallback)"
else
    echo "❌ Cả tflite_runtime và tensorflow.lite đều không có"
    echo "   Vui lòng cài thủ công:"
    echo "   sudo apt install python3-tflite-runtime"
    echo "   HOẶC"
    echo "   pip install tensorflow"
fi

echo ""
echo "Chạy test đầy đủ:"
echo "  python3 test_installation.py"
echo ""
echo "============================================================"
