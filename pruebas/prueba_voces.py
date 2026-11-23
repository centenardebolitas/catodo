#!/usr/bin/env python3
"""Prueba a ciegas de voces para Cátodo.

Sintetiza el mismo texto con varios proveedores, modelos y voces, y genera una
página HTML para escucharlos sin saber cuál es cuál.

Uso:
    python3 pruebas/prueba_voces.py               # genera todas las muestras activas
    python3 pruebas/prueba_voces.py --estimar     # solo calcula caracteres y créditos
    python3 pruebas/prueba_voces.py --solo gemini # solo un proveedor
    python3 pruebas/prueba_voces.py --buscar-voces        # voces de ElevenLabs en tu cuenta
    python3 pruebas/prueba_voces.py --buscar-voces --biblioteca  # biblioteca pública en español

Solo usa la biblioteca estándar de Python 3.11+. Lee las claves de .env
(ELEVENLABS_API_KEY, GEMINI_API_KEY) en la raíz del proyecto.
"""

import argparse
import base64
import html
import json
import random
import string
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_PRUEBAS = RAIZ / "pruebas"
CONFIG = DIR_PRUEBAS / "voces.toml"

# Créditos de ElevenLabs por carácter en suscripción (aproximado, para estimar).
CREDITOS_POR_CARACTER = {"eleven_flash_v2_5": 0.5, "eleven_flash_v2": 0.5}


# ---------------------------------------------------------------- utilidades

def cargar_env():
    """Lee .env (CLAVE=valor) sin dependencias externas."""
    valores = {}
    ruta = RAIZ / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def peticion(url, cuerpo=None, cabeceras=None, metodo=None, reintentos=3):
    """Hace una petición HTTP con reintentos ante 429 y errores 5xx. Devuelve bytes."""
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    cabeceras = dict(cabeceras or {})
    if datos is not None:
        cabeceras["Content-Type"] = "application/json"
    for intento in range(1, reintentos + 1):
        req = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", errors="replace")[:800]
            if e.code in (429, 500, 502, 503, 504) and intento < reintentos:
                espera = 5 * intento
                print(f"    error {e.code}, reintento en {espera} s…")
                time.sleep(espera)
                continue
            raise RuntimeError(f"HTTP {e.code}: {detalle}") from None
        except urllib.error.URLError as e:
            if intento < reintentos:
                time.sleep(5 * intento)
                continue
            raise RuntimeError(f"Error de red: {e.reason}") from None


# ---------------------------------------------------------------- proveedores

def sintetizar_elevenlabs(texto, cand, env):
    clave = env.get("ELEVENLABS_API_KEY")
    if not clave:
        raise RuntimeError("Falta ELEVENLABS_API_KEY en .env")
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{cand['voz']}"
           "?output_format=mp3_44100_128")
    cuerpo = {"text": texto, "model_id": cand["modelo"]}
    if cand["modelo"] != "eleven_multilingual_v2":
        cuerpo["language_code"] = "es"
    if "ajustes" in cand:
        cuerpo["voice_settings"] = cand["ajustes"]
    audio = peticion(url, cuerpo, {"xi-api-key": clave, "Accept": "audio/mpeg"})
    return audio, "mp3"


def _buscar_audio(nodo):
    """Recorre la respuesta de Gemini y devuelve el primer audio en base64 que encuentre."""
    if isinstance(nodo, dict):
        dato = nodo.get("data")
        if isinstance(dato, str) and len(dato) > 1000:
            try:
                return base64.b64decode(dato)
            except ValueError:
                pass
        for valor in nodo.values():
            encontrado = _buscar_audio(valor)
            if encontrado:
                return encontrado
    elif isinstance(nodo, list):
        for valor in nodo:
            encontrado = _buscar_audio(valor)
            if encontrado:
                return encontrado
    return None


def sintetizar_gemini(texto, cand, env, estilo):
    clave = env.get("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError("Falta GEMINI_API_KEY en .env")
    contenido = {"type": "text", "text": texto}
    if estilo:
        contenido["annotations"] = [{"type": "speech_metadata", "style": estilo}]
    cuerpo = {
        "model": cand["modelo"],
        "input": [{"type": "user_input", "content": [contenido]}],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": cand["voz"]}]},
    }
    respuesta = peticion(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        cuerpo, {"x-goog-api-key": clave})
    audio = _buscar_audio(json.loads(respuesta))
    if not audio:
        raise RuntimeError(f"La respuesta no trae audio: {respuesta[:500]!r}")
    if not audio.startswith(b"RIFF"):
        audio = envolver_wav(audio)
    return audio, "wav"


def envolver_wav(pcm, frecuencia=24000):
    """Añade cabecera WAV a PCM 16 bits mono (por si la API lo devuelve sin cabecera)."""
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(pcm)
    return buf.getvalue()


# ---------------------------------------------------------------- búsqueda de voces

def buscar_voces(env, biblioteca):
    clave = env.get("ELEVENLABS_API_KEY")
    if not clave:
        sys.exit("Falta ELEVENLABS_API_KEY en .env")
    if biblioteca:
        params = {"language": "es", "accent": "peninsular", "gender": "male",
                  "page_size": 100, "sort": "usage_character_count_1y"}
        url = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(params)
    else:
        url = "https://api.elevenlabs.io/v2/voices?page_size=100"
    datos = json.loads(peticion(url, cabeceras={"xi-api-key": clave}))
    voces = datos.get("voices", [])
    if not voces:
        print("No se han encontrado voces.")
    for v in voces:
        etiquetas = v.get("labels") or {}
        acento = v.get("accent") or etiquetas.get("accent", "")
        genero = v.get("gender") or etiquetas.get("gender", "")
        idioma = v.get("language") or etiquetas.get("language", "")
        print(f"{v.get('voice_id')}  {v.get('name', '')[:40]:40}  "
              f"{idioma:4} {acento:15} {genero:7}")


USOS_PRESELECCION = {"conversational", "informative_educational", "narrative_story", "social_media"}


def preseleccion(env):
    """Página con las muestras gratuitas de voces masculinas peninsulares de la biblioteca."""
    clave = env.get("ELEVENLABS_API_KEY")
    if not clave:
        sys.exit("Falta ELEVENLABS_API_KEY en .env")
    params = {"language": "es", "accent": "peninsular", "gender": "male",
              "page_size": 100, "sort": "usage_character_count_1y"}
    url = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(params)
    voces = json.loads(peticion(url, cabeceras={"xi-api-key": clave})).get("voices", [])
    voces = [v for v in voces if v.get("use_case") in USOS_PRESELECCION
             and v.get("age") != "old" and v.get("preview_url")][:30]
    bloques = []
    for v in voces:
        bloques.append(
            f'<div class="muestra"><h2>{html.escape(v["name"])}</h2>'
            f'<p>{html.escape(v.get("description") or "")}<br>'
            f'<small>{html.escape(v.get("use_case", ""))} · {html.escape(v.get("age", ""))} · '
            f'<code>{v["voice_id"]}</code></small></p>'
            f'<audio controls preload="none" src="{html.escape(v["preview_url"])}"></audio></div>')
    pagina = (PLANTILLA_HTML.format(muestras="\n".join(bloques))
              .replace("Prueba de voces de Cátodo</h1>", "Preselección de voces (ElevenLabs)</h1>")
              .replace('<button id="revelar">Revelar</button>', ""))
    pagina = pagina.replace(
        "Escucha cada muestra sin mirar quién es quién y puntúala del 1 al 5.\n"
        "Cuando acabes, pulsa «Revelar».",
        "Muestras oficiales de cada voz (no gastan créditos). Apunta las 2 o 3 que "
        "te parezcan más Cátodo: cálida, cercana, simpática.")
    salida = DIR_PRUEBAS / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "preseleccion.html").write_text(pagina, encoding="utf-8")
    print(f"{len(voces)} voces. Abre:\n  {salida / 'preseleccion.html'}")


# ---------------------------------------------------------------- página de escucha

PLANTILLA_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prueba de voces de Cátodo</title>
<style>
  :root {{ --fondo:#fafaf7; --texto:#1d1d1b; --suave:#6b6b66; --borde:#ddd; --acento:#c2410c; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fondo:#161615; --texto:#ecece8; --suave:#9a9a94; --borde:#333; --acento:#fb923c; }} }}
  body {{ font-family: system-ui, sans-serif; background:var(--fondo); color:var(--texto);
         max-width: 720px; margin: 0 auto; padding: 24px 16px; }}
  h1 {{ margin-bottom: 4px; }} p {{ color: var(--suave); }}
  .muestra {{ border:1px solid var(--borde); border-radius:10px; padding:14px 16px; margin:12px 0; }}
  .muestra h2 {{ margin:0 0 8px; font-size:1.2rem; }}
  audio {{ width:100%; }}
  .nota {{ display:flex; gap:6px; margin-top:8px; flex-wrap:wrap; }}
  .nota button {{ border:1px solid var(--borde); background:none; color:var(--texto);
                  border-radius:6px; padding:4px 10px; cursor:pointer; }}
  .nota button.elegido {{ background:var(--acento); color:#fff; border-color:var(--acento); }}
  .revelado {{ margin-top:8px; font-weight:600; color:var(--acento); display:none; }}
  body.ver .revelado {{ display:block; }}
  #revelar {{ margin-top:16px; padding:10px 16px; border-radius:8px; border:none;
             background:var(--acento); color:#fff; font-size:1rem; cursor:pointer; }}
</style></head><body>
<h1>Prueba de voces de Cátodo</h1>
<p>Escucha cada muestra sin mirar quién es quién y puntúala del 1 al 5.
Cuando acabes, pulsa «Revelar».</p>
{muestras}
<button id="revelar">Revelar</button>
<script>
  document.querySelectorAll('.nota').forEach(function (grupo) {{
    grupo.querySelectorAll('button').forEach(function (b) {{
      b.addEventListener('click', function () {{
        grupo.querySelectorAll('button').forEach(function (x) {{ x.classList.remove('elegido'); }});
        b.classList.add('elegido');
      }});
    }});
  }});
  document.getElementById('revelar').addEventListener('click', function () {{
    document.body.classList.add('ver');
  }});
</script>
</body></html>
"""


def generar_html(carpeta, resultados):
    bloques = []
    for r in resultados:
        botones = "".join(f"<button>{n}</button>" for n in range(1, 6))
        bloques.append(
            f'<div class="muestra"><h2>Muestra {r["letra"]}</h2>'
            f'<audio controls preload="none" src="{html.escape(r["fichero"])}"></audio>'
            f'<div class="nota">{botones}</div>'
            f'<div class="revelado">{html.escape(r["descripcion"])}</div></div>')
    (carpeta / "escucha.html").write_text(
        PLANTILLA_HTML.format(muestras="\n".join(bloques)), encoding="utf-8")


# ---------------------------------------------------------------- principal

def describir(cand):
    voz = cand.get("nombre_voz") or cand.get("voz")
    return f"{cand['proveedor']} · {cand['modelo']} · {voz}"


def main():
    parser = argparse.ArgumentParser(description="Prueba a ciegas de voces para Cátodo")
    parser.add_argument("--estimar", action="store_true", help="solo calcula el consumo")
    parser.add_argument("--solo", choices=["elevenlabs", "gemini"], help="solo un proveedor")
    parser.add_argument("--buscar-voces", action="store_true", help="lista voces de ElevenLabs")
    parser.add_argument("--biblioteca", action="store_true",
                        help="con --buscar-voces: busca en la biblioteca pública (español, masculinas)")
    parser.add_argument("--preseleccion", action="store_true",
                        help="página con las muestras gratuitas de voces peninsulares de ElevenLabs")
    args = parser.parse_args()

    env = cargar_env()
    if args.preseleccion:
        preseleccion(env)
        return
    if args.buscar_voces:
        buscar_voces(env, args.biblioteca)
        return

    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    texto = (DIR_PRUEBAS / config["texto"]).read_text(encoding="utf-8").strip()
    estilo = config.get("estilo_gemini", "")

    candidatos = []
    for cand in config.get("candidato", []):
        if not cand.get("activo", True):
            continue
        if args.solo and cand["proveedor"] != args.solo:
            continue
        if not cand.get("voz"):
            print(f"Saltado (sin voz configurada): {describir(cand)}")
            continue
        candidatos.append(cand)

    n_car = len(texto)
    print(f"\nTexto: {n_car} caracteres. Candidatos: {len(candidatos)}.")
    creditos = sum(n_car * CREDITOS_POR_CARACTER.get(c["modelo"], 1)
                   for c in candidatos if c["proveedor"] == "elevenlabs")
    if creditos:
        print(f"ElevenLabs: unos {creditos:,.0f} créditos (estimación).".replace(",", "."))
    if args.estimar or not candidatos:
        return

    carpeta = DIR_PRUEBAS / "salida" / datetime.now().strftime("%Y-%m-%d_%H%M")
    carpeta.mkdir(parents=True, exist_ok=True)
    random.shuffle(candidatos)

    resultados = []
    for letra, cand in zip(string.ascii_uppercase, candidatos):
        print(f"[{letra}] {describir(cand)}…", flush=True)
        inicio = time.time()
        try:
            if cand["proveedor"] == "elevenlabs":
                audio, ext = sintetizar_elevenlabs(texto, cand, env)
            elif cand["proveedor"] == "gemini":
                audio, ext = sintetizar_gemini(texto, cand, env, estilo)
            else:
                raise RuntimeError(f"Proveedor desconocido: {cand['proveedor']}")
        except RuntimeError as e:
            print(f"    FALLO: {e}")
            continue
        fichero = f"muestra_{letra}.{ext}"
        (carpeta / fichero).write_bytes(audio)
        print(f"    ok ({len(audio) / 1024:.0f} KB, {time.time() - inicio:.1f} s)")
        resultados.append({"letra": letra, "fichero": fichero, "descripcion": describir(cand)})

    if not resultados:
        carpeta.rmdir()
        print("\nNo se ha generado ninguna muestra.")
        return
    (carpeta / "clave.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    generar_html(carpeta, resultados)
    print(f"\nListo. Abre para escuchar:\n  {carpeta / 'escucha.html'}")


if __name__ == "__main__":
    main()
