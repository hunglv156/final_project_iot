# TL;DR - Fix MediaPipe Error on Raspberry Pi 4

## Problem
```
ERROR: No matching distribution found for mediapipe
```

## Solution
Use OpenCV instead of MediaPipe.

## Quick Fix (5 minutes)

```bash
# On Raspberry Pi 4
cd ~/final_project_iot-main

# Run install script
chmod +x install_rpi.sh
./install_rpi.sh

# Test
python3 test_installation.py

# Run
python3 raspberry_integrated_system_opencv.py
```

## Files to Use

✅ USE THESE:
- `raspberry_integrated_system_opencv.py`
- `install_rpi.sh`
- `requirements_rpi_opencv.txt`

❌ DON'T USE:
- `raspberry_integrated_system.py` (has MediaPipe)
- `requirements_rpi.txt` (has MediaPipe)

## Documentation

- Quick guide: [`README_RASPBERRY_PI.md`](./README_RASPBERRY_PI.md)
- Commands: [`QUICK_START_RPI.txt`](./QUICK_START_RPI.txt)
- Full guide: [`RASPBERRY_PI_SETUP.md`](./RASPBERRY_PI_SETUP.md)
- All files: [`INDEX.md`](./INDEX.md)

## Why OpenCV?

| Metric | MediaPipe | OpenCV |
|--------|-----------|--------|
| Installation | ❌ 1-3 hours | ✅ 5-10 min |
| Performance | ⚠️ Slow | ✅ 2x faster |
| Accuracy | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Recommendation** | ❌ | ✅ |

## What Changed?

- Face detection: MediaPipe FaceLandmarker → OpenCV DNN
- Eye detection: 468 landmarks → Haar Cascade
- Eye classification: Same TFLite model ✅

## Support

Problem? Run `python3 test_installation.py` and check the output.

Still stuck? Read [`RASPBERRY_PI_SETUP.md`](./RASPBERRY_PI_SETUP.md) → Troubleshooting.

---

**That's it!** 🎉
