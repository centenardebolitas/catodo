"""Fase 4: genera el feed RSS del podcast y las páginas de la web en docs/.

Uso:
    python src/feed.py

Recorre los episodios publicados (los que tienen episodes/AAAA-MM-DD/publicacion.json,
que escribe publish.py) y regenera:
  - docs/feed.xml: RSS de podcast válido para Apple Podcasts y Spotify;
  - docs/index.html: portada con la lista de episodios;
  - docs/episodios/AAAA-MM-DD.html: una página por episodio con notas y transcripción.
"""

import hashlib
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
        capitulos = carpeta / "capitulos.json"
        datos["capitulos"] = (json.loads(capitulos.read_text(encoding="utf-8"))["chapters"]
                              if capitulos.exists() else [])
        episodios.append(datos)
    return episodios


def duracion_hms(segundos):
    s = int(round(segundos))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fecha_rfc(iso):
    return format_datetime(datetime.fromisoformat(iso))


def marca(segundos):
    """0:41 o 1:02:05, como se escriben los capítulos en las notas."""
    s = int(segundos)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def hms(segundos):
    """00:00:41.250, para Podlove Simple Chapters."""
    ms = round(segundos * 1000)
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}.{ms % 1000:03d}"


def capitulos_texto(ep):
    """Los capítulos en las notas del feed: Apple los hace pulsables y Spotify los usa si no hay otros."""
    if not ep.get("capitulos"):
        return ""
    lineas = "<br>".join(f"{marca(c['startTime'])} {html.escape(c['title'])}" for c in ep["capitulos"])
    return f"<p><strong>Capítulos</strong><br>{lineas}</p>"


def descripcion_episodio(ep, cfg, capitulos=True):
    cuerpo = (capitulos_texto(ep) + "\n" if capitulos and ep.get("capitulos") else "") + md_a_html(ep["notas_md"], nivel_titulos=3)
    if "inteligencia artificial" not in ep["notas_md"].lower():
        cuerpo += f"\n<p>{html.escape(cfg['aviso_ia'])}</p>"
    return cuerpo


# ---------------------------------------------------------------- feed RSS


def capitulos_feed(ep, web):
    """Capítulos en el feed: JSON de Podcasting 2.0 (enlazado) y Podlove Simple Chapters (Spotify)."""
    if not ep.get("capitulos"):
        return ""
    psc = "\n".join(f'        <psc:chapter start="{hms(c["startTime"])}" title="{escape(c["title"], {chr(34): "&quot;"})}"/>'
                    for c in ep["capitulos"])
    return (f'      <podcast:chapters url="{web}/episodios/{ep["fecha"]}-capitulos.json" type="application/json+chapters"/>\n'
            f'      <psc:chapters version="1.2">\n{psc}\n      </psc:chapters>')


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
      {f'<itunes:image href="{escape(ep["url_portada"])}"/>' if ep.get("url_portada") else ""}
{capitulos_feed(ep, web)}
      <itunes:duration>{duracion_hms(ep['duracion_s'])}</itunes:duration>
      <itunes:episode>{ep['numero']}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>{'true' if cfg['explicito'] else 'false'}</itunes:explicit>
    </item>""")
    ultima = fecha_rfc(episodios[0]["publicado_en"]) if episodios else format_datetime(datetime.now().astimezone())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:psc="http://podlove.org/simple-chapters">
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
  :root { color-scheme:dark; --fondo:#0e0d13; --texto:#ecece8; --suave:#9a9aa8; --acento:#22d3ee; --borde:#25242e; --caja:#16151d; }
  html { background:var(--fondo); }
  body { margin:0; background:var(--fondo); color:var(--texto); font-family:system-ui,-apple-system,sans-serif;
         line-height:1.6; padding:0 16px; }
  main { max-width:680px; margin:48px auto 64px; }
  a { color:var(--acento); }
  h1 { font-size:clamp(2.2rem,7vw,3.4rem); margin:0; letter-spacing:-0.02em; }
  h1 span { color:var(--acento); }
  @font-face { font-family:'Tilt Neon'; font-style:normal; font-weight:400; font-display:swap;
               src:url(/fuentes/tilt-neon-latin.woff2) format('woff2'); }
  .neon { font-family:'Tilt Neon',system-ui,sans-serif; font-weight:400; letter-spacing:0; color:#e8feff; text-shadow:0 0 4px #22d3ee,0 0 12px #22d3ee,0 0 30px rgba(34,211,238,.6),0 0 70px rgba(34,211,238,.35); }
  .suave { color:var(--suave); }
  .episodio { padding:20px 0; border-top:1px solid var(--borde); }
  .episodio h2 { font-size:1.15rem; margin:0 0 4px; }
  audio { width:100%; margin:10px 0; }
  footer { margin-top:48px; font-size:0.85rem; color:var(--suave); }
  footer a { color:var(--suave); }
  details summary { cursor:pointer; color:var(--suave); margin-top:24px; }
  .con-portada { display:grid; grid-template-columns:112px 1fr; gap:0 18px; align-items:start; }
  .con-portada .mini { grid-row:span 2; display:block; }
  .con-portada .mini img { width:112px; height:112px; border-radius:12px; display:block; }
  .con-portada audio { grid-column:1 / -1; }
  .portada-ep { display:block; width:100%; max-width:440px; border-radius:16px; margin:18px 0 12px;
                box-shadow:0 0 40px rgba(34,211,238,.18); }

  .insignias { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:18px 0 20px; }  /* abajo, lo mismo que hay bajo la raya (.episodio) */
  .insignias a { display:block; line-height:0; }
  .insignias img { height:40px; width:auto; }
  .insignias .texto { line-height:1.2; color:var(--acento); text-decoration:none; border:1px solid var(--acento);
                      border-radius:8px; padding:9px 14px; font-size:0.95rem; }
  .episodio-insignias { margin:6px 0 4px; }
  .episodio-insignias img { height:34px; }
  .capitulos { list-style:none; padding:0; margin:18px 0; }
  .capitulos li { margin:4px 0; }
  .capitulos button { font:inherit; font-variant-numeric:tabular-nums; color:var(--acento); background:none;
                      border:1px solid var(--borde); border-radius:6px; padding:1px 8px; margin-right:10px; cursor:pointer; }
  .capitulos button:hover { border-color:var(--acento); }
"""


# Favicon e iconos (assets/favicon/generar.py). Copiados tal cual en docs/sobre.html y docs/legal.html.
ICONOS = """<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" href="/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0e0d13">"""


def con_version(ruta):
    """/insignias/x.svg?v=huella: si cambia el fichero, cambia la URL y nadie ve la vieja en caché."""
    fichero = DOCS / ruta.lstrip("/")
    if not ruta.startswith("/") or not fichero.exists():
        return ruta
    return f"{ruta}?v={hashlib.sha256(fichero.read_bytes()).hexdigest()[:8]}"


def insignias(cfg, ep=None, clase="insignias"):
    """Las insignias oficiales de config/podcast.yaml (escuchar), en el orden que piden (Apple primero).

    Con un episodio, Apple enlaza al episodio si ya sabemos su enlace (url_apple)."""
    enlaces = []
    for p in cfg.get("escuchar") or []:
        url = p["url"]
        if ep and p["nombre"] == "Apple Podcasts" and ep.get("url_apple"):
            url = ep["url_apple"]
        if ep and p["nombre"] == "Spotify" and ep.get("url_spotify"):
            url = ep["url_spotify"]
        texto = p.get("texto") or f"Escúchalo en {p['nombre']}"
        if p.get("insignia"):
            enlaces.append(f'<a href="{html.escape(url)}"><img src="{html.escape(con_version(p["insignia"]))}" '
                           f'alt="{html.escape(texto)}"></a>')
        else:
            enlaces.append(f'<a class="texto" href="{html.escape(url)}">{html.escape(texto)}</a>')
    return f'<nav class="{clase}" aria-label="Dónde escucharlo">{"".join(enlaces)}</nav>'


def enlaces_escuchar(cfg):
    """Las plataformas de config/podcast.yaml (escuchar), con el feed RSS siempre."""
    enlaces = [(p["nombre"], p["url"]) for p in cfg.get("escuchar") or []]
    return enlaces if any(url == "/feed.xml" for _, url in enlaces) else enlaces + [("Feed RSS", "/feed.xml")]


def plantilla(titulo, descripcion, cuerpo, cfg, raiz="", imagen=None, url=None):
    web = cfg["web"].rstrip("/")
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(descripcion)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(cfg['titulo'])}">
<meta property="og:title" content="{html.escape(titulo)}">
<meta property="og:description" content="{html.escape(descripcion)}">
<meta property="og:image" content="{html.escape(imagen or cfg['imagen'])}">
<meta property="og:url" content="{html.escape(url or web + '/')}">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{html.escape(cfg['titulo'])}" href="/feed.xml">
{ICONOS}
<style>{ESTILO}</style>
</head>
<body>
<main>
{cuerpo}
  <footer>{html.escape(cfg['aviso_ia'])}<br>
  {' · '.join(f'<a href="{html.escape(url)}">{html.escape(nombre)}</a>' for nombre, url in enlaces_escuchar(cfg))}<br>
  <a href="/sobre.html">De dónde sale Cátodo</a> · <a href="/legal.html">Aviso legal y privacidad</a> · <a href="mailto:{cfg['email']}">{cfg['email']}</a></footer>
</main>
</body>
</html>
"""


def generar_portada(episodios, cfg):
    lista = []
    for ep in episodios:
        pagina = f"/episodios/{ep['fecha']}.html"
        mini = (f'<a class="mini" href="{pagina}"><img src="{html.escape(ep.get("url_portada_web") or ep["url_portada"])}" '
                f'alt="" width="112" height="112"></a>\n    ' if ep.get("url_portada") else "")
        lista.append(f"""  <article class="episodio{' con-portada' if mini else ''}">
    {mini}<h2><a href="{pagina}">{html.escape(ep['titulo'])}</a></h2>
    <div class="suave">{ep['fecha']} · {int(ep['duracion_s'] // 60)} min</div>
    <audio controls preload="none" src="{html.escape(ep['url_audio'])}"></audio>
  </article>""")
    cuerpo = f"""  <h1 class="neon">Cátodo.</h1>
  <p class="suave">{html.escape(cfg['subtitulo'])}. {html.escape(cfg['descripcion'])}</p>
  {insignias(cfg)}
{chr(10).join(lista) if lista else '  <p>Muy pronto, el primer episodio.</p>'}"""
    return plantilla(cfg["titulo"], cfg["descripcion"], cuerpo, cfg)


def generar_pagina_episodio(ep, cfg):
    transcripcion = md_a_html(ep["guion_md"], nivel_titulos=3)
    cuerpo = f"""  <p><a href="/">← Cátodo</a></p>
  <h1 style="font-size:1.8rem">{html.escape(ep['titulo'])}</h1>
  <div class="suave">{ep['fecha']} · {int(ep['duracion_s'] // 60)} min</div>
  {portada_html(ep)}<audio id="audio" controls preload="metadata" src="{html.escape(ep['url_audio'])}"></audio>
  {insignias(cfg, ep, "insignias episodio-insignias")}
  {capitulos_html(ep)}{descripcion_episodio(ep, cfg, capitulos=False)}
  <details><summary>Transcripción</summary>
  {transcripcion}
  </details>"""
    return plantilla(f"{ep['titulo']} · Cátodo", ep["titulo"], cuerpo, cfg, imagen=ep.get("url_portada"),
                     url=f"{cfg['web'].rstrip('/')}/episodios/{ep['fecha']}.html")


def capitulos_html(ep):
    """Los capítulos en la web: cada marca salta a ese punto del audio."""
    if not ep.get("capitulos"):
        return ""
    filas = "\n".join(f'    <li><button type="button" data-t="{c["startTime"]}">{marca(c["startTime"])}</button>'
                      f'{html.escape(c["title"])}</li>' for c in ep["capitulos"])
    return f"""<ol class="capitulos" aria-label="Capítulos">
{filas}
  </ol>
  <script>
  document.querySelectorAll('.capitulos [data-t]').forEach(b => b.addEventListener('click', () => {{
    const a = document.getElementById('audio'); a.currentTime = parseFloat(b.dataset.t); a.play();
  }}));
  </script>
  """


def portada_html(ep):
    """La portada del episodio (el guion en emojis), si la tiene."""
    if not ep.get("url_portada"):
        return ""
    # Sin explicación a propósito: que sea un huevo de pascua para quien se fije.
    return (f'<img class="portada-ep" src="{html.escape(ep.get("url_portada_web") or ep["url_portada"])}" '
            f'width="440" height="440" alt="Portada del episodio">\n  ')


def generar_todo(destino=DOCS):
    cfg = cargar_yaml("podcast.yaml")
    episodios = episodios_publicados()
    (destino / "episodios").mkdir(parents=True, exist_ok=True)
    (destino / "feed.xml").write_text(generar_feed(episodios, cfg), encoding="utf-8")
    (destino / "index.html").write_text(generar_portada(episodios, cfg), encoding="utf-8")
    for ep in episodios:
        (destino / "episodios" / f"{ep['fecha']}.html").write_text(generar_pagina_episodio(ep, cfg), encoding="utf-8")
        if ep.get("capitulos"):  # lo que enlaza <podcast:chapters>
            (destino / "episodios" / f"{ep['fecha']}-capitulos.json").write_text(
                json.dumps({"version": "1.2.0", "chapters": ep["capitulos"]}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
    return episodios


def main():
    episodios = generar_todo()
    print(f"Feed y web regenerados con {len(episodios)} episodios: docs/feed.xml, docs/index.html, docs/episodios/")


if __name__ == "__main__":
    main()
