# utils/cooldown.py
# Prevents Spotify actions from triggering too quickly.

import time


class Cooldown:
    def __init__(self, delay=1.0):
        self.delay = delay
        self.last_trigger_time = 0

    def ready(self):
        current_time = time.time()

        if current_time - self.last_trigger_time >= self.delay:
            self.last_trigger_time = current_time
            return True

        return False

    def reset(self):
        self.last_trigger_time = 0
