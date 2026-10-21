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

SERVO_PORT = "S1"

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
# Returns: "organic", "inorganic", or None
# ==========================================

def normalize_family(family):
    if isinstance(family, bytes):
        family = family.decode("utf-8")

    return str(family).lower().replace("tag", "").strip()


def wait_for_classification(camera, scanner):

    print("Starting AprilTag detection...")

    start = time.monotonic()
    last_sequence = 0
    matches = 0
    last_detected = None
    frames_received = 0
    last_classification = None

    while time.monotonic() - start < SCAN_TIMEOUT:

        key = read_key()

        if key in (ord("q"), ord("Q"), 27):
            print("Scanning cancelled.")
            return None

        try:
            frame, sequence = camera.read_new(last_sequence)

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

        if tuple(sorted(detected_tags)) != last_detected:
            print("Detected AprilTags:", detected_tags)
            last_detected = tuple(sorted(detected_tags))

        # ==================================
        # CLASSIFY ORGANIC OR INORGANIC
        # ==================================

        if ORGANIC_TAG in detected_tags:
            classification = "organic"

        elif any(
            family == ORGANIC_TAG[0]
            for family, tag_id in detected_tags
        ):
            classification = "inorganic"

        else:
            classification = None

        # Require consecutive matching classifications.
        if classification is not None:
            if classification == last_classification:
                matches += 1
            else:
                last_classification = classification
                matches = 1
        else:
            matches = 0
            last_classification = None

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

        if classification == "organic":
            status = "ORGANIC DETECTED"
            color = (0, 255, 0)

        elif classification == "inorganic":
            status = "INORGANIC DETECTED"
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

        cv2.putText(
            panel,
            "Tags: " + str(detected_tags)[:55],
            (10, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )

        cv2.putText(
            panel,
            f"Matches: {matches}/{REQUIRED_MATCHES}",
            (10, 88),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )

        output = np.vstack((preview, panel))
        show_window(WINDOW_NAME, output)

        if matches >= REQUIRED_MATCHES:
            print("CLASSIFICATION CONFIRMED:", classification)
            return classification

    print("Scan timeout.")
    print("Camera frames received:", frames_received)
    print("Last detected tags:", last_detected)

    return None


# ==========================================
# ORGANIC SEQUENCE
# Existing movement sequence preserved
# ==========================================

def run_organic_sequence(servo, motor):

    print("Executing existing organic sequence...")

    # Block 1: Wait 1 second
    time.sleep(1)

    # Block 2: Motor 1 backward at 70%
    motor.runmotor(MOTOR_1, BACKWARD, 70)

    # Block 3: Motor 2 forward at 70%
    motor.runmotor(MOTOR_2, FORWARD, 70)

    # Block 4: Wait 0.9 seconds
    time.sleep(0.9)

    # Block 5: Stop robot
    stop(motor)

    # Block 6: Wait 1 second
    time.sleep(1)

    # Block 7: Servo S1 -> 20 degrees
    servo.moveservointime(SERVO_PORT, 20, 1)

    # Block 8: Wait 1 second
    time.sleep(1)

    # Block 9: Motor 1 forward at 70%
    motor.runmotor(MOTOR_1, FORWARD, 70)

    # Block 10: Motor 2 backward at 70%
    motor.runmotor(MOTOR_2, BACKWARD, 70)

    # Block 11: Wait 1.2 seconds
    time.sleep(1.2)

    # Block 12: Stop robot
    stop(motor)

    # Block 13: Wait 1 second
    time.sleep(1)

    # Block 14: Motor 2 forward at 55% for 1 second
    motor.runmotor(MOTOR_2, BACKWARD, 55)
    time.sleep(1)
    motor.stopmotor(MOTOR_2)

    # Block 15: Wait 1 second
    time.sleep(1)

    # Block 16: Servo S1 -> 90 degrees
    servo.moveservointime(SERVO_PORT, 90, 1)

    # Block 17: Wait 0.3 seconds
    time.sleep(0.3)

    # Block 18: Motor 1 forward at 80%
    motor.runmotor(MOTOR_1, FORWARD, 80)

    # Block 19: Motor 2 backward at 80%
    motor.runmotor(MOTOR_2, BACKWARD, 80)

    # Block 20: Wait 1 second
    time.sleep(1)

    # Block 21: Stop robot
    stop(motor)


# ==========================================
# INORGANIC EXTRA SEQUENCE
# Executes BEFORE the organic sequence
# ==========================================

def run_inorganic_sequence(motor):

    print("Executing additional inorganic blocks...")

    # Image Block 1:
    # Motor 1 backward at 70%
    motor.runmotor(MOTOR_1, BACKWARD, 70)

    # Image Block 2: Wait 1 second
    time.sleep(1)

    # Image Block 3: Stop robot
    stop(motor)

    # Image Block 4: Wait 1 second
    time.sleep(1)

    # Image Block 5:
    # Motor 2 backward at 60%
    motor.runmotor(MOTOR_2, BACKWARD, 60)

    # Image Block 6: Wait 1 second
    time.sleep(1)

    # Image Block 7: Stop robot
    stop(motor)
    
    motor.runmotor(MOTOR_1, BACKWARD, 80)

    # Block 19: Motor 2 backward at 80%
    motor.runmotor(MOTOR_2, FORWARD, 80)

    # Block 20: Wait 1 second
    time.sleep(0.8)

    # Block 21: Stop robot
    stop(motor)
    time.sleep(1)
 
    

    print("Additional inorganic blocks completed.")


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
        # INITIAL SERVO POSITION
        # ==================================

        print("Initializing servo to 90 degrees...")

        servo.moveservointime(SERVO_PORT, 90, 1)
        time.sleep(1)

        print("Servo initialization completed.")

        # ==================================
        # INITIAL MOTOR MOVEMENT
        # ==================================

        # Motor 2 forward at 67% for 1 second
        motor.runmotor(MOTOR_2, FORWARD, 67)
        time.sleep(1)
        motor.stopmotor(MOTOR_2)

        print("Initial motor movement completed.")

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
        # CLASSIFY WASTE
        # ==================================

        result = wait_for_classification(camera, scanner)

        if result is None:
            print("Classification unsuccessful or cancelled.")
            stop(motor)
            return

        # ==================================
        # BRANCH: INORGANIC
        # ==================================

        if result == "inorganic":

            print("INORGANIC WASTE CONFIRMED.")

            # Run extra blocks only for inorganic waste.
            run_inorganic_sequence(motor)

        # ==================================
        # BRANCH: ORGANIC
        # ==================================

        elif result == "organic":

            print("ORGANIC WASTE CONFIRMED.")
            print("Skipping additional inorganic blocks.")

        # ==================================
        # COMMON REMAINING SEQUENCE
        # Both classifications reach this point.
        # ==================================

        run_organic_sequence(servo, motor)

        print("Challenge completed successfully!")

    except KeyboardInterrupt:
        print("Program interrupted.")

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
