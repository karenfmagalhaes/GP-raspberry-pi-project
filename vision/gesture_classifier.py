import math


class GestureClassifier:
    """
    Rule-based hand gesture classifier using MediaPipe hand landmarks.

    Gestures:
    - wake = one finger up
    - open_palm = play
    - fist = pause
    - three_fingers = next
    - peace = previous
    - thumbs_up / thumbs_down = volume
    - shaka = open/close guide
    - rock = camera view on/off
    """

    def classify(self, hand_landmarks):
        lm = hand_landmarks.landmark

        def dist(a, b):
            return math.hypot(lm[a].x - lm[b].x, lm[a].y - lm[b].y)

        # Main finger states.
        index_up = lm[8].y < lm[6].y
        middle_up = lm[12].y < lm[10].y
        ring_up = lm[16].y < lm[14].y
        pinky_up = lm[20].y < lm[18].y

        index_down = not index_up
        middle_down = not middle_up
        ring_down = not ring_up
        pinky_down = not pinky_up

        # Thumb landmarks.
        thumb_tip = lm[4]
        thumb_ip = lm[3]
        thumb_mcp = lm[2]
        wrist = lm[0]

        # Thumb extension checks.
        thumb_sideways = abs(thumb_tip.x - thumb_mcp.x) > 0.055
        thumb_long = dist(4, 2) > dist(3, 2) * 1.15
        thumb_extended = thumb_sideways or thumb_long

        # More relaxed pinky extension for shaka/rock.
        pinky_long = dist(20, 17) > dist(18, 17) * 1.15
        pinky_extended = pinky_up or pinky_long

        # ------------------------------------------------------------
        # Interface gestures first
        # ------------------------------------------------------------

        # 🤙 Shaka: thumb + pinky extended, index/middle/ring folded.
        if thumb_extended and pinky_extended and index_down and middle_down and ring_down:
            return None  # shaka disabled because it opens guide by accident

        # 🤘 Rock: index + pinky extended, middle/ring folded.
        if index_up and pinky_extended and middle_down and ring_down:
            return "rock"

        # ------------------------------------------------------------
        # Spotify gestures
        # ------------------------------------------------------------

        # Open palm.
        if index_up and middle_up and ring_up and pinky_up:
            return "open_palm"

        # Fist / thumbs.
        # IMPORTANT:
        # Pause was getting confused with volume, so thumbs_up/down must be
        # very clear. Otherwise, a closed hand is treated as fist = pause.
        if index_down and middle_down and ring_down and pinky_down:
            clear_thumb_up = (
                thumb_extended
                and thumb_tip.y < wrist.y - 0.13
                and thumb_tip.y < thumb_mcp.y - 0.08
            )

            clear_thumb_down = (
                thumb_extended
                and thumb_tip.y > wrist.y + 0.18
                and thumb_tip.y > thumb_mcp.y + 0.08
            )

            if clear_thumb_up:
                return "thumbs_up"

            if clear_thumb_down:
                return "thumbs_down"

            return "fist"

        # Three fingers = next.
        if index_up and middle_up and ring_up and pinky_down:
            return "three_fingers"

        # Peace = previous.
        if index_up and middle_up and ring_down and pinky_down:
            return "peace"

        # Wake = only index up.
        if index_up and middle_down and ring_down and pinky_down:
            return "wake"

        return None
