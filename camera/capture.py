# camera/capture.py
# Camera capture wrapper.
# Raspberry Pi: uses rpicam-vid/libcamera-vid MJPEG stream.
# Windows/laptop test: uses OpenCV webcam.
# This allows testing in VS Code without changing main.py.

import os
import platform
import select
import shutil
import subprocess
import time

import cv2
import numpy as np


class CameraCapture:
    def __init__(
        self,
        camera_index=0,
        width=640,
        height=480,
        framerate=15,
        rotation=0,
        autofocus=False
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.framerate = framerate
        self.rotation = rotation
        self.autofocus = autofocus

        self.process = None
        self.cap = None
        self.buffer = bytearray()
        self.opened = False
        self.mode = None
        self.camera_command = None

        # ~1 MB is far larger than any 640x480 MJPEG frame.
        # If the buffer ever exceeds this, the stream is corrupt.
        self._max_buffer = 1 * 1024 * 1024

        system_name = platform.system().lower()

        # Windows / VS Code local testing.
        if system_name == "windows" or os.getenv("FORCE_WEBCAM") == "1":
            self._start_webcam()
            return

        # Raspberry Pi / Linux: try rpicam/libcamera first.
        self.camera_command = self._find_camera_command()

        if self.camera_command:
            self._start_camera_stream()
            return

        # Linux laptop fallback.
        print("[Camera] rpicam/libcamera not found. Using OpenCV webcam.")
        self._start_webcam()

    def _find_camera_command(self):
        if shutil.which("rpicam-vid"):
            return "rpicam-vid"

        if shutil.which("libcamera-vid"):
            return "libcamera-vid"

        return None

    # ------------------------------------------------------------
    # Raspberry Pi camera mode
    # ------------------------------------------------------------

    def _start_camera_stream(self):
        command = [
            self.camera_command,
            "--timeout", "0",
            "--codec", "mjpeg",
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(self.framerate),
            "--nopreview",
            "--output", "-"
        ]

        if self.autofocus:
            # Camera Module 3 continuous autofocus.
            command += ["--autofocus-mode", "continuous"]

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )

            time.sleep(2)

            if self.process.poll() is not None:
                print("[Camera] Raspberry Pi camera stream failed to start.")
                self.opened = False
                return

            self.mode = "rpicam"
            self.opened = True
            print("[Camera] Raspberry Pi camera stream started successfully")

        except Exception as e:
            print(f"[Camera] Raspberry Pi camera failed to start: {e}")
            self.opened = False

    def _read_rpicam_frame(self):
        if not self.opened or self.process is None or self.process.stdout is None:
            return False, None

        start_time = time.time()

        while time.time() - start_time < 3:
            if self.process.poll() is not None:
                print("[Camera] Camera process ended unexpectedly.")
                self.opened = False
                return False, None

            try:
                ready, _, _ = select.select([self.process.stdout], [], [], 0.05)

                if not ready:
                    continue

                chunk = os.read(self.process.stdout.fileno(), 65536)

                if not chunk:
                    return False, None

                self.buffer += chunk

                if len(self.buffer) > self._max_buffer:
                    self.buffer.clear()
                    continue

                jpg_start = self.buffer.find(b"\xff\xd8")

                if jpg_start == -1:
                    continue

                if jpg_start > 0:
                    del self.buffer[:jpg_start]

                latest_frame = None

                while True:
                    s = self.buffer.find(b"\xff\xd8")

                    if s == -1:
                        break

                    if s > 0:
                        del self.buffer[:s]

                    e = self.buffer.find(b"\xff\xd9", 2)

                    if e == -1:
                        break

                    jpg_data = bytes(self.buffer[:e + 2])
                    del self.buffer[:e + 2]

                    arr = np.frombuffer(jpg_data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                    if frame is not None:
                        latest_frame = frame

                if latest_frame is not None:
                    latest_frame = self._apply_rotation(latest_frame)
                    return True, latest_frame

            except Exception as e:
                print(f"[Camera] Failed to read Raspberry Pi frame: {e}")
                return False, None

        return False, None

    # ------------------------------------------------------------
    # Windows / laptop webcam mode
    # ------------------------------------------------------------

    def _start_webcam(self):
        print("[Camera] Using OpenCV webcam for VS Code testing")

        system_name = platform.system().lower()

        if system_name == "windows":
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(self.camera_index)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.framerate)

        if not self.cap.isOpened():
            print(f"[Camera] Could not open webcam at index {self.camera_index}")
            self.opened = False
            return

        self.mode = "webcam"
        self.opened = True
        print(f"[Camera] Webcam started successfully at index {self.camera_index}")

    def _read_webcam_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return False, None

        ret, frame = self.cap.read()

        if not ret:
            return False, None

        frame = self._apply_rotation(frame)
        return True, frame

    # ------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------

    def _apply_rotation(self, frame):
        if self.rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        if self.rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)

        if self.rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return frame

    def is_opened(self):
        return self.opened

    def read_frame(self):
        if self.mode == "rpicam":
            return self._read_rpicam_frame()

        if self.mode == "webcam":
            return self._read_webcam_frame()

        return False, None

    def release(self):
        self.opened = False

        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

        if self.cap is not None:
            self.cap.release()

        print("[Camera] Camera stopped")