import json
import random
import re
from html import unescape
from urllib.request import Request, urlopen
from flask import Flask, render_template_string, jsonify, Response

app = Flask(__name__)

API_BASE = "https://api3.timelesstoday.io/v2/cms/products/es-ES/group/2/12"
LIMIT = 12


def hacer_peticion(offset):
    url = f"{API_BASE}/{offset}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like"
            " Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://timelesstoday.tv/",
        "Origin": "https://timelesstoday.tv",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def procesar_evento(evento):
    raw_cita = evento.get("tt_one_line_quote")
    if not raw_cita:
        return None

    texto = unescape(str(raw_cita))
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    lugar_fecha = None
    match_firma = re.search(
        r"[\s–\-—]*Prem\s+Rawat(?:,\s*(.+))?$", texto, flags=re.IGNORECASE
    )

    if match_firma:
        texto = texto[: match_firma.start()].strip()
        if match_firma.group(1):
            lugar_fecha = match_firma.group(1).strip()

    if not lugar_fecha:
        nombre_evento = evento.get("tt_name")
        if nombre_evento and nombre_evento.strip():
            lugar_fecha = nombre_evento.strip()

    texto = re.sub(r'^["“”’\']+|["“”’\']+$', "", texto).strip()
    texto = re.sub(r'["”’\']+\s*\.?$', "", texto).strip()

    if texto and not texto.endswith((".", "!", "?", "…")):
        texto += "."

    if not texto:
        return None

    if lugar_fecha:
        lugar_fecha = re.sub(r'^["“”’\']+|["“”’\']+$', "", lugar_fecha).strip()
        lugar_fecha = lugar_fecha.rstrip(".")
        return f'“{texto}” — Prem Rawat, {lugar_fecha}'
    else:
        return f'“{texto}” — Prem Rawat'


def obtener_cita_random():
    primera_pagina = hacer_peticion(0)
    if not primera_pagina:
        return "No se pudo conectar con el servidor."

    total_eventos = primera_pagina.get("filter", {}).get("count", 0)
    if total_eventos == 0:
        return "No hay citas disponibles."

    offsets_posibles = list(range(0, total_eventos, LIMIT))

    for _ in range(5):
        offset_azar = random.choice(offsets_posibles)
        datos = (
            primera_pagina if offset_azar == 0 else hacer_peticion(offset_azar)
        )

        if not datos:
            continue

        eventos = datos.get("data", [])
        if not eventos:
            continue

        random.shuffle(eventos)

        for evento in eventos:
            resultado = procesar_evento(evento)
            if resultado:
                return resultado

    return "Intenta de nuevo."


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Prem Rawat</title>
    
    <link rel="manifest" href="/manifest.json">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="Prem Rawat">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#121212">

    <style>
        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }
        body {
            background-color: #121212;
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .card {
            width: 100%;
            max-width: 480px;
            background: #1e1e1e;
            padding: 36px 28px;
            border-radius: 24px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.6);
            border: 1px solid #2d2d2d;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .quote {
            font-size: 1.25rem;
            line-height: 1.6;
            font-style: italic;
            color: #f0f0f0;
            margin-bottom: 32px;
            min-height: 100px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: opacity 0.25s ease;
        }
        .quote.fade {
            opacity: 0.2;
        }
        .btn {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: white;
            border: none;
            padding: 14px 32px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
            transition: transform 0.1s, background 0.2s;
        }
        .btn:active {
            transform: scale(0.96);
            background: #1e40af;
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="quote" id="quoteText">Obteniendo cita...</div>
        <button class="btn" id="nextBtn" onclick="cargarCita()">Otra cita</button>
    </div>

    <script>
        async function cargarCita() {
            const quoteEl = document.getElementById('quoteText');
            const btnEl = document.getElementById('nextBtn');
            
            quoteEl.classList.add('fade');
            btnEl.disabled = true;

            try {
                const response = await fetch('/api/cita');
                const data = await response.json();
                
                setTimeout(() => {
                    quoteEl.textContent = data.cita;
                    quoteEl.classList.remove('fade');
                    btnEl.disabled = false;
                }, 200);
            } catch (error) {
                quoteEl.textContent = "Error al conectar. Intenta de nuevo.";
                quoteEl.classList.remove('fade');
                btnEl.disabled = false;
            }
        }

        window.onload = cargarCita;
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/cita")
def api_cita():
    return jsonify({"cita": obtener_cita_random()})


@app.route("/manifest.json")
def manifest():
    data = {
        "short_name": "Prem Rawat",
        "name": "Prem Rawat",
        "start_url": "/",
        "background_color": "#121212",
        "theme_color": "#121212",
        "display": "standalone",
        "icons": [
            {
                "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'><rect width='512' height='512' rx='100' fill='%231e1e1e'/><text x='50%' y='60%' dominant-baseline='middle' text-anchor='middle' font-size='280' fill='%232563eb'>PR</text></svg>",
                "sizes": "512x512",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
    }
    return Response(json.dumps(data), mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
