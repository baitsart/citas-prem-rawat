import io
import json
import os
import random
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
# Tamaño estándar para Wallpapers en la nube (Full HD o 4K)
WIDTH, HEIGHT = 1920, 1080

WALLHAVEN_API_KEY = os.environ.get(
    "WALLHAVEN_API_KEY", "jJm5diseSPiDVIqvvE7aUS4fWwgJ0koW"
)
WALLHAVEN_TAGS = ["Japan", "nature", "space", "animals"]
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ============================================================
# DESCARGA DE IMÁGENES DESDE SERVIDORES
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
        if not results:
            raise RuntimeError("No se encontraron resultados en Wallhaven.")
        return get_image_bytes(results[0]["path"])


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
            return Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception as e:
            print(f"Error descargando fondo: {e}")
            continue
    # Imagen de respaldo de color sólido si falla la red
    return Image.new("RGB", (WIDTH, HEIGHT), color=(30, 30, 30))


# ============================================================
# COMPOSICIÓN DE LA IMAGEN CON PILLOW (HEADLESS)
# ============================================================


def create_wallpaper(
    quote_text="La paz está dentro de ti.", author="Prem Rawat"
):
    # 1. Obtener y redimensionar fondo
    bg_image = fetch_random_background()
    bg_image = bg_image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    # 2. Obtenemos un color representativo promedio
    small_img = bg_image.resize((1, 1))
    avg_color = small_img.getpixel((0, 0))

    # 3. Crear capa semitransparente para el cuadro de texto
    overlay = Image.new("RGBA", bg_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Tamaño del cuadro
    box_w, box_h = int(WIDTH * 0.6), int(HEIGHT * 0.35)
    box_x = (WIDTH - box_w) // 2
    box_y = (HEIGHT - box_h) // 2

    # Dibujar fondo del cuadro con transparencia
    r, g, b = avg_color
    draw.rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h], fill=(r, g, b, 160)
    )

    # Combinar fondo e interfaz
    bg_image = Image.alpha_composite(bg_image.convert("RGBA"), overlay)
    draw_final = ImageDraw.Draw(bg_image)

    # Cargar fuente por defecto (en Linux Render usa DejaVuSans)
    try:
        font_quote = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 36
        )
        font_author = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", 28
        )
    except OSError:
        font_quote = ImageFont.load_default()
        font_author = ImageFont.load_default()

    # Dibujar texto
    text_content = f'"{quote_text}"'
    draw_final.text(
        (WIDTH // 2, box_y + 60),
        text_content,
        fill="white",
        font=font_quote,
        anchor="mm",
    )
    if author:
        draw_final.text(
            (box_x + box_w - 60, box_y + box_h - 50),
            f"— {author}",
            fill="white",
            font=font_author,
            anchor="rm",
        )

    return bg_image


# Ejemplo de ejecución
if __name__ == "__main__":
    img = create_wallpaper("La paz es la constante dentro de ti.")
    img.save("output_render.png")
    print("Imagen generada con éxito: output_render.png")
