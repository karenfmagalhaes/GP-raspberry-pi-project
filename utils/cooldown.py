import time


class Cooldown:
    def __init__(self, delay=2.0):
        self.delay = delay
        self.last_trigger_time = 0

    def ready(self):
        current_time = time.time()

        if current_time - self.last_trigger_time >= self.delay:
            self.last_trigger_time = current_time
            return True

        return False