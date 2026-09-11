import io
import json
import os
import random
import re
import urllib.parse
import urllib.request
from html import unescape
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from PIL import Image, ImageDraw, ImageFont

import os


FONT_DIRECTORIES = [
    "/usr/share/fonts",
]


def get_system_fonts():

    fonts = []

    for base_dir in FONT_DIRECTORIES:

        if not os.path.isdir(base_dir):
            continue

        for root, dirs, files in os.walk(base_dir):

            for filename in files:

                if not filename.lower().endswith(
                    (".ttf", ".otf", ".ttc")
                ):
                    continue

                path = os.path.join(
                    root,
                    filename
                )

                fonts.append(path)

    fonts.sort(
        key=lambda path: os.path.basename(path).lower()
    )

    return fonts


system_fonts = get_system_fonts()

print(
    f"INFO: Fuentes encontradas: {len(system_fonts)}"
)

for font in system_fonts:
    print(font)

app = FastAPI(
    title="Generador de Citas y Wallpapers"
)


@app.get("/fonts")
def fonts():

    return {
        "fonts": get_system_fonts()
    }

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

BASE_SIZE = 1920

WALLHAVEN_API_KEY = os.environ.get(
    "WALLHAVEN_API_KEY",
    "jJm5diseSPiDVIqvvE7aUS4fWwgJ0koW"
)

WALLHAVEN_TAGS = [
    "nature",
    "landscape",
    "mountains",
    "forest",
    "ocean",
    "animals",
    "space",
    "Japan",
    "architecture",
    "city",
]

RECENT_WALLHAVEN_IDS = []
MAX_RECENT_WALLHAVEN = 40

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ============================================================
# TIMELESS TODAY
#
# Las citas se cargan UNA SOLA VEZ al iniciar la aplicación.
# Después se mantienen en memoria.
# ============================================================

API_BASE = (
    "https://api3.timelesstoday.io/"
    "v2/cms/products/es-ES/group/2/12"
)

TIMESLESS_LIMIT = 12


# ============================================================
# PROPORCIONES DISPONIBLES
#
# El lado mayor siempre será 1920 px.
#
# 1:1    -> 1920 x 1920
# 2:3    -> 1280 x 1920
# 3:2    -> 1920 x 1280
# 3:4    -> 1440 x 1920
# 4:3    -> 1920 x 1440
# 4:5    -> 1536 x 1920
# 5:4    -> 1920 x 1536
# 5:3    -> 1920 x 1152
# 3:5    -> 1152 x 1920
# 16:9   -> 1920 x 1080
# 9:16   -> 1080 x 1920
# ============================================================

ASPECT_RATIOS = [
    (1, 1),
    (2, 3),
    (3, 2),
    (3, 4),
    (4, 3),
    (4, 5),
    (5, 4),
    (5, 3),
    (3, 5),
    (16, 9),
    (9, 16),
]


def get_random_dimensions():

    ratio_w, ratio_h = random.choice(
        ASPECT_RATIOS
    )

    if ratio_w >= ratio_h:

        width = BASE_SIZE

        height = int(
            BASE_SIZE
            * ratio_h
            / ratio_w
        )

    else:

        height = BASE_SIZE

        width = int(
            BASE_SIZE
            * ratio_w
            / ratio_h
        )

    return width, height


# ============================================================
# PARÁMETROS DE COMPOSICIÓN
#
# Basados en cita-variety.py
# ============================================================

FONT_SIZE = 42

BG_OPACITY = 55

TEXT_SHADOW = True

QUOTES_WIDTH = 70
QUOTES_HPOS = 100
QUOTES_VPOS = 40

MARGIN = 30


# ============================================================
# CITAS DE RESPALDO
#
# Se utilizan solamente si TimelessToday no puede cargar
# las citas al iniciar la aplicación.
# ============================================================

CITAS_MEMORIA = [
    (
        "La paz es la constante dentro de ti, no el evento que ocurre a tu alrededor.",
        "Prem Rawat",
    ),
    (
        "Lo que buscas está dentro de ti; solo necesitas la oportunidad de escucharlo.",
        "Prem Rawat",
    ),
    (
        "El regalo de la vida ya te ha sido otorgado. Aprécialo día a día.",
        "Prem Rawat",
    ),
    (
        "Siente la plenitud en tu corazón antes de buscar la satisfacción afuera.",
        "Prem Rawat",
    ),
    (
        "La serenidad no es ausencia de ruido, es presencia de claridad interior.",
        "Prem Rawat",
    ),
    (
        "Cada día, puedes aprender; cada día, puedes crecer; cada día, puedes entender.",
        "Prem Rawat",
    ),
]


# ============================================================
# COLECCIÓN DE CITAS
#
# Aquí se almacenan TODAS las citas obtenidas de la API.
# ============================================================

ALL_QUOTES = []


# ============================================================
# ESTADO
# ============================================================

STATE = {
    "current_image": None,
    "current_quote": None,
    "current_author": None,
    "current_width": None,
    "current_height": None,
}


# ============================================================
# FUENTE
# ============================================================

def get_quote_font():

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ]

    for filename in candidates:

        try:

            return ImageFont.truetype(
                filename,
                FONT_SIZE
            )

        except OSError:

            continue

    return ImageFont.load_default()


# ============================================================
# DESCARGAR BYTES
# ============================================================

def get_image_bytes(url):

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=15
    ) as resp:

        return resp.read()


# ============================================================
# TIMELESS TODAY
# HACER PETICIÓN
# ============================================================

def hacer_peticion(offset):

    url = f"{API_BASE}/{offset}"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://timelesstoday.tv/",
        "Origin": "https://timelesstoday.tv",
    }

    req = urllib.request.Request(
        url,
        headers=headers
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=15
        ) as resp:

            return json.loads(
                resp.read().decode("utf-8")
            )

    except Exception as e:

        print(
            "ERROR TimelessToday:",
            e
        )

        return None


# ============================================================
# PROCESAR EVENTO TIMELESS TODAY
#
# Mantiene las mismas reglas de limpieza de
# citas_timelesstoday.py
# ============================================================

def procesar_evento(evento):

    raw_cita = evento.get(
        "tt_one_line_quote"
    )

    if not raw_cita:

        return None

    # --------------------------------------------------------
    # 1. Limpieza inicial de HTML y espacios
    # --------------------------------------------------------

    texto = unescape(
        str(raw_cita)
    )

    texto = re.sub(
        r"<[^>]+>",
        "",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    ).strip()

    # --------------------------------------------------------
    # 2. Extraer "Prem Rawat" y fecha/lugar si vienen
    # dentro de la propia cita
    # --------------------------------------------------------

    lugar_fecha = None

    match_firma = re.search(
        r"[\s–\-—]*Prem\s+Rawat(?:,\s*(.+))?$",
        texto,
        flags=re.IGNORECASE
    )

    if match_firma:

        texto = texto[
            :match_firma.start()
        ].strip()

        if match_firma.group(1):

            lugar_fecha = (
                match_firma.group(1)
                .strip()
            )

    # --------------------------------------------------------
    # 3. Si no venía fecha/lugar dentro del texto,
    # usamos el nombre del evento
    # --------------------------------------------------------

    if not lugar_fecha:

        nombre_evento = evento.get(
            "tt_name"
        )

        if (
            nombre_evento
            and nombre_evento.strip()
        ):

            lugar_fecha = (
                nombre_evento.strip()
            )

    # --------------------------------------------------------
    # 4. Limpiar comillas basura
    # --------------------------------------------------------

    texto = re.sub(
        r'^["“”’\']+|["“”’\']+$',
        "",
        texto
    ).strip()

    texto = re.sub(
        r'["”’\']+\s*\.?$',
        "",
        texto
    ).strip()

    # --------------------------------------------------------
    # Asegurar punto final
    # --------------------------------------------------------

    if (
        texto
        and not texto.endswith(
            (".", "!", "?", "…")
        )
    ):

        texto += "."

    if not texto:

        return None

    # --------------------------------------------------------
    # 5. Formatear
    # --------------------------------------------------------

    if lugar_fecha:

        lugar_fecha = re.sub(
            r'^["“”’\']+|["“”’\']+$',
            "",
            lugar_fecha
        ).strip()

        lugar_fecha = (
            lugar_fecha.rstrip(".")
        )

        return (
            f'“{texto}” — Prem Rawat, '
            f'({lugar_fecha})'
        )

    else:

        return (
            f'“{texto}” — Prem Rawat'
        )


# ============================================================
# CARGAR TODAS LAS CITAS DE TIMELESS TODAY
#
# Esta función se ejecuta solamente al iniciar la aplicación.
# ============================================================

def load_all_quotes():

    global ALL_QUOTES

    print(
        "INFO: Cargando citas de TimelessToday..."
    )

    primera_pagina = hacer_peticion(0)

    if not primera_pagina:

        print(
            "WARNING: No se pudo obtener "
            "la primera página de TimelessToday."
        )

        ALL_QUOTES = list(
            CITAS_MEMORIA
        )

        return

    total_eventos = (
        primera_pagina
        .get("filter", {})
        .get("count", 0)
    )

    if total_eventos == 0:

        print(
            "WARNING: TimelessToday "
            "no devolvió eventos."
        )

        ALL_QUOTES = list(
            CITAS_MEMORIA
        )

        return

    print(
        f"INFO: TimelessToday informa "
        f"{total_eventos} eventos."
    )

    offsets = list(
        range(
            0,
            total_eventos,
            TIMESLESS_LIMIT
        )
    )

    citas = []

    for offset in offsets:

        # ----------------------------------------------------
        # La página 0 ya la tenemos.
        # ----------------------------------------------------

        if offset == 0:

            datos = primera_pagina

        else:

            datos = hacer_peticion(
                offset
            )

        if not datos:

            print(
                f"WARNING: No se pudo cargar "
                f"offset {offset}."
            )

            continue

        eventos = datos.get(
            "data",
            []
        )

        for evento in eventos:

            cita = procesar_evento(
                evento
            )

            if cita:

                citas.append(
                    cita
                )

    # --------------------------------------------------------
    # Eliminar duplicados conservando orden
    # --------------------------------------------------------

    citas_unicas = list(
        dict.fromkeys(citas)
    )

    if citas_unicas:

        ALL_QUOTES = citas_unicas

        print(
            "INFO: Citas cargadas: "
            f"{len(ALL_QUOTES)}"
        )

    else:

        print(
            "WARNING: No se pudo procesar "
            "ninguna cita de TimelessToday."
        )

        ALL_QUOTES = list(
            CITAS_MEMORIA
        )


# ============================================================
# CITA ALEATORIA
#
# IMPORTANTE:
#
# NO consulta Internet.
#
# Simplemente elige una de TODAS las citas que fueron
# cargadas al iniciar la aplicación.
# ============================================================

def get_new_quote():

    if not ALL_QUOTES:

        return random.choice(
            CITAS_MEMORIA
        )

    quote = random.choice(
        ALL_QUOTES
    )

    # --------------------------------------------------------
    # Las citas de TimelessToday ya vienen completas como:
    #
    # “texto” — Prem Rawat, lugar/fecha
    #
    # Aquí las separamos para que el resto de app.py
    # continúe funcionando exactamente igual.
    # --------------------------------------------------------

    match = re.match(
        r'^“(.*)”\s+—\s+Prem\s+Rawat(?:,\s*(.*))?$',
        quote,
        flags=re.DOTALL
    )

    if match:

        texto = f"“{match.group(1)}”"

        autor = "Prem Rawat"

        if match.group(2):

            autor += ", " + match.group(2)

        return (
            texto,
            autor
        )

    # --------------------------------------------------------
    # Respaldo por si alguna cita no coincide con el formato.
    # --------------------------------------------------------

    return (
        quote,
        "Prem Rawat"
    )


# ============================================================
# WALLHAVEN
# ============================================================

def get_wallhaven_wallpaper():
    tag = random.choice(WALLHAVEN_TAGS)

    query = urllib.parse.urlencode({
        "q": tag,
        "apikey": WALLHAVEN_API_KEY,
        "sorting": "random",
        "purity": "100",
        "categories": "100",
    })

    api_url = "https://wallhaven.cc/api/v1/search?" + query

    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": USER_AGENT}
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results = data.get("data", [])

    if not results:
        raise RuntimeError("No se encontraron resultados en Wallhaven.")

    # Preferir imágenes que no hayan aparecido recientemente.
    disponibles = [
        item for item in results
        if item.get("id") not in RECENT_WALLHAVEN_IDS
    ]

    if not disponibles:
        disponibles = results

    elegido = random.choice(disponibles)

    wallpaper_id = elegido.get("id")

    if wallpaper_id:
        RECENT_WALLHAVEN_IDS.append(wallpaper_id)

        if len(RECENT_WALLHAVEN_IDS) > MAX_RECENT_WALLHAVEN:
            del RECENT_WALLHAVEN_IDS[
                :len(RECENT_WALLHAVEN_IDS) - MAX_RECENT_WALLHAVEN
            ]

    return get_image_bytes(elegido["path"])


# ============================================================
# BING
# ============================================================

def get_bing_wallpaper():

    url = (
        "https://www.bing.com/"
        "HPImageArchive.aspx?"
        "format=js&"
        "idx=0&"
        "n=1&"
        "mkt=en-US"
    )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=10
    ) as resp:

        data = json.loads(
            resp.read().decode("utf-8")
        )

        img_url = (
            "https://www.bing.com"
            + data["images"][0]["url"]
        )

        return get_image_bytes(
            img_url
        )


# ============================================================
# RECORTE PROPORCIONAL
#
# NO deforma la imagen.
# ============================================================

def fit_wallpaper(
    image,
    target_width,
    target_height
):

    image = image.convert(
        "RGB"
    )

    iw, ih = image.size

    source_ratio = iw / ih

    target_ratio = (
        target_width
        / target_height
    )

    if source_ratio > target_ratio:

        new_height = target_height

        new_width = int(
            target_height
            * source_ratio
        )

    else:

        new_width = target_width

        new_height = int(
            target_width
            / source_ratio
        )

    image = image.resize(
        (
            new_width,
            new_height
        ),
        Image.Resampling.LANCZOS
    )

    left = max(
        0,
        (
            new_width
            - target_width
        ) // 2
    )

    top = max(
        0,
        (
            new_height
            - target_height
        ) // 2
    )

    image = image.crop(
        (
            left,
            top,
            left + target_width,
            top + target_height
        )
    )

    return image


# ============================================================
# OBTENER WALLPAPER ALEATORIO
# ============================================================

def fetch_random_background():
    target_width, target_height = get_random_dimensions()

    # Wallhaven es la fuente principal.
    try:
        img_data = get_wallhaven_wallpaper()

        img = Image.open(
            io.BytesIO(img_data)
        ).convert("RGB")

        img = fit_wallpaper(
            img,
            target_width,
            target_height
        )

        return img, target_width, target_height

    except Exception:
        pass

    # Bing queda solamente como respaldo.
    try:
        img_data = get_bing_wallpaper()

        img = Image.open(
            io.BytesIO(img_data)
        ).convert("RGB")

        img = fit_wallpaper(
            img,
            target_width,
            target_height
        )

        return img, target_width, target_height

    except Exception:
        pass

    # Último respaldo.
    img = Image.new(
        "RGB",
        (target_width, target_height),
        color=(40, 50, 60)
    )

    return img, target_width, target_height


# ============================================================
# COLOR REPRESENTATIVO
# ============================================================

def get_image_representative_color(
    image
):

    small_img = image.resize(
        (1, 1),
        Image.Resampling.LANCZOS
    )

    return small_img.getpixel(
        (0, 0)
    )


# ============================================================
# MEDICIÓN DE TEXTO
# ============================================================

def text_width(
    draw,
    text,
    font
):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    return (
        bbox[2]
        - bbox[0]
    )


def text_height(
    draw,
    text,
    font
):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    return (
        bbox[3]
        - bbox[1]
    )


# ============================================================
# WRAP DE TEXTO
# ============================================================

def wrap_text(
    text,
    font,
    max_width,
    draw
):

    words = text.split()

    lines = []

    current = ""

    for word in words:

        if not current:

            test = word

        else:

            test = (
                current
                + " "
                + word
            )

        if text_width(
            draw,
            test,
            font
        ) <= max_width:

            current = test

        else:

            if current:

                lines.append(
                    current
                )

            current = word

    if current:

        lines.append(
            current
        )

    return lines


# ============================================================
# PREPARAR LAYOUT
# ============================================================

def prepare_quote_layout(
    quote,
    author,
    canvas_width,
    canvas_height
):

    font = get_quote_font()

    dummy = Image.new(
        "RGB",
        (
            canvas_width,
            canvas_height
        )
    )

    draw = ImageDraw.Draw(
        dummy
    )

    initial_width = max(
        200,
        canvas_width
        * QUOTES_WIDTH
        // 100
    )

    max_text_width = (
        initial_width
        - 4 * MARGIN
    )

    wrapped_lines = wrap_text(
        quote,
        font,
        max_text_width,
        draw
    )

    if wrapped_lines:

        qwidth = max(
            text_width(
                draw,
                line,
                font
            )
            for line in wrapped_lines
        )

    else:

        qwidth = 0

    bbox = draw.textbbox(
        (0, 0),
        "Ag",
        font=font
    )

    line_height = (
        bbox[3]
        - bbox[1]
    )

    line_spacing = 5

    if wrapped_lines:

        qheight = (
            len(wrapped_lines)
            * line_height
            +
            max(
                0,
                len(wrapped_lines) - 1
            )
            * line_spacing
        )

    else:

        qheight = 0

    if QUOTES_WIDTH < 98:

        box_width = (
            qwidth
            + 4 * MARGIN
        )

    else:

        box_width = canvas_width

    author_lines = []

    aheight = 0

    if author:

        author_text = (
            "— "
            + author
        )

        author_lines = wrap_text(
            author_text,
            font,
            box_width
            - 4 * MARGIN,
            draw
        )

        if author_lines:

            aheight = (
                len(author_lines)
                * line_height
            )

    box_height = (
        qheight
        + aheight
        + int(
            2.5 * MARGIN
        )
    )

    return (
        font,
        wrapped_lines,
        qwidth,
        qheight,
        author_lines,
        aheight,
        box_width,
        box_height,
        line_height,
        line_spacing,
    )


# ============================================================
# GENERAR IMAGEN COMPUESTA
# ============================================================

def get_text_color(image):
    """
    Determina si conviene texto claro u oscuro
    según la luminosidad del fondo.
    """

    small = image.resize((40, 40), Image.Resampling.LANCZOS)

    pixels = list(small.getdata())

    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)

    luminance = (
        0.2126 * r +
        0.7152 * g +
        0.0722 * b
    )

    if luminance >= 145:
        return (
            (20, 20, 20, 255),
            (255, 255, 255, 190)
        )

    return (
        (255, 255, 255, 255),
        (0, 0, 0, 210)
    )

def generate_composite_image(
    bg_image,
    quote_text,
    author_text
):

    canvas_width = bg_image.width
    canvas_height = bg_image.height

    bg_color = (
        get_image_representative_color(
            bg_image
        )
    )

    r, g, b = bg_color

    print(
        "INFO: Color representativo: "
        f"RGB {r}, {g}, {b}"
    )

    (
        font,
        wrapped_lines,
        qwidth,
        qheight,
        author_lines,
        aheight,
        box_width,
        box_height,
        line_height,
        line_spacing,
    ) = prepare_quote_layout(
        quote_text,
        author_text,
        canvas_width,
        canvas_height
    )

    hpos = int(
        (
            canvas_width
            - box_width
        )
        * QUOTES_HPOS
        / 100
    )

    vpos = int(
        (
            canvas_height
            - box_height
        )
        * QUOTES_VPOS
        / 100
    )

    overlay = Image.new(
        "RGBA",
        (
            canvas_width,
            canvas_height
        ),
        (0, 0, 0, 0)
    )

    draw_overlay = ImageDraw.Draw(
        overlay
    )

    alpha = int(
        255
        * BG_OPACITY
        / 100
    )

    draw_overlay.rectangle(
        [
            hpos,
            vpos,
            hpos + box_width,
            vpos + box_height
        ],
        fill=(
            r,
            g,
            b,
            alpha
        )
    )

    result = Image.alpha_composite(
        bg_image.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(
        result
    )

    text_fill, text_stroke = get_text_color(result)

    text_x = (
        hpos
        + (
            box_width
            - qwidth
        )
        / 2
    )

    text_y = (
        vpos
        + MARGIN
    )

    for line in wrapped_lines:

        if TEXT_SHADOW:

            draw.text(
                (
                    int(text_x + 2),
                    int(text_y + 2)
                ),
                line,
                font=font,
                fill=(
                    0,
                    0,
                    0,
                    51
                )
            )

        draw.text(
            (
                int(text_x),
                int(text_y)
            ),
            line,
            font=font,
            fill=text_fill,
            stroke_width=2,
            stroke_fill=text_stroke
        )

        text_y += (
            line_height
            + line_spacing
        )

    if author_lines:

        author_y = (
            vpos
            + MARGIN
            + qheight
            + MARGIN / 2
        )

        author_layout_width = (
            box_width
            - 4 * MARGIN
        )

        author_x = (
            hpos
            + (
                box_width
                - qwidth
            )
            / 2
        )

        for author_line in author_lines:

            author_w = text_width(
                draw,
                author_line,
                font
            )

            author_draw_x = (
                author_x
                + author_layout_width
                - author_w
            )

            if TEXT_SHADOW:

                draw.text(
                    (
                        int(
                            author_draw_x
                            + 2
                        ),
                        int(
                            author_y
                            + 2
                        )
                    ),
                    author_line,
                    font=font,
                    fill=(
                        0,
                        0,
                        0,
                        51
                    )
                )

            draw.text(
                (
                    int(
                        author_draw_x
                    ),
                    int(
                        author_y
                    )
                ),
                author_line,
                font=font,
                fill=text_fill,
                stroke_width=2,
                stroke_fill=text_stroke
            )

            author_y += line_height

    return result


# ============================================================
# ASEGURAR ESTADO
# ============================================================

def ensure_state():

    if STATE["current_image"] is None:

        (
            image,
            width,
            height
        ) = fetch_random_background()

        STATE["current_image"] = image
        STATE["current_width"] = width
        STATE["current_height"] = height

    if STATE["current_quote"] is None:

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a


# ============================================================
# RENDER IMAGE
# ============================================================

@app.get("/render-image")
def render_image():

    ensure_state()

    composite = generate_composite_image(
        STATE["current_image"],
        STATE["current_quote"],
        STATE["current_author"],
    )

    buf = io.BytesIO()

    composite.convert(
        "RGB"
    ).save(
        buf,
        format="JPEG",
        quality=95
    )

    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store"
        }
    )


# ============================================================
# INFORMACIÓN DE LA CITA
# ============================================================

@app.get("/quote")
def get_quote():

    ensure_state()

    text = STATE["current_quote"]

    author = STATE["current_author"]

    full_text = (
        f"“{text}”\n"
        f"— {author}"
    )

    return JSONResponse(
        {
            "quote": text,
            "author": author,
            "text": full_text,
        }
    )


# ============================================================
# CAMBIAR IMAGEN / CITA / AMBAS
# ============================================================

@app.get("/action/{action_type}")
def handle_action(
    action_type: str
):

    if action_type == "change_image":

        (
            image,
            width,
            height
        ) = fetch_random_background()

        STATE["current_image"] = image
        STATE["current_width"] = width
        STATE["current_height"] = height

    elif action_type == "change_quote":

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a

    elif action_type == "change_both":

        (
            image,
            width,
            height
        ) = fetch_random_background()

        STATE["current_image"] = image
        STATE["current_width"] = width
        STATE["current_height"] = height

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a

    return {
        "status": "ok",
        "width": STATE["current_width"],
        "height": STATE["current_height"],
    }


# ============================================================
# DESCARGAR IMAGEN + CITA
# ============================================================

@app.get("/download")
def download_wallpaper():

    ensure_state()

    composite = generate_composite_image(
        STATE["current_image"],
        STATE["current_quote"],
        STATE["current_author"],
    )

    buf = io.BytesIO()

    composite.convert(
        "RGB"
    ).save(
        buf,
        format="JPEG",
        quality=100
    )

    buf.seek(0)

    nombre_archivo = (
        "cita_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        + ".jpg"
    )
    
    headers = {
        "Content-Disposition": (
            "attachment; "
            f"filename={nombre_archivo}"
        )
    }

    return StreamingResponse(
        buf,
        media_type="image/jpeg",
        headers=headers
    )


# ============================================================
# DESCARGAR SOLO LA IMAGEN
# ============================================================

@app.get("/download-image")
def download_image():

    ensure_state()

    buf = io.BytesIO()

    STATE["current_image"].convert(
        "RGB"
    ).save(
        buf,
        format="JPEG",
        quality=100
    )

    buf.seek(0)

    headers = {
        "Content-Disposition": (
            "attachment; "
            "filename=wallpaper.jpg"
        )
    }

    return StreamingResponse(
        buf,
        media_type="image/jpeg",
        headers=headers
    )


# ============================================================
# INTERFAZ WEB
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def index():

    return """
<!DOCTYPE html>

<html lang="es">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Citas de Prem Rawat</title>

    <style>

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {

            font-family:
                system-ui,
                -apple-system,
                sans-serif;

            background-color: #0f172a;

            color: #f8fafc;

            display: flex;

            flex-direction: column;

            align-items: center;

            justify-content: center;

            min-height: 100vh;

            padding: 20px;
        }

        .container {

            max-width: 1000px;

            width: 100%;

            text-align: center;
        }

        .preview-card {

            position: relative;

            width: 100%;

            border-radius: 12px;

            overflow: hidden;

            box-shadow:
                0 20px 25px -5px
                rgba(0,0,0,0.5);

            background-color: #1e293b;

            margin-bottom: 25px;

            display: flex;

            justify-content: center;

            align-items: center;
        }

        .preview-card img {

            width: 100%;

            height: auto;

            max-height: 75vh;

            object-fit: contain;

            display: block;
        }

        .loader {

            position: absolute;

            top: 0;
            left: 0;
            right: 0;
            bottom: 0;

            background:
                rgba(15, 23, 42, 0.7);

            display: flex;

            align-items: center;

            justify-content: center;

            font-size: 1.2rem;

            font-weight: 600;

            opacity: 0;

            pointer-events: none;

            transition:
                opacity 0.2s ease;
        }

        .loader.active {

            opacity: 1;

            pointer-events: all;
        }

        .btn-group {

            display: flex;

            gap: 12px;

            justify-content: center;

            flex-wrap: wrap;
        }

        button,
        a.btn {

            background-color: #334155;

            color: #ffffff;

            border: 1px solid #475569;

            padding: 12px 20px;

            font-size: 0.95rem;

            font-weight: 600;

            border-radius: 8px;

            cursor: pointer;

            transition:
                all 0.2s ease;

            text-decoration: none;

            display: inline-flex;

            align-items: center;

            justify-content: center;

            gap: 8px;
        }

        button:hover,
        a.btn:hover {

            background-color: #475569;

            transform:
                translateY(-2px);
        }

        button.primary,
        a.btn.primary {

            background-color: #2563eb;

            border-color: #3b82f6;
        }

        button.primary:hover,
        a.btn.primary:hover {

            background-color: #1d4ed8;
        }

        .copy-success {

            position: fixed;

            bottom: 25px;

            left: 50%;

            transform:
                translateX(-50%);

            background:
                rgba(30, 41, 59, 0.96);

            color: white;

            padding:
                12px 20px;

            border-radius: 8px;

            font-weight: 600;

            opacity: 0;

            pointer-events: none;

            transition:
                opacity 0.25s ease;
        }

        .copy-success.show {

            opacity: 1;
        }

        @media (max-width: 600px) {

            body {

                padding: 10px;
            }

            .btn-group {

                gap: 8px;
            }

            button,
            a.btn {

                padding:
                    10px 12px;

                font-size:
                    0.85rem;
            }

        }

    </style>

</head>

<body>

    <div class="container">

        <h1
            style="
                margin-bottom: 20px;
            "
        >
            🖼️ Citas de Prem
        </h1>

        <div class="preview-card">

            <img
                id="wallpaper"
                src="/render-image"
                alt="Wallpaper con cita"
            >

            <div
                id="loader"
                class="loader"
            >
                Procesando...
            </div>

        </div>

        <div class="btn-group">

            <button
                onclick="
                    triggerAction('change_image')
                "
            >
                🖼️ Cambiar de imagen
            </button>

            <button
                onclick="
                    triggerAction('change_quote')
                "
            >
                ✍️ Cambiar de cita
            </button>

            <button
                onclick="
                    triggerAction('change_both')
                "
            >
                🔀 Cambiar ambas
            </button>

            <a
                href="/download"
                class="btn primary"
                target="_blank"
            >
                📥 Descargar
            </a>

            <a
                href="/download-image"
                class="btn"
            >
                📥 Descargar solo la imagen
            </a>

            <button
                onclick="
                    copyQuote()
                "
            >
                📋 Copiar la cita
            </button>

        </div>

    </div>

    <div
        id="copy-success"
        class="copy-success"
    >
        ✓ Cita copiada
    </div>

    <script>

        // ====================================================
        // CAMBIAR IMAGEN / CITA / AMBAS
        // ====================================================

        async function triggerAction(
            actionType
        ) {

            const loader =
                document.getElementById(
                    'loader'
                );

            const img =
                document.getElementById(
                    'wallpaper'
                );

            loader.classList.add(
                'active'
            );

            try {

                await fetch(
                    '/action/'
                    + actionType
                );

                const newSrc =
                    '/render-image?t='
                    + new Date().getTime();

                img.onload = () => {

                    loader.classList.remove(
                        'active'
                    );

                };

                img.src = newSrc;

            } catch (e) {

                loader.classList.remove(
                    'active'
                );

                alert(
                    'Error actualizando la imagen'
                );

            }

        }


        // ====================================================
        // COPIAR CITA
        // ====================================================

        async function copyQuote() {

            try {

                const response =
                    await fetch(
                        '/quote'
                    );

                const data =
                    await response.json();

                await navigator.clipboard.writeText(
                    data.text
                );

                const message =
                    document.getElementById(
                        'copy-success'
                    );

                message.classList.add(
                    'show'
                );

                setTimeout(
                    () => {

                        message.classList.remove(
                            'show'
                        );

                    },
                    1800
                );

            } catch (error) {

                alert(
                    'No se pudo copiar la cita.'
                );

            }

        }

    </script>

</body>

</html>
"""


# ============================================================
# CARGAR CITAS AL INICIAR
#
# Se ejecuta antes de aceptar peticiones.
# ============================================================

load_all_quotes()


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
