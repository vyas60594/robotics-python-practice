"""Codeavour Track 2 - Challenge 1: identify a waste AprilTag.

Uses the VERIFIED Intellio UDP camera scanner in intellio_apriltag_scanner.py.
Runs in computer-side Python/PictoBlox Stage Mode (not standalone robot firmware).

Keys: Q = quit, S = save raw & annotated images.
"""
import time
from pathlib import Path

import cv2

from April_tag_detector import (
    IntellioCamera,
    AprilTagScanner,
    annotate,
    save_images
)
ORGANIC_TAG = ("16h5", 6)
# IMPORTANT: Set only after independently scanning the Inorganic marker.
# Example format: ("16h5", 12). Do NOT assume its ID is 5.
INORGANIC_TAG = None

# Two fresh camera frames are required for a confirmed classification.
REQUIRED_MATCHING_FRAMES = 2
SCAN_TIMEOUT_SECONDS = 5.0      # Starts after the first valid camera frame
CAMERA_START_TIMEOUT = 12.0     # Max time to wait for the first valid frame
REPORT_INTERVAL_SECONDS = 1.0


def classify(tags, image_width):
    """Return ((family, id), label) for the known tag closest to center.

    Unknown detected tags are reported but never classified as Inorganic.
    """
    if not tags:
        return None, "NO TAG"

    # Center position belongs to the view returned by AprilTagScanner.scan().
    nearest = min(tags, key=lambda t: abs(t["center"][0] - image_width / 2))
    identity = (nearest["family"], nearest["id"])
    if identity == ORGANIC_TAG:
        return identity, "ORGANIC WASTE"
    if INORGANIC_TAG is not None and identity == INORGANIC_TAG:
        return identity, "INORGANIC WASTE"
    return identity, "UNKNOWN TAG"


def run_scan():
    if INORGANIC_TAG is not None and INORGANIC_TAG == ORGANIC_TAG:
        raise ValueError("Organic and Inorganic markers must have different identities")
    if REQUIRED_MATCHING_FRAMES < 1:
        raise ValueError("REQUIRED_MATCHING_FRAMES must be >= 1")

    scanner = AprilTagScanner(families=("16h5",))
    camera = IntellioCamera()  # Ensure no other script is listening on the same UDP port!

    previous_identity = None
    streak = 0
    last_sequence = 0
    connected_at = time.monotonic()
    scan_started = None
    last_report = 0.0
    outcome = "NO CONFIRMED TAG"
    latest_raw = None
    latest_display = None

    try:
        while True:
            now = time.monotonic()
            frame, sequence = camera.read_new(last_sequence)
            if frame is None:
                if scan_started is None and now - connected_at > CAMERA_START_TIMEOUT:
                    outcome = "CAMERA TIMEOUT"
                    print("No valid Intellio frames. Confirm stream sender, host and port.")
                    break
                if scan_started is not None and now - scan_started >= SCAN_TIMEOUT_SECONDS:
                    print("No confirmed waste marker before timeout.")
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    outcome = "CANCELLED"
                    break
                time.sleep(0.02)
                continue

            last_sequence = sequence
            if scan_started is None:
                scan_started = time.monotonic()
                print("Intellio camera connected. Scanning Challenge 1 marker...")

            tags, variant, view, _diagnostics = scanner.scan(frame)
            identity, label = classify(tags, view.shape[1])

            if label in ("ORGANIC WASTE", "INORGANIC WASTE"):
                if identity == previous_identity:
                    streak += 1
                else:
                    streak = 1
                previous_identity = identity
            else:
                previous_identity = None
                streak = 0

            latest_raw = frame
            latest_display = annotate(view, tags, variant)
            cv2.putText(latest_display, f"Waste: {label}", (12, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
            cv2.imshow("Challenge 1 | S save | Q quit", latest_display)

            if time.monotonic() - last_report >= REPORT_INTERVAL_SECONDS:
                if identity is not None:
                    print(f"Seen family={identity[0]}, id={identity[1]} -> {label} "
                          f"(confirmed frames: {streak}/{REQUIRED_MATCHING_FRAMES})")
                else:
                    print("No AprilTag visible")
                last_report = time.monotonic()

            if streak >= REQUIRED_MATCHING_FRAMES:
                outcome = label
                print(f"CONFIRMED | family={identity[0]} | id={identity[1]} | {outcome}")
                break

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                outcome = "CANCELLED"
                break
            if key == ord("s") and latest_raw is not None:
                save_images(latest_raw, latest_display)
            if time.monotonic() - scan_started >= SCAN_TIMEOUT_SECONDS:
                print("No confirmed waste marker before timeout.")
                break

        print("Final result:", outcome)
        return outcome
    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_scan()
