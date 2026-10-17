"""Codeavour Track 2 - Challenge 1: identify labelled organic / inorganic waste.
 
Run in PictoBlox Python Stage Mode for Tobi speech. Also runs in regular
Python for detection only. The Intellio UDP JPEG sender must already be
streaming to the local receiver on port 6000.
 
Needs April_tag_detector.py in the SAME folder. S saves images, Q quits.
"""
import os
import sys
import time
 
import cv2
 
# Make the sibling detector importable even when the working dir differs.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
except NameError:  # __file__ missing in some embedded runners
    pass
 
try:
    from April_tag_detector import (IntellioCamera, AprilTagScanner, display_image,
                                    save_images, create_tobi, safe_say,
                                    show_window, read_key, close_windows)
except ImportError as exc:
    raise SystemExit(f"Cannot import April_tag_detector.py ({exc}). "
                     "Keep both files in the same folder.")
 
ORGANIC_TAG = ("16h5", 6)
INORGANIC_TAG = ("16h5", 5)  # Verify against the physical marker
REQUIRED_MATCHING_FRAMES = 2
RESET_AFTER_MISSING_FRAMES = 3
CAMERA_START_TIMEOUT = 12.0
STREAM_LOST_SECONDS = 3.0
STATUS_INTERVAL = 1.0
NO_FRAME_SLEEP = 0.02
SPEECH_COOLDOWN = 1.0
 
LABELS = {ORGANIC_TAG: "ORGANIC WASTE", INORGANIC_TAG: "INORGANIC WASTE"}
 
 
def get_tobi():
    """Main PictoBlox script has the injected Sprite; look it up here."""
    return create_tobi(globals().get("Sprite"))
 
 
def classify(tags, image_width):
    """Pick the valid waste tag closest to the image centre.
 
    Unknown tags (or false positives) never hide a valid waste tag.
    """
    if not tags:
        return None, "NO TAG"
    known = [t for t in tags if (t["family"], t["id"]) in LABELS]
    pool = known or tags
    marker = min(pool, key=lambda tag: abs(tag["center"][0] - image_width / 2))
    identity = (marker["family"], marker["id"])
    return identity, LABELS.get(identity, "UNKNOWN TAG")
 
 
def announce_waste(tobi, category):
    message = {
        "ORGANIC WASTE": "It's organic waste.",
        "INORGANIC WASTE": "It's inorganic waste.",
    }.get(category)
    if message:
        print("ANNOUNCEMENT:", message)
        safe_say(tobi, message)
 
 
def draw_status(preview, category, frames):
    color = ((0, 255, 0) if category == "ORGANIC WASTE" else
             (0, 165, 255) if category == "INORGANIC WASTE" else
             (0, 255, 255))
    cv2.putText(preview, f"Waste: {category}", (12, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(preview, f"Confirmation: {min(frames, REQUIRED_MATCHING_FRAMES)}/{REQUIRED_MATCHING_FRAMES}",
                (12, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return preview
 
 
def run_scan():
    if ORGANIC_TAG == INORGANIC_TAG or REQUIRED_MATCHING_FRAMES < 1:
        raise ValueError("Invalid marker IDs or frame confirmation threshold")
 
    tobi = get_tobi()
    scanner = AprilTagScanner(families=tuple(sorted({ORGANIC_TAG[0], INORGANIC_TAG[0]})))
    try:
        camera = IntellioCamera()  # Owns UDP port 6000; don't run two programs at once.
    except RuntimeError as exc:
        print("ERROR:", exc)
        return
 
    wanted = set(LABELS)
    last_sequence = 0
    previous_identity = None
    consecutive = 0
    missing_frames = 0
    announced_identity = None
    last_speech_time = -float("inf")
    started = time.monotonic()
    camera_connected = False
    last_frame_time = started
    stream_lost_reported = False
    last_status = started
    last_raw = last_preview = None
    detection_count = 0
 
    print("Challenge 1: ID 6 = organic, ID 5 = inorganic. S = save, Q = quit")
    try:
        while True:
            now = time.monotonic()
            if not camera_connected and now - started >= CAMERA_START_TIMEOUT:
                print("CAMERA TIMEOUT: no complete JPEG frames. Start/check the existing UDP sender at 127.0.0.1:6000.")
                break
 
            frame, sequence = camera.read_new(last_sequence)
            if frame is None:
                if camera_connected and now - last_frame_time > STREAM_LOST_SECONDS:
                    if not stream_lost_reported:
                        print("Stream lost - waiting for frames...")
                        stream_lost_reported = True
                    # Allow re-announcement once the stream returns.
                    announced_identity = None
                    previous_identity = None
                    consecutive = 0
                key = read_key()
                if key in (ord("q"), ord("Q")):
                    break
                if key in (ord("s"), ord("S")) and last_raw is not None:
                    save_images(last_raw, last_preview)
                time.sleep(NO_FRAME_SLEEP)
                continue
 
            last_sequence = sequence
            last_frame_time = now
            if stream_lost_reported:
                print("Stream restored.")
                stream_lost_reported = False
            if not camera_connected:
                camera_connected = True
                print("Camera connected. Scanning...")
 
            tags, variant, view = scanner.scan(frame, wanted=wanted)
            identity, category = classify(tags, view.shape[1])
            known = category in ("ORGANIC WASTE", "INORGANIC WASTE")
 
            if known:
                missing_frames = 0
                consecutive = consecutive + 1 if identity == previous_identity else 1
                previous_identity = identity
            else:
                previous_identity = None
                consecutive = 0
                missing_frames += 1
                if missing_frames >= RESET_AFTER_MISSING_FRAMES:
                    announced_identity = None
 
            last_raw = frame
            last_preview = draw_status(display_image(view, tags, variant), category, consecutive)
            show_window("Challenge 1 | S Save | Q Quit", last_preview)
 
            now = time.monotonic()
            if now - last_status >= STATUS_INTERVAL:
                print(f"Frame {sequence}: {identity or 'NO TAG'} -> {category} "
                      f"({min(consecutive, REQUIRED_MATCHING_FRAMES)}/{REQUIRED_MATCHING_FRAMES})")
                last_status = now
 
            # Don't re-announce a stationary tag; a cooldown-postponed
            # announcement is still made once the cooldown ends.
            if (known and consecutive >= REQUIRED_MATCHING_FRAMES
                    and identity != announced_identity
                    and now - last_speech_time >= SPEECH_COOLDOWN):
                print(f"CONFIRMED: {identity} -> {category}")
                announce_waste(tobi, category)
                announced_identity = identity
                last_speech_time = time.monotonic()
                detection_count += 1
 
            key = read_key()
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("s"), ord("S")) and last_raw is not None:
                save_images(last_raw, last_preview)
    except KeyboardInterrupt:
        pass
    finally:
        camera.close()
        close_windows()
        print(f"Scanning stopped. Confirmed recognition events: {detection_count}")
 
 
if __name__ == "__main__":
    run_scan()