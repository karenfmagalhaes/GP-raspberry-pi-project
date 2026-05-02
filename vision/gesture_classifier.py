import math


class GestureClassifier:
    """
    Reliable gesture classifier for HoloBeat.

    Final gestures:
    - wake = one finger up
    - open_palm = play
    - fist = pause
    - three_fingers = next track
    - peace = previous track
    - ok_sign = volume up
    - l_sign = volume down
    - rock = camera view on/off
    """

    def classify(self, hand_landmarks):
        lm = hand_landmarks.landmark

        def dist(a, b):
            return math.hypot(lm[a].x - lm[b].x, lm[a].y - lm[b].y)

        # Finger states.
        index_up = lm[8].y < lm[6].y
        middle_up = lm[12].y < lm[10].y
        ring_up = lm[16].y < lm[14].y
        pinky_up = lm[20].y < lm[18].y

        index_down = not index_up
        middle_down = not middle_up
        ring_down = not ring_up
        pinky_down = not pinky_up

        # Hand scale, so distances work closer/farther from camera.
        palm_size = max(0.001, dist(0, 9))

        # Thumb checks.
        thumb_index_touching = dist(4, 8) < palm_size * 0.42
        thumb_side_extended = abs(lm[4].x - lm[2].x) > palm_size * 0.42

        # Pinky extension relaxed for rock gesture.
        pinky_long = dist(20, 17) > dist(18, 17) * 1.15
        pinky_extended = pinky_up or pinky_long

        # ------------------------------------------------------------
        # Interface gesture
        # ------------------------------------------------------------

        # 🤘 Rock = camera view on/off.
        if index_up and pinky_extended and middle_down and ring_down:
            return "rock"

        # ------------------------------------------------------------
        # Volume gestures
        # ------------------------------------------------------------

        # 👌 OK sign = volume up.
        # Thumb and index touch, other three fingers mostly up.
        if thumb_index_touching and middle_up and ring_up and pinky_up:
            return "volume_up"

        # L sign = volume down.
        # Index up + thumb extended sideways, other fingers folded.
        if index_up and thumb_side_extended and middle_down and ring_down and pinky_down:
            return "volume_down"

        # ------------------------------------------------------------
        # Spotify playback gestures
        # ------------------------------------------------------------

        # Open palm = play.
        if index_up and middle_up and ring_up and pinky_up:
            return "open_palm"

        # Fist = pause.
        # Thumb is ignored to avoid confusion with volume.
        if index_down and middle_down and ring_down and pinky_down:
            return "fist"

        # Three fingers = next.
        if index_up and middle_up and ring_up and pinky_down:
            return "three_fingers"

        # Peace = previous.
        if index_up and middle_up and ring_down and pinky_down:
            return "peace"

        # Wake = only index finger up.
        if index_up and middle_down and ring_down and pinky_down:
            return "wake"

        return None
