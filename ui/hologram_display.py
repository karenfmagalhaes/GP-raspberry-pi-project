"""
ui/hologram_display.py
Clean hologram-style display for HoloBeat.

Adjusted for Raspberry Pi screen:
- shorter window height so bottom panels fit
- central hologram moved up slightly
- bottom panels moved up
- smaller title and text
- animated music wave included
"""

import math
import time

import cv2
import pygame


class HologramDisplay:
    W = 640
    H = 420

    _GESTURE_LABELS = {
        "open_palm":     "OPEN PALM",
        "fist":          "FIST",
        "three_fingers": "3 FINGERS",
        "peace":         "PEACE",
        "thumbs_up":     "THUMBS UP",
        "thumbs_down":   "THUMBS DN",
        "wake":          "WAKE",
    }

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

        self.font_big = pygame.font.SysFont("arial", 64, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 26, bold=True)
        self.font_small = pygame.font.SysFont("arial", 14, bold=True)
        self.font_tiny = pygame.font.SysFont("arial", 11)
        self.show_help = False
        self.font_help_title = pygame.font.SysFont("arial", 24, bold=True)
        self.font_help = pygame.font.SysFont("arial", 15, bold=True)

        self._camera_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._camera_overlay.fill((0, 8, 12, 120))
        self._panel_surfaces = {}

        self._help_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._help_overlay.fill((0, 0, 0, 210))
        self._help_panel = pygame.Surface((self.W - 140, self.H - 58), pygame.SRCALPHA)
        self._help_panel.fill((2, 8, 14, 235))

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
        camera_on=False,
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
            camera_on=camera_on,
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
                
                if event.key == pygame.K_g:
                    self.show_help = not self.show_help

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
        camera_on=False,
        wake_progress=0.0,
    ):
        self.screen.fill((0, 0, 0))

        if self.show_camera and frame_bgr is not None:
            self.draw_camera_background(frame_bgr)

        self.draw_grid()
        self.draw_hologram_frame()

        if time.time() - self.action_start_time > self.action_duration:
            self.current_action = "idle"

        if self.current_action == "idle":
            self.draw_idle_visualizer(state, wake_progress)
        else:
            self.draw_action()

        self.draw_top_title(state)
        self.draw_center_status(message)
        self.draw_system_status_panel(state)
        self.draw_gesture_panel(gesture, camera_on)

        if track:
            self.draw_track(track)
        
        self.draw_shortcuts()
        
        if self.show_help:
            self.draw_help_menu()
        
        pygame.display.flip()
        self.clock.tick(self.fps)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def draw_camera_background(self, frame_bgr):
        frame_bgr = cv2.resize(frame_bgr, (self.W, self.H))
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        surface = pygame.image.frombuffer(
            frame_rgb.tobytes(),
            (self.W, self.H),
            "RGB",
        )

        surface.set_alpha(58)
        self.screen.blit(surface, (0, 0))
        self.screen.blit(self._camera_overlay, (0, 0))

    def draw_grid(self):
        grid_color = (0, 60, 72)

        for x in range(0, self.W, 40):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, self.H), 1)

        for y in range(0, self.H, 40):
            pygame.draw.line(self.screen, grid_color, (0, y), (self.W, y), 1)

    def draw_hologram_frame(self):
        color = (0, 210, 255)
        magenta = (255, 60, 220)

        margin = 12
        length = 44

        corners = [
            ((margin, margin), (1, 1), color),
            ((self.W - margin, margin), (-1, 1), color),
            ((margin, self.H - margin), (1, -1), color),
            ((self.W - margin, self.H - margin), (-1, -1), magenta),
        ]

        for (x, y), (dx, dy), c in corners:
            pygame.draw.line(self.screen, c, (x, y), (x + length * dx, y), 2)
            pygame.draw.line(self.screen, c, (x, y), (x, y + length * dy), 2)

    # ------------------------------------------------------------------
    # Hologram centre
    # ------------------------------------------------------------------

    def draw_idle_visualizer(self, state, wake_progress):
        center_x = self.W // 2
        center_y = 188
        t = time.time()

        color = self.get_state_color(state)

        # Rotating particles.
        for i in range(24):
            angle = t * 1.6 + i * (math.pi * 2 / 24)
            radius = 82 + math.sin(t * 2.8 + i) * 8

            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius

            size = 2 + int(2 * (0.5 + 0.5 * math.sin(t * 3 + i)))

            particle_color = (255, 60, 220) if i % 4 == 0 else color

            pygame.draw.circle(
                self.screen,
                particle_color,
                (int(x), int(y)),
                size,
            )

        # Rings.
        pygame.draw.circle(self.screen, self.dim(color, 0.22), (center_x, center_y), 100, 1)
        pygame.draw.circle(self.screen, color, (center_x, center_y), 75, 2)
        pygame.draw.circle(self.screen, (245, 250, 255), (center_x, center_y), 42, 1)

        # Hologram base under orb.
        base_y = center_y + 88

        for r in [36, 25, 15]:
            pygame.draw.ellipse(
                self.screen,
                self.dim((0, 210, 255), 0.65),
                (
                    center_x - r,
                    base_y - int(r * 0.25),
                    r * 2,
                    int(r * 0.5),
                ),
                1,
            )

        pygame.draw.line(
            self.screen,
            self.dim((0, 210, 255), 0.55),
            (center_x, base_y),
            (center_x, center_y + 48),
            1,
        )

        if wake_progress > 0:
            self.draw_wake_arc(center_x, center_y, wake_progress, color)

        self.draw_center_text("♪", size="big", color=color, y=center_y)

    def draw_action(self):
        actions = {
            "play": "PLAY",
            "pause": "PAUSE",
            "next": "NEXT",
            "previous": "PREV",
            "volume_up": "VOL+",
            "volume_down": "VOL-",
            "error": "ERROR",
            "idle": "♪",
        }

        text = actions.get(self.current_action, "♪")

        if self.current_action == "error":
            color = (255, 85, 85)
        elif self.current_action in ("volume_up", "volume_down"):
            color = (255, 210, 80)
        elif self.current_action in ("play", "next", "previous"):
            color = (0, 255, 210)
        elif self.current_action == "pause":
            color = (230, 100, 255)
        else:
            color = (0, 255, 255)

        center_x = self.W // 2
        center_y = 188

        for radius, factor in [(100, 0.12), (78, 0.22), (58, 0.45)]:
            pygame.draw.circle(
                self.screen,
                self.dim(color, factor),
                (center_x, center_y),
                radius,
                2,
            )

        self.draw_center_text(text, size="medium", color=color, y=center_y)

    def draw_center_text(self, text, size="big", color=(0, 255, 255), y=None):
        if y is None:
            y = self.H // 2

        font = self.font_big if size == "big" else self.font_medium

        main_color = (245, 255, 255)
        glow_color = color

        text_surface = font.render(text, True, main_color)
        glow_surface = font.render(text, True, glow_color)

        rect = text_surface.get_rect(center=(self.W // 2, y))

        for offset in [6, 4, 2]:
            glow_rect = glow_surface.get_rect(
                center=(self.W // 2 + offset, y + offset)
            )
            self.screen.blit(glow_surface, glow_rect)

        self.screen.blit(text_surface, rect)

    def draw_wake_arc(self, cx, cy, progress, color):
        radius = 112
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
            pygame.draw.lines(self.screen, color, False, points, 3)

    # ------------------------------------------------------------------
    # UI text / panels
    # ------------------------------------------------------------------

    def draw_top_title(self, state):
        color = self.get_state_color(state)

        title = self.font_medium.render("HOLOBEAT", True, color)
        rect = title.get_rect(center=(self.W // 2, 28))
        self.screen.blit(title, rect)

        subtitle = self.font_small.render(
            "HOLOGRAPHIC MUSIC ASSISTANT",
            True,
            self.dim(color, 0.9),
        )
        sub_rect = subtitle.get_rect(center=(self.W // 2, 53))
        self.screen.blit(subtitle, sub_rect)

    def draw_center_status(self, message):
        msg = message if message else "Waiting for command."

        # Moved lower, but still above bottom panels.
        y = 315

        glow = self.font_small.render(msg[:44], True, (255, 60, 220))
        text = self.font_small.render(msg[:44], True, (0, 220, 255))

        glow_rect = glow.get_rect(center=(self.W // 2 + 1, y + 1))
        text_rect = text.get_rect(center=(self.W // 2, y))

        self.screen.blit(glow, glow_rect)
        self.screen.blit(text, text_rect)

    def draw_system_status_panel(self, state):
        x = 18
        y = 352
        w = 150
        h = 52

        self.draw_panel_box(x, y, w, h)

        label = self.font_tiny.render("SYSTEM STATUS", True, (180, 120, 255))
        self.screen.blit(label, (x + 10, y + 7))

        state_labels = {
            "standby":   ("STANDBY", (0, 200, 255)),
            "ready":     ("ACTIVE",  (80, 255, 140)),
            "executing": ("PLAYING", (255, 80, 230)),
            "error":     ("ERROR",   (255, 90, 90)),
        }
        status_text, color = state_labels.get(state, ("STANDBY", (0, 200, 255)))

        status = self.font_small.render(status_text, True, color)
        self.screen.blit(status, (x + 10, y + 23))

        pygame.draw.circle(self.screen, color, (x + w - 22, y + 28), 5)

    def draw_gesture_panel(self, gesture, camera_on):
        x = self.W - 168
        y = 352
        w = 150
        h = 52

        self.draw_panel_box(x, y, w, h)

        if gesture and gesture != "No hand":
            gesture_text = self._GESTURE_LABELS.get(gesture, gesture.upper()[:12])
        else:
            gesture_text = "WAITING"

        label = self.font_tiny.render("GESTURE", True, (80, 255, 140))
        self.screen.blit(label, (x + 10, y + 7))

        text = self.font_small.render(gesture_text, True, (80, 255, 140))
        self.screen.blit(text, (x + 10, y + 23))

        camera_text = "VIEW: ON" if camera_on else "VIEW: OFF"
        camera_surface = self.font_tiny.render(camera_text, True, (0, 220, 255))
        self.screen.blit(camera_surface, (x + 10, y + 39))

    def draw_track(self, track):
        w = 270
        h = 52
        x = (self.W - w) // 2
        y = 352

        self.draw_panel_box(x, y, w, h)

        label = self.font_tiny.render("NOW PLAYING", True, (255, 80, 220))
        self.screen.blit(label, (x + 10, y + 6))

        text = track

        if len(text) > 30:
            text = text[:28] + ".."

        surface = self.font_small.render(text, True, (0, 220, 255))
        self.screen.blit(surface, (x + 10, y + 21))

        self.draw_music_wave(x + 10, y + 45, w - 20)

    def draw_music_wave(self, x, y, width):
        t = time.time()

        bars = 36
        gap = 3
        bar_width = 2

        total_width = bars * (bar_width + gap)
        start_x = x + max(0, (width - total_width) // 2)

        for i in range(bars):
            bx = start_x + i * (bar_width + gap)
            height = int(3 + abs(math.sin(t * 5 + i * 0.45)) * 10)

            color = (255, 80, 220) if i % 4 == 0 else (0, 220, 255)

            pygame.draw.line(
                self.screen,
                color,
                (bx, y),
                (bx, y - height),
                bar_width,
            )

    def draw_panel_box(self, x, y, w, h):
        key = (w, h)

        if key not in self._panel_surfaces:
            surface = pygame.Surface((w, h), pygame.SRCALPHA)
            surface.fill((0, 0, 0, 175))
            self._panel_surfaces[key] = surface

        self.screen.blit(self._panel_surfaces[key], (x, y))

        pygame.draw.rect(self.screen, (255, 60, 220), (x, y, w, h), 1)
        pygame.draw.rect(
            self.screen,
            (0, 220, 255),
            (x + 3, y + 3, w - 6, h - 6),
            1,
        )

    # ------------------------------------------------------------------
    # Guide menu
    # ------------------------------------------------------------------

    def draw_shortcuts(self):
        text = "G: Guide   H: Camera   Q: Quit"
        surface = self.font_tiny.render(text, True, (120, 220, 235))
        self.screen.blit(surface, (18, 18))

    def draw_help_menu(self):
        self.screen.blit(self._help_overlay, (0, 0))

        x = 70
        y = 38
        w = self.W - 140
        h = self.H - 58

        self.screen.blit(self._help_panel, (x, y))

        pygame.draw.rect(self.screen, (0, 220, 255), (x, y, w, h), 2)
        pygame.draw.rect(
            self.screen,
            (255, 60, 220),
            (x + 5, y + 5, w - 10, h - 10),
            1,
        )

        title = self.font_help_title.render(
            "HOLOBEAT GESTURE GUIDE",
            True,
            (0, 220, 255),
        )
        title_rect = title.get_rect(center=(self.W // 2, y + 27))
        self.screen.blit(title, title_rect)

        lines = [
            ("ACTIVATE",      "Hold one finger up"),
            ("OPEN PALM",     "Play"),
            ("FIST",          "Pause"),
            ("THREE FINGERS", "Next track"),
            ("PEACE SIGN",    "Previous track"),
            ("THUMB UP",      "Volume up"),
            ("THUMB DOWN",    "Volume down"),
            ("H: VIEW ON",    "Camera background visible"),
            ("H: VIEW OFF",   "Background hidden, gestures active"),
        ]

        start_y = y + 60

        for i, (gesture_name, action) in enumerate(lines):
            row_y = start_y + i * 21
            colour = (255, 80, 220) if i in (1, 2, 3, 4, 5, 6) else (0, 220, 255)

            gesture_surface = self.font_help.render(gesture_name, True, colour)
            action_surface = self.font_help.render(action, True, (230, 240, 245))

            self.screen.blit(gesture_surface, (x + 32, row_y))
            self.screen.blit(action_surface, (x + 190, row_y))

        tips = [
            "Palm facing camera",
            "Hand fully visible",
            "Stay around 50-60 cm away",
            "Hold gesture still for 1 second",
        ]

        tip_y = start_y + len(lines) * 21 + 10

        for i, tip in enumerate(tips):
            surface = self.font_tiny.render(tip, True, (150, 220, 235))
            self.screen.blit(surface, (x + 32, tip_y + i * 15))

        footer = self.font_tiny.render(
            "Press G again to close this guide.",
            True,
            (255, 80, 220),
        )
        footer_rect = footer.get_rect(center=(self.W // 2, y + h - 14))
        self.screen.blit(footer, footer_rect)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_state_color(self, state):
        colors = {
            "standby":   (0, 210, 255),
            "ready":     (80, 255, 120),
            "executing": (255, 80, 230),
            "error":     (255, 80, 80),
        }

        return colors.get(state, colors["standby"])

    def dim(self, color, factor):
        return tuple(max(0, min(255, int(c * factor))) for c in color)
