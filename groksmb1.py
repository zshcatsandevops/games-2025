# ULTRA! LEGACY MAARIO 0.1 [C] Samsoft — a tiny procedural platformer (32 levels)
# Resolution: 600 x 400
# Engine: pygame
# License: CC0-1.0 (Public Domain) — No Rights Reserved
# You are free to copy, modify, and use this code without attribution.
#
# Controls:
#   Left / Right or A / D  - move
#   Space / W / Up          - jump
#   R                       - restart level
#   N                       - skip to next level (for testing)
#   Esc                     - quit
# Notes:
#   - All visuals are generated with basic shapes (no external assets).
#   - Levels are procedurally generated on the fly based on level_index.
#   - Designed to be compact and readable rather than feature-complete.
#
# Tested with pygame 2.x
#   pip install pygame
#   python ultra_legacy_maario.py

import os
import sys
import math
import random
import pygame

# --- Config ------------------------------------------------------------------
WIDTH, HEIGHT = 600, 400
TILE = 20
ROWS, COLS_VIEW = HEIGHT // TILE, WIDTH // TILE
MAX_LEVELS = 32
FPS = 60

# Physics
GRAVITY = 0.35
MAX_FALL = 10
ACCEL = 0.35
FRICTION = 0.83
MAX_RUN = 3.2
JUMP_VELOCITY = 7.6
SPRING_BOOST = 1.55

# Tiles
EMPTY, DIRT, GRASS, PLATFORM, SPIKE, COIN, SPRING, EXIT = range(8)
SOLID = {DIRT, GRASS, PLATFORM}

# Colors (simple palette)
COL = {
    "sky": (150, 200, 255),
    "earth": (130, 95, 60),
    "grass": (64, 168, 60),
    "platform": (120, 120, 140),
    "spike": (220, 220, 230),
    "coin": (250, 210, 70),
    "spring": (190, 50, 60),
    "player": (50, 80, 180),
    "player_outline": (15, 20, 60),
    "enemy": (200, 60, 60),
    "enemy_eye": (255, 255, 255),
    "hud": (20, 30, 50),
    "exit": (250, 120, 50)
}

# Utility ---------------------------------------------------------------------
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def rect_from_cell(cx, cy):
    return pygame.Rect(cx * TILE, cy * TILE, TILE, TILE)

# Level generation ------------------------------------------------------------
class Level:
    def __init__(self, index):
        self.index = index
        # world length grows with difficulty, capped
        self.cols = min(120, 60 + index * 2)  # 60..120
        self.rows = ROWS
        self.map = [[EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.coins = set()
        self.springs = set()
        self.spikes = set()
        self.exit_cell = (self.cols - 4, 6)  # will be adjusted after terrain
        self.enemies = []  # list of Enemy
        self.spawn = (2, 5)  # will be adjusted after terrain

        self._generate()

    def _generate(self):
        rnd = random.Random(1337 + self.index * 99991)

        # baseline terrain ridge
        ground = [14] * self.cols
        cur = rnd.randint(12, 16)
        for x in range(self.cols):
            # occasional pits (increase with level)
            if rnd.random() < clamp(0.03 + self.index * 0.0025, 0, 0.10):
                # width grows slightly with level
                w = rnd.randint(1, 2 + (self.index // 8))
                for i in range(w):
                    if x + i < self.cols:
                        ground[x + i] = ROWS  # no ground (pit)
                x += w - 1
                continue

            # gentle height drift
            drift_chance = 0.23
            if rnd.random() < drift_chance:
                cur += rnd.choice([-1, 0, 1])
                cur = clamp(cur, 10, ROWS - 3)
            ground[x] = cur

        # lay terrain
        for x in range(self.cols):
            g = ground[x]
            if g >= ROWS:  # pit
                continue
            # top grass, dirt below
            self.map[g][x] = GRASS
            for y in range(g + 1, self.rows):
                self.map[y][x] = DIRT

        # helper: place a safe spawn near start (first non-pit)
        sx = 2
        while sx < self.cols - 1 and ground[sx] >= ROWS:
            sx += 1
        sy = ground[sx] - 1 if ground[sx] < ROWS else 6
        self.spawn = (sx, sy)

        # platforms
        plat_density = clamp(0.08 + self.index * 0.005, 0.08, 0.18)
        for x in range(5, self.cols - 5):
            if ground[x] >= ROWS:
                continue
            if rnd.random() < plat_density:
                h = clamp(ground[x] - rnd.randint(3, 6), 3, ground[x] - 2)
                w = rnd.randint(2, 4 + (self.index // 12))
                for i in range(w):
                    px = clamp(x + i, 0, self.cols - 1)
                    if self.map[h][px] == EMPTY:
                        self.map[h][px] = PLATFORM

        # spikes (on ground tops only; avoid start zone)
        spike_rate = clamp(0.05 + self.index * 0.007, 0.05, 0.22)
        for x in range(8, self.cols - 2):
            g = ground[x]
            if g >= ROWS:  # pit
                continue
            if rnd.random() < spike_rate and self.map[g][x] == GRASS:
                self.map[g - 1][x] = SPIKE
                self.spikes.add((x, g - 1))

        # coins over safe places
        coin_rate = clamp(0.12 + self.index * 0.004, 0.12, 0.22)
        for x in range(3, self.cols - 3):
            g = ground[x]
            if g >= ROWS:
                continue
            y = g - rnd.randint(2, 4)
            if 1 <= y < g and rnd.random() < coin_rate and self.map[y][x] == EMPTY:
                self.map[y][x] = COIN
                self.coins.add((x, y))

        # springs (rare)
        spring_rate = clamp(0.012 + self.index * 0.002, 0.012, 0.04)
        for x in range(10, self.cols - 10):
            g = ground[x]
            if g < ROWS and rnd.random() < spring_rate and self.map[g - 1][x] != SPIKE:
                self.map[g - 1][x] = SPRING
                self.springs.add((x, g - 1))

        # enemies
        enemy_count = clamp(2 + self.index // 2, 2, 14)
        tried = 0
        while len(self.enemies) < enemy_count and tried < enemy_count * 8:
            tried += 1
            x = rnd.randint(8, self.cols - 6)
            g = ground[x]
            if g >= ROWS:
                continue
            y = g - 1
            # avoid cluttered cells
            if self.map[y][x] in (EMPTY, COIN) and self.map[g - 1][x] != SPIKE:
                self.enemies.append(Enemy((x * TILE + 2, (y + 1) * TILE - 14)))
                # mildly block enemy spawn cell
                if self.map[y][x] == EMPTY:
                    self.map[y][x] = EMPTY  # keep empty

        # exit near far end on a reachable ledge
        ex = self.cols - 3
        gx = ex
        while gx > self.cols - 12 and ground[gx] >= ROWS:
            gx -= 1
        gy = ground[gx] - 2 if ground[gx] < ROWS else 6
        gy = clamp(gy, 3, ROWS - 4)
        self.exit_cell = (gx, gy)
        self.map[gy][gx] = EXIT

    # --- queries -------------------------------------------------------------
    def rects_in_region(self, x0, y0, x1, y1, codes):
        rx0 = max(int(x0 // TILE) - 1, 0)
        ry0 = max(int(y0 // TILE) - 1, 0)
        rx1 = min(int(math.ceil(x1 / TILE)) + 1, self.cols - 1)
        ry1 = min(int(math.ceil(y1 / TILE)) + 1, self.rows - 1)
        rects = []
        for cy in range(ry0, ry1 + 1):
            for cx in range(rx0, rx1 + 1):
                t = self.map[cy][cx]
                if t in codes:
                    rects.append(pygame.Rect(cx * TILE, cy * TILE, TILE, TILE))
        return rects

# Entities --------------------------------------------------------------------
class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 16, 18)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.dead = False
        self.facing = 1
        self.score = 0

    def input(self, keys):
        ax = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            ax -= ACCEL
            self.facing = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            ax += ACCEL
            self.facing = 1
        self.vx += ax
        self.vx = clamp(self.vx, -MAX_RUN, MAX_RUN)

    def jump(self):
        if self.on_ground:
            self.vy = -JUMP_VELOCITY
            self.on_ground = False

    def apply_gravity(self):
        self.vy += GRAVITY
        if self.vy > MAX_FALL:
            self.vy = MAX_FALL

    def move_and_collide(self, level: Level, dt):
        # Horizontal
        self.rect.x += int(self.vx)
        solids = level.rects_in_region(self.rect.x, self.rect.y, self.rect.right, self.rect.bottom, SOLID)
        for r in solids:
            if self.rect.colliderect(r):
                if self.vx > 0:
                    self.rect.right = r.left
                elif self.vx < 0:
                    self.rect.left = r.right
                self.vx = 0.0

        # Vertical
        self.rect.y += int(self.vy)
        self.on_ground = False
        solids = level.rects_in_region(self.rect.x, self.rect.y, self.rect.right, self.rect.bottom, SOLID)
        for r in solids:
            if self.rect.colliderect(r):
                if self.vy > 0:
                    self.rect.bottom = r.top
                    self.on_ground = True
                elif self.vy < 0:
                    self.rect.top = r.bottom
                self.vy = 0.0

        # Friction when grounded
        if self.on_ground:
            self.vx *= FRICTION
            if abs(self.vx) < 0.05:
                self.vx = 0.0

    def draw(self, surf, camx):
        # simple rounded rectangle character
        body = pygame.Rect(self.rect.x - camx, self.rect.y, self.rect.w, self.rect.h)
        pygame.draw.rect(surf, COL["player"], body, border_radius=4)
        pygame.draw.rect(surf, COL["player_outline"], body, width=2, border_radius=4)
        # tiny eye
        eye_r = 2
        ex = body.centerx + (3 * self.facing)
        ey = body.y + 6
        pygame.draw.circle(surf, (255,255,255), (ex, ey), eye_r)

class Enemy:
    def __init__(self, pos_px):
        self.rect = pygame.Rect(pos_px[0], pos_px[1], 16, 14)
        self.vx = random.choice([-1.1, 1.1])

    def update(self, level: Level):
        # basic ground-hugger with edge turn
        self.rect.x += int(self.vx)
        solids = level.rects_in_region(self.rect.x, self.rect.y, self.rect.right, self.rect.bottom, SOLID)
        for r in solids:
            if self.rect.colliderect(r):
                if self.vx > 0:
                    self.rect.right = r.left
                else:
                    self.rect.left = r.right
                self.vx *= -1

        # edge detect
        ahead_x = self.rect.centerx + (10 if self.vx > 0 else -10)
        ahead_y = self.rect.bottom + 2
        below = level.rects_in_region(ahead_x, ahead_y, ahead_x+2, ahead_y+2, SOLID)
        if not below:
            self.vx *= -1

    def draw(self, surf, camx):
        r = self.rect.move(-camx, 0)
        pygame.draw.rect(surf, COL["enemy"], r, border_radius=3)
        pygame.draw.circle(surf, COL["enemy_eye"], (r.centerx-3, r.y+5), 2)
        pygame.draw.circle(surf, COL["enemy_eye"], (r.centerx+3, r.y+5), 2)

# Game ------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("ULTRA! LEGACY MAARIO 0.1 [C] Samsoft")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)

        self.level_index = 1
        self.level = Level(self.level_index)
        sx, sy = self.level.spawn
        self.player = Player(sx * TILE + 2, (sy + 1) * TILE - 18)
        self.camx = 0
        self.coins_left = set(self.level.coins)

    def restart_level(self):
        self.level = Level(self.level_index)
        sx, sy = self.level.spawn
        self.player = Player(sx * TILE + 2, (sy + 1) * TILE - 18)
        self.coins_left = set(self.level.coins)
        self.camx = 0

    def next_level(self):
        if self.level_index < MAX_LEVELS:
            self.level_index += 1
        else:
            self.level_index = 1
        self.restart_level()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE,):
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                        self.player.jump()
                    elif event.key == pygame.K_r:
                        self.restart_level()
                    elif event.key == pygame.K_n:
                        self.next_level()

            keys = pygame.key.get_pressed()
            self.player.input(keys)
            self.player.apply_gravity()
            self.player.move_and_collide(self.level, dt)

            # Interactions ----------------------------------------------------
            self.handle_coins()
            self.handle_springs()
            self.handle_spikes()
            self.update_enemies_and_handle_collisions()
            self.check_exit()

            # Camera follows player
            self.camx = clamp(self.player.rect.centerx - WIDTH // 2, 0, self.level.cols * TILE - WIDTH)

            # Draw
            self.draw()

        pygame.quit()

    # --- interactions ---------------------------------------------------------
    def handle_coins(self):
        # coins are at tile centers
        px, py = self.player.rect.centerx // TILE, self.player.rect.centery // TILE
        # check surrounding area for speed
        for cy in range(max(0, py-2), min(self.level.rows, py+3)):
            for cx in range(max(0, px-2), min(self.level.cols, px+3)):
                if (cx, cy) in self.coins_left:
                    c_rect = rect_from_cell(cx, cy)
                    if self.player.rect.colliderect(c_rect):
                        self.coins_left.remove((cx, cy))
                        self.level.map[cy][cx] = EMPTY
                        self.player.score += 10

    def handle_springs(self):
        px, py = self.player.rect.centerx // TILE, self.player.rect.bottom // TILE
        for cy in range(max(0, py-1), min(self.level.rows, py+2)):
            for cx in range(max(0, px-1), min(self.level.cols, px+2)):
                if self.level.map[cy][cx] == SPRING:
                    s_rect = rect_from_cell(cx, cy)
                    s_rect.y += TILE//4  # top area sensitivity
                    s_rect.h = TILE//3
                    if self.player.rect.colliderect(s_rect) and self.player.vy >= 0:
                        self.player.vy = -JUMP_VELOCITY * SPRING_BOOST
                        self.player.on_ground = False

    def handle_spikes(self):
        # treat spike as a hazard triangle; approximate with a top rectangle hitbox
        px, py = self.player.rect.centerx // TILE, self.player.rect.bottom // TILE
        for cy in range(max(0, py-1), min(self.level.rows, py+2)):
            for cx in range(max(0, px-1), min(self.level.cols, px+2)):
                if self.level.map[cy][cx] == SPIKE:
                    r = rect_from_cell(cx, cy)
                    r.y += TILE//2
                    r.h = TILE//2
                    if self.player.rect.colliderect(r):
                        self.restart_level()
                        return

    def update_enemies_and_handle_collisions(self):
        for e in self.level.enemies:
            e.update(self.level)
        # player-enemy collisions
        for e in self.level.enemies[:]:
            if self.player.rect.colliderect(e.rect):
                # stomp from above
                if self.player.vy > 1.5 and self.player.rect.bottom - e.rect.top < 10:
                    self.player.vy = -JUMP_VELOCITY * 0.7
                    self.level.enemies.remove(e)
                    self.player.score += 25
                else:
                    self.restart_level()
                    return

    def check_exit(self):
        ex, ey = self.level.exit_cell
        er = rect_from_cell(ex, ey)
        if self.player.rect.colliderect(er):
            self.player.score += 100
            self.next_level()

    # --- drawing --------------------------------------------------------------
    def draw_tile(self, surf, code, cx, cy, camx):
        x = cx * TILE - camx
        y = cy * TILE
        r = pygame.Rect(x, y, TILE, TILE)
        if code == DIRT:
            pygame.draw.rect(surf, COL["earth"], r)
        elif code == GRASS:
            pygame.draw.rect(surf, COL["earth"], r)
            top = pygame.Rect(x, y, TILE, 6)
            pygame.draw.rect(surf, COL["grass"], top)
        elif code == PLATFORM:
            pygame.draw.rect(surf, COL["platform"], r, border_radius=4)
            lip = pygame.Rect(x, y, TILE, 4)
            pygame.draw.rect(surf, (180,180,200), lip, border_top_left_radius=4, border_top_right_radius=4)
        elif code == SPIKE:
            # draw three little spikes
            for i in range(3):
                tip_x = x + 3 + i*6
                pygame.draw.polygon(surf, COL["spike"], [(tip_x, y+TILE-2), (tip_x+3, y+6), (tip_x+6, y+TILE-2)])
        elif code == COIN:
            pygame.draw.circle(surf, COL["coin"], (x + TILE//2, y + TILE//2), 5)
        elif code == SPRING:
            pygame.draw.rect(surf, COL["spring"], (x+4, y+10, TILE-8, 6))
            pygame.draw.rect(surf, (240, 120, 130), (x+6, y+6, TILE-12, 4))
        elif code == EXIT:
            door = pygame.Rect(x+3, y+3, TILE-6, TILE-2)
            pygame.draw.rect(surf, COL["exit"], door, border_radius=4)
            pygame.draw.rect(surf, (80,40,20), (x+TILE//2-2, y+TILE//2, 4, 4))

    def draw(self):
        self.screen.fill(COL["sky"])

        # draw visible tiles
        c0 = max(int(self.camx // TILE) - 1, 0)
        c1 = min(int((self.camx + WIDTH) // TILE) + 2, self.level.cols - 1)
        for cy in range(self.level.rows):
            for cx in range(c0, c1 + 1):
                t = self.level.map[cy][cx]
                if t != EMPTY:
                    self.draw_tile(self.screen, t, cx, cy, self.camx)

        for e in self.level.enemies:
            e.draw(self.screen, self.camx)
        self.player.draw(self.screen, self.camx)

        # HUD
        text = f"Level {self.level_index}/{MAX_LEVELS}   Score {self.player.score}   Coins {len(self.level.coins) - len(self.coins_left)}/{len(self.level.coins)}"
        img = self.font.render(text, True, COL["hud"])
        self.screen.blit(img, (8, 8))

        tip = self.font.render("Arrows/A-D to move, Space/W/Up to jump, R to restart, N next level, Esc to quit", True, COL["hud"])
        self.screen.blit(tip, (8, HEIGHT - 22))

        pygame.display.flip()

# Entrypoint ------------------------------------------------------------------
if __name__ == "__main__":
    # Avoid working dir surprises if launched from elsewhere
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    Game().run()
