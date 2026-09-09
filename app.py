import io
import json
import os
import random
import textwrap
import urllib.parse
import urllib.request
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Generador de Citas y Wallpapers")

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
WIDTH, HEIGHT = 1920, 1080

WALLHAVEN_API_KEY = os.environ.get(
    "WALLHAVEN_API_KEY", "jJm5diseSPiDVIqvvE7aUS4fWwgJ0koW"
)
WALLHAVEN_TAGS = ["Japan", "nature", "space", "animals"]
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Citas de respaldo
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
    )
]

STATE = {"current_image": None, "current_quote": None, "current_author": None}

# ============================================================
# DESCARGA DE IMÁGENES
# ============================================================

def get_image_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


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
    api_url = f"https://wallhaven.cc/api/v1/search?{query}"
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        results = data.get("data", [])
        if results:
            return get_image_bytes(results[0]["path"])
    raise RuntimeError("No se encontraron resultados en Wallhaven.")


def get_bing_wallpaper():
    url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        img_url = "https://www.bing.com" + data["images"][0]["url"]
        return get_image_bytes(img_url)


def fetch_random_background():
    providers = [get_wallhaven_wallpaper, get_bing_wallpaper]
    random.shuffle(providers)

    for provider in providers:
        try:
            img_data = provider()
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        except Exception:
            continue

    return Image.new("RGB", (WIDTH, HEIGHT), color=(40, 50, 60))


def get_new_quote():
    return random.choice(CITAS_MEMORIA)


# ============================================================
# COMPOSICIÓN DE LA IMAGEN (ESTILO VARIETY / CAIRO)
# ============================================================

def wrap_text(text, font, max_width, draw):
    """Divide el texto automáticamente para que quepa en el ancho definido."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def generate_composite_image(bg_image, quote_text, author_text):
    # 1. Color representativo de la imagen
    small_img = bg_image.resize((1, 1))
    avg_color = small_img.getpixel((0, 0))

    overlay = Image.new("RGBA", bg_image.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    # 2. Cargar fuentes locales con fallback
    try:
        font_quote = ImageFont.truetype("DejaVuSerif.ttf", 38)
        font_author = ImageFont.truetype("DejaVuSerif-Italic.ttf", 28)
    except OSError:
        try:
            font_quote = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 38)
            font_author = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", 28)
        except OSError:
            font_quote = ImageFont.load_default()
            font_author = ImageFont.load_default()

    # 3. Dimensiones y envoltura de texto
    box_w = int(WIDTH * 0.70)
    margin = 40
    max_text_w = box_w - (margin * 2)

    wrapped_lines = wrap_text(f'"{quote_text}"', font_quote, max_text_w, draw_overlay)
    
    # Cálculo de alturas
    line_bbox = font_quote.getbbox("A")
    line_height = (line_bbox[3] - line_bbox[1]) + 14
    quote_height = len(wrapped_lines) * line_height
    
    author_height = 0
    if author_text:
        a_bbox = font_author.getbbox("A")
        author_height = (a_bbox[3] - a_bbox[1]) + 20
    
    box_h = quote_height + author_height + (margin * 2)
    box_x = (WIDTH - box_w) // 2
    box_y = (HEIGHT - box_h) // 2

    # 4. Dibujar recuadro de fondo (opacidad 55%)
    r, g, b = avg_color
    draw_overlay.rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h], fill=(r, g, b, 140)
    )

    bg_composite = Image.alpha_composite(bg_image.convert("RGBA"), overlay)
    draw_final = ImageDraw.Draw(bg_composite)

    # 5. Renderizar Texto de Cita con Sombra
    current_y = box_y + margin
    for line in wrapped_lines:
        # Sombra
        draw_final.text((box_x + margin + 2, current_y + 2), line, fill=(0, 0, 0, 160), font=font_quote)
        # Texto principal
        draw_final.text((box_x + margin, current_y), line, fill="white", font=font_quote)
        current_y += line_height

    # 6. Renderizar Firma del Autor
    if author_text:
        author_str = f"— {author_text}"
        current_y += 10
        # Sombra
        draw_final.text((box_x + margin + 2, current_y + 2), author_str, fill=(0, 0, 0, 160), font=font_author)
        # Texto principal
        draw_final.text((box_x + margin, current_y), author_str, fill="white", font=font_author)

    return bg_composite


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/render-image")
def render_image():
    if STATE["current_image"] is None:
        STATE["current_image"] = fetch_random_background()
    if STATE["current_quote"] is None:
        q, a = get_new_quote()
        STATE["current_quote"], STATE["current_author"] = q, a

    composite = generate_composite_image(
        STATE["current_image"],
        STATE["current_quote"],
        STATE["current_author"],
    )

    buf = io.BytesIO()
    composite.convert("RGB").save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


@app.get("/action/{action_type}")
def handle_action(action_type: str):
    if action_type == "change_image":
        STATE["current_image"] = fetch_random_background()
    elif action_type == "change_quote":
        q, a = get_new_quote()
        STATE["current_quote"], STATE["current_author"] = q, a
    elif action_type == "change_both":
        STATE["current_image"] = fetch_random_background()
        q, a = get_new_quote()
        STATE["current_quote"], STATE["current_author"] = q, a

    return {"status": "ok"}


@app.get("/download")
def download_wallpaper():
    composite = generate_composite_image(
        STATE["current_image"],
        STATE["current_quote"],
        STATE["current_author"],
    )
    buf = io.BytesIO()
    composite.convert("RGB").save(buf, format="JPEG", quality=100)
    buf.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=wallpaper_cita.jpg"
    }
    return StreamingResponse(buf, media_type="image/jpeg", headers=headers)


# ============================================================
# VISTA INTERACTIVA WEB
# ============================================================

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Wallpaper Quote Studio</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: system-ui, -apple-system, sans-serif;
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
                box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);
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
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(15, 23, 42, 0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.2rem;
                font-weight: 600;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease;
            }
            .loader.active { opacity: 1; pointer-events: all; }
            .btn-group {
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }
            button, a.btn {
                background-color: #334155;
                color: #ffffff;
                border: 1px solid #475569;
                padding: 12px 20px;
                font-size: 0.95rem;
                font-weight: 600;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                text-decoration: none;
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }
            button:hover, a.btn:hover {
                background-color: #475569;
                transform: translateY(-2px);
            }
            button.primary, a.btn.primary {
                background-color: #2563eb;
                border-color: #3b82f6;
            }
            button.primary:hover, a.btn.primary:hover {
                background-color: #1d4ed8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="margin-bottom: 20px;">🖼️ Wallpaper Quote Studio</h1>
            
            <div class="preview-card">
                <img id="wallpaper" src="/render-image" alt="Wallpaper Preview">
                <div id="loader" class="loader">Procesando...</div>
            </div>

            <div class="btn-group">
                <button onclick="triggerAction('change_image')">🖼️ Cambiar de imagen</button>
                <button onclick="triggerAction('change_quote')">✍️ Cambiar de cita</button>
                <button onclick="triggerAction('change_both')">🔀 Cambiar ambas</button>
                <a href="/download" class="btn primary" target="_blank">📥 Descargar</a>
            </div>
        </div>

        <script>
            async function triggerAction(actionType) {
                const loader = document.getElementById('loader');
                const img = document.getElementById('wallpaper');
                loader.classList.add('active');
                
                try {
                    await fetch('/action/' + actionType);
                    img.src = '/render-image?t=' + new Date().getTime();
                } catch (e) {
                    alert('Error actualizando la imagen');
                } finally {
                    img.onload = () => loader.classList.remove('active');
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
