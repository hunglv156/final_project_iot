"""GPIO helpers for HC-SR04 sensors and buzzer."""

from __future__ import annotations

import threading
import time
from typing import Dict, Iterable

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover - only for non-Pi development.
    GPIO = None  # type: ignore[assignment]


def _require_gpio() -> None:
    if GPIO is None:
        raise RuntimeError("RPi.GPIO is not available. Run this module on Raspberry Pi.")


def setup_sensors(sensor_config: Dict[str, Dict[str, int]]) -> None:
    _require_gpio()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for cfg in sensor_config.values():
        trig = cfg["trig"]
        echo = cfg["echo"]
        GPIO.setup(trig, GPIO.OUT)
        GPIO.setup(echo, GPIO.IN)
        GPIO.output(trig, False)


def setup_buzzer(pin: int) -> None:
    _require_gpio()
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, False)


def get_distance(trig_pin: int, echo_pin: int, timeout: float = 0.1) -> float:
    _require_gpio()
    GPIO.output(trig_pin, True)
    time.sleep(0.00001)
    GPIO.output(trig_pin, False)

    start_wait = time.time()
    pulse_start = start_wait
    while GPIO.input(echo_pin) == 0:
        pulse_start = time.time()
        if pulse_start - start_wait > timeout:
            return float("inf")

    pulse_end = pulse_start
    while GPIO.input(echo_pin) == 1:
        pulse_end = time.time()
        if pulse_end - pulse_start > timeout:
            return float("inf")

    pulse_duration = pulse_end - pulse_start
    distance_cm = pulse_duration * 17150
    return round(distance_cm, 2)


def buzzer_beep(pin: int, pattern_list: Iterable[float], lock: threading.Lock | None = None) -> None:
    _require_gpio()
    if lock is None:
        lock = threading.Lock()
    with lock:
        for index, duration in enumerate(pattern_list):
            if index % 2 == 0:
                GPIO.output(pin, True)
                time.sleep(max(0.0, duration))
                GPIO.output(pin, False)
            else:
                time.sleep(max(0.0, duration))


def cleanup_gpio() -> None:
    if GPIO is not None:
        GPIO.cleanup()
