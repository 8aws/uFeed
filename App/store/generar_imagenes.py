"""Imágenes de la ficha de la App Store: cabecera 21:9 (3840x1646) y resultado de
búsqueda 3:2 (3840x2560), en español e inglés. Sin canal alfa, como exige Apple.
Uso (desde App/): python3 store/generar_imagenes.py"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ICONO = "assets/icon/ufeed_icon.png"
NEGRITA = "assets/fonts/AtkinsonHyperlegible-Bold.ttf"
NORMAL = "assets/fonts/AtkinsonHyperlegible-Regular.ttf"

TEXTOS = {
    "es": ("uFeed", ("Lee y escucha tus noticias,", "también sin conexión"),
           ("Artículo completo", "Voz natural", "Post radio", "Traducción")),
    "en": ("uFeed", ("Read and listen to your news,", "offline too"),
           ("Full articles", "Natural voice", "Post radio", "Translation")),
}


def fondo(w, h):
    """Azul noche (el fondo oscuro de la app) con un halo naranja detrás del icono."""
    g = Image.new("RGB", (w, h))
    px = g.load()
    a, b = (15, 23, 42), (30, 41, 82)
    for y in range(h):
        for x in range(w):
            t = (x / w) * 0.6 + (y / h) * 0.4
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return g


def icono(lado):
    im = Image.open(ICONO).convert("RGB").resize((lado, lado), Image.LANCZOS)
    m = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, lado - 1, lado - 1), radius=int(lado * 0.225), fill=255)
    return im, m


def componer(w, h, lado, tam_titulo, tam_sub, tam_chip, lang, nombre):
    titulo, sub, chips = TEXTOS[lang]
    base = fondo(w, h).convert("RGBA")
    ic, mask = icono(lado)
    cx, cy = w - lado - int(w * 0.08), (h - lado) // 2
    # halo naranja y sombra
    halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((cx - lado * 0.35, cy - lado * 0.35, cx + lado * 1.35, cy + lado * 1.35),
                                 fill=(242, 113, 28, 90))
    base = Image.alpha_composite(base, halo.filter(ImageFilter.GaussianBlur(lado // 4)))
    sombra = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((cx, cy + 40, cx + lado, cy + lado + 40),
                                             radius=int(lado * 0.225), fill=(0, 0, 0, 140))
    base = Image.alpha_composite(base, sombra.filter(ImageFilter.GaussianBlur(50)))
    base.paste(ic, (cx, cy), mask)

    f_t, f_s, f_c = (ImageFont.truetype(NEGRITA, tam_titulo), ImageFont.truetype(NORMAL, tam_sub),
                     ImageFont.truetype(NEGRITA, tam_chip))
    alto_chip = int(tam_chip * 2)
    x0 = int(w * 0.07)
    d = ImageDraw.Draw(base)
    # las etiquetas bajan de línea antes de llegar al icono
    limite, filas, fila, ancho = cx - int(w * 0.04), [], [], x0
    for texto in chips:
        cw = d.textlength(texto, font=f_c) + int(tam_chip * 1.2)
        if fila and ancho + cw > limite:
            filas.append(fila)
            fila, ancho = [], x0
        fila.append(texto)
        ancho += cw + int(tam_chip * 0.5)
    filas.append(fila)
    alto_filas = len(filas) * alto_chip + (len(filas) - 1) * int(tam_chip * 0.5)
    bloque = int(tam_titulo * 1.15) + int(tam_sub * 1.3) * len(sub) + int(tam_sub * 0.6) + alto_filas
    y = (h - bloque) // 2
    d.text((x0, y), titulo, font=f_t, fill="white")
    y += int(tam_titulo * 1.15)
    for linea in sub:
        d.text((x0, y), linea, font=f_s, fill=(203, 213, 225))
        y += int(tam_sub * 1.3)
    y += int(tam_sub * 0.6)
    capa = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    for fila in filas:
        x = x0
        for texto in fila:
            tw = d.textlength(texto, font=f_c)
            pad = int(tam_chip * 0.6)
            dc.rounded_rectangle((x, y, x + tw + 2 * pad, y + alto_chip), radius=alto_chip // 2,
                                 fill=(242, 113, 28, 60), outline=(251, 146, 60, 255), width=4)
            dc.text((x + pad, y + (alto_chip - tam_chip) / 2 - tam_chip * 0.08), texto, font=f_c, fill="white")
            x += tw + 2 * pad + int(tam_chip * 0.5)
        y += alto_chip + int(tam_chip * 0.5)
    base = Image.alpha_composite(base, capa)
    base.convert("RGB").save(nombre, "PNG", optimize=True)
    print(nombre, w, h)


for lang in ("es", "en"):
    componer(3840, 1646, 1150, 260, 104, 58, lang, f"store/cabecera_3840x1646_{lang}.png")
    componer(3840, 2560, 1450, 290, 120, 64, lang, f"store/busqueda_3840x2560_{lang}.png")
