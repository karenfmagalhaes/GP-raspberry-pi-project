# vision/hand_tracker.py
# Detects one hand using MediaPipe Hands and draws hand landmarks.

import cv2
import mediapipe as mp


class HandTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils

        # model_complexity=0 is lighter and better for Raspberry Pi performance.
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )

    def process(self, frame):
        # Camera frames are BGR because camera/capture.py uses BGR888.
        # MediaPipe needs RGB, so we convert here.
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Improves performance because MediaPipe does not need to modify the image.
        rgb_frame.flags.writeable = False
        results = self.hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        return results

    def draw_landmarks(self, frame, hand_landmarks):
        self.mp_draw.draw_landmarks(
            frame,
            hand_landmarks,
            self.mp_hands.HAND_CONNECTIONS
        )

    def close(self):
        self.hands.close()
