"""Portada de cada episodio: el guion «impreso» en emojis, en duotono cian sobre noche.

Uso:
    python src/portada_episodio.py --fecha AAAA-MM-DD [--emojis fichero.txt]

Lee episodes/FECHA/emojis.txt (una línea por párrafo del guion, solo emojis) y deja
episodes/FECHA/portada.jpg (3000x3000, para el feed) y portada-web.jpg (600x600). Los emojis van siempre del mismo tamaño en una
rejilla fija: si el guion no cabe, se corta; si sobra sitio, queda vacío. Entre párrafo
y párrafo, una casilla en blanco. La esquina de abajo a la derecha se reserva para
«Cátodo.» en neón, y los emojis la rodean, no pasan por detrás.

Los dibujos de los emojis son los PNG de Noto Emoji de Google (imágenes con licencia
Apache 2.0; las banderas, de region-flags, de dominio público), descargados de su
repositorio en una versión fija y guardados en caché (CATODO_CACHE_EMOJI o
cache/emoji). Un emoji que no exista en Noto se salta. La tipografía es Tilt Neon
(assets/fuentes/, licencia OFL), la misma de la portada del programa y del favicon.
"""

import argparse
import os
import sys
from pathlib import Path

import regex
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from comun import EPISODIOS, RAIZ, cargar_yaml

AJUSTES = cargar_yaml("settings.yaml")["portada"]
LADO = 3000
COLUMNAS = AJUSTES["columnas"]     # rejilla fija: los emojis tienen siempre el mismo tamaño
CASILLA = LADO // COLUMNAS
EMOJI = round(CASILLA * 0.79)      # tamaño de cada emoji dentro de su casilla
MARCA = tuple(AJUSTES["marca"])    # casillas (ancho, alto) reservadas abajo a la derecha
WEB = AJUSTES["lado_web_px"]       # lado de la versión para la web
NOCHE, CIAN, NUCLEO = "#0e0d13", "#22d3ee", "#e8feff"
OPACIDAD = 0.9

NOTO = "https://raw.githubusercontent.com/googlefonts/noto-emoji/v2026-09-24-unicode18_0"
CACHE = Path(os.environ.get("CATODO_CACHE_EMOJI") or RAIZ / "cache" / "emoji")
FUENTE = RAIZ / "assets" / "fuentes" / "TiltNeon.ttf"
INDICADOR = range(0x1F1E6, 0x1F1FF + 1)   # letras de las banderas


def emojis_de(linea):
    """Los emojis de una línea, uno por grafema (👩‍⚖️ o 🇪🇸 cuentan como uno)."""
    return [g for g in regex.findall(r"\X", linea) if not g.isspace()]


def ruta_noto(grafema):
    """Dónde está el PNG de ese emoji en el repositorio de Noto."""
    puntos = [ord(c) for c in grafema]
    if len(puntos) == 2 and all(p in INDICADOR for p in puntos):
        pais = "".join(chr(p - 0x1F1E6 + ord("A")) for p in puntos)
        return f"third_party/region-flags/png/{pais}.png"
    codigos = "_".join(f"{p:04x}" for p in puntos if p != 0xFE0F)
    return f"2D/png/128/emoji_u{codigos}.png"


def imagen_emoji(grafema, sesion):
    """El PNG del emoji (de la caché o de Noto), o None si Noto no lo tiene."""
    ruta = ruta_noto(grafema)
    local = CACHE / ruta.replace("/", "_")
    falta = local.with_suffix(".no")
    if falta.exists():
        return None
    if not local.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        r = sesion.get(f"{NOTO}/{ruta}", timeout=20)
        if r.status_code == 404:
            falta.touch()
            return None
        r.raise_for_status()
        local.write_bytes(r.content)
    return Image.open(local).convert("RGBA")


def duotono(img):
    """Grises llevados a la rampa noche-cian, conservando la transparencia."""
    alfa = img.getchannel("A").point(lambda a: round(a * OPACIDAD))
    tono = ImageOps.colorize(ImageOps.grayscale(img.convert("RGB")), black=NOCHE, white=CIAN).convert("RGBA")
    tono.putalpha(alfa)
    return tono


def encajar(img, lado):
    """Reduce a un cuadrado de `lado` sin deformar (las banderas son apaisadas)."""
    img.thumbnail((lado, lado), Image.LANCZOS)
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    lienzo.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2), img)
    return lienzo


def casillas_libres():
    """Las casillas en orden de lectura, sin las de la marca."""
    ancho, alto = MARCA
    for fila in range(COLUMNAS):
        for col in range(COLUMNAS):
            if fila >= COLUMNAS - alto and col >= COLUMNAS - ancho:
                continue
            yield col, fila


def secuencia(lineas):
    """Emojis en orden, con None como hueco entre párrafos."""
    for i, linea in enumerate(lineas):
        trozos = emojis_de(linea)
        if not trozos:
            continue
        if i:
            yield None
        yield from trozos


def neon(lienzo):
    """«Cátodo.» en neón dentro del recuadro reservado."""
    ancho, alto = MARCA[0] * CASILLA, MARCA[1] * CASILLA
    x0, y0 = LADO - ancho, LADO - alto
    texto = "Cátodo."
    tam = 300
    fuente = ImageFont.truetype(str(FUENTE), tam)
    while fuente.getbbox(texto)[2] > ancho * 0.82:
        tam -= 10
        fuente = ImageFont.truetype(str(FUENTE), tam)
    caja = fuente.getbbox(texto)
    x = x0 + (ancho - (caja[2] - caja[0])) // 2 - caja[0]
    y = y0 + (alto - (caja[3] - caja[1])) // 2 - caja[1]
    capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((x, y), texto, font=fuente, fill=CIAN)
    for radio, veces in ((90, 2), (45, 2), (20, 2), (8, 2), (3, 1)):
        halo = capa.filter(ImageFilter.GaussianBlur(radio))
        for _ in range(veces):
            lienzo.alpha_composite(halo)
    ImageDraw.Draw(lienzo).text((x, y), texto, font=fuente, fill=NUCLEO)


def generar(lineas, salida):
    lienzo = Image.new("RGBA", (LADO, LADO), NOCHE)
    sesion = requests.Session()
    margen = (CASILLA - EMOJI) // 2
    puestos = saltados = 0
    libres = casillas_libres()
    for grafema in secuencia(lineas):
        if grafema is None:
            if next(libres, None) is None:
                break
            continue
        img = imagen_emoji(grafema, sesion)
        if img is None:
            saltados += 1
            continue
        sitio = next(libres, None)
        if sitio is None:
            break
        col, fila = sitio
        lienzo.alpha_composite(duotono(encajar(img, EMOJI)), (col * CASILLA + margen, fila * CASILLA + margen))
        puestos += 1
    neon(lienzo)
    final = lienzo.convert("RGB")
    final.save(salida, "JPEG", quality=85, optimize=True, progressive=True)
    # Versión ligera para la web (la grande va al feed, como piden Apple y Spotify).
    final.resize((WEB, WEB), Image.LANCZOS).save(salida.with_name("portada-web.jpg"), "JPEG", quality=82,
                                                  optimize=True, progressive=True)
    return puestos, saltados


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fecha", required=True)
    p.add_argument("--emojis", help="fichero de emojis (por defecto, episodes/FECHA/emojis.txt)")
    args = p.parse_args()
    carpeta = EPISODIOS / args.fecha
    origen = Path(args.emojis) if args.emojis else carpeta / "emojis.txt"
    if not origen.exists():
        sys.exit(f"No encuentro {origen}")
    salida = carpeta / "portada.jpg"
    puestos, saltados = generar(origen.read_text(encoding="utf-8").splitlines(), salida)
    total = COLUMNAS * COLUMNAS - MARCA[0] * MARCA[1]
    print(f"Portada: {salida} ({puestos} emojis de {total} casillas; {saltados} sin dibujo en Noto, "
          f"{salida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
