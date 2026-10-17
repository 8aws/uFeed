"""Capturas de la App Store para iPad 13" con un título encima, a 2752x2064
(horizontal, uno de los tamaños que acepta App Store Connect).
Parte de capturas crudas del simulador (iPad Air 13", 2732x2048, cuenta de
invitado) en store/crudo_ipad/<lang>/<n>.png.
Uso (desde App/): python3 store/generar_capturas_ipad.py"""
import glob
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2752, 2064
NEGRITA = "assets/fonts/AtkinsonHyperlegible-Bold.ttf"
TITULOS = {
    "es": {
        "1_lista": ("Lista y artículo,", "lado a lado"),
        "2_mosaico": ("Mosaico, tarjetas o lista:", "tú eliges"),
        "3_escucha": ("Escucha tus noticias", "con voz natural"),
        "4_oscuro": ("También en modo oscuro,", "con la letra a tu medida"),
    },
    "en": {
        "1_lista": ("List and article,", "side by side"),
        "2_mosaico": ("Mosaic, cards or list:", "your choice"),
        "3_escucha": ("Listen to your news", "in a natural voice"),
        "4_oscuro": ("Dark mode too,", "with text sized for you"),
    },
}


def fondo(w, h):
    g = Image.new("RGB", (w, h))
    px = g.load()
    a, b = (15, 23, 42), (30, 41, 82)
    for y in range(h):
        for x in range(w):
            t = (x / w) * 0.4 + (y / h) * 0.6
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return g


def componer(lang):
    carpeta = f"store/capturas_ipad_13/{lang}"
    os.makedirs(carpeta, exist_ok=True)
    f = ImageFont.truetype(NEGRITA, 92)
    for ruta in sorted(glob.glob(f"store/crudo_ipad/{lang}/*.png")):
        nombre = os.path.basename(ruta)[:-4]
        l1, l2 = TITULOS[lang][nombre]
        base = fondo(W, H).convert("RGBA")
        d = ImageDraw.Draw(base)
        for i, linea in enumerate((l1, l2)):
            lw = d.textlength(linea, font=f)
            color = "white" if i == 0 else (251, 146, 60)
            d.text(((W - lw) / 2, 52 + i * 118), linea, font=f, fill=color)
        alto = H - 330 - 70
        cap = Image.open(ruta).convert("RGB")
        ancho = int(cap.width * alto / cap.height)
        cap = cap.resize((ancho, alto), Image.LANCZOS)
        radio = 46
        m = Image.new("L", cap.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, cap.width - 1, cap.height - 1), radius=radio, fill=255)
        x0, y0 = (W - cap.width) // 2, 330
        sombra = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle(
            (x0, y0 + 16, x0 + cap.width, y0 + cap.height + 16), radius=radio, fill=(0, 0, 0, 140)
        )
        base = Image.alpha_composite(base, sombra.filter(ImageFilter.GaussianBlur(26)))
        base.paste(cap, (x0, y0), m)
        out = f"{carpeta}/{nombre}.png"
        base.convert("RGB").save(out, "PNG", optimize=True)
        print(out)


for lang in ("es", "en"):
    componer(lang)
