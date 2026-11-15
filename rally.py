"""Hardware-independent Matrix Rally rules."""

import math

PADDLE_WIDTH = 12
TOP_Y = 3
BOTTOM_Y = 59
DIFFICULTIES = ("EASY", "MEDIUM", "HARD")
SETTINGS = ((26.0, 22.0, 8.0), (36.0, 32.0, 4.0), (48.0, 48.0, 1.5))


class Rally:
    def __init__(self):
        self.difficulty = 1
        self.events = []
        self.show_menu()

    def show_menu(self):
        self.state = "menu"
        self.clock = 0.0
        self.select_at = 0.0
        self.player_score = 0
        self.computer_score = 0
        self.player_x = 26.0
        self.computer_x = 26.0
        self.ball_x = 32.0
        self.ball_y = 32.0
        self.events.clear()

    def start(self):
        self.show_menu()
        self.ball_speed, self.computer_speed, self.computer_error = SETTINGS[
            self.difficulty
        ]
        self.state = "playing"
        self._serve(1)
        self.events.append("wave")

    def pause(self):
        if self.state == "playing":
            self.state = "paused"
            return True
        if self.state == "paused":
            self.state = "playing"
            return True
        return False

    def _serve(self, direction):
        self.ball_x = 32.0
        self.ball_y = 32.0
        self.ball_speed = SETTINGS[self.difficulty][0]
        side = 1 if (self.player_score + self.computer_score) % 2 == 0 else -1
        self.vx = self.ball_speed * 0.35 * side
        self.vy = self.ball_speed * math.sqrt(1 - 0.35 ** 2) * direction
        self.serve_at = self.clock + 0.8

    def _point(self, player):
        if player:
            self.player_score += 1
        else:
            self.computer_score += 1
        if max(self.player_score, self.computer_score) >= 5:
            self.state = "over"
            self.events.append("clear" if player else "over")
        else:
            self.events.append("clear" if player else "damage")
            self._serve(-1 if player else 1)

    def _bounce(self, paddle_x, direction):
        offset = (self.ball_x - (paddle_x + PADDLE_WIDTH / 2)) / (
            PADDLE_WIDTH / 2 + 1
        )
        offset = max(-1.0, min(1.0, offset))
        if abs(offset) < 0.15:
            offset = 0.15 if self.vx >= 0 else -0.15
        self.ball_speed = min(85.0, self.ball_speed + 2.0)
        angle = offset * math.pi / 3
        self.vx = self.ball_speed * math.sin(angle)
        self.vy = self.ball_speed * math.cos(angle) * direction
        self.events.append("hit")

    def update(self, dt, velocity):
        self.events.clear()
        if self.state not in ("menu", "playing"):
            return
        if dt < 0:
            raise ValueError("Frame duration cannot be negative")
        dt = min(dt, 0.05)
        self.clock += dt
        if self.state == "menu":
            if velocity == 0:
                self.select_at = self.clock
            elif self.clock >= self.select_at:
                selection = max(0, min(2, self.difficulty + (1 if velocity > 0 else -1)))
                if selection != self.difficulty:
                    self.difficulty = selection
                    self.events.append("step")
                self.select_at = self.clock + 0.35
            return
        self.player_x = max(0.0, min(52.0, self.player_x + velocity * dt))
        target = self.ball_x + math.sin(self.clock * 2) * self.computer_error
        delta = target - (self.computer_x + PADDLE_WIDTH / 2)
        movement = max(-self.computer_speed * dt, min(self.computer_speed * dt, delta))
        self.computer_x = max(0.0, min(52.0, self.computer_x + movement))
        if self.clock < self.serve_at:
            return
        # Substeps keep even the fastest ball from skipping a paddle face.
        steps = max(1, math.ceil(dt / 0.01))
        for _ in range(steps):
            old_x, old_y = self.ball_x, self.ball_y
            self.ball_x += self.vx * dt / steps
            self.ball_y += self.vy * dt / steps
            if self.ball_x < 1:
                self.ball_x = 2 - self.ball_x
                self.vx = abs(self.vx)
                self.events.append("step")
            elif self.ball_x > 62:
                self.ball_x = 124 - self.ball_x
                self.vx = -abs(self.vx)
                self.events.append("step")
            face = BOTTOM_Y - 1 if self.vy > 0 else TOP_Y + 2
            crossed = (
                old_y <= face <= self.ball_y if self.vy > 0
                else self.ball_y <= face <= old_y
            )
            if crossed and self.ball_y != old_y:
                hit_x = old_x + (self.ball_x - old_x) * (
                    (face - old_y) / (self.ball_y - old_y)
                )
                paddle = self.player_x if self.vy > 0 else self.computer_x
                if paddle - 1 <= hit_x <= paddle + PADDLE_WIDTH:
                    self.ball_x = hit_x
                    self.ball_y = float(face)
                    self._bounce(paddle, -1 if self.vy > 0 else 1)
            if self.ball_y < -1 or self.ball_y > 64:
                self._point(self.ball_y < -1)
                return
