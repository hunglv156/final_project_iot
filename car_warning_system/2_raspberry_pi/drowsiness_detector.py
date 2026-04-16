"""Realtime drowsiness detection module."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from utils.camera_helper import capture_frame, draw_info_on_frame, init_camera, release_camera

try:
    import tensorflow as tf
except ImportError:  # pragma: no cover
    tf = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)


class DrowsinessDetector:
    def __init__(
        self,
        model_path: str,
        camera_index: int = 0,
        drowsy_threshold: int = 4,
        confidence_threshold: float = 0.7,
        no_face_timeout_sec: float = 30.0,
    ) -> None:
        self.model_path = Path(model_path)
        self.camera = init_camera(camera_index=camera_index, width=640, height=480)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            raise RuntimeError("Could not load Haar cascade classifier.")

        self.drowsy_threshold = drowsy_threshold
        self.confidence_threshold = confidence_threshold
        self.no_face_timeout_sec = no_face_timeout_sec
        self.drowsy_frame_count = 0
        self.latched_alert = False
        self.last_face_time = time.time()
        self.last_result: Dict[str, object] = {
            "status": "AWAKE",
            "confidence": 0.0,
            "frame_count": 0,
            "trigger_alert": False,
            "face_detected": False,
        }
        self._load_model()

    def _load_model(self) -> None:
        if self.model_path.suffix == ".tflite":
            if tf is None:
                raise RuntimeError("TensorFlow is required for TFLite interpreter in this setup.")
            self.backend = "tflite"
            self.interpreter = tf.lite.Interpreter(model_path=str(self.model_path))
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
        else:
            if tf is None:
                raise RuntimeError("TensorFlow is not installed.")
            self.backend = "keras"
            self.keras_model = tf.keras.models.load_model(self.model_path)
        LOGGER.info("Loaded model: %s", self.model_path)

    def detect_face(self, frame: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60)
        )
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
        return frame[y : y + h, x : x + w]

    @staticmethod
    def preprocess_face(face_img: np.ndarray) -> np.ndarray:
        resized = cv2.resize(face_img, (224, 224))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        return np.expand_dims(rgb, axis=0)

    def predict_drowsiness(self, face_array: np.ndarray) -> Tuple[float, float]:
        if self.backend == "keras":
            probs = self.keras_model.predict(face_array, verbose=0)[0]
        else:
            input_idx = self.input_details[0]["index"]
            output_idx = self.output_details[0]["index"]
            input_dtype = self.input_details[0]["dtype"]
            batch = face_array.astype(input_dtype)
            self.interpreter.set_tensor(input_idx, batch)
            self.interpreter.invoke()
            probs = self.interpreter.get_tensor(output_idx)[0]
        prob_awake = float(probs[0])
        prob_drowsy = float(probs[1])
        return prob_awake, prob_drowsy

    def _reset_state(self) -> None:
        self.drowsy_frame_count = 0
        self.latched_alert = False

    def update_state(self, is_drowsy: bool) -> bool:
        if is_drowsy:
            self.drowsy_frame_count += 1
        else:
            self._reset_state()
            return False
        if self.drowsy_frame_count >= self.drowsy_threshold and not self.latched_alert:
            self.latched_alert = True
            return True
        return False

    def process_frame(self) -> Dict[str, object]:
        ok, frame = capture_frame(self.camera)
        if not ok or frame is None:
            raise RuntimeError("Failed to capture frame from camera.")

        face = self.detect_face(frame)
        if face is None:
            if time.time() - self.last_face_time > self.no_face_timeout_sec:
                self._reset_state()
            self.last_result = {
                "status": "NO_FACE",
                "confidence": 0.0,
                "frame_count": self.drowsy_frame_count,
                "trigger_alert": False,
                "face_detected": False,
            }
            return self.last_result

        self.last_face_time = time.time()
        face_array = self.preprocess_face(face)
        _, prob_drowsy = self.predict_drowsiness(face_array)
        is_drowsy = prob_drowsy >= self.confidence_threshold
        trigger = self.update_state(is_drowsy)
        status = "DROWSY" if is_drowsy else "AWAKE"
        self.last_result = {
            "status": status,
            "confidence": round(prob_drowsy, 4),
            "frame_count": self.drowsy_frame_count,
            "trigger_alert": trigger,
            "face_detected": True,
        }
        return self.last_result

    def release(self) -> None:
        release_camera(self.camera)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_path",
        default="models/drowsiness_model.h5",
        help="Path to .h5 or .tflite model file",
    )
    parser.add_argument("--camera_index", type=int, default=0)
    parser.add_argument("--threshold", type=int, default=4)
    parser.add_argument("--confidence", type=float, default=0.7)
    parser.add_argument("--show", action="store_true", help="Show debug camera window")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
    )
    args = parse_args()
    detector = DrowsinessDetector(
        model_path=args.model_path,
        camera_index=args.camera_index,
        drowsy_threshold=args.threshold,
        confidence_threshold=args.confidence,
    )
    LOGGER.info("Drowsiness detector started.")
    try:
        while True:
            result = detector.process_frame()
            LOGGER.info(
                "DROWSINESS: %s (confidence=%.2f, count=%d, trigger=%s)",
                result["status"],
                result["confidence"],
                result["frame_count"],
                result["trigger_alert"],
            )
            if args.show:
                ok, frame = capture_frame(detector.camera)
                if ok and frame is not None:
                    frame = draw_info_on_frame(frame, result)
                    cv2.imshow("Drowsiness Debug", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
            time.sleep(0.05)
    except KeyboardInterrupt:
        LOGGER.info("Stopping drowsiness detector...")
    finally:
        detector.release()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
