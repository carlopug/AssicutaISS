"""Genera icona e schermata di avvio di AssicutaISS in assets/ (prima versione, da personalizzare).

Uso:  .venv\\Scripts\\python.exe tools\\make_assets.py
Si possono sostituire liberamente assets/icona.png, assets/icona.ico e assets/splash.png con immagini proprie.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

NAVY = (11, 22, 44)
NAVY2 = (20, 44, 82)
ORANGE = (240, 140, 50)
GOLD = (232, 190, 92)
WHITE = (236, 242, 250)
# colori delle barre SSTV (Robot36 test pattern)
BARS = [(235, 235, 235), (230, 216, 74), (79, 198, 210), (76, 176, 90), (180, 91, 180), (207, 75, 60), (61, 85, 196)]


def font(name, size):
    for n in (name, "segoeuib.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(os.path.join(FONTS, n), size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_iss(d, cx, cy, s, panel=GOLD, body=WHITE, detail=True):
    """ISS stilizzata centrata in (cx, cy); s = larghezza totale."""
    u = s / 20.0
    # traliccio principale
    d.rectangle([cx - 9.5 * u, cy - 0.45 * u, cx + 9.5 * u, cy + 0.45 * u], fill=body)
    # 4 coppie di pannelli solari (sopra e sotto il traliccio)
    for x in (-8.3, -5.2, 5.2, 8.3):
        for sign in (-1, 1):
            y0 = cy + sign * 0.9 * u
            y1 = cy + sign * 6.2 * u
            d.rectangle([cx + (x - 1.2) * u, min(y0, y1), cx + (x + 1.2) * u, max(y0, y1)], fill=panel)
            if detail:
                for k in range(1, 4):
                    yy = y0 + (y1 - y0) * k / 4
                    d.line([cx + (x - 1.2) * u, yy, cx + (x + 1.2) * u, yy], fill=NAVY, width=max(1, int(u * 0.18)))
    # moduli pressurizzati al centro
    d.rectangle([cx - 1.0 * u, cy - 3.6 * u, cx + 1.0 * u, cy + 3.6 * u], fill=body)
    d.rectangle([cx - 2.6 * u, cy - 1.1 * u, cx + 2.6 * u, cy + 1.1 * u], fill=body)
    # radiatori
    if detail:
        for x in (-2.6, 2.6):
            d.rectangle([cx + (x - 0.35) * u, cy + 1.3 * u, cx + (x + 0.35) * u, cy + 3.8 * u], fill=(190, 205, 220))


def make_icon(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # fondo: quadrato arrotondato con sfumatura verticale
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / size
        gd.line([(0, y), (size, y)], fill=tuple(int(NAVY2[i] * (1 - t) + NAVY[i] * t) for i in range(3)) + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.2), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # arco d'orbita
    r = size * 0.62
    d.arc([size * 0.5 - r, size * 0.62 - r * 0.42, size * 0.5 + r, size * 0.62 + r * 0.42],
          start=195, end=345, fill=ORANGE, width=int(size * 0.035))
    # ISS
    draw_iss(d, size * 0.5, size * 0.44, size * 0.78)
    # barre SSTV in basso
    x0, x1 = size * 0.16, size * 0.84
    y0, y1 = size * 0.76, size * 0.86
    w = (x1 - x0) / len(BARS)
    for i, c in enumerate(BARS):
        d.rectangle([x0 + i * w, y0, x0 + (i + 1) * w - 1, y1], fill=c)
    return img


def make_splash(w=640, h=400, scale=2):
    W, H = w * scale, h * scale
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(NAVY[i] * (1 - t) + (6, 12, 26)[i] * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    # stelle
    rnd = random.Random(36)
    for _ in range(260):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H * 0.8)
        r = rnd.choice([1, 1, 1, 2, 2, 3]) * scale * 0.6
        a = rnd.randint(90, 255)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(a, a, min(255, a + 20)))
    # Terra: grande disco in basso a sinistra con alone atmosferico
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    ex, ey, er = W * 0.12, H * 1.55, H * 1.0
    gd.ellipse([ex - er - 30 * scale, ey - er - 30 * scale, ex + er + 30 * scale, ey + er + 30 * scale], fill=200)
    glow = glow.filter(ImageFilter.GaussianBlur(22 * scale))
    img.paste(Image.new("RGB", (W, H), (80, 150, 255)), (0, 0), glow)
    d = ImageDraw.Draw(img)
    d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=(18, 52, 98))
    d.ellipse([ex - er + 6 * scale, ey - er + 6 * scale, ex + er, ey + er], fill=(14, 40, 78))
    # orbita
    d.arc([W * 0.05, H * 0.18, W * 1.25, H * 1.05], start=263, end=335, fill=ORANGE, width=3 * scale)
    # ISS
    draw_iss(d, W * 0.78, H * 0.30, W * 0.30)
    # testi
    title = font("bahnschrift.ttf", 58 * scale)
    sub = font("bahnschrift.ttf", 20 * scale)
    tx = 40 * scale
    d.text((tx, 52 * scale), "Assicuta", font=title, fill=WHITE)
    tw = d.textlength("Assicuta", font=title)
    d.text((tx + tw, 52 * scale), "ISS", font=title, fill=ORANGE)
    d.text((tx + 3 * scale, 128 * scale), "an ISS SSTV Receiver for Robot36", font=sub, fill=(190, 205, 225))
    # barre SSTV
    bx0, by0 = tx + 3 * scale, 168 * scale
    bw, bh = 34 * scale, 10 * scale
    for i, c in enumerate(BARS):
        d.rectangle([bx0 + i * bw, by0, bx0 + (i + 1) * bw - 2 * scale, by0 + bh], fill=c)
    d.text((bx0, by0 + bh + 10 * scale), "437.550 MHz FM  ·  Robot 36  ·  RTL-SDR", font=font("consola.ttf", 14 * scale),
           fill=(150, 170, 200))
    # fascia libera in basso per versione e stato del caricamento
    d.rectangle([0, H - 40 * scale, W, H], fill=(6, 12, 26))
    d.line([0, H - 40 * scale, W, H - 40 * scale], fill=(40, 60, 95), width=scale)
    return img.resize((w, h), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    big = make_icon(1024)
    icon = big.resize((256, 256), Image.LANCZOS)
    icon.save(os.path.join(OUT, "icona.png"))
    big.save(os.path.join(OUT, "icona.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    make_splash().save(os.path.join(OUT, "splash.png"))
    print("creati:", ", ".join(sorted(os.listdir(OUT))))


if __name__ == "__main__":
    main()
