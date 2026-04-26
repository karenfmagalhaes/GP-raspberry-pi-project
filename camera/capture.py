# camera/capture.py
# Handles Raspberry Pi Camera Module capture using Picamera2.
# This class keeps the same methods used in main.py:
# is_opened(), read_frame(), and release().

from picamera2 import Picamera2


class CameraCapture:
    def __init__(self, camera_index=0, width=640, height=480):
        # camera_index is kept so the rest of the project does not break.
        # Picamera2 does not use camera_index in the same way as OpenCV webcams.
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.picam2 = None
        self.opened = False

        try:
            self.picam2 = Picamera2()

            # BGR888 is important because OpenCV uses BGR format.
            # MediaPipe will later convert BGR to RGB in hand_tracker.py.
            config = self.picam2.create_preview_configuration(
                main={
                    "format": "BGR888",
                    "size": (self.width, self.height)
                }
            )

            self.picam2.configure(config)
            self.picam2.start()

            self.opened = True
            print("Camera started successfully")

        except Exception as e:
            print(f"Camera failed to start: {e}")
            self.opened = False

    def is_opened(self):
        return self.opened

    def read_frame(self):
        if not self.opened or self.picam2 is None:
            return False, None

        try:
            frame = self.picam2.capture_array()
            return True, frame

        except Exception as e:
            print(f"Failed to read frame: {e}")
            return False, None

    def release(self):
        if self.opened and self.picam2 is not None:
            try:
                self.picam2.stop()
                print("Camera stopped")
            except Exception as e:
                print(f"Error stopping camera: {e}")

        self.opened = False
