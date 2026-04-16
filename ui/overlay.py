import cv2


def draw_overlay(frame, gesture_text, action_text):
    cv2.putText(
        frame,
        f"Gesture: {gesture_text}",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"Action: {action_text}",
        (30, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 0),
        2
    )

    cv2.putText(
        frame,
        "Press Q to quit",
        (30, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 200, 255),
        2
    )

    return frame