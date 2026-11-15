import math
import unittest

from game import Game, Steering
from graphics import render_rally
from rally import Rally, SETTINGS
from test_game import Bitmap


class RallyTests(unittest.TestCase):
    def setUp(self):
        self.rally = Rally()
        self.rally.start()
        self.rally.serve_at = 0

    def test_menu_responds_to_gentle_tilt_that_moves_defender(self):
        for degrees, expected in ((-6, 0), (6, 2)):
            with self.subTest(degrees=degrees):
                steering = Steering()
                steering.calibrate((0, 9.8, 0))
                angle = math.radians(degrees)
                acceleration = (9.8 * math.sin(angle), 9.8 * math.cos(angle), 0)
                defender = Game()
                defender.start()
                rally = Rally()
                initial_x = defender.player_x
                for _ in range(30):
                    velocity = steering.velocity(acceleration, 1 / 30)
                    defender.update(1 / 30, velocity, False)
                    rally.update(1 / 30, velocity)
                self.assertGreater((defender.player_x - initial_x) * degrees, 0)
                self.assertEqual(rally.difficulty, expected)

    def test_tilt_selection_deadzone_repeat_and_limits(self):
        rally = Rally()
        rally.update(0.05, 0)
        self.assertEqual(rally.difficulty, 1)
        rally.update(0.05, -65)
        self.assertEqual(rally.difficulty, 0)
        for _ in range(20):
            rally.update(0.05, -65)
        self.assertEqual(rally.difficulty, 0)
        rally.update(0.05, 0)
        rally.update(0.05, 65)
        self.assertEqual(rally.difficulty, 1)
        rally.update(0.05, 65)
        self.assertEqual(rally.difficulty, 1)
        for _ in range(20):
            rally.update(0.05, 65)
        self.assertEqual(rally.difficulty, 2)
        rally.start()
        self.assertEqual(rally.difficulty, 2)
        self.assertEqual(rally.ball_speed, SETTINGS[2][0])

    def test_menu_keeps_selection_for_tilt_inside_steering_deadzone(self):
        steering = Steering()
        steering.calibrate((0, 9.8, 0))
        rally = Rally()
        for frame in range(30):
            angle = math.radians(1 if frame % 2 else -1)
            acceleration = (9.8 * math.sin(angle), 9.8 * math.cos(angle), 0)
            rally.update(1 / 30, steering.velocity(acceleration, 1 / 30))
        self.assertEqual(rally.difficulty, 1)

    def test_paddle_bounds_and_difficulty_speed(self):
        speeds = []
        computer_movements = []
        for difficulty in range(3):
            rally = Rally()
            rally.difficulty = difficulty
            rally.start()
            rally.ball_x = 62
            rally.update(0.05, 10000)
            self.assertEqual(rally.player_x, 52)
            computer_movements.append(rally.computer_x - 26)
            speeds.append(math.hypot(rally.vx, rally.vy))
            rally.update(0.05, -10000)
            self.assertEqual(rally.player_x, 0)
        self.assertLess(speeds[0], speeds[1])
        self.assertLess(speeds[1], speeds[2])
        self.assertLess(computer_movements[0], computer_movements[1])
        self.assertLess(computer_movements[1], computer_movements[2])

    def test_walls_and_both_paddle_faces_at_max_speed(self):
        rally = self.rally
        rally.ball_x, rally.ball_y = 61.9, 32
        rally.vx, rally.vy = 85, 0
        rally.update(0.05, 0)
        self.assertLess(rally.vx, 0)
        self.assertLessEqual(rally.ball_x, 62)
        rally.ball_x = 1.1
        rally.vx = -85
        rally.update(0.05, 0)
        self.assertGreater(rally.vx, 0)
        self.assertGreaterEqual(rally.ball_x, 1)
        for y, vy in ((57, 85), (6, -85)):
            with self.subTest(y=y):
                rally.ball_x, rally.ball_y = 32, y
                rally.vx, rally.vy = 0, vy
                rally.ball_speed = 85
                rally.update(0.05, 0)
                self.assertLess(rally.vy * vy, 0)
                self.assertIn("hit", rally.events)
                self.assertAlmostEqual(math.hypot(rally.vx, rally.vy), 85)
                self.assertNotEqual(rally.vx, 0)

    def test_missed_paddles_score_and_end_at_five(self):
        rally = self.rally
        for player in (True, False):
            rally.start()
            for point in range(5):
                rally.serve_at = 0
                rally.ball_x = 1
                rally.ball_y = 0 if player else 63
                rally.vx = 0
                rally.vy = -85 if player else 85
                rally.update(0.05, 0)
                score = rally.player_score if player else rally.computer_score
                self.assertEqual(score, point + 1)
                self.assertEqual(rally.state, "over" if point == 4 else "playing")
            self.assertIn("clear" if player else "over", rally.events)
            rally.show_menu()
            self.assertEqual(rally.state, "menu")
            self.assertEqual((rally.player_score, rally.computer_score), (0, 0))

    def test_ball_outside_paddle_does_not_bounce(self):
        rally = self.rally
        rally.ball_x, rally.ball_y = 1, 57
        rally.vx, rally.vy = 0, 85
        rally.update(0.05, 0)
        self.assertGreater(rally.ball_y, 59)
        self.assertGreater(rally.vy, 0)
        self.assertNotIn("hit", rally.events)

    def test_pause_freezes_serve_ball_paddles_and_score(self):
        rally = self.rally
        rally.serve_at = 0.8
        rally.update(0.05, 0)
        self.assertEqual(rally.ball_y, 32)
        before = (rally.clock, rally.ball_x, rally.ball_y, rally.player_x)
        self.assertTrue(rally.pause())
        rally.update(10, 65)
        self.assertEqual(
            (rally.clock, rally.ball_x, rally.ball_y, rally.player_x), before
        )
        self.assertTrue(rally.pause())
        rally.serve_at = 0
        rally.update(10, 65)
        self.assertAlmostEqual(rally.clock, before[0] + 0.05)
        self.assertNotEqual(rally.ball_y, before[2])
        with self.assertRaises(ValueError):
            rally.update(-1, 0)

    def test_all_screens_and_extreme_positions_fit_panel(self):
        bitmap = Bitmap()
        rally = self.rally
        for state in ("menu", "playing", "paused", "over"):
            for difficulty in range(3):
                for muted in (False, True):
                    rally.state = state
                    rally.difficulty = difficulty
                    rally.player_score = 5
                    rally.computer_score = 4
                    render_rally(bitmap, rally, muted)
                    self.assertEqual(bitmap.pixels[8, 0], 7 if muted else 4)
                    render_rally(bitmap, rally, muted, True)
        rally.state = "playing"
        for x in (0, 52):
            for y in (-1, 64):
                rally.player_x = rally.computer_x = x
                rally.ball_x, rally.ball_y = x, y
                render_rally(bitmap, rally, False)

    def test_menu_options_share_one_row_and_only_selection_is_green(self):
        bitmap = Bitmap()
        rally = Rally()
        for selected in range(3):
            rally.difficulty = selected
            render_rally(bitmap, rally, False)
            options = {
                (x, y): color for (x, y), color in bitmap.pixels.items()
                if 20 <= y < 48
            }
            rows = {y for _, y in options}
            self.assertEqual(max(rows) - min(rows), 4)
            for i, (left, right) in enumerate(((0, 24), (24, 40), (40, 64))):
                pixels = {
                    color for (x, _), color in options.items() if left <= x < right
                }
                self.assertEqual(pixels, {1 if i == selected else 5})


if __name__ == "__main__":
    unittest.main()
