# vision/motion_gesture_detector.py
# Detects movement-based gestures after a hand shape is recognised.

import time
import collections


class MotionGestureDetector:
    _HISTORY_SIZE = 10

    # --- Swipe detection (one_finger) ---
    _SWIPE_MIN_FRAMES     = 3      # ~0.3 s at 10 fps
    _SWIPE_H_THRESHOLD    = 0.08   # minimum net horizontal displacement (normalised)
    _SWIPE_DOMINANT_RATIO = 1.5    # |dx| must beat |dy| by this factor
    _SWIPE_COOLDOWN       = 0.8    # seconds between successive swipe triggers

    # --- Volume zone detection (peace) ---
    _BASELINE_FRAMES  = 4     # consecutive peace frames before baseline is locked
    _DEAD_ZONE        = 0.06  # normalised y units around baseline — no action here
    _REPEAT_INTERVAL  = 1.0   # seconds between successive volume fires while held

    # Landmark indices for a stable palm centre (wrist + base of each finger)
    _PALM_LANDMARKS = [0, 5, 9, 13, 17]

    def __init__(self):
        self._history      = collections.deque(maxlen=self._HISTORY_SIZE)
        self._last_gesture = None
        self._last_trigger = {}

        # Peace / volume baseline state (reset on every shape change)
        self._peace_baseline_y      = None
        self._peace_baseline_frames = 0
        self._peace_last_fired      = 0.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def update(self, hand_landmarks, hand_shape):
        """
        Record the current palm centre and check for a combination gesture.
        Returns a gesture name string or None.
        """
        # Shape change → clear history and reset volume baseline.
        if hand_shape != self._last_gesture:
            self._history.clear()
            self._last_gesture = hand_shape
            self._reset_peace_state()

        lm = hand_landmarks.landmark
        n  = len(self._PALM_LANDMARKS)
        cx = sum(lm[i].x for i in self._PALM_LANDMARKS) / n
        cy = sum(lm[i].y for i in self._PALM_LANDMARKS) / n
        self._history.append((cx, cy))

        now = time.time()

        if hand_shape == "one_finger":
            return self._check_swipe(hand_shape, now)

        if hand_shape == "peace":
            return self._check_volume_zone(cy, now)

        return None

    def reset(self):
        self._history.clear()
        self._last_gesture = None
        self._last_trigger.clear()
        self._reset_peace_state()

    # ------------------------------------------------------------------
    # Swipe detection
    # ------------------------------------------------------------------

    def _check_swipe(self, hand_shape, now):
        """Detect one_finger_swipe_right or one_finger_swipe_left."""
        if len(self._history) < self._SWIPE_MIN_FRAMES:
            return None

        pts = list(self._history)
        dx  = pts[-1][0] - pts[0][0]   # positive = rightward
        dy  = pts[-1][1] - pts[0][1]

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

    # ------------------------------------------------------------------
    # Volume zone detection
    # ------------------------------------------------------------------

    def _check_volume_zone(self, cy, now):
           # Accumulate frames until baseline is stable enough to lock.
        if self._peace_baseline_y is None:
            self._peace_baseline_frames += 1
            if self._peace_baseline_frames >= self._BASELINE_FRAMES:
                self._peace_baseline_y = cy
            return None

        up_threshold   = self._peace_baseline_y - self._DEAD_ZONE
        down_threshold = self._peace_baseline_y + self._DEAD_ZONE

        elapsed = now - self._peace_last_fired

        if cy < up_threshold:
            if elapsed >= self._REPEAT_INTERVAL:
                self._peace_last_fired = now
                return "peace_move_up"

        elif cy > down_threshold:
            if elapsed >= self._REPEAT_INTERVAL:
                self._peace_last_fired = now
                return "peace_move_down"

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset_peace_state(self):
        self._peace_baseline_y      = None
        self._peace_baseline_frames = 0
        self._peace_last_fired      = 0.0

    def _trigger(self, gesture, now, cooldown):
        """Returns True and stamps the trigger time if the cooldown has elapsed."""
        if now - self._last_trigger.get(gesture, 0.0) < cooldown:
            return False
        self._last_trigger[gesture] = now
        return True
