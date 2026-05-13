# ui/hologram_display.py
# Pygame fullscreen hologram display for WaveBeat.

import math
import time

import cv2
import pygame


class HologramDisplay:
    _GESTURE_LABELS = {
        "ok": "OK SIGN",
        "open_palm": "OPEN PALM",
        "fist": "FIST",
        "peace": "PEACE",
        "one_finger": "ONE FINGER",
        "one_finger_swipe_right": "FINGER RIGHT",
        "one_finger_swipe_left": "FINGER LEFT",
        "peace_move_up": "PEACE UP",
        "peace_move_down": "PEACE DOWN",
        "rock": "ROCK",
        "hand": "HAND",
    }

    def __init__(
        self,
        fps=12,
        show_camera=False,
        fullscreen=True,
        mirror_output=True,
    ):
        pygame.init()

        if fullscreen:
            self.display_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.W, self.H = self.display_surface.get_size()
            pygame.mouse.set_visible(False)
        else:
            self.W, self.H = 640, 420
            self.display_surface = pygame.display.set_mode((self.W, self.H))

        pygame.display.set_caption("WaveBeat")

        # Draw to hidden surface first, then optionally mirror for hologram.
        self.screen = pygame.Surface((self.W, self.H))
        self.mirror_output = mirror_output

        # Colours
        self.CYAN = (0, 230, 255)
        self.CYAN_SOFT = (90, 235, 255)
        self.MAGENTA = (255, 70, 220)
        self.GREEN = (80, 255, 140)
        self.YELLOW = (255, 220, 80)
        self.RED = (255, 90, 90)
        self.WHITE = (245, 255, 255)
        self.GREY = (170, 190, 200)
        self.DARK = (0, 0, 0)

        # Scale
        self.sx = self.W / 640
        self.sy = self.H / 420
        self.s = min(self.sx, self.sy)

        # Layout fixed for better fit on Pi screen/hologram box.
        self.cx = self.W // 2
        self.cy_orb = int(self.H * 0.420)
        self.cy_status = int(self.H * 0.695)

        self.panel_h = int(self.H * 0.145)

        # Put the bottom boxes down so they touch the bottom corner frame line.
        self.cy_panels = self.H - self._sc(14) - self.panel_h
        self.side_w = int(self.W * 0.250)
        self.center_w = int(self.W * 0.390)
        self.gap = int(self.W * 0.018)

        self.left_x = int(self.W * 0.025)
        self.center_x = (self.W - self.center_w) // 2
        self.right_x = self.W - self.side_w - int(self.W * 0.025)

        # Guide layout
        self._gw = int(self.W * 0.72)
        self._gh = int(self.H * 0.66)
        self._gx = (self.W - self._gw) // 2
        self._gy = (self.H - self._gh) // 2

        self.clock = pygame.time.Clock()
        self.fps = fps
        self.show_camera = show_camera

        self.current_action = "idle"
        self.action_start_time = time.time()
        self.action_duration = 2.2

        self.show_help = False

        def fs(ref):
            return max(9, int(ref * self.s))

        self.font_big = pygame.font.SysFont("arial", fs(74), bold=True)
        self.font_medium = pygame.font.SysFont("arial", fs(32), bold=True)
        self.font_small = pygame.font.SysFont("arial", fs(18), bold=True)
        self.font_tiny = pygame.font.SysFont("arial", fs(13), bold=True)

        self.font_g_title = pygame.font.SysFont("arial", fs(22), bold=True)
        self.font_g_sub = pygame.font.SysFont("arial", fs(11), bold=True)
        self.font_g_sec = pygame.font.SysFont("arial", fs(11), bold=True)
        self.font_g_row = pygame.font.SysFont("arial", fs(11), bold=True)
        self.font_g_tip = pygame.font.SysFont("arial", fs(9), bold=True)

        self._camera_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._camera_overlay.fill((0, 8, 12, 65))

        self._help_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._help_overlay.fill((0, 0, 0, 250))

        self._guide_panel = pygame.Surface((self._gw, self._gh), pygame.SRCALPHA)
        self._guide_panel.fill((4, 8, 12, 252))

        self._panel_surfaces = {}

    def _sc(self, value):
        return int(value * self.s)

    def _scx(self, value):
        return int(value * self.sx)

    def _scy(self, value):
        return int(value * self.sy)

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
            view_on=self.show_camera,
            wake_progress=wake_progress,
        )

    def poll(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    return "quit"

                if event.key == pygame.K_g:
                    self.show_help = not self.show_help

                if event.key == pygame.K_m:
                    self.mirror_output = not self.mirror_output
                    print(
                        f"[WaveBeat] Mirror output "
                        f"{'ON' if self.mirror_output else 'OFF'}"
                    )

        return None

    def close(self):
        pygame.quit()

    def show_action(self, action):
        self.current_action = action
        self.action_start_time = time.time()

    def show_action_from_gesture(self, gesture):
        gesture_to_action = {
            "open_palm": "play",
            "fist": "pause",
            "one_finger_swipe_right": "next",
            "one_finger_swipe_left": "previous",
            "peace_move_up": "volume_up",
            "peace_move_down": "volume_down",
            "rock": "view",
        }

        self.show_action(gesture_to_action.get(gesture, "idle"))

    def update(
        self,
        frame_bgr=None,
        state="standby",
        message="",
        gesture="",
        track="",
        view_on=False,
        wake_progress=0.0,
    ):
        self.screen.fill(self.DARK)

        if view_on and frame_bgr is not None:
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
        self.draw_track(track if track else "No track detected")
        self.draw_gesture_panel(gesture)

        self.draw_shortcuts()

        if self.show_help:
            self.draw_help_menu()

        if self.mirror_output:
            output_surface = pygame.transform.flip(self.screen, True, False)
        else:
            output_surface = self.screen

        self.display_surface.blit(output_surface, (0, 0))
        pygame.display.flip()
        self.clock.tick(self.fps)

    def draw_camera_background(self, frame_bgr):
        frame_bgr = cv2.resize(frame_bgr, (self.W, self.H))
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        surface = pygame.image.frombuffer(
            frame_rgb.tobytes(),
            (self.W, self.H),
            "RGB",
        )

        surface.set_alpha(115)
        self.screen.blit(surface, (0, 0))
        self.screen.blit(self._camera_overlay, (0, 0))

    def draw_grid(self):
        color = (0, 42, 55)
        step = max(24, self._sc(46))

        for x in range(0, self.W, step):
            pygame.draw.line(self.screen, color, (x, 0), (x, self.H), 1)

        for y in range(0, self.H, step):
            pygame.draw.line(self.screen, color, (0, y), (self.W, y), 1)

    def draw_hologram_frame(self):
        margin = self._sc(14)
        length = self._sc(50)

        corners = [
            ((margin, margin), (1, 1), self.MAGENTA),
            ((self.W - margin, margin), (-1, 1), self.CYAN),
            ((margin, self.H - margin), (1, -1), self.CYAN),
            ((self.W - margin, self.H - margin), (-1, -1), self.MAGENTA),
        ]

        for (x, y), (dx, dy), colour in corners:
            pygame.draw.line(self.screen, colour, (x, y), (x + length * dx, y), 3)
            pygame.draw.line(self.screen, colour, (x, y), (x, y + length * dy), 3)

    def draw_idle_visualizer(self, state, wake_progress):
        cx = self.cx
        cy = self.cy_orb
        t = time.time()

        color = self.get_state_color(state)
        base_r = self._sc(88)
        var_r = self._sc(9)

        for i in range(26):
            angle = t * 1.6 + i * (math.pi * 2 / 26)
            radius = base_r + math.sin(t * 2.8 + i) * var_r

            px = cx + math.cos(angle) * radius
            py = cy + math.sin(angle) * radius

            size = max(
                2,
                self._sc(3) + int(self._sc(2) * (0.5 + 0.5 * math.sin(t * 3 + i))),
            )

            particle_color = self.MAGENTA if i % 4 == 0 else color
            pygame.draw.circle(
                self.screen,
                particle_color,
                (int(px), int(py)),
                size,
            )

        pygame.draw.circle(self.screen, self.dim(color, 0.25), (cx, cy), self._sc(108), 2)
        pygame.draw.circle(self.screen, color, (cx, cy), self._sc(78), 3)
        pygame.draw.circle(self.screen, self.WHITE, (cx, cy), self._sc(42), 2)

        base_y = cy + self._scy(92)

        for r in [42, 30, 18]:
            sr = self._sc(r)
            pygame.draw.ellipse(
                self.screen,
                self.dim(self.CYAN, 0.75),
                (
                    cx - sr,
                    base_y - max(1, sr // 4),
                    sr * 2,
                    max(2, sr // 2),
                ),
                2,
            )

        pygame.draw.line(
            self.screen,
            self.dim(self.CYAN, 0.65),
            (cx, base_y),
            (cx, cy + self._scy(48)),
            2,
        )

        if wake_progress > 0:
            self.draw_wake_arc(cx, cy, wake_progress, color)

        self.draw_center_text("♪", size="big", color=color, y=cy)

    def draw_action(self):
        actions = {
            "play": "PLAY",
            "pause": "PAUSE",
            "next": "NEXT",
            "previous": "PREV",
            "volume_up": "VOL+",
            "volume_down": "VOL-",
            "error": "ERROR",
            "guide": "GUIDE",
            "view": "VIEW",
            "idle": "♪",
        }

        text = actions.get(self.current_action, "♪")

        if self.current_action == "error":
            color = self.RED
        elif self.current_action in ("volume_up", "volume_down"):
            color = self.YELLOW
        elif self.current_action in ("play", "next", "previous"):
            color = (0, 255, 210)
        elif self.current_action == "pause":
            color = (235, 120, 255)
        elif self.current_action == "view":
            color = self.CYAN_SOFT
        else:
            color = self.CYAN

        cx = self.cx
        cy = self.cy_orb

        for radius, factor in [(112, 0.15), (86, 0.28), (62, 0.50)]:
            pygame.draw.circle(
                self.screen,
                self.dim(color, factor),
                (cx, cy),
                self._sc(radius),
                3,
            )

        self.draw_center_text(text, size="big", color=color, y=cy)

    def draw_center_text(self, text, size="big", color=(0, 255, 255), y=None):
        if y is None:
            y = self.H // 2

        font = self.font_big if size == "big" else self.font_medium

        main_surf = font.render(text, True, self.WHITE)
        glow_surf = font.render(text, True, color)
        rect = main_surf.get_rect(center=(self.cx, y))

        for offset, alpha in [(8, 60), (5, 85), (3, 110)]:
            glow_surf.set_alpha(alpha)
            self.screen.blit(glow_surf, glow_surf.get_rect(center=(self.cx + offset, y + offset)))
            self.screen.blit(glow_surf, glow_surf.get_rect(center=(self.cx - offset, y - offset)))
            self.screen.blit(glow_surf, glow_surf.get_rect(center=(self.cx + offset, y - offset)))
            self.screen.blit(glow_surf, glow_surf.get_rect(center=(self.cx - offset, y + offset)))

        self.screen.blit(main_surf, rect)

    def draw_wake_arc(self, cx, cy, progress, color):
        radius = self._sc(116)
        start = -math.pi / 2
        end = start + 2 * math.pi * progress
        steps = max(2, int(100 * progress))

        points = []

        for i in range(steps + 1):
            angle = start + (end - start) * i / steps
            points.append(
                (
                    int(cx + math.cos(angle) * radius),
                    int(cy + math.sin(angle) * radius),
                )
            )

        if len(points) > 1:
            pygame.draw.lines(self.screen, color, False, points, 4)

    def draw_top_title(self, state):
        color = self.get_state_color(state)

        title = self.font_medium.render("WAVEBEAT", True, color)
        self.screen.blit(
            title,
            title.get_rect(center=(self.cx, self._scy(26))),
        )

        sub = self.font_tiny.render(
            "Spotify Gesture Controller",
            True,
            self.dim(self.WHITE, 0.82),
        )
        self.screen.blit(
            sub,
            sub.get_rect(center=(self.cx, self._scy(56))),
        )

    def draw_center_status(self, message):
        msg = (message if message else "Waiting for command.")[:38]
        y = self.cy_status

        glow = self.font_small.render(msg, True, self.MAGENTA)
        text = self.font_small.render(msg, True, self.CYAN_SOFT)

        self.screen.blit(glow, glow.get_rect(center=(self.cx + 2, y + 2)))
        self.screen.blit(text, text.get_rect(center=(self.cx, y)))

    def draw_system_status_panel(self, state):
        x = self.left_x
        y = self.cy_panels
        w = self.side_w
        h = self.panel_h

        self.draw_panel_box(x, y, w, h)

        self.screen.blit(
            self.font_tiny.render("SYSTEM", True, self.MAGENTA),
            (x + self._sc(10), y + self._sc(8)),
        )

        state_labels = {
            "standby": ("STANDBY", self.CYAN),
            "ready": ("ACTIVE", self.GREEN),
            "executing": ("RUNNING", self.MAGENTA),
            "error": ("ERROR", self.RED),
        }

        label, color = state_labels.get(state, ("STANDBY", self.CYAN))

        self.screen.blit(
            self.font_small.render(label, True, color),
            (x + self._sc(10), y + self._sc(34)),
        )

        pygame.draw.circle(
            self.screen,
            color,
            (x + w - self._sc(24), y + self._sc(42)),
            self._sc(7),
        )

    def draw_gesture_panel(self, gesture):
        x = self.right_x
        y = self.cy_panels
        w = self.side_w
        h = self.panel_h

        self.draw_panel_box(x, y, w, h)

        if gesture and gesture != "No hand":
            gesture_text = self._GESTURE_LABELS.get(gesture, gesture.upper()[:12])
        else:
            gesture_text = "WAITING"

        self.screen.blit(
            self.font_tiny.render("GESTURE", True, self.GREEN),
            (x + self._sc(10), y + self._sc(8)),
        )

        self.screen.blit(
            self.font_small.render(gesture_text, True, self.GREEN),
            (x + self._sc(10), y + self._sc(34)),
        )

    def draw_track(self, track):
        x = self.center_x
        y = self.cy_panels
        w = self.center_w
        h = self.panel_h

        self.draw_panel_box(x, y, w, h)

        self.screen.blit(
            self.font_tiny.render("NOW PLAYING", True, self.MAGENTA),
            (x + self._sc(10), y + self._sc(8)),
        )

        # Keep song name in the old style position.
        # Do not let the wave animation overlap it.
        text = track if track and len(track) <= 22 else (track[:20] + ".." if track else "No track")

        self.screen.blit(
            self.font_small.render(text, True, self.CYAN_SOFT),
            (x + self._sc(10), y + self._sc(30)),
        )

        # Wave stays low and short.
        self.draw_music_wave(
            x + self._sc(10),
            y + h - self._sc(10),
            w - self._sc(20),
        )

    def draw_music_wave(self, x, y, width):
        t = time.time()

        bar_w = max(2, self._sc(2))
        gap = max(2, self._sc(4))
        bars = max(10, width // (bar_w + gap))
        start_x = x + max(0, (width - bars * (bar_w + gap)) // 2)

        for i in range(bars):
            bx = start_x + i * (bar_w + gap)

            # Short bars only. This fixes the overlap.
            height = max(
                2,
                int((2 + abs(math.sin(t * 5 + i * 0.45)) * 4) * self.sy),
            )

            color = self.MAGENTA if i % 4 == 0 else self.CYAN
            pygame.draw.line(self.screen, color, (bx, y), (bx, y - height), bar_w)

    def draw_panel_box(self, x, y, w, h):
        key = (w, h)

        if key not in self._panel_surfaces:
            surface = pygame.Surface((w, h), pygame.SRCALPHA)
            surface.fill((0, 0, 0, 215))
            self._panel_surfaces[key] = surface

        self.screen.blit(self._panel_surfaces[key], (x, y))

        pygame.draw.rect(self.screen, self.MAGENTA, (x, y, w, h), 2)
        pygame.draw.rect(self.screen, self.CYAN, (x + 4, y + 4, w - 8, h - 8), 1)

    def draw_shortcuts(self):
        if self.show_help:
            return

        text = "G Guide   M Mirror   Q Quit"

        self.screen.blit(
            self.font_tiny.render(text, True, self.CYAN_SOFT),
            (self._scx(18), self._scy(18)),
        )

    def draw_help_menu(self):
        gx = self._gx
        gy = self._gy
        gw = self._gw
        gh = self._gh
        cx_g = gx + gw // 2

        self.screen.blit(self._help_overlay, (0, 0))
        self.screen.blit(self._guide_panel, (gx, gy))

        white = self.WHITE
        grey = self.GREY
        dim_grey = (120, 140, 150)

        pygame.draw.rect(self.screen, self.CYAN, (gx, gy, gw, gh), 3)

        pad_x = self._sc(28)
        pad_y = self._sc(16)

        left_x = gx + pad_x
        right_x = gx + gw // 2 + self._sc(18)

        left_action_x = left_x + int(gw * 0.25)
        right_action_x = right_x + int(gw * 0.23)

        top_y = gy + pad_y

        title = self.font_g_title.render("WAVEBEAT GUIDE", True, self.CYAN)
        self.screen.blit(
            title,
            title.get_rect(center=(cx_g, top_y + title.get_height() // 2)),
        )

        sub_y = top_y + title.get_height() + self._sc(4)
        subtitle = self.font_g_sub.render("Spotify Gesture Controller", True, grey)
        self.screen.blit(
            subtitle,
            subtitle.get_rect(center=(cx_g, sub_y + subtitle.get_height() // 2)),
        )

        line_y = sub_y + subtitle.get_height() + self._sc(10)
        pygame.draw.line(self.screen, self.CYAN, (left_x, line_y), (gx + gw - pad_x, line_y), 2)

        content_top = line_y + self._sc(13)

        footer_h = self._sc(38)
        footer_top = gy + gh - footer_h

        pygame.draw.line(
            self.screen,
            (0, 110, 130),
            (left_x, footer_top),
            (gx + gw - pad_x, footer_top),
            2,
        )

        row_gap = self._sc(20)
        section_gap = self._sc(11)

        def section_title(text, x, y):
            surf = self.font_g_sec.render(text, True, self.MAGENTA)
            self.screen.blit(surf, (x, y))
            return y + surf.get_height() + self._sc(7)

        def row(label, action, x1, x2, y):
            label_surf = self.font_g_row.render(label, True, white)
            action_surf = self.font_g_row.render(action, True, grey)

            self.screen.blit(label_surf, (x1, y))
            self.screen.blit(action_surf, (x2, y))

            return y + row_gap

        y = content_top

        y = section_title("ACTIVATION", left_x, y)
        y = row("OK sign", "Activate", left_x, left_action_x, y)

        y += section_gap

        y = section_title("MUSIC", left_x, y)
        y = row("Open palm", "Play", left_x, left_action_x, y)
        y = row("Fist", "Pause", left_x, left_action_x, y)
        y = row("One finger ->", "Next", left_x, left_action_x, y)
        y = row("One finger <-", "Previous", left_x, left_action_x, y)

        y = content_top

        y = section_title("VOLUME", right_x, y)
        y = row("Peace up", "Volume +", right_x, right_action_x, y)
        y = row("Peace down", "Volume -", right_x, right_action_x, y)

        y += section_gap

        y = section_title("SYSTEM", right_x, y)
        y = row("M", "Mirror mode", right_x, right_action_x, y)
        y = row("G", "Guide", right_x, right_action_x, y)
        y = row("Q / ESC", "Quit", right_x, right_action_x, y)

        tips = "Use large clear gestures  •  Press M if reflected text is backwards"
        tips_surf = self.font_g_tip.render(tips, True, dim_grey)

        self.screen.blit(
            tips_surf,
            tips_surf.get_rect(center=(cx_g, footer_top + self._sc(13))),
        )

        close = self.font_g_tip.render("Press G to close guide", True, grey)

        self.screen.blit(
            close,
            close.get_rect(center=(cx_g, footer_top + self._sc(29))),
        )

    def get_state_color(self, state):
        return {
            "standby": self.CYAN,
            "ready": self.GREEN,
            "executing": self.MAGENTA,
            "error": self.RED,
        }.get(state, self.CYAN)

    def dim(self, color, factor):
        return tuple(max(0, min(255, int(c * factor))) for c in color)
