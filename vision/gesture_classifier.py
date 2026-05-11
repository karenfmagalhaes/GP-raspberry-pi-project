# vision/gesture_classifier.py
# Classifies static hand shapes used by the WaveBeat gesture controller.

import math

class GestureClassifier:
    # Distance limit for detecting the OK sign.
    _OK_TOUCH_RATIO = 0.42

    def classify(self, hand_landmarks):
        lm = hand_landmarks.landmark

        def dist(a, b):
            return math.hypot(lm[a].x - lm[b].x, lm[a].y - lm[b].y)

        palm_size = max(0.001, dist(0, 9))   # wrist (0) to middle-finger base (9)

        index_up  = lm[8].y  < lm[6].y
        middle_up = lm[12].y < lm[10].y
        ring_up   = lm[16].y < lm[14].y
        pinky_up  = lm[20].y < lm[18].y

        index_down  = not index_up
        middle_down = not middle_up
        ring_down   = not ring_up
        pinky_down  = not pinky_up

        # Thumb-index proximity for OK sign.
        # The index is bent in a proper OK circle so index_up is unreliable.
        thumb_index_touching = dist(4, 8) < palm_size * self._OK_TOUCH_RATIO

        # Rock: index AND pinky raised, middle AND ring down.
        # Checked first — shares index_up with several other gestures.
        if index_up and pinky_up and middle_down and ring_down:
            return "rock"

        # OK sign: thumb touching index, other three fingers extended up.
        # Checked before open_palm — in open_palm the thumb is free, not circling.
        if thumb_index_touching and middle_up and ring_up and pinky_up:
            return "ok"

        # Open palm: all four fingers up (thumb not constrained after ok check).
        if index_up and middle_up and ring_up and pinky_up:
            return "open_palm"

        # Peace: index + middle up, ring + pinky down.
        if index_up and middle_up and ring_down and pinky_down:
            return "peace"

        # Fist: all four fingers down (thumb ignored).
        if index_down and middle_down and ring_down and pinky_down:
            return "fist"

        # One finger: only index up, all others down.
        # Used for directional swipes (next / previous track).
        if index_up and middle_down and ring_down and pinky_down:
            return "one_finger"

        return None
