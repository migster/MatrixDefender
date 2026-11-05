"""Hardware-independent rules and controls for Matrix Defender."""

import math
import random

WIDTH = 64
HEIGHT = 64
PLAYER_Y = 58
FIRE_INTERVAL = 0.24
MAX_PLAYER_SHOTS = 4
MAX_ENEMY_SHOTS = 5
ALIEN_WIDTH = 5
ALIEN_HEIGHT = 4


class Button:
    """Debounce an active-low input using stable transitions."""

    def __init__(self, value=True):
        self.raw = value
        self.stable = value
        self.changed_at = 0.0
        self.pressed = False
        self.fell = False

    def update(self, value, now):
        self.fell = False
        if value != self.raw:
            self.raw = value
            self.changed_at = now
        if value != self.stable and now - self.changed_at >= 0.03:
            self.stable = value
            self.fell = not value
        self.pressed = not self.stable


class Steering:
    def __init__(self, horizontal=0, vertical=1, direction=1):
        if horizontal not in (0, 1, 2) or vertical not in (0, 1, 2):
            raise ValueError("Accelerometer axes must be 0, 1, or 2")
        if horizontal == vertical or direction not in (-1, 1):
            raise ValueError("Use distinct axes and a direction of -1 or 1")
        self.horizontal = horizontal
        self.vertical = vertical
        self.direction = direction
        self.neutral = 0.0
        self.filtered = 0.0

    def calibrate(self, acceleration):
        h = acceleration[self.horizontal]
        v = acceleration[self.vertical]
        if math.sqrt(h * h + v * v) < 3.0:
            raise ValueError("Hold panel upright; check configured accelerometer axes")
        self.neutral = math.atan2(h, v)
        self.filtered = 0.0

    def velocity(self, acceleration, dt):
        angle = math.atan2(
            acceleration[self.horizontal], acceleration[self.vertical]
        )
        delta = (angle - self.neutral + math.pi) % (2 * math.pi) - math.pi
        alpha = min(1.0, dt / 0.08)
        self.filtered += alpha * (delta - self.filtered)
        magnitude = abs(self.filtered)
        if magnitude <= 0.06:
            return 0.0
        speed = min(1.0, (magnitude - 0.06) / 0.39) * 65.0
        return speed * (1 if self.filtered > 0 else -1) * self.direction


def score_bar(score, width=52):
    """Fill toward 1000 points, then successive doubling milestones."""
    goal = 1000
    while score > goal:
        goal *= 2
    return min(width, score * width // goal), goal


class Game:
    def __init__(self, rng=None):
        self.rng = rng if rng is not None else random
        self.best = 0
        self.state = "ready"
        self.score = 0
        self.lives = 3
        self.wave = 0
        self.player_x = 29.0
        self.clock = 0.0
        self.invulnerable_until = 0.0
        self.aliens = []
        self.player_shots = []
        self.enemy_shots = []
        self.events = []

    def start(self):
        self.score = 0
        self.lives = 3
        self.wave = 0
        self.player_x = 29.0
        self.clock = 0.0
        self.invulnerable_until = 0.0
        self.player_shots.clear()
        self.enemy_shots.clear()
        self.events.clear()
        self._new_wave()

    def _new_wave(self):
        self.wave += 1
        self.aliens = [
            [7 + column * 9, 8 + row * 7, row]
            for row in range(3)
            for column in range(6)
        ]
        self.direction = 1
        self.move_at = self.clock + 0.5
        self.enemy_fire_at = self.clock + 1.2
        self.fire_at = self.clock
        self.state = "playing"
        self.events.append("wave")

    def pause(self):
        if self.state in ("playing", "wave"):
            self.resume_state = self.state
            self.state = "paused"
            return True
        if self.state == "paused":
            self.state = self.resume_state
            return True
        return False

    def _finish(self):
        self.state = "over"
        self.best = max(self.best, self.score)
        self.events.append("over")

    def _damage(self):
        if self.clock < self.invulnerable_until:
            return
        self.lives -= 1
        self.enemy_shots.clear()
        self.invulnerable_until = self.clock + 1.5
        self.events.append("damage")
        if self.lives == 0:
            self._finish()

    def update(self, dt, velocity, firing):
        self.events.clear()
        if self.state not in ("playing", "wave"):
            return
        if dt < 0:
            raise ValueError("Frame duration cannot be negative")
        # Cap stalls so projectiles cannot tunnel through sprites.
        dt = min(dt, 0.05)
        self.clock += dt
        if self.state == "wave":
            if self.clock >= self.wave_at:
                self._new_wave()
            return
        self.player_x = max(0.0, min(57.0, self.player_x + velocity * dt))
        if firing and self.clock >= self.fire_at:
            if len(self.player_shots) < MAX_PLAYER_SHOTS:
                self.player_shots.append([self.player_x + 3, PLAYER_Y - 1.0])
                self.events.append("fire")
            self.fire_at = self.clock + FIRE_INTERVAL

        for shot in self.player_shots[:]:
            old_y = shot[1]
            shot[1] -= 75 * dt
            for alien in self.aliens:
                if (
                    alien[0] <= shot[0] < alien[0] + ALIEN_WIDTH
                    and shot[1] <= alien[1] + ALIEN_HEIGHT - 1
                    and old_y >= alien[1]
                ):
                    self.aliens.remove(alien)
                    self.player_shots.remove(shot)
                    self.score += (3 - alien[2]) * 10
                    self.best = max(self.best, self.score)
                    self.events.append("hit")
                    break
            else:
                if shot[1] < 2:
                    self.player_shots.remove(shot)

        if not self.aliens:
            self.player_shots.clear()
            self.enemy_shots.clear()
            self.state = "wave"
            self.wave_at = self.clock + 1.0
            self.events.append("clear")
            return

        if self.clock >= self.move_at:
            hit_edge = any(
                alien[0] + self.direction * 2 < 0
                or alien[0] + self.direction * 2 + ALIEN_WIDTH > WIDTH
                for alien in self.aliens
            )
            if hit_edge:
                self.direction = -self.direction
                for alien in self.aliens:
                    alien[1] += 3
            else:
                for alien in self.aliens:
                    alien[0] += self.direction * 2
            interval = max(
                0.08, (0.5 - min(self.wave - 1, 12) * 0.025)
                * (0.35 + 0.65 * len(self.aliens) / 18)
            )
            self.move_at = self.clock + interval
            self.events.append("step")
            if any(a[1] + ALIEN_HEIGHT >= PLAYER_Y for a in self.aliens):
                self.lives = 0
                self._finish()
                return

        if self.clock >= self.enemy_fire_at:
            if len(self.enemy_shots) < MAX_ENEMY_SHOTS:
                # Only the lowest surviving alien in each column can fire.
                front = {}
                for alien in self.aliens:
                    if alien[0] not in front or alien[1] > front[alien[0]][1]:
                        front[alien[0]] = alien
                alien = self.rng.choice(list(front.values()))
                self.enemy_shots.append(
                    [alien[0] + 2, float(alien[1] + ALIEN_HEIGHT)]
                )
            self.enemy_fire_at = self.clock + self.rng.uniform(
                max(0.3, 1.0 - self.wave * 0.04),
                max(0.5, 1.7 - self.wave * 0.06),
            )
        for shot in self.enemy_shots[:]:
            old_y = shot[1]
            shot[1] += min(58, 25 + self.wave * 2) * dt
            if (
                self.player_x <= shot[0] < self.player_x + 7
                and shot[1] >= PLAYER_Y
                and old_y <= PLAYER_Y + 3
                and self.clock >= self.invulnerable_until
            ):
                self._damage()
                break
            if shot[1] >= HEIGHT:
                self.enemy_shots.remove(shot)
