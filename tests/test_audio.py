"""Exercise the real audio controller with stand-in CircuitPython devices."""

from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class Output:
    def __init__(self, **pins):
        self.pins = pins
        self.playing = False

    def play(self, source):
        self.playing = True

    def stop(self):
        self.playing = False


class Synth:
    def __init__(self, **settings):
        self.pressed = []

    def press(self, note):
        self.pressed.append(note)

    def release(self, note):
        self.pressed.remove(note)


class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        modules = {
            name: SimpleNamespace()
            for name in (
                "adafruit_lis3dh", "digitalio", "displayio",
                "framebufferio", "rgbmatrix",
            )
        }
        modules["board"] = SimpleNamespace(A1="A1", A2="A2", A3="A3")
        modules["audiobusio"] = SimpleNamespace(I2SOut=Output)
        modules["synthio"] = SimpleNamespace(
            Synthesizer=Synth, Note=SimpleNamespace, Envelope=SimpleNamespace
        )
        path = Path(__file__).resolve().parents[1] / "code.py"
        with patch.dict(sys.modules, modules):
            cls.Sound = runpy.run_path(str(path), run_name="audio_test")["Sound"]

    def setUp(self):
        self.sound = self.Sound()

    def test_original_speaker_pins(self):
        self.assertEqual(
            self.sound.output.pins,
            {"bit_clock": "A1", "word_select": "A2", "data": "A3"},
        )

    def test_mute_stops_active_sound_and_blocks_every_effect(self):
        self.sound.play("over", 0)
        self.sound.toggle(0.1)
        self.assertTrue(self.sound.muted)
        self.assertFalse(self.sound.output.playing)
        self.assertEqual(self.sound.synth.pressed, [])
        for event in self.sound.notes:
            self.sound.play(event, 1)
            self.assertIsNone(self.sound.active)
        self.sound.toggle(2)
        self.assertFalse(self.sound.muted)
        self.assertTrue(self.sound.output.playing)
        self.assertEqual(self.sound.active_name, "unmute")
        self.sound.update(2.2)
        self.assertEqual(self.sound.synth.pressed, [])

    def test_priority_and_timed_release(self):
        self.sound.play("damage", 0)
        self.sound.play("step", 0.01)
        self.sound.play("fire", 0.02)
        self.assertEqual(self.sound.active_name, "damage")
        self.sound.play("over", 0.03)
        self.assertEqual(self.sound.active_name, "over")
        self.assertEqual(len(self.sound.synth.pressed), 1)
        self.sound.update(0.64)
        self.assertIsNone(self.sound.active)
        self.assertEqual(self.sound.synth.pressed, [])


if __name__ == "__main__":
    unittest.main()
