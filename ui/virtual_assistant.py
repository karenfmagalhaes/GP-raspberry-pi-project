import cv2
import math
import time

# Soft, non-neon colors (BGR).
_STATE_COLORS = {
    "standby":   (130, 100,  70),   # steel blue-grey
    "ready":     (70,  185,  80),   # soft green
    "executing": (175,  55, 155),   # soft purple
    "error":     (50,   50, 195),   # soft red
    # backward-compat aliases
    "waiting":   (130, 100,  70),
    "watching":  (130, 100,  70),
    "listening": (70,  185,  80),
    "acting":    (175,  55, 155),
    "action":    (175,  55, 155),
    "sleeping":  (130, 100,  70),
}

_PANEL_W = 155
_PANEL_H = 178
_MARGIN  = 10
_NOW_H   = 28     # now-playing strip height


def get_state_color(state):
    return _STATE_COLORS.get(state, _STATE_COLORS["standby"])


def draw_virtual_assistant(frame, state, message, gesture="", action="", track="",
                           name="HoloBeat", wake_progress=0.0):
    t = time.time()
    h, w = frame.shape[:2]
    color = get_state_color(state)
    dim   = tuple(int(c * 0.38) for c in color)

    _draw_panel(frame, w, color, dim, state, message, name, t, wake_progress)

    if track:
        _draw_now_playing(frame, h, w, track, color, dim)

    return frame


# ---------------------------------------------------------------------------
# HoloBeat panel — top-right corner
# ---------------------------------------------------------------------------

def _draw_panel(frame, w, color, dim, state, message, name, t, wake_progress):
    px = w - _PANEL_W - _MARGIN
    py = _MARGIN

    # Dark glass background
    bg = frame.copy()
    cv2.rectangle(bg, (px, py), (px + _PANEL_W, py + _PANEL_H), (8, 8, 12), -1)
    cv2.addWeighted(bg, 0.84, frame, 0.16, 0, frame)

    # Outer border (subtle)
    cv2.rectangle(frame, (px, py), (px + _PANEL_W, py + _PANEL_H), dim, 1)

    # Top accent line (state color, thin)
    cv2.line(frame, (px, py), (px + _PANEL_W, py), color, 2)

    # Title
    cv2.putText(frame, name.upper(), (px + 10, py + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    # Thin divider below title
    cv2.line(frame, (px + 8, py + 29), (px + _PANEL_W - 8, py + 29), dim, 1)

    # State label
    cv2.putText(frame, state.upper(), (px + 10, py + 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.34, color, 1, cv2.LINE_AA)

    # Central graphic
    cx = px + _PANEL_W // 2
    cy = py + 105

    if state == "executing":
        _draw_bars(frame, cx, cy, color, dim, t)
    else:
        _draw_orb(frame, cx, cy, color, dim, state, t)

    # Message text (2 lines max, wrapped)
    lines = _wrap(message, 19)
    for i, line in enumerate(lines[:2]):
        cv2.putText(frame, line, (px + 10, py + 145 + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.31, (165, 165, 165), 1, cv2.LINE_AA)

    # Wake progress bar — fills along the panel bottom
    if wake_progress > 0.0:
        bar_w = int((_PANEL_W - 2) * wake_progress)
        cv2.rectangle(frame,
                      (px + 1, py + _PANEL_H - 4),
                      (px + 1 + bar_w, py + _PANEL_H - 1),
                      color, -1)


def _draw_orb(frame, cx, cy, color, dim, state, t):
    speed = 2.0 if state == "ready" else 0.8
    pulse = 0.5 + 0.5 * math.sin(t * speed)

    # Single expanding ring (ready only)
    if state == "ready":
        phase    = (t * 1.6) % 1.0
        r_ring   = int(24 + phase * 16)
        fade_col = tuple(int(c * (1.0 - phase) * 0.55) for c in color)
        cv2.circle(frame, (cx, cy), r_ring, fade_col, 1)

    # Outer static ring
    cv2.circle(frame, (cx, cy), 24, dim, 1)

    # Inner breathing fill
    r_inner = int(12 + pulse * 6)
    cv2.circle(frame, (cx, cy), r_inner, dim, -1)
    cv2.circle(frame, (cx, cy), r_inner, color, 1)


def _draw_bars(frame, cx, cy, color, dim, t):
    n = 5
    bar_w, gap = 7, 5
    total_w = n * (bar_w + gap) - gap
    bx0 = cx - total_w // 2

    for i in range(n):
        h_bar = int(8 + abs(math.sin(t * 4.0 + i * 0.9)) * 26)
        bx     = bx0 + i * (bar_w + gap)
        by_bot = cy + 16
        by_top = by_bot - h_bar
        cv2.rectangle(frame, (bx, by_top), (bx + bar_w, by_bot), dim, -1)
        cv2.rectangle(frame, (bx, by_top), (bx + bar_w, by_bot), color, 1)


# ---------------------------------------------------------------------------
# Now-playing strip — bottom of frame
# ---------------------------------------------------------------------------

def _draw_now_playing(frame, h, w, track, color, dim):
    y0 = h - _NOW_H

    bg = frame.copy()
    cv2.rectangle(bg, (0, y0), (w, h), (6, 6, 10), -1)
    cv2.addWeighted(bg, 0.78, frame, 0.22, 0, frame)

    cv2.line(frame, (0, y0), (w, y0), dim, 1)

    label = "Now:  " + (track if len(track) <= 60 else track[:58] + "..")
    cv2.putText(frame, label, (14, y0 + 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (160, 160, 160), 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wrap(text, max_chars):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        if len(cur) + len(word) + (1 if cur else 0) <= max_chars:
            cur = (cur + " " + word).strip() if cur else word
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines
