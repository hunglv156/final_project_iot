#!/bin/bash
# ============================================================
# Script kiểm tra files cần thiết trước khi deploy
# ============================================================

echo "======================================================================"
echo "KIỂM TRA FILES CẦN THIẾT CHO RASPBERRY PI DEPLOYMENT"
echo "======================================================================"
echo ""

ERROR=0

# Kiểm tra file code chính
if [ -f "raspberry_integrated_system.py" ]; then
    SIZE=$(ls -lh raspberry_integrated_system.py | awk '{print $5}')
    echo "✓ raspberry_integrated_system.py ($SIZE)"
else
    echo "✗ THIẾU: raspberry_integrated_system.py"
    ERROR=1
fi

# Kiểm tra requirements
if [ -f "requirements_rpi.txt" ]; then
    SIZE=$(ls -lh requirements_rpi.txt | awk '{print $5}')
    echo "✓ requirements_rpi.txt ($SIZE)"
else
    echo "✗ THIẾU: requirements_rpi.txt"
    ERROR=1
fi

# Kiểm tra model TFLite
if [ -f "models/eye_model_best.tflite" ]; then
    SIZE=$(ls -lh models/eye_model_best.tflite | awk '{print $5}')
    echo "✓ models/eye_model_best.tflite ($SIZE)"
else
    echo "✗ THIẾU: models/eye_model_best.tflite"
    ERROR=1
fi

# Kiểm tra MediaPipe model
if [ -f "models/face_landmarker.task" ]; then
    SIZE=$(ls -lh models/face_landmarker.task | awk '{print $5}')
    echo "✓ models/face_landmarker.task ($SIZE)"
else
    echo "✗ THIẾU: models/face_landmarker.task"
    ERROR=1
fi

echo ""
echo "----------------------------------------------------------------------"

if [ $ERROR -eq 0 ]; then
    echo "✅ TẤT CẢ FILES CẦN THIẾT ĐÃ SẴN SÀNG!"
    echo ""
    echo "Tổng dung lượng cần copy:"
    du -sh raspberry_integrated_system.py requirements_rpi.txt models/eye_model_best.tflite models/face_landmarker.task 2>/dev/null | tail -n 1 | awk '{print $1}'
    echo ""
    echo "Bước tiếp theo:"
    echo "  1. Copy 4 files trên sang Raspberry Pi"
    echo "  2. Xem hướng dẫn chi tiết trong: DEPLOY_RASPBERRY_PI.md"
    echo ""
    echo "Copy qua SCP (thay PI_IP bằng IP của Raspberry Pi):"
    echo "  scp raspberry_integrated_system.py pi@PI_IP:~/final_project/"
    echo "  scp requirements_rpi.txt pi@PI_IP:~/final_project/"
    echo "  scp models/eye_model_best.tflite pi@PI_IP:~/final_project/models/"
    echo "  scp models/face_landmarker.task pi@PI_IP:~/final_project/models/"
else
    echo "❌ THIẾU MỘT SỐ FILES CẦN THIẾT!"
    echo ""
    echo "Vui lòng kiểm tra lại project!"
fi

echo "======================================================================"
