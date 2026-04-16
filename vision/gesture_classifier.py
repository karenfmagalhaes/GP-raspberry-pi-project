class GestureClassifier:
    def __init__(self):
        pass

    def classify(self, hand_landmarks):
        landmarks = hand_landmarks.landmark

        # Index, middle, ring, pinky
        tips = [8, 12, 16, 20]
        fingers_up = []

        for tip in tips:
            if landmarks[tip].y < landmarks[tip - 2].y:
                fingers_up.append(1)
            else:
                fingers_up.append(0)

        total_fingers = sum(fingers_up)

        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        wrist = landmarks[0]

        thumb_up = (
            thumb_tip.y < thumb_ip.y < thumb_mcp.y and
            thumb_tip.y < wrist.y
        )

        thumb_down = (
            thumb_tip.y > thumb_ip.y > thumb_mcp.y and
            thumb_tip.y > wrist.y
        )

        index_down = landmarks[8].y > landmarks[6].y
        middle_down = landmarks[12].y > landmarks[10].y
        ring_down = landmarks[16].y > landmarks[14].y
        pinky_down = landmarks[20].y > landmarks[18].y

        all_other_fingers_down = index_down and middle_down and ring_down and pinky_down

        # thumbs up
        if thumb_up and all_other_fingers_down:
            return "thumbs_up"

        # thumbs down
        if thumb_down and all_other_fingers_down:
            return "thumbs_down"

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