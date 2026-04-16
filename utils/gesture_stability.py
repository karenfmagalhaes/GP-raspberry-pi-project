class GestureStability:
    def __init__(self, required_frames=5):
        self.required_frames = required_frames
        self.last_gesture = None
        self.frame_count = 0

    def update(self, gesture):
        if gesture == self.last_gesture and gesture is not None:
            self.frame_count += 1
        else:
            self.last_gesture = gesture
            self.frame_count = 1 if gesture is not None else 0

        if self.frame_count >= self.required_frames:
            return gesture

        return None