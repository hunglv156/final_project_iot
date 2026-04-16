"""Utility helpers for USB camera operations."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import cv2
import numpy as np


def init_camera(camera_index: int = 0, width: int = 640, height: int = 480) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 20)
    return cap


def check_camera_available(camera_index: int = 0) -> bool:
    cap = cv2.VideoCapture(camera_index)
    ok = cap.isOpened()
    cap.release()
    return ok


def capture_frame(camera: cv2.VideoCapture) -> Tuple[bool, Optional[np.ndarray]]:
    ok, frame = camera.read()
    if not ok:
        return False, None
    return True, frame


def draw_info_on_frame(frame: np.ndarray, status_dict: Dict[str, object]) -> np.ndarray:
    status = str(status_dict.get("status", "UNKNOWN"))
    confidence = float(status_dict.get("confidence", 0.0))
    frame_count = int(status_dict.get("frame_count", 0))
    color = (0, 0, 255) if status == "DROWSY" else (0, 255, 0)
    cv2.putText(
        frame,
        f"Status: {status}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"Conf: {confidence:.2f} | Cnt: {frame_count}",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def release_camera(camera: cv2.VideoCapture) -> None:
    if camera is not None:
        camera.release()
