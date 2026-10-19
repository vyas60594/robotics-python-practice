
import time

# Initialize controllers
servo = QuarkyIntellio()

motor = QuarkyMiniExpansion()
motor.miniinitialise()

# ==========================================
# CHALLENGE 5
# ==========================================

try:
    # Block 1: Set servo S1 to 90 degrees
    servo.moveservointime('S1', 90, 1)

    # Block 2: Wait 1 second
    time.sleep(1)

    # Block 3: Motor 1 backward at 65% speed
    motor.runmotor("L", "2", 65)

    # Block 4: Motor 2 forward at 70% speed
    motor.runmotor("R", "1", 70)

    # Block 5: Wait 1 second
    time.sleep(1)

    # Block 6: Stop robot
    motor.stopmotor("L")
    motor.stopmotor("R")

    # Block 7: Set servo S1 to 0 degrees
    servo.moveservointime('S1', 0, 1)

    # Block 8: Wait 1 second
    time.sleep(1)

    # Block 9: Stop robot
    motor.stopmotor("L")
    motor.stopmotor("R")

    # Block 10: Wait 1 second
    time.sleep(1)

    # Block 11: Motor 1 forward at 63% speed
    motor.runmotor("L", "1", 63)

    # Block 12: Motor 2 backward at 67% speed
    motor.runmotor("R", "2", 67)

    # Block 13: Wait 1 second
    time.sleep(1)

    # Block 14: Stop robot
    motor.stopmotor("L")
    motor.stopmotor("R")

finally:
    # Ensure both motors stop
    motor.stopmotor("L")
    motor.stopmotor("R")
