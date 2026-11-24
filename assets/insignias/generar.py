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
    """El icono de feed de siempre (naranja, punto y dos arcos)."""
    x, y, l = ICONO_X, ICONO_Y, ICONO_LADO
    return (f'<rect x="{x}" y="{y}" width="{l}" height="{l}" rx="6" fill="#F78422"/>\n'
            f'  <g transform="translate({x + 6.2} {y + 6.2}) scale(0.0533)" fill="#fff">'
            f'<circle cx="45" cy="205" r="45"/>'
            f'<path d="M0 85v60a105 105 0 0 1 105 105h60A165 165 0 0 0 0 85z"/>'
            f'<path d="M0 0v60a190 190 0 0 1 190 190h60A250 250 0 0 0 0 0z"/></g>')


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "spotify.svg").write_text(insignia(icono_spotify(), "Escúchalo en", "Spotify", "Escúchalo en Spotify"),
                                      encoding="utf-8")
    (DOCS / "rss.svg").write_text(insignia(icono_rss(), "Suscríbete por", "RSS", "Suscríbete por RSS"),
                                  encoding="utf-8")
    print("Insignias en docs/insignias/: spotify.svg, rss.svg")


if __name__ == "__main__":
    main()
