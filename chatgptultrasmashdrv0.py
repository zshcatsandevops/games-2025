"""Ultra Smash Bros - Pygame homage to Super Smash Bros. 64.

This module implements a lightweight brawler inspired by the N64 classic.
It recreates the overall flow (title, character select, stage select, battle,
results) while using simple shapes and effects instead of copyrighted assets.

Run with `python program.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame

# Screen constants match the requested N64-like setup
WIDTH, HEIGHT = 600, 400
FPS = 60


class GameState(Enum):
    TITLE = auto()
    CHARACTER_SELECT = auto()
    STAGE_SELECT = auto()
    BATTLE = auto()
    RESULTS = auto()


# Character roster inspired by Smash 64 (all renamed to Ultra Smash Bros branding)
ROSTER = [
    "Ultra Mario",
    "Ultra Donkey Kong",
    "Ultra Link",
    "Ultra Samus",
    "Ultra Fox",
    "Ultra Pikachu",
    "Ultra Yoshi",
    "Ultra Kirby",
    "Ultra Jigglypuff",
    "Ultra Captain Falcon",
    "Ultra Luigi",
    "Ultra Ness",
]


STAGES = [
    "Ultra Peach Castle",
    "Ultra Congo Jungle",
    "Ultra Hyrule Castle",
    "Ultra Planet Zebes",
    "Ultra Sector Z",
    "Ultra Saffron City",
    "Ultra Dream Land",
    "Ultra Yoshi's Island",
    "Ultra Mushroom Kingdom",
]


@dataclass
class Fighter:
    name: str
    color: Tuple[int, int, int]
    stock: int = 3
    damage: float = 0.0
    pos: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(WIDTH / 3, HEIGHT / 2))
    velocity: pygame.Vector2 = field(default_factory=pygame.Vector2)
    facing: int = 1

    def reset(self, spawn: Tuple[float, float]) -> None:
        self.stock = 3
        self.damage = 0.0
        self.pos.xy = spawn
        self.velocity.xy = (0, 0)
        self.facing = 1

    def apply_damage(self, amount: float, knockback: pygame.Vector2) -> None:
        self.damage += amount
        self.velocity += knockback * (1 + self.damage / 100)

    def update(self, dt: float, left: bool, right: bool, jump: bool, attack: bool, stage_rect: pygame.Rect) -> Optional[Dict[str, float]]:
        # movement
        if left:
            self.velocity.x -= 600 * dt
            self.facing = -1
        if right:
            self.velocity.x += 600 * dt
            self.facing = 1

        # friction and gravity
        self.velocity.x *= 0.85
        self.velocity.y += 900 * dt

        # jump
        if jump and abs(self.velocity.y) < 1 and self.pos.y >= stage_rect.top:
            self.velocity.y = -350

        # integrate
        self.pos += self.velocity * dt

        # collisions with stage
        if self.pos.y >= stage_rect.top:
            self.pos.y = stage_rect.top
            self.velocity.y = 0

        # knockback effect when attacking
        damage_event: Optional[Dict[str, float]] = None
        if attack:
            damage_event = {"damage": 12.0, "knockback_x": 250 * self.facing, "knockback_y": -200}
        return damage_event

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.pos.x) - 20, int(self.pos.y) - 40, 40, 40)


@dataclass
class BattleResult:
    winner: str
    loser: str
    stage: str


class UltraSmashBros:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Ultra Smash Bros")
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.SysFont("futura", 36)
        self.font_medium = pygame.font.SysFont("futura", 24)
        self.font_small = pygame.font.SysFont("futura", 18)
        self.state = GameState.TITLE
        self.players = [
            Fighter(ROSTER[0], (220, 50, 50)),
            Fighter(ROSTER[5], (255, 220, 0)),
        ]
        self.player_index = 0
        self.selected_characters: List[str] = [self.players[0].name, self.players[1].name]
        self.stage_index = 0
        self.selected_stage = STAGES[0]
        self.stage_rect = pygame.Rect(80, HEIGHT - 120, WIDTH - 160, 20)
        self.result: Optional[BattleResult] = None
        self.battle_timer = 0.0

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event.key)

            self.update(dt)
            self.render()

        pygame.quit()

    def handle_keydown(self, key: int) -> None:
        if self.state == GameState.TITLE and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.state = GameState.CHARACTER_SELECT
        elif self.state == GameState.CHARACTER_SELECT:
            self.handle_character_select_input(key)
        elif self.state == GameState.STAGE_SELECT:
            self.handle_stage_select_input(key)
        elif self.state == GameState.RESULTS and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.state = GameState.TITLE

    def handle_character_select_input(self, key: int) -> None:
        if key == pygame.K_RIGHT:
            self.player_index = (self.player_index + 1) % len(self.players)
        elif key == pygame.K_LEFT:
            self.player_index = (self.player_index - 1) % len(self.players)
        elif key == pygame.K_UP:
            roster_index = (ROSTER.index(self.players[self.player_index].name) - 1) % len(ROSTER)
            self.players[self.player_index].name = ROSTER[roster_index]
        elif key == pygame.K_DOWN:
            roster_index = (ROSTER.index(self.players[self.player_index].name) + 1) % len(ROSTER)
            self.players[self.player_index].name = ROSTER[roster_index]
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.selected_characters = [p.name for p in self.players]
            self.state = GameState.STAGE_SELECT

    def handle_stage_select_input(self, key: int) -> None:
        if key == pygame.K_RIGHT:
            self.stage_index = (self.stage_index + 1) % len(STAGES)
        elif key == pygame.K_LEFT:
            self.stage_index = (self.stage_index - 1) % len(STAGES)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.selected_stage = STAGES[self.stage_index]
            self.start_battle()

    def start_battle(self) -> None:
        spawns = [(WIDTH / 2 - 120, self.stage_rect.top), (WIDTH / 2 + 120, self.stage_rect.top)]
        for fighter, spawn in zip(self.players, spawns):
            fighter.reset(spawn)
        self.battle_timer = 0.0
        self.state = GameState.BATTLE

    def update(self, dt: float) -> None:
        if self.state == GameState.BATTLE:
            self.update_battle(dt)

    def update_battle(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        controls = [
            (keys[pygame.K_a], keys[pygame.K_d], keys[pygame.K_w], keys[pygame.K_s]),
            (keys[pygame.K_LEFT], keys[pygame.K_RIGHT], keys[pygame.K_UP], keys[pygame.K_DOWN]),
        ]

        for fighter, control in zip(self.players, controls):
            left, right, jump, attack = control
            damage_event = fighter.update(dt, left, right, jump, attack, self.stage_rect)
            opponent = self.players[1] if fighter is self.players[0] else self.players[0]
            if damage_event and fighter.rect().colliderect(opponent.rect()):
                knockback = pygame.Vector2(damage_event["knockback_x"], damage_event["knockback_y"])
                opponent.apply_damage(damage_event["damage"], knockback)

        # Respawn logic when fighters fall off stage
        for fighter in self.players:
            if fighter.pos.y > HEIGHT + 60 or fighter.pos.x < -60 or fighter.pos.x > WIDTH + 60:
                fighter.stock -= 1
                if fighter.stock <= 0:
                    winner = self.players[0] if fighter is self.players[1] else self.players[1]
                    self.result = BattleResult(winner.name, fighter.name, self.selected_stage)
                    self.state = GameState.RESULTS
                    return
                spawn = (WIDTH / 2 - 120, self.stage_rect.top) if fighter is self.players[0] else (WIDTH / 2 + 120, self.stage_rect.top)
                fighter.reset(spawn)

        self.battle_timer += dt

    def render(self) -> None:
        self.screen.fill((15, 20, 45))
        if self.state == GameState.TITLE:
            self.render_title()
        elif self.state == GameState.CHARACTER_SELECT:
            self.render_character_select()
        elif self.state == GameState.STAGE_SELECT:
            self.render_stage_select()
        elif self.state == GameState.BATTLE:
            self.render_battle()
        elif self.state == GameState.RESULTS:
            self.render_results()
        pygame.display.flip()

    def render_title(self) -> None:
        title = self.font_large.render("Ultra Smash Bros 64", True, (255, 255, 255))
        subtitle = self.font_medium.render("Press Start to Enter the Ultra Arena", True, (200, 200, 255))
        self.screen.blit(title, title.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 40)))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 20)))

    def render_character_select(self) -> None:
        header = self.font_medium.render("Select Your Ultra Fighters", True, (255, 255, 255))
        self.screen.blit(header, (20, 20))
        for idx, fighter in enumerate(self.players):
            label = f"Player {idx + 1}: {fighter.name}"
            color = (255, 230, 120) if idx == self.player_index else (180, 180, 180)
            text = self.font_small.render(label, True, color)
            self.screen.blit(text, (40, 70 + idx * 30))
        roster_hint = self.font_small.render("Up/Down: Change Fighter  Left/Right: Switch Player  Start: Confirm", True, (200, 200, 200))
        self.screen.blit(roster_hint, (40, HEIGHT - 40))

    def render_stage_select(self) -> None:
        header = self.font_medium.render("Choose an Ultra Stage", True, (255, 255, 255))
        self.screen.blit(header, (20, 20))
        stage_text = self.font_large.render(STAGES[self.stage_index], True, (255, 200, 200))
        self.screen.blit(stage_text, stage_text.get_rect(center=(WIDTH / 2, HEIGHT / 2)))
        hint = self.font_small.render("Left/Right: Cycle Stages  Start: Battle!", True, (200, 200, 200))
        self.screen.blit(hint, (WIDTH / 2 - hint.get_width() / 2, HEIGHT - 50))

    def render_battle(self) -> None:
        # draw stage
        pygame.draw.rect(self.screen, (60, 60, 60), self.stage_rect)
        pygame.draw.rect(self.screen, (120, 120, 120), self.stage_rect.inflate(40, 0), 4)

        # draw fighters
        for fighter in self.players:
            pygame.draw.rect(self.screen, fighter.color, fighter.rect())

        # UI overlay
        for idx, fighter in enumerate(self.players):
            text = self.font_small.render(
                f"{fighter.name}: Stock {fighter.stock} | Damage {int(fighter.damage)}%",
                True,
                (255, 255, 255),
            )
            self.screen.blit(text, (20, 20 + idx * 20))

        timer_text = self.font_small.render(f"Ultra Time: {self.battle_timer:05.2f}", True, (200, 200, 255))
        self.screen.blit(timer_text, (WIDTH - timer_text.get_width() - 20, 20))

    def render_results(self) -> None:
        if not self.result:
            return
        winner_text = self.font_large.render(f"{self.result.winner} Wins!", True, (255, 255, 255))
        loser_text = self.font_medium.render(f"{self.result.loser} is Out!", True, (200, 120, 120))
        stage_text = self.font_small.render(f"Stage: {self.result.stage}", True, (200, 200, 200))
        prompt = self.font_small.render("Press Start to Return", True, (180, 180, 240))
        self.screen.blit(winner_text, winner_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 40)))
        self.screen.blit(loser_text, loser_text.get_rect(center=(WIDTH / 2, HEIGHT / 2)))
        self.screen.blit(stage_text, stage_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 40)))
        self.screen.blit(prompt, prompt.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 90)))


if __name__ == "__main__":
    UltraSmashBros().run()
