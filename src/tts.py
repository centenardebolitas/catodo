"""Fase 3, paso 1: sintetiza el guion por bloques con Gemini TTS.

Uso:
    python src/tts.py [--fecha AAAA-MM-DD] [--prueba]

Lee episodes/AAAA-MM-DD/guion.md, lo divide por los encabezados "## ",
aplica las sustituciones de config/pronunciacion.yaml y sintetiza cada bloque
con el modelo, la voz y el estilo de settings.yaml. Deja un WAV por bloque en
episodes/AAAA-MM-DD/bloques/ (si ya existe y el texto no ha cambiado, no lo repite).
Con --prueba, además une los bloques en prueba.wav (sin sintonía ni normalizar)
y, si está afconvert (macOS), crea prueba.m4a.
"""

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
import wave
from datetime import date

import requests

from comun import EPISODIOS, cargar_env, cargar_yaml

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/interactions"
SILENCIO_ENTRE_BLOQUES_S = 0.7


def bloques_del_guion(texto):
    """Devuelve [(titulo, texto)] a partir de los encabezados '## '."""
    partes = re.split(r"(?m)^## ", texto)
    bloques = []
    for parte in partes[1:]:
        titulo, _, cuerpo = parte.partition("\n")
        cuerpo = cuerpo.strip()
        if cuerpo:
            bloques.append((titulo.strip(), cuerpo))
    return bloques


def aplicar_pronunciacion(texto, sustituciones):
    for original, como_suena in (sustituciones or {}).items():
        texto = re.sub(rf"(?<!\w){re.escape(original)}(?!\w)", como_suena, texto)
    # Las cursivas de Markdown (*feature*) no deben llegar a la voz.
    return re.sub(r"\*+([^*]+)\*+", r"\1", texto)


def _audio_de_respuesta(nodo):
    if isinstance(nodo, dict):
        dato = nodo.get("data")
        if isinstance(dato, str) and len(dato) > 1000:
            try:
                return base64.b64decode(dato)
            except ValueError:
                pass
        for valor in nodo.values():
            encontrado = _audio_de_respuesta(valor)
            if encontrado:
                return encontrado
    elif isinstance(nodo, list):
        for valor in nodo:
            encontrado = _audio_de_respuesta(valor)
            if encontrado:
                return encontrado
    return None


def sintetizar(texto, tts, clave, reintentos=4):
    contenido = {"type": "text", "text": texto}
    if tts.get("estilo"):
        contenido["annotations"] = [{"type": "speech_metadata", "style": tts["estilo"]}]
    cuerpo = {
        "model": tts["modelo"],
        "input": [{"type": "user_input", "content": [contenido]}],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": tts["voz"]}]},
    }
    for intento in range(1, reintentos + 1):
        try:
            r = requests.post(URL_GEMINI, json=cuerpo, headers={"x-goog-api-key": clave}, timeout=600)
        except requests.RequestException as e:
            error = str(e)
        else:
            if r.status_code == 200:
                audio = _audio_de_respuesta(r.json())
                if audio:
                    return audio if audio.startswith(b"RIFF") else envolver_wav(audio)
                error = "la respuesta no trae audio"
            else:
                error = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code not in (429, 500, 502, 503, 504) or "per day" in r.text:
                    break  # error definitivo o cuota diaria agotada: reintentar no sirve
        espera = 10 * intento
        print(f"    fallo ({error[:120]}); reintento en {espera} s")
        time.sleep(espera)
    raise RuntimeError(f"No se pudo sintetizar el bloque: {error}")


def envolver_wav(pcm, frecuencia=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(pcm)
    return buf.getvalue()


def duracion_wav(ruta):
    with wave.open(str(ruta)) as w:
        return w.getnframes() / w.getframerate()


def unir(rutas, destino):
    """Une WAV del mismo formato con un silencio breve entre ellos."""
    with wave.open(str(rutas[0])) as primero:
        parametros = primero.getparams()
    silencio = b"\x00" * int(parametros.framerate * SILENCIO_ENTRE_BLOQUES_S) * parametros.sampwidth * parametros.nchannels
    with wave.open(str(destino), "wb") as salida:
        salida.setparams(parametros)
        for n, ruta in enumerate(rutas):
            with wave.open(str(ruta)) as w:
                salida.writeframes(w.readframes(w.getnframes()))
            if n < len(rutas) - 1:
                salida.writeframes(silencio)


def main():
    parser = argparse.ArgumentParser(description="Sintetiza el guion de Cátodo por bloques")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--prueba", action="store_true", help="une los bloques en prueba.wav / prueba.m4a")
    args = parser.parse_args()

    tts = cargar_yaml("settings.yaml")["tts"]
    sustituciones = cargar_yaml("pronunciacion.yaml").get("sustituciones")
    clave = cargar_env().get("GEMINI_API_KEY")
    if not clave:
        sys.exit("Falta GEMINI_API_KEY en .env")

    carpeta = EPISODIOS / args.fecha
    guion = (carpeta / "guion.md").read_text(encoding="utf-8")
    destino = carpeta / "bloques"
    destino.mkdir(exist_ok=True)
    indice_ruta = destino / "indice.json"
    indice = json.loads(indice_ruta.read_text(encoding="utf-8")) if indice_ruta.exists() else {}

    rutas, segundos_totales = [], 0.0
    bloques = bloques_del_guion(guion)
    for n, (titulo, cuerpo) in enumerate(bloques, 1):
        texto = aplicar_pronunciacion(cuerpo, sustituciones)
        huella = hashlib.sha1(f"{tts['modelo']}|{tts['voz']}|{tts.get('estilo')}|{texto}".encode()).hexdigest()
        ruta = destino / f"{n:02d}.wav"
        if ruta.exists() and indice.get(ruta.name) == huella:
            print(f"[{n}/{len(bloques)}] {titulo}: ya sintetizado")
        else:
            print(f"[{n}/{len(bloques)}] {titulo} ({len(texto)} caracteres)…", flush=True)
            inicio = time.time()
            ruta.write_bytes(sintetizar(texto, tts, clave))
            indice[ruta.name] = huella
            indice_ruta.write_text(json.dumps(indice, indent=2), encoding="utf-8")
            print(f"    {duracion_wav(ruta):.0f} s de audio en {time.time() - inicio:.0f} s")
        rutas.append(ruta)
        segundos_totales += duracion_wav(ruta)

    tokens = segundos_totales * 25
    print(f"\nAudio total: {segundos_totales / 60:.1f} min (unos {tokens:,.0f} tokens de audio).".replace(",", "."))

    if args.prueba:
        prueba = carpeta / "prueba.wav"
        unir(rutas, prueba)
        print(f"Prueba sin sintonía ni normalizar: {prueba.relative_to(EPISODIOS.parent)}")
        if shutil.which("afconvert"):
            m4a = carpeta / "prueba.m4a"
            # 48 kbps: suficiente para voz y compatible con audio mono a 24 kHz.
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "48000", str(prueba), str(m4a)], check=True)
            print(f"Versión comprimida: {m4a.relative_to(EPISODIOS.parent)} ({m4a.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
