import pygame
import serial
import time
import random
import threading
from collections import deque

# -----------------------
# CONFIG
# -----------------------
SERIAL_PORT = "/dev/ttyACM0"   # change to your port
BAUDRATE = 9600
SERIAL_TIMEOUT = 0.1          # seconds, non-blocking-ish read

WIDTH, HEIGHT = 900, 600
FPS = 30

# sensitivity thresholds (tweak to match your MPU6050 output)
AX_POS_THRESHOLD = 2000  # move right
AX_NEG_THRESHOLD = -2000 # move left
AY_POS_THRESHOLD = 2000  # move up
AY_NEG_THRESHOLD = -2000 # move down

SWITCH_DEBOUNCE = 0.5     # seconds between allowed character switches
SHAKE_THRESHOLD = 15000   # strong spike to register a shake switch

# gameplay
BALL_RADIUS = 25
BALL_SPEED = 5
COIN_RADIUS = 15
POWERUP_CHANCE = 0.18     # 18% coins are power-ups
POWERUP_DURATION = 6.0    # seconds, effect lasts this long
OBSTACLE_COUNT = 3
OBSTACLE_MIN_SPEED = 2
OBSTACLE_MAX_SPEED = 4
GAME_DURATION = 60        # seconds per round

# Sound files (optional)
SOUND_COIN = "coin.wav"
SOUND_POWER = "power.wav"
SOUND_HIT = "hit.wav"
MUSIC_BG = "background.mp3"

# -----------------------
# SERIAL READING THREAD
# -----------------------
# We'll run a thread reading serial lines into a queue so main loop never blocks
class SerialReader(threading.Thread):
    def __init__(self, port, baud, timeout=0.1):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.running = True
        self.queue = deque(maxlen=100)
        self.ser = None
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            time.sleep(1.5)  # allow Arduino to reset
            print(f"[SerialReader] Connected to {self.port} at {self.baud}")
        except Exception as e:
            print(f"[SerialReader] Warning: couldn't open serial port {self.port}: {e}")
            self.ser = None

    def run(self):
        if not self.ser:
            return
        while self.running:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if line:
                        self.queue.append(line)
                else:
                    time.sleep(0.005)
            except Exception as e:
                print("[SerialReader] Read error:", e)
                time.sleep(0.1)

    def stop(self):
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except:
                pass

    def get_latest(self):
        # return latest line or None
        return self.queue.pop() if self.queue else None

# -----------------------
# Game classes
# -----------------------
class Obstacle:
    def __init__(self, x, y, w, h, vx, vy):
        self.rect = pygame.Rect(x, y, w, h)
        self.vx = vx
        self.vy = vy

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy

        # bounce on screen edges
        if self.rect.left < 0 or self.rect.right > WIDTH:
            self.vx *= -1
            self.rect.x = max(0, min(self.rect.x, WIDTH - self.rect.width))
        if self.rect.top < 0 or self.rect.bottom > HEIGHT:
            self.vy *= -1
            self.rect.y = max(0, min(self.rect.y, HEIGHT - self.rect.height))

    def draw(self, surf):
        pygame.draw.rect(surf, (180, 60, 60), self.rect, border_radius=6)

# -----------------------
# Utility functions
# -----------------------
def safe_load_sound(path):
    try:
        s = pygame.mixer.Sound(path)
        return s
    except Exception as e:
        print(f"[Sound] Couldn't load {path}: {e}")
        return None

def safe_load_music(path):
    try:
        pygame.mixer.music.load(path)
        return True
    except Exception as e:
        print(f"[Music] Couldn't load {path}: {e}")
        return False

def parse_serial_line(line):
    """
    Accept lines like:
     "ax,ay,az"  or "ax,ay,az,btn"
    Returns dict: {'ax':int,'ay':int,'az':int,'btn':int or None}
    If parsing fails returns None
    """
    parts = [p.strip() for p in line.split(",") if p.strip() != ""]
    if len(parts) < 3:
        return None
    # only accept ints (allow leading -)
    try:
        ax = int(parts[0])
        ay = int(parts[1])
        az = int(parts[2])
    except:
        return None
    btn = None
    if len(parts) >= 4:
        try:
            btn = int(parts[3])
        except:
            btn = None
    return {"ax": ax, "ay": ay, "az": az, "btn": btn}

# MAIN GAME
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("GY-521 Ball Collecting Coins (improved)")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 36)
    big_font = pygame.font.Font(None, 72)

    # sounds
    pygame.mixer.init()
    coin_sound = safe_load_sound(SOUND_COIN)
    power_sound = safe_load_sound(SOUND_POWER)
    hit_sound = safe_load_sound(SOUND_HIT)
    music_loaded = safe_load_music(MUSIC_BG)
    if music_loaded:
        try:
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(-1)
        except:
            pass

    # serial thread
    ser_reader = SerialReader(SERIAL_PORT, BAUDRATE, timeout=SERIAL_TIMEOUT)
    ser_reader.start()

    # Characters: either colors or later replace with sprite surfaces
    characters = [
        {"name": "Green", "color": (60, 200, 80), "radius": BALL_RADIUS},
        {"name": "Blue", "color": (60, 140, 220), "radius": BALL_RADIUS},
        {"name": "Orange", "color": (255, 165, 60), "radius": BALL_RADIUS}
    ]
    current_char = 0
    last_switch = 0.0

    # Game state
    STATE_MENU = "MENU"
    STATE_PLAY = "PLAY"
    STATE_PAUSE = "PAUSE"
    STATE_GAMEOVER = "GAMEOVER"
    state = STATE_MENU

    # Gameplay variables (set when game starts)
    obstacles = []
    start_time = 0.0
    def init_game():
        nonlocal ball_x, ball_y, score, coin_x, coin_y, coin_special, power_active, power_ends_at
        nonlocal obstacles, start_time

        ball_x = WIDTH // 2
        ball_y = HEIGHT // 2
        score = 0
        coin_x = random.randint(COIN_RADIUS, WIDTH - COIN_RADIUS)
        coin_y = random.randint(COIN_RADIUS, HEIGHT - COIN_RADIUS)
        coin_special = random.random() < POWERUP_CHANCE
        power_active = False
        power_ends_at = 0.0
        obstacles = []
        # spawn obstacles at random positions with random velocities
        for _ in range(OBSTACLE_COUNT):
            w = random.randint(30, 70)
            h = random.randint(30, 50)
            x = random.randint(0, WIDTH - w)
            y = random.randint(0, HEIGHT - h)
            vx = random.choice([-1, 1]) * random.uniform(OBSTACLE_MIN_SPEED, OBSTACLE_MAX_SPEED)
            vy = random.choice([-1, 1]) * random.uniform(OBSTACLE_MIN_SPEED, OBSTACLE_MAX_SPEED)
            obstacles.append(Obstacle(x, y, w, h, vx, vy))
        start_time = time.time()

    init_game()

    # helper for drawing text centered
    def draw_centered_text(surface, text, font_obj, y, color=(255,255,255)):
        txt = font_obj.render(text, True, color)
        rect = txt.get_rect(center=(WIDTH//2, y))
        surface.blit(txt, rect)

    # movement state (from sensors)
    move_dx = 0
    move_dy = 0

    # game loop
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        now = time.time()

        # ----- EVENTS -----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if state == STATE_MENU:
                    if event.key == pygame.K_RETURN:
                        state = STATE_PLAY
                        init_game()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                elif state == STATE_PLAY:
                    if event.key == pygame.K_p:
                        state = STATE_PAUSE
                    elif event.key == pygame.K_ESCAPE:
                        state = STATE_MENU
                elif state == STATE_PAUSE:
                    if event.key == pygame.K_p:
                        state = STATE_PLAY
                    elif event.key == pygame.K_ESCAPE:
                        state = STATE_MENU
                elif state == STATE_GAMEOVER:
                    if event.key == pygame.K_RETURN:
                        state = STATE_PLAY
                        init_game()
                    elif event.key == pygame.K_ESCAPE:
                        state = STATE_MENU

        # ----- SERIAL INPUT PROCESSING -----
        latest_line = ser_reader.get_latest()
        if latest_line:
            parsed = parse_serial_line(latest_line)
            if parsed:
                ax = parsed["ax"]
                ay = parsed["ay"]
                az = parsed["az"]
                btn = parsed["btn"]
                # map sensor to movement directions
                # ax -> left/right, ay -> forward/back depending on orientation
                move_dx = 0
                move_dy = 0
                if ax > AX_POS_THRESHOLD:
                    move_dx += BALL_SPEED
                elif ax < AX_NEG_THRESHOLD:
                    move_dx -= BALL_SPEED
                if ay > AY_POS_THRESHOLD:
                    move_dy -= BALL_SPEED  # forward tilt moves up
                elif ay < AY_NEG_THRESHOLD:
                    move_dy += BALL_SPEED  # backward tilt moves down

                # Character switching: either via button or strong shake on z axis
                switched = False
                if btn is not None and btn == 1 and (now - last_switch) > SWITCH_DEBOUNCE:
                    current_char = (current_char + 1) % len(characters)
                    last_switch = now
                    switched = True
                    # optional feedback sound
                if not switched and abs(az) > SHAKE_THRESHOLD and (now - last_switch) > SWITCH_DEBOUNCE:
                    current_char = (current_char + 1) % len(characters)
                    last_switch = now

        # Also allow keyboard arrow fallback control for debugging
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            move_dx -= BALL_SPEED
        if keys[pygame.K_RIGHT]:
            move_dx += BALL_SPEED
        if keys[pygame.K_UP]:
            move_dy -= BALL_SPEED
        if keys[pygame.K_DOWN]:
            move_dy += BALL_SPEED

        # ----- UPDATE GAME STATE -----
        if state == STATE_PLAY:
            # update ball position
            ball_x += int(move_dx)
            ball_y += int(move_dy)

            # boundary checks
            ball_x = max(characters[current_char]["radius"], min(WIDTH - characters[current_char]["radius"], ball_x))
            ball_y = max(characters[current_char]["radius"], min(HEIGHT - characters[current_char]["radius"], ball_y))

            # check coin collection
            dist = ((ball_x - coin_x)**2 + (ball_y - coin_y)**2)**0.5
            if dist < characters[current_char]["radius"] + COIN_RADIUS:
                if coin_special:
                    # power-up effect: give points and temporary speed boost / bigger radius
                    score += 5
                    power_active = True
                    power_ends_at = now + POWERUP_DURATION
                    # increase radius while power active
                    characters[current_char]["radius"] = BALL_RADIUS + 8
                    if power_sound:
                        power_sound.play()
                else:
                    score += 1
                    if coin_sound:
                        coin_sound.play()
                # spawn new coin
                coin_x = random.randint(COIN_RADIUS, WIDTH - COIN_RADIUS)
                coin_y = random.randint(COIN_RADIUS, HEIGHT - COIN_RADIUS)
                coin_special = random.random() < POWERUP_CHANCE

            # power-up timeout
            if power_active and now >= power_ends_at:
                power_active = False
                characters[current_char]["radius"] = BALL_RADIUS

            # update obstacles
            for obs in obstacles:
                obs.update()
                # collision detection circle vs rect
                circle_dist_x = abs(ball_x - obs.rect.centerx)
                circle_dist_y = abs(ball_y - obs.rect.centery)
                if circle_dist_x > (obs.rect.width/2 + characters[current_char]["radius"]):
                    continue
                if circle_dist_y > (obs.rect.height/2 + characters[current_char]["radius"]):
                    continue
                # approximate more precisely
                # (closest point)
                closest_x = max(obs.rect.left, min(ball_x, obs.rect.right))
                closest_y = max(obs.rect.top, min(ball_y, obs.rect.bottom))
                d = ((ball_x - closest_x)**2 + (ball_y - closest_y)**2)**0.5
                if d < characters[current_char]["radius"]:
                    # collision! game over
                    if hit_sound:
                        hit_sound.play()
                    state = STATE_GAMEOVER
                    game_over_time = now

            # game duration timer
            elapsed = now - start_time
            if elapsed >= GAME_DURATION:
                state = STATE_GAMEOVER
                game_over_time = now

        # ----- DRAW -----
        screen.fill((30, 30, 30))  # background

        if state == STATE_MENU:
            draw_centered_text(screen, "GY-521 Ball Collect Coins", big_font, HEIGHT//2 - 80)
            draw_centered_text(screen, "Press ENTER to start  •  ESC to quit", font, HEIGHT//2)
            draw_centered_text(screen, "Use MPU6050 tilt to move, button or shake to switch character", font, HEIGHT//2 + 40)
        elif state == STATE_PAUSE:
            # draw gameplay behind dimmed overlay
            # (we'll still draw last known positions so player sees pause state)
            # draw coin
            if coin_special:
                pygame.draw.circle(screen, (255,0,255), (coin_x, coin_y), COIN_RADIUS)
            else:
                pygame.draw.circle(screen, (240, 200, 40), (coin_x, coin_y), COIN_RADIUS)
            # draw obstacles
            for obs in obstacles:
                obs.draw(screen)
            # draw ball
            pygame.draw.circle(screen, characters[current_char]["color"], (ball_x, ball_y), characters[current_char]["radius"])
            # dim overlay
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,150))
            screen.blit(overlay, (0,0))
            draw_centered_text(screen, "PAUSED", big_font, HEIGHT//2 - 20)
            draw_centered_text(screen, "Press P to resume • ESC to exit to menu", font, HEIGHT//2 + 40)
        elif state == STATE_PLAY:
            # coin
            if coin_special:
                pygame.draw.circle(screen, (200, 40, 200), (coin_x, coin_y), COIN_RADIUS)
                # small sparkle (visual)
                pygame.draw.circle(screen, (255, 220, 255), (coin_x, coin_y), COIN_RADIUS//2, 1)
            else:
                pygame.draw.circle(screen, (240, 200, 40), (coin_x, coin_y), COIN_RADIUS)

            # obstacles
            for obs in obstacles:
                obs.draw(screen)

            # ball (character)
            pygame.draw.circle(screen, characters[current_char]["color"], (ball_x, ball_y), characters[current_char]["radius"])

            # HUD: score and timer
            score_text = font.render(f"Score: {score}", True, (240,240,240))
            screen.blit(score_text, (16, 12))
            elapsed = now - start_time
            time_text = font.render(f"Time: {max(0, int(GAME_DURATION - elapsed))}s", True, (240,240,240))
            screen.blit(time_text, (WIDTH - 160, 12))

            # small indicator for current character
            char_text = font.render(f"Char: {characters[current_char]['name']}", True, (240,240,240))
            screen.blit(char_text, (WIDTH//2 - 80, 12))

            # power-up indicator
            if power_active:
                ptxt = font.render(f"POWER! {int(power_ends_at - now)}s", True, (255,180,60))
                screen.blit(ptxt, (WIDTH//2 - 80, 46))

        elif state == STATE_GAMEOVER:
            # show final positions lightly
            pygame.draw.circle(screen, characters[current_char]["color"], (ball_x, ball_y), characters[current_char]["radius"])
            for obs in obstacles:
                obs.draw(screen)
            draw_centered_text(screen, "GAME OVER", big_font, HEIGHT//2 - 80)
            draw_centered_text(screen, f"Score: {score}", font, HEIGHT//2)
            draw_centered_text(screen, "Press ENTER to play again • ESC to return to menu", font, HEIGHT//2 + 40)

        pygame.display.flip()

    # cleanup
    ser_reader.stop()
    pygame.mixer.music.stop()
    pygame.quit()

if __name__ == "__main__":
    main()
