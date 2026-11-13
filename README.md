# Matrix Defender

An original tilt-controlled alien-defense game for the Adafruit MatrixPortal
S3 and one 64x64 RGB LED matrix. Reuses the speaker hardware from
[MatrixHalloween](https://github.com/migster/MatrixHalloween), without the PIR.
No Wi-Fi, cloud services, downloaded sprites, or audio files are needed.

## Hardware and wiring

- Adafruit MatrixPortal S3 (PID 5778).
- 64x64, 1/32-scan RGB matrix (previous project's PID 3649).
- Existing NS4168 I2S amplifier and speaker.
- **New:** normally-open momentary push button.

Disconnect USB power before rewiring. Remove the PIR and its power wires.
Leave the working amplifier and panel power connections unchanged.

| MatrixPortal S3 | Connection |
| --- | --- |
| A1 | NS4168 BCLK |
| A2 | NS4168 LRC / word select |
| A3 | NS4168 DIN |
| A4 | One terminal of the new fire button |
| GND | Other terminal of the fire button; common amplifier ground |
| HUB75 | Panel INPUT connector |
| Panel power +5V / GND | Existing panel red / black power leads |

The fire input uses an internal pull-up: pressing connects A4 to GND.
**Never connect A4 to +5V.** A1-A4 are board labels, not raw GPIO numbers.
For a four-legged tactile switch, use terminals on opposite electrical sides;
verify with a continuity meter, because same-side terminals are usually joined.
Speaker leads stay connected to the amplifier's speaker output, not ground.
Retain the shared power bus and amplifier supply from the working build;
verify the amplifier's supply rating before substituting hardware.

The MatrixPortal S3 **Address E** solder jumper must remain bridged to **8**
for the 64x64 1/32-scan panel. The built-in up/down buttons and accelerometer
need no additional wiring.

## Installation

1. Keep the reported CircuitPython 10.3.1 firmware if already working on this
   board. If reinstalling, use the official
   [MatrixPortal S3 board download](https://circuitpython.org/board/adafruit_matrixportal_s3/),
   not firmware for the older M4 MatrixPortal.
2. From the matching **CircuitPython 10.x**
   [Adafruit library bundle](https://circuitpython.org/libraries), copy:
   - `adafruit_lis3dh.mpy`
   - the complete `adafruit_bus_device/` directory
   to `CIRCUITPY/lib/`. These are the only external runtime dependencies.
3. Back up the old `CIRCUITPY/code.py` somewhere outside the device.
4. Copy this project's `game.py`, `graphics.py`, and finally `code.py` to the
   **root** of `CIRCUITPY`. Copying the entry point last avoids a premature
   reload with missing game modules. Do not copy tests onto the board.
5. CircuitPython automatically reloads. The panel should show MATRIX DEFENDER.
   Open the USB serial console for startup errors and calibration messages.

`board`, `digitalio`, `displayio`, `rgbmatrix`, `framebufferio`, `audiobusio`,
and `synthio` are firmware modules, not files to copy from the bundle.
No old Halloween code or audio assets are required.

## Play

- Press **fire** to start. Hold the panel upright, facing you and still for
  approximately 0.6 seconds while it averages a neutral steering position.
  Calibration repeats on each new game.
- Tilt left/right like a steering wheel to move. More tilt means faster
  movement; a small dead zone and filtering suppress jitter.
- Hold **fire** for repeated shots, at most approximately four shots/second.
- **Up:** pause/resume, including the between-wave countdown.
- **Down:** toggle **all** audio, even while paused or at game over.
  An amber pixel indicates audio enabled; dim means muted. Unmuting beeps.
- Destroy all 18 aliens to advance. Top/middle/bottom rows award 30/20/10
  points. Aliens accelerate as their numbers fall and as waves increase.
- Enemy shots cost one of three lives. After a hit, the ship blinks and is
  protected for 1.5 seconds. Aliens reaching the ship's row end the game
  immediately, even if lives remain.
- Game over shows exact score and best score; press fire to restart.
  Best score and mute state survive restarts **within the running session**,
  but reset on power loss or CircuitPython reload. No flash writes occur.

### Single-row HUD

Only row 0 is reserved:

- x=0,2,4: three green life LEDs; lost lives become dim.
- x=8: amber audio-enabled indicator.
- x=12..63: 52-pixel blue score progress bar on a dim track.

The score bar fills toward **1000 points**, then **2000**, **4000**, etc.
At each milestone it is full; after crossing it, it scales to the next
milestone, so the visible fill drops to about half. This is a progress
indicator, not a decimal score. Exact score is always shown at game over.

## Steering / display orientation

The display output is rotated 90 degrees clockwise for the handle-mounted
orientation. Defaults in `code.py` retain accelerometer X and Y as the
steering axes:

```python
ACCEL_HORIZONTAL_AXIS = 0
ACCEL_VERTICAL_AXIS = 1
STEERING_DIRECTION = 1
DISPLAY_ROTATION = 90
```

Axes are 0=X, 1=Y, 2=Z. If movement is reversed, set
`STEERING_DIRECTION = -1`. If tilting does not move the ship correctly,
swap the horizontal and vertical axes, then restart and recalibrate.
Use distinct axes lying in the panel's plane. Rotation can be
0, 90, 180, or 270 degrees clockwise. Start a new game after changing the
panel orientation to recalibrate neutral steering. The existing in-plane
axes support this quarter-turn without swapping; verify left/right movement
on hardware.

If calibration reports "Hold panel upright", hold it vertically rather than
flat and verify the selected axes. Failed calibration leaves the game on
its previous start/game-over screen; press fire again to retry.
The onboard LIS3DH uses I2C address 0x19, as in Adafruit's
[MatrixPortal accelerometer example](https://github.com/adafruit/Adafruit_CircuitPython_LIS3DH/blob/main/examples/lis3dh_simpletest.py).

## Validation and troubleshooting

Host-side rules, input, and pixel-boundary tests require only Python's standard
library:

```sh
python3 -m unittest discover -s tests -v
```

These tests do **not** prove physical accelerometer orientation, installed
firmware support, frame rate, sound volume, or wiring. Initial hardware check:

1. Confirm the title screen and serial startup message.
2. Start upright; test both steering directions and held fire.
3. Check up pauses movement/shots and down silences audio immediately.
4. Test audio at low volume. Adjust `AUDIO_VOLUME` in `code.py` if needed.
5. Play through a wave and a game over; confirm lives, progress, and restart.

Missing-library errors: check `lib/` placement and use the 10.x bundle.
I2C initialization errors: verify this is the MatrixPortal S3 and the onboard
accelerometer is accessible; startup exceptions are intentionally not hidden.
Blank/duplicated panel rows: check HUB75 INPUT, power, and Address E jumper.
No sound: check A1/A2/A3, amplifier power/common ground and mute indicator.
Unresponsive fire: verify the button shorts A4 to GND, not two already-joined
legs. Disconnect power before adjusting connections.

The game updates at a nominal 30 FPS, bounds projectile counts, reuses sound
notes, and caps simulation stalls to prevent collision tunneling. On a slow
frame the simulation slows rather than advancing through missed collisions.
