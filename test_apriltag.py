
import cv2

aruco = cv2.aruco

families = {
    "16h5": aruco.DICT_APRILTAG_16h5,
    "25h9": aruco.DICT_APRILTAG_25h9,
    "36h11": aruco.DICT_APRILTAG_36h11
}

detectors = {}

for name, dictionary_id in families.items():
    dictionary = aruco.getPredefinedDictionary(dictionary_id)
    detectors[name] = aruco.ArucoDetector(dictionary)

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    raise RuntimeError("Camera not found")

print("AprilTag detector started. Press Q to exit.")

while True:
    success, frame = cap.read()

    if not success:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    for family, detector in detectors.items():
        corners, ids, rejected = detector.detectMarkers(gray)

        if ids is not None:
            for tag_id in ids.flatten():
                print(f"Detected: {family}, ID: {tag_id}")

            aruco.drawDetectedMarkers(frame, corners, ids)

    cv2.imshow("AprilTag Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
