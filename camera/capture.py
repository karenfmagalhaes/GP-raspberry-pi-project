# camera/capture.py
# Camera capture via rpicam-vid MJPEG stream (avoids Picamera2 pyenv issues).

import os
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
        self.buffer = bytearray()
        self.opened = False

        # ~1 MB is far larger than any 640x480 MJPEG frame.
        # If the buffer ever exceeds this, the stream is corrupt.
        self._max_buffer = 1 * 1024 * 1024

        self.camera_command = self._find_camera_command()

        if not self.camera_command:
            print("Camera command not found. Install/use rpicam-apps.")
            return

        self._start_camera_stream()

    def _find_camera_command(self):
        if shutil.which("rpicam-vid"):
            return "rpicam-vid"

        if shutil.which("libcamera-vid"):
            return "libcamera-vid"

        return None

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
            # CM3 continuous autofocus — keeps focus sharp as the hand moves.
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
                print("Camera stream failed to start.")
                self.opened = False
                return

            self.opened = True
            print("Camera stream started successfully")

        except Exception as e:
            print(f"Camera failed to start: {e}")
            self.opened = False

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
        if not self.opened or self.process is None or self.process.stdout is None:
            return False, None

        start_time = time.time()

        while time.time() - start_time < 3:
            if self.process.poll() is not None:
                print("Camera process ended unexpectedly.")
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

                # Drop any bytes that arrived before the first JPEG SOI marker.
                jpg_start = self.buffer.find(b"\xff\xd8")

                if jpg_start == -1:
                    continue

                if jpg_start > 0:
                    del self.buffer[:jpg_start]

                # Drain ALL complete JPEG frames from the buffer and keep only
                # the newest one. This reduces visible camera lag.
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
                print(f"Failed to read frame: {e}")
                return False, None

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

        print("Camera stream stopped")
