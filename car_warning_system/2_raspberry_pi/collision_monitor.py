"""Collision monitor module for 4x HC-SR04 sensors."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from typing import Dict, Tuple

from utils.gpio_helper import buzzer_beep, cleanup_gpio, get_distance, setup_buzzer, setup_sensors

LOGGER = logging.getLogger(__name__)

DEFAULT_SENSOR_CONFIG: Dict[str, Dict[str, int]] = {
    "front": {"trig": 23, "echo": 24, "warn_dist": 50.0},
    "rear": {"trig": 17, "echo": 27, "warn_dist": 30.0},
    "left": {"trig": 5, "echo": 6, "warn_dist": 40.0},
    "right": {"trig": 20, "echo": 21, "warn_dist": 40.0},
}

PATTERNS = {
    "collision_danger": [0.3, 0.1, 0.3, 0.1, 0.3],
    "collision_warning": [0.1, 0.05],
}


@dataclass
class CollisionResult:
    side: str
    distance_cm: float
    level: str


class CollisionMonitor:
    def __init__(self, sensor_config: Dict[str, Dict[str, int]], buzzer_pin: int = 12) -> None:
        self.sensor_config = sensor_config
        self.buzzer_pin = buzzer_pin
        setup_sensors(sensor_config)
        setup_buzzer(buzzer_pin)

    def classify_distance(self, side: str, distance_cm: float) -> str:
        warn_dist = float(self.sensor_config[side]["warn_dist"])
        if distance_cm == float("inf"):
            return "NO_ECHO"
        if distance_cm < warn_dist * 0.5:
            return "DANGER"
        if distance_cm < warn_dist:
            return "WARNING"
        return "OK"

    def read_side(self, side: str) -> CollisionResult:
        trig = int(self.sensor_config[side]["trig"])
        echo = int(self.sensor_config[side]["echo"])
        distance = get_distance(trig, echo, timeout=0.03)
        level = self.classify_distance(side, distance)
        return CollisionResult(side=side, distance_cm=distance, level=level)

    def read_all(self) -> Dict[str, CollisionResult]:
        return {side: self.read_side(side) for side in self.sensor_config}

    @staticmethod
    def max_alert_level(results: Dict[str, CollisionResult]) -> Tuple[str, str]:
        priorities = {"DANGER": 3, "WARNING": 2, "OK": 1, "NO_ECHO": 0}
        best = max(results.values(), key=lambda r: priorities[r.level])
        return best.level, best.side

    def run(self, interval_sec: float = 0.2, enable_buzzer: bool = True) -> None:
        try:
            while True:
                results = self.read_all()
                level, side = self.max_alert_level(results)
                msg = " | ".join(
                    f"{s}={r.distance_cm:.1f}cm ({r.level})" if r.distance_cm != float("inf") else f"{s}=inf ({r.level})"
                    for s, r in results.items()
                )
                LOGGER.info("COLLISION: %s", msg)
                if enable_buzzer:
                    if level == "DANGER":
                        LOGGER.warning("ALERT: collision danger on %s", side)
                        buzzer_beep(self.buzzer_pin, PATTERNS["collision_danger"])
                    elif level == "WARNING":
                        buzzer_beep(self.buzzer_pin, PATTERNS["collision_warning"])
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            LOGGER.info("Stopping collision monitor...")
        finally:
            cleanup_gpio()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--buzzer_pin", type=int, default=12)
    parser.add_argument("--no_buzzer", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
    )
    args = parse_args()
    monitor = CollisionMonitor(DEFAULT_SENSOR_CONFIG, buzzer_pin=args.buzzer_pin)
    monitor.run(interval_sec=args.interval, enable_buzzer=not args.no_buzzer)


if __name__ == "__main__":
    main()
