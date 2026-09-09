import io
import json
import os
import random
import urllib.parse
import urllib.request

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from PIL import Image, ImageDraw, ImageFont


app = FastAPI(title="Generador de Citas y Wallpapers")


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

BASE_SIZE = 1920

WALLHAVEN_API_KEY = os.environ.get(
    "WALLHAVEN_API_KEY",
    "jJm5diseSPiDVIqvvE7aUS4fWwgJ0koW"
)

WALLHAVEN_TAGS = [
    "Japan",
    "nature",
    "space",
    "animals"
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ============================================================
# PROPORCIONES DISPONIBLES
#
# El lado mayor siempre será 1920 px.
#
# 1:1    -> 1920 x 1920
# 2:3    -> 1280 x 1920
# 3:2    -> 1920 x 1280
# 3:4    -> 1440 x 1920
# 4:5    -> 1536 x 1920
# 5:3    -> 1920 x 1152
# 16:9   -> 1920 x 1080
# 9:16   -> 1080 x 1920
# ============================================================

ASPECT_RATIOS = [
    (1, 1),
    (2, 3),
    (3, 2),
    (3, 4),
    (4, 5),
    (5, 3),
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
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "DejaVuSerif.ttf",
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
# WALLHAVEN
# ============================================================

def get_wallhaven_wallpaper():

    tag = random.choice(
        WALLHAVEN_TAGS
    )

    query = urllib.parse.urlencode(
        {
            "q": tag,
            "apikey": WALLHAVEN_API_KEY,
            "sorting": "random",
            "purity": "100",
        }
    )

    api_url = (
        "https://wallhaven.cc/api/v1/search?"
        + query
    )

    req = urllib.request.Request(
        api_url,
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

        results = data.get(
            "data",
            []
        )

        if results:

            return get_image_bytes(
                results[0]["path"]
            )

    raise RuntimeError(
        "No se encontraron resultados en Wallhaven."
    )


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
#
# La imagen se amplía hasta cubrir completamente
# el formato elegido y luego se recorta el sobrante.
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

    # --------------------------------------------------------
    # Imagen demasiado ancha
    # --------------------------------------------------------

    if source_ratio > target_ratio:

        new_height = target_height

        new_width = int(
            target_height
            * source_ratio
        )

    # --------------------------------------------------------
    # Imagen demasiado alta
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Recorte centrado
    # --------------------------------------------------------

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

    target_width, target_height = (
        get_random_dimensions()
    )

    providers = [
        get_wallhaven_wallpaper,
        get_bing_wallpaper,
    ]

    random.shuffle(
        providers
    )

    for provider in providers:

        try:

            img_data = provider()

            img = Image.open(
                io.BytesIO(img_data)
            ).convert("RGB")

            img = fit_wallpaper(
                img,
                target_width,
                target_height
            )

            return (
                img,
                target_width,
                target_height
            )

        except Exception:

            continue

    # --------------------------------------------------------
    # Fondo de emergencia
    # --------------------------------------------------------

    img = Image.new(
        "RGB",
        (
            target_width,
            target_height
        ),
        color=(40, 50, 60)
    )

    return (
        img,
        target_width,
        target_height
    )


# ============================================================
# CITA ALEATORIA
# ============================================================

def get_new_quote():

    return random.choice(
        CITAS_MEMORIA
    )


# ============================================================
# COLOR REPRESENTATIVO
#
# Equivalente al método utilizado en Variety:
#
# imagen -> 1x1 -> RGB
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
#
# Equivalente a Pango.WrapMode.WORD
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

    # --------------------------------------------------------
    # Igual que:
    #
    # sw * QUOTES_WIDTH / 100
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CITA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Altura de línea
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Igual que Variety:
    #
    # width = qwidth + 4*MARGIN
    # --------------------------------------------------------

    if QUOTES_WIDTH < 98:

        box_width = (
            qwidth
            + 4 * MARGIN
        )

    else:

        box_width = canvas_width

    # --------------------------------------------------------
    # FIRMA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Igual que Variety:
    #
    # height =
    #     qheight
    #     + aheight
    #     + 2.5*MARGIN
    # --------------------------------------------------------

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

def generate_composite_image(
    bg_image,
    quote_text,
    author_text
):

    canvas_width = bg_image.width
    canvas_height = bg_image.height

    # ========================================================
    # COLOR
    # ========================================================

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


    # ========================================================
    # LAYOUT
    # ========================================================

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


    # ========================================================
    # POSICIÓN HORIZONTAL
    #
    # Variety:
    #
    # hpos =
    # trimw
    # +
    # (sw-width) * HPos / 100
    #
    # Aquí la imagen ya está recortada,
    # por lo que trimw = 0.
    # ========================================================

    hpos = int(
        (
            canvas_width
            - box_width
        )
        * QUOTES_HPOS
        / 100
    )


    # ========================================================
    # POSICIÓN VERTICAL
    # ========================================================

    vpos = int(
        (
            canvas_height
            - box_height
        )
        * QUOTES_VPOS
        / 100
    )


    # ========================================================
    # CAPA DEL RECUADRO
    # ========================================================

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


    # ========================================================
    # OPACIDAD
    # ========================================================

    alpha = int(
        255
        * BG_OPACITY
        / 100
    )


    # ========================================================
    # RECUADRO
    # ========================================================

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


    # ========================================================
    # COMPONER
    # ========================================================

    result = Image.alpha_composite(
        bg_image.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(
        result
    )


    # ========================================================
    # TEXTO
    #
    # Igual que Variety:
    #
    # hpos + (width-qwidth)/2
    # ========================================================

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


    # ========================================================
    # CITA
    # ========================================================

    for line in wrapped_lines:

        # ----------------------------------------------------
        # Sombra
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Texto
        # ----------------------------------------------------

        draw.text(
            (
                int(text_x),
                int(text_y)
            ),
            line,
            font=font,
            fill=(
                255,
                255,
                255,
                255
            )
        )

        text_y += (
            line_height
            + line_spacing
        )


    # ========================================================
    # FIRMA
    #
    # A LA DERECHA
    # ========================================================

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

            # ------------------------------------------------
            # Sombra
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Firma
            # ------------------------------------------------

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
                fill=(
                    255,
                    255,
                    255,
                    255
                )
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
#
# Usada por el botón "Copiar la cita".
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

    headers = {
        "Content-Disposition": (
            "attachment; "
            "filename=wallpaper_cita.jpg"
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
