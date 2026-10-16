"""Codeavour Track 2 — Challenge 1 waste identification.

Uses the generic `april_tag_detector.py` module to read the Intellio camera.
This file alone maps AprilTag identities to waste categories.

 

Runs in PictoBlox Python Stage Mode on the COMPUTER (not standalone robot).
Requires the existing Intellio UDP JPEG sender to be active.
Keys: S = save frames, Q = cancel.
"""
import time

import cv2

from april_tag_detector import (
    IntellioCamera,
    AprilTagScanner,
    display_image,
    save_images,
    tobi,
)

# -------- CHALLENGE 1 SETTINGS --------
ORGANIC_TAG = ("16h5", 6)           # Verified using your Intellio camera
INORGANIC_TAG = ("16h5", 5)                # Set to ("16h5", <measured_id>) later
REQUIRED_MATCHING_FRAMES = 2
CAMERA_START_TIMEOUT = 12.0        # Seconds waiting for the first camera frame
SCAN_TIMEOUT = 5.0                 # Seconds after the first camera frame
NO_FRAME_SLEEP = 0.02
STATUS_INTERVAL = 1.0


def classify(tags, image_width):
    """Return ((family, id), category) for the marker nearest image center.

    Unrecognized IDs are UNKNOWN, never assumed to be inorganic.
    """
    if not tags:
        return None, "NO TAG"

    marker = min(tags, key=lambda tag: abs(tag["center"][0] - image_width / 2))
    identity = (marker["family"], marker["id"])

    if identity == ORGANIC_TAG:
        return identity, "ORGANIC WASTE"
    if INORGANIC_TAG is not None and identity == INORGANIC_TAG:
        return identity, "INORGANIC WASTE"
    return identity, "UNKNOWN TAG"


def run_scan():
    """Read fresh camera frames until a known category is confirmed or timed out.

    Returns one of: ORGANIC WASTE, INORGANIC WASTE, NO CONFIRMED TAG,
    CAMERA TIMEOUT, CANCELLED.
    """
    if INORGANIC_TAG is not None and INORGANIC_TAG == ORGANIC_TAG:
        raise ValueError("Organic and inorganic marker IDs must differ")
    if REQUIRED_MATCHING_FRAMES < 1:
        raise ValueError("REQUIRED_MATCHING_FRAMES must be at least 1")

    families = (ORGANIC_TAG[0],) if INORGANIC_TAG is None else tuple(
        sorted({ORGANIC_TAG[0], INORGANIC_TAG[0]})
    )
    scanner = AprilTagScanner(families=families)
    camera = IntellioCamera()  # Run only one UDP receiver on port 6000.

    last_sequence = 0
    previous_identity = None
    consecutive = 0
    connected_at = time.monotonic()
    scan_started = None
    last_status = 0.0
    outcome = "NO CONFIRMED TAG"
    last_raw = None
    last_preview = None

    print("Challenge 1: waiting for Intellio camera frames...")
    try:
        while True:
            now = time.monotonic()
            if scan_started is None and now - connected_at >= CAMERA_START_TIMEOUT:
                outcome = "CAMERA TIMEOUT"
                print("Camera timeout: check the Intellio UDP sender and port.")
                break
            if scan_started is not None and now - scan_started >= SCAN_TIMEOUT:
                print("Scan timeout: no confirmed known waste marker.")
                break

            frame, sequence = camera.read_new(last_sequence)
            if frame is None:
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    outcome = "CANCELLED"
                    break
                time.sleep(NO_FRAME_SLEEP)
                continue

            last_sequence = sequence
            if scan_started is None:
                scan_started = time.monotonic()
                print("Camera connected. Scanning AprilTag...")

            # Keep the proven mirrored-first + fallback pipeline in the scanner.
            tags, variant, view = scanner.scan(frame)
            identity, label = classify(tags, view.shape[1])

            if label in ("ORGANIC WASTE", "INORGANIC WASTE"):
                consecutive = consecutive + 1 if identity == previous_identity else 1
                previous_identity = identity
            else:
                consecutive = 0
                previous_identity = None

            last_raw = frame
            last_preview = display_image(view, tags, variant)
            cv2.putText(last_preview, f"Waste: {label}", (12, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("Challenge 1 | S save | Q quit", last_preview)

            if time.monotonic() - last_status >= STATUS_INTERVAL:
                if identity is None:
                    print("No AprilTag visible")
                else:
                    print(f"Seen {identity[0]} ID:{identity[1]} -> {label} "
                          f"({consecutive}/{REQUIRED_MATCHING_FRAMES} frames)")
                last_status = time.monotonic()

            # Tobi comes from PictoBlox, created in the generic detector module.
            # It should report category only in this challenge-specific program.
            if consecutive >= REQUIRED_MATCHING_FRAMES:
                outcome = label
                print(f"CONFIRMED: {identity[0]} ID:{identity[1]} = {outcome}")
                tobi.say(f"AprilTag ID {identity[1]}: {outcome}")
                break

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                outcome = "CANCELLED"
                break
            if key == ord("s") and last_raw is not None:
                save_images(last_raw, last_preview)

        print("Final result:", outcome)
        return outcome
    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_scan()
