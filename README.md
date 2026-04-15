# Driver Drowsiness Detection - IOT Final Project

Hệ thống phát hiện tài xế ngủ gật sử dụng MobileNetV2 + MediaPipe + Raspberry Pi 4.

## Cấu trúc dự án

```
final_project/
├── train_eye_model.py      # Train model phân loại mắt (MRL Eye Dataset)
├── train_face_model.py     # Train model phân loại buồn ngủ (DDD Dataset)
├── inference.py            # Inference server chạy trên Raspberry Pi
├── stream_client.py        # Webcam stream client chạy trên Mac
├── requirements.txt        # Dependencies cho Mac/PC (training)
├── requirements_rpi.txt    # Dependencies cho Raspberry Pi
├── models/                 # Thư mục lưu models
│   ├── eye_model.h5
│   ├── eye_model.tflite
│   ├── face_model.h5
│   └── face_model.tflite
├── mrl_eye_dataset/        # MRL Eye Dataset (tạo thủ công)
│   ├── open/
│   └── closed/
└── ddd_dataset/            # DDD Dataset (tạo thủ công)
    ├── drowsy/
    └── non_drowsy/
```

## Hướng dẫn sử dụng

### Bước 1: Chuẩn bị dataset

Tải dataset và đặt đúng cấu trúc thư mục:
- **MRL Eye Dataset**: `mrl_eye_dataset/open/` và `mrl_eye_dataset/closed/`
- **DDD Dataset**: `ddd_dataset/drowsy/` và `ddd_dataset/non_drowsy/`

### Bước 2: Cài đặt dependencies (trên Mac)

```bash
pip install -r requirements.txt
```

### Bước 3: Train model

```bash
# Train model phân loại mắt
python train_eye_model.py

# Train model phân loại buồn ngủ (tùy chọn)
python train_face_model.py
```

Output: `models/eye_model.tflite` và `models/eye_model.h5`

### Bước 4: Copy model lên Raspberry Pi

```bash
scp models/eye_model.tflite pi@<RASPBERRY_PI_IP>:~/drowsiness/models/
```

### Bước 5: Chạy inference trên Raspberry Pi

```bash
# Cài dependencies trên Raspberry Pi
pip install -r requirements_rpi.txt

# Chạy inference server
python inference.py --model models/eye_model.tflite --port 9999
```

### Bước 6: Chạy stream client trên Mac

```bash
python stream_client.py --host <RASPBERRY_PI_IP> --port 9999
```

## Thông số kỹ thuật

| Thành phần | Giá trị |
|---|---|
| Model | MobileNetV2 alpha=0.35 |
| Input size | 32×32 pixels |
| Quantization | Float16 |
| Ngưỡng cảnh báo | 20 frames (~0.67 giây ở 30fps) |
| GPIO Buzzer | Pin 17 (BCM) |
| Stream port | 9999 (TCP) |

## Sơ đồ hệ thống

```
[Mac Webcam] → [stream_client.py] --TCP Socket--> [inference.py on RPi]
                                                         ↓
                                              [MediaPipe FaceMesh]
                                                         ↓
                                              [TFLite Eye Classifier]
                                                         ↓
                                              [Drowsiness Logic]
                                                         ↓
                                              [GPIO Buzzer Alarm]
```
