# Wonder - intérprete CHIP-8 / Super-CHIP (escrito para Wonder)
#
# CHIP-8 es una "consola" inventada en 1977: un programa de unos cientos de bytes
# (la ROM) usa 35 instrucciones muy simples, una pantalla de 64x32 puntos y un
# teclado de 16 teclas (0-F). Super-CHIP le agrega una pantalla de 128x64.
#
# Este archivo es la "máquina": lee la ROM y la ejecuta. La parte rápida usa el
# modo "viper" de MicroPython (se compila a código de máquina), por eso las
# variables llevan tipos (int, ptr8...).
#
# Reglas (quirks) que usan los juegos de Wonder, las mismas de Octo:
#   8xy6 / 8xyE desplazan vy, Fx55 / Fx65 avanzan I, VF se escribe al final,
#   los sprites que se salen por un borde aparecen por el otro.

import sys

try:
    import micropython
except ImportError:                                # en el computador (para probar)
    class micropython:
        @staticmethod
        def viper(f):
            return f

if sys.implementation.name != "micropython":      # en el computador (para probar)
    def ptr8(b):
        return b

    def ptr16(b):
        return memoryview(b).cast("H")

FUENTE = bytes((
    0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70, 0xF0, 0x10, 0xF0, 0x80, 0xF0,
    0xF0, 0x10, 0xF0, 0x10, 0xF0, 0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0,
    0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40, 0xF0, 0x90, 0xF0, 0x90, 0xF0,
    0xF0, 0x90, 0xF0, 0x10, 0xF0, 0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
    0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0, 0xF0, 0x80, 0xF0, 0x80, 0xF0,
    0xF0, 0x80, 0xF0, 0x80, 0x80))
FUENTE_GRANDE = bytes((
    0xFF, 0xFF, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0xFF, 0xFF, 0x18, 0x78, 0x78, 0x18, 0x18,
    0x18, 0x18, 0x18, 0xFF, 0xFF, 0xFF, 0xFF, 0x03, 0x03, 0xFF, 0xFF, 0xC0, 0xC0, 0xFF, 0xFF,
    0xFF, 0xFF, 0x03, 0x03, 0xFF, 0xFF, 0x03, 0x03, 0xFF, 0xFF, 0xC3, 0xC3, 0xC3, 0xC3, 0xFF,
    0xFF, 0x03, 0x03, 0x03, 0x03, 0xFF, 0xFF, 0xC0, 0xC0, 0xFF, 0xFF, 0x03, 0x03, 0xFF, 0xFF,
    0xFF, 0xFF, 0xC0, 0xC0, 0xFF, 0xFF, 0xC3, 0xC3, 0xFF, 0xFF, 0xFF, 0xFF, 0x03, 0x03, 0x06,
    0x0C, 0x18, 0x18, 0x18, 0x18, 0xFF, 0xFF, 0xC3, 0xC3, 0xFF, 0xFF, 0xC3, 0xC3, 0xFF, 0xFF,
    0xFF, 0xFF, 0xC3, 0xC3, 0xFF, 0xFF, 0x03, 0x03, 0xFF, 0xFF))

# Posiciones dentro de "est" (16 bits cada una)
_PC, _I, _SP, _DT, _ST, _HIRES, _AZAR, _CAMBIO, _TECLAS, _N, _FG, _BG, _ANTES = range(13)
_PILA = 16          # est[16..31] = pila de 16 llamadas
ANCHO, ALTO = 128, 64


@micropython.viper
def _correr(mem, regs, est, disp) -> int:
    """Ejecuta est[_N] instrucciones. 0 = normal, 1 = el juego terminó (00FD),
    2 = esperando una tecla (Fx0A), 3 = instrucción desconocida."""
    m = ptr8(mem)
    V = ptr8(regs)
    e = ptr16(est)
    d = ptr8(disp)
    pc = int(e[0])
    ii = int(e[1])
    sp = int(e[2])
    hires = int(e[5])
    teclas = int(e[8])
    n = int(e[9])
    w = 64
    h = 32
    if hires:
        w = 128
        h = 64
    res = 0
    while n > 0:
        n -= 1
        op = (int(m[pc & 0xFFF]) << 8) | int(m[(pc + 1) & 0xFFF])
        pc = (pc + 2) & 0xFFF
        x = (op >> 8) & 0xF
        y = (op >> 4) & 0xF
        kk = op & 0xFF
        nnn = op & 0xFFF
        a = op >> 12
        if a == 0:
            if op == 0x00E0:
                k = 0
                while k < 8192:
                    d[k] = 0
                    k += 1
                e[7] = 1
            elif op == 0x00EE:
                sp = (sp - 1) & 15
                pc = int(e[16 + sp])
            elif (op & 0xFFF0) == 0x00C0:            # bajar la pantalla n filas
                nf = op & 0xF
                fy = h - 1
                while fy >= 0:
                    fx = 0
                    while fx < w:
                        v = 0
                        if fy >= nf:
                            v = int(d[(fy - nf) * 128 + fx])
                        d[fy * 128 + fx] = v
                        fx += 1
                    fy -= 1
                e[7] = 1
            elif op == 0x00FB or op == 0x00FC:       # correr la pantalla 4 a la der / izq
                fy = 0
                while fy < h:
                    if op == 0x00FB:
                        fx = w - 1
                        while fx >= 0:
                            v = 0
                            if fx >= 4:
                                v = int(d[fy * 128 + fx - 4])
                            d[fy * 128 + fx] = v
                            fx -= 1
                    else:
                        fx = 0
                        while fx < w:
                            v = 0
                            if fx + 4 < w:
                                v = int(d[fy * 128 + fx + 4])
                            d[fy * 128 + fx] = v
                            fx += 1
                    fy += 1
                e[7] = 1
            elif op == 0x00FD:
                res = 1
                break
            elif op == 0x00FE or op == 0x00FF:
                hires = 0
                w = 64
                h = 32
                if op == 0x00FF:
                    hires = 1
                    w = 128
                    h = 64
                k = 0
                while k < 8192:
                    d[k] = 0
                    k += 1
                e[7] = 1
            else:
                res = 3
                break
        elif a == 1:
            pc = nnn
        elif a == 2:
            e[16 + sp] = pc
            sp = (sp + 1) & 15
            pc = nnn
        elif a == 3:
            if int(V[x]) == kk:
                pc = (pc + 2) & 0xFFF
        elif a == 4:
            if int(V[x]) != kk:
                pc = (pc + 2) & 0xFFF
        elif a == 5:
            if int(V[x]) == int(V[y]):
                pc = (pc + 2) & 0xFFF
        elif a == 6:
            V[x] = kk
        elif a == 7:
            V[x] = (int(V[x]) + kk) & 0xFF
        elif a == 8:
            t = op & 0xF
            vx = int(V[x])
            vy = int(V[y])
            if t == 0:
                V[x] = vy
            elif t == 1:
                V[x] = vx | vy
            elif t == 2:
                V[x] = vx & vy
            elif t == 3:
                V[x] = vx ^ vy
            elif t == 4:
                r = vx + vy
                V[x] = r & 0xFF
                if r > 255:
                    V[15] = 1
                else:
                    V[15] = 0
            elif t == 5:
                V[x] = (vx - vy) & 0xFF
                if vx >= vy:
                    V[15] = 1
                else:
                    V[15] = 0
            elif t == 6:
                V[x] = vy >> 1
                V[15] = vy & 1
            elif t == 7:
                V[x] = (vy - vx) & 0xFF
                if vy >= vx:
                    V[15] = 1
                else:
                    V[15] = 0
            elif t == 0xE:
                V[x] = (vy << 1) & 0xFF
                V[15] = (vy >> 7) & 1
        elif a == 9:
            if int(V[x]) != int(V[y]):
                pc = (pc + 2) & 0xFFF
        elif a == 0xA:
            ii = nnn
        elif a == 0xB:
            pc = (nnn + int(V[0])) & 0xFFF
        elif a == 0xC:
            r = int(e[6])
            r ^= (r << 7) & 0xFFFF
            r ^= r >> 9
            r ^= (r << 8) & 0xFFFF
            e[6] = r
            V[x] = (r ^ (r >> 8)) & kk
        elif a == 0xD:
            filas = op & 0xF
            ancho = 8
            if filas == 0:
                filas = 16
                ancho = 16
            x0 = int(V[x]) & (w - 1)
            y0 = int(V[y]) & (h - 1)
            choque = 0
            f = 0
            while f < filas:
                if ancho == 16:
                    bits = (int(m[(ii + 2 * f) & 0xFFF]) << 8) | int(m[(ii + 2 * f + 1) & 0xFFF])
                else:
                    bits = int(m[(ii + f) & 0xFFF]) << 8
                py = (y0 + f) & (h - 1)
                c = 0
                while c < ancho:
                    if bits & (0x8000 >> c):
                        k = py * 128 + ((x0 + c) & (w - 1))
                        if d[k]:
                            choque = 1
                        d[k] = int(d[k]) ^ 1
                    c += 1
                f += 1
            V[15] = choque
            e[7] = 1
        elif a == 0xE:
            k = (teclas >> (int(V[x]) & 0xF)) & 1
            if kk == 0x9E:
                if k:
                    pc = (pc + 2) & 0xFFF
            elif kk == 0xA1:
                if not k:
                    pc = (pc + 2) & 0xFFF
        elif a == 0xF:
            if kk == 0x07:
                V[x] = int(e[3]) & 0xFF
            elif kk == 0x0A:
                nuevas = teclas & (0xFFFF ^ int(e[12]))
                if nuevas:
                    k = 0
                    while not (nuevas >> k) & 1:
                        k += 1
                    V[x] = k
                else:
                    pc = (pc - 2) & 0xFFF
                    res = 2
                    break
            elif kk == 0x15:
                e[3] = int(V[x])
            elif kk == 0x18:
                e[4] = int(V[x])
            elif kk == 0x1E:
                ii = (ii + int(V[x])) & 0xFFFF
            elif kk == 0x29:
                ii = 0x50 + (int(V[x]) & 0xF) * 5
            elif kk == 0x30:
                ii = 0xA0 + (int(V[x]) & 0xF) * 10
            elif kk == 0x33:
                v = int(V[x])
                m[ii & 0xFFF] = v // 100
                m[(ii + 1) & 0xFFF] = (v // 10) % 10
                m[(ii + 2) & 0xFFF] = v % 10
            elif kk == 0x55:
                k = 0
                while k <= x:
                    m[(ii + k) & 0xFFF] = int(V[k])
                    k += 1
                ii = (ii + x + 1) & 0xFFFF
            elif kk == 0x65:
                k = 0
                while k <= x:
                    V[k] = int(m[(ii + k) & 0xFFF])
                    k += 1
                ii = (ii + x + 1) & 0xFFFF
            elif kk == 0x75:
                k = 0
                while k <= x and k < 8:
                    V[16 + k] = int(V[k])
                    k += 1
            elif kk == 0x85:
                k = 0
                while k <= x and k < 8:
                    V[k] = int(V[16 + k])
                    k += 1
    e[0] = pc
    e[1] = ii
    e[2] = sp
    e[5] = hires
    return res


@micropython.viper
def _pintar(disp, pant, est) -> int:
    """Pasa la pantalla CHIP-8 a colores RGB565 (128x64 puntos de Wonder).
    En modo normal (64x32) cada punto se dibuja de 2x2."""
    d = ptr8(disp)
    p = ptr16(pant)
    e = ptr16(est)
    fg = int(e[10])
    bg = int(e[11])
    if int(e[5]):
        k = 0
        while k < 8192:
            if d[k]:
                p[k] = fg
            else:
                p[k] = bg
            k += 1
    else:
        y = 0
        while y < 32:
            x = 0
            while x < 64:
                c = bg
                if d[y * 128 + x]:
                    c = fg
                o = y * 256 + x * 2
                p[o] = c
                p[o + 1] = c
                p[o + 128] = c
                p[o + 129] = c
                x += 1
            y += 1
    return 0


class Maquina:
    def __init__(self, rom, por_cuadro=15, fg=0xFFFF, bg=0x0000):
        """rom = bytes del juego. por_cuadro = instrucciones en cada 1/60 de segundo.
        fg y bg = colores ya en el formato de la pantalla (como los de color() en main.py)."""
        self.mem = bytearray(4096)
        self.mem[0x50:0x50 + len(FUENTE)] = FUENTE
        self.mem[0xA0:0xA0 + len(FUENTE_GRANDE)] = FUENTE_GRANDE
        self.mem[0x200:0x200 + len(rom)] = rom
        self.regs = bytearray(32)
        self.est = bytearray(64)
        self.disp = bytearray(ANCHO * ALTO)
        self.pant = bytearray(ANCHO * ALTO * 2)
        self._poner(_PC, 0x200)
        self._poner(_AZAR, 0xACE1 ^ (id(self) & 0xFFFF) or 1)
        self._poner(_N, por_cuadro)
        self._poner(_FG, fg & 0xFFFF)
        self._poner(_BG, bg & 0xFFFF)
        self.por_cuadro = por_cuadro
        self.estado = 0

    def _poner(self, i, v):
        self.est[2 * i] = v & 0xFF
        self.est[2 * i + 1] = (v >> 8) & 0xFF

    def _leer(self, i):
        return self.est[2 * i] | (self.est[2 * i + 1] << 8)

    def sembrar(self, n):
        self._poner(_AZAR, (n & 0xFFFF) or 1)

    def cuadro(self, teclas):
        """Un cuadro de 1/60 s: corre las instrucciones y baja los temporizadores.
        teclas = número con un bit por tecla CHIP-8 apretada. Devuelve el estado."""
        self._poner(_TECLAS, teclas)
        self._poner(_N, self.por_cuadro)
        self.estado = _correr(self.mem, self.regs, self.est, self.disp)
        self._poner(_ANTES, teclas)
        dt, st = self._leer(_DT), self._leer(_ST)
        if dt:
            self._poner(_DT, dt - 1)
        if st:
            self._poner(_ST, st - 1)
        return self.estado

    def sonido(self):
        """Cuántos 1/60 s le quedan al "buzzer" (0 = callado)."""
        return self._leer(_ST)

    def cambio(self):
        """True si la pantalla cambió desde el último pintar()."""
        return self.est[2 * _CAMBIO] != 0

    def pintar(self):
        self.est[2 * _CAMBIO] = 0
        _pintar(self.disp, self.pant, self.est)
        return self.pant
