import time


class HoldDetector:
    def __init__(self, target_gesture, hold_seconds=1.5):
        self.target_gesture = target_gesture
        self.hold_seconds = hold_seconds
        self.start_time = None

    def update(self, gesture):
        now = time.time()

        if gesture == self.target_gesture:
            if self.start_time is None:
                self.start_time = now

            return now - self.start_time >= self.hold_seconds

        self.start_time = None
        return False

    def reset(self):
        self.start_time = None