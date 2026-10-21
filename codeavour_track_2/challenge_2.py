import time

sprite = Sprite('Stage')

# ==========================================
# CONFIGURATION
# ==========================================

POWER = 60
MOVE_TIME = 1.0

LEFT_MOTOR = "L"
RIGHT_MOTOR = "R"

FORWARD = "1"
BACKWARD = "2"


# ==========================================
# INITIALIZE ROBOT
# ==========================================

def initialize_robot():
    global mini

    mini = QuarkyMiniExpansion()
    mini.miniinitialise()
    mini.stoprobot()

    print("Robot initialized successfully.")


# ==========================================
# MOVEMENT FUNCTIONS
# ==========================================

def stop_robot():
    mini.stoprobot()


def wait():
    time.sleep(0.5)


def turn_left():
    """Turn left using both motors."""
    mini.runmotor(LEFT_MOTOR, FORWARD, str(POWER))
    mini.runmotor(RIGHT_MOTOR, BACKWARD, str(POWER))
    time.sleep(0.5)
    stop_robot()


def turn_right(speed=POWER):
    """Turn right using the right motor."""
    mini.runmotor(RIGHT_MOTOR, FORWARD, str(speed))
    time.sleep(MOVE_TIME)
    stop_robot()


def move_forward(duration=MOVE_TIME):
    """Move both motors forward."""
    mini.runmotor(LEFT_MOTOR, FORWARD, str(POWER))
    mini.runmotor(RIGHT_MOTOR, FORWARD, str(POWER))
    time.sleep(duration)
    stop_robot()


def move_backward(duration=1.2):
    """Move both motors backward."""
    mini.runmotor(LEFT_MOTOR, BACKWARD, str(POWER))
    mini.runmotor(RIGHT_MOTOR, BACKWARD, str(POWER))
    time.sleep(duration)
    stop_robot()


def turn_left_single_motor():
    """Turn left using the left motor."""
    mini.runmotor(LEFT_MOTOR, FORWARD, str(POWER))
    time.sleep(MOVE_TIME)
    stop_robot()


# ==========================================
# TASK SEQUENCE
# ==========================================

def execute_task():

    # Step 1: Turn LEFT using both motors
    turn_left()
    wait()

    # Step 2: Turn RIGHT
    turn_right()
    wait()

    # Step 3: Move FORWARD for 1 second
    move_forward(MOVE_TIME)
    wait()

    # Step 4: Move BACKWARD
    move_backward(1.2)
    wait()

    # Step 5: Turn RIGHT at 65% speed
    turn_right(speed=65)
    wait()

    # Step 6: Turn LEFT using the left motor
    turn_left_single_motor()
    wait()

    # Step 7: Move FORWARD for 0.5 seconds
    move_forward(0.5)
    wait()

    # Step 8: Move BACKWARD
    move_backward(1.2)
    wait()

    print("Task completed.")


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():
    try:
        initialize_robot()
        execute_task()

    except KeyboardInterrupt:
        print("Task interrupted by user.")

    except Exception as exc:
        print("Error:", exc)

    finally:
        if 'mini' in globals():
            stop_robot()


main()
