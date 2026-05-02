"""
ui/hologram_display.py
Pygame-based hologram display for HoloBeat.
640 x 480  |  12 FPS  |  minimal elements

Layout
------
  top-left   : gesture badge + body indicator (tiny)
  top-center : HOLOBEAT title
  center     : animated orb (standby/ready) or sound bars (executing)
  center-low : state label + message text
  bottom     : now-playing strip (32 px)
"""

import math
import time

import cv2
import pygame

# ---------------------------------------------------------------------------
# Color palette  —  RGB (NOT BGR; pygame uses RGB)
# ---------------------------------------------------------------------------
_BG = (4, 4, 8)

_COLORS = {
    "standby":   (70, 100, 130),    # steel-blue
    "ready":     (80, 190,  70),    # soft green
    "executing": (155,  55, 175),   # soft purple
    "error":     (195,  55,  50),   # soft red
    # backward-compat aliases
    "waiting":   (70, 100, 130),
    "watching":  (70, 100, 130),
    "listening": (80, 190,  70),
    "acting":    (155,  55, 175),
    "action":    (155,  55, 175),
    "sleeping":  (70, 100, 130),
}


def _color(state):
    return _COLORS.get(state, _COLORS["standby"])


def _dim(rgb, f=0.28):
    return tuple(max(0, int(c * f)) for c in rgb)


def _wrap(text, max_chars=48):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        fits = len(cur) + len(word) + (1 if cur else 0) <= max_chars
        if fits:
            cur = (cur + " " + word).strip() if cur else word
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class HologramDisplay:
    W = 640
    H = 480

    # Orb sits slightly above centre so text fits below it.
    ORB_CX = 320
    ORB_CY = 210

    def __init__(self, fps=12, show_camera=True):
        pygame.init()
        pygame.display.set_caption("HoloBeat")
        self.screen = pygame.display.set_mode((self.W, self.H))
        self.clock  = pygame.time.Clock()
        self.fps    = fps
        self.show_camera = show_camera

        # Monospace fonts — sizes kept small for Pi LCD readability.
        self._f_title = pygame.font.SysFont("monospace", 19, bold=True)
        self._f_state = pygame.font.SysFont("monospace", 14, bold=True)
        self._f_msg   = pygame.font.SysFont("monospace", 12)
        self._f_track = pygame.font.SysFont("monospace", 11)
        self._f_badge = pygame.font.SysFont("monospace", 10)

        # Pre-rendered static overlays (built once).
        self._scanlines = self._build_scanlines()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def draw(self, frame_bgr, state, message,
             gesture="", track="", body_on=False, wake_progress=0.0):
        t     = time.time()
        color = _color(state)
        dim   = _dim(color)

        # 1 · Dark background
        self.screen.fill(_BG)

        # 2 · Camera layer.
        #     When body_on=True, frame_bgr is already the hologram-transformed
        #     image (dark + glowing body), so we raise alpha so it reads through.
        if self.show_camera and frame_bgr is not None:
            cam_alpha = 72 if body_on else 32
            self._blit_camera(frame_bgr, alpha=cam_alpha)

        # 3 · Subtle grid texture
        self._draw_grid(dim)

        # 4 · Scan lines
        self.screen.blit(self._scanlines, (0, 0))

        cx, cy = self.ORB_CX, self.ORB_CY

        # 5 · Central graphic  (orb or sound bars)
        if state == "executing":
            self._draw_bars(cx, cy, color, dim, t)
        else:
            self._draw_orb(cx, cy, color, dim, state, t)

        # 6 · Wake-hold progress arc (appears around orb while finger is held up)
        if wake_progress > 0.0:
            self._draw_wake_arc(cx, cy, wake_progress, color)

        # 7 · Title  ─────────────────────────────────────────────────────
        self._center_text(self._f_title, "HOLOBEAT", self.W // 2, 28, color)
        pygame.draw.line(self.screen, dim,
                         (self.W // 2 - 68, 40), (self.W // 2 + 68, 40), 1)

        # 8 · State + message  ───────────────────────────────────────────
        self._center_text(self._f_state, state.upper(), self.W // 2, cy + 74, color)
        for i, line in enumerate(_wrap(message)[:2]):
            self._center_text(self._f_msg, line, self.W // 2, cy + 96 + i * 17,
                              (135, 135, 135))

        # 9 · Gesture badge  (top-left, only when a hand is detected)
        if gesture and gesture != "No hand":
            self._badge(gesture[:22], 10, 10)

        # 10 · Body indicator  (top-left, below gesture badge)
        self._badge("body ON" if body_on else "body OFF",
                    10, 34, bright=body_on)

        # 11 · Now-playing strip  (bottom 32 px)
        if track:
            self._draw_track_strip(track, color, dim)

        pygame.display.flip()
        self.clock.tick(self.fps)

    def poll(self):
        """
        Process pygame events.  Returns one of:
          'quit'         – user pressed Q or closed the window
          'toggle_body'  – user pressed H
          None           – nothing actionable
        """
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
    # Drawing helpers
    # ------------------------------------------------------------------

    def _blit_camera(self, frame_bgr, alpha):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        # frombuffer is faster than surfarray on Raspberry Pi.
        surf = pygame.image.frombuffer(frame_rgb.tobytes(), (self.W, self.H), "RGB")
        surf.set_alpha(alpha)
        self.screen.blit(surf, (0, 0))

    def _draw_grid(self, color):
        step = 40
        for x in range(0, self.W + 1, step):
            pygame.draw.line(self.screen, color, (x, 0), (x, self.H), 1)
        for y in range(0, self.H + 1, step):
            pygame.draw.line(self.screen, color, (0, y), (self.W, y), 1)

    def _draw_orb(self, cx, cy, color, dim, state, t):
        speed = 1.8 if state == "ready" else 0.7

        # One expanding ghost ring (fades out as it grows).
        phase   = (t * speed) % 1.0
        r_ring  = int(44 + phase * 28)
        a_ring  = int(88 * (1.0 - phase))
        if a_ring > 0:
            ring_surf = pygame.Surface((r_ring * 2 + 4, r_ring * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, (*color, a_ring),
                               (r_ring + 2, r_ring + 2), r_ring, 1)
            self.screen.blit(ring_surf, (cx - r_ring - 2, cy - r_ring - 2))

        # Static outer ring.
        pygame.draw.circle(self.screen, dim, (cx, cy), 44, 1)

        # Breathing inner orb — soft glow approximation without SRCALPHA.
        pulse   = 0.5 + 0.5 * math.sin(t * speed)
        r_inner = int(16 + pulse * 8)

        for i in range(4):
            r_g = r_inner + (4 - i) * 5
            brightness = 0.22 - i * 0.05
            if brightness <= 0:
                break
            c = tuple(int(ch * brightness) for ch in color)
            pygame.draw.circle(self.screen, c, (cx, cy), r_g)

        # Crisp outline.
        pygame.draw.circle(self.screen, color, (cx, cy), r_inner, 2)

    def _draw_bars(self, cx, cy, color, dim, t):
        n = 5
        bw, gap = 10, 7
        x0 = cx - (n * (bw + gap) - gap) // 2

        for i in range(n):
            h_bar = int(10 + abs(math.sin(t * 4.2 + i * 0.95)) * 44)
            bx    = x0 + i * (bw + gap)
            by_b  = cy + 30
            rect  = pygame.Rect(bx, by_b - h_bar, bw, h_bar)
            pygame.draw.rect(self.screen, dim,   rect)
            pygame.draw.rect(self.screen, color, rect, 1)

    def _draw_wake_arc(self, cx, cy, progress, color):
        r     = 56
        start = -math.pi / 2
        end   = start + 2 * math.pi * progress
        steps = max(2, int(72 * progress))
        pts   = [
            (int(cx + r * math.cos(start + (end - start) * k / steps)),
             int(cy + r * math.sin(start + (end - start) * k / steps)))
            for k in range(steps + 1)
        ]
        if len(pts) >= 2:
            pygame.draw.lines(self.screen, color, False, pts, 2)

    def _draw_track_strip(self, track, color, dim):
        y0    = self.H - 32
        strip = pygame.Surface((self.W, 32), pygame.SRCALPHA)
        strip.fill((5, 5, 10, 210))
        self.screen.blit(strip, (0, y0))
        pygame.draw.line(self.screen, dim, (0, y0), (self.W, y0), 1)
        label = "Now:  " + (track if len(track) <= 64 else track[:62] + "..")
        self.screen.blit(self._f_track.render(label, True, (125, 125, 125)), (14, y0 + 10))

    def _badge(self, text, x, y, bright=True):
        tw, _ = self._f_badge.size(text)
        bw, bh = tw + 14, 20
        s = pygame.Surface((bw, bh), pygame.SRCALPHA)
        s.fill((8, 8, 14, 180))
        self.screen.blit(s, (x, y))
        pygame.draw.rect(self.screen, (46, 46, 52), (x, y, bw, bh), 1)
        col = (148, 148, 148) if bright else (85, 85, 85)
        self.screen.blit(self._f_badge.render(text, True, col), (x + 7, y + 5))

    def _center_text(self, font, text, x, y, color):
        surf = font.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(center=(x, y)))

    def _build_scanlines(self):
        s = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for y in range(0, self.H, 3):
            pygame.draw.line(s, (0, 0, 0, 26), (0, y), (self.W, y), 1)
        return s
