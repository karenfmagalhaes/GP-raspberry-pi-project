"""
vision/pose_visualizer.py
Holographic body renderer for HoloBeat.

draw_hologram_body()
  Full transformation: darkens the camera frame to ~12 % brightness,
  overlays a neon glow skeleton, glowing joints, transparent torso fill,
  large pulsing hand auras with motion trails, and a subtle HUD frame.

draw_glow_pose()
  Lightweight single-color glow skeleton — kept for backward compatibility.
"""

import time
import cv2
import mediapipe as mp
import numpy as np

# ---------------------------------------------------------------------------
# Landmark groups
# ---------------------------------------------------------------------------
_FACE_IDX    = set(range(11))          # skip face — no lines on the face
_WRISTS      = {15, 16}                # handled separately with hand glow
_MAJOR_JTS   = {11, 12, 13, 14,        # shoulders, elbows
                23, 24, 25, 26}        # hips, knees

# Body-only connections (no face, includes hand spokes for glow detail).
_CONNECTIONS = [
    (11, 12),                          # collar line
    (11, 13), (13, 15),                # left arm
    (12, 14), (14, 16),                # right arm
    (11, 23), (12, 24),                # torso sides
    (23, 24),                          # hip line
    (23, 25), (25, 27),                # left leg
    (24, 26), (26, 28),                # right leg
    (15, 17), (15, 19), (15, 21),      # left hand spokes
    (16, 18), (16, 20), (16, 22),      # right hand spokes
    (27, 31), (28, 32),                # feet (optional — skipped if invisible)
]

# All body joints to mark (11-32, wrists excluded from normal flow).
_JOINTS = list(range(11, 33))

# ---------------------------------------------------------------------------
# Hologram color palettes  (BGR – OpenCV)
# ---------------------------------------------------------------------------
_PALETTE = {
    "standby": {
        "skel":  (255, 230,   0),   # vivid cyan
        "fill":  ( 58,  46,   0),   # dim cyan  (torso fill)
        "joint": (255, 255, 145),   # cyan-white
        "hand":  (215,  18, 255),   # purple-magenta  (contrasts with cyan)
        "acnt":  (175,   0, 210),   # magenta  (HUD corners)
        "grid":  ( 16,   7,   0),   # barely-there cyan grid
    },
    "ready": {
        "skel":  ( 28, 242,  78),   # neon green
        "fill":  (  8,  68,  18),
        "joint": ( 88, 255, 148),
        "hand":  ( 18, 228, 255),   # warm yellow-amber  (contrast)
        "acnt":  (  0, 175,  78),
        "grid":  (  0,  11,   4),
    },
    "executing": {
        "skel":  (248,  32, 198),   # electric purple
        "fill":  ( 92,  10,  72),
        "joint": (255, 118, 238),
        "hand":  (  0, 218, 255),   # warm yellow  (contrast)
        "acnt":  (192,   0, 172),
        "grid":  (  8,   1,   6),
    },
    "error": {
        "skel":  ( 32,  32, 248),   # bright red
        "fill":  ( 11,  11,  88),
        "joint": ( 78,  78, 255),
        "hand":  ( 14, 188, 255),   # warm orange
        "acnt":  (  0,  52, 196),
        "grid":  (  1,   1,  10),
    },
}

_ALIAS = {
    "waiting": "standby", "watching": "standby", "sleeping": "standby",
    "listening": "ready",
    "acting": "executing", "action": "executing",
}


def _pal(state):
    return _PALETTE.get(_ALIAS.get(state, state), _PALETTE["standby"])


# ---------------------------------------------------------------------------
# Low-level glow primitives  (module-level for speed — no self overhead)
# ---------------------------------------------------------------------------

def _glow_line(img, p1, p2, color, base_t=3):
    """Four-layer neon glow line: wide dim → medium → bright → crisp core."""
    if p1 is None or p2 is None:
        return
    c1 = tuple(max(0, int(c * 0.08)) for c in color)
    c2 = tuple(max(0, int(c * 0.28)) for c in color)
    c3 = tuple(max(0, int(c * 0.62)) for c in color)
    cv2.line(img, p1, p2, c1, base_t * 9)
    cv2.line(img, p1, p2, c2, base_t * 4)
    cv2.line(img, p1, p2, c3, base_t + 2)
    cv2.line(img, p1, p2, color, max(1, base_t - 1), cv2.LINE_AA)


def _glow_dot(img, center, radius, color):
    """Three-layer glow circle with bright white core."""
    if center is None:
        return
    c1 = tuple(max(0, int(c * 0.09)) for c in color)
    c2 = tuple(max(0, int(c * 0.36)) for c in color)
    cv2.circle(img, center, radius * 4, c1, -1)
    cv2.circle(img, center, radius * 2, c2, -1)
    cv2.circle(img, center, radius,     color, -1)
    core = tuple(min(255, int(c * 0.65 + 80)) for c in color)
    cv2.circle(img, center, max(1, radius // 2), core, -1)


def _hand_glow(img, center, color):
    """Large multi-layer aura — makes hands the brightest feature."""
    c1 = tuple(max(0, int(c * 0.07)) for c in color)
    c2 = tuple(max(0, int(c * 0.20)) for c in color)
    c3 = tuple(max(0, int(c * 0.52)) for c in color)
    cv2.circle(img, center, 60, c1, -1)
    cv2.circle(img, center, 38, c2, -1)
    cv2.circle(img, center, 22, c3, -1)
    cv2.circle(img, center, 11, color,      -1)
    cv2.circle(img, center,  5, (215, 215, 215), -1)   # white core


def _torso_fill(img, pts, fill_color):
    """Semi-transparent filled torso polygon."""
    if any(p is None for p in pts):
        return
    poly  = np.array(pts, dtype=np.int32)
    layer = np.zeros_like(img)
    cv2.fillPoly(layer, [poly], fill_color)
    cv2.addWeighted(img, 1.0, layer, 0.72, 0, img)


def _bg_grid(img, w, h, color):
    step = 42
    for x in range(0, w + 1, step):
        cv2.line(img, (x, 0), (x, h), color, 1)
    for y in range(0, h + 1, step):
        cv2.line(img, (0, y), (w, y), color, 1)


def _hud_corners(img, w, h, color):
    """Corner brackets — gives a scanning HUD feel."""
    dim = tuple(max(0, int(c * 0.22)) for c in color)
    L = 34
    for (cx, cy), (dx, dy) in [
        ((  0,   0), ( 1,  1)),
        ((w-1,   0), (-1,  1)),
        ((  0, h-1), ( 1, -1)),
        ((w-1, h-1), (-1, -1)),
    ]:
        cv2.line(img, (cx, cy), (cx + (L + 8) * dx, cy),          dim,   3)
        cv2.line(img, (cx, cy), (cx,          cy + (L + 8) * dy), dim,   3)
        cv2.line(img, (cx, cy), (cx + L * dx, cy),                 color, 1)
        cv2.line(img, (cx, cy), (cx,          cy + L * dy),        color, 1)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PoseVisualizer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils

        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=False,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )

        # Motion-trail buffers for both wrists.
        # Each entry: (x, y, timestamp)
        self._trails: dict = {15: [], 16: []}

    def process(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.pose.process(rgb)
        rgb.flags.writeable = True
        return results

    # ------------------------------------------------------------------
    # Full hologram transformation
    # ------------------------------------------------------------------

    def draw_hologram_body(self, frame, results, state="standby"):
        """
        Transforms the camera frame into a holographic body figure.

        Steps
        -----
        1  Darken the whole frame to ~12 % + add a blue-teal tint.
        2  Draw a subtle grid texture.
        3  Draw HUD corner brackets.
        4  (if pose detected)
           a  Semi-transparent torso fill.
           b  Four-layer glow skeleton.
           c  Glowing joints.
           d  Hand motion trails.
           e  Large hand-aura glow.

        Returns the transformed frame (new array, does not modify input).
        """
        h, w = frame.shape[:2]
        p = _pal(state)

        # --- 1. Dark + tinted background ---------------------------------
        out = cv2.convertScaleAbs(frame, alpha=0.12, beta=0)
        tint = np.zeros_like(out)
        tint[:, :, 0] = 20   # blue channel boost
        tint[:, :, 1] =  8   # green channel boost
        cv2.add(out, tint, out)

        # --- 2. Background grid ------------------------------------------
        _bg_grid(out, w, h, p["grid"])

        # --- 3. HUD corner brackets --------------------------------------
        _hud_corners(out, w, h, p["acnt"])

        # --- No pose detected: return atmospheric background only --------
        if results is None or not results.pose_landmarks:
            return out

        lm = results.pose_landmarks.landmark
        now = time.time()

        def pt(idx, min_vis=0.38):
            l = lm[idx]
            return (int(l.x * w), int(l.y * h)) if l.visibility >= min_vis else None

        # --- 4a. Torso fill ----------------------------------------------
        _torso_fill(
            out,
            [pt(11), pt(12), pt(24), pt(23)],  # L-shoulder, R-shoulder, R-hip, L-hip
            p["fill"],
        )

        # --- 4b. Glow skeleton -------------------------------------------
        for a, b in _CONNECTIONS:
            _glow_line(out, pt(a), pt(b), p["skel"], base_t=3)

        # --- 4c. Joint dots (skip wrists — they get hand treatment) ------
        for idx in _JOINTS:
            if idx in _WRISTS:
                continue
            pos = pt(idx)
            if pos:
                r = 9 if idx in _MAJOR_JTS else 5
                _glow_dot(out, pos, r, p["joint"])

        # --- 4d & 4e. Hands: trails + aura glow --------------------------
        for wrist_idx in (15, 16):
            wrist = pt(wrist_idx)
            trail = self._trails[wrist_idx]

            # Update trail.
            if wrist:
                trail.append((wrist[0], wrist[1], now))
            # Drop old trail points (keep last 0.45 s).
            trail[:] = [(x, y, t) for x, y, t in trail if now - t < 0.45]
            if len(trail) > 10:
                trail[:] = trail[-10:]

            # Draw motion streak.
            n = len(trail)
            for i in range(1, n):
                ratio = i / n
                tc    = tuple(int(v * ratio * 0.55) for v in p["hand"])
                thick = max(1, int(6 * ratio))
                x0, y0, _ = trail[i - 1]
                x1, y1, _ = trail[i]
                cv2.line(out, (x0, y0), (x1, y1), tc, thick, cv2.LINE_AA)

            # Draw large hand glow.
            if wrist:
                _hand_glow(out, wrist, p["hand"])

        return out

    # ------------------------------------------------------------------
    # Lightweight glow skeleton  (kept for backward compatibility)
    # ------------------------------------------------------------------

    def draw_glow_pose(self, frame, results, glow_color=(130, 100, 70)):
        if not results or not results.pose_landmarks:
            return frame

        h, w = frame.shape[:2]
        lm  = results.pose_landmarks.landmark
        dim = tuple(int(c * 0.28) for c in glow_color)

        for s_idx, e_idx in self.mp_pose.POSE_CONNECTIONS:
            if s_idx in _FACE_IDX or e_idx in _FACE_IDX:
                continue
            s, e = lm[s_idx], lm[e_idx]
            if s.visibility < 0.55 or e.visibility < 0.55:
                continue
            p1 = (int(s.x * w), int(s.y * h))
            p2 = (int(e.x * w), int(e.y * h))
            cv2.line(frame, p1, p2, dim,        6)
            cv2.line(frame, p1, p2, glow_color, 1)

        return frame

    def draw_normal_pose(self, frame, results):
        if not results or not results.pose_landmarks:
            return frame
        self.mp_draw.draw_landmarks(
            frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS
        )
        return frame

    def close(self):
        self.pose.close()
