"""
ui/hologram_display.py
HoloBeat hologram-style display.

This version creates a cleaner hologram interface:
- dark futuristic background
- rotating music particles
- glowing central action symbol
- camera/hologram body can appear faintly in the background
- gesture/action/track info stays visible
"""

import math
import time

import cv2
import pygame


class HologramDisplay:
    W = 640
    H = 480

    def __init__(self, fps=12, show_camera=True):
        pygame.init()

        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("HoloBeat")

        self.clock = pygame.time.Clock()
        self.fps = fps
        self.show_camera = show_camera

        self.current_action = "idle"
        self.action_start_time = time.time()
        self.action_duration = 1.5

        self.font_big = pygame.font.SysFont("arial", 92, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 34, bold=True)
        self.font_small = pygame.font.SysFont("arial", 18, bold=True)
        self.font_tiny = pygame.font.SysFont("arial", 14)

    # ------------------------------------------------------------------
    # Public API used by main.py
    # ------------------------------------------------------------------

    def draw(
        self,
        frame_bgr,
        state,
        message,
        gesture="",
        track="",
        body_on=False,
        wake_progress=0.0,
    ):
        if state == "executing":
            self.show_action_from_gesture(gesture)
        elif state == "error":
            self.show_action("error")

        self.update(
            frame_bgr=frame_bgr,
            state=state,
            message=message,
            gesture=gesture,
            track=track,
            body_on=body_on,
            wake_progress=wake_progress,
        )

    def poll(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    return "quit"

                if event.key == pygame.K_h:
                    return "toggle_body"

        return None

    def close(self):
        pygame.quit()

    # ------------------------------------------------------------------
    # Action state
    # ------------------------------------------------------------------

    def show_action(self, action):
        self.current_action = action
        self.action_start_time = time.time()

    def show_action_from_gesture(self, gesture):
        gesture_to_action = {
            "open_palm": "play",
            "fist": "pause",
            "three_fingers": "next",
            "peace": "previous",
            "thumbs_up": "volume_up",
            "thumbs_down": "volume_down",
        }

        action = gesture_to_action.get(gesture, "idle")
        self.show_action(action)

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update(
        self,
        frame_bgr=None,
        state="standby",
        message="",
        gesture="",
        track="",
        body_on=False,
        wake_progress=0.0,
    ):
        self.screen.fill((0, 0, 0))

        if self.show_camera and frame_bgr is not None:
            self.draw_camera_background(frame_bgr, body_on)

        self.draw_grid()
        self.draw_hologram_frame()

        if time.time() - self.action_start_time > self.action_duration:
            self.current_action = "idle"

        if self.current_action == "idle":
            self.draw_idle_visualizer(state, wake_progress)
        else:
            self.draw_action()

        self.draw_top_title(state)
        self.draw_status(message, gesture, body_on)

        if track:
            self.draw_track(track)

        pygame.display.flip()
        self.clock.tick(self.fps)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def draw_camera_background(self, frame_bgr, body_on):
        frame_bgr = cv2.resize(frame_bgr, (self.W, self.H))
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        surface = pygame.image.frombuffer(
            frame_rgb.tobytes(),
            (self.W, self.H),
            "RGB",
        )

        # Body hologram mode should be more visible.
        surface.set_alpha(95 if body_on else 38)
        self.screen.blit(surface, (0, 0))

    def draw_grid(self):
        grid_color = (0, 55, 65)

        for x in range(0, self.W, 40):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, self.H), 1)

        for y in range(0, self.H, 40):
            pygame.draw.line(self.screen, grid_color, (0, y), (self.W, y), 1)

    def draw_hologram_frame(self):
        color = (0, 160, 180)
        margin = 14
        length = 52

        corners = [
            ((margin, margin), (1, 1)),
            ((self.W - margin, margin), (-1, 1)),
            ((margin, self.H - margin), (1, -1)),
            ((self.W - margin, self.H - margin), (-1, -1)),
        ]

        for (x, y), (dx, dy) in corners:
            pygame.draw.line(
                self.screen,
                color,
                (x, y),
                (x + length * dx, y),
                2,
            )
            pygame.draw.line(
                self.screen,
                color,
                (x, y),
                (x, y + length * dy),
                2,
            )

    # ------------------------------------------------------------------
    # Hologram centre
    # ------------------------------------------------------------------

    def draw_idle_visualizer(self, state, wake_progress):
        center_x = self.W // 2
        center_y = self.H // 2
        t = time.time()

        color = self.get_state_color(state)

        # Rotating particles.
        for i in range(28):
            angle = t * 1.8 + i * (math.pi * 2 / 28)
            radius = 118 + math.sin(t * 3 + i) * 18

            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius

            size = 3 + int(2 * (0.5 + 0.5 * math.sin(t * 4 + i)))
            pygame.draw.circle(self.screen, color, (int(x), int(y)), size)

        # Outer rings.
        pygame.draw.circle(self.screen, self.dim(color, 0.35), (center_x, center_y), 124, 1)
        pygame.draw.circle(self.screen, color, (center_x, center_y), 92, 2)
        pygame.draw.circle(self.screen, (230, 255, 255), (center_x, center_y), 56, 1)

        # Wake progress arc.
        if wake_progress > 0:
            self.draw_wake_arc(center_x, center_y, wake_progress, color)

        self.draw_center_text("♪", size="big", color=color)

    def draw_action(self):
        actions = {
            "play": "PLAY",
            "pause": "PAUSE",
            "next": "NEXT",
            "previous": "PREV",
            "volume_up": "VOL +",
            "volume_down": "VOL -",
            "like": "LOVE",
            "error": "ERROR",
            "idle": "♪",
        }

        text = actions.get(self.current_action, "♪")

        if self.current_action == "error":
            color = (255, 70, 70)
        elif self.current_action in ("volume_up", "volume_down"):
            color = (255, 210, 60)
        elif self.current_action in ("play", "next", "previous"):
            color = (0, 255, 210)
        elif self.current_action == "pause":
            color = (210, 90, 255)
        else:
            color = (0, 255, 255)

        center_x = self.W // 2
        center_y = self.H // 2

        # Action glow circle.
        for radius, alpha_color in [
            (132, self.dim(color, 0.12)),
            (102, self.dim(color, 0.22)),
            (72, self.dim(color, 0.45)),
        ]:
            pygame.draw.circle(self.screen, alpha_color, (center_x, center_y), radius, 2)

        self.draw_center_text(text, size="medium", color=color)

    def draw_center_text(self, text, size="big", color=(0, 255, 255)):
        font = self.font_big if size == "big" else self.font_medium

        main_color = (245, 255, 255)
        glow_color = color

        text_surface = font.render(text, True, main_color)
        glow_surface = font.render(text, True, glow_color)

        rect = text_surface.get_rect(center=(self.W // 2, self.H // 2))

        # Glow effect.
        for offset in [8, 5, 3]:
            glow_rect = glow_surface.get_rect(
                center=(self.W // 2 + offset, self.H // 2 + offset)
            )
            self.screen.blit(glow_surface, glow_rect)

        self.screen.blit(text_surface, rect)

    def draw_wake_arc(self, cx, cy, progress, color):
        radius = 145
        start = -math.pi / 2
        end = start + 2 * math.pi * progress

        steps = max(2, int(100 * progress))
        points = []

        for i in range(steps + 1):
            angle = start + (end - start) * i / steps
            x = int(cx + math.cos(angle) * radius)
            y = int(cy + math.sin(angle) * radius)
            points.append((x, y))

        if len(points) > 1:
            pygame.draw.lines(self.screen, color, False, points, 4)

    # ------------------------------------------------------------------
    # UI text
    # ------------------------------------------------------------------

    def draw_top_title(self, state):
        color = self.get_state_color(state)

        title = self.font_small.render("HOLOBEAT", True, color)
        rect = title.get_rect(center=(self.W // 2, 28))
        self.screen.blit(title, rect)

        pygame.draw.line(
            self.screen,
            self.dim(color, 0.5),
            (self.W // 2 - 80, 44),
            (self.W // 2 + 80, 44),
            1,
        )

    def draw_status(self, message, gesture, body_on):
        y = self.H - 92

        if gesture and gesture != "No hand":
            gesture_text = f"Gesture: {gesture}"
        else:
            gesture_text = "Gesture: waiting"

        body_text = "Body hologram: ON" if body_on else "Body hologram: OFF"

        msg = message if message else "Waiting for command."

        lines = [
            gesture_text,
            body_text,
            msg,
        ]

        for i, line in enumerate(lines):
            surface = self.font_tiny.render(line[:70], True, (155, 175, 180))
            rect = surface.get_rect(center=(self.W // 2, y + i * 18))
            self.screen.blit(surface, rect)

    def draw_track(self, track):
        strip_h = 30
        y = self.H - strip_h

        strip = pygame.Surface((self.W, strip_h), pygame.SRCALPHA)
        strip.fill((0, 0, 0, 185))
        self.screen.blit(strip, (0, y))

        label = "Now playing: " + track
        if len(label) > 76:
            label = label[:74] + ".."

        surface = self.font_tiny.render(label, True, (170, 210, 215))
        self.screen.blit(surface, (14, y + 8))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_state_color(self, state):
        colors = {
            "standby": (0, 210, 255),
            "ready": (80, 255, 120),
            "executing": (255, 80, 230),
            "error": (255, 80, 80),
            "waiting": (0, 210, 255),
            "listening": (80, 255, 120),
            "acting": (255, 80, 230),
        }

        return colors.get(state, colors["standby"])

    def dim(self, color, factor):
        return tuple(max(0, min(255, int(c * factor))) for c in color)


