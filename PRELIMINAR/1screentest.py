from machine import Pin, SPI
import time
import math

WIDTH = 128
HEIGHT = 160
X_OFFSET = 0
Y_OFFSET = 0

# SPI0: GP4 = SCK, GP3 = MOSI/SDA
spi = SPI(
    0,
    baudrate=20_000_000,
    polarity=0,
    phase=0,
    sck=Pin(18),
    mosi=Pin(19),
)

cs = Pin(0, Pin.OUT, value=1)       # GP0 -> CS
dc = Pin(1, Pin.OUT, value=0)       # GP1 -> DC
reset = Pin(2, Pin.OUT, value=1)    # GP2 -> RES
backlight = Pin(5, Pin.OUT, value=1)  # GP5 -> BL


def command(cmd, data=None):
    cs.value(0)
    dc.value(0)
    spi.write(bytes((cmd,)))
    if data:
        dc.value(1)
        spi.write(data)
    cs.value(1)


def init_display():
    reset.value(0)
    time.sleep_ms(50)
    reset.value(1)
    time.sleep_ms(150)

    command(0x01)  # Software reset
    time.sleep_ms(150)
    command(0x11)  # Sleep out
    time.sleep_ms(120)

    command(0xB1, bytes((0x01, 0x2C, 0x2D)))
    command(0xB2, bytes((0x01, 0x2C, 0x2D)))
    command(0xB3, bytes((0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D)))
    command(0xB4, bytes((0x07,)))
    command(0xC0, bytes((0xA2, 0x02, 0x84)))
    command(0xC1, bytes((0xC5,)))
    command(0xC2, bytes((0x0A, 0x00)))
    command(0xC3, bytes((0x8A, 0x2A)))
    command(0xC4, bytes((0x8A, 0xEE)))
    command(0xC5, bytes((0x0E,)))
    command(0x20)  # Inversion off
    command(0x36, bytes((0xC8,)))  # Orientación y orden BGR
    command(0x3A, bytes((0x05,)))  # Color de 16 bits

    command(0xE0, bytes((
        0x02, 0x1C, 0x07, 0x12, 0x37, 0x32, 0x29, 0x2D,
        0x29, 0x25, 0x2B, 0x39, 0x00, 0x01, 0x03, 0x10
    )))
    command(0xE1, bytes((
        0x03, 0x1D, 0x07, 0x06, 0x2E, 0x2C, 0x29, 0x2D,
        0x2E, 0x2E, 0x37, 0x3F, 0x00, 0x00, 0x02, 0x10
    )))

    command(0x13)  # Normal display mode
    command(0x29)  # Display on
    time.sleep_ms(100)


# Buffer RGB565, con bytes en el orden que espera el ST7735.
buffer = bytearray(WIDTH * HEIGHT * 2)


def color_bytes(rgb565):
    return bytes((rgb565 >> 8, rgb565 & 0xFF))


def fill(rgb565):
    buffer[:] = color_bytes(rgb565) * (WIDTH * HEIGHT)


def pixel(x, y, rgb565):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        i = (y * WIDTH + x) * 2
        buffer[i] = rgb565 >> 8
        buffer[i + 1] = rgb565 & 0xFF


def rect(x, y, w, h, rgb565):
    if w <= 0 or h <= 0:
        return
    row = color_bytes(rgb565) * w
    for yy in range(max(0, y), min(HEIGHT, y + h)):
        left = max(0, x)
        right = min(WIDTH, x + w)
        if left < right:
            start = (yy * WIDTH + left) * 2
            buffer[start:start + (right - left) * 2] = row[:(right - left) * 2]


def triangle_row(y, apex_x, base_left, base_right, apex_y, base_y, rgb565):
    if y < apex_y or y > base_y:
        return
    t = (y - apex_y) / max(1, base_y - apex_y)
    left = int(apex_x + (base_left - apex_x) * t)
    right = int(apex_x + (base_right - apex_x) * t)
    rect(left, y, right - left + 1, 1, rgb565)


def draw_cat():
    background = 0x1028
    fur = 0xD5B2
    dark = 0x2104
    pink = 0xF986
    white = 0xFFFF
    green = 0x07E0

    fill(background)

    # Cola
    rect(88, 108, 8, 24, fur)
    rect(96, 100, 8, 16, fur)
    rect(88, 96, 16, 8, fur)

    # Cuerpo ovalado
    for y in range(82, 137):
        dy = (y - 109) / 28
        half_width = int(27 * math.sqrt(max(0, 1 - dy * dy)))
        rect(64 - half_width, y, half_width * 2, 1, fur)

    # Patas
    rect(43, 125, 14, 17, fur)
    rect(71, 125, 14, 17, fur)
    rect(39, 139, 20, 6, white)
    rect(69, 139, 20, 6, white)

    # Orejas y cabeza
    for y in range(32, 59):
        triangle_row(y, 43, 31, 63, 32, 58, fur)
        triangle_row(y, 85, 65, 99, 32, 58, fur)
        triangle_row(y, 44, 38, 55, 39, 57, pink)
        triangle_row(y, 84, 73, 91, 39, 57, pink)
    rect(34, 50, 60, 51, fur)

    # Ojos, nariz y boca
    rect(47, 68, 11, 12, green)
    rect(70, 68, 11, 12, green)
    rect(52, 70, 3, 9, dark)
    rect(75, 70, 3, 9, dark)
    rect(61, 83, 7, 5, pink)
    rect(64, 88, 2, 6, dark)
    rect(57, 93, 8, 2, dark)
    rect(65, 93, 8, 2, dark)

    # Bigotes
    rect(18, 83, 27, 2, white)
    rect(20, 91, 25, 2, white)
    rect(83, 83, 27, 2, white)
    rect(83, 91, 25, 2, white)


def show():
    command(0x2A, bytes((
        0, X_OFFSET, 0, X_OFFSET + WIDTH - 1
    )))
    command(0x2B, bytes((
        0, Y_OFFSET, 0, Y_OFFSET + HEIGHT - 1
    )))
    command(0x2C)

    cs.value(0)
    dc.value(1)
    spi.write(buffer)
    cs.value(1)


init_display()
draw_cat()
show()
