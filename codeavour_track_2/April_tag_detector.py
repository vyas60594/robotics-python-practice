 """Generic Intellio AprilTag detector for PictoBlox Python Stage Mode.

Receives JPEG frames from an ALREADY RUNNING Intellio UDP sender using:
    b'SIZE:<N>' datagram followed by ordered JPEG payload datagrams.
Detects tag family, numeric ID, center, and corners; displays them via
OpenCV and Tobi speech. Does not classify tags or control robot hardware.

Runs on the COMPUTER, not as standalone Intellio firmware.
Keys: S = save raw + annotated images, Q = quit.
"""
import socket
import threading
import time
from pathlib import Path

import cv2
import numpy as np

# PictoBlox injects Sprite in Python Stage Mode. This is not standard Python.
tobi = Sprite("Tobi")

# ---------- CONFIGURATION ----------
HOST = "127.0.0.1"  # Keep this if your working sender uses localhost:6000.
PORT = 6000
FAMILIES = ("16h5",)  # Verified for your current tags; expand when required.
START_TIMEOUT = 12.0
STALE_SECONDS = 2.0
TRANSFER_TIMEOUT = 1.0
MAX_JPEG_BYTES = 2_000_000
STATUS_INTERVAL = 3.0
SAVE_DIR = Path("intellio_diagnostics")

FAMILY_CONSTANTS = {
    "16h5": "DICT_APRILTAG_16h5",
    "25h9": "DICT_APRILTAG_25h9",
    "36h11": "DICT_APRILTAG_36h11",
}


class IntellioCamera:
    """Receive decoded JPEG frames from the existing Intellio UDP sender."""

    def __init__(self, host=HOST, port=PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.25)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.frame = None
        self.frame_time = 0.0
        self.sequence = 0
        self.worker = threading.Thread(target=self._receive, daemon=True)
        self.worker.start()
        print(f"Listening for Intellio JPEG stream at {host}:{port}")

    def _receive(self):
        expected = 0
        buffer = bytearray()
        transfer_start = 0.0
        sender = None
        while not self.stop_event.is_set():
            try:
                packet, source = self.sock.recvfrom(65535)
            except socket.timeout:
                if expected and time.monotonic() - transfer_start > TRANSFER_TIMEOUT:
                    expected = 0
                    buffer.clear()
                    sender = None
                continue
            except OSError:
                break

            now = time.monotonic()
            if packet.startswith(b"SIZE:"):
                try:
                    amount = int(packet[5:].strip())
                except ValueError:
                    amount = 0
                expected = amount if 0 < amount <= MAX_JPEG_BYTES else 0
                buffer.clear()
                transfer_start = now
                sender = source if expected else None
                continue

            if not expected or source != sender:
                continue
            if now - transfer_start > TRANSFER_TIMEOUT or len(buffer) + len(packet) > expected:
                expected = 0
                buffer.clear()
                sender = None
                continue

            buffer.extend(packet)
            if len(buffer) == expected:
                image = cv2.imdecode(np.frombuffer(bytes(buffer), dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is not None:
                    with self.lock:
                        self.frame = image
                        self.frame_time = now
                        self.sequence += 1
                expected = 0
                buffer.clear()
                sender = None

    def read_new(self, last_sequence):
        """Return (new BGR frame, sequence) or (None, last_sequence)."""
        with self.lock:
            if (self.frame is None or self.sequence == last_sequence or
                    time.monotonic() - self.frame_time > STALE_SECONDS):
                return None, last_sequence
            return self.frame.copy(), self.sequence

    def close(self):
        self.stop_event.set()
        self.sock.close()
        self.worker.join(timeout=1.0)


class AprilTagScanner:
    """Detect tags using mirrored-first, then normal and contrast fallbacks."""

    def __init__(self, families=FAMILIES):
        if not hasattr(cv2, "aruco") or not hasattr(cv2.aruco, "ArucoDetector"):
            raise RuntimeError("Install opencv-contrib-python with ArucoDetector support")
        self.detectors = {}
        for family in families:
            if family not in FAMILY_CONSTANTS:
                raise ValueError(f"Unsupported AprilTag family: {family}")
            constant = getattr(cv2.aruco, FAMILY_CONSTANTS[family])
            dictionary = cv2.aruco.getPredefinedDictionary(constant)
            params = cv2.aruco.DetectorParameters()
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            params.minMarkerPerimeterRate = 0.01
            self.detectors[family] = cv2.aruco.ArucoDetector(dictionary, params)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def views(self, raw):
        """Preserve proven detection order; build enhanced views only if needed."""
        yield "mirrored", cv2.flip(raw, 1)
        yield "normal", raw
        gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.cvtColor(self.clahe.apply(gray), cv2.COLOR_GRAY2BGR)
        yield "mirrored_enhanced", cv2.flip(enhanced, 1)
        yield "enhanced", enhanced

    def scan(self, raw):
        """Return (tags, view_name, view).

        Each tag is {family, id, center, corners}. All tags in the first
        successful view are returned. Coordinates refer to returned view.
        """
        first_view = None
        for variant, view in self.views(raw):
            if first_view is None:
                first_view = view
            gray = cv2.cvtColor(view, cv2.COLOR_BGR2GRAY)
            found = []
            for family, detector in self.detectors.items():
                corners_list, ids, _ = detector.detectMarkers(gray)
                if ids is None:
                    continue
                for tag_id, corners in zip(ids.flatten(), corners_list):
                    points = corners.reshape(4, 2).astype(np.int32)
                    center = tuple(points.mean(axis=0).astype(int))
                    found.append({
                        "family": family,
                        "id": int(tag_id),
                        "center": center,
                        "corners": points,
                    })
            if found:
                return found, variant, view
        return [], "mirrored", first_view


def display_image(view, tags, variant):
    """Draw tag boundary, ID, and family without category classification."""
    result = view.copy()
    for tag in tags:
        cv2.polylines(result, [tag["corners"]], True, (0, 255, 0), 2)
        x, y = tag["center"]
        cv2.putText(result, f'{tag["family"]} ID:{tag["id"]}',
                    (max(0, x - 60), max(45, y - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    cv2.putText(result, f"View: {variant} | Tags: {len(tags)}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    return result


def make_message(tags):
    """Make a generic Tobi message from every unique (family, ID)."""
    if not tags:
        return "No AprilTag Detected"
    identities = sorted({(tag["family"], tag["id"]) for tag in tags})
    if len(identities) == 1:
        family, tag_id = identities[0]
        return f"AprilTag Detected! ID: {tag_id} ({family})"
    details = ", ".join(f"{family}:{tag_id}" for family, tag_id in identities)
    return f"AprilTags Detected! {details}"


def save_images(raw, shown):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for suffix, image in (("raw", raw), ("detected", shown)):
        path = SAVE_DIR / f"{stamp}_{suffix}.jpg"
        if cv2.imwrite(str(path), image):
            print("Saved:", path.resolve())
        else:
            print("Could not save:", path.resolve())


def run():
    scanner = AprilTagScanner()
    camera = IntellioCamera()
    last_sequence = 0
    camera_connected = False
    started = time.monotonic()
    last_status = started
    last_ids = None
    latest_raw = None
    latest_preview = None

    tobi.say("Waiting for Intellio camera...")
    try:
        while True:
            frame, sequence = camera.read_new(last_sequence)
            now = time.monotonic()
            if frame is not None:
                last_sequence = sequence
                if not camera_connected:
                    print("Live Intellio frames received")
                    camera_connected = True
                tags, variant, view = scanner.scan(frame)
                ids = frozenset((tag["family"], tag["id"]) for tag in tags)

                if ids != last_ids:
                    message = make_message(tags)
                    tobi.say(message)
                    print(message)
                    last_ids = ids

                if now - last_status >= STATUS_INTERVAL:
                    print(f"Frame #{sequence} | {frame.shape[1]}x{frame.shape[0]} | tags={len(tags)}")
                    last_status = now

                latest_raw = frame
                latest_preview = display_image(view, tags, variant)
                cv2.imshow("Intellio AprilTags | S save | Q quit", latest_preview)
            else:
                if not camera_connected and now - started > START_TIMEOUT:
                    raise RuntimeError("No camera frames. Check UDP sender, host and port.")
                if camera_connected and now - last_status >= STATUS_INTERVAL:
                    print("No new frames recently; check stream")
                    last_status = now
                time.sleep(0.02)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s") and latest_raw is not None:
                save_images(latest_raw, latest_preview)
    finally:
        camera.close()
        cv2.destroyAllWindows()
        tobi.say("")


if __name__ == "__main__":
    run()
