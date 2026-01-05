#!/usr/bin/env python3
"""
Simple Servo Test Script
=========================
Tests a servo connected to GPIO18 (physical pin 12).

Wiring:
  - Servo Signal (orange/yellow) -> GPIO18 (pin 12)
  - Servo GND (brown/black)      -> GND (pin 6)
  - Servo V+ (red)               -> 5V (pin 2/4) or external 5V

Before running:
  1. sudo apt install pigpio python3-pigpio
  2. sudo systemctl enable --now pigpiod
  3. python3 test_servo.py
"""

import time
import sys

# ============================================================================
# CONFIGURATION - Change GPIO if you used a different pin
# ============================================================================
SERVO_GPIO = 18  # BCM GPIO number (GPIO18 = physical pin 12)

# ============================================================================

try:
    from servo_control import MG90SServo, ServoConfig
except ImportError:
    print("ERROR: servo_control.py not found in the same directory")
    sys.exit(1)


def test_basic_movement(servo: MG90SServo):
    """Test basic servo movement to key positions."""
    print("\n" + "=" * 50)
    print("TEST 1: Basic Movement")
    print("=" * 50)
    
    positions = [
        (90, "CENTER (90°)"),
        (0, "MIN (0°)"),
        (90, "CENTER (90°)"),
        (180, "MAX (180°)"),
        (90, "CENTER (90°)"),
    ]
    
    for angle, description in positions:
        print(f"  Moving to {description}...", end=" ", flush=True)
        servo.set_angle(angle)
        print("✓")
        time.sleep(1)
    
    print("  Basic movement test PASSED!")


def test_sweep(servo: MG90SServo):
    """Test smooth sweep from 0 to 180 and back."""
    print("\n" + "=" * 50)
    print("TEST 2: Sweep Test (0° → 180° → 0°)")
    print("=" * 50)
    
    # Sweep forward
    print("  Sweeping 0° to 180°...")
    for angle in range(0, 181, 10):
        servo.set_angle(angle)
        print(f"    {angle}°", end="\r", flush=True)
        time.sleep(0.1)
    print("    180° ✓")
    
    time.sleep(0.5)
    
    # Sweep backward
    print("  Sweeping 180° to 0°...")
    for angle in range(180, -1, -10):
        servo.set_angle(angle)
        print(f"    {angle}° ", end="\r", flush=True)
        time.sleep(0.1)
    print("    0° ✓")
    
    # Return to center
    servo.set_angle(90)
    print("  Returned to center (90°)")
    print("  Sweep test PASSED!")


def test_interactive(servo: MG90SServo):
    """Interactive mode - type angles to move servo."""
    print("\n" + "=" * 50)
    print("TEST 3: Interactive Mode")
    print("=" * 50)
    print("  Type an angle (0-180) and press Enter to move.")
    print("  Type 'q' to quit, 'c' for center, 's' for sweep.")
    print()
    
    while True:
        try:
            user_input = input("  Angle> ").strip().lower()
            
            if user_input == 'q':
                print("  Exiting interactive mode.")
                break
            elif user_input == 'c':
                servo.set_angle(90)
                print("  → Moved to center (90°)")
            elif user_input == 's':
                print("  → Quick sweep...", end=" ", flush=True)
                for a in [0, 90, 180, 90]:
                    servo.set_angle(a)
                    time.sleep(0.4)
                print("Done!")
            else:
                try:
                    angle = float(user_input)
                    actual = servo.set_angle(angle)
                    print(f"  → Moved to {actual:.1f}°")
                except ValueError:
                    print("  Invalid input. Enter a number 0-180, 'c', 's', or 'q'.")
        except KeyboardInterrupt:
            print("\n  Interrupted.")
            break


def main():
    print("=" * 50)
    print("  SERVO TEST - GPIO{} (pin 12)".format(SERVO_GPIO))
    print("=" * 50)
    
    # Create servo configuration
    config = ServoConfig(
        gpio=SERVO_GPIO,
        min_us=500,      # 0° position pulse width
        max_us=2500,     # 180° position pulse width
        min_angle=0.0,
        max_angle=180.0
    )
    
    try:
        print("\nConnecting to pigpio daemon...", end=" ", flush=True)
        servo = MG90SServo(config)
        print("OK!\n")
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        print("\nTroubleshooting:")
        print("  1. Install pigpio: sudo apt install pigpio python3-pigpio")
        print("  2. Start daemon:   sudo systemctl enable --now pigpiod")
        print("  3. Check status:   sudo systemctl status pigpiod")
        return 1
    
    try:
        # Run tests
        test_basic_movement(servo)
        test_sweep(servo)
        test_interactive(servo)
        
        # Cleanup
        print("\nTest complete! Turning servo off...")
        servo.off()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted! Cleaning up...")
    finally:
        servo.close()
        print("Servo closed. Done!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
