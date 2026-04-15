# Fix Lỗi TFLite Runtime

## Vấn Đề

```bash
pip install tflite-runtime
ERROR: No matching distribution found for tflite-runtime
```

## Nguyên Nhân

Package `tflite-runtime` đã **DEPRECATED** từ TensorFlow 2.16+. Google không còn phát hành package này nữa.

## Giải Pháp Nhanh

### Cách 1: Chạy Script Tự Động (Khuyến Nghị)

```bash
# Script sẽ tự động cài TFLite từ apt hoặc tensorflow
chmod +x install_rpi.sh
./install_rpi.sh
```

### Cách 2: Cài Thủ Công

#### Option A: Từ System Package (Nhẹ nhất)

```bash
# Cài python3-tflite-runtime từ Raspberry Pi OS
sudo apt update
sudo apt install python3-tflite-runtime
```

**Lưu ý:** Phải **THOÁT** khỏi virtual environment trước:
```bash
deactivate  # Nếu đang trong venv
sudo apt install python3-tflite-runtime
```

#### Option B: Từ TensorFlow (Nặng hơn ~200MB)

```bash
# Trong virtual environment
pip install tensorflow
```

Hoặc phiên bản CPU-only (nhẹ hơn):
```bash
pip install tensorflow-cpu
```

## Kiểm Tra

```bash
# Test import
python3 -c "import tflite_runtime.interpreter as tflite; print('✓ tflite_runtime OK')"

# Hoặc
python3 -c "import tensorflow.lite as tflite; print('✓ tensorflow.lite OK')"

# Hoặc chạy test script
python3 test_installation.py
```

## Code Tự Động Fallback

Code đã được cập nhật để tự động fallback:

```python
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite
```

Bạn **KHÔNG CẦN** sửa code, nó sẽ tự động dùng package nào có sẵn.

## Hướng Dẫn Chi Tiết Từng Bước

### Trường Hợp 1: Đang Dùng Virtual Environment

```bash
# 1. Thoát venv
deactivate

# 2. Cài từ system
sudo apt update
sudo apt install python3-tflite-runtime

# 3. Vào lại venv
source venv/bin/activate

# 4. Cài các packages còn lại (không có tflite-runtime)
pip install opencv-contrib-python numpy RPi.GPIO Pillow

# 5. Test
python3 test_installation.py
```

### Trường Hợp 2: Không Dùng Virtual Environment

```bash
# 1. Cài từ system
sudo apt update
sudo apt install python3-tflite-runtime

# 2. Cài các packages còn lại
pip3 install opencv-contrib-python numpy RPi.GPIO Pillow

# 3. Test
python3 test_installation.py
```

### Trường Hợp 3: Dùng TensorFlow (Nếu Không Có python3-tflite-runtime)

```bash
# Trong venv hoặc không
pip install tensorflow

# Hoặc tensorflow-cpu (nhẹ hơn)
pip install tensorflow-cpu

# Cài các packages còn lại
pip install opencv-contrib-python numpy RPi.GPIO Pillow

# Test
python3 test_installation.py
```

## Troubleshooting

### Lỗi: `python3-tflite-runtime not found`

Raspberry Pi OS cũ có thể không có package này trong repository.

**Giải pháp:** Dùng TensorFlow
```bash
pip install tensorflow-cpu
```

### Lỗi: `tensorflow too large`

TensorFlow full ~200MB, nặng cho Raspberry Pi.

**Giải pháp:**
1. Dùng tensorflow-cpu (nhẹ hơn)
2. Hoặc tăng swap memory:
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile
   # Đổi CONF_SWAPSIZE=2048
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

### Lỗi: `ImportError: No module named 'tflite_runtime'`

Code đang tìm `tflite_runtime` nhưng không có.

**Giải pháp:** Code đã có fallback, nhưng nếu vẫn lỗi:
```python
# Sửa import trong code (nếu cần)
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite
```

## So Sánh Options

| Option | Size | Performance | Cài Đặt |
|--------|------|-------------|---------|
| python3-tflite-runtime (apt) | ~10MB | ⚡ Nhanh | ✅ Dễ |
| tensorflow-cpu (pip) | ~100MB | ⚡ Nhanh | ✅ Dễ |
| tensorflow (pip) | ~200MB | ⚠️ Nặng | ⚠️ Lâu |

**Khuyến nghị:** Dùng `python3-tflite-runtime` từ apt nếu có.

## Summary

1. **Vấn đề:** `tflite-runtime` package không còn được phát hành
2. **Giải pháp:** Dùng system package hoặc tensorflow
3. **Thực hiện:** Chạy `./install_rpi.sh` (tự động xử lý)
4. **Code:** Đã có fallback tự động, không cần sửa

---

**Chạy ngay:**
```bash
chmod +x install_rpi.sh
./install_rpi.sh
python3 test_installation.py
python3 raspberry_integrated_system_opencv.py
```
