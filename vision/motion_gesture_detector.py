import time
import collections


class MotionGestureDetector:
    """
    Detects hand-shape + movement combination gestures.

    Combinations detected:
        one_finger + swipe right  → one_finger_swipe_right
        one_finger + swipe left   → one_finger_swipe_left
        peace      + move up      → peace_move_up
        peace      + move down    → peace_move_down
    """

    _HISTORY_SIZE = 10

    # Swipe detection
    _SWIPE_MIN_FRAMES = 3
    _SWIPE_H_THRESHOLD = 0.08
    _SWIPE_DOMINANT_RATIO = 1.5
    _SWIPE_COOLDOWN = 0.8

    # Volume detection
    _VERT_MIN_FRAMES = 4
    _VERT_MIN_DY = 0.10
    _VERT_DOMINANT_RATIO = 1.5
    _VERT_COOLDOWN = 1.0

    _PALM_LANDMARKS = [0, 5, 9, 13, 17]

    def __init__(self):
        self._history = collections.deque(maxlen=self._HISTORY_SIZE)
        self._last_gesture = None
        self._last_trigger = {}

    def update(self, hand_landmarks, hand_shape):
        if hand_shape != self._last_gesture:
            self._history.clear()
            self._last_gesture = hand_shape

        lm = hand_landmarks.landmark
        n = len(self._PALM_LANDMARKS)

        cx = sum(lm[i].x for i in self._PALM_LANDMARKS) / n
        cy = sum(lm[i].y for i in self._PALM_LANDMARKS) / n

        self._history.append((cx, cy))

        now = time.time()

        if hand_shape == "one_finger":
            return self._check_swipe(hand_shape, now)

        if hand_shape == "peace":
            return self._check_vertical(hand_shape, now)

        return None

    def reset(self):
        self._history.clear()
        self._last_gesture = None
        self._last_trigger.clear()

    def _check_swipe(self, hand_shape, now):
        if len(self._history) < self._SWIPE_MIN_FRAMES:
            return None

        pts = list(self._history)

        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]

        print(f"[Swipe debug] shape={hand_shape}, dx={dx:.3f}, dy={dy:.3f}")

        if abs(dx) > self._SWIPE_H_THRESHOLD and abs(dx) > abs(dy) * self._SWIPE_DOMINANT_RATIO:
            if dx > 0:
                if self._trigger("one_finger_swipe_right", now, self._SWIPE_COOLDOWN):
                    self._history.clear()
                    return "one_finger_swipe_right"

            if dx < 0:
                if self._trigger("one_finger_swipe_left", now, self._SWIPE_COOLDOWN):
                    self._history.clear()
                    return "one_finger_swipe_left"

        return None

    def _check_vertical(self, hand_shape, now):
        if len(self._history) < self._VERT_MIN_FRAMES:
            return None

        window = list(self._history)[-self._VERT_MIN_FRAMES:]

        dx = window[-1][0] - window[0][0]
        dy = window[-1][1] - window[0][1]

        print(f"[Volume debug] shape={hand_shape}, dx={dx:.3f}, dy={dy:.3f}")

        if abs(dy) > self._VERT_MIN_DY and abs(dy) > abs(dx) * self._VERT_DOMINANT_RATIO:
            if dy < 0:
                if self._trigger("peace_move_up", now, self._VERT_COOLDOWN):
                    self._history.clear()
                    return "peace_move_up"

            if dy > 0:
                if self._trigger("peace_move_down", now, self._VERT_COOLDOWN):
                    self._history.clear()
                    return "peace_move_down"

        return None

    def _trigger(self, gesture, now, cooldown):
        if now - self._last_trigger.get(gesture, 0.0) < cooldown:
            return False

        self._last_trigger[gesture] = now
        return True