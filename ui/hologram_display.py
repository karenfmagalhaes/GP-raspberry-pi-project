"""
ui/hologram_display.py
Hologram-style display for WaveBeat.

All layout values are derived from two scale factors (sx, sy) so the
interface adapts to any screen resolution — including Pi fullscreen.
"""

import math
import time

import cv2
import pygame


class HologramDisplay:

    _GESTURE_LABELS = {
        "ok":                     "OK SIGN",
        "open_palm":              "OPEN PALM",
        "fist":                   "FIST",
        "peace":                  "PEACE",
        "one_finger":             "ONE FINGER",
        "one_finger_swipe_right": "FINGER RIGHT",
        "one_finger_swipe_left":  "FINGER LEFT",
        "peace_move_up":          "PEACE UP",
        "peace_move_down":        "PEACE DOWN",
        "rock":                   "ROCK",
        "hand":                   "HAND",
    }

    def __init__(self, fps=12, show_camera=True, fullscreen=True):
        pygame.init()

        # --- Screen setup ---
        if fullscreen:
            # (0, 0) + FULLSCREEN → pygame uses the native display resolution.
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.W, self.H = self.screen.get_size()
            pygame.mouse.set_visible(False)
        else:
            self.W, self.H = 640, 420
            self.screen = pygame.display.set_mode((self.W, self.H))

        pygame.display.set_caption("WaveBeat")

        # --- Scale factors (reference design: 640 × 420) ---
        self.sx = self.W / 640   # horizontal
        self.sy = self.H / 420   # vertical
        self.s  = min(self.sx, self.sy)   # uniform (fonts, radii)

        # --- Layout landmarks computed once from screen size ---
        self.cx        = self.W // 2
        self.cy_orb    = int(self.H * 0.448)   # hologram orb centre
        self.cy_status = int(self.H * 0.750)   # centre status message
        self.cy_panels = int(self.H * 0.838)   # bottom panel row
        self.panel_h   = int(self.H * 0.124)   # bottom panel height
        self.spw       = int(self.W * 0.234)   # side panel width
        self.cpw       = int(self.W * 0.422)   # centre panel width

        # Guide panel bounds (cached) — 58% wide × 88% tall, centred
        self._gw = int(self.W * 0.58)
        self._gh = int(self.H * 0.88)
        self._gx = (self.W - self._gw) // 2
        self._gy = (self.H - self._gh) // 2

        # --- Clock / state ---
        self.clock              = pygame.time.Clock()
        self.fps                = fps
        self.show_camera        = show_camera
        self.current_action     = "idle"
        self.action_start_time  = time.time()
        self.action_duration    = 1.5
        self.show_help          = False
        self.guide_until        = 0.0

        # --- Fonts (all scaled from reference sizes) ---
        def fs(ref):
            return max(8, int(ref * self.s))

        self.font_big    = pygame.font.SysFont("arial", fs(64), bold=True)
        self.font_medium = pygame.font.SysFont("arial", fs(26), bold=True)
        self.font_small  = pygame.font.SysFont("arial", fs(14), bold=True)
        self.font_tiny   = pygame.font.SysFont("arial", fs(11))

        # Guide-specific fonts
        self.font_g_title = pygame.font.SysFont("arial", fs(20), bold=True)
        self.font_g_sec   = pygame.font.SysFont("arial", fs(10), bold=True)
        self.font_g_row   = pygame.font.SysFont("arial", fs(12))
        self.font_g_tip   = pygame.font.SysFont("arial", fs(10))

        # --- Pre-built surfaces ---
        self._camera_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._camera_overlay.fill((0, 8, 12, 120))

        self._help_overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._help_overlay.fill((0, 0, 0, 235))

        self._guide_panel = pygame.Surface((self._gw, self._gh), pygame.SRCALPHA)
        self._guide_panel.fill((8, 12, 18, 242))

        self._panel_surfaces = {}

    # ------------------------------------------------------------------
    # Scale helpers
    # ------------------------------------------------------------------

    def _sc(self, v):  return int(v * self.s)
    def _scx(self, v): return int(v * self.sx)
    def _scy(self, v): return int(v * self.sy)

    # ------------------------------------------------------------------
    # Public API
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
            view_on=self.show_camera,
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
        self.current_action    = action
        self.action_start_time = time.time()

    def show_action_from_gesture(self, gesture):
        gesture_to_action = {
            "open_palm":              "play",
            "fist":                   "pause",
            "one_finger_swipe_right": "next",
            "one_finger_swipe_left":  "previous",
            "peace_move_up":          "volume_up",
            "peace_move_down":        "volume_down",
            "rock":                   "view",
        }
        self.show_action(gesture_to_action.get(gesture, "idle"))

    # ------------------------------------------------------------------
    # Main render loop
    # ------------------------------------------------------------------

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
        self.screen.fill((0, 0, 0))

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
        self.draw_gesture_panel(gesture, view_on)
        self.draw_shortcuts()

        if self.show_help or time.time() < self.guide_until:
            self.draw_help_menu()

        pygame.display.flip()
        self.clock.tick(self.fps)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def draw_camera_background(self, frame_bgr):
        frame_bgr = cv2.resize(frame_bgr, (self.W, self.H))
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        surface   = pygame.image.frombuffer(frame_rgb.tobytes(), (self.W, self.H), "RGB")
        surface.set_alpha(58)
        self.screen.blit(surface, (0, 0))
        self.screen.blit(self._camera_overlay, (0, 0))

    def draw_grid(self):
        color = (0, 60, 72)
        step  = max(20, self._sc(40))
        for x in range(0, self.W, step):
            pygame.draw.line(self.screen, color, (x, 0), (x, self.H), 1)
        for y in range(0, self.H, step):
            pygame.draw.line(self.screen, color, (0, y), (self.W, y), 1)

    def draw_hologram_frame(self):
        cyan    = (0, 210, 255)
        magenta = (255, 60, 220)
        m       = self._sc(12)
        length  = self._sc(44)
        corners = [
            ((m, m),                   ( 1,  1), magenta),
            ((self.W - m, m),          (-1,  1), cyan),
            ((m, self.H - m),          ( 1, -1), cyan),
            ((self.W - m, self.H - m), (-1, -1), magenta),
        ]
        for (x, y), (dx, dy), colour in corners:
            pygame.draw.line(self.screen, colour, (x, y), (x + length * dx, y), 2)
            pygame.draw.line(self.screen, colour, (x, y), (x, y + length * dy), 2)

    # ------------------------------------------------------------------
    # Hologram orb
    # ------------------------------------------------------------------

    def draw_idle_visualizer(self, state, wake_progress):
        cx = self.cx
        cy = self.cy_orb
        t  = time.time()

        color   = self.get_state_color(state)
        base_r  = self._sc(82)
        var_r   = self._sc(8)

        for i in range(24):
            angle  = t * 1.6 + i * (math.pi * 2 / 24)
            radius = base_r + math.sin(t * 2.8 + i) * var_r
            px     = cx + math.cos(angle) * radius
            py     = cy + math.sin(angle) * radius
            size   = max(1, self._sc(2) + int(self._sc(2) * (0.5 + 0.5 * math.sin(t * 3 + i))))
            pcol   = (255, 60, 220) if i % 4 == 0 else color
            pygame.draw.circle(self.screen, pcol, (int(px), int(py)), size)

        pygame.draw.circle(self.screen, self.dim(color, 0.22), (cx, cy), self._sc(100), 1)
        pygame.draw.circle(self.screen, color,                 (cx, cy), self._sc(75),  2)
        pygame.draw.circle(self.screen, (245, 250, 255),       (cx, cy), self._sc(42),  1)

        base_y = cy + self._scy(88)
        for r in [36, 25, 15]:
            sr = self._sc(r)
            pygame.draw.ellipse(
                self.screen,
                self.dim((0, 210, 255), 0.65),
                (cx - sr, base_y - max(1, sr // 4), sr * 2, max(2, sr // 2)),
                1,
            )

        pygame.draw.line(
            self.screen,
            self.dim((0, 210, 255), 0.55),
            (cx, base_y),
            (cx, cy + self._scy(48)),
            1,
        )

        if wake_progress > 0:
            self.draw_wake_arc(cx, cy, wake_progress, color)

        self.draw_center_text("♪", size="big", color=color, y=cy)

    def draw_action(self):
        actions = {
            "play":       "PLAY",
            "pause":      "PAUSE",
            "next":       "NEXT",
            "previous":   "PREV",
            "volume_up":  "VOL+",
            "volume_down":"VOL-",
            "error":      "ERROR",
            "guide":      "GUIDE",
            "view":       "VIEW",
            "idle":       "♪",
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

        cx = self.cx
        cy = self.cy_orb
        for r, factor in [(100, 0.12), (78, 0.22), (58, 0.45)]:
            pygame.draw.circle(
                self.screen, self.dim(color, factor), (cx, cy), self._sc(r), 2
            )
        self.draw_center_text(text, size="medium", color=color, y=cy)

    def draw_center_text(self, text, size="big", color=(0, 255, 255), y=None):
        if y is None:
            y = self.H // 2
        font        = self.font_big if size == "big" else self.font_medium
        main_surf   = font.render(text, True, (245, 255, 255))
        glow_surf   = font.render(text, True, color)
        rect        = main_surf.get_rect(center=(self.cx, y))
        for offset in [6, 4, 2]:
            gr = glow_surf.get_rect(center=(self.cx + offset, y + offset))
            self.screen.blit(glow_surf, gr)
        self.screen.blit(main_surf, rect)

    def draw_wake_arc(self, cx, cy, progress, color):
        radius = self._sc(112)
        start  = -math.pi / 2
        end    = start + 2 * math.pi * progress
        steps  = max(2, int(100 * progress))
        points = []
        for i in range(steps + 1):
            angle = start + (end - start) * i / steps
            points.append((int(cx + math.cos(angle) * radius),
                           int(cy + math.sin(angle) * radius)))
        if len(points) > 1:
            pygame.draw.lines(self.screen, color, False, points, 3)

    # ------------------------------------------------------------------
    # UI panels and text
    # ------------------------------------------------------------------

    def draw_top_title(self, state):
        color = self.get_state_color(state)
        title = self.font_medium.render("WAVEBEAT", True, color)
        self.screen.blit(title, title.get_rect(center=(self.cx, self._scy(28))))
        sub = self.font_small.render("Spotify Gesture Controller", True, self.dim(color, 0.72))
        self.screen.blit(sub, sub.get_rect(center=(self.cx, self._scy(53))))

    def draw_center_status(self, message):
        msg  = (message if message else "Waiting for command.")[:44]
        y    = self.cy_status
        glow = self.font_small.render(msg, True, (255, 60, 220))
        text = self.font_small.render(msg, True, (0, 220, 255))
        self.screen.blit(glow, glow.get_rect(center=(self.cx + 1, y + 1)))
        self.screen.blit(text, text.get_rect(center=(self.cx, y)))

    def draw_system_status_panel(self, state):
        x = self._scx(18)
        y = self.cy_panels
        w = self.spw
        h = self.panel_h
        self.draw_panel_box(x, y, w, h)

        self.screen.blit(
            self.font_tiny.render("SYSTEM", True, (180, 120, 255)),
            (x + self._sc(10), y + self._sc(7)),
        )

        state_labels = {
            "standby":  ("STANDBY", (0, 200, 255)),
            "ready":    ("ACTIVE",  (80, 255, 140)),
            "executing":("PLAYING", (255, 80, 230)),
            "error":    ("ERROR",   (255, 90, 90)),
        }
        label, color = state_labels.get(state, ("STANDBY", (0, 200, 255)))
        self.screen.blit(
            self.font_small.render(label, True, color),
            (x + self._sc(10), y + self._sc(23)),
        )
        pygame.draw.circle(self.screen, color, (x + w - self._sc(22), y + self._sc(28)), self._sc(5))

    def draw_gesture_panel(self, gesture, view_on):
        x = self.W - self.spw - self._scx(18)
        y = self.cy_panels
        w = self.spw
        h = self.panel_h
        self.draw_panel_box(x, y, w, h)

        gesture_text = (
            self._GESTURE_LABELS.get(gesture, gesture.upper()[:12])
            if gesture and gesture != "No hand"
            else "WAITING"
        )
        self.screen.blit(
            self.font_tiny.render("GESTURE", True, (80, 255, 140)),
            (x + self._sc(10), y + self._sc(7)),
        )
        self.screen.blit(
            self.font_small.render(gesture_text, True, (80, 255, 140)),
            (x + self._sc(10), y + self._sc(22)),
        )
        self.screen.blit(
            self.font_tiny.render("VIEW ON" if view_on else "VIEW OFF", True, (0, 220, 255)),
            (x + self._sc(10), y + self._sc(38)),
        )

    def draw_track(self, track):
        w = self.cpw
        h = self.panel_h
        x = (self.W - w) // 2
        y = self.cy_panels
        self.draw_panel_box(x, y, w, h)

        self.screen.blit(
            self.font_tiny.render("NOW PLAYING", True, (255, 80, 220)),
            (x + self._sc(10), y + self._sc(6)),
        )
        text = track if len(track) <= 30 else track[:28] + ".."
        self.screen.blit(
            self.font_small.render(text, True, (0, 220, 255)),
            (x + self._sc(10), y + self._sc(21)),
        )
        self.draw_music_wave(x + self._sc(10), y + self._sc(45), w - self._sc(20))

    def draw_music_wave(self, x, y, width):
        t       = time.time()
        bar_w   = max(1, self._sc(2))
        gap     = max(1, self._sc(3))
        bars    = max(12, width // (bar_w + gap))
        start_x = x + max(0, (width - bars * (bar_w + gap)) // 2)
        for i in range(bars):
            bx  = start_x + i * (bar_w + gap)
            h   = max(2, int((3 + abs(math.sin(t * 5 + i * 0.45)) * 10) * self.sy))
            col = (255, 80, 220) if i % 4 == 0 else (0, 220, 255)
            pygame.draw.line(self.screen, col, (bx, y), (bx, y - h), bar_w)

    def draw_panel_box(self, x, y, w, h):
        key = (w, h)
        if key not in self._panel_surfaces:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            s.fill((0, 0, 0, 175))
            self._panel_surfaces[key] = s
        self.screen.blit(self._panel_surfaces[key], (x, y))
        pygame.draw.rect(self.screen, (255, 60, 220), (x, y, w, h), 1)
        pygame.draw.rect(self.screen, (0, 220, 255), (x + 3, y + 3, w - 6, h - 6), 1)

    # ------------------------------------------------------------------
    # Gesture guide overlay
    # ------------------------------------------------------------------

    def draw_shortcuts(self):
        text = "G Guide   H View   Q Quit"
        self.screen.blit(
            self.font_tiny.render(text, True, (145, 235, 245)),
            (self._scx(18), self._scy(18)),
        )

    def draw_help_menu(self):
        gx   = self._gx
        gy   = self._gy
        gw   = self._gw
        gh   = self._gh
        cx_g = gx + gw // 2

        self.screen.blit(self._help_overlay, (0, 0))
        self.screen.blit(self._guide_panel, (gx, gy))
        pygame.draw.rect(self.screen, (0, 140, 170), (gx, gy, gw, gh), 1)

        pad       = self._sc(24)
        row_h     = max(15, self._sc(18))
        sec_gap   = max(8,  self._sc(10))
        inner_gap = max(3,  self._sc(4))
        col1      = gx + pad
        col2      = gx + pad + int(gw * 0.46)
        right_edge = gx + gw - pad

        # Bottom-anchored footer: work backwards from panel bottom
        close_y = gy + gh - self._sc(14)
        div_y   = close_y - self._sc(16)
        tips_y  = div_y   - max(14, self._sc(16))

        # ---- Title ----
        cy = gy + self._sc(16)
        t1 = self.font_g_title.render("WAVEBEAT", True, (0, 200, 235))
        self.screen.blit(t1, t1.get_rect(center=(cx_g, cy + t1.get_height() // 2)))
        cy += t1.get_height() + self._sc(3)

        t2 = self.font_g_sec.render("Gesture Guide", True, (128, 143, 158))
        self.screen.blit(t2, t2.get_rect(center=(cx_g, cy + t2.get_height() // 2)))
        cy += t2.get_height() + self._sc(8)

        pygame.draw.line(self.screen, (0, 100, 130), (col1, cy), (right_edge, cy), 1)
        cy += self._sc(10)

        # ---- ACTIVATION ----
        sec = self.font_g_sec.render("ACTIVATION", True, (185, 75, 185))
        self.screen.blit(sec, (col1, cy))
        cy += sec.get_height() + inner_gap

        for name, action in [("OK sign  (hold 1.5 s)", "Activate gesture control")]:
            self.screen.blit(self.font_g_row.render(name,   True, (178, 193, 206)), (col1, cy))
            self.screen.blit(self.font_g_row.render(action, True, (232, 238, 244)), (col2, cy))
            cy += row_h

        cy += sec_gap

        # ---- MUSIC CONTROLS ----
        sec = self.font_g_sec.render("MUSIC CONTROLS", True, (185, 75, 185))
        self.screen.blit(sec, (col1, cy))
        cy += sec.get_height() + inner_gap

        for name, action in [
            ("Open palm",    "Play"),
            ("Fist",         "Pause"),
            ("One finger →", "Next track"),
            ("One finger ←", "Previous track"),
        ]:
            self.screen.blit(self.font_g_row.render(name,   True, (178, 193, 206)), (col1, cy))
            self.screen.blit(self.font_g_row.render(action, True, (232, 238, 244)), (col2, cy))
            cy += row_h

        cy += sec_gap

        # ---- VOLUME CONTROLS ----
        sec = self.font_g_sec.render("VOLUME CONTROLS", True, (185, 75, 185))
        self.screen.blit(sec, (col1, cy))
        cy += sec.get_height() + inner_gap

        for name, action in [
            ("Peace sign up",   "Volume up"),
            ("Peace sign down",  "Volume down"),
        ]:
            self.screen.blit(self.font_g_row.render(name,   True, (178, 193, 206)), (col1, cy))
            self.screen.blit(self.font_g_row.render(action, True, (232, 238, 244)), (col2, cy))
            cy += row_h

        cy += sec_gap

        # ---- SYSTEM ----
        sec = self.font_g_sec.render("SYSTEM", True, (185, 75, 185))
        self.screen.blit(sec, (col1, cy))
        cy += sec.get_height() + inner_gap

        for name, action in [
            ("Rock sign  (hold)", "Toggle camera view"),
            ("G",                 "Show / hide guide"),
            ("H",                 "Toggle camera"),
            ("Q",                 "Quit"),
        ]:
            self.screen.blit(self.font_g_row.render(name,   True, (178, 193, 206)), (col1, cy))
            self.screen.blit(self.font_g_row.render(action, True, (232, 238, 244)), (col2, cy))
            cy += row_h

        # ---- Bottom footer (anchored) ----
        pygame.draw.line(self.screen, (0, 100, 130), (col1, div_y), (right_edge, div_y), 1)

        tip = self.font_g_tip.render(
            "Keep hand visible  •  50–60 cm from camera  •  Hold peace sign steady for volume",
            True, (90, 108, 125),
        )
        self.screen.blit(tip, tip.get_rect(center=(cx_g, tips_y)))

        close = self.font_g_tip.render("Press G to close", True, (128, 143, 158))
        self.screen.blit(close, close.get_rect(center=(cx_g, close_y)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_state_color(self, state):
        return {
            "standby":  (0, 210, 255),
            "ready":    (80, 255, 120),
            "executing":(255, 80, 230),
            "error":    (255, 80, 80),
        }.get(state, (0, 210, 255))

    def dim(self, color, factor):
        return tuple(max(0, min(255, int(c * factor))) for c in color)
