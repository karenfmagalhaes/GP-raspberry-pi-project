# ui/virtual_assistant.py
# Draws the Sendo virtual assistant panel on the OpenCV frame.
# Uses only OpenCV, math, and time to stay lightweight on Raspberry Pi.

import cv2
import math
import time


_STATE_COLORS = {
    "sleeping":  (0, 140, 255),   # orange (BGR)
    "listening": (50, 220, 80),   # green  (BGR)
    "action":    (220, 50, 200),  # purple (BGR)
    "error":     (30, 30, 220),   # red    (BGR)
}

_PANEL_W = 200
_PANEL_H = 275


def _wrap_text(text, max_chars=24):
    words = text.split()
    lines, current = [], ""
    for word in words:
        fits = len(current) + len(word) + (1 if current else 0) <= max_chars
        if fits:
            current = (current + " " + word).strip() if current else word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_virtual_assistant(frame, state, message, gesture="", action="", track="", name="Sendo"):
    t = time.time()
    h, w = frame.shape[:2]

    px = w - _PANEL_W - 5
    py = 5

    color = _STATE_COLORS.get(state, _STATE_COLORS["sleeping"])
    dim   = tuple(int(c * 0.45) for c in color)

    # Semi-transparent dark background
    panel_bg = frame.copy()
    cv2.rectangle(panel_bg, (px, py), (px + _PANEL_W, py + _PANEL_H), (5, 5, 15), -1)
    cv2.addWeighted(panel_bg, 0.72, frame, 0.28, 0, frame)

    # Panel border
    cv2.rectangle(frame, (px, py), (px + _PANEL_W, py + _PANEL_H), color, 1)

    # Scan lines for hologram feel
    scan = tuple(int(c * 0.07) for c in color)
    for sy in range(py + 1, py + _PANEL_H, 6):
        cv2.line(frame, (px + 1, sy), (px + _PANEL_W - 1, sy), scan, 1)

    # Name header
    cv2.putText(frame, name, (px + 10, py + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2)

    # Divider
    cv2.line(frame, (px + 5, py + 29), (px + _PANEL_W - 5, py + 29), dim, 1)

    # State label
    cv2.putText(frame, state.upper(), (px + 10, py + 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)

    # Avatar center
    cx = px + _PANEL_W // 2
    cy = py + 135

    if state == "action":
        _draw_sound_bars(frame, cx, cy, color, t)
    else:
        _draw_circle_avatar(frame, cx, cy, color, dim, state, t)

    # Message text
    lines = _wrap_text(message)
    for i, line in enumerate(lines[:3]):
        cv2.putText(frame, line, (px + 8, py + 208 + i * 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1)

    # Track at bottom
    if track:
        display = (track[:21] + "..") if len(track) > 23 else track
        cv2.putText(frame, display, (px + 5, py + _PANEL_H - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, dim, 1)

    return frame


def _draw_circle_avatar(frame, cx, cy, color, dim, state, t):
    # Pulsing outward rings
    for i in range(3):
        phase = (t * 1.3 + i * 0.33) % 1.0
        r = int(40 + phase * 25)
        alpha = int(160 * (1.0 - phase))
        ring_color = tuple(int(c * alpha // 255) for c in color)
        cv2.circle(frame, (cx, cy), r, ring_color, 1)

    # Outer glow
    cv2.circle(frame, (cx, cy), 38, dim, 6)
    # Main circle
    cv2.circle(frame, (cx, cy), 38, color, 2)

    _draw_face(frame, cx, cy, state, color, t)


def _draw_face(frame, cx, cy, state, color, t):
    if state == "sleeping":
        # Droopy closed eyes
        cv2.line(frame, (cx - 14, cy - 7), (cx - 6,  cy - 7), color, 2)
        cv2.line(frame, (cx + 6,  cy - 7), (cx + 14, cy - 7), color, 2)
        # Neutral resting mouth
        cv2.ellipse(frame, (cx, cy + 13), (10, 4), 0, 0, 180, color, 1)
        # Floating z's that bob gently
        z_bob = int(abs(math.sin(t * 1.2)) * 4)
        cv2.putText(frame, "z", (cx + 20, cy - 18 - z_bob),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1)
        cv2.putText(frame, "z", (cx + 27, cy - 28 - z_bob),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1)

    elif state == "listening":
        # Alert open eyes with pupils
        cv2.circle(frame, (cx - 11, cy - 7), 5, color, -1)
        cv2.circle(frame, (cx + 11, cy - 7), 5, color, -1)
        cv2.circle(frame, (cx - 11, cy - 7), 2, (240, 240, 240), -1)
        cv2.circle(frame, (cx + 11, cy - 7), 2, (240, 240, 240), -1)
        # Small attentive mouth
        cv2.ellipse(frame, (cx, cy + 13), (8, 4), 0, 0, 360, color, 1)

    elif state == "error":
        # X eyes
        for dx in (-11, 11):
            cv2.line(frame, (cx + dx - 5, cy - 12), (cx + dx + 5, cy - 2), color, 2)
            cv2.line(frame, (cx + dx + 5, cy - 12), (cx + dx - 5, cy - 2), color, 2)
        # Sad downturned mouth
        cv2.ellipse(frame, (cx, cy + 18), (10, 6), 0, 180, 360, color, 2)


def _draw_sound_bars(frame, cx, cy, color, t):
    n = 7
    bar_w = 9
    gap = 5
    total_w = n * (bar_w + gap) - gap
    bx0 = cx - total_w // 2
    dim = tuple(int(c * 0.35) for c in color)

    for i in range(n):
        phase = t * 5.0 + i * 0.9
        bar_h = int(18 + abs(math.sin(phase)) * 50)
        bx = bx0 + i * (bar_w + gap)
        by_bot = cy + 32
        by_top = by_bot - bar_h

        # Glow behind bar
        cv2.rectangle(frame, (bx - 1, by_top - 1), (bx + bar_w + 1, by_bot), dim, -1)
        # Bar fill
        cv2.rectangle(frame, (bx, by_top), (bx + bar_w, by_bot), color, -1)
