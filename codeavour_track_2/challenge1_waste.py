
import time
import cv2
import numpy as np

from April_tag_detector import (
    IntellioCamera,
    AprilTagScanner,
    show_window,
    read_key,
    close_windows
)

# ==========================================
# CONFIGURATION
# ==========================================

ORGANIC_TAG = ("16h5", 6)

SERVO_PORT = 'S1'

MOTOR_1 = "L"
MOTOR_2 = "R"

FORWARD = "1"
BACKWARD = "2"

REQUIRED_MATCHES = 3
SCAN_TIMEOUT = 30.0

WINDOW_NAME = "Codeavour - AprilTag Camera"


# ==========================================
# MOTOR CONTROL
# ==========================================

def stop(motor):
    motor.stopmotor(MOTOR_1)
    motor.stopmotor(MOTOR_2)


# ==========================================
# APRILTAG DETECTION
# ==========================================

def normalize_family(family):
    if isinstance(family, bytes):
        family = family.decode("utf-8")
    return str(family).lower().replace("tag", "").strip()


def wait_for_organic(camera, scanner):

    print("Starting AprilTag detection...")

    start = time.monotonic()
    last_sequence = 0
    matches = 0
    last_detected = None
    frames_received = 0

    while time.monotonic() - start < SCAN_TIMEOUT:

        key = read_key()

        if key in (ord("q"), ord("Q"), 27):
            print("Scanning cancelled")
            return False

        try:
            frame, sequence = camera.read_new(
                last_sequence
            )
        except Exception as exc:
            print("Camera read error:", exc)
            time.sleep(0.01)
            continue

        if frame is None:
            time.sleep(0.01)
            continue

        last_sequence = sequence
        frames_received += 1

        try:
            tags, variant, view = scanner.scan(frame)

        except Exception as exc:
            print("Scanner error:", exc)
            continue

        detected_tags = []

        for tag in tags:
            family = normalize_family(tag["family"])
            tag_id = int(tag["id"])
            detected_tags.append((family, tag_id))

        current = tuple(sorted(detected_tags))

        if current != last_detected:
            print("Detected AprilTags:", detected_tags)
            last_detected = current

        organic = ORGANIC_TAG in detected_tags

        matches = matches + 1 if organic else 0

        # ==================================
        # CAMERA PREVIEW
        # ==================================

        preview = view.copy()

        if preview.ndim == 2:
            preview = cv2.cvtColor(
                preview, cv2.COLOR_GRAY2BGR
            )

        panel = np.zeros(
            (100, preview.shape[1], 3),
            dtype=np.uint8
        )

        if organic:
            status = "ORGANIC DETECTED"
            color = (0, 255, 0)
        elif detected_tags:
            status = "TAG FOUND - NOT ORGANIC"
            color = (0, 165, 255)
        else:
            status = "SCANNING APRILTAG..."
            color = (0, 255, 255)

        cv2.putText(
            panel,
            status,
            (10, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2
        )

        tag_text = str(detected_tags)

        cv2.putText(
            panel,
            "Tags: " + tag_text[:55],
            (10, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )

        cv2.putText(
            panel,
            f"Organic matches: {matches}/{REQUIRED_MATCHES}",
            (10, 88),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )

        output = np.vstack((preview, panel))

        show_window(WINDOW_NAME, output)

        if matches >= REQUIRED_MATCHES:
            print("ORGANIC CONFIRMED:", ORGANIC_TAG)
            return True

    print("Scan timeout.")
    print("Camera frames received:", frames_received)
    print("Last detected tags:", last_detected)
    return False


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    servo = QuarkyIntellio()

    motor = QuarkyMiniExpansion()
    motor.miniinitialise()

    camera = None

    try:
        stop(motor)

        # ==================================
        # UPDATED: INITIAL SERVO POSITION
        # ==================================

        print("Initializing servo to 70 degrees...")

        servo.moveservointime(
            SERVO_PORT, 70, 1
        )

        time.sleep(1)

        print("Servo initialization completed.")

        # Block 2: Motor 2 forward 67% for 1 sec
        motor.runmotor(MOTOR_2, FORWARD, 67)
        time.sleep(1)
        motor.stopmotor(MOTOR_2)

        print("Initial turn completed")

        # ==================================
        # CAMERA INITIALIZATION
        # ==================================

        cv2.namedWindow(
            WINDOW_NAME,
            cv2.WINDOW_NORMAL
        )

        loading = np.zeros(
            (240, 440, 3),
            dtype=np.uint8
        )

        cv2.putText(
            loading,
            "Waiting for camera...",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        show_window(WINDOW_NAME, loading)
        read_key()

        camera = IntellioCamera()

        scanner = AprilTagScanner(
            families=("16h5",)
        )

        # ==================================
        # ORGANIC CONDITION
        # ==================================

        if not wait_for_organic(camera, scanner):
            print("Organic not confirmed.")
            return

        print("Executing remaining blocks")

        # Block 3: Wait 1 second
        time.sleep(1)

        # Block 4: Motor 1 forward 70%
        motor.runmotor(MOTOR_1, BACKWARD, 70)

        # Block 5: Motor 2 forward 70%
        motor.runmotor(MOTOR_2, FORWARD, 70)

        # Block 6: Wait 0.9 seconds
        time.sleep(0.9)

        # Block 7: Stop robot
        stop(motor)

        # Block 8: Wait 1 second
        time.sleep(1)

        # Block 9: Servo S1 -> 20 degrees in 1 sec
        servo.moveservointime(SERVO_PORT, 20, 1)

        # Block 10: Wait 1 second
        time.sleep(1)

        # Block 11: Motor 1 backward 70%
        motor.runmotor(MOTOR_1, FORWARD, 70)

        # Block 12: Motor 2 backward 70%
        motor.runmotor(MOTOR_2, BACKWARD, 70)

        # Block 13: Wait 1.2 seconds
        time.sleep(1.2)

        # Block 14: Stop robot
        stop(motor)

        # Block 15: Wait 1 second
        time.sleep(1)

        # Block 16: Motor 2 forward 55% for 1 sec
        motor.runmotor(MOTOR_2, FORWARD, 55)
        time.sleep(1)
        motor.stopmotor(MOTOR_2)

        # Block 17: Wait 1 second
        time.sleep(1)

        # Block 18: Servo S1 -> 70 degrees
        servo.moveservointime(SERVO_PORT, 70, 1)

        # Block 19: Wait 0.3 seconds
        time.sleep(0.3)

        # Block 20: Motor 1 backward 80%
        motor.runmotor(MOTOR_1, FORWARD, 80)

        # Block 21: Motor 2 backward 80%
        motor.runmotor(MOTOR_2, BACKWARD, 80)

        # Wait 1 second
        time.sleep(1)

        # Stop robot
        stop(motor)

        print("Challenge completed!")

    except KeyboardInterrupt:
        print("Program interrupted")

    except Exception as exc:
        print("Program error:", exc)

    finally:
        stop(motor)

        if camera is not None:
            try:
                camera.close()
            except Exception:
                pass

        close_windows()


if __name__ == "__main__":
    main()
