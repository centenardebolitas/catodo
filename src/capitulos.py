"""Capítulos del episodio: dónde empieza cada bloque del guion en el MP3.

Uso:
    python src/capitulos.py --fecha AAAA-MM-DD [--incrustar]

Calcula el inicio de cada bloque (apertura, cada noticia y cierre) con la misma línea de
tiempo que monta mix.py: los bloques de voz de bloques/, las pausas, el «bzz» al final de
cada noticia y la entrada de la voz a los SOLAPE_INTRO_S segundos de la sintonía. Deja
episodes/FECHA/capitulos.json en el formato de Podcasting 2.0 (JSON chapters), que es el
que enlaza el feed (<podcast:chapters>); feed.py lo copia también como Podlove Simple
Chapters (lo que lee Spotify) y como marcas de tiempo en las notas y la web.

Con --incrustar mete además los capítulos en el MP3 como etiquetas ID3 (CHAP), que es lo
que lee Apple Podcasts. No vuelve a codificar el audio: solo reescribe las etiquetas.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import mix
from comun import EPISODIOS, RAIZ
from feed import marca

FORMATO = "1.2.0"


def titulo_capitulo(cabecera):
    """«Noticia 2: CrowdStrike compra Zscaler» -> «CrowdStrike compra Zscaler»."""
    return re.sub(r"^Noticia\s+\d+\s*:\s*", "", cabecera.strip())


def linea_de_tiempo(carpeta):
    """[(cabecera del bloque, segundo en que empieza en el MP3)], como lo monta mix.py."""
    guion = (carpeta / "guion.md").read_text(encoding="utf-8")
    titulos = re.findall(r"(?m)^## (.+)$", guion)
    bloques = [carpeta / "bloques" / f"{n:02d}.wav" for n in range(1, len(titulos) + 1)]
    faltan = [b.name for b in bloques if not b.exists()]
    if faltan:
        sys.exit(f"Faltan bloques de audio ({', '.join(faltan)}): ejecuta antes `make voz`.")
    separador = RAIZ / "assets" / "separador.wav"
    intro = RAIZ / "assets" / "sintonia_intro.wav"
    bzz = mix.duracion(separador) if separador.exists() else 0
    t = mix.SOLAPE_INTRO_S if intro.exists() else 0.0
    inicios = []
    for n, (titulo, bloque) in enumerate(zip(titulos, bloques)):
        inicios.append((titulo, t))
        t += mix.duracion(bloque)
        if n == len(bloques) - 1:
            break
        if separador.exists() and titulo.lower().startswith("noticia"):
            t += mix.PAUSA_ANTES_SEPARADOR_S + bzz + mix.PAUSA_TRAS_SEPARADOR_S
        else:
            t += mix.PAUSA_ENTRE_BLOQUES_S
    return inicios


def calcular(carpeta):
    """Los capítulos en JSON chapters. El primero empieza en 0 (con la sintonía)."""
    capitulos = []
    for n, (cabecera, inicio) in enumerate(linea_de_tiempo(carpeta)):
        capitulos.append({"startTime": 0 if n == 0 else round(inicio, 2), "title": titulo_capitulo(cabecera)})
    return {"version": FORMATO, "chapters": capitulos}


def leer(carpeta):
    ruta = carpeta / "capitulos.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def escribir(carpeta):
    datos = calcular(carpeta)
    (carpeta / "capitulos.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return datos


def incrustar(mp3, datos):
    """Reescribe las etiquetas del MP3 con los capítulos (ID3 CHAP), sin recodificar el audio."""
    total = mix.duracion(mp3)
    capitulos = datos["chapters"]
    lineas = [";FFMETADATA1"]
    for n, c in enumerate(capitulos):
        fin = capitulos[n + 1]["startTime"] if n + 1 < len(capitulos) else total
        titulo = re.sub(r"([=;#\\\n])", r"\\\1", c["title"])
        lineas += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={round(c['startTime'] * 1000)}",
                   f"END={round(fin * 1000)}", f"title={titulo}"]
    with tempfile.TemporaryDirectory() as tmp:
        meta = Path(tmp) / "capitulos.txt"
        meta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        salida = Path(tmp) / mp3.name
        mix.ffmpeg("-i", str(mp3), "-i", str(meta), "-map", "0:a", "-map_metadata", "0", "-map_chapters", "1",
                   "-c", "copy", "-id3v2_version", "3", "-write_id3v1", "1", str(salida))
        salida.replace(mp3)


def capitulos_del_mp3(mp3):
    """Los capítulos que lleva el MP3 (para comprobar)."""
    salida = subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(mp3)],
                            capture_output=True, text=True)
    return [(float(c["start_time"]), c.get("tags", {}).get("title")) for c in json.loads(salida.stdout)["chapters"]]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fecha", required=True)
    p.add_argument("--incrustar", action="store_true", help="mete los capítulos en el MP3 (ID3)")
    args = p.parse_args()
    carpeta = EPISODIOS / args.fecha
    datos = escribir(carpeta)
    for c in datos["chapters"]:
        print(f"  {marca(c['startTime']):>6}  {c['title']}")
    if args.incrustar:
        mp3 = carpeta / f"catodo-{args.fecha}.mp3"
        incrustar(mp3, datos)
        print(f"Capítulos en {mp3.name}: {len(capitulos_del_mp3(mp3))}")


if __name__ == "__main__":
    main()
