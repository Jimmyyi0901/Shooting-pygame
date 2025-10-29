"""
Project: SHOOTING (2D shooting practice game)
Instructions: Use the mouse to move the crosshair and click (shoot) the target to score points; points will be deducted for missing targets, and points will be deducted for targets that disappear after the timeout.
Author: <Yifeng Chen>
SID: 540796922
Course: COMP9001 Final Project
Run: python shooting_game.py (depends on pygame)
"""

import math
import random
import pygame
from dataclasses import dataclass
from typing import List, Tuple
# -----------------------------
# Config
# -----------------------------
WIDTH, HEIGHT = 900, 600
FPS = 120

# Gameplay tuning
TARGET_MIN_RADIUS = 16
TARGET_MAX_RADIUS = 36
TARGET_LIFETIME = 1.5  # seconds a target stays alive
SPAWN_INTERVAL_START = 0.85  # seconds between spawns (will speed up)
SPAWN_INTERVAL_MIN = 0.35
SPAWN_ACCEL_EVERY = 5  # every N seconds, decrease spawn interval a bit
SPAWN_ACCEL_STEP = 0.04
MAX_TARGETS_ON_SCREEN = 7

MISS_SCORE = -5
TIMEOUT_SCORE = -3
# Ring scoring: bullseye (inner) -> middle -> outer
RING_SCORES = (10, 5, 1)
# Fractions of target radius that define the rings (ascending)
RING_FRACS = (0.25, 0.55, 1.00)

ROUND_TIME = 15  # seconds; set to None for endless

# Colors
BG = (14, 18, 26)
WHITE = (240, 240, 240)
GREEN = (45, 200, 120)
RED = (230, 60, 70)
YELLOW = (250, 220, 90)
CYAN = (60, 210, 230)
MUTED = (120, 130, 145)

# -----------------------------
# Data structures
# -----------------------------
@dataclass
class Target:
    """
    Circular target entity
    Attributes:
    x, y (float): Center coordinates (pixels)
    r (float): Radius
    spawn_time (float): Spawn time (seconds)
    lifetime (float): Lifetime (seconds)
    vx, vy (float): Velocity (can be 0 to indicate rest)
    """
    x: float
    y: float
    r: float
    spawn_time: float
    lifetime: float
    def contains(self, px: float, py: float) -> bool:
        return (self.x - px) ** 2 + (self.y - py) ** 2 <= self.r ** 2

# -----------------------------
# Utility
# -----------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))#limitation

# -----------------------------
# Game
# -----------------------------
class Game:
    """Game main loop and state management: event processing → logic update → screen rendering."""
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("consolas", 18)
        self.font_med = pygame.font.SysFont("consolas", 24, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 46, bold=True)
        self.crosshair_radius = 12
        self.crosshair_gap = 4
        self.reset()

    def reset(self):
        self.running = True
        self.playing = False  # start screen first
        self.paused = False
        self.targets: List[Target] = []
        self.spawn_interval = SPAWN_INTERVAL_START
        self.last_spawn = 0.0
        self.start_time = 0.0
        self.elapsed = 0.0
        # Stats
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.timeouts = 0
        self.best_score = 0
        # Floating texts: (text, color, x, y, birth_time)
        self.floating_texts: List[Tuple[str, Tuple[int,int,int], float, float, float]] = []

    # -------------------------
    # Core loop
    # -------------------------
    def start_round(self, now):
        """Start a new round: reset statistics and timer, clear targets, and cancel pause."""
        self.playing = True
        self.targets.clear()
        self.spawn_interval = SPAWN_INTERVAL_START
        self.last_spawn = now
        self.start_time = now
        self.elapsed = 0.0
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.timeouts = 0
        self.floating_texts.clear()

    def update(self, dt, now):
        """Updates the game state (spawning/expiring targets, scoring, round timeout, etc.)"""
        if not self.playing:
            return
        if self.paused:
            return
        self.elapsed = now - self.start_time

        # Difficulty: speed up spawns periodically
        if SPAWN_ACCEL_EVERY and self.elapsed > 0:
            steps = int(self.elapsed // SPAWN_ACCEL_EVERY)
            self.spawn_interval = clamp(
                SPAWN_INTERVAL_START - steps * SPAWN_ACCEL_STEP,
                SPAWN_INTERVAL_MIN,
                SPAWN_INTERVAL_START,
            )

        # Spawn targets
        if (now - self.last_spawn >= self.spawn_interval
            and len(self.targets) < MAX_TARGETS_ON_SCREEN):
            self.spawn_target(now)
            self.last_spawn = now

        # Expire targets
        alive = []
        for t in self.targets:
            if now - t.spawn_time > t.lifetime:
                self.score += TIMEOUT_SCORE
                self.timeouts += 1
                self.make_float_text(f"-{abs(TIMEOUT_SCORE)}", RED, t.x, t.y, now)
            else:
                alive.append(t)
        self.targets = alive

        # End round
        if ROUND_TIME is not None and self.elapsed >= ROUND_TIME:
            self.best_score = max(self.best_score, self.score)
            self.playing = False

    def spawn_target(self, now):
        r = random.uniform(TARGET_MIN_RADIUS, TARGET_MAX_RADIUS)
        x = random.uniform(r + 8, WIDTH - r - 8)
        y = random.uniform(r + 8 + 40, HEIGHT - r - 8)  # leave space for HUD
        life = TARGET_LIFETIME * random.uniform(0.85, 1.15)
        self.targets.append(Target(x, y, r, now, life))

    def handle_click(self, pos, now):
        if not self.playing:
            self.start_round(now)
            return

        mx, my = pos

        # Find the closest hit target, if any, and which ring it belongs to
        hit_index = -1
        closest_d2 = 1e12
        ring_idx_for_hit = None

        for i, t in enumerate(self.targets):
            dx = mx - t.x
            dy = my - t.y
            d2 = dx * dx + dy * dy

            # inside outer ring?
            if d2 <= (t.r * RING_FRACS[-1]) ** 2:
                if d2 < closest_d2:
                    closest_d2 = d2
                    hit_index = i

                    if d2 <= (t.r * RING_FRACS[0]) ** 2:
                        ring_idx_for_hit = 0  # bullseye
                    elif d2 <= (t.r * RING_FRACS[1]) ** 2:
                        ring_idx_for_hit = 1  # middle
                    else:
                        ring_idx_for_hit = 2  # outer

        if hit_index >= 0 and ring_idx_for_hit is not None:
            t = self.targets.pop(hit_index)
            award = RING_SCORES[ring_idx_for_hit]
            self.score += award
            self.hits += 1

            # feedback color by ring
            if award == 10:
                color = GREEN
            elif award == 5:
                color = CYAN
            else:
                color = WHITE

            self.make_float_text(f"+{award}", color, t.x, t.y, now)
        else:
            # Miss (clicked outside all targets)
            self.score += MISS_SCORE
            self.misses += 1
            self.make_float_text(str(MISS_SCORE), RED, mx, my, now)

    def make_float_text(self, text, color, x, y, now):
        self.floating_texts.append((text, color, x, y, now))

    # -------------------------
    # Rendering
    # -------------------------
    def draw(self, now):
        """Draw the scene (target, HUD, overlay, crosshair, etc.)"""
        self.screen.fill(BG)

        # Targets (bullseye look + timeout arc)
        for t in self.targets:
            age = now - t.spawn_time
            alpha = clamp(255 - int((age / t.lifetime) * 255), 30, 255)
            pygame.draw.circle(self.screen, WHITE, (int(t.x), int(t.y)), int(t.r), 2)
            inner_r = int(t.r * 0.55)
            pygame.draw.circle(self.screen, CYAN, (int(t.x), int(t.y)), inner_r, 2)
            core_r = int(t.r * 0.25)
            pygame.draw.circle(self.screen, WHITE, (int(t.x), int(t.y)), core_r, 0)
            progress = clamp((now - t.spawn_time) / t.lifetime, 0, 1.0)
            end_angle = -math.pi/2 + 2 * math.pi * progress
            pygame.draw.arc(
                self.screen,
                (alpha, 80, 80),
                (t.x - t.r - 2, t.y - t.r - 2, (t.r + 2) * 2, (t.r + 2) * 2),
                -math.pi/2,
                end_angle,
                3
            )
        if self.paused:
            tip_s = self.font_big.render("PAUSED", True, YELLOW)
            self.screen.blit(tip_s, ((WIDTH - tip_s.get_width()) // 2, HEIGHT // 2 - 20))

        # Floating texts
        ft_alive = []
        for text, color, x, y, birth in self.floating_texts:
            age = now - birth
            if age < 0.7:
                dy = -40 * age
                surf = self.font_med.render(text, True, color)
                self.screen.blit(surf, (x - surf.get_width() // 2, y + dy))
                ft_alive.append((text, color, x, y, birth))
        self.floating_texts = ft_alive

        # HUD bar
        pygame.draw.rect(self.screen, (20, 24, 32), (0, 0, WIDTH, 36))
        pygame.draw.line(self.screen, (40, 46, 58), (0, 36), (WIDTH, 36), 1)

        acc = (self.hits / max(1, (self.hits + self.misses))) * 100.0
        hud_items = [
            f"Score: {self.score}",
            f"Hits: {self.hits}",
            f"Misses: {self.misses}",
            f"Timeouts: {self.timeouts}",
            f"Acc: {acc:.1f}%",
        ]
        if ROUND_TIME is not None and self.playing:
            time_left = max(0, int(ROUND_TIME - (now - self.start_time)))
            hud_items.append(f"Time: {time_left}s")
        elif ROUND_TIME is not None and not self.playing:
            hud_items.append("Time: 0s")

        x = 10
        for item in hud_items:
            surf = self.font_small.render(item, True, WHITE)
            self.screen.blit(surf, (x, 9))
            x += surf.get_width() + 18

        # Start / end overlays
        if not self.playing:
            if ROUND_TIME is not None and self.elapsed >= ROUND_TIME:
                title = "ROUND OVER"
                sub = f"Score: {self.score}    Best: {self.best_score}"
                tip = "Click to play again   |   R: reset best   |   ESC: quit"
            else:
                title = "SHOOTING"
                sub = "Click to start. Hit targets +10, Miss -5, Timeout -3."
                tip = "ESC: quit   |   R: reset best"
            title_s = self.font_big.render(title, True, WHITE)
            sub_s = self.font_med.render(sub, True, MUTED)
            tip_s = self.font_small.render(tip, True, MUTED)
            self.screen.blit(title_s, ((WIDTH - title_s.get_width()) // 2, HEIGHT // 2 - 64))
            self.screen.blit(sub_s, ((WIDTH - sub_s.get_width()) // 2, HEIGHT // 2 - 16))
            self.screen.blit(tip_s, ((WIDTH - tip_s.get_width()) // 2, HEIGHT // 2 + 20))

        # Crosshair
        mx, my = pygame.mouse.get_pos()
        self.draw_crosshair(mx, my)

    def draw_crosshair(self, mx, my):
        r = self.crosshair_radius
        g = self.crosshair_gap
        pygame.draw.line(self.screen, YELLOW, (mx - r, my), (mx - g, my), 2)
        pygame.draw.line(self.screen, YELLOW, (mx + g, my), (mx + r, my), 2)
        pygame.draw.line(self.screen, YELLOW, (mx, my - r), (mx, my - g), 2)
        pygame.draw.line(self.screen, YELLOW, (mx, my + g), (mx, my + r), 2)
        pygame.draw.circle(self.screen, YELLOW, (mx, my), 2)

    # -------------------------
    # Event handling
    # -------------------------
    def handle_events(self, now):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.best_score = 0
                elif event.key == pygame.K_p and self.playing:
                    self.paused = not self.paused
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_click(event.pos, now)

    # -------------------------
    # Main run
    # -------------------------
    def run(self):
        pygame.mouse.set_visible(False)
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            now = pygame.time.get_ticks() / 1000.0
            self.handle_events(now)
            self.update(dt, now)
            self.draw(now)
            pygame.display.flip()
        pygame.mouse.set_visible(True)

def main():
    pygame.init()
    pygame.display.set_caption("SHOOTING - COMP9001")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    try:
        Game(screen).run()
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()
