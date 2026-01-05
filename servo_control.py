from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


try:
    import pigpio  # type: ignore
except Exception:  # pragma: no cover
    pigpio = None


@dataclass(frozen=True)
class ServoConfig:
    gpio: int
    min_us: int = 500
    max_us: int = 2500
    min_angle: float = 0.0
    max_angle: float = 180.0

    def clamp_pulse_us(self, pulse_us: int) -> int:
        return max(self.min_us, min(self.max_us, int(pulse_us)))

    def clamp_angle(self, angle: float) -> float:
        return max(self.min_angle, min(self.max_angle, float(angle)))


class MG90SServo:
    """Simple MG90S servo control for Raspberry Pi.

    Recommended backend: pigpio (stable 50Hz servo pulses).

    Wiring reminders:
    - Servo signal -> GPIO (BCM numbering)
    - Servo V+ -> 5V external supply (recommended)
    - Servo GND -> supply GND AND Pi GND (common ground)
    """

    def __init__(self, config: ServoConfig, *, pi: Optional["pigpio.pi"] = None):
        self.config = config
        self._pi = pi
        self._owns_pi = False

        if pigpio is None:
            raise RuntimeError(
                "pigpio is required. Install with: sudo apt-get install pigpio python3-pigpio\n"
                "Then start the daemon: sudo systemctl enable --now pigpiod"
            )

        if self._pi is None:
            self._pi = pigpio.pi()  # type: ignore[attr-defined]
            self._owns_pi = True

        if not self._pi.connected:  # type: ignore[union-attr]
            raise RuntimeError(
                "Cannot connect to pigpio daemon. Start it with: sudo systemctl enable --now pigpiod"
            )

    def close(self) -> None:
        try:
            self.off()
        finally:
            if self._owns_pi and self._pi is not None:
                self._pi.stop()  # type: ignore[union-attr]
                self._pi = None

    def __enter__(self) -> "MG90SServo":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def off(self) -> None:
        """Stop sending pulses (servo relaxes)."""
        if self._pi is None:
            return
        self._pi.set_servo_pulsewidth(self.config.gpio, 0)  # type: ignore[union-attr]

    def set_pulse_us(self, pulse_us: int) -> int:
        """Set raw pulse width in microseconds. Returns the clamped value."""
        if self._pi is None:
            raise RuntimeError("Servo is closed")
        clamped = self.config.clamp_pulse_us(pulse_us)
        self._pi.set_servo_pulsewidth(self.config.gpio, clamped)  # type: ignore[union-attr]
        return clamped

    def set_angle(self, angle: float) -> float:
        """Set angle in degrees. Returns the clamped angle."""
        if self._pi is None:
            raise RuntimeError("Servo is closed")

        angle = self.config.clamp_angle(angle)

        span_angle = self.config.max_angle - self.config.min_angle
        if span_angle <= 0:
            raise ValueError("Invalid angle range")

        t = (angle - self.config.min_angle) / span_angle
        pulse = int(self.config.min_us + t * (self.config.max_us - self.config.min_us))
        self.set_pulse_us(pulse)
        return angle
