import cv2


class CameraCapture:
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)

    def is_opened(self):
        return self.cap.isOpened()

    def read_frame(self):
        return self.cap.read()

    def release(self):
        self.cap.release()