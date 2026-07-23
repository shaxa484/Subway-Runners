import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import socket
import time

# --- UDP Setup ---
UDP_IP = "127.0.0.1"
UDP_PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# --- MediaPipe Tasks API Setup ---
MODEL_PATH = "pose_landmarker.task"  # path to the .task file you downloaded

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO,   # VIDEO mode = synchronous per-frame
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# --- Landmark indices (BlazePose 33-point model) ---
NOSE = 0
L_SHOULDER = 11
R_SHOULDER = 12
L_HIP = 23
R_HIP = 24

# --- State machine ---
current_state = "C"   # C=Center, L=Left, R=Right, J=Jump, D=Duck
last_state = "C"
last_jump_time = 0
last_duck_time = 0
baseline_body_height = 0.0
baseline_shoulder_y = 0.0  # <--- NEW: Tracks vertical starting position

# --- Manual landmark drawing (replaces mp.solutions.drawing_utils) ---
# Pairs of landmark indices to connect with lines (a subset of BlazePose)
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),   # arms
    (11, 23), (12, 24), (23, 24),                         # torso
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),    # left leg
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),    # right leg
    (0, 11), (0, 12),                                     # neck
]

def draw_landmarks(frame, landmarks, w, h):
    """Draw skeleton on the frame using OpenCV (replaces drawing_utils)."""
    # Draw connection lines
    for start_idx, end_idx in POSE_CONNECTIONS:
        if start_idx < len(landmarks) and end_idx < len(landmarks):
            p1 = landmarks[start_idx]
            p2 = landmarks[end_idx]
            cv2.line(frame,
                     (int(p1.x * w), int(p1.y * h)),
                     (int(p2.x * w), int(p2.y * h)),
                     (0, 255, 0), 2)
    # Draw landmark points
    for lm in landmarks:
        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 0, 255), -1)

# --- Open webcam ---
cap = cv2.VideoCapture(0)
print("Calibrating... Please stand straight in front of the camera for 2 seconds.")
start_time = time.time()
prev_timestamp_ms = 0

# --- Create the landmarker (use as a context manager so it cleans up) ---
with PoseLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Mirror for natural interaction
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Convert BGR -> RGB, then wrap in mp.Image for the Tasks API
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Timestamp must be monotonically increasing in milliseconds for VIDEO mode
        timestamp_ms = int(time.time() * 1000)
        if timestamp_ms <= prev_timestamp_ms:
            timestamp_ms = prev_timestamp_ms + 1
        prev_timestamp_ms = timestamp_ms

        # Run inference (synchronous in VIDEO mode)
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            landmarks = result.pose_landmarks[0]   # list of 33 NormalizedLandmark

            # Draw skeleton for debugging
            draw_landmarks(frame, landmarks, w, h)

            # Extract the landmarks we care about
            nose = landmarks[NOSE]
            l_shoulder = landmarks[L_SHOULDER]
            r_shoulder = landmarks[R_SHOULDER]
            l_hip = landmarks[L_HIP]
            r_hip = landmarks[R_HIP]

            shoulder_x = (l_shoulder.x + r_shoulder.x) / 2
            shoulder_y = (l_shoulder.y + r_shoulder.y) / 2
            hip_y = (l_hip.y + r_hip.y) / 2

            # --- Calibration (first 2 seconds) ---
            if time.time() - start_time < 2:
                # Establish the "ruler" (torso height)
                baseline_body_height = abs(shoulder_y - hip_y)
                # Establish the vertical starting position
                baseline_shoulder_y = shoulder_y # <--- NEW: Grab starting Y coordinate
                
                cv2.putText(frame, "CALIBRATING...", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                current_state = "C"

                # 1. Lane detection (shoulders left/right of center)
                if shoulder_x < 0.35:
                    current_state = "L"
                elif shoulder_x > 0.65:
                    current_state = "R"

                # --- NEW JUMP/DUCK LOGIC ---
                # Calculate a dynamic threshold based on the person's size
                # 25% of their torso height is a good threshold for jumps/ducks
                vertical_threshold = baseline_body_height * 0.15 

                # 2. Jump detection (Shoulders move UP from starting position)
                # Note: y decreases as you go UP the screen
                if shoulder_y < (baseline_shoulder_y - vertical_threshold) and time.time() - last_jump_time > 1:
                    current_state = "J"
                    last_jump_time = time.time()

                # 3. Duck detection (Shoulders move DOWN from starting position)
                # Note: y increases as you go DOWN the screen
                elif shoulder_y > (baseline_shoulder_y + vertical_threshold) and time.time() - last_duck_time > 1:
                    current_state = "D"
                    last_duck_time = time.time()

            # Send state over UDP when it changes
            if current_state != last_state:
                sock.sendto(current_state.encode("utf-8"), (UDP_IP, UDP_PORT))
                last_state = current_state

            # On-screen debug readout
            cv2.putText(frame, f"STATE: {current_state}", (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

        # Show the webcam feed (press 'q' to quit)
        cv2.imshow("Cardio Tracker", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
cv2.destroyAllWindows()
sock.close()