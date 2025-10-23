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
#   N                       - skip to next level
#   Esc                     - quit
# Notes:
#   - All visuals are generated with basic shapes (no external assets).
#   - Levels are procedurally generated on the fly based on level_index.
#   - Designed to be compact and readable rather than feature-complete.
#   - Optimized: Pre-rendered level and background surfaces; NES-style scanlines.
#   - Game over on death (enemies, spikes, falls); SMB1-style NES HUD.
#
# Tested with pygame 2.x
#   pip install pygame
#   python program.py
#
# Changelog (this fixed build):
#   - Fixed syntax errors and incomplete level generation (cloud list append, etc.).
#   - Completed procedural generation for coins, spikes, platforms, springs, exit placement.
#   - Implemented enemies (Goomba-like), stomp logic, and hazards.
#   - Robust tile collisions (axis-separated), coyote-time jumps, and friction/acceleration.
#   - Pre-rendered background (sky, hills, clouds) and tilemap for performance.
#   - NES-style scanline overlay, HUD, restart/next-level/game-over loops.
#   - No external assets; everything drawn with primitives.
#
import math
import random
import sys
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

# Colors (simple palette, extended for SMB1 style; NES-inspired)
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
    "hud": (0, 0, 0),  # Black for NES-style text
    "exit": (250, 120, 50),
    "mario_flesh": (255, 220, 177),
    "mario_hat": (200, 0, 0),
    "mario_shirt": (255, 0, 0),
    "mario_overalls": (0, 0, 255),
    "mario_glove": (255, 255, 255),
    "mario_shoe": (139, 69, 19),
    "mario_black": (0, 0, 0),
    # Goomba colors
    "goomba_body": (101, 67, 33),
    "goomba_dark": (79, 52, 26),
    "goomba_eye_black": (0, 0, 0),
    "goomba_pupil": (255, 255, 255),
    # Background
    "cloud": (255, 255, 255),
    "hill": (34, 139, 34)
}

# Utility ---------------------------------------------------------------------
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def rect_from_cell(cx, cy):
    return pygame.Rect(cx * TILE, cy * TILE, TILE, TILE)

# Pre-rendered global sprites -------------------------------------------------
def create_goomba_sprite():
    temp = pygame.Surface((16, 14), pygame.SRCALPHA)
    # Goomba body
    body_rect = pygame.Rect(2, 2, 12, 10)
    pygame.draw.ellipse(temp, COL["goomba_body"], body_rect)
    # Feet (darker brown)
    pygame.draw.rect(temp, COL["goomba_dark"], pygame.Rect(3, 10, 3, 2))
    pygame.draw.rect(temp, COL["goomba_dark"], pygame.Rect(10, 10, 3, 2))
    # Eyes (black with white pupils)
    pygame.draw.ellipse(temp, COL["goomba_eye_black"], pygame.Rect(4, 4, 3, 3))
    pygame.draw.ellipse(temp, COL["goomba_eye_black"], pygame.Rect(9, 4, 3, 3))
    pygame.draw.circle(temp, COL["goomba_pupil"], (5, 5), 1)
    pygame.draw.circle(temp, COL["goomba_pupil"], (10, 5), 1)
    # Teeth
    pygame.draw.rect(temp, COL["goomba_eye_black"], pygame.Rect(6, 8, 1, 2))
    pygame.draw.rect(temp, COL["goomba_eye_black"], pygame.Rect(9, 8, 1, 2))
    return temp

def create_tile_surfaces():
    tile_surfaces = {}
    for code in range(1, 8):  # Skip EMPTY
        surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        x, y = 0, 0
        r = pygame.Rect(x, y, TILE, TILE)
        if code == DIRT:
            # SMB1 brick/dirt pattern
            pygame.draw.rect(surf, COL["earth"], r)
            for i in range(1, 5):
                pygame.draw.line(surf, (100, 70, 40), (x, y + i*4), (x + TILE, y + i*4), 1)
            for i in range(0, TILE, 8):
                pygame.draw.line(surf, (100, 70, 40), (x + i, y), (x + i, y + TILE), 1)
        elif code == GRASS:
            pygame.draw.rect(surf, COL["earth"], r)
            top_h = 6
            pygame.draw.rect(surf, COL["grass"], pygame.Rect(x, y, TILE, top_h))
            for i in range(0, TILE, 3):
                pygame.draw.line(surf, (40, 140, 40), (x + i, y + top_h), (x + i + 1, y), 1)
        elif code == PLATFORM:
            pygame.draw.rect(surf, COL["platform"], r)
            for i in range(1, 5):
                pygame.draw.line(surf, (100, 100, 120), (x, y + i*4), (x + TILE, y + i*4), 1)
            for i in range(0, TILE, 8):
                pygame.draw.line(surf, (100, 100, 120), (x + i, y), (x + i, y + TILE), 1)
            pygame.draw.rect(surf, (180, 180, 200), pygame.Rect(x, y, TILE, 2))
        elif code == SPIKE:
            for i in range(3):
                tip_x = x + 3 + i*6
                pygame.draw.polygon(surf, COL["spike"],
                                    [(tip_x, y+TILE-2), (tip_x+3, y+6), (tip_x+6, y+TILE-2)])
        elif code == COIN:
            center_x, center_y = x + TILE//2, y + TILE//2
            pygame.draw.circle(surf, COL["coin"], (center_x, center_y), 8)
            shine_r = pygame.Rect(center_x - 2, center_y - 4, 4, 3)
            pygame.draw.ellipse(surf, (255, 255, 200), shine_r)
        elif code == SPRING:
            pygame.draw.rect(surf, COL["spring"], (x+4, y+10, TILE-8, 6))
            pygame.draw.rect(surf, (240, 120, 130), (x+6, y+6, TILE-12, 4))
            pygame.draw.circle(surf, COL["spring"], (x + TILE//2, y + TILE//2), 2)
        elif code == EXIT:
            # Flagpole
            pygame.draw.rect(surf, COL["mario_black"], pygame.Rect(x + TILE//2 - 1, y - 10, 2, TILE + 10))
            flag_points = [(x + TILE//2, y - 8), (x + TILE//2 + 6, y - 5), (x + TILE//2, y - 2)]
            pygame.draw.polygon(surf, COL["mario_shirt"], flag_points)
        tile_surfaces[code] = surf
    return tile_surfaces

# Level generation ------------------------------------------------------------
class Level:
    def __init__(self, index, tile_surfaces):
        self.index = index
        self.tile_surfaces = tile_surfaces
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
        self.clouds = []  # list of (cx, cy) for cloud centers
        self.hills = []  # list of (cx, height)

        self._generate()
        self._render_surfaces()

    def _generate(self):
        rnd = random.Random(1337 + self.index * 99991)

        # --- baseline terrain ridge (gentle drift + pits) --------------------
        ground = [14] * self.cols
        cur = rnd.randint(12, 16)
        x = 0
        while x < self.cols:
            # occasional pits (increase with level)
            if rnd.random() < clamp(0.03 + self.index * 0.0025, 0, 0.10) and 5 < x < self.cols - 6:
                w = rnd.randint(1, 2 + (self.index // 8))  # width grows slightly with level
                for i in range(w):
                    if x + i < self.cols:
                        ground[x + i] = ROWS  # no ground (pit)
                x += w
                continue

            # gentle height drift
            if rnd.random() < 0.23:
                cur += rnd.choice([-1, 0, 1])
                cur = clamp(cur, 10, ROWS - 3)
            ground[x] = cur
            x += 1

        # lay terrain
        for cx in range(self.cols):
            g = ground[cx]
            if g >= ROWS:  # pit
                continue
            # top grass, dirt below
            self.map[g][cx] = GRASS
            for y in range(g + 1, self.rows):
                self.map[y][cx] = DIRT

        # --- Background elements (hills + clouds) ----------------------------
        hill_spacing = 20 + rnd.randint(0, 10)
        hx = 0
        while hx < self.cols:
            hwidth = rnd.randint(8, 15)
            hheight = rnd.randint(3, 6)
            self.hills.append((hx + hwidth // 2, ROWS - hheight))
            hx += hwidth + hill_spacing + rnd.randint(0, 5)

        cloud_count = 3 + self.index // 4
        for _ in range(cloud_count):
            cx = rnd.randint(5, self.cols - 6)
            cy = rnd.randint(2, 8)
            self.clouds.append((cx, cy))

        # --- Platforms -------------------------------------------------------
        plat_attempts = 25 + self.index * 2
        for _ in range(plat_attempts):
            cx = rnd.randint(3, self.cols - 4)
            base = ground[cx]
            if base >= ROWS:
                continue
            cy = clamp(base - rnd.randint(3, 6), 3, ROWS - 7)
            length = rnd.randint(2, 6)
            for i in range(length):
                ccx = cx + i
                if 0 <= ccx < self.cols:
                    self.map[cy][ccx] = PLATFORM

        # --- Spikes on flat tops --------------------------------------------
        for cx in range(2, self.cols - 2):
            g = ground[cx]
            if g >= ROWS:
                continue
            if rnd.random() < 0.06 and self.map[g][cx] == GRASS:
                self.map[g - 1][cx] = SPIKE
                self.spikes.add((cx, g - 1))

        # --- Springs ---------------------------------------------------------
        for cx in range(3, self.cols - 3):
            g = ground[cx]
            if g >= ROWS:
                continue
            if rnd.random() < 0.02:
                self.map[g - 1][cx] = SPRING
                self.springs.add((cx, g - 1))

        # --- Coins (clusters) -----------------------------------------------
        coin_groups = 20
        for _ in range(coin_groups):
            cx = rnd.randint(2, self.cols - 3)
            base = ground[cx]
            if base >= ROWS:
                continue
            cy = clamp(base - rnd.randint(3, 7), 2, ROWS - 8)
            span = rnd.randint(2, 5)
            for i in range(span):
                ccx = cx + i
                if 0 <= ccx < self.cols and self.map[cy][ccx] == EMPTY:
                    self.map[cy][ccx] = COIN
                    self.coins.add((ccx, cy))

        # --- Enemies ---------------------------------------------------------
        enemy_count = min(24, 6 + self.index // 2)
        for _ in range(enemy_count):
            cx = rnd.randint(4, self.cols - 4)
            gy = ground[cx]
            if gy >= ROWS:
                continue
            # don't spawn on spikes or springs
            if self.map[gy - 1][cx] in (SPIKE, SPRING):
                continue
            self.enemies.append(Enemy(cx * TILE + 2, (gy - 1) * TILE + 6, rnd.choice([-1, 1])))

        # --- Spawn & Exit ----------------------------------------------------
        # spawn near the first safe ground
        for cx in range(2, min(18, self.cols - 1)):
            g = ground[cx]
            if g < ROWS and self.map[g - 1][cx] not in (SPIKE, SPRING):
                self.spawn = (cx, g - 2)
                break

        # exit at the last safe column
        for cx in range(self.cols - 6, 5, -1):
            g = ground[cx]
            if g < ROWS:
                self.exit_cell = (cx, g - 1)
                self.map[g - 1][cx] = EXIT
                break

    # ------------------------------------------------------------------------
    def _render_surfaces(self):
        # Pre-render background (sky + hills + clouds)
        self.bg_surface = pygame.Surface((self.cols * TILE, HEIGHT)).convert()
        self.bg_surface.fill(COL["sky"])

        # Hills
        for center_cx, top_row in self.hills:
            cx_px = center_cx * TILE
            top_py = top_row * TILE
            base_py = HEIGHT
            width = 8 * TILE
            hill_rect = pygame.Rect(cx_px - width // 2, top_py, width, base_py - top_py)
            pygame.draw.ellipse(self.bg_surface, COL["hill"], hill_rect)

        # Clouds
        def draw_cloud(surface, cx_cell, cy_cell):
            x = cx_cell * TILE
            y = cy_cell * TILE
            pygame.draw.circle(surface, COL["cloud"], (x, y), 10)
            pygame.draw.circle(surface, COL["cloud"], (x + 12, y + 2), 12)
            pygame.draw.circle(surface, COL["cloud"], (x - 12, y + 2), 12)
            pygame.draw.circle(surface, COL["cloud"], (x, y + 6), 12)
        for (cx, cy) in self.clouds:
            draw_cloud(self.bg_surface, cx, cy)

        # Pre-render tile map
        self.map_surface = pygame.Surface((self.cols * TILE, self.rows * TILE), pygame.SRCALPHA).convert_alpha()
        for cy in range(self.rows):
            for cx in range(self.cols):
                code = self.map[cy][cx]
                if code != EMPTY:
                    surf = self.tile_surfaces.get(code)
                    if surf:
                        self.map_surface.blit(surf, (cx * TILE, cy * TILE))

    # Helpers -----------------------------------------------------------------
    def tile_at_cell(self, cx, cy):
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            return self.map[cy][cx]
        return EMPTY

    def is_solid_at_cell(self, cx, cy):
        return self.tile_at_cell(cx, cy) in SOLID

    def hazard_hit(self, rect):
        # spikes or fall
        if rect.top >= ROWS * TILE + 80:
            return True
        # check spikes overlap
        left = rect.left // TILE
        right = (rect.right - 1) // TILE
        top = rect.top // TILE
        bottom = (rect.bottom - 1) // TILE
        for cy in range(top, bottom + 1):
            for cx in range(left, right + 1):
                if self.tile_at_cell(cx, cy) == SPIKE:
                    if rect.colliderect(rect_from_cell(cx, cy)):
                        return True
        return False

# Entities --------------------------------------------------------------------
class Enemy:
    def __init__(self, x, y, direction=1):
        self.rect = pygame.Rect(int(x), int(y), 16, 14)
        self.vx = 0.7 * direction

    def update(self, level: Level):
        # Move horizontally, reverse on wall or edge
        self.rect.x += int(self.vx)
        # wall collision
        if self._hits_solid(level):
            self.rect.x -= int(self.vx)
            self.vx *= -1
        # edge detection: if front foot would fall
        front_x = self.rect.centerx + (8 if self.vx > 0 else -8)
        foot_y = self.rect.bottom + 1
        front_cx = front_x // TILE
        below_cy = foot_y // TILE
        if not level.is_solid_at_cell(front_cx, below_cy):
            self.vx *= -1

    def _hits_solid(self, level: Level):
        left = self.rect.left // TILE
        right = (self.rect.right - 1) // TILE
        top = self.rect.top // TILE
        bottom = (self.rect.bottom - 1) // TILE
        for cy in range(top, bottom + 1):
            for cx in range(left, right + 1):
                if level.is_solid_at_cell(cx, cy):
                    if self.rect.colliderect(rect_from_cell(cx, cy)):
                        return True
        return False

    def draw(self, surface, cam_x, goomba_sprite):
        img = goomba_sprite
        if self.vx < 0:
            img = pygame.transform.flip(goomba_sprite, True, False)
        surface.blit(img, (self.rect.x - cam_x, self.rect.y))

class Player:
    def __init__(self, spawn_cell):
        sx, sy = spawn_cell
        self.rect = pygame.Rect(sx * TILE, sy * TILE, 14, 18)
        self.vx, self.vy = 0.0, 0.0
        self.on_ground = False
        self.coyote_time = 0.0
        self.coins = 0
        self.lives = 3
        self.score = 0

    def update(self, keys, level: Level, dt):
        ax = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            ax -= ACCEL
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            ax += ACCEL

        # Horizontal acceleration + friction
        self.vx += ax
        if ax == 0:
            self.vx *= FRICTION
            if abs(self.vx) < 0.02:
                self.vx = 0.0
        self.vx = clamp(self.vx, -MAX_RUN, MAX_RUN)

        # Apply gravity
        self.vy += GRAVITY
        self.vy = clamp(self.vy, -50, MAX_FALL)

        # Coyote time
        if self.on_ground:
            self.coyote_time = 0.12
        else:
            self.coyote_time = max(0.0, self.coyote_time - dt)

        # Jump
        want_jump = (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP])
        if want_jump and self.coyote_time > 0.0:
            self.vy = -JUMP_VELOCITY
            self.on_ground = False
            self.coyote_time = 0.0

        # Move and collide
        self._move_and_collide(level, dt)

        # Collect coins
        self._collect(level)

    def _move_and_collide(self, level: Level, dt):
        # Horizontal
        dx = self.vx
        self.rect.x += int(dx)
        if self._collide_solid(level):
            # resolve
            if dx > 0:
                self._resolve_right(level)
            elif dx < 0:
                self._resolve_left(level)
            self.vx = 0.0

        # Vertical
        dy = self.vy
        self.rect.y += int(dy)
        landed = False
        hit_head = False
        colliding, first_tile = self._collide_solid(level, return_first=True)
        if colliding:
            if dy > 0:
                # coming down: place on top
                self.rect.bottom = first_tile.top
                landed = True
            elif dy < 0:
                # going up: place under
                self.rect.top = first_tile.bottom
                hit_head = True
            self.vy = 0.0

        # Springs (only when landing on top of them)
        if landed:
            # determine tile under feet
            feet_cy = (self.rect.bottom) // TILE
            cx_left = self.rect.left // TILE
            cx_right = (self.rect.right - 1) // TILE
            for cx in range(cx_left, cx_right + 1):
                if level.tile_at_cell(cx, feet_cy) == SPRING:
                    self.vy = -JUMP_VELOCITY * SPRING_BOOST
                    landed = False
                    break

        self.on_ground = landed and not hit_head

        # Hazards
        if level.hazard_hit(self.rect):
            raise PlayerDied()

    def _collect(self, level: Level):
        left = self.rect.left // TILE
        right = (self.rect.right - 1) // TILE
        top = self.rect.top // TILE
        bottom = (self.rect.bottom - 1) // TILE
        for cy in range(top, bottom + 1):
            for cx in range(left, right + 1):
                if level.tile_at_cell(cx, cy) == COIN and (cx, cy) in level.coins:
                    # Remove coin from map & surface
                    level.coins.remove((cx, cy))
                    level.map[cy][cx] = EMPTY
                    self.coins += 1
                    self.score += 100
                    # Clear that tile area on pre-render (cheap re-blit)
                    pygame.draw.rect(level.map_surface, (0, 0, 0, 0), rect_from_cell(cx, cy))

    def _collide_solid(self, level: Level, return_first=False):
        left = self.rect.left // TILE
        right = (self.rect.right - 1) // TILE
        top = self.rect.top // TILE
        bottom = (self.rect.bottom - 1) // TILE
        first_rect = None
        for cy in range(top, bottom + 1):
            for cx in range(left, right + 1):
                if level.is_solid_at_cell(cx, cy):
                    trect = rect_from_cell(cx, cy)
                    if self.rect.colliderect(trect):
                        if return_first:
                            return True, trect
                        else:
                            return True
        if return_first:
            return False, first_rect
        return False

    def _resolve_left(self, level: Level):
        # Move right until not colliding
        left = self.rect.left // TILE
        top = self.rect.top // TILE
        bottom = (self.rect.bottom - 1) // TILE
        for cx in range(left, left + 2):
            for cy in range(top, bottom + 1):
                if level.is_solid_at_cell(cx, cy):
                    self.rect.left = rect_from_cell(cx, cy).right

    def _resolve_right(self, level: Level):
        right = (self.rect.right - 1) // TILE
        top = self.rect.top // TILE
        bottom = (self.rect.bottom - 1) // TILE
        for cx in range(right, right - 2, -1):
            for cy in range(top, bottom + 1):
                if level.is_solid_at_cell(cx, cy):
                    self.rect.right = rect_from_cell(cx, cy).left

class PlayerDied(Exception):
    pass

# Drawing helpers -------------------------------------------------------------
def draw_player(surface, player: Player, cam_x):
    # Simple "Mario-ish" blocky character with outline
    x = player.rect.x - cam_x
    y = player.rect.y
    body = pygame.Rect(x, y, player.rect.w, player.rect.h)
    pygame.draw.rect(surface, COL["player"], body)
    pygame.draw.rect(surface, COL["player_outline"], body, 1)

def draw_hud(surface, font, level_idx, player: Player, time_left):
    # SMB1-like HUD
    txt = f"SCORE {player.score:06d}   COIN {player.coins:02d}   WORLD {level_idx+1:02d}-{(level_idx%4)+1}   TIME {int(time_left):03d}"
    img = font.render(txt, True, COL["hud"])
    surface.blit(img, (10, 6))

def make_scanlines():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(overlay, (0, 0, 0, 32), (0, y), (WIDTH, y))
    return overlay

# Main game loop --------------------------------------------------------------
def run_game():
    pygame.init()
    pygame.display.set_caption("ULTRA! LEGACY MAARIO 0.1 — Samsoft")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 18)

    goomba_sprite = create_goomba_sprite()
    tile_surfaces = create_tile_surfaces()
    scanlines = make_scanlines()

    level_index = 0
    level = Level(level_index, tile_surfaces)
    player = Player(level.spawn)

    # Camera
    cam_x = 0

    # Timing
    level_time = 400.0  # SMB-ish countdown

    running = True
    game_over = False
    won = False

    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    # restart level
                    level = Level(level_index, tile_surfaces)
                    player = Player(level.spawn)
                    cam_x = 0
                    game_over = False
                    won = False
                    level_time = 400.0
                if event.key == pygame.K_n:
                    # next level (testing)
                    level_index = (level_index + 1) % MAX_LEVELS
                    level = Level(level_index, tile_surfaces)
                    player = Player(level.spawn)
                    cam_x = 0
                    game_over = False
                    won = False
                    level_time = 400.0

        keys = pygame.key.get_pressed()

        # Update -------------------------------------------------------------
        if not game_over and not won:
            level_time = max(0.0, level_time - dt)
            try:
                # Player
                player.update(keys, level, dt)

                # Enemies
                for e in level.enemies:
                    e.update(level)

                # Player vs Enemy
                for e in list(level.enemies):
                    if player.rect.colliderect(e.rect):
                        # stomp check
                        if player.vy > 0 and player.rect.centery < e.rect.top + 6:
                            # stomp
                            level.enemies.remove(e)
                            player.score += 200
                            player.vy = -JUMP_VELOCITY * 0.6
                        else:
                            raise PlayerDied()

                # Exit reached?
                ex_cx, ex_cy = level.exit_cell
                exit_rect = rect_from_cell(ex_cx, ex_cy)
                if player.rect.colliderect(exit_rect):
                    level_index += 1
                    if level_index >= MAX_LEVELS:
                        won = True
                    else:
                        level = Level(level_index, tile_surfaces)
                        player = Player(level.spawn)
                        cam_x = 0
                        level_time = 400.0

                # Time over?
                if level_time <= 0.0:
                    raise PlayerDied()

            except PlayerDied:
                player.lives -= 1
                if player.lives <= 0:
                    game_over = True
                else:
                    # respawn
                    player = Player(level.spawn)

            # Camera follow
            cam_x = int(player.rect.centerx - WIDTH // 2)
            cam_x = clamp(cam_x, 0, level.cols * TILE - WIDTH)

        # Draw ---------------------------------------------------------------
        # Background
        screen.blit(level.bg_surface, (-cam_x * 0.5, 0))  # slight parallax

        # Tilemap
        screen.blit(level.map_surface, (-cam_x, 0))

        # Enemies
        for e in level.enemies:
            e.draw(screen, cam_x, goomba_sprite)

        # Player
        draw_player(screen, player, cam_x)

        # HUD & overlays
        draw_hud(screen, font, level_index, player, level_time)
        screen.blit(scanlines, (0, 0))

        # UI states
        if game_over:
            msg = font.render("GAME OVER — press R to restart level, N for next, Esc to quit.", True, COL["hud"])
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 8))
        elif won:
            msg = font.render("YOU CLEARED ALL 32 LEVELS! Press R to replay or Esc to quit.", True, COL["hud"])
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 8))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    try:
        run_game()
    except Exception as e:
        # In case something unexpected happens, fail gracefully in console.
        print("Fatal error:", e)
        pygame.quit()
        sys.exit(1)
