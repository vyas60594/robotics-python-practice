"""Codeavour 8.0 Track 2 - Challenge 6: Smart Grid recognition and motor test.

Elementary: AprilTag 16h5 ID 1 -> Residential, ID 2 -> Business.
Junior/Senior: IDs 1+3 -> Residential, IDs 2+4 -> Business.

Residential -> drive FORWARD for 3 seconds.
Business -> drive BACKWARD for 3 seconds.

The first confirmed decision triggers exactly one movement, then the
program stops. Q quits before any detection.

PictoBlox Python Stage Mode, Mini Expansion Board extension,
April_tag_detector.py and existing Intellio UDP JPEG sender required.
"""

import time
import cv2

from April_tag_detector import (
    IntellioCamera, AprilTagScanner, display_image,
    create_tobi, safe_say, show_window, read_key, close_windows
)

# ---------- CONFIGURATION ----------
AGE_GROUP = "ELEMENTARY"  # or "JUNIOR_SENIOR"
FAMILY = "16h5"
ELEMENTARY_ZONES = {1: "RESIDENTIAL", 2: "BUSINESS"}
RESIDENTIAL_PAIR = frozenset((1, 3))
BUSINESS_PAIR = frozenset((2, 4))
VALID_IDS = frozenset((1, 2, 3, 4))
WANTED = {(FAMILY, tag_id) for tag_id in VALID_IDS}

CONFIRM_FRAMES = 1  # Fast; change to 2 if misreads occur.
MEMORY_SECONDS = {"ELEMENTARY": 0.8, "JUNIOR_SENIOR": 4.0}
CAMERA_START_TIMEOUT = 12.0
IDLE_SLEEP = 0.005
WINDOW_NAME = "Challenge 6 | Q quit"

MOTOR_PORTS = ("L", "R")
MOTOR_SPEED = 100
MOTOR_SECONDS = 3.0
# Match these direction values to your installed Mini Expansion Board.
FORWARD_DIRECTION = "1"
BACKWARD_DIRECTION = "2"


def decide(recent_ids):
    if AGE_GROUP == "ELEMENTARY":
        present = recent_ids.intersection(ELEMENTARY_ZONES)
        if len(present) == 1:
            return ELEMENTARY_ZONES[next(iter(present))]
        return None

    residential = RESIDENTIAL_PAIR.issubset(recent_ids)
    business = BUSINESS_PAIR.issubset(recent_ids)
    if residential == business:
        return None
    return "RESIDENTIAL" if residential else "BUSINESS"


def connect_motor():
    factory = globals().get("QuarkyMiniExpansion")
    if factory is None:
        raise RuntimeError(
            "QuarkyMiniExpansion unavailable. Run inside PictoBlox Python "
            "Stage Mode with the Mini Expansion Board extension enabled."
        )
    board = factory()
    board.miniinitialise()
    return board


def stop_motors(board):
    for port in MOTOR_PORTS:
        board.stopmotor(port)



def move_for_decision(board, zone):
    """Move for up to 3 seconds. Q stops both motors early."""

    if zone == "RESIDENTIAL":
        direction = FORWARD_DIRECTION
        print("RESIDENTIAL -> FORWARD")

    elif zone == "BUSINESS":
        direction = BACKWARD_DIRECTION
        print("BUSINESS -> BACKWARD")

    else:
        return False

    try:
        board.runmotor("L", direction, MOTOR_SPEED)
        board.runmotor("R", direction, MOTOR_SPEED)

        end_time = time.monotonic() + MOTOR_SECONDS

        while time.monotonic() < end_time:

            key = read_key()

            if key in (ord("q"), ord("Q")):
                print("Q pressed! Stopping immediately.")
                return False

            time.sleep(0.01)

        print("3-second movement completed.")
        return True

    finally:
        stop_motors(board)
        print("Both motors stopped.")



def draw_dashboard(view, tags, variant, zone, recent_ids):
    preview = display_image(view, tags, variant)
    height, width = preview.shape[:2]
    label = (f"{zone} NEEDS POWER" if zone else "SCANNING - WAITING FOR TAGS")
    color = (35, 140, 45) if zone == "RESIDENTIAL" else (
        (175, 95, 25) if zone == "BUSINESS" else (75, 75, 75)
    )
    band_height = min(75, height)
    top = height - band_height
    cv2.rectangle(preview, (0, top), (width - 1, height - 1), color, -1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = min(0.75, max(0.3, width / max(1, len(label) * 19)))
    cv2.putText(preview, label, (8, top + min(31, band_height - 5)),
                font, scale, (255, 255, 255), 2, cv2.LINE_AA)
    if band_height >= 65:
        ids = ",".join(map(str, sorted(recent_ids))) or "none"
        info = f"{AGE_GROUP} | Confirmed IDs: {ids}"
        cv2.putText(preview, info, (8, height - 12), font, 0.43,
                    (255, 255, 255), 1, cv2.LINE_AA)
    return preview


def run_scan():
    if AGE_GROUP not in MEMORY_SECONDS:
        raise ValueError("AGE_GROUP must be ELEMENTARY or JUNIOR_SENIOR")
    if CONFIRM_FRAMES < 1:
        raise ValueError("CONFIRM_FRAMES must be >= 1")

    # Initialize the board independently of the camera.
    board = connect_motor()
    camera = None
    try:
        tobi = create_tobi(globals().get("Sprite"))
        scanner = AprilTagScanner(families=(FAMILY,))
        camera = IntellioCamera()

        streak = {tag_id: 0 for tag_id in VALID_IDS}
        last_seen = {}
        decision = None  # One-shot decision.
        last_sequence = 0
        started = time.monotonic()
        received_first_frame = False
        preview_data = None
        print(f"Challenge 6: {AGE_GROUP} | Residential forward, Business backward")

        while True:
            now = time.monotonic()
            frame, sequence = camera.read_new(last_sequence)
            if frame is not None:
                last_sequence = sequence
                received_first_frame = True
                tags, variant, view = scanner.scan(frame, wanted=WANTED)
                visible_ids = {tag["id"] for tag in tags
                               if (tag["family"], tag["id"]) in WANTED}
                for tag_id in VALID_IDS:
                    streak[tag_id] = streak[tag_id] + 1 if tag_id in visible_ids else 0
                    if streak[tag_id] >= CONFIRM_FRAMES:
                        last_seen[tag_id] = time.monotonic()
                preview_data = (view, tags, variant)
            elif not received_first_frame and now - started >= CAMERA_START_TIMEOUT:
                print("CAMERA TIMEOUT: check existing UDP JPEG sender on port 6000")
                break

            now = time.monotonic()
            memory_window = MEMORY_SECONDS[AGE_GROUP]
            last_seen = {tag_id: ts for tag_id, ts in last_seen.items()
                         if now - ts <= memory_window}
            recent_ids = set(last_seen)

            if decision is None:
                new_decision = decide(recent_ids)
                if new_decision is not None:
                    decision = new_decision
                    message = f"{decision.title()} needs power."
                    print("DECISION:", message)
                    # Display immediately before the blocking motor command.
                    if preview_data is not None:
                        view, tags, variant = preview_data
                        show_window(WINDOW_NAME, draw_dashboard(
                            view, tags, variant, decision, recent_ids))
                        read_key()
                     
                    # Announce the decision.
                    safe_say(tobi, message)

                    # Move for 3 seconds or stop early if Q is pressed.
                    completed = move_for_decision(board, decision)

                    if completed:
                        print("Challenge 6 completed.")
                    else:
                        print("Challenge 6 cancelled by Q.")

                    break


            if frame is not None and preview_data is not None:
                view, tags, variant = preview_data
                show_window(WINDOW_NAME, draw_dashboard(
                    view, tags, variant, decision, recent_ids))

            key = read_key()
            if key in (ord("q"), ord("Q")):
                break
            if frame is None:
                time.sleep(IDLE_SLEEP)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            stop_motors(board)
        finally:
            if camera is not None:
                camera.close()
            close_windows()
        print("Challenge 6 stopped")


if __name__ == "__main__":
    run_scan()
