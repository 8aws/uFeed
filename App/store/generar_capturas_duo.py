"""Capturas de la App Store para iPhone Duo con un título encima, al mismo
tamaño que las capturas crudas del simulador (tamaños que acepta App Store
Connect: 1398x2034 pantalla exterior; 2007x2853 y 2853x2007 interior).
Parte de store/crudo_duo/<posicion>/<lang>/<n>.png y escribe en
store/capturas_duo/<posicion>/<lang>/.
Uso (desde App/): python3 store/generar_capturas_duo.py"""
import glob
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

NEGRITA = "assets/fonts/AtkinsonHyperlegible-Bold.ttf"
TITULOS = {
    "exterior": {
        "es": {
            "1_lista": ("Tus noticias,", "en la pantalla exterior"),
            "2_articulo": ("El artículo completo,", "sin abrir el móvil"),
            "3_mosaico_oscuro": ("Mosaico y modo oscuro,", "a tu gusto"),
        },
        "en": {
            "1_lista": ("Your news,", "on the cover screen"),
            "2_articulo": ("The full article,", "without unfolding"),
            "3_mosaico_oscuro": ("Mosaic and dark mode,", "your way"),
        },
    },
    "interior_vertical": {
        "es": {
            "1_lista": ("Más espacio", "para tus fuentes"),
            "2_articulo": ("Lee con", "comodidad"),
            "3_mosaico_oscuro": ("Mosaico y modo oscuro,", "a tu gusto"),
        },
        "en": {
            "1_lista": ("More room", "for your feeds"),
            "2_articulo": ("Read in", "comfort"),
            "3_mosaico_oscuro": ("Mosaic and dark mode,", "your way"),
        },
    },
    "interior_horizontal": {
        "es": {
            "1_lista": ("Lista y artículo,", "lado a lado"),
            "2_mosaico_oscuro": ("Mosaico en modo oscuro,", "con el artículo al lado"),
        },
        "en": {
            "1_lista": ("List and article,", "side by side"),
            "2_mosaico_oscuro": ("Dark mosaic,", "with the article beside it"),
        },
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


def componer(pos, lang):
    carpeta = f"store/capturas_duo/{pos}/{lang}"
    os.makedirs(carpeta, exist_ok=True)
    for ruta in sorted(glob.glob(f"store/crudo_duo/{pos}/{lang}/*.png")):
        nombre = os.path.basename(ruta)[:-4]
        l1, l2 = TITULOS[pos][lang][nombre]
        cap = Image.open(ruta).convert("RGB")
        w, h = cap.size
        retrato = h > w
        fs = int(min(w, h) * (0.062 if retrato else 0.05))
        f = ImageFont.truetype(NEGRITA, fs)
        titulo_h = int(fs * 3.0)
        base = fondo(w, h).convert("RGBA")
        d = ImageDraw.Draw(base)
        for i, linea in enumerate((l1, l2)):
            lw = d.textlength(linea, font=f)
            color = "white" if i == 0 else (251, 146, 60)
            d.text(((w - lw) / 2, fs * 0.55 + i * fs * 1.3), linea, font=f, fill=color)
        margen = int(min(w, h) * 0.04)
        alto = h - titulo_h - margen
        ancho = int(w * alto / h)
        c = cap.resize((ancho, alto), Image.LANCZOS)
        radio = int(min(ancho, alto) * 0.045)
        m = Image.new("L", c.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, c.width - 1, c.height - 1), radius=radio, fill=255)
        x0, y0 = (w - ancho) // 2, titulo_h
        sombra = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle(
            (x0, y0 + 12, x0 + ancho, y0 + alto + 12), radius=radio, fill=(0, 0, 0, 140)
        )
        base = Image.alpha_composite(base, sombra.filter(ImageFilter.GaussianBlur(22)))
        base.paste(c, (x0, y0), m)
        out = f"{carpeta}/{nombre}.png"
        base.convert("RGB").save(out, "PNG", optimize=True)
        print(out, base.size)


for pos in TITULOS:
    for lang in ("es", "en"):
        componer(pos, lang)
