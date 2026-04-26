# ui/overlay.py
# Draws gesture and Spotify action information on top of the camera frame.

import cv2


def draw_overlay(frame, gesture_text, action_text):
    # Gesture text
    cv2.putText(
        frame,
        f"Gesture: {gesture_text}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )

    # Spotify action text
    cv2.putText(
        frame,
        f"Action: {action_text}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 0),
        2
    )

    # Quit instruction
    cv2.putText(
        frame,
        "Press Q to quit",
        (20, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 200, 255),
        2
    )

    return frame
