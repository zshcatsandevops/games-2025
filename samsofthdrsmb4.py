#!/usr/bin/env python3
# program.py — Single-file, no-asset Pygame platformer
# 600x400 window • Main Menu → Overworld Map → 32 procedurally generated levels
# Inspired by classic side-scrollers but uses original level generation and shapes (no IP assets).
#
# Controls:
#   MENU / MAP:  Enter = select,  Arrow keys = move,  Esc = quit
#   IN-LEVEL:    ← → = move,  Z or Space = jump,  P = pause,  Esc = quit
#
# Python 3.10+ recommended. Requires pygame (pip install pygame).
# Tested with pygame 2.x.
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from typing import List, Tuple

import pygame

# ------------------------------
# Configuration / Constants
# ------------------------------
WIDTH, HEIGHT = 600, 400
TILE = 20
FPS = 60

# Tile types
AIR = 0
GROUND = 1
BRICK = 2
QBLOCK = 3
PIPE = 4
FLAG = 5  # not solid; used to detect goal

SOLID_TILES = {GROUND, BRICK, QBLOCK, PIPE}

# Colors (RGB)
COL_BG = (135, 206, 235)       # sky blue
COL_GROUND = (155, 118, 83)    # ground brown
COL_BRICK = (110, 70, 50)      # brick
COL_QBLOCK = (222, 186, 80)    # q-block gold
COL_PIPE = (34, 139, 34)       # green
COL_FLAG = (240, 240, 240)     # light flag pole
COL_FLAG_TOP = (220, 30, 30)   # red flag
COL_PLAYER = (255, 255, 255)   # white
COL_PLAYER_ACCENT = (20, 20, 20)
COL_ENEMY = (190, 60, 60)
COL_COIN = (255, 220, 0)
COL_TEXT = (30, 30, 30)
COL_SHADOW = (0, 0, 0)

# Player physics
MOVE_SPEED = 2.4
AIR_CONTROL = 0.85
FRICTION = 0.82
GRAVITY = 0.35
JUMP_VELOCITY = -7.2
TERMINAL_VY = 10.0

# Enemy
ENEMY_SPEED = 1.0

# Game states
MENU = "menu"
WORLD_MAP = "world_map"
PLAYING = "playing"
PAUSED = "paused"
GAME_OVER = "game_over"

# ------------------------------
# Utilities
# ------------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def tile_rect(tx: int, ty: int) -> pygame.Rect:
    return pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)

# ------------------------------
# Level generation
# ------------------------------
class Level:
    def __init__(self, world: int, stage: int, width_tiles: int = 160, height_tiles: int = 20):
        # Seed with world/stage to make levels stable across runs.
        seed = (world + 1) * 100 + (stage + 1) * 7
        self.rng = random.Random(seed)
        self.world = world
        self.stage = stage
        self.width = width_tiles
        self.height = height_tiles
        self.tiles = [[AIR for _ in range(self.width)] for _ in range(self.height)]
        self.enemies: List["Enemy"] = []
        self.coins: List[pygame.Rect] = []
        self.goal_rect = pygame.Rect(0, 0, TILE, TILE * 6)

        self._generate()

    @property
    def pixel_width(self) -> int:
        return self.width * TILE

    def _generate(self):
        # Ground height profile and gaps
        base = self.rng.randint(12, 15)  # y value where ground begins
        ground = [base for _ in range(self.width)]
        x = 0
        while x < self.width:
            if 8 < x < self.width - 20 and self.rng.random() < 0.06:
                # gap (pit)
                gap_len = self.rng.randint(1, 3)
                for i in range(gap_len):
                    if x + i < self.width:
                        ground[x + i] = self.height  # no ground -> pit
                x += gap_len
            else:
                # gentle slopes
                if self.rng.random() < 0.2:
                    delta = self.rng.choice([-1, 0, 1])
                    new = clamp(ground[x - 1] + delta if x > 0 else base, 10, 17)
                    ground[x] = new
                x += 1

        # Lay down ground tiles
        for tx in range(self.width):
            gy = ground[tx]
            for ty in range(gy, self.height):
                self.tiles[ty][tx] = GROUND

        # Bricks & question blocks above ground
        for tx in range(4, self.width - 6):
            gy = ground[tx]
            near_gap = gy >= self.height  # treat gap as near-gap
            if not near_gap and self.rng.random() < 0.05:
                ty = gy - self.rng.choice([3, 4])
                if 2 <= ty < self.height:
                    self.tiles[ty][tx] = BRICK
            if not near_gap and self.rng.random() < 0.04:
                ty = gy - self.rng.choice([4, 5])
                if 2 <= ty < self.height:
                    self.tiles[ty][tx] = QBLOCK

        # Pipes (2-wide), spaced out
        tx = 10
        while tx < self.width - 15:
            if self.rng.random() < 0.12:
                gy = ground[tx]
                if gy < self.height:
                    h = self.rng.randint(2, 4)
                    for w in (0, 1):
                        for ty in range(gy - h, gy):
                            if 1 <= ty < self.height:
                                self.tiles[ty][tx + w] = PIPE
                tx += self.rng.randint(8, 14)
            else:
                tx += 1

        # Coins sprinkled
        for tx in range(6, self.width - 6):
            gy = ground[tx]
            if gy < self.height and self.rng.random() < 0.07:
                ty = gy - self.rng.choice([5, 6, 7])
                if 1 <= ty < self.height and self.tiles[ty][tx] == AIR:
                    self.coins.append(pygame.Rect(tx * TILE + 5, ty * TILE + 5, TILE - 10, TILE - 10))

        # Enemies walking on ground tops
        for tx in range(8, self.width - 12):
            gy = ground[tx]
            if gy < self.height and self.tiles[gy - 1][tx] == AIR and self.rng.random() < 0.08:
                ex = tx * TILE + 3
                ey = (gy - 1) * TILE - 12
                direction = -1 if self.rng.random() < 0.5 else 1
                self.enemies.append(Enemy(ex, ey, direction))

        # Start & goal
        self.start_px = 2 * TILE
        start_gy = ground[2] if 2 < len(ground) else base
        self.start_py = (start_gy - 2) * TILE - 4

        flag_tx = self.width - 4
        flag_gy = ground[flag_tx]
        flag_top = max(2, flag_gy - 6)
        self.goal_rect = pygame.Rect(flag_tx * TILE, flag_top * TILE, TILE, (flag_gy - flag_top) * TILE)
        for ty in range(flag_top, flag_gy):
            self.tiles[ty][flag_tx] = FLAG  # not solid, drawn visually

    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.width and 0 <= ty < self.height

    def tile_at(self, tx: int, ty: int) -> int:
        if not self.in_bounds(tx, ty):
            # Make left border solid, right empty to allow finishing
            if tx < 0:  # left wall
                return BRICK
            if ty >= self.height:
                return GROUND  # below bottom counts as solid
            return AIR
        return self.tiles[ty][tx]

    def is_solid(self, tx: int, ty: int) -> bool:
        return self.tile_at(tx, ty) in SOLID_TILES

    def solids_in_rect(self, rect: pygame.Rect) -> List[pygame.Rect]:
        left = max(0, rect.left // TILE - 1)
        right = min(self.width - 1, rect.right // TILE + 1)
        top = max(0, rect.top // TILE - 1)
        bottom = min(self.height - 1, rect.bottom // TILE + 1)
        hits = []
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if self.is_solid(tx, ty):
                    r = tile_rect(tx, ty)
                    if rect.colliderect(r):
                        hits.append(r)
        return hits

    def draw(self, surf: pygame.Surface, cam_x: int):
        surf.fill(COL_BG)
        # Visible tile range
        left = max(0, cam_x // TILE)
        right = min(self.width, (cam_x + WIDTH) // TILE + 2)

        # Draw tiles
        for ty in range(self.height):
            for tx in range(left, right):
                t = self.tiles[ty][tx]
                if t == AIR:
                    continue
                r = pygame.Rect(tx * TILE - cam_x, ty * TILE, TILE, TILE)
                if t == GROUND:
                    pygame.draw.rect(surf, COL_GROUND, r)
                elif t == BRICK:
                    pygame.draw.rect(surf, COL_BRICK, r)
                    # brick grooves
                    pygame.draw.line(surf, (80, 50, 40), (r.left, r.centery), (r.right, r.centery), 1)
                    pygame.draw.line(surf, (80, 50, 40), (r.centerx, r.top), (r.centerx, r.bottom), 1)
                elif t == QBLOCK:
                    pygame.draw.rect(surf, COL_QBLOCK, r)
                    pygame.draw.rect(surf, (180, 150, 60), r, 2)
                elif t == PIPE:
                    pygame.draw.rect(surf, COL_PIPE, r)
                    topband = pygame.Rect(r.left - 2, r.top - 4, r.width + 4, 6)
                    pygame.draw.rect(surf, COL_PIPE, topband)
                elif t == FLAG:
                    # draw pole & flag
                    pole = pygame.Rect(r.centerx - 1, r.top, 2, r.height)
                    pygame.draw.rect(surf, COL_FLAG, pole)
                    flag = pygame.Rect(pole.right, r.top + 4, 10, 8)
                    pygame.draw.rect(surf, COL_FLAG_TOP, flag)

        # Draw coins
        for c in self.coins:
            if c.right < cam_x or c.left > cam_x + WIDTH:
                continue
            rc = c.copy()
            rc.x -= cam_x
            pygame.draw.ellipse(surf, COL_COIN, rc)
            pygame.draw.ellipse(surf, (200, 170, 0), rc, 2)

# ------------------------------
# Entities
# ------------------------------
class Player:
    WIDTH = 14
    HEIGHT = 18

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.lives = 3
        self.score = 0
        self.coins = 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.WIDTH, self.HEIGHT)

    def kill(self):
        self.lives -= 1
        return self.lives

    def move_and_collide(self, level: Level, dx: float, dy: float):
        # Horizontal
        self.x += dx
        r = self.rect
        for solid in level.solids_in_rect(r):
            if dx > 0 and r.right > solid.left:
                r.right = solid.left
                self.x = r.x
                self.vx = 0
            elif dx < 0 and r.left < solid.right:
                r.left = solid.right
                self.x = r.x
                self.vx = 0

        # Vertical
        self.y += dy
        r = self.rect
        self.on_ground = False
        for solid in level.solids_in_rect(r):
            if dy > 0 and r.bottom > solid.top:
                r.bottom = solid.top
                self.y = r.y
                self.vy = 0
                self.on_ground = True
            elif dy < 0 and r.top < solid.bottom:
                r.top = solid.bottom
                self.y = r.y
                self.vy = 0

    def update(self, keys, level: Level):
        # Horizontal input
        move_dir = 0
        if keys[pygame.K_LEFT]:
            move_dir -= 1
        if keys[pygame.K_RIGHT]:
            move_dir += 1

        accel = MOVE_SPEED if self.on_ground else MOVE_SPEED * AIR_CONTROL
        target_vx = move_dir * MOVE_SPEED
        self.vx += (target_vx - self.vx) * (0.5 if self.on_ground else 0.2)

        # Friction if no input
        if move_dir == 0 and self.on_ground:
            self.vx *= FRICTION

        # Jump
        if (keys[pygame.K_z] or keys[pygame.K_SPACE]) and self.on_ground:
            self.vy = JUMP_VELOCITY
            self.on_ground = False

        # Gravity
        self.vy = clamp(self.vy + GRAVITY, -999, TERMINAL_VY)

        # Move and resolve
        self.move_and_collide(level, self.vx, 0)
        self.move_and_collide(level, 0, self.vy)

    def draw(self, surf: pygame.Surface, cam_x: int):
        r = self.rect.move(-cam_x, 0)
        # body
        pygame.draw.rect(surf, COL_PLAYER, r)
        # face
        eye = pygame.Rect(r.centerx - 3, r.top + 4, 2, 2)
        pygame.draw.rect(surf, COL_PLAYER_ACCENT, eye)
        eye2 = pygame.Rect(r.centerx + 1, r.top + 4, 2, 2)
        pygame.draw.rect(surf, COL_PLAYER_ACCENT, eye2)

class Enemy:
    WIDTH = 14
    HEIGHT = 14

    def __init__(self, x, y, direction= -1):
        self.x = float(x)
        self.y = float(y)
        self.vx = ENEMY_SPEED * float(direction)
        self.vy = 0.0
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.WIDTH, self.HEIGHT)

    def update(self, level: Level):
        if not self.alive:
            return
        # simple AI: walk, fall with gravity, turn on collision or at ledges
        self.vy = clamp(self.vy + GRAVITY, -999, TERMINAL_VY)

        # anticipate ledge: tile just ahead under feet
        ahead_x = self.rect.centerx + (8 if self.vx > 0 else -8)
        ahead_tx = ahead_x // TILE
        feet_ty = (self.rect.bottom + 1) // TILE
        # If no ground below ahead, reverse (prevents walking into pits)
        if not level.is_solid(int(ahead_tx), int(feet_ty)):
            self.vx *= -1

        # Move with collisions
        self.x += self.vx
        r = self.rect
        for solid in level.solids_in_rect(r):
            if self.vx > 0 and r.right > solid.left:
                r.right = solid.left
                self.x = r.x
                self.vx *= -1
            elif self.vx < 0 and r.left < solid.right:
                r.left = solid.right
                self.x = r.x
                self.vx *= -1

        self.y += self.vy
        r = self.rect
        for solid in level.solids_in_rect(r):
            if self.vy > 0 and r.bottom > solid.top:
                r.bottom = solid.top
                self.y = r.y
                self.vy = 0
            elif self.vy < 0 and r.top < solid.bottom:
                r.top = solid.bottom
                self.y = r.y
                self.vy = 0

    def draw(self, surf: pygame.Surface, cam_x: int):
        if not self.alive:
            return
        r = self.rect.move(-cam_x, 0)
        pygame.draw.rect(surf, COL_ENEMY, r)
        # simple eyes
        pygame.draw.rect(surf, COL_SHADOW, (r.left+3, r.top+3, 2, 2))
        pygame.draw.rect(surf, COL_SHADOW, (r.right-5, r.top+3, 2, 2))

# ------------------------------
# Overworld Map
# ------------------------------
@dataclass
class Node:
    world: int
    stage: int
    pos: Tuple[int, int]
    cleared: bool = False

class Overworld:
    def __init__(self, progress: List[List[bool]]):
        self.progress = progress  # 8x4 booleans
        self.nodes: List[Node] = []
        self.sel_world = 0
        self.sel_stage = 0
        self._build_nodes()

    def _build_nodes(self):
        self.nodes.clear()
        # Arrange nodes in a neat grid: 4 columns × 8 rows
        margin_x = 70
        step_x = 120
        margin_y = 50
        step_y = 40
        for w in range(8):
            for s in range(4):
                x = margin_x + s * step_x
                y = margin_y + w * step_y
                self.nodes.append(Node(w, s, (x, y), cleared=self.progress[w][s]))

    def move_sel(self, dx: int, dy: int):
        self.sel_stage = clamp(self.sel_stage + dx, 0, 3)
        self.sel_world = clamp(self.sel_world + dy, 0, 7)

    def draw(self, surf: pygame.Surface):
        surf.fill((95, 200, 255))
        # decorative ground
        pygame.draw.rect(surf, (90, 170, 90), (0, HEIGHT - 60, WIDTH, 60))

        # Connectors (paths)
        for n in self.nodes:
            w, s = n.world, n.stage
            # draw horizontal path to next stage in same world
            if s < 3:
                n2 = self.get_node(w, s + 1)
                pygame.draw.line(surf, (220, 240, 220), n.pos, n2.pos, 4)

        # Nodes
        for n in self.nodes:
            x, y = n.pos
            radius = 12
            pygame.draw.circle(surf, (245, 245, 245), (x, y), radius)
            if n.cleared:
                pygame.draw.circle(surf, (255, 215, 0), (x, y), 6)
            else:
                pygame.draw.circle(surf, (160, 160, 160), (x, y), 6)

        # Selector
        s = self.get_node(self.sel_world, self.sel_stage)
        pygame.draw.circle(surf, (20, 20, 20), s.pos, 16, 2)

        # Labels
        font = pygame.font.SysFont(None, 24)
        title = font.render("Overworld — Choose a Level", True, COL_TEXT)
        surf.blit(title, (WIDTH//2 - title.get_width()//2, 8))

        sub = font.render(f"World {self.sel_world + 1} - {self.sel_stage + 1}  (Enter = Play, Arrows = Move, Esc = Quit)", True, COL_TEXT)
        surf.blit(sub, (WIDTH//2 - sub.get_width()//2, 30))

    def get_node(self, w: int, s: int) -> Node:
        idx = w * 4 + s
        return self.nodes[idx]

# ------------------------------
# Game
# ------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Program.py — 32 On-the-Fly Levels")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)
        self.bigfont = pygame.font.SysFont(None, 48)

        self.state = MENU
        self.progress = [[False for _ in range(4)] for _ in range(8)]  # 8 worlds x 4 stages
        self.overworld = Overworld(self.progress)
        self.level: Level | None = None
        self.player: Player | None = None
        self.cam_x = 0
        self.current_world = 0
        self.current_stage = 0
        self.paused = False

    # ------------- State Transitions
    def start_level(self, w: int, s: int):
        self.current_world, self.current_stage = w, s
        self.level = Level(w, s)
        self.player = Player(self.level.start_px, self.level.start_py)
        self.cam_x = 0
        self.state = PLAYING
        self.paused = False

    def complete_level(self):
        self.progress[self.current_world][self.current_stage] = True
        self.overworld = Overworld(self.progress)
        self.state = WORLD_MAP

    def lose_life_and_respawn(self):
        if self.player is None or self.level is None:
            return
        remaining = self.player.kill()
        if remaining <= 0:
            self.state = GAME_OVER
        else:
            # Respawn at start of level
            self.player.x, self.player.y = self.level.start_px, self.level.start_py
            self.player.vx, self.player.vy = 0.0, 0.0

    # ------------- Drawing Helpers
    def draw_text_center(self, text: str, y: int, big=False):
        f = self.bigfont if big else self.font
        s = f.render(text, True, COL_TEXT)
        self.screen.blit(s, (WIDTH//2 - s.get_width()//2, y))

    def draw_hud(self):
        if not self.player:
            return
        hud = self.font.render(
            f"W{self.current_world+1}-{self.current_stage+1}  Score:{self.player.score}  Coins:{self.player.coins}  Lives:{self.player.lives}",
            True, COL_TEXT)
        self.screen.blit(hud, (8, 8))

    # ------------- Event Loop
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.state in (MENU, WORLD_MAP):
                        running = False
                    elif self.state == PLAYING:
                        self.paused = not self.paused
                        self.state = PAUSED if self.paused else PLAYING
                    elif self.state == GAME_OVER:
                        running = False

            if self.state == MENU:
                self.update_menu()
            elif self.state == WORLD_MAP:
                self.update_world_map()
            elif self.state == PLAYING:
                self.update_playing()
            elif self.state == PAUSED:
                self.update_paused()
            elif self.state == GAME_OVER:
                self.update_game_over()

            pygame.display.flip()

        pygame.quit()

    # ------------- State Updates
    def update_menu(self):
        self.screen.fill((25, 25, 35))
        self.draw_text_center("program.py", 70, big=True)
        self.draw_text_center("Single-file Pygame • 600x400 • 32 on-the-fly levels", 120)
        self.draw_text_center("[Enter] Start    [Esc] Quit", 160)
        self.draw_text_center("No assets used. Original shapes & generator.", 200)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER]:
            self.state = WORLD_MAP

    def update_world_map(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.overworld.move_sel(-1, 0)
        if keys[pygame.K_RIGHT]:
            self.overworld.move_sel(1, 0)
        if keys[pygame.K_UP]:
            self.overworld.move_sel(0, -1)
        if keys[pygame.K_DOWN]:
            self.overworld.move_sel(0, 1)
        if keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER]:
            self.start_level(self.overworld.sel_world, self.overworld.sel_stage)

        self.overworld.draw(self.screen)

    def update_playing(self):
        assert self.level and self.player
        keys = pygame.key.get_pressed()
        self.player.update(keys, self.level)

        # Camera follows
        self.cam_x = clamp(int(self.player.rect.centerx) - WIDTH // 2, 0, max(0, self.level.pixel_width - WIDTH))

        # Collect coins
        new_coins = []
        for c in self.level.coins:
            if self.player.rect.colliderect(c):
                self.player.coins += 1
                self.player.score += 100
            else:
                new_coins.append(c)
        self.level.coins = new_coins

        # Enemies
        for e in self.level.enemies:
            e.update(self.level)
            if not e.alive:
                continue
            if self.player.rect.colliderect(e.rect):
                # Check stomp vs hit
                falling = self.player.vy > 0 and self.player.rect.bottom - e.rect.top < 10
                if falling:
                    e.alive = False
                    self.player.vy = JUMP_VELOCITY * 0.7
                    self.player.score += 200
                else:
                    self.lose_life_and_respawn()
                    break

        # Death by falling off map
        if self.player.rect.top > HEIGHT + 100:
            self.lose_life_and_respawn()

        # Level complete?
        if self.player.rect.colliderect(self.level.goal_rect):
            self.player.score += 1000
            self.complete_level()

        # Draw
        self.level.draw(self.screen, self.cam_x)
        for e in self.level.enemies:
            e.draw(self.screen, self.cam_x)
        self.player.draw(self.screen, self.cam_x)
        self.draw_hud()

    def update_paused(self):
        # Draw playing scene dimmed, show pause overlay
        if self.level:
            self.level.draw(self.screen, self.cam_x)
            if self.player:
                for e in self.level.enemies:
                    e.draw(self.screen, self.cam_x)
                self.player.draw(self.screen, self.cam_x)
            self.draw_hud()
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        self.draw_text_center("Paused — [Esc] Resume", HEIGHT//2 - 12)

    def update_game_over(self):
        self.screen.fill((0, 0, 0))
        self.draw_text_center("Game Over", 120, big=True)
        self.draw_text_center("[Enter] Back to Overworld  •  [Esc] Quit", 170)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER]:
            # Reset lives and return
            self.state = WORLD_MAP
            # Reset player lives for new runs
            if self.player:
                self.player.lives = 3

# ------------------------------
# Main
# ------------------------------
def main():
    try:
        Game().run()
    except Exception as e:
        # Fail-safe: print to console and attempt graceful quit
        print("Fatal error:", e)
        try:
            pygame.quit()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
