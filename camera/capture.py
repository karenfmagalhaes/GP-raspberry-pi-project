from picamera2 import Picamera2
from libcamera import controls


class Camera:
    def __init__(self, width=1920, height=1080, autofocus=True):
        self.width = width
        self.height = height
        self.autofocus = autofocus
        self.cam = None

    def start(self):
        self.cam = Picamera2()
        config = self.cam.create_preview_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"}
        )
        self.cam.configure(config)
        self.cam.start()

        if self.autofocus:
            self.cam.set_controls({"AfMode": controls.AfModeEnum.Continuous})

    def read(self):
        if self.cam is None:
            raise RuntimeError("Camera has not been started.")
        return self.cam.capture_array()

    def release(self):
        if self.cam is not None:
            self.cam.stop()
            self.cam.close()
            self.cam = None
