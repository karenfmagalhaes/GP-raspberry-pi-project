import cv2


def _glass(frame, x1, y1, x2, y2, alpha=0.52):
    ov = frame.copy()
    cv2.rectangle(ov, (x1, y1), (x2, y2), (8, 8, 12), -1)
    cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (50, 50, 55), 1)


def _small(frame, text, x, y, color=(150, 150, 150), scale=0.34):
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_overlay(frame, gesture, action, track=""):
    # Only show a gesture badge when a hand is actually detected.
    if not gesture or gesture == "No hand":
        return frame

    x1, y1, x2, y2 = 10, 10, 178, 34
    _glass(frame, x1, y1, x2, y2)
    _small(frame, gesture[:28], x1 + 9, y1 + 17)

    return frame


def draw_hologram_status(frame, hologram_enabled):
    label = "Body: ON" if hologram_enabled else "Body: OFF"
    color = (75, 155, 75) if hologram_enabled else (95, 95, 95)

    x1, y1, x2, y2 = 10, 40, 96, 60
    _glass(frame, x1, y1, x2, y2)
    _small(frame, label, x1 + 8, y1 + 14, color=color, scale=0.30)

    return frame
