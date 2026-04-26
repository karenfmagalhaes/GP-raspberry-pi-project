# vision/gesture_classifier.py
# Classifies hand gestures from MediaPipe hand landmarks.
# This version makes fist detection easier and more stable.

class GestureClassifier:
    def __init__(self):
        # Small tolerance helps avoid shaky landmark detection.
        self.tolerance = 0.03

    def finger_is_up(self, landmarks, tip_index, pip_index):
        # In image coordinates, smaller y means higher on screen.
        return landmarks[tip_index].y < landmarks[pip_index].y - self.tolerance

    def finger_is_down(self, landmarks, tip_index, pip_index):
        return landmarks[tip_index].y > landmarks[pip_index].y + self.tolerance

    def classify(self, hand_landmarks):
        landmarks = hand_landmarks.landmark

        # Finger indexes:
        # Index:  tip 8,  pip 6
        # Middle: tip 12, pip 10
        # Ring:   tip 16, pip 14
        # Pinky:  tip 20, pip 18

        index_up = self.finger_is_up(landmarks, 8, 6)
        middle_up = self.finger_is_up(landmarks, 12, 10)
        ring_up = self.finger_is_up(landmarks, 16, 14)
        pinky_up = self.finger_is_up(landmarks, 20, 18)

        index_down = self.finger_is_down(landmarks, 8, 6)
        middle_down = self.finger_is_down(landmarks, 12, 10)
        ring_down = self.finger_is_down(landmarks, 16, 14)
        pinky_down = self.finger_is_down(landmarks, 20, 18)

        fingers_up = [index_up, middle_up, ring_up, pinky_up]
        fingers_down = [index_down, middle_down, ring_down, pinky_down]

        total_up = sum(fingers_up)
        total_down = sum(fingers_down)

        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        wrist = landmarks[0]

        thumb_up = (
            thumb_tip.y < thumb_ip.y - self.tolerance and
            thumb_ip.y < thumb_mcp.y - self.tolerance and
            thumb_tip.y < wrist.y
        )

        thumb_down = (
            thumb_tip.y > thumb_ip.y + self.tolerance and
            thumb_ip.y > thumb_mcp.y + self.tolerance and
            thumb_tip.y > wrist.y
        )

        # Thumbs up/down need most other fingers down.
        # We accept 3 out of 4 fingers down because the camera may miss one finger.
        if thumb_up and total_down >= 3:
            return "thumbs_up"

        if thumb_down and total_down >= 3:
            return "thumbs_down"

        # Peace: index and middle up, ring and pinky down.
        if index_up and middle_up and ring_down and pinky_down:
            return "peace"

        # Three fingers: index, middle, and ring up, pinky down.
        if index_up and middle_up and ring_up and pinky_down:
            return "three_fingers"

        # Open palm: all four main fingers up.
        if total_up == 4:
            return "open_palm"

        # Fist:
        # More flexible than before.
        # It accepts fist if at least 3 fingers are clearly down.
        if total_down >= 3 and total_up <= 1:
            return "fist"

        return None
