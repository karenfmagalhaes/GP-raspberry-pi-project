# vision/gesture_classifier.py
# Classifies simple hand gestures from MediaPipe hand landmarks.

class GestureClassifier:
    def __init__(self):
        pass

    def classify(self, hand_landmarks):
        landmarks = hand_landmarks.landmark

        # MediaPipe hand landmark indexes:
        # 4  = thumb tip
        # 8  = index finger tip
        # 12 = middle finger tip
        # 16 = ring finger tip
        # 20 = pinky finger tip

        # Check index, middle, ring, and pinky fingers.
        finger_tips = [8, 12, 16, 20]
        fingers_up = []

        for tip in finger_tips:
            # In image coordinates, smaller y means higher on the screen.
            if landmarks[tip].y < landmarks[tip - 2].y:
                fingers_up.append(1)
            else:
                fingers_up.append(0)

        total_fingers = sum(fingers_up)

        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        wrist = landmarks[0]

        # Thumb up/down checks.
        thumb_up = (
            thumb_tip.y < thumb_ip.y < thumb_mcp.y and
            thumb_tip.y < wrist.y
        )

        thumb_down = (
            thumb_tip.y > thumb_ip.y > thumb_mcp.y and
            thumb_tip.y > wrist.y
        )

        # Check if the other four fingers are down.
        index_down = landmarks[8].y > landmarks[6].y
        middle_down = landmarks[12].y > landmarks[10].y
        ring_down = landmarks[16].y > landmarks[14].y
        pinky_down = landmarks[20].y > landmarks[18].y

        all_other_fingers_down = (
            index_down and
            middle_down and
            ring_down and
            pinky_down
        )

        # Thumbs up gesture.
        if thumb_up and all_other_fingers_down:
            return "thumbs_up"

        # Thumbs down gesture.
        if thumb_down and all_other_fingers_down:
            return "thumbs_down"

        # Open palm: four fingers up.
        if total_fingers == 4:
            return "open_palm"

        # Fist: four fingers down and thumb is not clearly up/down.
        if total_fingers == 0 and not thumb_up and not thumb_down:
            return "fist"

        # Peace sign: index and middle up only.
        if (
            fingers_up[0] == 1 and
            fingers_up[1] == 1 and
            fingers_up[2] == 0 and
            fingers_up[3] == 0
        ):
            return "peace"

        # Three fingers: index, middle, and ring up.
        if (
            fingers_up[0] == 1 and
            fingers_up[1] == 1 and
            fingers_up[2] == 1 and
            fingers_up[3] == 0
        ):
            return "three_fingers"

        return None         return "thumbs_down"

        # open palm
        if total_fingers == 4:
            return "open_palm"

        # fist
        if total_fingers == 0 and not thumb_up and not thumb_down:
            return "fist"

        # peace
        if (
            fingers_up[0] == 1 and
            fingers_up[1] == 1 and
            fingers_up[2] == 0 and
            fingers_up[3] == 0
        ):
            return "peace"

        # three fingers
        if (
            fingers_up[0] == 1 and
            fingers_up[1] == 1 and
            fingers_up[2] == 1 and
            fingers_up[3] == 0
        ):
            return "three_fingers"

        return None
