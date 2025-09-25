import pygame
import serial
import time
import random
# Connect to Arduino
ser = serial.Serial("/dev/ttyACM0", 9600)
time.sleep(2)  # wait for Arduino connection
# Game setup
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("GY-521 Ball Collecting Coins Game")
# Colors
BLACK = (30, 30, 30)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
# Ball setup
ball_radius = 25
ball_x = WIDTH // 2
ball_y = HEIGHT // 2
speed = 5
# Coin setup
coin_radius = 15
coin_x = random.randint(coin_radius, WIDTH - coin_radius)
coin_y = random.randint(coin_radius, HEIGHT - coin_radius)
score = 0
font = pygame.font.Font(None, 36)
clock = pygame.time.Clock()
running = True
while running:
    screen.fill(BLACK)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    # Read sensor data from Arduino (skip incomplete lines)
    if ser.in_waiting > 0:
        line = ser.readline().decode(errors='ignore').strip()
        parts = line.split(",")
        # Only process full data lines
        if len(parts) == 3 and all(p.strip().lstrip('-').isdigit() for p in parts):
            ax, ay, az = map(int, parts)
            # Adjust sensitivity if needed
            if ax > 2000:
                ball_x += speed
            elif ax < -2000:
                ball_x -= speed
            if ay > 2000:
                ball_y -= speed  # forward tilt moves up
            elif ay < -2000:
                ball_y += speed  # backward tilt moves down
    # Keep ball INSIDE window (boundary check)
    if ball_x - ball_radius < 0:
        ball_x = ball_radius
    elif ball_x + ball_radius > WIDTH:
        ball_x = WIDTH - ball_radius
    if ball_y - ball_radius < 0:
        ball_y = ball_radius
    elif ball_y + ball_radius > HEIGHT:
        ball_y = HEIGHT - ball_radius
    # Check for coin collection
    distance = ((ball_x - coin_x)**2 + (ball_y - coin_y)**2) ** 0.5
    if distance < ball_radius + coin_radius:
        score += 1
        coin_x = random.randint(coin_radius, WIDTH - coin_radius)
        coin_y = random.randint(coin_radius, HEIGHT - coin_radius)
    # Draw ball
    pygame.draw.circle(screen, GREEN, (ball_x, ball_y), ball_radius)
    # Draw coin
    pygame.draw.circle(screen, YELLOW, (coin_x, coin_y), coin_radius)
    # Draw score
    score_text = font.render(f"Score: {score}", True, WHITE)
    screen.blit(score_text, (20, 20))
    pygame.display.flip()
    clock.tick(30)
pygame.quit()