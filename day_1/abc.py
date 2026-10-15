
import time

motor = QuarkyMiniExpansion()
servo = QuarkyIntellio()

motor.miniinitialise()

SPEED = 87
STRAIGHT = 90
LEFT = 40

TURN_TIME = 2.0

try:
    servo.moveservointime("S1", STRAIGHT, 1)
    time.sleep(1)

    motor.runmotor('L', '1', SPEED)
    time.sleep(10)
    motor.stopmotor('L')

    servo.moveservointime("S1", LEFT, 1)
    time.sleep(1)

    motor.runmotor('L', '1', 55)
    time.sleep(TURN_TIME)
    motor.stopmotor('L')

    servo.moveservointime("S1", STRAIGHT, 1)
    time.sleep(1)

    motor.runmotor('L', '1', SPEED)
    time.sleep(10)

finally:
    motor.stopmotor('L')

print("Movement completed!")
