# camera/capture.py
# Camera capture using rpicam-vid MJPEG stream.
# This avoids Picamera2 Python binding problems in custom Python/pyenv environments.

import os
import select
import shutil
import subprocess
import time

import cv2
import numpy as np


class CameraCapture:
    def __init__(self, camera_index=0, width=640, height=480, framerate=15, autofocus=False):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.framerate = framerate

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
                ready, _, _ = select.select([self.process.stdout], [], [], 0.5)

                if not ready:
                    continue

                chunk = os.read(self.process.stdout.fileno(), 4096)

                if not chunk:
                    return False, None

                self.buffer += chunk

                # Drop any bytes that arrived before the first JPEG SOI marker.
                jpg_start = self.buffer.find(b"\xff\xd8")
                if jpg_start == -1:
                    # No start marker anywhere — discard everything if the buffer
                    # is large enough to be considered corrupt data.
                    if len(self.buffer) > self._max_buffer:
                        self.buffer.clear()
                    continue
                if jpg_start > 0:
                    del self.buffer[:jpg_start]

                # Search for the JPEG EOI marker after the start.
                jpg_end = self.buffer.find(b"\xff\xd9", 2)
                if jpg_end == -1:
                    # Incomplete frame — safe to keep buffering, but flush if the
                    # buffer has grown past the cap (corrupt/stalled stream).
                    if len(self.buffer) > self._max_buffer:
                        self.buffer.clear()
                    continue

                # Extract the complete JPEG and advance the buffer.
                jpg_data = bytes(self.buffer[:jpg_end + 2])
                del self.buffer[:jpg_end + 2]

                image_array = np.frombuffer(jpg_data, dtype=np.uint8)
                frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

                if frame is not None:
                    return True, frame

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
