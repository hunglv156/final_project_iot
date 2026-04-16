# Car Warning System

Raspberry Pi 4 system that combines:
- Collision warning from 4x HC-SR04 sensors
- Driver drowsiness detection from USB webcam + CNN model
- Shared buzzer alert with priority handling

## Project Structure

```text
car_warning_system/
├── 1_train_model/
│   ├── train_drowsiness_model.py
│   ├── requirements_training.txt
│   └── dataset/
│       ├── Drowsy/
│       └── Non Drowsy/
└── 2_raspberry_pi/
    ├── drowsiness_detector.py
    ├── collision_monitor.py
    ├── integrated_system.py
    ├── requirements_pi.txt
    ├── models/
    │   └── drowsiness_model.h5 or drowsiness_model.tflite
    └── utils/
        ├── camera_helper.py
        └── gpio_helper.py
```

## 1) Training (PC/Laptop)

```bash
cd car_warning_system/1_train_model
pip install -r requirements_training.txt
python train_drowsiness_model.py --dataset_dir dataset --epochs 25
```

Outputs are saved in `outputs/`:
- `outputs/models/drowsiness_model.h5`
- `outputs/models/drowsiness_model.tflite`
- `outputs/training_history.png`
- `outputs/classification_report.txt`
- `outputs/final_metrics.json`

## 2) Deploy model to Raspberry Pi

```bash
scp outputs/models/drowsiness_model.h5 pi@raspberrypi.local:~/car_warning_system/2_raspberry_pi/models/
```

## 3) Setup Raspberry Pi

```bash
cd ~/car_warning_system/2_raspberry_pi
pip3 install -r requirements_pi.txt
python3 -c "import cv2; cap=cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera FAILED'); cap.release()"
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('GPIO OK')"
```

## 4) Run modules separately

Collision monitor:
```bash
python3 collision_monitor.py
```

Drowsiness detector:
```bash
python3 drowsiness_detector.py --model_path models/drowsiness_model.h5 --show
```

## 5) Run integrated system

```bash
python3 integrated_system.py --model_path models/drowsiness_model.h5
```

Priority in integrated mode:
1. `collision_danger`
2. `drowsiness`
3. `collision_warning`

## GPIO Defaults

- `BUZZER_PIN=12`
- Sensors (BCM):
  - Front: trig=23, echo=24, warn=50cm
  - Rear: trig=17, echo=27, warn=30cm
  - Left: trig=5, echo=6, warn=40cm
  - Right: trig=20, echo=21, warn=40cm

Adjust these in `collision_monitor.py` if wiring differs.

## Notes

- `drowsiness_detector.py` supports both `.h5` and `.tflite`.
- Temporal smoothing is enabled (`drowsy_threshold`, default `4` frames).
- No-face timeout resets drowsiness state after 30 seconds.
- Always stop with `Ctrl+C` to release camera and cleanup GPIO.
