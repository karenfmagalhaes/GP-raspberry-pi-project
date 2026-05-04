import time
import collections


class MotionGestureDetector:
    """
    Detects hand-shape + movement combination gestures.

    Combinations detected:
        one_finger + swipe right  → one_finger_swipe_right  (next track)
        one_finger + swipe left   → one_finger_swipe_left   (previous track)
        peace      + move up      → peace_move_up            (volume up)
        peace      + move down    → peace_move_down          (volume down)

    History is cleared whenever the hand shape changes, and also after a
    volume trigger fires — this prevents one long movement from producing
    multiple volume commands.
    """

    _HISTORY_SIZE = 10

    # --- Swipe detection (one_finger) ---
    _SWIPE_MIN_FRAMES     = 3      # ~0.3 s at 10 fps
    _SWIPE_H_THRESHOLD    = 0.08   # minimum net horizontal displacement (normalised)
    _SWIPE_DOMINANT_RATIO = 1.5    # |dx| must beat |dy| by this factor
    _SWIPE_COOLDOWN       = 0.8    # seconds between successive swipe triggers

    # --- Vertical / volume detection (peace) ---
    # Only the last _VERT_MIN_FRAMES frames are measured, so history older
    # than ~0.4 s cannot bleed into the next check.
    _VERT_MIN_FRAMES     = 4       # ~0.4 s at 10 fps
    _VERT_MIN_DY         = 0.10    # minimum net vertical displacement (normalised)
    _VERT_DOMINANT_RATIO = 1.5     # |dy| must beat |dx| by this factor
    _VERT_COOLDOWN       = 1.0     # seconds between successive volume triggers

    # Landmark indices for a stable palm centre (wrist + base of each finger)
    _PALM_LANDMARKS = [0, 5, 9, 13, 17]

    def __init__(self):
        self._history      = collections.deque(maxlen=self._HISTORY_SIZE)
        self._last_gesture = None
        self._last_trigger = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def update(self, hand_landmarks, hand_shape):
        """
        Append the current palm centre to history and check for a
        combination gesture.  Returns a gesture name string or None.
        """
        # Clear history when the hand shape changes so stale movement from
        # a previous shape never bleeds into the next detection window.
        if hand_shape != self._last_gesture:
            self._history.clear()
            self._last_gesture = hand_shape

        lm = hand_landmarks.landmark
        n  = len(self._PALM_LANDMARKS)
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

    # ------------------------------------------------------------------
    # Shape-specific detection
    # ------------------------------------------------------------------

    def _check_swipe(self, hand_shape, now):
        """Detect one_finger_swipe_right or one_finger_swipe_left."""
        if len(self._history) < self._SWIPE_MIN_FRAMES:
            return None

        pts = list(self._history)
        dx  = pts[-1][0] - pts[0][0]   # positive = rightward
        dy  = pts[-1][1] - pts[0][1]

        print(f"shape={hand_shape}, dx={dx:.3f}, dy={dy:.3f}")

        if abs(dx) > self._SWIPE_H_THRESHOLD and abs(dx) > abs(dy) * self._SWIPE_DOMINANT_RATIO:
            if dx > 0:
                if self._trigger("one_finger_swipe_right", now, self._SWIPE_COOLDOWN):
                    self._history.clear()
                    return "one_finger_swipe_right"
                else:
                    if self._trigger("one_finger_swipe_left", now, self._SWIPE_COOLDOWN):
                        self._history.clear()
                        return "one_finger_swipe_left"

    def _check_vertical(self, hand_shape, now):
        """Detect peace_move_up or peace_move_down."""
        if len(self._history) < self._VERT_MIN_FRAMES:
            return None

        # Measure only over the most-recent window so that positions from
        # before the last trigger cannot accumulate and re-fire.
        window = list(self._history)[-self._VERT_MIN_FRAMES:]
        dx = window[-1][0] - window[0][0]
        dy = window[-1][1] - window[0][1]   # positive = downward in image coords

        print(f"[Volume debug] shape={hand_shape}, dx={dx:.3f}, dy={dy:.3f}")

        if abs(dy) > self._VERT_MIN_DY and abs(dy) > abs(dx) * self._VERT_DOMINANT_RATIO:
            if dy < 0:   # hand moved up (y decreases)
                if self._trigger("peace_move_up", now, self._VERT_COOLDOWN):
                    self._history.clear()   # prevent the same movement re-triggering
                    return "peace_move_up"
            else:        # hand moved down (y increases)
                if self._trigger("peace_move_down", now, self._VERT_COOLDOWN):
                    self._history.clear()
                    return "peace_move_down"

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trigger(self, gesture, now, cooldown):
        """Returns True and stamps the trigger time if the cooldown has elapsed."""
        if now - self._last_trigger.get(gesture, 0.0) < cooldown:
            return False
        self._last_trigger[gesture] = now
        return True
