"""Genera las variantes de portada de Cátodo (3000x3000) con Chrome sin interfaz.

Uso:
    python assets/portada/generar.py

Cada variante es una página HTML con la tipografía Space Grotesk (Google Fonts,
licencia OFL). Se renderiza a PNG y se convierte a JPEG con `sips` (macOS).
Deja variante-*.jpg y comparativa.png en esta carpeta.
"""

import subprocess
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FUENTE = '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=block" rel="stylesheet">'

BASE = """<!doctype html><html><head><meta charset="utf-8">{fuente}<style>
html,body{{margin:0;width:3000px;height:3000px;overflow:hidden}}
body{{font-family:'Space Grotesk',sans-serif;display:flex;align-items:center;justify-content:center;position:relative}}
.marca{{font-weight:700;font-size:640px;letter-spacing:-0.045em;line-height:1}}
.sub{{font-weight:500;font-size:150px;letter-spacing:-0.01em;margin-top:70px}}
.bloque{{position:relative;z-index:2;text-align:left}}
{extra}
</style></head><body>{cuerpo}</body></html>"""

VARIANTES = {
    "a-noche": dict(
        extra="body{background:#141413;color:#ecece8}.punto{color:#fb923c}.sub{color:#9a9a94}",
        cuerpo='<div class="bloque"><div class="marca">Cátodo<span class="punto">.</span></div>'
               '<div class="sub">tecnología cada mañana</div></div>'),
    "b-papel": dict(
        extra="body{background:#fafaf7;color:#1d1d1b}.punto{color:#c2410c}.sub{color:#6b6b66}",
        cuerpo='<div class="bloque"><div class="marca">Cátodo<span class="punto">.</span></div>'
               '<div class="sub">tecnología cada mañana</div></div>'),
    "c-crt": dict(
        extra="""body{background:#0b0b0a}
.pantalla{position:absolute;inset:230px;border-radius:260px;background:radial-gradient(ellipse at center,#2a1a0e 0%,#120c07 70%,#070505 100%);
  box-shadow:inset 0 0 220px rgba(0,0,0,.9), 0 0 0 40px #1c1c1a, 0 0 0 46px #2c2c2a}
.pantalla::after{content:'';position:absolute;inset:0;border-radius:260px;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.28) 0 6px,transparent 6px 14px)}
.marca{color:#ffb070;text-shadow:0 0 40px rgba(251,146,60,.85),0 0 120px rgba(251,146,60,.55),0 0 260px rgba(194,65,12,.5)}
.sub{color:#f3a56a;opacity:.85;text-shadow:0 0 30px rgba(251,146,60,.6)}""",
        cuerpo='<div class="pantalla"></div><div class="bloque"><div class="marca">Cátodo.</div>'
               '<div class="sub">tecnología cada mañana</div></div>'),
    "d-haz": dict(
        extra="""body{background:#c2410c;color:#fff8f0}
.haz{position:absolute;left:0;top:0;width:3000px;height:3000px;z-index:1}
.sub{color:#ffd9bd}""",
        cuerpo="""<svg class="haz" viewBox="0 0 3000 3000"><defs>
<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".55"/></linearGradient></defs>
<g stroke="url(#g)" stroke-width="10" fill="none">
<path d="M-50 600 C 900 700, 1700 1150, 2540 1560"/><path d="M-50 1000 C 900 1050, 1700 1350, 2540 1560"/>
<path d="M-50 1500 C 900 1500, 1700 1540, 2540 1560"/><path d="M-50 2000 C 900 1950, 1700 1760, 2540 1560"/>
<path d="M-50 2400 C 900 2300, 1700 1950, 2540 1560"/></g>
<circle cx="2540" cy="1560" r="70" fill="#fff"/><circle cx="2540" cy="1560" r="170" fill="#fff" opacity=".18"/></svg>
<div class="bloque" style="margin-right:520px"><div class="marca">Cátodo</div><div class="sub">tecnología cada mañana</div></div>"""),
}


FUENTE_NEON = ('<link href="https://fonts.googleapis.com/css2?family=Tilt+Neon&family=Neonderthaw'
               '&display=block" rel="stylesheet">')


def neon(color, nucleo, fuente="'Tilt Neon'", tam=600, punto=None, sub_color=None, inclinacion=0):
    """Cartel de neón: núcleo casi blanco y halo del color, sobre una pared oscura."""
    def halo(c):
        return ",".join(f"0 0 {r}px {c}" for r in (6, 16, 40, 90, 170, 300))
    punto = punto or color
    sub_color = sub_color or color
    extra = f"""
body{{background:radial-gradient(ellipse at 50% 45%,#1d1b26 0%,#0e0d13 55%,#060509 100%)}}
body::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 46%,{color}26 0%,transparent 48%)}}
.marca{{font-family:{fuente};font-weight:400;font-size:{tam}px;letter-spacing:0;color:{nucleo};text-shadow:{halo(color)};
  transform:rotate({inclinacion}deg)}}
.punto{{color:#fff6fb;text-shadow:{halo(punto)}}}
.sub{{font-family:'Tilt Neon';font-weight:400;font-size:140px;color:{nucleo};opacity:.92;text-shadow:{halo(sub_color)};margin-top:110px}}
.bloque{{text-align:center}}"""
    cuerpo = ('<div class="bloque"><div class="marca">Cátodo<span class="punto">.</span></div>'
              '<div class="sub">tecnología cada mañana</div></div>')
    return dict(extra=extra, cuerpo=cuerpo)


VARIANTES_NEON = {
    "n1-cian": neon("#22d3ee", "#e8feff"),
    "n2-rosa": neon("#ff3fb4", "#fff0f8"),
    "n3-verde": neon("#3dff8a", "#efffef"),
    "n4-violeta": neon("#a855f7", "#f6eeff"),
    "n5-manuscrita-rosa": neon("#ff3fb4", "#fff0f8", "'Neonderthaw'", tam=900, inclinacion=-4),
    "n6-bicolor": neon("#22d3ee", "#e8feff", punto="#ff3fb4", sub_color="#ff3fb4"),
}


def renderizar(nombre, html):
    fuente = CARPETA / f"variante-{nombre}.html"
    fuente.write_text(html, encoding="utf-8")
    png = CARPETA / f"variante-{nombre}.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--window-size=3000,3000",
                    "--virtual-time-budget=8000", f"--screenshot={png}", fuente.as_uri()],
                   check=True, capture_output=True)
    jpg = CARPETA / f"variante-{nombre}.jpg"
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90", str(png), "--out", str(jpg)],
                   check=True, capture_output=True)
    png.unlink()
    fuente.unlink()
    return jpg


def comparativa(jpgs):
    """Una hoja con cada variante en grande y en miniatura, como se ven en las apps."""
    filas = "".join(
        f'<div class="fila"><img class="g" src="{j.as_uri()}"><img class="m" src="{j.as_uri()}">'
        f'<img class="xs" src="{j.as_uri()}"><span>{j.stem.replace("variante-", "")}</span></div>'
        for j in jpgs)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;padding:40px;background:#e9e9e4;font:600 28px system-ui;width:1520px}}
.fila{{display:flex;align-items:flex-end;gap:40px;margin-bottom:40px}}
.g{{width:600px;height:600px}} .m{{width:180px;height:180px}} .xs{{width:60px;height:60px}}
img{{border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.25)}}</style></head><body>{filas}</body></html>"""
    fuente = CARPETA / "comparativa.html"
    fuente.write_text(html, encoding="utf-8")
    alto = 40 + len(jpgs) * 640 + 40
    salida = CARPETA / "comparativa.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                    "--force-device-scale-factor=1", f"--window-size=1600,{alto}", "--virtual-time-budget=4000",
                    f"--screenshot={salida}", fuente.as_uri()], check=True, capture_output=True)
    fuente.unlink()
    return salida


def main():
    import sys
    tanda_neon = len(sys.argv) > 1 and sys.argv[1] == "neon"
    variantes, fuente = (VARIANTES_NEON, FUENTE_NEON) if tanda_neon else (VARIANTES, FUENTE)
    jpgs = []
    for nombre, partes in variantes.items():
        html = BASE.format(fuente=fuente, **partes)
        jpgs.append(renderizar(nombre, html))
        print("Generada:", jpgs[-1].name)
    print("Comparativa:", comparativa(jpgs).name)


if __name__ == "__main__":
    main()
