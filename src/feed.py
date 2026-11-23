"""Fase 4: genera el feed RSS del podcast y las páginas de la web en docs/.

Uso:
    python src/feed.py

Recorre los episodios publicados (los que tienen episodes/AAAA-MM-DD/publicacion.json,
que escribe publish.py) y regenera:
  - docs/feed.xml: RSS de podcast válido para Apple Podcasts y Spotify;
  - docs/index.html: portada con la lista de episodios;
  - docs/episodios/AAAA-MM-DD.html: una página por episodio con notas y transcripción.
"""

import html
import json
import re
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape

from comun import EPISODIOS, RAIZ, cargar_yaml

DOCS = RAIZ / "docs"

# ---------------------------------------------------------------- Markdown mínimo


def _en_linea(texto):
    """Escapa HTML y convierte enlaces, negritas y cursivas de Markdown."""
    t = html.escape(texto, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
    return t


def md_a_html(texto, nivel_titulos=2):
    """Convierte el Markdown sencillo de notas y guiones a HTML."""
    bloques, parrafo = [], []

    def cerrar():
        if parrafo:
            bloques.append("<p>" + "<br>".join(_en_linea(l) for l in parrafo) + "</p>")
            parrafo.clear()

    for linea in texto.splitlines():
        s = linea.strip()
        cabecera = re.match(r"^(#{1,6})\s+(.*)$", s)
        if not s:
            cerrar()
        elif cabecera:
            cerrar()
            n = min(6, len(cabecera.group(1)) + nivel_titulos - 1)
            bloques.append(f"<h{n}>{_en_linea(cabecera.group(2))}</h{n}>")
        elif s in ("---", "***"):
            cerrar()
            bloques.append("<hr>")
        elif s.startswith(("- ", "* ")):
            cerrar()
            bloques.append(f"<p>• {_en_linea(s[2:])}</p>")
        else:
            parrafo.append(s)
    cerrar()
    return "\n".join(bloques)


# ---------------------------------------------------------------- episodios


def episodios_publicados():
    episodios = []
    for pub in sorted(EPISODIOS.glob("*/publicacion.json"), reverse=True):
        datos = json.loads(pub.read_text(encoding="utf-8"))
        carpeta = pub.parent
        notas = (carpeta / "notas.md").read_text(encoding="utf-8")
        titulo = re.search(r"(?m)^#\s+(.+)$", notas)
        datos["titulo"] = datos.get("titulo") or (titulo.group(1).strip() if titulo else f"Cátodo · {datos['fecha']}")
        datos["notas_md"] = re.sub(r"(?m)^#\s+.+$\n?", "", notas, count=1).strip()
        datos["guion_md"] = (carpeta / "guion.md").read_text(encoding="utf-8")
        episodios.append(datos)
    return episodios


def duracion_hms(segundos):
    s = int(round(segundos))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fecha_rfc(iso):
    return format_datetime(datetime.fromisoformat(iso))


def descripcion_episodio(ep, cfg):
    cuerpo = md_a_html(ep["notas_md"], nivel_titulos=3)
    if "inteligencia artificial" not in ep["notas_md"].lower():
        cuerpo += f"\n<p>{html.escape(cfg['aviso_ia'])}</p>"
    return cuerpo


# ---------------------------------------------------------------- feed RSS


def generar_feed(episodios, cfg):
    web = cfg["web"].rstrip("/")
    items = []
    for ep in episodios:
        pagina = f"{web}/episodios/{ep['fecha']}.html"
        items.append(f"""    <item>
      <title>{escape(ep['titulo'])}</title>
      <link>{pagina}</link>
      <guid isPermaLink="false">catodo-{ep['fecha']}</guid>
      <pubDate>{fecha_rfc(ep['publicado_en'])}</pubDate>
      <description><![CDATA[{descripcion_episodio(ep, cfg)}]]></description>
      <enclosure url="{escape(ep['url_audio'])}" length="{ep['bytes']}" type="audio/mpeg"/>
      <itunes:duration>{duracion_hms(ep['duracion_s'])}</itunes:duration>
      <itunes:episode>{ep['numero']}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>{'true' if cfg['explicito'] else 'false'}</itunes:explicit>
    </item>""")
    ultima = fecha_rfc(episodios[0]["publicado_en"]) if episodios else format_datetime(datetime.now().astimezone())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(cfg['titulo'])}</title>
    <link>{web}</link>
    <atom:link href="{web}/feed.xml" rel="self" type="application/rss+xml"/>
    <language>{cfg['idioma']}</language>
    <copyright>{escape(cfg['copyright'])}</copyright>
    <description>{escape(cfg['descripcion'])}</description>
    <lastBuildDate>{ultima}</lastBuildDate>
    <itunes:subtitle>{escape(cfg['subtitulo'])}</itunes:subtitle>
    <itunes:summary>{escape(cfg['descripcion'])}</itunes:summary>
    <itunes:author>{escape(cfg['autor'])}</itunes:author>
    <itunes:owner>
      <itunes:name>{escape(cfg['autor'])}</itunes:name>
      <itunes:email>{escape(cfg['email'])}</itunes:email>
    </itunes:owner>
    <itunes:image href="{escape(cfg['imagen'])}"/>
    <image><url>{escape(cfg['imagen'])}</url><title>{escape(cfg['titulo'])}</title><link>{web}</link></image>
    <itunes:category text="{escape(cfg['categoria'])}"><itunes:category text="{escape(cfg['subcategoria'])}"/></itunes:category>
    <itunes:explicit>{'true' if cfg['explicito'] else 'false'}</itunes:explicit>
    <itunes:type>episodic</itunes:type>
{chr(10).join(items)}
  </channel>
</rss>
"""


# ---------------------------------------------------------------- web

ESTILO = """
  :root { --fondo:#fafaf7; --texto:#1d1d1b; --suave:#6b6b66; --acento:#c2410c; --borde:#e4e4de; }
  @media (prefers-color-scheme: dark) {
    :root { --fondo:#141413; --texto:#ecece8; --suave:#9a9a94; --acento:#fb923c; --borde:#2c2c2a; } }
  body { margin:0; background:var(--fondo); color:var(--texto); font-family:system-ui,-apple-system,sans-serif;
         line-height:1.6; padding:0 16px; }
  main { max-width:680px; margin:48px auto 64px; }
  a { color:var(--acento); }
  h1 { font-size:clamp(2.2rem,7vw,3.4rem); margin:0; letter-spacing:-0.02em; }
  h1 span { color:var(--acento); }
  .suave { color:var(--suave); }
  .episodio { padding:20px 0; border-top:1px solid var(--borde); }
  .episodio h2 { font-size:1.15rem; margin:0 0 4px; }
  audio { width:100%; margin:10px 0; }
  footer { margin-top:48px; font-size:0.85rem; color:var(--suave); }
  footer a { color:var(--suave); }
  details summary { cursor:pointer; color:var(--suave); margin-top:24px; }
"""


def plantilla(titulo, descripcion, cuerpo, cfg, raiz=""):
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(descripcion)}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(cfg['titulo'])}" href="/feed.xml">
<style>{ESTILO}</style>
</head>
<body>
<main>
{cuerpo}
  <footer>{html.escape(cfg['aviso_ia'])}<br>
  <a href="/sobre.html">De dónde sale Cátodo</a> · <a href="/feed.xml">Feed RSS</a> · <a href="/legal.html">Aviso legal y privacidad</a> · <a href="mailto:{cfg['email']}">{cfg['email']}</a></footer>
</main>
</body>
</html>
"""


def generar_portada(episodios, cfg):
    lista = []
    for ep in episodios:
        lista.append(f"""  <article class="episodio">
    <h2><a href="/episodios/{ep['fecha']}.html">{html.escape(ep['titulo'])}</a></h2>
    <div class="suave">{ep['fecha']} · {int(ep['duracion_s'] // 60)} min</div>
    <audio controls preload="none" src="{html.escape(ep['url_audio'])}"></audio>
  </article>""")
    cuerpo = f"""  <h1>Cátodo<span>.</span></h1>
  <p class="suave">{html.escape(cfg['subtitulo'])}. {html.escape(cfg['descripcion'])}</p>
{chr(10).join(lista) if lista else '  <p>Muy pronto, el primer episodio.</p>'}"""
    return plantilla(cfg["titulo"], cfg["descripcion"], cuerpo, cfg)


def generar_pagina_episodio(ep, cfg):
    transcripcion = md_a_html(ep["guion_md"], nivel_titulos=3)
    cuerpo = f"""  <p><a href="/">← Cátodo</a></p>
  <h1 style="font-size:1.8rem">{html.escape(ep['titulo'])}</h1>
  <div class="suave">{ep['fecha']} · {int(ep['duracion_s'] // 60)} min</div>
  <audio controls preload="metadata" src="{html.escape(ep['url_audio'])}"></audio>
  {descripcion_episodio(ep, cfg)}
  <details><summary>Transcripción</summary>
  {transcripcion}
  </details>"""
    return plantilla(f"{ep['titulo']} · Cátodo", ep["titulo"], cuerpo, cfg)


def generar_todo(destino=DOCS):
    cfg = cargar_yaml("podcast.yaml")
    episodios = episodios_publicados()
    (destino / "episodios").mkdir(parents=True, exist_ok=True)
    (destino / "feed.xml").write_text(generar_feed(episodios, cfg), encoding="utf-8")
    (destino / "index.html").write_text(generar_portada(episodios, cfg), encoding="utf-8")
    for ep in episodios:
        (destino / "episodios" / f"{ep['fecha']}.html").write_text(generar_pagina_episodio(ep, cfg), encoding="utf-8")
    return episodios


def main():
    episodios = generar_todo()
    print(f"Feed y web regenerados con {len(episodios)} episodios: docs/feed.xml, docs/index.html, docs/episodios/")


if __name__ == "__main__":
    main()
