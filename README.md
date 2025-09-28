# Eclipsera

Eclipsera is a motion-controlled 2D arcade game where you guide a glowing orb to collect coins using an MPU6050 motion sensor (via Arduino). Tilt the sensor to drift across the screen, collect points, and enjoy audio-visual feedback. This project combines hardware and software, turning physical motion into interactive gameplay with Pygame.

## Features

- **Motion-based control:** Move the ball by tilting the MPU6050 sensor (Arduino → Serial → Pygame).
- **Coin collection:** Randomly spawned coins increase score upon collection.
- **Boundary checks:** Ball stays within screen limits.
- **Dynamic visuals:** Colorful sprites for ball and coins.
- **Audio feedback:** Sound effects for collecting coins and scoring milestones.
- **Character switching:** Switch between playable characters (skins) using the MPU6050’s switch input.
- **Special features:**
    - Smooth real-time movement
    - Randomized coin placement
    - Extendable scoring/level system

## Requirements

- Python 3.8+
- Pygame
- Arduino with MPU6050 (GY-521) module
- PySerial

Install dependencies:
```bash
pip install pygame pyserial
```

## Hardware Setup

1. Connect MPU6050 (GY-521) to Arduino (I²C: SCL → A5, SDA → A4, VCC → 5V, GND → GND).
2. Upload Arduino sketch that reads accelerometer values and sends them via Serial in format:
        ```
        ax,ay,az
        ```
3. Connect Arduino to PC (check your port, e.g. `/dev/ttyACM0` or `COM3`).

## Run the Game

```bash
python axis_drift.py
```
Tilt the MPU6050 sensor to control the glowing orb, collect coins, and rack up points!

## How to Win or Lose

- **Win:** Reach a target score (e.g., 20 coins) to trigger a victory screen.
- **Lose:** Future versions may include hazards or a countdown timer that ends the game if coins aren’t collected in time.




## Future Improvements

- Multiple difficulty levels
- Power-ups (speed boost, shields, etc.)
- Enemies/obstacles to avoid
- Online leaderboard
- Mobile adaptation (gyro controls)

## Credits

- **Developer:** Isaac
- **Libraries:** Pygame, PySerial
- **Hardware:** Arduino + MPU6050 (GY-521)