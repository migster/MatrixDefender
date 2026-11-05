"""Small original sprites and a 3x5 font; no external image/font files."""

from game import PLAYER_Y, score_bar

FONT = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"),
    "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "110"),
}
ALIENS = (
    ("10101", "01110", "11111", "01010"),
    ("00100", "11111", "10101", "11011"),
)
SHIP = ("0001000", "0011100", "1111111", "1100011")


def sprite(bitmap, rows, x, y, color):
    for dy, row in enumerate(rows):
        for dx, value in enumerate(row):
            px, py = int(x) + dx, int(y) + dy
            if value == "1" and 0 <= px < 64 and 1 <= py < 64:
                bitmap[px, py] = color


def text(bitmap, message, y, color=5):
    x = (64 - (len(message) * 4 - 1)) // 2
    for char in message:
        if char != " ":
            sprite(bitmap, FONT[char], x, y, color)
        x += 4


def number(bitmap, value, y, color=5):
    # Python integers are exact; split long scores across rows rather than clip.
    digits = str(value)
    for offset in range(0, len(digits), 15):
        text(bitmap, digits[offset:offset + 15], y + (offset // 15) * 6, color)


def render(bitmap, game, muted, calibrating=False):
    bitmap.fill(0)
    for i in range(3):
        bitmap[i * 2, 0] = 1 if i < game.lives else 7
    bitmap[8, 0] = 7 if muted else 4
    filled, _ = score_bar(game.score)
    for i in range(52):
        bitmap[12 + i, 0] = 2 if i < filled else 7
    if calibrating:
        text(bitmap, "HOLD", 20)
        text(bitmap, "UPRIGHT", 28)
        text(bitmap, "STILL", 36)
    elif game.state == "ready":
        text(bitmap, "MATRIX", 9, 2)
        text(bitmap, "DEFENDER", 17, 1)
        sprite(bitmap, ALIENS[0], 29, 29, 3)
        text(bitmap, "FIRE", 42)
        text(bitmap, "TO START", 50)
    elif game.state == "over":
        text(bitmap, "GAME OVER", 6, 3)
        text(bitmap, "SCORE", 16)
        number(bitmap, game.score, 23, 2)
        text(bitmap, "BEST", 33)
        number(bitmap, game.best, 40, 1)
        text(bitmap, "FIRE TO GO", 53)
    elif game.state == "paused":
        text(bitmap, "PAUSED", 26, 2)
        text(bitmap, "UP TO GO", 38)
    elif game.state == "wave":
        text(bitmap, "WAVE", 24, 1)
        number(bitmap, game.wave + 1, 33)
    else:
        frame = int(game.clock * 4) % 2
        for x, y, row in game.aliens:
            sprite(bitmap, ALIENS[frame], x, y, (3, 2, 1)[row])
        if (
            game.clock >= game.invulnerable_until
            or int(game.clock * 10) % 2 == 0
        ):
            sprite(bitmap, SHIP, game.player_x, PLAYER_Y, 1)
        for x, y in game.player_shots:
            sprite(bitmap, ("1", "1"), x, y, 5)
        for x, y in game.enemy_shots:
            sprite(bitmap, ("1", "1"), x, y, 3)
