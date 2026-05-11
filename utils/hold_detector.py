# utils/hold_detector.py
# Detects when a specific gesture is held for a required amount of time.

import time

class HoldDetector:
    def __init__(self, target_gesture, hold_seconds=1.5):
        # Gesture that needs to be held.
        self.target_gesture = target_gesture

        # How long the gesture must stay active.
        self.hold_seconds = hold_seconds

        # Stores when the hold started.
        self.start_time = None

    def update(self, gesture):
        # Check the current time.
        now = time.time()

        if gesture == self.target_gesture:
            # Start counting only once.
            if self.start_time is None:
                self.start_time = now

            # Return True when the gesture was held long enough.
            return now - self.start_time >= self.hold_seconds

        # Reset if the gesture changes or disappears.
        self.start_time = None
        return False

    def reset(self):
        # Manually clear the hold timer.
        self.start_time = None