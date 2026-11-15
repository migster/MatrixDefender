"""Matrix Defender entry point for the Adafruit MatrixPortal S3."""

from array import array
import time

import adafruit_lis3dh
import audiobusio
import board
import digitalio
import displayio
import framebufferio
import rgbmatrix
import synthio

from game import Button, Game, HandButtons, Steering
from graphics import render, render_rally
from rally import Rally

# These axes depend on how the MatrixPortal is mounted behind the panel.
ACCEL_HORIZONTAL_AXIS = 0
ACCEL_VERTICAL_AXIS = 1
STEERING_DIRECTION = 1
DISPLAY_ROTATION = 90
AUDIO_VOLUME = 0.12
FRAME_SECONDS = 1 / 30


def input_pin(pin):
    result = digitalio.DigitalInOut(pin)
    result.switch_to_input(pull=digitalio.Pull.UP)
    return result


class Sound:
    def __init__(self):
        self.output = audiobusio.I2SOut(
            bit_clock=board.A1, word_select=board.A2, data=board.A3
        )
        self.synth = synthio.Synthesizer(sample_rate=22050, channel_count=1)
        self.output.play(self.synth)
        self.waveform = array("h", [12000] * 16 + [-12000] * 16)
        envelope = synthio.Envelope(
            attack_time=0.005, decay_time=0.04, release_time=0.015,
            attack_level=AUDIO_VOLUME, sustain_level=AUDIO_VOLUME * 0.5,
        )
        self.notes = {
            name: synthio.Note(
                frequency=frequency, waveform=self.waveform, envelope=envelope
            )
            for name, frequency in (
                ("fire", 880), ("hit", 180), ("damage", 65),
                ("over", 49), ("clear", 660), ("wave", 440),
                ("step", 90), ("unmute", 1046),
            )
        }
        self.durations = {
            "fire": 0.045, "hit": 0.09, "damage": 0.28, "over": 0.6,
            "clear": 0.25, "wave": 0.2, "step": 0.025, "unmute": 0.12,
        }
        self.priorities = {
            "step": 0, "fire": 1, "hit": 2, "wave": 3, "unmute": 3,
            "clear": 4, "damage": 5, "over": 6,
        }
        self.active = None
        self.active_name = None
        self.ends_at = 0.0
        self.muted = False

    def stop(self):
        if self.active is not None:
            self.synth.release(self.active)
            self.active = None
            self.active_name = None

    def update(self, now):
        if self.active is not None and now >= self.ends_at:
            self.stop()

    def play(self, name, now):
        if self.muted:
            return
        if (
            self.active_name is not None
            and self.priorities[name] < self.priorities[self.active_name]
        ):
            return
        self.stop()
        self.active = self.notes[name]
        self.active_name = name
        self.synth.press(self.active)
        self.ends_at = now + self.durations[name]

    def toggle(self, now):
        self.muted = not self.muted
        self.stop()
        # Stop the output too, so an envelope release cannot leak past mute.
        if self.muted:
            self.output.stop()
        else:
            self.output.play(self.synth)
            self.play("unmute", now)
        print("Audio muted" if self.muted else "Audio enabled")


def main():
    displayio.release_displays()
    matrix = rgbmatrix.RGBMatrix(
        width=64, height=64, bit_depth=3, doublebuffer=True,
        rgb_pins=(
            board.MTX_R1, board.MTX_G1, board.MTX_B1,
            board.MTX_R2, board.MTX_G2, board.MTX_B2,
        ),
        addr_pins=(
            board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC,
            board.MTX_ADDRD, board.MTX_ADDRE,
        ),
        clock_pin=board.MTX_CLK, latch_pin=board.MTX_LAT,
        output_enable_pin=board.MTX_OE,
    )
    display = framebufferio.FramebufferDisplay(
        matrix, auto_refresh=False, rotation=DISPLAY_ROTATION
    )
    bitmap = displayio.Bitmap(64, 64, 8)
    palette = displayio.Palette(8)
    for i, color in enumerate((
        0x000000, 0x00A040, 0x0080D0, 0xC02010,
        0x804000, 0x808080, 0x500080, 0x080808,
    )):
        palette[i] = color
    root = displayio.Group()
    root.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    display.root_group = root

    right_button_pin = input_pin(board.A4)
    left_button_pin = input_pin(board.RX)
    down_pin = input_pin(board.BUTTON_DOWN)
    up_pin = input_pin(board.BUTTON_UP)
    hands = HandButtons(right_button_pin.value, left_button_pin.value)
    down = Button(down_pin.value)
    up = Button(up_pin.value)
    # LIS3DH is onboard at 0x19; its driver manages the I2C lock.
    accel = adafruit_lis3dh.LIS3DH_I2C(board.I2C(), address=0x19)
    accel.range = adafruit_lis3dh.RANGE_2_G
    steering = Steering(
        ACCEL_HORIZONTAL_AXIS, ACCEL_VERTICAL_AXIS, STEERING_DIRECTION
    )
    sound = Sound()
    game = Game()
    rally = Rally()
    active = game
    calibration_at = None
    calibration_action = "start"
    menu_calibrated = False
    shortcut_to_rally = False
    samples = 0
    sums = [0.0, 0.0, 0.0]
    last_frame = time.monotonic()
    print("Matrix Defender ready: A4 right / RXI left start/fire, UP pause, DOWN mute")
    try:
        while True:
            now = time.monotonic()
            previous_hold = hands.hold_at
            shortcut = hands.update(right_button_pin.value, left_button_pin.value, now)
            if previous_hold is None and hands.hold_at is not None:
                shortcut_to_rally = (
                    active is game and game.state == "ready"
                    and calibration_at is None
                )
            down.update(down_pin.value, now)
            up.update(up_pin.value, now)
            sound.update(now)
            if down.fell:
                sound.toggle(now)
            if shortcut:
                sound.stop()
                calibration_at = None
                if shortcut_to_rally:
                    rally.show_menu()
                    active = rally
                    menu_calibrated = False
                    calibration_action = "menu"
                    calibration_at = now
                    samples = 0
                    sums = [0.0, 0.0, 0.0]
                    print("Matrix Rally: hold panel upright and still for menu calibration")
                else:
                    game.return_to_title()
                    active = game
                    print("Returned to Matrix Defender title")
            if up.fell and calibration_at is None and active.pause():
                sound.stop()
            if (
                hands.start_pressed
                and active.state in ("ready", "over", "menu")
                and calibration_at is None
            ):
                calibration_action = "start"
                if active is rally:
                    if rally.state == "over":
                        rally.show_menu()
                        menu_calibrated = False
                    if not menu_calibrated:
                        calibration_action = "menu"
                calibration_at = now
                samples = 0
                sums = [0.0, 0.0, 0.0]
                sound.stop()
                print("Calibrating: hold panel upright and still")
            dt = now - last_frame
            if dt < FRAME_SECONDS:
                time.sleep(0.002)
                continue
            last_frame = now
            acceleration = accel.acceleration
            if calibration_at is not None:
                for axis in range(3):
                    sums[axis] += acceleration[axis]
                samples += 1
                if now - calibration_at >= 0.6:
                    try:
                        steering.calibrate(tuple(v / samples for v in sums))
                    except ValueError as error:
                        print("Calibration failed:", error, "- press FIRE to retry")
                    else:
                        if calibration_action == "menu":
                            menu_calibrated = True
                            print("Matrix Rally: tilt to select, FIRE to start")
                        else:
                            active.start()
                            sound.play("wave", now)
                            print("Game started; neutral angle:", steering.neutral)
                    calibration_at = None
            else:
                velocity = steering.velocity(acceleration, min(dt, 0.05))
                if active is game:
                    game.update(dt, velocity, hands.firing)
                elif rally.state != "menu" or menu_calibrated:
                    rally.update(dt, velocity)
                if active.events:
                    event = max(active.events, key=lambda e: sound.priorities[e])
                    sound.play(event, now)
                    if active is game and "over" in game.events:
                        print("Game over. Score:", game.score, "Best:", game.best)
            if active is game:
                render(bitmap, game, sound.muted, calibration_at is not None)
            else:
                render_rally(bitmap, rally, sound.muted, calibration_at is not None)
            display.refresh(minimum_frames_per_second=0)
    finally:
        sound.stop()
        sound.output.stop()
        sound.output.deinit()
        sound.synth.deinit()
        right_button_pin.deinit()
        left_button_pin.deinit()
        down_pin.deinit()
        up_pin.deinit()


if __name__ == "__main__":
    main()
