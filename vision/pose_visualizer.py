"""
vision/pose_visualizer.py
Holographic body renderer for HoloBeat.

This version makes the hologram look more like a coloured body-shaped
virtual assistant instead of only dark skeleton lines.

Main idea:
- Keep the real camera visible.
- Use MediaPipe pose segmentation to colour the person's body shape.
- Add neon body outline, glowing joints, hand glow, and subtle HUD grid.
"""

import time

import cv2
import mediapipe as mp
import numpy as np


_FACE_IDX = set(range(11))
_WRISTS = {15, 16}

_MAJOR_JOINTS = {
    11, 12, 13, 14,
    23, 24, 25, 26
}

_BODY_CONNECTIONS = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28),
    (15, 17), (15, 19), (15, 21),
    (16, 18), (16, 20), (16, 22),
]

_BODY_JOINTS = list(range(11, 33))


# BGR colours for OpenCV
_PALETTE = {
    "standby": {
        "body": (255, 160, 40),      # cyan/blue
        "edge": (255, 240, 120),
        "skel": (255, 210, 40),
        "joint": (255, 255, 190),
        "hand": (255, 50, 255),      # magenta
        "grid": (35, 22, 10),
        "hud": (255, 130, 40),
    },
    "ready": {
        "body": (80, 255, 120),      # green
        "edge": (150, 255, 180),
        "skel": (80, 255, 130),
        "joint": (210, 255, 220),
        "hand": (0, 230, 255),       # yellow/cyan
        "grid": (8, 35, 12),
        "hud": (60, 255, 100),
    },
    "executing": {
        "body": (255, 60, 210),      # purple/pink
        "edge": (255, 150, 255),
        "skel": (255, 60, 220),
        "joint": (255, 190, 255),
        "hand": (0, 230, 255),
        "grid": (28, 8, 26),
        "hud": (255, 60, 220),
    },
    "error": {
        "body": (50, 50, 255),       # red
        "edge": (120, 120, 255),
        "skel": (50, 50, 255),
        "joint": (190, 190, 255),
        "hand": (0, 160, 255),
        "grid": (8, 8, 32),
        "hud": (50, 50, 255),
    },
}

_ALIAS = {
    "waiting": "standby",
    "watching": "standby",
    "sleeping": "standby",
    "listening": "ready",
    "acting": "executing",
    "action": "executing",
}


def _palette(state):
    return _PALETTE.get(_ALIAS.get(state, state), _PALETTE["standby"])


def _dim_colour(colour, scale):
    return tuple(max(0, min(255, int(c * scale))) for c in colour)


def _glow_line(img, p1, p2, colour, thickness=2):
    if p1 is None or p2 is None:
        return

    cv2.line(img, p1, p2, _dim_colour(colour, 0.14), thickness * 8, cv2.LINE_AA)
    cv2.line(img, p1, p2, _dim_colour(colour, 0.35), thickness * 4, cv2.LINE_AA)
    cv2.line(img, p1, p2, _dim_colour(colour, 0.75), thickness * 2, cv2.LINE_AA)
    cv2.line(img, p1, p2, colour, thickness, cv2.LINE_AA)


def _glow_dot(img, center, radius, colour):
    if center is None:
        return

    cv2.circle(img, center, radius * 4, _dim_colour(colour, 0.12), -1)
    cv2.circle(img, center, radius * 2, _dim_colour(colour, 0.35), -1)
    cv2.circle(img, center, radius, colour, -1)
    cv2.circle(img, center, max(2, radius // 2), (245, 245, 245), -1)


def _hand_glow(img, center, colour):
    if center is None:
        return

    cv2.circle(img, center, 58, _dim_colour(colour, 0.10), -1)
    cv2.circle(img, center, 38, _dim_colour(colour, 0.25), -1)
    cv2.circle(img, center, 22, _dim_colour(colour, 0.60), -1)
    cv2.circle(img, center, 12, colour, -1)
    cv2.circle(img, center, 5, (255, 255, 255), -1)


def _draw_grid(img, colour):
    h, w = img.shape[:2]

    grid_colour = _dim_colour(colour, 0.55)
    step = 48

    for x in range(0, w, step):
        cv2.line(img, (x, 0), (x, h), grid_colour, 1)

    for y in range(0, h, step):
        cv2.line(img, (0, y), (w, y), grid_colour, 1)


def _draw_scanlines(img):
    h, w = img.shape[:2]
    overlay = np.zeros_like(img)

    for y in range(0, h, 6):
        cv2.line(overlay, (0, y), (w, y), (255, 255, 255), 1)

    cv2.addWeighted(img, 1.0, overlay, 0.025, 0, img)


def _draw_hud_corners(img, colour):
    h, w = img.shape[:2]
    length = 42
    margin = 10

    points = [
        ((margin, margin), (1, 1)),
        ((w - margin, margin), (-1, 1)),
        ((margin, h - margin), (1, -1)),
        ((w - margin, h - margin), (-1, -1)),
    ]

    for (x, y), (dx, dy) in points:
        cv2.line(img, (x, y), (x + length * dx, y), colour, 2, cv2.LINE_AA)
        cv2.line(img, (x, y), (x, y + length * dy), colour, 2, cv2.LINE_AA)


def _apply_body_silhouette(img, segmentation_mask, body_colour, edge_colour):
    """
    Colours the person's full body shape using MediaPipe segmentation.
    This is what makes the assistant look body-shaped, not only skeleton-shaped.
    """
    if segmentation_mask is None:
        return img

    mask = segmentation_mask.astype(np.float32)
    mask = cv2.GaussianBlur(mask, (21, 21), 0)

    alpha = np.clip((mask - 0.22) / 0.55, 0.0, 1.0)
    alpha = alpha * 0.42
    alpha_3 = alpha[:, :, None]

    colour_layer = np.full_like(img, body_colour, dtype=np.uint8)

    blended = (
        img.astype(np.float32) * (1.0 - alpha_3) +
        colour_layer.astype(np.float32) * alpha_3
    ).astype(np.uint8)

    img[:] = blended

    # Body outline glow from the segmentation mask.
    body_mask = (mask > 0.25).astype(np.uint8) * 255
    edges = cv2.Canny(body_mask, 50, 130)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    glow = np.zeros_like(img)
    glow[edges > 0] = edge_colour

    glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=5, sigmaY=5)
    cv2.addWeighted(img, 1.0, glow, 0.85, 0, img)

    img[edges > 0] = edge_colour

    return img


class PoseVisualizer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils

        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            enable_segmentation=True,
            smooth_segmentation=True,
            min_detection_confidence=0.55,
            min_tracking_confidence=0.55,
        )

        # Motion trails for wrists.
        self._trails = {
            15: [],
            16: [],
        }

    def process(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.pose.process(rgb)
        rgb.flags.writeable = True
        return results

    def draw_hologram_body(self, frame, results, state="standby"):
        h, w = frame.shape[:2]
        p = _palette(state)

        # Keep the camera visible. Old version was too dark at alpha=0.12.
        out = cv2.convertScaleAbs(frame, alpha=0.42, beta=-8)

        # Soft blue/purple futuristic tint.
        tint = np.zeros_like(out)
        tint[:, :, 0] = 22
        tint[:, :, 1] = 8
        cv2.add(out, tint, out)

        _draw_grid(out, p["grid"])
        _draw_scanlines(out)
        _draw_hud_corners(out, p["hud"])

        if results is None:
            return out

        # Colour the full body silhouette if MediaPipe segmentation is available.
        segmentation_mask = getattr(results, "segmentation_mask", None)
        out = _apply_body_silhouette(
            out,
            segmentation_mask,
            p["body"],
            p["edge"],
        )

        if not results.pose_landmarks:
            return out

        landmarks = results.pose_landmarks.landmark
        now = time.time()

        def point(index, min_visibility=0.35):
            lm = landmarks[index]

            if lm.visibility < min_visibility:
                return None

            return (
                int(lm.x * w),
                int(lm.y * h),
            )

        # Neon skeleton.
        for a, b in _BODY_CONNECTIONS:
            _glow_line(
                out,
                point(a),
                point(b),
                p["skel"],
                thickness=2,
            )

        # Glowing joints.
        for index in _BODY_JOINTS:
            if index in _WRISTS:
                continue

            pos = point(index)

            if pos:
                radius = 8 if index in _MAJOR_JOINTS else 5
                _glow_dot(out, pos, radius, p["joint"])

        # Hand glow and trails.
        for wrist_index in (15, 16):
            wrist = point(wrist_index)
            trail = self._trails[wrist_index]

            if wrist:
                trail.append((wrist[0], wrist[1], now))

            # Keep recent trail only.
            trail[:] = [
                (x, y, t)
                for x, y, t in trail
                if now - t < 0.40
            ]

            if len(trail) > 10:
                trail[:] = trail[-10:]

            # Draw trail.
            for i in range(1, len(trail)):
                ratio = i / len(trail)
                colour = _dim_colour(p["hand"], 0.25 + 0.55 * ratio)
                thickness = max(1, int(6 * ratio))

                x0, y0, _ = trail[i - 1]
                x1, y1, _ = trail[i]

                cv2.line(
                    out,
                    (x0, y0),
                    (x1, y1),
                    colour,
                    thickness,
                    cv2.LINE_AA,
                )

            if wrist:
                _hand_glow(out, wrist, p["hand"])

        return out

    def draw_glow_pose(self, frame, results, glow_color=(255, 80, 220)):
        if not results or not results.pose_landmarks:
            return frame

        h, w = frame.shape[:2]
        landmarks = results.pose_landmarks.landmark

        for start_index, end_index in self.mp_pose.POSE_CONNECTIONS:
            if start_index in _FACE_IDX or end_index in _FACE_IDX:
                continue

            start = landmarks[start_index]
            end = landmarks[end_index]

            if start.visibility < 0.55 or end.visibility < 0.55:
                continue

            p1 = (int(start.x * w), int(start.y * h))
            p2 = (int(end.x * w), int(end.y * h))

            _glow_line(frame, p1, p2, glow_color, thickness=2)

        return frame

    def draw_normal_pose(self, frame, results):
        if not results or not results.pose_landmarks:
            return frame

        self.mp_draw.draw_landmarks(
            frame,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
        )

        return frame

    def close(self):
        self.pose.close()
