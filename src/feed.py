"""Fase 4: genera el feed RSS del podcast y las páginas de la web en docs/.

Uso:
    python src/feed.py

Recorre los episodios publicados (los que tienen episodes/AAAA-MM-DD/publicacion.json,
que escribe publish.py) y regenera:
  - docs/feed.xml: RSS de podcast válido para Apple Podcasts y Spotify;
  - docs/sitemap.xml: las páginas que debe indexar Google (sin legal.html);
  - docs/index.html: portada con la lista de episodios;
  - docs/episodios/AAAA-MM-DD.html: una página por episodio con notas y el guion completo.
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


def generar_sitemap(episodios, cfg):
    """docs/sitemap.xml para Search Console: portada, sobre.html y cada episodio.
    legal.html se queda fuera a propósito (además lleva noindex)."""
    web = cfg["web"].rstrip("/")
    urls = [(f"{web}/", episodios[0]["publicado_en"][:10] if episodios else None),
            (f"{web}/sobre.html", None)]
    urls += [(f"{web}/episodios/{ep['fecha']}.html", ep["publicado_en"][:10]) for ep in episodios]
    entradas = "\n".join(
        f"  <url><loc>{escape(loc)}</loc>{f'<lastmod>{fecha}</lastmod>' if fecha else ''}</url>"
        for loc, fecha in urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entradas}
</urlset>
"""


# ---------------------------------------------------------------- web

# El pie, también en docs/sobre.html y docs/legal.html (actualizar_pie).
ESTILO_PIE = """  footer { margin-top:48px; font-size:0.85rem; color:var(--suave); display:flex; flex-wrap:wrap;
           justify-content:space-between; align-items:center; gap:12px 24px;
           padding-top:20px; border-top:1px solid var(--borde); }
  footer a { color:var(--suave); }
  footer nav { margin:0; }
  footer .redes { display:flex; gap:16px; }
  footer .redes a { display:block; line-height:0; }
  footer .redes a:hover { color:var(--texto); }
  .contacto { width:min(480px, calc(100vw - 32px)); max-height:calc(100dvh - 32px); padding:0; font-size:1rem;
              border:1px solid var(--borde); border-radius:14px; background:var(--caja); color:var(--texto); }
  .contacto::backdrop { background:rgba(5,5,10,.75); }
  .contacto form { position:relative; display:grid; gap:14px; padding:22px 22px 20px; }
  .contacto h2 { margin:0; font-size:1.25rem; }
  .contacto p { margin:0; }
  .contacto .cerrar { position:absolute; top:10px; right:10px; width:36px; height:36px; font:inherit; font-size:1.5rem;
                      line-height:1; color:var(--suave); background:none; border:0; border-radius:8px; cursor:pointer; }
  .contacto .cerrar:hover { color:var(--texto); }
  .contacto fieldset { border:0; padding:0; margin:0; display:flex; flex-wrap:wrap; gap:8px; }
  .contacto legend { padding:0; margin-bottom:8px; font-size:0.9rem; color:var(--suave); }
  .contacto .asunto { position:relative; }
  .contacto .asunto input { position:absolute; opacity:0; inset:0; margin:0; }
  .contacto .asunto span { display:block; padding:5px 12px; font-size:0.9rem; border:1px solid var(--borde);
                           border-radius:999px; cursor:pointer; }
  .contacto .asunto input:checked + span { color:var(--acento); border-color:var(--acento); }
  .contacto .asunto input:focus-visible + span { outline:2px solid var(--acento); outline-offset:2px; }
  .contacto .campo { display:grid; gap:4px; font-size:0.9rem; color:var(--suave); }
  .contacto .fila { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .contacto input[type=text], .contacto input[type=email], .contacto textarea {
    font:inherit; font-size:1rem; color:var(--texto); background:var(--fondo); border:1px solid var(--borde);
    border-radius:8px; padding:8px 10px; }
  .contacto input:focus, .contacto textarea:focus { outline:none; border-color:var(--acento); }
  .contacto textarea { min-height:120px; resize:vertical; }
  .contacto .aviso { font-size:0.8rem; color:var(--suave); }
  .contacto .aviso a { color:var(--suave); }
  .contacto .acciones { display:flex; flex-wrap:wrap; align-items:center; gap:10px 16px; }
  .contacto .enviar { font:inherit; font-weight:600; color:var(--fondo); background:var(--acento); border:0;
                      border-radius:8px; padding:8px 20px; cursor:pointer; }
  .contacto .enviar:disabled { opacity:.6; cursor:wait; }
  .contacto .estado { font-size:0.9rem; }
  .contacto .estado.error { color:#fca5a5; }
  .contacto .trampa { position:absolute; left:-9999px; width:1px; height:1px; overflow:hidden; }
  @media (max-width:520px) { .contacto .fila { grid-template-columns:1fr; } }
"""

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
  details summary { cursor:pointer; color:var(--suave); margin-top:24px; }
  .con-portada { display:grid; grid-template-columns:112px 1fr; gap:0 18px; align-items:center; }
  .con-portada .mini { display:block; }
  .con-portada .mini img { width:112px; height:112px; border-radius:12px; display:block; }
  .con-portada audio { grid-column:1 / -1; }
  .cabecera { margin:20px 0 16px; }
  .cabecera.con-portada { grid-template-columns:168px 1fr; gap:20px; align-items:center; }
  .cabecera .portada-ep { display:block; line-height:0; }
  .cabecera .portada-ep img { width:168px; height:168px; border-radius:14px; display:block;
                              box-shadow:0 0 32px rgba(34,211,238,.18); }
  .dato { font-size:0.85rem; color:var(--suave); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px; }
  .cabecera h1 { font-size:1.6rem; line-height:1.2; letter-spacing:-0.01em; }
  @media (max-width:520px) {
    .cabecera.con-portada { grid-template-columns:96px 1fr; gap:14px; }
    .cabecera .portada-ep img { width:96px; height:96px; border-radius:10px; }
    .dato { font-size:0.75rem; letter-spacing:0.04em; }
    .con-portada { grid-template-columns:96px 1fr; gap:0 14px; }
    .con-portada .mini img { width:96px; height:96px; border-radius:10px; }
    .cabecera h1 { font-size:1.2rem; }
  }

  .insignias { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:18px 0 20px; }  /* abajo, lo mismo que hay bajo la raya (.episodio) */
  .insignias a { display:block; line-height:0; }
  .insignias img { height:40px; width:auto; }
  .insignias .texto { line-height:1.2; color:var(--acento); text-decoration:none; border:1px solid var(--acento);
                      border-radius:8px; padding:9px 14px; font-size:0.95rem; }
  .episodio-insignias { margin:6px 0 4px; }
  .episodio-insignias img { height:34px; }
  .capitulos { list-style:none; padding:0; margin:18px 0; }
  .capitulos li { margin:4px 0; display:grid; grid-template-columns:auto 1fr; align-items:baseline; }
  .capitulos button { font:inherit; font-variant-numeric:tabular-nums; color:var(--acento); background:none;
                      border:1px solid var(--borde); border-radius:6px; padding:1px 8px; margin-right:10px; cursor:pointer; }
  .capitulos button:hover { border-color:var(--acento); }
  .vecinos { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:32px; padding-top:20px; border-top:1px solid var(--borde); }
  .vecinos a { display:block; text-decoration:none; line-height:1.35; }
  .vecinos a .suave { display:block; font-size:0.85rem; margin-bottom:2px; }
  .vecinos .siguiente { text-align:right; }
""" + ESTILO_PIE


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


ICONOS_REDES = RAIZ / "assets" / "redes" / "iconos"


def iconos_redes(cfg):
    """Los perfiles de config/podcast.yaml (redes), cada uno con su icono en el color del texto."""
    enlaces = []
    for r in cfg.get("redes") or []:
        svg = (ICONOS_REDES / f"{r['icono']}.svg").read_text(encoding="utf-8").strip()
        svg = re.sub(r"<title>.*?</title>", "", svg)
        svg = svg.replace('<svg role="img"', '<svg aria-hidden="true" focusable="false" fill="currentColor" width="20" height="20"', 1)
        enlaces.append(f'<a href="{html.escape(r["url"])}" target="_blank" rel="noopener" title="Cátodo en {html.escape(r["nombre"])}" '
                       f'aria-label="Cátodo en {html.escape(r["nombre"])}">{svg}</a>')
    return f'<nav class="redes" aria-label="Cátodo en redes">{"".join(enlaces)}</nav>' if enlaces else ""


def pie(cfg):
    """El pie de todas las páginas: enlaces a un lado y redes al otro, en una línea.

    El aviso de IA no va aquí: ya está en la descripción de la portada y en las notas de
    cada episodio. Tampoco Apple, Spotify ni el RSS: están en las insignias de arriba.

    Con clave de Web3Forms, «Contacto» abre un formulario y el correo no sale en la web."""
    clave = (cfg.get("contacto") or {}).get("web3forms")
    if clave:
        contacto, dialogo = '<a href="#contacto">Contacto</a>', formulario_contacto(cfg, clave)
    else:
        contacto, dialogo = f'<a href="mailto:{cfg["email"]}">{cfg["email"]}</a>', ""
    return f"""<footer><nav class="enlaces-pie" aria-label="Más sobre Cátodo"><a href="/sobre.html">De dónde sale Cátodo</a> · <a href="/legal.html">Aviso legal y privacidad</a> · {contacto}</nav>
  {iconos_redes(cfg)}{dialogo}</footer>"""


# Abre el formulario desde cualquier enlace a #contacto (también al entrar en catodo.es/#contacto)
# y lo envía a Web3Forms sin salir de la página.
SCRIPT_CONTACTO = """<script>
  (() => {
    const d = document.getElementById('contacto'), f = d.querySelector('form'), estado = d.querySelector('.estado');
    const boton = f.querySelector('.enviar'), mensaje = f.elements.message;
    const abrir = e => { if (e) e.preventDefault(); estado.textContent = ''; d.showModal(); };
    document.querySelectorAll('a[href="#contacto"]').forEach(a => a.addEventListener('click', abrir));
    if (location.hash === '#contacto') abrir();
    d.addEventListener('close', () => { if (location.hash === '#contacto') history.replaceState(null, '', location.pathname + location.search); });
    d.addEventListener('click', e => { if (e.target === d) d.close(); });  // fuera del cuadro
    d.querySelector('.cerrar').addEventListener('click', () => d.close());
    const pista = () => { mensaje.placeholder = f.querySelector('[name=asunto]:checked').dataset.pista; };
    f.querySelectorAll('[name=asunto]').forEach(r => r.addEventListener('change', pista));
    pista();
    f.addEventListener('submit', async e => {
      e.preventDefault();
      const datos = Object.fromEntries(new FormData(f));
      datos.subject = 'Cátodo · ' + datos.asunto;
      datos.pagina = location.origin + location.pathname;
      boton.disabled = true; estado.className = 'estado'; estado.textContent = 'Enviando…';
      try {
        const r = await fetch(f.action, { method: 'POST', body: JSON.stringify(datos),
                                          headers: { 'Content-Type': 'application/json', Accept: 'application/json' } });
        if (!(await r.json()).success) throw new Error();
        f.reset(); pista();
        estado.textContent = 'Enviado. Gracias: te contestaremos a tu correo.';
      } catch {
        estado.className = 'estado error';
        estado.textContent = 'No se ha podido enviar. Inténtalo de nuevo en un rato.';
      } finally { boton.disabled = false; }
    });
  })();
  </script>"""


def formulario_contacto(cfg, clave):
    """El diálogo de contacto: asunto, mensaje, nombre y correo para responder.

    Contra el spam: Web3Forms filtra en su lado y descarta lo que marque la casilla trampa
    (botcheck), que una persona no ve."""
    asuntos = "\n      ".join(
        f'<label class="asunto"><input type="radio" name="asunto" value="{html.escape(a["texto"])}" '
        f'data-pista="{html.escape(a.get("pista", ""))}"{" checked" if i == 0 else ""}><span>{html.escape(a["texto"])}</span></label>'
        for i, a in enumerate(cfg["contacto"]["asuntos"]))
    return f"""
  <dialog id="contacto" class="contacto" aria-labelledby="contacto-titulo">
    <form action="https://api.web3forms.com/submit" method="post">
    <input type="hidden" name="access_key" value="{html.escape(clave)}">
    <input type="hidden" name="from_name" value="Web de {html.escape(cfg['titulo'])}">
    <h2 id="contacto-titulo">Escribe a {html.escape(cfg['titulo'])}</h2>
    <button type="button" class="cerrar" aria-label="Cerrar">×</button>
    <fieldset>
      <legend>¿Sobre qué?</legend>
      {asuntos}
    </fieldset>
    <label class="campo">Mensaje<textarea name="message" required maxlength="4000" rows="5"></textarea></label>
    <div class="fila">
      <label class="campo">Nombre (opcional)<input type="text" name="name" maxlength="100" autocomplete="name"></label>
      <label class="campo">Tu correo, para responderte<input type="email" name="email" required maxlength="200" autocomplete="email"></label>
    </div>
    <label class="trampa" aria-hidden="true">No marques esta casilla<input type="checkbox" name="botcheck" tabindex="-1" autocomplete="off"></label>
    <p class="aviso">Usaremos tu correo solo para responderte. Más en <a href="/legal.html#privacidad">privacidad</a>.</p>
    <div class="acciones"><button type="submit" class="enviar">Enviar</button><p class="estado" role="status"></p></div>
    </form>
  </dialog>
  {SCRIPT_CONTACTO}"""


def actualizar_pie(fichero, cfg):
    """docs/sobre.html y docs/legal.html están escritas a mano: se les pone el mismo pie."""
    if not fichero.exists():
        return
    texto = fichero.read_text(encoding="utf-8")
    nuevo = re.sub(r"<footer>.*?</footer>", lambda _: pie(cfg), texto, count=1, flags=re.S)
    if "<footer>" not in nuevo:
        nuevo = nuevo.replace("\n</main>", f"\n\n  {pie(cfg)}\n</main>", 1)
    # Los estilos del pie, los mismos que en las páginas generadas y siempre al final del <style>.
    if "  footer {" in nuevo:
        nuevo = re.sub(r"  footer \{.*?(?=</style>)", lambda _: ESTILO_PIE, nuevo, count=1, flags=re.S)
    else:
        nuevo = nuevo.replace("</style>", ESTILO_PIE + "</style>", 1)
    if nuevo != texto:
        fichero.write_text(nuevo, encoding="utf-8")


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
  {pie(cfg)}
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
    {mini}<div><div class="dato">{dato_episodio(ep)}</div>
    <h2><a href="{pagina}">{html.escape(ep['titulo'])}</a></h2></div>
    <audio controls preload="none" src="{html.escape(ep['url_audio'])}"></audio>
  </article>""")
    cuerpo = f"""  <h1 class="neon">Cátodo.</h1>
  <p class="suave">{html.escape(cfg['subtitulo'])}. {html.escape(cfg['descripcion'])}</p>
  {insignias(cfg)}
{chr(10).join(lista) if lista else '  <p>Muy pronto, el primer episodio.</p>'}"""
    return plantilla(cfg["titulo"], cfg["descripcion"], cuerpo, cfg)


def navegacion_episodios(anterior, siguiente):
    """Enlaces al episodio anterior (más antiguo) y al siguiente (más reciente), si los hay."""
    if not anterior and not siguiente:
        return ""
    def enlace(ep, rel, flecha_antes, flecha_despues, texto):
        return (f'<a class="{rel}" rel="{"prev" if rel == "anterior" else "next"}" href="/episodios/{ep["fecha"]}.html">'
                f'<span class="suave">{flecha_antes}{texto}{flecha_despues}</span>{html.escape(ep["titulo"])}</a>')
    partes = [enlace(anterior, "anterior", "← ", "", "Anterior") if anterior else "<span></span>",
              enlace(siguiente, "siguiente", "", " →", "Siguiente") if siguiente else "<span></span>"]
    return f'<nav class="vecinos" aria-label="Otros episodios">{"".join(partes)}</nav>'


def generar_pagina_episodio(ep, cfg, anterior=None, siguiente=None):
    transcripcion = md_a_html(ep["guion_md"], nivel_titulos=3)
    cuerpo = f"""  <p><a href="/">← Cátodo</a></p>
  {cabecera_episodio(ep)}
  <audio id="audio" controls preload="metadata" src="{html.escape(ep['url_audio'])}"></audio>
  {insignias(cfg, ep, "insignias episodio-insignias")}
  {capitulos_html(ep)}{descripcion_episodio(ep, cfg, capitulos=False)}
  <details><summary>Leer el guion completo</summary>
  {transcripcion}
  </details>
  {navegacion_episodios(anterior, siguiente)}"""
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


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


def fecha_corta(iso):
    """26 nov 2026."""
    d = datetime.fromisoformat(iso)
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def dato_episodio(ep):
    """Episodio 3 · 26 nov 2026 · 11 min (en mayúsculas por CSS), encima del título."""
    partes = (f"Episodio {ep['numero']}" if ep.get("numero") else "", fecha_corta(ep["fecha"]),
              f"{int(ep['duracion_s'] // 60)} min")
    return " · ".join(x.replace(" ", "\u00a0") for x in partes if x)  # solo se corta entre los puntos


def cabecera_episodio(ep):
    """Ficha del episodio: la portada en pequeño y, a su lado, número, fecha, duración y título.

    La portada (el guion en emojis) abre en grande al pulsarla. Sin explicación a propósito:
    que sea un huevo de pascua para quien se fije."""
    texto = f'<div><div class="dato">{dato_episodio(ep)}</div>\n    <h1>{html.escape(ep["titulo"])}</h1></div>'
    if not ep.get("url_portada"):
        return f'<header class="cabecera">\n    {texto}\n  </header>'
    mini = ep.get("url_portada_web") or ep["url_portada"]
    return (f'<header class="cabecera con-portada">\n'
            f'    <a class="portada-ep" href="{html.escape(ep["url_portada"])}"><img src="{html.escape(mini)}" '
            f'width="168" height="168" alt="Portada del episodio"></a>\n'
            f'    {texto}\n  </header>')


def generar_todo(destino=DOCS):
    cfg = cargar_yaml("podcast.yaml")
    episodios = episodios_publicados()
    (destino / "episodios").mkdir(parents=True, exist_ok=True)
    (destino / "feed.xml").write_text(generar_feed(episodios, cfg), encoding="utf-8")
    (destino / "sitemap.xml").write_text(generar_sitemap(episodios, cfg), encoding="utf-8")
    (destino / "index.html").write_text(generar_portada(episodios, cfg), encoding="utf-8")
    for estatica in ("sobre.html", "legal.html"):
        actualizar_pie(destino / estatica, cfg)
    for i, ep in enumerate(episodios):  # de más reciente a más antiguo
        anterior = episodios[i + 1] if i + 1 < len(episodios) else None
        siguiente = episodios[i - 1] if i > 0 else None
        (destino / "episodios" / f"{ep['fecha']}.html").write_text(
            generar_pagina_episodio(ep, cfg, anterior, siguiente), encoding="utf-8")
        if ep.get("capitulos"):  # lo que enlaza <podcast:chapters>
            (destino / "episodios" / f"{ep['fecha']}-capitulos.json").write_text(
                json.dumps({"version": "1.2.0", "chapters": ep["capitulos"]}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
    return episodios


def main():
    episodios = generar_todo()
    print(f"Feed y web regenerados con {len(episodios)} episodios: docs/feed.xml, docs/sitemap.xml, docs/index.html, docs/episodios/")


if __name__ == "__main__":
    main()
