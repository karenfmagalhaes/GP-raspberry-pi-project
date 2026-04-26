# vision/pose_visualizer.py
# Detects body pose and draws a glowing skeleton effect on the camera frame.

import cv2
import mediapipe as mp


class PoseVisualizer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils

        # model_complexity=0 is lighter for Raspberry Pi.
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )

    def process(self, frame):
        # Frame is BGR from OpenCV/Picamera2.
        # MediaPipe needs RGB.
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        rgb_frame.flags.writeable = False
        results = self.pose.process(rgb_frame)
        rgb_frame.flags.writeable = True

        return results

    def draw_glow_pose(self, frame, results):
        if not results.pose_landmarks:
            return frame

        height, width, _ = frame.shape
        landmarks = results.pose_landmarks.landmark

        # Draw glowing pose connections.
        for connection in self.mp_pose.POSE_CONNECTIONS:
            start_index, end_index = connection

            start = landmarks[start_index]
            end = landmarks[end_index]

            # Skip landmarks MediaPipe cannot see clearly.
            if start.visibility < 0.5 or end.visibility < 0.5:
                continue

            start_point = (
                int(start.x * width),
                int(start.y * height)
            )

            end_point = (
                int(end.x * width),
                int(end.y * height)
            )

            # Outer glow line.
            cv2.line(
                frame,
                start_point,
                end_point,
                (255, 0, 255),
                8
            )

            # Inner bright line.
            cv2.line(
                frame,
                start_point,
                end_point,
                (255, 255, 255),
                2
            )

        return frame

    def draw_normal_pose(self, frame, results):
        if not results.pose_landmarks:
            return frame

        self.mp_draw.draw_landmarks(
            frame,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS
        )

        return frame

    def close(self):
        self.pose.close()
