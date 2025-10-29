import pygame
from pygame.locals import *

pygame.init()

# Screen setup
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 400
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('PvZ Clone')

# Colors
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# Simple classes for Plant and Zombie
class Plant(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40, 40))
        self.image.fill(GREEN)
        self.rect = self.image.get_rect(topleft=(x, y))

class Zombie(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40, 40))
        self.image.fill(RED)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.speed = -1  # Move left

    def update(self):
        self.rect.x += self.speed

# Groups
all_sprites = pygame.sprite.Group()
plants = pygame.sprite.Group()
zombies = pygame.sprite.Group()

# Main menu function
def main_menu():
    font = pygame.font.SysFont(None, 48)
    text = font.render('Plants vs Zombies - Click to Start', True, WHITE)
    screen.blit(text, (50, 150))
    pygame.display.flip()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
            if event.type == MOUSEBUTTONDOWN:
                waiting = False

# Game loop for one level
def game_level():
    clock = pygame.time.Clock()
    running = True

    # Add a zombie
    zombie = Zombie(SCREEN_WIDTH - 50, 180)
    all_sprites.add(zombie)
    zombies.add(zombie)

    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            if event.type == MOUSEBUTTONDOWN:
                # Place plant on click
                x, y = event.pos
                plant = Plant(x, y - 20)
                all_sprites.add(plant)
                plants.add(plant)

        all_sprites.update()

        # Simple collision (zombie eats plant)
        hits = pygame.sprite.groupcollide(zombies, plants, False, True)
        if hits:
            pass  # Handle eating

        screen.fill((0, 0, 0))  # Black background
        all_sprites.draw(screen)
        pygame.display.flip()
        clock.tick(60)

# Run
main_menu()
game_level()
pygame.quit()
