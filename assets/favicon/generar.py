"""Genera el favicon de Cátodo, con el mismo neón cian que la portada (n1-cian).

Uso:
    python assets/favicon/generar.py            # variantes y hoja comparativa
    python assets/favicon/generar.py f1-c-punto # iconos finales de esa variante en docs/

Cada variante se dibuja a 512x512 con Chrome sin interfaz (tipografía Tilt Neon,
Google Fonts, licencia OFL) y se reduce con `sips` (macOS). Los iconos finales:
favicon.ico (32 px, con ffmpeg), favicon-32.png, apple-touch-icon.png (180 px)
e icon-512.png.
"""

import subprocess
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
DOCS = CARPETA.parent.parent / "docs"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FUENTE = '<link href="https://fonts.googleapis.com/css2?family=Tilt+Neon&display=block" rel="stylesheet">'
CIAN, NUCLEO = "#22d3ee", "#e8feff"


def halo(color, escala=1.0):
    return ",".join(f"0 0 {round(r * escala)}px {color}" for r in (2, 6, 14, 30, 56))


def pagina(texto, tam, grosor=0, desplazar_y=0):
    """Letra de neón centrada sobre la misma pared oscura de la portada.

    grosor: trazo extra (px) para que la letra no desaparezca a 16 px.
    """
    trazo = f"-webkit-text-stroke:{grosor}px {NUCLEO};" if grosor else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTE}<style>
html,body{{margin:0;width:512px;height:512px;overflow:hidden}}
body{{display:flex;align-items:center;justify-content:center;
  background:radial-gradient(ellipse at 50% 45%,#1d1b26 0%,#0e0d13 60%,#060509 100%)}}
.m{{font-family:'Tilt Neon';font-size:{tam}px;line-height:1;color:{NUCLEO};{trazo}
  text-shadow:{halo(CIAN)};transform:translateY({desplazar_y}px)}}
.p{{color:#fff6fb}}
</style></head><body><div class="m">{texto}</div></body></html>"""


VARIANTES = {
    "f1-c-punto": pagina('C<span class="p">.</span>', 400, grosor=6, desplazar_y=-10),
    "f2-c": pagina("C", 440, grosor=8, desplazar_y=-14),
    "f3-c-minuscula": pagina('c<span class="p">.</span>', 470, grosor=8, desplazar_y=-60),
}


def chrome(html_path, png, ancho, alto, extra=()):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", *extra,
                    "--force-device-scale-factor=1", f"--window-size={ancho},{alto}",
                    "--virtual-time-budget=6000", f"--screenshot={png}", html_path.as_uri()],
                   check=True, capture_output=True)


def renderizar(nombre, html):
    fuente = CARPETA / f"variante-{nombre}.html"
    fuente.write_text(html, encoding="utf-8")
    png = CARPETA / f"variante-{nombre}.png"
    chrome(fuente, png, 512, 512)
    fuente.unlink()
    return png


def reducir(png, lado, destino):
    subprocess.run(["sips", "-z", str(lado), str(lado), str(png), "--out", str(destino)],
                   check=True, capture_output=True)
    return destino


def comparativa(pngs):
    """Cada variante a 180, 32 y 16 px, sobre pestaña clara y oscura, como en el navegador."""
    filas = []
    for png in pngs:
        p16 = reducir(png, 16, CARPETA / f"{png.stem}-16.png")
        p32 = reducir(png, 32, CARPETA / f"{png.stem}-32.png")
        filas.append(f"""<div class="fila"><img class="g" src="{png.as_uri()}">
  <div class="pest claro"><img src="{p16.as_uri()}" width="16"> Cátodo</div>
  <div class="pest oscuro"><img src="{p16.as_uri()}" width="16"> Cátodo</div>
  <img src="{p32.as_uri()}" width="32"><img src="{p32.as_uri()}" width="64" style="image-rendering:pixelated">
  <span>{png.stem.replace('variante-', '')}</span></div>""")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;padding:30px;background:#e9e9e4;font:600 20px system-ui;width:1040px}}
.fila{{display:flex;align-items:center;gap:28px;margin-bottom:28px}}
.g{{width:180px;height:180px;border-radius:40px}}
.pest{{display:flex;align-items:center;gap:8px;font:400 13px system-ui;padding:8px 14px;border-radius:8px 8px 0 0;width:150px}}
.claro{{background:#fff;color:#222}} .oscuro{{background:#35363a;color:#eee}}</style></head><body>{''.join(filas)}</body></html>"""
    fuente = CARPETA / "comparativa.html"
    fuente.write_text(html, encoding="utf-8")
    salida = CARPETA / "comparativa.png"
    chrome(fuente, salida, 1100, 60 + len(pngs) * 208, extra=("--allow-file-access-from-files",))
    fuente.unlink()
    return salida


def finales(nombre):
    png = renderizar(nombre, VARIANTES[nombre])
    reducir(png, 512, DOCS / "icon-512.png")
    reducir(png, 180, DOCS / "apple-touch-icon.png")
    p32 = reducir(png, 32, DOCS / "favicon-32.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p32), str(DOCS / "favicon.ico")], check=True)
    print("Iconos en docs/: favicon.ico, favicon-32.png, apple-touch-icon.png, icon-512.png")


def main():
    if len(sys.argv) > 1:
        finales(sys.argv[1])
        return
    pngs = [renderizar(n, h) for n, h in VARIANTES.items()]
    print("Comparativa:", comparativa(pngs))


if __name__ == "__main__":
    main()
