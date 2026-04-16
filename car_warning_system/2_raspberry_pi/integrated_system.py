"""Integrated collision + drowsiness warning system."""

from __future__ import annotations

import argparse
import logging
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from collision_monitor import CollisionMonitor, DEFAULT_SENSOR_CONFIG
from drowsiness_detector import DrowsinessDetector
from utils.gpio_helper import buzzer_beep, cleanup_gpio, setup_buzzer

LOGGER = logging.getLogger(__name__)

BUZZER_PIN = 12
PATTERNS = {
    "collision_danger": [0.3, 0.1, 0.3, 0.1, 0.3],
    "collision_warning": [0.1, 0.05],
    "drowsiness": [0.15, 0.1, 0.15, 0.1, 0.15, 0.1, 0.15, 0.1, 0.15],
}
PRIORITIES = {
    "collision_danger": 1,
    "drowsiness": 2,
    "collision_warning": 3,
}


@dataclass(order=True)
class AlertEvent:
    priority: int
    kind: str = field(compare=False)
    message: str = field(compare=False, default="")
    created_at: float = field(compare=False, default_factory=time.time)


def read_cpu_temp() -> Optional[float]:
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            check=True,
            capture_output=True,
            text=True,
        )
        text = result.stdout.strip()
        if "=" in text and "'" in text:
            return float(text.split("=")[1].split("'")[0])
    except Exception:
        return None
    return None


class IntegratedSystem:
    def __init__(
        self,
        model_path: str,
        camera_index: int = 0,
        drowsy_threshold: int = 4,
        drowsy_confidence: float = 0.7,
    ) -> None:
        self.stop_event = threading.Event()
        self.alert_queue: queue.PriorityQueue[AlertEvent] = queue.PriorityQueue(maxsize=50)
        self.stats: Dict[str, int] = {
            "collision_danger": 0,
            "collision_warning": 0,
            "drowsiness": 0,
        }
        self.last_warning_time = 0.0

        self.collision_monitor = CollisionMonitor(DEFAULT_SENSOR_CONFIG, buzzer_pin=BUZZER_PIN)
        self.drowsiness_detector = DrowsinessDetector(
            model_path=model_path,
            camera_index=camera_index,
            drowsy_threshold=drowsy_threshold,
            confidence_threshold=drowsy_confidence,
        )
        setup_buzzer(BUZZER_PIN)

    def enqueue_alert(self, kind: str, message: str) -> None:
        try:
            self.alert_queue.put_nowait(
                AlertEvent(priority=PRIORITIES[kind], kind=kind, message=message)
            )
        except queue.Full:
            LOGGER.warning("Alert queue full, dropping alert: %s", kind)

    def collision_thread(self) -> None:
        LOGGER.info("Collision thread started.")
        while not self.stop_event.is_set():
            results = self.collision_monitor.read_all()
            level, side = self.collision_monitor.max_alert_level(results)
            summary = " | ".join(
                f"{k}={v.distance_cm:.1f}cm({v.level})" if v.distance_cm != float("inf") else f"{k}=inf({v.level})"
                for k, v in results.items()
            )
            LOGGER.info("COLLISION: %s", summary)
            now = time.time()
            if level == "DANGER":
                self.stats["collision_danger"] += 1
                self.enqueue_alert("collision_danger", f"Danger at {side}")
            elif level == "WARNING" and now - self.last_warning_time > 1.0:
                self.last_warning_time = now
                self.stats["collision_warning"] += 1
                self.enqueue_alert("collision_warning", f"Warning at {side}")
            time.sleep(0.2)

    def drowsiness_thread(self) -> None:
        LOGGER.info("Drowsiness thread started.")
        while not self.stop_event.is_set():
            try:
                result = self.drowsiness_detector.process_frame()
            except Exception as exc:
                LOGGER.error("Drowsiness processing failed: %s", exc)
                time.sleep(1.0)
                continue
            status = result["status"]
            conf = result["confidence"]
            count = result["frame_count"]
            LOGGER.info("DROWSINESS: %s (confidence=%.2f, count=%d)", status, conf, count)
            if bool(result["trigger_alert"]):
                self.stats["drowsiness"] += 1
                self.enqueue_alert("drowsiness", f"Drowsiness detected (count={count})")
            time.sleep(0.05)

    def buzzer_thread(self) -> None:
        LOGGER.info("Buzzer thread started.")
        while not self.stop_event.is_set():
            try:
                event = self.alert_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            pattern = PATTERNS.get(event.kind)
            if pattern:
                LOGGER.warning("ALERT: %s | %s", event.kind, event.message)
                buzzer_beep(BUZZER_PIN, pattern)
            self.alert_queue.task_done()

    def health_thread(self) -> None:
        LOGGER.info("Health thread started.")
        while not self.stop_event.is_set():
            cpu_temp = read_cpu_temp()
            if cpu_temp is None:
                LOGGER.info(
                    "HEALTH: alerts=%s queue=%d",
                    self.stats,
                    self.alert_queue.qsize(),
                )
            else:
                LOGGER.info(
                    "HEALTH: cpu_temp=%.1fC alerts=%s queue=%d",
                    cpu_temp,
                    self.stats,
                    self.alert_queue.qsize(),
                )
            time.sleep(5.0)

    def run(self) -> None:
        threads = [
            threading.Thread(target=self.collision_thread, daemon=True),
            threading.Thread(target=self.drowsiness_thread, daemon=True),
            threading.Thread(target=self.buzzer_thread, daemon=True),
            threading.Thread(target=self.health_thread, daemon=True),
        ]
        for t in threads:
            t.start()
        LOGGER.info("Integrated system started.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            LOGGER.info("Shutting down integrated system...")
        finally:
            self.stop_event.set()
            self.drowsiness_detector.release()
            cleanup_gpio()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", default="models/drowsiness_model.h5")
    parser.add_argument("--camera_index", type=int, default=0)
    parser.add_argument("--drowsy_threshold", type=int, default=4)
    parser.add_argument("--drowsy_confidence", type=float, default=0.7)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
    )
    args = parse_args()
    system = IntegratedSystem(
        model_path=args.model_path,
        camera_index=args.camera_index,
        drowsy_threshold=args.drowsy_threshold,
        drowsy_confidence=args.drowsy_confidence,
    )
    system.run()


if __name__ == "__main__":
    main()
