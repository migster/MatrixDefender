"""Exercise both hand buttons through the real entry-point loop."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from game import Game, HandButtons
from rally import Rally


class ButtonIntegrationTests(unittest.TestCase):
    def test_either_button_starts_restarts_and_fires(self):
        for state in ("ready", "over"):
            for held in (("A4",), ("RX",)):
                with self.subTest(state=state, held=held):
                    self.check_buttons(state, held)

    def check_buttons(self, state, held):
        pins = {
            name: Mock(value=True)
            for name in ("A4", "RX", "DOWN", "UP")
        }
        digitalio = SimpleNamespace(
            DigitalInOut=Mock(side_effect=pins.__getitem__),
            Pull=SimpleNamespace(UP="pull-up"),
        )
        board = MagicMock(A4="A4", RX="RX", BUTTON_DOWN="DOWN", BUTTON_UP="UP")
        game = Mock(state=state, events=[])

        def start():
            game.state = "playing"

        game.start.side_effect = start
        sound = Mock(muted=False)
        steering = Mock()
        steering.velocity.return_value = 0
        accel = SimpleNamespace(acceleration=(0, 9.8, 0))
        modules = {
            name: MagicMock()
            for name in (
                "audiobusio", "displayio", "framebufferio", "rgbmatrix", "synthio",
            )
        }
        modules.update(
            board=board,
            digitalio=digitalio,
            adafruit_lis3dh=SimpleNamespace(
                LIS3DH_I2C=Mock(return_value=accel), RANGE_2_G=2,
            ),
        )
        path = Path(__file__).resolve().parents[1] / "code.py"
        with patch.dict(sys.modules, modules):
            entry = runpy.run_path(str(path), run_name="button_test")

        frames = iter(range(23))

        def tick():
            frame = next(frames)
            for name in ("A4", "RX"):
                pressed = name in held and 1 <= frame <= 18
                pins[name].value = not pressed
            return frame * 0.05

        with patch.dict(entry["main"].__globals__, {
            "time": SimpleNamespace(monotonic=tick, sleep=Mock()),
            "Game": Mock(return_value=game),
            "Sound": Mock(return_value=sound),
            "Steering": Mock(return_value=steering),
            "render": Mock(),
        }), redirect_stdout(StringIO()):
            with self.assertRaises(StopIteration):
                entry["main"]()

        game.start.assert_called_once_with()
        steering.calibrate.assert_called_once()
        firing = [call.args[2] for call in game.update.call_args_list]
        self.assertIn(True, firing)
        self.assertEqual(firing[-3:], [False, False, False])
        for name in ("A4", "RX"):
            pins[name].switch_to_input.assert_called_once_with(pull="pull-up")
            pins[name].deinit.assert_called_once_with()


class HandButtonTests(unittest.TestCase):
    def test_shortcut_threshold_and_release_rearming(self):
        hands = HandButtons()
        hands.update(False, False, 0)
        self.assertFalse(hands.update(False, False, 0.04))
        self.assertFalse(hands.update(False, False, 3.039))
        self.assertFalse(hands.firing)
        self.assertFalse(hands.start_pressed)
        self.assertTrue(hands.update(False, False, 3.04))
        self.assertFalse(hands.update(False, False, 9))
        hands.update(True, False, 10)
        hands.update(True, False, 10.04)
        self.assertFalse(hands.firing)
        hands.update(True, True, 11)
        hands.update(True, True, 11.04)
        hands.update(False, False, 12)
        hands.update(False, False, 12.04)
        self.assertTrue(hands.update(False, False, 15.04))

    def test_interrupted_hold_resets_timer(self):
        hands = HandButtons()
        hands.update(False, False, 0)
        hands.update(False, False, 0.04)
        hands.update(True, False, 2)
        hands.update(False, False, 2.01)
        self.assertFalse(hands.update(False, False, 3.04))
        self.assertTrue(hands.update(False, False, 5.01))

    def test_staggered_chord_cancels_start_and_fire(self):
        hands = HandButtons()
        hands.update(False, True, 0)
        hands.update(False, True, 0.04)
        hands.update(False, False, 0.06)
        self.assertFalse(hands.firing)
        hands.update(False, False, 0.10)
        hands.update(False, False, 0.15)
        self.assertFalse(hands.start_pressed)
        self.assertFalse(hands.firing)

    def test_short_single_press_still_selects_once_after_release(self):
        hands = HandButtons()
        hands.update(False, True, 0)
        hands.update(False, True, 0.04)
        hands.update(True, True, 0.06)
        hands.update(True, True, 0.10)
        hands.update(True, True, 0.13)
        self.assertTrue(hands.start_pressed)
        self.assertFalse(hands.firing)
        hands.update(True, True, 0.20)
        self.assertFalse(hands.start_pressed)


class ShortcutIntegrationTests(unittest.TestCase):
    def run_loop(self, game, schedule, frames, velocity=0, on_frame=None):
        pins = {name: Mock(value=True) for name in ("A4", "RX", "DOWN", "UP")}
        rally = Rally()
        steering = Mock(neutral=0)
        steering.velocity.return_value = velocity
        sound = Mock(muted=False)
        sound.priorities = {
            "step": 0, "fire": 1, "hit": 2, "wave": 3, "unmute": 3,
            "clear": 4, "damage": 5, "over": 6,
        }
        modules = {
            name: MagicMock()
            for name in (
                "audiobusio", "displayio", "framebufferio", "rgbmatrix", "synthio",
            )
        }
        modules.update(
            board=MagicMock(A4="A4", RX="RX", BUTTON_DOWN="DOWN", BUTTON_UP="UP"),
            digitalio=SimpleNamespace(
                DigitalInOut=Mock(side_effect=pins.__getitem__),
                Pull=SimpleNamespace(UP="pull-up"),
            ),
            adafruit_lis3dh=SimpleNamespace(
                LIS3DH_I2C=Mock(return_value=SimpleNamespace(acceleration=(0, 9.8, 0))),
                RANGE_2_G=2,
            ),
        )
        path = Path(__file__).resolve().parents[1] / "code.py"
        with patch.dict(sys.modules, modules):
            entry = runpy.run_path(str(path), run_name="shortcut_test")
        ticks = iter(range(frames))
        screens = []

        def tick():
            frame = next(ticks)
            if on_frame is not None:
                on_frame(frame, rally)
            held = schedule(frame)
            for name, pin in pins.items():
                pin.value = name not in held
            return frame * 0.05

        def capture(mode):
            def render(bitmap, active, muted, calibrating):
                screens.append((mode, active.state, calibrating))
            return render

        with patch.dict(entry["main"].__globals__, {
            "time": SimpleNamespace(monotonic=tick, sleep=Mock()),
            "Game": Mock(return_value=game),
            "Rally": Mock(return_value=rally),
            "Sound": Mock(return_value=sound),
            "Steering": Mock(return_value=steering),
            "render": capture("defender"),
            "render_rally": capture("rally"),
        }), redirect_stdout(StringIO()):
            with self.assertRaises(StopIteration):
                entry["main"]()
        return rally, screens, sound

    def test_home_chord_opens_menu_without_starting_and_requires_release(self):
        game = Game()
        rally, screens, _ = self.run_loop(
            game, lambda frame: ("A4", "RX") if frame >= 1 else (), 160
        )
        self.assertEqual(game.state, "ready")
        self.assertEqual(rally.state, "menu")
        self.assertIn(("rally", "menu", False), screens)
        self.assertNotIn(("defender", "playing", False), screens)
        self.assertEqual(screens[-1], ("rally", "menu", False))

    def test_defender_chord_suppresses_fire_and_returns_home_from_all_states(self):
        for state in ("playing", "paused", "wave", "over"):
            with self.subTest(state=state):
                game = Game()
                game.start()
                game.score = 123
                game.best = 456
                game.state = state
                if state == "wave":
                    game.wave_at = 100
                game.update = Mock(wraps=game.update)
                _, screens, _ = self.run_loop(
                    game, lambda frame: ("A4", "RX") if frame >= 1 else (), 140
                )
                self.assertEqual(game.state, "ready")
                self.assertEqual(game.best, 456)
                self.assertEqual(game.player_shots, [])
                self.assertFalse(any(call.args[2] for call in game.update.call_args_list))
                self.assertFalse(any(mode == "rally" for mode, _, _ in screens))

    def test_menu_selection_start_pause_mute_and_return(self):
        def schedule(frame):
            if 1 <= frame <= 80 or frame >= 130:
                return ("A4", "RX")
            if 85 <= frame <= 90:
                return ("RX",)
            if 110 <= frame <= 113:
                return ("UP",)
            if 118 <= frame <= 121:
                return ("DOWN",)
            return ()

        game = Game()
        rally, screens, sound = self.run_loop(game, schedule, 210, velocity=65)
        self.assertEqual(rally.difficulty, 2)
        self.assertIn(("rally", "playing", False), screens)
        self.assertIn(("rally", "paused", False), screens)
        sound.toggle.assert_called_once()
        self.assertEqual(screens[-1], ("defender", "ready", False))
        self.assertEqual(game.state, "ready")

    def test_return_from_rally_menu_requires_a_new_hold(self):
        def schedule(frame):
            if 1 <= frame <= 80 or frame >= 86:
                return ("A4", "RX")
            return ()

        _, screens, _ = self.run_loop(Game(), schedule, 160)
        self.assertIn(("rally", "menu", False), screens)
        self.assertEqual(screens[-1], ("defender", "ready", False))

    def test_short_home_chord_does_not_start_either_game(self):
        _, screens, _ = self.run_loop(
            Game(), lambda frame: ("A4", "RX") if 1 <= frame <= 59 else (), 90
        )
        self.assertTrue(all(screen == ("defender", "ready", False) for screen in screens))

    def test_shortcut_during_start_calibration_returns_home_not_rally(self):
        def schedule(frame):
            if 1 <= frame <= 4:
                return ("A4",)
            if frame >= 6:
                return ("A4", "RX")
            return ()

        _, screens, _ = self.run_loop(Game(), schedule, 110)
        self.assertIn(("defender", "ready", True), screens)
        self.assertFalse(any(mode == "rally" for mode, _, _ in screens))
        self.assertEqual(screens[-1], ("defender", "ready", False))

    def test_rally_game_over_returns_to_menu_and_allows_rematch(self):
        def schedule(frame):
            if 1 <= frame <= 80:
                return ("A4", "RX")
            if 85 <= frame <= 90 or 115 <= frame <= 120 or 140 <= frame <= 145:
                return ("RX",)
            return ()

        def finish(frame, rally):
            if frame == 110:
                rally.player_score = 5
                rally.state = "over"

        rally, screens, _ = self.run_loop(Game(), schedule, 170, on_frame=finish)
        self.assertIn(("rally", "over", False), screens)
        self.assertIn(("rally", "menu", False), screens[110:])
        self.assertEqual(rally.state, "playing")
        self.assertEqual((rally.player_score, rally.computer_score), (0, 0))


if __name__ == "__main__":
    unittest.main()
