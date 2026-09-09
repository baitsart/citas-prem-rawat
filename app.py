import io
import json
import os
import random
import urllib.parse
import urllib.request

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from PIL import Image, ImageDraw, ImageFont


app = FastAPI(title="Generador de Citas y Wallpapers")


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

WIDTH = 1920
HEIGHT = 1080

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
# PARÁMETROS IGUALES A cita-variety.py
# ============================================================

FONT_SIZE = 30

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
}


# ============================================================
# FUENTES
# ============================================================

def get_quote_font():
    """
    Equivalente aproximado a:

        Pango.FontDescription("Serif 30")

    Se intenta primero DejaVu Serif, que está disponible
    habitualmente en los servidores Linux.
    """

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
# DESCARGA DE IMÁGENES
# ============================================================

def get_image_bytes(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


# ============================================================
# WALLHAVEN
# ============================================================

def get_wallhaven_wallpaper():

    tag = random.choice(WALLHAVEN_TAGS)

    query = urllib.parse.urlencode(
        {
            "q": tag,
            "apikey": WALLHAVEN_API_KEY,
            "sorting": "random",
            "purity": "100",
            "ratios": "16x9,16x10",
        }
    )

    api_url = (
        "https://wallhaven.cc/api/v1/search?"
        + query
    )

    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": USER_AGENT}
    )

    with urllib.request.urlopen(req, timeout=10) as resp:

        data = json.loads(
            resp.read().decode("utf-8")
        )

        results = data.get("data", [])

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
        headers={"User-Agent": USER_AGENT}
    )

    with urllib.request.urlopen(req, timeout=10) as resp:

        data = json.loads(
            resp.read().decode("utf-8")
        )

        img_url = (
            "https://www.bing.com"
            + data["images"][0]["url"]
        )

        return get_image_bytes(img_url)


# ============================================================
# AJUSTAR WALLPAPER AL FORMATO 1920×1080
#
# Igual que Variety:
#
# - conserva proporción
# - cubre toda la pantalla
# - recorta el sobrante
# - NO deforma la imagen
# ============================================================

def fit_wallpaper(image):

    image = image.convert("RGB")

    iw, ih = image.size

    image_ratio = iw / ih
    screen_ratio = WIDTH / HEIGHT

    if image_ratio > screen_ratio:

        # Imagen más ancha:
        # ajustamos la altura y recortamos horizontalmente.

        new_height = HEIGHT

        new_width = int(
            HEIGHT * image_ratio
        )

    else:

        # Imagen más alta:
        # ajustamos la anchura y recortamos verticalmente.

        new_width = WIDTH

        new_height = int(
            WIDTH / image_ratio
        )

    image = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )

    left = max(
        0,
        (new_width - WIDTH) // 2
    )

    top = max(
        0,
        (new_height - HEIGHT) // 2
    )

    image = image.crop(
        (
            left,
            top,
            left + WIDTH,
            top + HEIGHT
        )
    )

    return image


# ============================================================
# OBTENER WALLPAPER ALEATORIO
# ============================================================

def fetch_random_background():

    providers = [
        get_wallhaven_wallpaper,
        get_bing_wallpaper
    ]

    random.shuffle(providers)

    for provider in providers:

        try:

            img_data = provider()

            img = Image.open(
                io.BytesIO(img_data)
            ).convert("RGB")

            return fit_wallpaper(img)

        except Exception:
            continue

    return Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        color=(40, 50, 60)
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
# Equivalente a:
#
# GdkPixbuf.Pixbuf.new_from_file_at_scale(
#     filename,
#     1,
#     1,
#     True
# )
#
# En PIL:
#
# image.resize((1,1))
# ============================================================

def get_image_representative_color(image):

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

def text_width(draw, text, font):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    return bbox[2] - bbox[0]


def text_height(draw, text, font):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    return bbox[3] - bbox[1]


# ============================================================
# WRAP
#
# Equivalente al:
#
# Pango.WrapMode.WORD
#
# con ancho máximo definido por QUOTES_WIDTH.
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
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


# ============================================================
# CREAR LAYOUT DE CITA
#
# Esta parte reproduce la lógica de:
#
# qlayout = make_layout(...)
# qwidth, qheight = qlayout.get_pixel_size()
#
# width = qwidth + 4*MARGIN
# ============================================================

def prepare_quote_layout(
    quote,
    author
):

    font = get_quote_font()

    dummy = Image.new(
        "RGB",
        (WIDTH, HEIGHT)
    )

    draw = ImageDraw.Draw(dummy)

    # --------------------------------------------------------
    # Ancho inicial de Pango
    #
    # sw * QUOTES_WIDTH / 100
    # --------------------------------------------------------

    initial_width = max(
        200,
        WIDTH * QUOTES_WIDTH // 100
    )

    # El layout recibe:
    #
    # width - 4*MARGIN
    #
    max_text_width = (
        initial_width
        - 4 * MARGIN
    )

    # --------------------------------------------------------
    # IMPORTANTE:
    #
    # No agregamos comillas aquí.
    #
    # cita-variety.py tampoco las agrega.
    # Si la fuente de la cita las trae, se conservan.
    # --------------------------------------------------------

    wrapped_lines = wrap_text(
        quote,
        font,
        max_text_width,
        draw
    )

    # --------------------------------------------------------
    # Medir ancho real de la cita
    #
    # Pango get_pixel_size() devuelve el ancho real ocupado.
    # --------------------------------------------------------

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
    # Altura de líneas
    #
    # Se aproxima al espaciado natural de Pango.
    # --------------------------------------------------------

    sample_bbox = draw.textbbox(
        (0, 0),
        "Ag",
        font=font
    )

    line_height = (
        sample_bbox[3]
        - sample_bbox[1]
    )

    # Un pequeño espaciado entre líneas.
    line_spacing = 4

    if wrapped_lines:

        qheight = (
            len(wrapped_lines)
            * line_height
            + max(
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

        box_width = WIDTH

    # --------------------------------------------------------
    # FIRMA
    #
    # En Variety:
    #
    # author_layout:
    # width - 4*MARGIN
    # alignment RIGHT
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
            box_width - 4 * MARGIN,
            draw
        )

        if author_lines:

            author_line_height = (
                line_height
            )

            aheight = (
                len(author_lines)
                * author_line_height
            )

    # --------------------------------------------------------
    # Igual que:
    #
    # height = qheight + aheight + int(2.5*MARGIN)
    # --------------------------------------------------------

    box_height = (
        qheight
        + aheight
        + int(2.5 * MARGIN)
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
# COMPOSICIÓN PRINCIPAL
#
# ESTA ES LA PARTE QUE REPRODUCE cita-variety.py
# ============================================================

def generate_composite_image(
    bg_image,
    quote_text,
    author_text
):

    # ========================================================
    # 1. COLOR REPRESENTATIVO
    # ========================================================

    bg_color = get_image_representative_color(
        bg_image
    )

    r, g, b = bg_color

    print(
        "INFO: Color representativo DE LA IMAGEN: "
        f"RGB {r}, {g}, {b}"
    )


    # ========================================================
    # 2. PREPARAR LAYOUT
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
        author_text
    )


    # ========================================================
    # 3. POSICIÓN
    #
    # Equivalente exacto a:
    #
    # hpos = trimw + (sw-width) * HPos / 100
    #
    # vpos = trimh + (sh-height) * VPos / 100
    #
    # Como aquí ya hicimos el crop de la imagen a 1920×1080:
    #
    # trimw = 0
    # trimh = 0
    # ========================================================

    hpos = (
        (WIDTH - box_width)
        * QUOTES_HPOS
        // 100
    )

    vpos = (
        (HEIGHT - box_height)
        * QUOTES_VPOS
        // 100
    )


    # ========================================================
    # 4. CAPA TRANSPARENTE
    # ========================================================

    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw_overlay = ImageDraw.Draw(
        overlay
    )


    # ========================================================
    # 5. FONDO DEL RECUADRO
    #
    # Variety:
    #
    # context.set_source_rgba(
    #     r/255,
    #     g/255,
    #     b/255,
    #     BG_OPACITY/100
    # )
    # ========================================================

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


    # ========================================================
    # 6. UNIR FONDO + RECUADRO
    # ========================================================

    result = Image.alpha_composite(
        bg_image.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(
        result
    )


    # ========================================================
    # 7. POSICIÓN DEL TEXTO
    #
    # Variety:
    #
    # hpos + (width-qwidth)/2
    #
    # Esto deja el texto centrado dentro del recuadro,
    # aunque el layout de la cita sea LEFT.
    # ========================================================

    text_x = (
        hpos
        + (box_width - qwidth) / 2
    )

    text_y = (
        vpos
        + MARGIN
    )


    # ========================================================
    # 8. CITA
    # ========================================================

    for line in wrapped_lines:

        # ----------------------------------------------------
        # Sombra
        #
        # Variety:
        #
        # negro alpha 0.2
        # luego translate(-2,-2)
        #
        # Aquí se reproduce visualmente como desplazamiento
        # de 2 px.
        # ----------------------------------------------------

        if TEXT_SHADOW:

            draw.text(
                (
                    text_x + 2,
                    text_y + 2
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
        # Texto blanco
        # ----------------------------------------------------

        draw.text(
            (
                text_x,
                text_y
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
    # 9. FIRMA
    #
    # Variety:
    #
    # translate(
    #     hpos + (width-qwidth)/2,
    #     vpos + MARGIN + qheight + MARGIN/2
    # )
    #
    # Y el layout está alineado a la DERECHA.
    # ========================================================

    if author_lines:

        author_y = (
            vpos
            + MARGIN
            + qheight
            + MARGIN / 2
        )

        # El ancho del layout de autor:
        author_layout_width = (
            box_width
            - 4 * MARGIN
        )

        # El inicio del layout.
        author_x = (
            hpos
            + (box_width - qwidth) / 2
        )

        for author_line in author_lines:

            author_w = text_width(
                draw,
                author_line,
                font
            )

            # Pango.Alignment.RIGHT
            author_draw_x = (
                author_x
                + author_layout_width
                - author_w
            )

            if TEXT_SHADOW:

                draw.text(
                    (
                        author_draw_x + 2,
                        author_y + 2
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
                    author_draw_x,
                    author_y
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


    # ========================================================
    # 10. DEVOLVER
    # ========================================================

    return result


# ============================================================
# ENDPOINT: RENDER IMAGE
# ============================================================

@app.get("/render-image")
def render_image():

    if STATE["current_image"] is None:

        STATE["current_image"] = (
            fetch_random_background()
        )

    if STATE["current_quote"] is None:

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a


    composite = generate_composite_image(
        STATE["current_image"],
        STATE["current_quote"],
        STATE["current_author"],
    )


    buf = io.BytesIO()

    composite.convert("RGB").save(
        buf,
        format="JPEG",
        quality=95
    )

    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/jpeg"
    )


# ============================================================
# ENDPOINT: ACCIONES
# ============================================================

@app.get("/action/{action_type}")
def handle_action(action_type: str):

    if action_type == "change_image":

        STATE["current_image"] = (
            fetch_random_background()
        )

    elif action_type == "change_quote":

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a

    elif action_type == "change_both":

        STATE["current_image"] = (
            fetch_random_background()
        )

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a

    return {
        "status": "ok"
    }


# ============================================================
# ENDPOINT: DESCARGAR
# ============================================================

@app.get("/download")
def download_wallpaper():

    # Por seguridad, si alguien entra directamente a /download
    # antes de generar /render-image.

    if STATE["current_image"] is None:

        STATE["current_image"] = (
            fetch_random_background()
        )

    if STATE["current_quote"] is None:

        q, a = get_new_quote()

        STATE["current_quote"] = q
        STATE["current_author"] = a


    composite = generate_composite_image(
        STATE["current_image"],
        STATE["current_quote"],
        STATE["current_author"],
    )


    buf = io.BytesIO()

    composite.convert("RGB").save(
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

            aspect-ratio: 16 / 9;

            margin-bottom: 25px;
        }


        .preview-card img {

            width: 100%;

            height: 100%;

            object-fit: cover;

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
                alt="Wallpaper Preview"
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


        </div>


    </div>


    <script>

        async function triggerAction(actionType) {

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
                    '/action/' + actionType
                );


                img.src =
                    '/render-image?t='
                    + new Date().getTime();


            } catch (e) {

                alert(
                    'Error actualizando la imagen'
                );

            } finally {

                img.onload = () => {

                    loader.classList.remove(
                        'active'
                    );

                };

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
