"""Capturas de la App Store con un título encima, a 1206x2622 (iPhone 6,3", el
tamaño que pide App Store Connect) y 1320x2868 (6,9").
Parte de capturas crudas del simulador (cuenta demo) en store/crudo/<lang>/<n>.png.
Uso (desde App/): python3 store/generar_capturas.py"""
import glob
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TAMANOS = [(1206, 2622, "capturas_iphone_6.3"), (1320, 2868, "capturas_iphone_6.9")]
NEGRITA = "assets/fonts/AtkinsonHyperlegible-Bold.ttf"
TITULOS = {
    "es": {
        "1_lista": ("Tus webs y blogs favoritos,", "de un vistazo"),
        "2_articulo": ("El artículo completo,", "aunque el feed dé un extracto"),
        "3_escucha": ("Escucha tus noticias", "con voz natural"),
        "4_radio": ("Post radio: tus noticias", "una tras otra"),
        "5_traduccion": ("Tradúcelas y resúmelas", "en tu idioma"),
        "6_oscuro": ("Accesible y sin conexión,", "también en modo oscuro"),
    },
    "en": {
        "1_lista": ("Your favourite sites and blogs,", "at a glance"),
        "2_articulo": ("Clean reading,", "no ads, no distractions"),
        "3_escucha": ("Listen to your news", "in a natural voice"),
        "4_radio": ("Post radio: your news,", "one after another"),
        "5_traduccion": ("Translate and summarize", "in your language"),
        "6_oscuro": ("Accessible and offline,", "dark mode too"),
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


def componer(w, h, carpeta, lang):
    os.makedirs(f"store/{carpeta}/{lang}", exist_ok=True)
    k0 = w / 1320
    f = ImageFont.truetype(NEGRITA, int(80 * k0))
    for ruta in sorted(glob.glob(f"store/crudo/{lang}/*.png")):
        nombre = os.path.basename(ruta)[:-4]
        l1, l2 = TITULOS[lang][nombre]
        base = fondo(w, h).convert("RGBA")
        d = ImageDraw.Draw(base)
        for i, linea in enumerate((l1, l2)):
            if linea:
                lw = d.textlength(linea, font=f)
                color = "white" if i == 0 else (251, 146, 60)
                d.text(((w - lw) / 2, int(150 * k0) + i * int(108 * k0)), linea, font=f, fill=color)
        k = 0.86
        cap = Image.open(ruta).convert("RGB").resize((int(w * k), int(h * k)), Image.LANCZOS)
        m = Image.new("L", cap.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, cap.width - 1, cap.height + 200), radius=int(90 * k0), fill=255)
        x0, y0 = (w - cap.width) // 2, int(430 * k0)
        sombra = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle((x0, y0 + 20, x0 + cap.width, y0 + cap.height + 220),
                                                 radius=int(90 * k0), fill=(0, 0, 0, 130))
        base = Image.alpha_composite(base, sombra.filter(ImageFilter.GaussianBlur(30)))
        base.paste(cap, (x0, y0), m)
        out = f"store/{carpeta}/{lang}/{nombre}.png"
        base.convert("RGB").save(out, "PNG", optimize=True)
        print(out)


for w, h, carpeta in TAMANOS:
    for lang in ("es", "en"):
        componer(w, h, carpeta, lang)
