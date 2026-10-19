
import time
import cv2

from April_tag_detector import (
    IntellioCamera,
    AprilTagScanner,
    display_image,
    show_window,
    read_key,
    close_windows
)

# ==========================================
# CONFIGURATION
# ==========================================

FAMILY = "16h5"

MOTOR_1 = "L"
MOTOR_2 = "R"

FORWARD = "1"
BACKWARD = "2"

WINDOW_NAME = "Challenge 6 - Smart Grid"

CAMERA_TIMEOUT = 12
SCAN_TIMEOUT = 30

# Time allowed to collect multiple tags
DETECTION_TIME = 4.0

# Number of consecutive frames needed
CONFIRM_FRAMES = 2


# ==========================================
# APRILTAG DECISION
# ==========================================

def decide(ids):

    # Junior/Senior: paired AprilTags
    residential_pair = {1, 3}.issubset(ids)
    business_pair = {2, 4}.issubset(ids)

    if residential_pair and not business_pair:
        return "RESIDENTIAL"

    if business_pair and not residential_pair:
        return "BUSINESS"

    # Do not choose if both pairs are present
    if residential_pair and business_pair:
        return None

    # Elementary: single AprilTag
    # Only decide when no Junior/Senior tag
    # (ID 3 or 4) has been detected.
    if 3 not in ids and 4 not in ids:

        if 1 in ids and 2 not in ids:
            return "RESIDENTIAL"

        if 2 in ids and 1 not in ids:
            return "BUSINESS"

    return None


# ==========================================
# CAMERA SCANNING
# ==========================================

def scan_power():

    camera = None
    scanner = AprilTagScanner(
        families=(FAMILY,)
    )

    wanted = {
        (FAMILY, i)
        for i in (1, 2, 3, 4)
    }

    last_sequence = 0
    streak = {i: 0 for i in (1, 2, 3, 4)}

    # Store every confirmed ID during scan
    confirmed_ids = set()

    start = time.monotonic()
    first_frame_time = None

    try:
        cv2.namedWindow(
            WINDOW_NAME,
            cv2.WINDOW_NORMAL
        )

        camera = IntellioCamera()

        print("Scanning power requirement...")

        while time.monotonic() - start < SCAN_TIMEOUT:

            if read_key() in (ord("q"), ord("Q"), 27):
                print("Scan cancelled")
                return None

            frame, sequence = camera.read_new(
                last_sequence
            )

            if frame is None:

                if (
                    first_frame_time is None
                    and time.monotonic() - start
                    >= CAMERA_TIMEOUT
                ):
                    print("Camera timeout")
                    return None

                time.sleep(0.01)
                continue

            last_sequence = sequence

            if first_frame_time is None:
                first_frame_time = time.monotonic()

            try:
                tags, variant, view = scanner.scan(
                    frame,
                    wanted=wanted
                )

            except Exception as error:
                print("Scanner error:", error)
                continue

            visible_ids = set()

            for tag in tags:
                family = tag["family"]

                if isinstance(family, bytes):
                    family = family.decode("utf-8")

                tag_id = int(tag["id"])

                if family == FAMILY and tag_id in (1, 2, 3, 4):
                    visible_ids.add(tag_id)

            # Confirm tags
            for tag_id in (1, 2, 3, 4):

                if tag_id in visible_ids:
                    streak[tag_id] += 1
                else:
                    streak[tag_id] = 0

                if streak[tag_id] >= CONFIRM_FRAMES:
                    confirmed_ids.add(tag_id)

            elapsed = time.monotonic() - first_frame_time

            # Wait for the collection window
            # so Junior/Senior pairs can be detected
            decision = None

            if elapsed >= DETECTION_TIME:
                decision = decide(confirmed_ids)

            # ==================================
            # CAMERA PREVIEW
            # ==================================

            preview = display_image(
                view, tags, variant
            )

            height, width = preview.shape[:2]

            cv2.rectangle(
                preview,
                (0, height - 90),
                (width, height),
                (40, 40, 40),
                -1
            )

            if decision:
                status = f"{decision} NEEDS POWER"
                color = (0, 255, 0)

            else:
                status = "SCANNING APRILTAGS..."
                color = (255, 255, 255)

            cv2.putText(
                preview,
                status,
                (10, height - 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2
            )

            cv2.putText(
                preview,
                f"Confirmed IDs: {sorted(confirmed_ids)}",
                (10, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            show_window(WINDOW_NAME, preview)

            if decision:
                print("Detected IDs:", confirmed_ids)
                print("DECISION:", decision)
                return decision

        print("No unambiguous decision")
        print("Confirmed IDs:", confirmed_ids)
        return None

    finally:
        if camera is not None:
            camera.close()

        close_windows()


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    motor = QuarkyMiniExpansion()
    motor.miniinitialise()

    try:
        motor.stopmotor(MOTOR_1)
        motor.stopmotor(MOTOR_2)

        # STEP 1: Scan and decide
        decision = scan_power()

        if decision is None:
            print("No valid decision. Robot stopped.")
            return

        # ==================================
        # STEP 2: MUST MOVEMENT
        # ==================================

        print("Executing MUST movement")

        # Motor 1 backward 65% for 1 second
        motor.runmotor(MOTOR_1, BACKWARD, 65)
        time.sleep(1)
        motor.stopmotor(MOTOR_1)

        # Wait 1 second
        time.sleep(1)

        # ==================================
        # STEP 3: RESIDENTIAL MOVEMENT
        # ==================================

        if decision == "RESIDENTIAL":

            print("Executing RESIDENTIAL movement")

            # Motor 1 backward 75% for 0.8 sec
            motor.runmotor(MOTOR_1, BACKWARD, 75)
            time.sleep(0.8)
            motor.stopmotor(MOTOR_1)

            # Wait 1 second
            time.sleep(1)

            # Motor 1 forward 75% for 0.8 sec
            motor.runmotor(MOTOR_1, FORWARD, 75)
            time.sleep(0.8)
            motor.stopmotor(MOTOR_1)

            # Wait 1 second
            time.sleep(1)

        # ==================================
        # STEP 4: BUSINESS MOVEMENT
        # ==================================

        elif decision == "BUSINESS":

            print("Executing BUSINESS movement")

            # Motor 2 forward 65% for 1 second
            motor.runmotor(MOTOR_2, FORWARD, 65)
            time.sleep(1)
            motor.stopmotor(MOTOR_2)

            # Wait 1 second
            time.sleep(1)

            # Motor 2 backward 65% for 1 second
            motor.runmotor(MOTOR_2, BACKWARD, 65)
            time.sleep(1)
            motor.stopmotor(MOTOR_2)

        print("Challenge 6 completed!")

    except KeyboardInterrupt:
        print("Program interrupted")

    except Exception as error:
        print("Error:", error)

    finally:
        motor.stopmotor(MOTOR_1)
        motor.stopmotor(MOTOR_2)
        print("Motors stopped")


if __name__ == "__main__":
    main()
