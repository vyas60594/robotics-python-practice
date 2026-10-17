"""Generic Intellio AprilTag detector for PictoBlox Python Stage Mode.
 
Receives JPEG frames from an ALREADY RUNNING Intellio UDP sender using:
    b'SIZE:<N>' datagram followed by ordered JPEG payload datagrams.
Detects tag family, numeric ID, center, and corners; displays them via
OpenCV and Tobi speech. Does not control robot hardware.
 
Can be run directly (generic detector) or imported by challenge scripts.
Keys: S = save raw + annotated images, Q = quit.
"""
import socket
import threading
import time
from pathlib import Path
 
import cv2
import numpy as np
 
# ---------- CONFIGURATION ----------
HOST = "127.0.0.1"   # Use "0.0.0.0" if the sender is on another device.
PORT = 6000
FAMILIES = ("16h5",)  # Add "36h11" / "25h9" here if your tags change.
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
 
 
# ---------- TOBI / GUI HELPERS (safe outside PictoBlox) ----------
def create_tobi(sprite_class=None):
    """Create the Tobi sprite if PictoBlox's Sprite exists; otherwise None."""
    if sprite_class is None:
        sprite_class = globals().get("Sprite")
    if sprite_class is None:
        try:
            import builtins
            sprite_class = getattr(builtins, "Sprite", None)
        except Exception:
            sprite_class = None
    if sprite_class is None:
        print("WARNING: Sprite unavailable (not Stage Mode). Tobi speech disabled.")
        return None
    try:
        return sprite_class("Tobi")
    except Exception as exc:
        print(f"WARNING: Could not initialize Tobi: {exc}. Speech disabled.")
        return None
 
 
def safe_say(tobi, text):
    if tobi is None:
        return
    try:
        tobi.say(text)
    except Exception as exc:
        print(f"WARNING: Tobi speech failed: {exc}")
 
 
_gui_ok = True
 
 
def show_window(title, image):
    """imshow that degrades gracefully on headless OpenCV builds."""
    global _gui_ok
    if not _gui_ok or image is None:
        return
    try:
        cv2.imshow(title, image)
    except cv2.error as exc:
        _gui_ok = False
        print(f"WARNING: No display available ({exc}). Running without window.")
 
 
def read_key():
    """Return pressed key code (lowercase-safe) or -1. Always yields CPU."""
    global _gui_ok
    if not _gui_ok:
        time.sleep(0.01)
        return -1
    try:
        return cv2.waitKey(1) & 0xFF
    except cv2.error:
        _gui_ok = False
        return -1
 
 
def close_windows():
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass
 
 
# ---------- CAMERA ----------
class IntellioCamera:
    """Receive decoded JPEG frames from the existing Intellio UDP sender."""
 
    def __init__(self, host=HOST, port=PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        except OSError:
            pass
        try:
            self.sock.bind((host, port))
        except OSError as exc:
            self.sock.close()
            raise RuntimeError(
                f"Cannot bind {host}:{port} ({exc}). Another script is probably "
                "using this port - stop it (or the previous run) and try again."
            ) from exc
        self.sock.settimeout(0.25)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.frame = None
        self.frame_time = 0.0
        self.sequence = 0
        self.worker = threading.Thread(target=self._receive, daemon=True)
        self.worker.start()
        print(f"Listening for Intellio JPEG stream at {host}:{port}")
 
    def _publish(self, data, now):
        image = cv2.imdecode(np.frombuffer(bytes(data), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is not None:
            with self.lock:
                self.frame = image
                self.frame_time = now
                self.sequence += 1
 
    def _receive(self):
        expected = 0
        buffer = bytearray()
        transfer_start = 0.0
        sender_ip = None
        while not self.stop_event.is_set():
            try:
                packet, source = self.sock.recvfrom(65535)
            except socket.timeout:
                if expected and time.monotonic() - transfer_start > TRANSFER_TIMEOUT:
                    expected = 0
                    buffer.clear()
                    sender_ip = None
                continue
            except ConnectionResetError:
                continue  # Windows: ICMP "port unreachable" must not kill the thread
            except OSError:
                if self.stop_event.is_set():
                    break
                time.sleep(0.01)
                continue
 
            now = time.monotonic()
            if packet.startswith(b"SIZE:"):
                try:
                    amount = int(packet[5:].strip())
                except ValueError:
                    amount = 0
                expected = amount if 0 < amount <= MAX_JPEG_BYTES else 0
                buffer.clear()
                transfer_start = now
                sender_ip = source[0] if expected else None
                continue
 
            if not expected:
                # Fallback: a complete JPEG sent in one datagram without header.
                if packet[:2] == b"\xff\xd8" and packet[-2:] == b"\xff\xd9":
                    self._publish(packet, now)
                continue
            if source[0] != sender_ip:
                continue
            if now - transfer_start > TRANSFER_TIMEOUT or len(buffer) + len(packet) > expected:
                expected = 0
                buffer.clear()
                sender_ip = None
                continue
 
            buffer.extend(packet)
            if len(buffer) == expected:
                self._publish(buffer, now)
                expected = 0
                buffer.clear()
                sender_ip = None
 
    def read_new(self, last_sequence):
        """Return (new BGR frame, sequence) or (None, last_sequence)."""
        with self.lock:
            if (self.frame is None or self.sequence == last_sequence or
                    time.monotonic() - self.frame_time > STALE_SECONDS):
                return None, last_sequence
            return self.frame.copy(), self.sequence
 
    def close(self):
        self.stop_event.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self.worker.join(timeout=1.0)
 
 
# ---------- DETECTION ----------
class AprilTagScanner:
    """Detect tags using mirrored-first, then normal and contrast fallbacks.
 
    Works with both the new (OpenCV >= 4.7) and old (4.1-4.6) aruco APIs.
    """
 
    def __init__(self, families=FAMILIES):
        if not hasattr(cv2, "aruco"):
            raise RuntimeError("Install opencv-contrib-python (cv2.aruco missing)")
        aruco = cv2.aruco
        self.new_api = hasattr(aruco, "ArucoDetector")
        self.detectors = {}
        for family in families:
            if family not in FAMILY_CONSTANTS:
                raise ValueError(f"Unsupported AprilTag family: {family}")
            constant_name = FAMILY_CONSTANTS[family]
            if not hasattr(aruco, constant_name):
                raise RuntimeError(f"This OpenCV build lacks {constant_name}")
            dictionary = aruco.getPredefinedDictionary(getattr(aruco, constant_name))
            params = (aruco.DetectorParameters() if self.new_api
                      else aruco.DetectorParameters_create())
            params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
            params.minMarkerPerimeterRate = 0.01
            if self.new_api:
                self.detectors[family] = aruco.ArucoDetector(dictionary, params)
            else:
                self.detectors[family] = (dictionary, params)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
 
    def views(self, raw):
        """Preserve proven detection order; build enhanced views only if needed."""
        yield "mirrored", cv2.flip(raw, 1)
        yield "normal", raw
        gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.cvtColor(self.clahe.apply(gray), cv2.COLOR_GRAY2BGR)
        yield "mirrored_enhanced", cv2.flip(enhanced, 1)
        yield "enhanced", enhanced
 
    def _detect(self, view):
        gray = cv2.cvtColor(view, cv2.COLOR_BGR2GRAY)
        found = []
        for family, detector in self.detectors.items():
            try:
                if self.new_api:
                    corners_list, ids, _ = detector.detectMarkers(gray)
                else:
                    dictionary, params = detector
                    corners_list, ids, _ = cv2.aruco.detectMarkers(
                        gray, dictionary, parameters=params)
            except cv2.error:
                continue
            if ids is None:
                continue
            for tag_id, corners in zip(ids.flatten(), corners_list):
                points = corners.reshape(4, 2).astype(np.int32)
                center = tuple(int(v) for v in points.mean(axis=0))
                found.append({
                    "family": family,
                    "id": int(tag_id),
                    "center": center,
                    "corners": points,
                })
        return found
 
    def scan(self, raw, wanted=None):
        """Return (tags, view_name, view).
 
        Each tag is {family, id, center, corners}; coordinates refer to the
        returned view. If `wanted` (set of (family, id)) is given, views are
        tried until one contains a wanted tag, so a false positive in an
        early view cannot hide a real tag in a later one. If no view has a
        wanted tag, the first view with any detection is returned.
        """
        first = None
        fallback = None
        for variant, view in self.views(raw):
            if first is None:
                first = (variant, view)
            found = self._detect(view)
            if not found:
                continue
            if wanted is None or any((t["family"], t["id"]) in wanted for t in found):
                return found, variant, view
            if fallback is None:
                fallback = (found, variant, view)
        if fallback is not None:
            return fallback
        return [], first[0], first[1]
 
 
def display_image(view, tags, variant):
    """Draw tag boundary, ID, and family without category classification."""
    result = view.copy()
    for tag in tags:
        cv2.polylines(result, [tag["corners"]], True, (0, 255, 0), 2)
        x, y = tag["center"]
        cv2.circle(result, (x, y), 4, (0, 0, 255), -1)
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
    if raw is None:
        return
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print("Could not create save folder:", exc)
        return
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for suffix, image in (("raw", raw), ("detected", shown)):
        if image is None:
            continue
        path = SAVE_DIR / f"{stamp}_{suffix}.jpg"
        if cv2.imwrite(str(path), image):
            print("Saved:", path.resolve())
        else:
            print("Could not save:", path.resolve())
 
 
def run():
    tobi = create_tobi()
    scanner = AprilTagScanner()
    camera = IntellioCamera()
    last_sequence = 0
    camera_connected = False
    started = time.monotonic()
    last_status = started
    last_ids = None
    latest_raw = None
    latest_preview = None
 
    safe_say(tobi, "Waiting for Intellio camera...")
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
                    safe_say(tobi, message)
                    print(message)
                    last_ids = ids
 
                if now - last_status >= STATUS_INTERVAL:
                    print(f"Frame #{sequence} | {frame.shape[1]}x{frame.shape[0]} | tags={len(tags)}")
                    last_status = now
 
                latest_raw = frame
                latest_preview = display_image(view, tags, variant)
                show_window("Intellio AprilTags | S save | Q quit", latest_preview)
            else:
                if not camera_connected and now - started > START_TIMEOUT:
                    print("No camera frames. Check UDP sender, host and port.")
                    break
                if camera_connected and now - last_status >= STATUS_INTERVAL:
                    print("No new frames recently; check stream")
                    last_status = now
                time.sleep(0.02)
 
            key = read_key()
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("s"), ord("S")) and latest_raw is not None:
                save_images(latest_raw, latest_preview)
    except KeyboardInterrupt:
        pass
    finally:
        camera.close()
        close_windows()
        safe_say(tobi, "")
 
 
if __name__ == "__main__":
    run()
 