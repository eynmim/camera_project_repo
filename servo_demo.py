#!/usr/bin/env python3

import argparse
import time

from servo_control import MG90SServo, ServoConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="MG90S servo quick test (pigpio)")
    parser.add_argument("--gpio", type=int, required=True, help="BCM GPIO number (signal pin)")
    parser.add_argument("--min-us", type=int, default=500, help="Minimum pulse width (us)")
    parser.add_argument("--max-us", type=int, default=2500, help="Maximum pulse width (us)")
    parser.add_argument("--angle", type=float, default=None, help="Move once to angle and exit")
    parser.add_argument("--sweep", action="store_true", help="Sweep 0->180->0")
    parser.add_argument("--delay", type=float, default=0.6, help="Delay between moves")
    args = parser.parse_args()

    cfg = ServoConfig(gpio=args.gpio, min_us=args.min_us, max_us=args.max_us)

    with MG90SServo(cfg) as servo:
        if args.angle is not None:
            angle = servo.set_angle(args.angle)
            print(f"Moved to {angle:.1f}°")
            time.sleep(args.delay)
            return 0

        if args.sweep:
            for a in (0, 45, 90, 135, 180, 135, 90, 45, 0):
                servo.set_angle(a)
                print(f"Angle: {a}")
                time.sleep(args.delay)
            return 0

        # Default: center servo
        servo.set_angle(90)
        print("Moved to 90°")
        time.sleep(args.delay)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
