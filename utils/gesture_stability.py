# utils/gesture_stability.py
# Confirms a gesture only after it appears for several frames in a row.

class GestureStability:
    def __init__(self, required_frames=5):
        # required_frames = how many frames the same gesture must appear
        # before it is accepted as stable.
        self.required_frames = required_frames
        self.last_gesture = None
        self.frame_count = 0

    def update(self, gesture):
        # If the same gesture continues, count one more frame.
        if gesture == self.last_gesture and gesture is not None:
            self.frame_count += 1

        # If the gesture changes, start counting again.
        else:
            self.last_gesture = gesture
            self.frame_count = 1 if gesture is not None else 0

        # Only return the gesture when it is stable.
        if self.frame_count >= self.required_frames:
            return gesture

        return None

    def reset(self):
        # Clears the saved gesture.
        self.last_gesture = None
        self.frame_count = 0
