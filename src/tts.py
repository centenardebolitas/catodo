"""Fase 3, paso 1: sintetiza el guion por bloques con Gemini TTS.

Uso:
    python src/tts.py [--fecha AAAA-MM-DD] [--prueba]

Dos vías (tts.via en settings.yaml):
  - agent_platform: Agent Platform de Google Cloud (antes Vertex AI). Se factura a la
    cuenta de Google Cloud y usa las credenciales de gcloud
    (`gcloud auth application-default login`, una sola vez).
  - gemini_api: API de Gemini de AI Studio, con GEMINI_API_KEY en .env.

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

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
BASES_AGENT_PLATFORM = {
    "global": "https://aiplatform.googleapis.com",
    "us": "https://aiplatform.us.rep.googleapis.com",
    "eu": "https://aiplatform.eu.rep.googleapis.com",
}
_TOKEN = {"valor": None, "hasta": 0}
CARACTERES_POR_SEGUNDO = 17  # ritmo aproximado de lectura, para detectar audios anómalos
ESPERA_LIMITE_MINUTO_S = 65
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


def _token_gcloud():
    """Token de acceso de las credenciales de gcloud (dura una hora; se renueva solo)."""
    if _TOKEN["valor"] and time.time() < _TOKEN["hasta"]:
        return _TOKEN["valor"]
    if not shutil.which("gcloud"):
        sys.exit("Falta gcloud: instálalo con `brew install --cask gcloud-cli`.")
    proceso = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                             capture_output=True, text=True)
    if proceso.returncode != 0 or not proceso.stdout.strip():
        sys.exit("gcloud no tiene credenciales: ejecuta `gcloud auth application-default login` "
                 "y vuelve a intentarlo.")
    _TOKEN.update(valor=proceso.stdout.strip(), hasta=time.time() + 45 * 60)
    return _TOKEN["valor"]


def _preparar(texto, tts, clave, con_estilo):
    """Devuelve (url, cuerpo, cabeceras) para la vía configurada."""
    estilo = tts.get("estilo") if con_estilo else None
    if tts.get("via", "gemini_api") == "agent_platform":
        region = tts.get("region", "global")
        url = (f"{BASES_AGENT_PLATFORM[region]}/v1/projects/{tts['proyecto_gcp']}/locations/{region}"
               f"/publishers/google/models/{tts['modelo']}:generateContent")
        parte = {"text": texto}
        if estilo:
            parte["speechMetadata"] = {"style": " ".join(estilo.split())}
        cuerpo = {
            "contents": [{"role": "user", "parts": [parte]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"voice": tts["voz"]}}},
        }
        cabeceras = {"Authorization": f"Bearer {_token_gcloud()}", "x-goog-user-project": tts["proyecto_gcp"]}
        return url, cuerpo, cabeceras
    if estilo:
        texto = f"{estilo}\n\nLee en voz alta el siguiente texto, sin decir estas indicaciones:\n\n{texto}"
    cuerpo = {
        "contents": [{"parts": [{"text": texto}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": tts["voz"]}}}},
    }
    return URL_GEMINI.format(modelo=tts["modelo"]), cuerpo, {"x-goog-api-key": clave}


def _peticion(texto, tts, clave, con_estilo, reintentos):
    """Una síntesis. Devuelve los bytes WAV."""
    error = "sin intentos"
    for intento in range(1, reintentos + 1):
        url, cuerpo, cabeceras = _preparar(texto, tts, clave, con_estilo)
        try:
            r = requests.post(url, json=cuerpo, headers=cabeceras, timeout=600)
        except requests.RequestException as e:
            error, espera = str(e), 15
        else:
            if r.status_code == 200:
                audio = _audio_de_respuesta(r.json())
                if audio:
                    return audio if audio.startswith(b"RIFF") else envolver_wav(audio)
                error, espera = "la respuesta no trae audio", 15
            else:
                try:
                    mensaje = r.json()["error"]["message"]
                except (ValueError, KeyError, TypeError):
                    mensaje = r.text
                error = f"HTTP {r.status_code}: " + " ".join(mensaje.split())[:600]
                if r.status_code == 401:
                    _TOKEN.update(valor=None, hasta=0)  # token caducado: se pide otro
                    espera = 1
                elif r.status_code == 429:
                    diaria = re.search(r"per ?day|PerDay|requests per day", mensaje, re.I)
                    if diaria and "minute" not in mensaje.lower():
                        break  # cuota diaria agotada: reintentar hoy no sirve
                    espera = ESPERA_LIMITE_MINUTO_S  # límite por minuto
                elif r.status_code in (500, 502, 503, 504):
                    espera = 15
                else:
                    break  # error definitivo (permisos, petición mal formada...)
        if intento < reintentos:
            print(f"    {error[:400]}\n    espero {espera} s (intento {intento}/{reintentos})")
            time.sleep(espera)
    raise RuntimeError(f"No se pudo sintetizar el bloque: {error}")


def sintetizar(texto, tts, clave, reintentos=8):
    """Sintetiza un bloque. Si con estilo el audio dura demasiado (señal de que la voz ha
    leído también las indicaciones), lo repite sin estilo."""
    con_estilo = tts.get("estilo_modo", "prefijo") != "ninguno"
    audio = _peticion(texto, tts, clave, con_estilo, reintentos)
    esperado = len(texto) / CARACTERES_POR_SEGUNDO
    real = duracion_bytes(audio)
    if con_estilo and tts.get("via") != "agent_platform" and real > esperado * 1.4 + 5:
        print(f"    el audio dura {real:.0f} s y se esperaban unos {esperado:.0f} s: repito sin estilo")
        time.sleep(ESPERA_LIMITE_MINUTO_S)
        audio = _peticion(texto, tts, clave, False, reintentos)
    return audio


def duracion_bytes(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return w.getnframes() / w.getframerate()


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
    if tts.get("via", "gemini_api") == "gemini_api" and not clave:
        sys.exit("Falta GEMINI_API_KEY en .env")

    carpeta = EPISODIOS / args.fecha
    guion = (carpeta / "guion.md").read_text(encoding="utf-8")
    destino = carpeta / "bloques"
    destino.mkdir(exist_ok=True)
    indice_ruta = destino / "indice.json"
    indice = json.loads(indice_ruta.read_text(encoding="utf-8")) if indice_ruta.exists() else {}

    rutas, segundos_totales, sintetizados = [], 0.0, 0
    bloques = bloques_del_guion(guion)
    for n, (titulo, cuerpo) in enumerate(bloques, 1):
        texto = aplicar_pronunciacion(cuerpo, sustituciones)
        huella = hashlib.sha1(f"{tts.get('via')}|{tts.get('region')}|{tts['modelo']}|{tts['voz']}|{tts.get('estilo_modo')}|{tts.get('estilo')}|{texto}"
                              .encode()).hexdigest()
        ruta = destino / f"{n:02d}.wav"
        if ruta.exists() and indice.get(ruta.name) == huella:
            print(f"[{n}/{len(bloques)}] {titulo}: ya sintetizado")
        else:
            print(f"[{n}/{len(bloques)}] {titulo} ({len(texto)} caracteres)…", flush=True)
            inicio = time.time()
            if sintetizados and tts.get("via") != "agent_platform":
                time.sleep(ESPERA_LIMITE_MINUTO_S)  # la API de AI Studio admite muy pocas por minuto
            ruta.write_bytes(sintetizar(texto, tts, clave))
            sintetizados += 1
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
