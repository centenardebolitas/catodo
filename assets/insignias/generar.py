"""Insignias de Spotify y del feed RSS con el mismo formato que la oficial de Apple.

Uso:
    python assets/insignias/generar.py

La de Apple (docs/insignias/apple-podcasts.svg) es la oficial, tal cual la da Apple
(toolbox.marketingtools.apple.com). Spotify ya no da insignia descargable, así que la
suya se compone como era su insignia oficial: su icono (el oficial, del kit de prensa
de newsroom.spotify.com, sin modificar) y el texto «Escúchalo en / Spotify». La del RSS
lleva el icono de feed de siempre. Las tres miden 40 de alto, con el mismo marco, la
misma posición del icono y los mismos tamaños de letra que la de Apple.
"""

import base64
import io
from pathlib import Path

import requests
from PIL import Image, ImageFont

CARPETA = Path(__file__).resolve().parent
DOCS = CARPETA.parent.parent / "docs" / "insignias"
ICONO_SPOTIFY = "https://storage.googleapis.com/pr-newsroom-wp/1/2023/05/Spotify_Primary_Logo_RGB_Green.png"
LETRA = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MEDIR = "/System/Library/Fonts/Helvetica.ttc"  # para calcular el ancho (en la web sale la del sistema)

# Medidas de la insignia de Apple (viewBox 164.86 x 40).
ALTO, ICONO_X, ICONO_Y, ICONO_LADO = 40, 8, 7, 26
TEXTO_X, PEQUENO_Y, PEQUENO_TAM, GRANDE_Y, GRANDE_TAM = 39.5, 15.2, 8.4, 31.2, 17.8


def ancho_texto(texto, tam):
    return ImageFont.truetype(MEDIR, round(tam * 10)).getlength(texto) / 10


def insignia(icono_svg, pequeno, grande, titulo):
    ancho = round(TEXTO_X + max(ancho_texto(grande, GRANDE_TAM) * 1.06, ancho_texto(pequeno, PEQUENO_TAM)) + 11, 2)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{ancho}" height="{ALTO}" viewBox="0 0 {ancho} {ALTO}">
  <title>{titulo}</title>
  <rect x="0.5" y="0.5" width="{ancho - 1}" height="{ALTO - 1}" rx="8" fill="#000" stroke="#A6A6A6"/>
  {icono_svg}
  <text x="{TEXTO_X}" y="{PEQUENO_Y}" fill="#fff" font-family="{LETRA}" font-size="{PEQUENO_TAM}">{pequeno}</text>
  <text x="{TEXTO_X - 0.6}" y="{GRANDE_Y}" fill="#fff" font-family="{LETRA}" font-size="{GRANDE_TAM}" font-weight="400" letter-spacing="-0.2">{grande}</text>
</svg>
'''


def icono_spotify():
    img = Image.open(io.BytesIO(requests.get(ICONO_SPOTIFY, timeout=30).content)).convert("RGBA")
    img = img.crop(img.getbbox()).resize((ICONO_LADO * 4, ICONO_LADO * 4), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    datos = base64.b64encode(buf.getvalue()).decode()
    return (f'<!-- Icono oficial de Spotify (kit de prensa), sin modificar -->\n  '
            f'<image x="{ICONO_X}" y="{ICONO_Y}" width="{ICONO_LADO}" height="{ICONO_LADO}" '
            f'xlink:href="data:image/png;base64,{datos}"/>')


def icono_rss():
    """El icono de feed de siempre (el de Mozilla, de uso libre): cuadrado naranja con
    degradado, punto y dos arcos, en su proporción original (lienzo de 256)."""
    x, y, l = ICONO_X, ICONO_Y, ICONO_LADO
    return (f'<defs><linearGradient id="rss" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="#F9A243"/><stop offset="1" stop-color="#E8591F"/></linearGradient></defs>\n'
            f'  <g transform="translate({x} {y}) scale({l / 256})">'
            f'<rect width="256" height="256" rx="58" fill="url(#rss)"/>'
            f'<circle cx="68" cy="189" r="24" fill="#fff"/>'
            f'<path d="M160 213h-34a82 82 0 0 0-82-82V97a116 116 0 0 1 116 116z" fill="#fff"/>'
            f'<path d="M184 213A140 140 0 0 0 44 73V38a175 175 0 0 1 175 175z" fill="#fff"/></g>')


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "spotify.svg").write_text(insignia(icono_spotify(), "Escúchalo en", "Spotify", "Escúchalo en Spotify"),
                                      encoding="utf-8")
    (DOCS / "rss.svg").write_text(insignia(icono_rss(), "Suscríbete por", "RSS", "Suscríbete por RSS"),
                                  encoding="utf-8")
    print("Insignias en docs/insignias/: spotify.svg, rss.svg")


if __name__ == "__main__":
    main()
