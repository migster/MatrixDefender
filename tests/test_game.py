import math
import random
import unittest

from game import Button, Game, Steering, score_bar
from graphics import render


class Bitmap:
    def __init__(self):
        self.pixels = {}

    def fill(self, value):
        self.pixels.clear()

    def __setitem__(self, coordinates, color):
        x, y = coordinates
        assert 0 <= x < 64 and 0 <= y < 64
        assert 0 <= color < 8
        self.pixels[coordinates] = color


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(random.Random(42))
        self.game.start()

    def test_start_and_restart(self):
        self.assertEqual(len(self.game.aliens), 18)
        self.game.score = 123
        self.game._finish()
        self.game.start()
        self.assertEqual((self.game.score, self.game.lives, self.game.wave), (0, 3, 1))
        self.assertEqual(self.game.best, 123)

    def test_clamp_and_fire_rate(self):
        self.game.update(0.05, -10000, True)
        self.assertEqual(self.game.player_x, 0)
        self.assertEqual(len(self.game.player_shots), 1)
        for _ in range(4):
            self.game.update(0.05, 0, True)
        self.assertEqual(len(self.game.player_shots), 1)
        self.game.update(0.05, 10000, True)
        self.assertEqual(self.game.player_x, 57)
        self.assertEqual(len(self.game.player_shots), 2)

    def test_projectile_hits_nearest_alien_and_awards_score(self):
        self.game.aliens = [[10, 10, 0], [10, 18, 2]]
        self.game.player_shots = [[12, 23.0]]
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.aliens, [[10, 10, 0]])
        self.assertEqual(self.game.score, 10)

    def test_damage_and_invulnerability(self):
        self.game.enemy_shots = [[32, 57.0], [32, 57.0]]
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.lives, 2)
        self.assertEqual(self.game.enemy_shots, [])
        self.game.enemy_shots = [[32, 57.0]]
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.lives, 2)
        self.game.clock = self.game.invulnerable_until
        self.game.enemy_shots = [[32, 57.0]]
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.lives, 1)
        self.game.clock = self.game.invulnerable_until
        self.game.enemy_shots = [[32, 57.0]]
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.state, "over")

    def test_edge_reversal_and_invasion(self):
        self.game.aliens = [[59, 50, 0]]
        self.game.move_at = 0
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.aliens[0][:2], [59, 53])
        self.assertEqual(self.game.direction, -1)
        self.game.aliens = [[0, 54, 0]]
        self.game.move_at = 0
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.state, "over")
        self.assertEqual(self.game.lives, 0)

    def test_pause_freezes_all_timers_and_wave_transition(self):
        self.game.aliens.clear()
        self.game.update(0.05, 0, False)
        self.assertEqual(self.game.state, "wave")
        self.game.pause()
        clock = self.game.clock
        self.game.update(20, 100, True)
        self.assertEqual(self.game.clock, clock)
        self.game.pause()
        for _ in range(21):
            self.game.update(0.05, 0, False)
        self.assertEqual(self.game.wave, 2)
        self.assertEqual(len(self.game.aliens), 18)

    def test_projectile_limits_and_enemy_front_row(self):
        for _ in range(250):
            self.game.update(0.05, 0, True)
            self.assertLessEqual(len(self.game.player_shots), 4)
            self.assertLessEqual(len(self.game.enemy_shots), 5)
        self.game.start()
        self.game.enemy_fire_at = 0
        self.game.update(0.01, 0, False)
        self.assertGreaterEqual(self.game.enemy_shots[0][1], 26)

    def test_stall_cap_and_invalid_duration(self):
        self.game.update(20, 0, False)
        self.assertEqual(self.game.clock, 0.05)
        with self.assertRaises(ValueError):
            self.game.update(-1, 0, False)

    def test_all_screens_fit_panel(self):
        bitmap = Bitmap()
        for state in ("ready", "playing", "paused", "wave", "over"):
            self.game.state = state
            for muted in (False, True):
                render(bitmap, self.game, muted)
                self.assertEqual(bitmap.pixels[0, 0], 1)
                self.assertEqual(bitmap.pixels[8, 0], 7 if muted else 4)
                self.assertEqual(len([p for p in bitmap.pixels if p[1] == 0]), 56)
        render(bitmap, self.game, False, True)
        self.game.score = 123456789012345678
        self.game.best = self.game.score
        self.game.state = "over"
        render(bitmap, self.game, False)


class ControlTests(unittest.TestCase):
    def test_button_bounce_and_hold(self):
        button = Button()
        button.update(False, 1)
        button.update(True, 1.01)
        button.update(False, 1.02)
        button.update(False, 1.06)
        self.assertTrue(button.fell)
        self.assertTrue(button.pressed)
        button.update(False, 2)
        self.assertFalse(button.fell)
        button.update(True, 3)
        button.update(True, 3.04)
        self.assertFalse(button.pressed)

    def test_calibration_deadzone_direction_and_wrap(self):
        steering = Steering()
        steering.calibrate((0, 9.8, 0))
        self.assertEqual(steering.velocity((0, 9.8, 0), 0.1), 0)
        self.assertGreater(steering.velocity((5, 8, 0), 0.1), 0)
        self.assertLess(steering.velocity((-5, 8, 0), 0.1), 0)
        steering.calibrate((0.01, -9.8, 0))
        self.assertEqual(steering.velocity((-0.01, -9.8, 0), 0.1), 0)
        inverted = Steering(direction=-1)
        inverted.calibrate((0, 9.8, 0))
        self.assertLess(inverted.velocity((5, 8, 0), 0.1), 0)
        with self.assertRaises(ValueError):
            steering.calibrate((0, 0, 9.8))
        with self.assertRaises(ValueError):
            Steering(0, 0)

    def test_progress_bar_milestones(self):
        self.assertEqual(score_bar(0), (0, 1000))
        self.assertEqual(score_bar(500), (26, 1000))
        self.assertEqual(score_bar(1000), (52, 1000))
        self.assertEqual(score_bar(1010), (26, 2000))
        self.assertEqual(score_bar(2000), (52, 2000))
        self.assertEqual(score_bar(4000), (52, 4000))


if __name__ == "__main__":
    unittest.main()
