# Setup Checklist - Raspberry Pi 4

## Pre-Setup

- [ ] Raspberry Pi 4 đã cài Raspberry Pi OS
- [ ] Đã kết nối internet
- [ ] Python 3.9+ đã cài đặt (`python3 --version`)
- [ ] Có quyền sudo
- [ ] USB Camera DV20 đã kết nối
- [ ] 4x HC-SR04 sensors đã kết nối đúng GPIO pins
- [ ] Buzzer đã kết nối GPIO 12

---

## Installation Steps

### 1. Copy Project Files

- [ ] Copy project lên Raspberry Pi:
  ```bash
  scp -r final_project_iot-main/ pi@raspberrypi:~/
  ```
  
- [ ] SSH vào Raspberry Pi:
  ```bash
  ssh pi@raspberrypi
  ```

- [ ] Di chuyển vào thư mục project:
  ```bash
  cd ~/final_project_iot-main
  ```

### 2. Create Virtual Environment (Optional but Recommended)

- [ ] Tạo virtual environment:
  ```bash
  python3 -m venv venv
  ```

- [ ] Activate virtual environment:
  ```bash
  source venv/bin/activate
  ```

### 3. Run Installation Script

- [ ] Make script executable:
  ```bash
  chmod +x install_rpi.sh
  ```

- [ ] Run installation:
  ```bash
  ./install_rpi.sh
  ```

- [ ] Wait for completion (5-10 minutes)

- [ ] Check for errors in output

### 4. Verify Installation

- [ ] Run test script:
  ```bash
  python3 test_installation.py
  ```

- [ ] Expected output: `✅ CÀI ĐẶT HOÀN TẤT!`

- [ ] If errors, check Troubleshooting section in `RASPBERRY_PI_SETUP.md`

### 5. Verify Model Files

- [ ] Check models directory:
  ```bash
  ls -lh models/
  ```

- [ ] Verify files exist:
  - [ ] `opencv_face_detector.pbtxt` (~10 KB)
  - [ ] `opencv_face_detector_uint8.pb` (~2.7 MB)
  - [ ] `haarcascade_eye.xml` (~100 KB)
  - [ ] `eye_model_best.tflite` (~620 KB)

- [ ] If `eye_model_best.tflite` missing, copy from training machine:
  ```bash
  scp models/eye_model_best.tflite pi@raspberrypi:~/final_project_iot-main/models/
  ```

### 6. Test Camera

- [ ] Check camera device:
  ```bash
  ls /dev/video*
  ```

- [ ] Expected: `/dev/video0` (or similar)

- [ ] Test camera with Python:
  ```bash
  python3 -c "import cv2; cap = cv2.VideoCapture(0); print('✓ OK' if cap.isOpened() else '❌ FAIL'); cap.release()"
  ```

- [ ] Expected output: `✓ OK`

- [ ] If FAIL, check camera connection or permissions:
  ```bash
  sudo usermod -a -G video $USER
  sudo reboot
  ```

### 7. Test GPIO Sensors (Optional)

- [ ] Test GPIO access:
  ```bash
  python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('✓ OK')"
  ```

- [ ] Expected output: `✓ OK`

---

## Running the System

### 8. Initial Test Run

- [ ] Run system:
  ```bash
  python3 raspberry_integrated_system_opencv.py
  ```

- [ ] Check console output for errors

- [ ] Verify components initialize:
  - [ ] `[Buzzer] Khởi tạo tại GPIO 12`
  - [ ] `[Trước] Cảm biến siêu âm khởi tạo...`
  - [ ] `[OpenCV] ✓ Face detector (DNN) tải thành công`
  - [ ] `[OpenCV] ✓ Eye detector (Haar Cascade) tải thành công`
  - [ ] `[DrowsinessDetection] ✓ Camera khởi tạo thành công`
  - [ ] `[System] ✓ Hệ thống đang chạy`

- [ ] Test drowsiness detection (close eyes for 1+ second)

- [ ] Test collision warning (put hand near sensors)

- [ ] Test buzzer sounds (should beep on alerts)

- [ ] Stop system with `Ctrl+C`

- [ ] Verify clean shutdown:
  - [ ] `[System] Đang dừng hệ thống...`
  - [ ] `[System] ✓ Đã dừng hoàn toàn`

---

## Troubleshooting Checklist

### If Installation Fails

- [ ] Check internet connection
- [ ] Check disk space: `df -h`
- [ ] Check Python version: `python3 --version` (need 3.9+)
- [ ] Re-run installation: `./install_rpi.sh`
- [ ] Check logs in terminal output

### If Camera Fails

- [ ] Check camera connection (unplug/replug USB)
- [ ] Check permissions: `ls -l /dev/video0`
- [ ] Add user to video group: `sudo usermod -a -G video $USER`
- [ ] Reboot: `sudo reboot`
- [ ] Try different USB port

### If Model Files Missing

- [ ] Re-run installation: `./install_rpi.sh`
- [ ] Manually download models:
  ```bash
  cd models
  wget https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/opencv_face_detector.pbtxt
  wget https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/opencv_face_detector_uint8.pb
  wget https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml
  ```

### If Performance is Low

- [ ] Reduce camera resolution (edit code line ~609):
  ```python
  cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)   # from 640
  cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # from 480
  cap.set(cv2.CAP_PROP_FPS, 15)            # from 30
  ```

- [ ] Close other applications
- [ ] Check CPU temperature: `vcgencmd measure_temp`
- [ ] Add heatsink/fan if temperature > 70°C

### If Import Errors

- [ ] `ImportError: No module named 'cv2'`
  ```bash
  pip3 install opencv-contrib-python
  ```

- [ ] `ImportError: No module named 'tflite_runtime'`
  ```bash
  pip3 install tflite-runtime
  ```

- [ ] `ImportError: No module named 'RPi.GPIO'`
  ```bash
  pip3 install RPi.GPIO
  ```

- [ ] `numpy version conflict`
  ```bash
  pip3 uninstall numpy
  pip3 install "numpy>=1.23.0,<2.0.0"
  ```

---

## Hardware Checklist

### GPIO Connections

- [ ] Buzzer:
  - [ ] Positive → GPIO 12
  - [ ] Negative → GND

- [ ] HC-SR04 Trước (Front):
  - [ ] VCC → 5V
  - [ ] TRIG → GPIO 17
  - [ ] ECHO → GPIO 27 (with voltage divider!)
  - [ ] GND → GND

- [ ] HC-SR04 Sau (Back):
  - [ ] VCC → 5V
  - [ ] TRIG → GPIO 22
  - [ ] ECHO → GPIO 23 (with voltage divider!)
  - [ ] GND → GND

- [ ] HC-SR04 Trái (Left):
  - [ ] VCC → 5V
  - [ ] TRIG → GPIO 5
  - [ ] ECHO → GPIO 6 (with voltage divider!)
  - [ ] GND → GND

- [ ] HC-SR04 Phải (Right):
  - [ ] VCC → 5V
  - [ ] TRIG → GPIO 24
  - [ ] ECHO → GPIO 25 (with voltage divider!)
  - [ ] GND → GND

**⚠️ IMPORTANT:** HC-SR04 ECHO pin outputs 5V, but Raspberry Pi GPIO only accepts 3.3V!  
Use voltage divider: ECHO → 1kΩ resistor → GPIO + 2kΩ resistor → GND

### Camera Connection

- [ ] USB Camera DV20 connected to USB port
- [ ] Camera LED indicator on (if available)
- [ ] Camera detected: `ls /dev/video*` shows `/dev/video0`

---

## Final Checklist

### Before Production Use

- [ ] System runs without errors for 5+ minutes
- [ ] Drowsiness detection works (tested with closed eyes)
- [ ] All 4 sensors detect obstacles correctly
- [ ] Buzzer beeps correctly for different alerts
- [ ] Camera feed is clear
- [ ] No memory leaks (check with `htop`)
- [ ] CPU usage reasonable (<80%)
- [ ] Temperature reasonable (<70°C)

### Documentation Read

- [ ] Read `README_RASPBERRY_PI.md`
- [ ] Familiar with `RASPBERRY_PI_SETUP.md` (troubleshooting)
- [ ] Understand `COMPARISON_DIAGRAM.txt` (MediaPipe vs OpenCV)

### Backup & Safety

- [ ] Backed up model files
- [ ] Backed up configuration
- [ ] Know how to stop system (`Ctrl+C`)
- [ ] Know how to access remotely (SSH)

---

## Success Criteria

✅ All checks passed:
- [ ] Installation completed without errors
- [ ] Test script shows "✅ CÀI ĐẶT HOÀN TẤT!"
- [ ] Camera works
- [ ] All sensors work
- [ ] Buzzer works
- [ ] System runs stably for 5+ minutes
- [ ] Drowsiness detection accurate
- [ ] Collision warning accurate

🎉 **Congratulations! Your system is ready!** 🎉

---

## Maintenance

### Daily

- [ ] Check system logs for errors
- [ ] Verify camera focus (clean lens if needed)
- [ ] Check sensor alignment

### Weekly

- [ ] Update system: `sudo apt update && sudo apt upgrade`
- [ ] Check disk space: `df -h`
- [ ] Check temperature: `vcgencmd measure_temp`

### Monthly

- [ ] Backup models and code
- [ ] Review and update thresholds if needed
- [ ] Test all features end-to-end

---

## Support

If you encounter issues:

1. Check this checklist
2. Read `RASPBERRY_PI_SETUP.md` → Troubleshooting section
3. Run `python3 test_installation.py` for diagnostics
4. Collect information:
   - [ ] Python version: `python3 --version`
   - [ ] System info: `uname -a`
   - [ ] Test output: `python3 test_installation.py`
   - [ ] Full error log
5. Refer to documentation or ask for help with collected info

---

## Notes

- Virtual environment recommended but optional
- Installation takes 5-10 minutes with good internet
- First run may be slower (model loading)
- Adjust thresholds in code if needed:
  - `DROWSY_THRESHOLD = 25` (frames with eyes closed)
  - `FACE_CONFIDENCE_THRESHOLD = 0.5`
  - Sensor `warn_dist` values

---

**Date:** _____________  
**Checked by:** _____________  
**Status:** ☐ Passed ☐ Failed (see notes)  
**Notes:** _____________________________________________
