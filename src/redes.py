"""Difusión en redes del episodio publicado: Bluesky, Instagram, Facebook, Threads y YouTube.

Uso:
    python src/redes.py --fecha AAAA-MM-DD [--simulacro] [--solo red,red]
    python src/redes.py autorizar-youtube     # una vez, en el Mac: saca el refresh token
    python src/redes.py autorizar-meta        # una vez: token y ID de la página de Facebook
    python src/redes.py autorizar-threads     # una vez: token largo de Threads

Lo lanza ops cuando Ulises elige «Difundir en redes» en el aviso del episodio publicado
(catodo.preparar, src/ops.py responder): espera, si hace falta, a que el episodio esté en
catodo.es. Solo publica en las redes de `redes.activas` (config/settings.yaml)
que tengan sus credenciales. Para cada episodio:

  - Bluesky: un mensaje con el titular y una tarjeta con el enlace a la página del episodio.
  - Instagram (Reel), Facebook (vídeo de la página) y Threads: el clip vertical de la
    primera noticia (src/difusion.py), que antes se sube a R2 para que Meta lo descargue.
  - YouTube: el episodio entero en vídeo, con sus capítulos, y el clip como Short.

Lo ya publicado se apunta en R2 (difusion/FECHA.json) red a red, en cuanto sale: si se
repite, no se publica dos veces. Si una red falla, las demás siguen; al final, si alguna
ha fallado, termina con error: ops avisa y lo reintenta, y solo se repiten las que faltan.

Las credenciales llegan por el entorno (en el Mac, de .env): BLUESKY_APP_PASSWORD (la
cuenta, `redes.bluesky` de settings.yaml); INSTAGRAM_TOKEN; META_PAGE_ID y META_PAGE_TOKEN; THREADS_USER_ID y
THREADS_TOKEN; YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET y YOUTUBE_REFRESH_TOKEN.

Instagram va con la API de Instagram con inicio de sesión de Instagram (graph.instagram.com),
no con la de Facebook: no hace falta que la cuenta esté vinculada a la página de Facebook.
Su token se saca en el panel de la app de Meta (Instagram › Configuración de la API con
inicio de sesión de Instagram › Generar token). Los tokens de Instagram y de Threads duran
60 días: se renuevan solos cada semana y el renovado se guarda en CATODO_ESTADO (en ops, el
HOME del trabajo, que no se borra entre ejecuciones). El de la página de Facebook no caduca.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from comun import EPISODIOS, RAIZ, cargar_env, cargar_yaml

REDES = ["bluesky", "instagram", "facebook", "threads", "youtube"]
CARPETA_R2 = "difusion"
AJUSTES = cargar_yaml("settings.yaml").get("redes", {})
GRAPH = f"https://graph.facebook.com/{AJUSTES.get('version_graph', 'v24.0')}"
GRAPH_VIDEO = f"https://graph-video.facebook.com/{AJUSTES.get('version_graph', 'v24.0')}"
THREADS = "https://graph.threads.net/v1.0"
INSTAGRAM = f"https://graph.instagram.com/{AJUSTES.get('version_graph', 'v24.0')}"
BLUESKY = "https://bsky.social/xrpc"
ESPERA_MAX_S = 600


class ErrorRed(Exception):
    pass


def pedir(metodo, url, **kwargs):
    """Una petición HTTP que, si falla, dice por qué (sin mostrar tokens)."""
    kwargs.setdefault("timeout", 120)
    r = requests.request(metodo, url, **kwargs)
    if r.status_code >= 400:
        cuerpo = re.sub(r"(access_token=)[^&\s\"]+", r"\1***", r.text[:600])
        raise ErrorRed(f"{metodo} {url.split('?')[0]}: HTTP {r.status_code}: {cuerpo}")
    return r.json() if r.content and "json" in r.headers.get("Content-Type", "") else {}


# ---------------------------------------------------------------- textos

def titulares(capitulos):
    return [c["title"] for c in capitulos if c["title"] not in ("Apertura", "Cierre")]


def url_pagina(fecha):
    return f"{cargar_yaml('podcast.yaml')['web'].rstrip('/')}/episodios/{fecha}.html"


def graphemes(texto):
    import regex
    return len(regex.findall(r"\X", texto))


def con_lista(cabecera, lista, pie, limite, medir=len):
    """cabecera + tantos titulares como quepan + pie, sin pasar de `limite`."""
    for n in range(len(lista), -1, -1):
        cuerpo = "\n".join(f"• {t}" for t in lista[:n])
        texto = "\n\n".join(p for p in (cabecera, cuerpo, pie) if p)
        if medir(texto) <= limite:
            return texto
    return cabecera[:limite]


def texto_bluesky(datos):
    cabecera = f"{datos['titulo']}\n\nEpisodio {datos['publicacion']['numero']} de Cátodo 🎧"
    return con_lista(cabecera, titulares(datos["capitulos"]), "", 300, graphemes)


AVISO_IA_CORTO = "Guion y voz generados con IA y revisados por personas."
ETIQUETAS = "#tecnología #noticias #podcast #IA"


def texto_instagram(datos):
    pie = (f"🎧 El episodio completo, en catodo.es (enlace en el perfil), Spotify y Apple Podcasts.\n\n"
           f"{AVISO_IA_CORTO}\n\n{ETIQUETAS}")
    return con_lista(f"{datos['titulo']}\n\nHoy en Cátodo:", titulares(datos["capitulos"]), pie, 2200)


def texto_facebook(datos):
    pie = f"🎧 Escúchalo entero: {url_pagina(datos['fecha'])}\n\n{AVISO_IA_CORTO}"
    return con_lista(f"{datos['titulo']}\n\nHoy en Cátodo:", titulares(datos["capitulos"]), pie, 5000)


def texto_threads(datos):
    pie = f"🎧 {url_pagina(datos['fecha'])}"
    return con_lista(datos["titulo"], titulares(datos["capitulos"]), pie, 500)


def titulo_youtube(datos):
    sufijo = f" | Cátodo {datos['publicacion']['numero']}"
    titulo = datos["titulo"]
    if len(titulo) + len(sufijo) > 100:
        titulo = titulo[:100 - len(sufijo) - 1].rsplit(" ", 1)[0] + "…"
    return re.sub(r"[<>]", "", titulo + sufijo)


def descripcion_youtube(datos):
    from feed import marca
    podcast = cargar_yaml("podcast.yaml")
    capitulos = "\n".join(f"{marca(c['startTime'])} {c['title']}" for c in datos["capitulos"])
    escuchar = "\n".join(f"{e['nombre']}: {e['url']}" for e in podcast.get("escuchar", []) if e["url"].startswith("http"))
    texto = (f"Episodio {datos['publicacion']['numero']} de Cátodo, el pódcast diario de noticias de tecnología "
             f"en español ({datos['fecha']}).\n\n{capitulos}\n\n"
             f"Fuentes y notas del episodio: {url_pagina(datos['fecha'])}\n\n{escuchar}\n\n{podcast['aviso_ia']}")
    return re.sub(r"[<>]", "", texto)[:4900]


def descripcion_short(datos, url_video):
    completo = f"Episodio completo: {url_video}\n\n" if url_video else ""
    return f"{completo}Fuentes: {url_pagina(datos['fecha'])}\n\n{AVISO_IA_CORTO}\n\n#Shorts {ETIQUETAS}"


# ---------------------------------------------------------------- estado en R2

def cliente_r2(env):
    import ops
    return ops.cliente_r2(env)


def leer_estado(cliente, bucket, fecha):
    try:
        objeto = cliente.get_object(Bucket=bucket, Key=f"{CARPETA_R2}/{fecha}.json")
    except cliente.exceptions.NoSuchKey:
        return {}
    return json.loads(objeto["Body"].read())


def guardar_estado(cliente, bucket, fecha, estado):
    cliente.put_object(Bucket=bucket, Key=f"{CARPETA_R2}/{fecha}.json", ContentType="application/json",
                       CacheControl="no-store", Body=json.dumps(estado, ensure_ascii=False, indent=2).encode())


def subir_clip(cliente, env, fecha, clip):
    """Sube el clip a R2 (Meta lo descarga de una URL pública) y devuelve esa URL."""
    huella = hashlib.sha256(clip.read_bytes()).hexdigest()[:8]
    clave = f"{CARPETA_R2}/catodo-{fecha}-clip-{huella}.mp4"
    cliente.upload_file(str(clip), env.get("R2_BUCKET", "catodo-audio"), clave, ExtraArgs={
        "ContentType": "video/mp4", "CacheControl": "public, max-age=31536000, immutable"})
    return f"{env.get('R2_PUBLIC_BASE_URL', 'https://audio.catodo.es').rstrip('/')}/{clave}"


# ---------------------------------------------------------------- redes

def falta(env, *nombres):
    faltan = [n for n in nombres if not env.get(n)]
    if faltan:
        raise ErrorRed(f"faltan las credenciales {', '.join(faltan)}")


def bluesky(datos, env, medios):
    env = {"BLUESKY_HANDLE": AJUSTES.get("bluesky"), **{k: v for k, v in env.items() if v}}
    falta(env, "BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    sesion = pedir("POST", f"{BLUESKY}/com.atproto.server.createSession",
                   json={"identifier": env["BLUESKY_HANDLE"], "password": env["BLUESKY_APP_PASSWORD"]})
    cabeceras = {"Authorization": f"Bearer {sesion['accessJwt']}"}
    tarjeta = {"uri": url_pagina(datos["fecha"]), "title": datos["titulo"],
               "description": " · ".join(titulares(datos["capitulos"]))[:300]}
    miniatura = datos["publicacion"].get("url_portada_web")
    if miniatura:
        imagen = requests.get(miniatura, timeout=60)
        if imagen.ok and len(imagen.content) < 1_000_000:
            blob = pedir("POST", f"{BLUESKY}/com.atproto.repo.uploadBlob", data=imagen.content,
                         headers={**cabeceras, "Content-Type": "image/jpeg"})
            tarjeta["thumb"] = blob["blob"]
    registro = {"$type": "app.bsky.feed.post", "text": texto_bluesky(datos), "langs": ["es"],
                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "embed": {"$type": "app.bsky.embed.external", "external": tarjeta}}
    hecho = pedir("POST", f"{BLUESKY}/com.atproto.repo.createRecord", headers=cabeceras,
                  json={"repo": sesion["did"], "collection": "app.bsky.feed.post", "record": registro})
    clave = hecho["uri"].rsplit("/", 1)[-1]
    return {"id": hecho["uri"], "url": f"https://bsky.app/profile/{env['BLUESKY_HANDLE']}/post/{clave}"}


def esperar(comprobar, nombre, espera=10, limite=ESPERA_MAX_S):
    """Espera a que Meta termine de procesar un vídeo."""
    inicio = time.monotonic()
    while True:
        estado = comprobar()
        if estado in ("FINISHED", "PUBLISHED"):
            return
        if estado in ("ERROR", "EXPIRED"):
            raise ErrorRed(f"{nombre}: el vídeo no se ha podido procesar ({estado})")
        if time.monotonic() - inicio > limite:
            raise ErrorRed(f"{nombre}: el vídeo sigue procesándose tras {limite} s")
        time.sleep(espera)


def instagram(datos, env, medios):
    falta(env, "INSTAGRAM_TOKEN")
    token = token_renovable(env, "instagram")
    usuario = env.get("INSTAGRAM_USER_ID") or pedir("GET", f"{INSTAGRAM}/me", params={
        "fields": "user_id", "access_token": token})["user_id"]
    contenedor = pedir("POST", f"{INSTAGRAM}/{usuario}/media", data={
        "media_type": "REELS", "video_url": medios["url_clip"], "caption": texto_instagram(datos),
        "share_to_feed": "true", "access_token": token})["id"]
    esperar(lambda: pedir("GET", f"{INSTAGRAM}/{contenedor}", params={
        "fields": "status_code", "access_token": token}).get("status_code"), "Instagram")
    publicado = pedir("POST", f"{INSTAGRAM}/{usuario}/media_publish",
                      data={"creation_id": contenedor, "access_token": token})["id"]
    enlace = pedir("GET", f"{INSTAGRAM}/{publicado}", params={"fields": "permalink", "access_token": token})
    return {"id": publicado, "url": enlace.get("permalink")}


def facebook(datos, env, medios):
    falta(env, "META_PAGE_ID", "META_PAGE_TOKEN")
    hecho = pedir("POST", f"{GRAPH_VIDEO}/{env['META_PAGE_ID']}/videos", data={
        "file_url": medios["url_clip"], "title": datos["titulo"][:250], "description": texto_facebook(datos),
        "access_token": env["META_PAGE_TOKEN"]})
    return {"id": hecho["id"], "url": f"https://www.facebook.com/{env['META_PAGE_ID']}/videos/{hecho['id']}"}


# Tokens de 60 días que se renuevan: (variable con el de las credenciales, URL y grant_type).
RENOVABLES = {
    "threads": ("THREADS_TOKEN", f"{THREADS.rsplit('/', 1)[0]}/refresh_access_token", "th_refresh_token"),
    "instagram": ("INSTAGRAM_TOKEN", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
}


def token_threads(env):
    return token_renovable(env, "threads")


def token_renovable(env, red):
    """El token de Threads o de Instagram: el último renovado (CATODO_ESTADO) o el de las
    credenciales. Si tiene más de una semana, lo renueva (dura 60 días desde la última)."""
    variable, url, tipo = RENOVABLES[red]
    estado_dir = Path(env.get("CATODO_ESTADO") or RAIZ / "cache")
    ruta = estado_dir / f"{red}-token.json"
    guardado = json.loads(ruta.read_text()) if ruta.exists() else {}
    original = env.get(variable, "")
    if guardado.get("origen") != hashlib.sha256(original.encode()).hexdigest()[:12]:
        guardado = {}  # han cambiado la credencial: manda la nueva
    token = guardado.get("token") or original
    if time.time() - guardado.get("renovado", 0) > 7 * 86400:
        try:
            nuevo = pedir("GET", url, params={"grant_type": tipo, "access_token": token})
            token = nuevo["access_token"]
            estado_dir.mkdir(parents=True, exist_ok=True)
            ruta.write_text(json.dumps({"token": token, "renovado": time.time(),
                                        "origen": hashlib.sha256(original.encode()).hexdigest()[:12]}))
            ruta.chmod(0o600)
        except ErrorRed as e:
            print(f"  {red.capitalize()}: no se ha podido renovar el token ({e}); sigo con el que hay.")
    return token


def threads(datos, env, medios):
    falta(env, "THREADS_USER_ID", "THREADS_TOKEN")
    token, usuario = token_threads(env), env["THREADS_USER_ID"]
    contenedor = pedir("POST", f"{THREADS}/{usuario}/threads", data={
        "media_type": "VIDEO", "video_url": medios["url_clip"], "text": texto_threads(datos),
        "access_token": token})["id"]
    esperar(lambda: pedir("GET", f"{THREADS}/{contenedor}", params={
        "fields": "status", "access_token": token}).get("status"), "Threads")
    publicado = pedir("POST", f"{THREADS}/{usuario}/threads_publish",
                      data={"creation_id": contenedor, "access_token": token})["id"]
    enlace = pedir("GET", f"{THREADS}/{publicado}", params={"fields": "permalink", "access_token": token})
    return {"id": publicado, "url": enlace.get("permalink")}


def token_google(env):
    falta(env, "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    return pedir("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": env["YOUTUBE_CLIENT_ID"], "client_secret": env["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": env["YOUTUBE_REFRESH_TOKEN"], "grant_type": "refresh_token"})["access_token"]


def subir_youtube(token, fichero, titulo, descripcion):
    """Subida reanudable a YouTube: público, en español, declarado como contenido sintético."""
    metadatos = {
        "snippet": {"title": titulo, "description": descripcion, "categoryId": "28",
                    "defaultLanguage": "es", "defaultAudioLanguage": "es",
                    "tags": ["tecnología", "noticias", "podcast", "Cátodo"]},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    tam = fichero.stat().st_size
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status"}, json=metadatos, timeout=60,
                      headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                               "X-Upload-Content-Length": str(tam)})
    if r.status_code >= 400:
        raise ErrorRed(f"YouTube: HTTP {r.status_code}: {r.text[:600]}")
    with open(fichero, "rb") as f:
        subida = requests.put(r.headers["Location"], data=f, timeout=1800,
                              headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4",
                                       "Content-Length": str(tam)})
    if subida.status_code >= 400:
        raise ErrorRed(f"YouTube: HTTP {subida.status_code}: {subida.text[:600]}")
    video = subida.json()
    if video.get("status", {}).get("privacyStatus") != "public":
        print(f"  YouTube: el vídeo {video['id']} ha quedado {video.get('status', {}).get('privacyStatus')} "
              "(¿proyecto sin auditar?).")
    return video["id"]


def youtube(datos, env, medios):
    token = token_google(env)
    hecho = {}
    if medios.get("video"):
        video = subir_youtube(token, medios["video"], titulo_youtube(datos), descripcion_youtube(datos))
        hecho.update(id=video, url=f"https://youtu.be/{video}")
    if medios.get("clip"):
        noticia = medios.get("noticia") or datos["titulo"]
        short = subir_youtube(token, medios["clip"], f"{noticia[:90]} #Shorts",
                              descripcion_short(datos, hecho.get("url")))
        hecho.update(short=short, url_short=f"https://youtube.com/shorts/{short}")
    return hecho


PUBLICAR = {"bluesky": bluesky, "instagram": instagram, "facebook": facebook, "threads": threads,
            "youtube": youtube}
CON_CLIP = {"instagram", "facebook", "threads", "youtube"}


# ---------------------------------------------------------------- el día

def esta_publicado(datos):
    """El episodio está en la web y su audio se descarga."""
    for url in (url_pagina(datos["fecha"]), datos["publicacion"]["url_audio"]):
        r = requests.head(url, timeout=30, allow_redirects=True)
        if r.status_code != 200:
            return f"{url} da HTTP {r.status_code}"
    return None


def activas(solo=None):
    lista = [r for r in AJUSTES.get("activas") or [] if r in REDES]
    return [r for r in lista if r in solo] if solo else lista


def esperar_publicado(datos, segundos, cada=30):
    """Espera hasta `segundos` a que el episodio esté en la web (GitHub Pages tarda unos
    minutos tras el push). Devuelve el problema si sigue sin estar, o None."""
    limite = time.monotonic() + segundos
    while True:
        try:
            problema = esta_publicado(datos)
        except requests.RequestException as e:
            problema = str(e)
        if not problema or time.monotonic() + cada > limite:
            return problema
        print(f"Aún no está en la web ({problema}): espero {cada} s.", flush=True)
        time.sleep(cada)


def difundir(fecha, simulacro=False, solo=None, salida=None, esperar=0):
    """Publica el episodio en las redes activas. Devuelve {red: resultado o error}.
    `esperar`: segundos que aguarda a que el episodio esté en la web antes de rendirse."""
    import difusion

    # En simulacro, --solo vale aunque la red no esté activa: para ver los textos antes de activarla.
    redes = [r for r in solo if r in REDES] if simulacro and solo else activas(solo)
    if not redes:
        print("No hay redes activas (redes.activas en config/settings.yaml): nada que hacer.")
        return {}
    if not (EPISODIOS / fecha / "publicacion.json").exists():
        raise SystemExit(f"El episodio del {fecha} no está publicado (falta publicacion.json).")
    env = cargar_env()
    datos = difusion.datos_episodio(fecha)
    estado, cliente, bucket = {}, None, env.get("R2_BUCKET", "catodo-audio")
    if not simulacro:
        problema = esperar_publicado(datos, esperar)
        if problema:
            raise SystemExit(f"El episodio del {fecha} aún no está en la web: {problema}.")
        cliente = cliente_r2(env)
        estado = leer_estado(cliente, bucket, fecha)
    pendientes = [r for r in redes if r not in estado.get("redes", {})]
    for r in redes:
        if r not in pendientes:
            print(f"  {r}: ya publicado ({estado['redes'][r].get('url')})")
    if not pendientes:
        return {}

    medios = {}
    if CON_CLIP & set(pendientes):
        _, hecho = difusion.generar(fecha, salida, video="youtube" in pendientes)
        medios.update(clip=hecho["clip"], video=hecho.get("video"), noticia=hecho["clip_info"]["noticia"])
        if not simulacro and {"instagram", "facebook", "threads"} & set(pendientes):
            medios["url_clip"] = subir_clip(cliente, env, fecha, hecho["clip"])

    resultados = {}
    for red in pendientes:
        if simulacro:
            resultados[red] = {"simulacro": True}
            print(f"\n== {red} (simulacro)\n{textos_de(red, datos, medios)}")
            continue
        try:
            resultado = PUBLICAR[red](datos, env, medios)
            resultado["cuando"] = datetime.now().isoformat(timespec="seconds")
            estado.setdefault("redes", {})[red] = resultado
            guardar_estado(cliente, bucket, fecha, estado)
            resultados[red] = resultado
            print(f"  {red}: {resultado.get('url')}")
        except (ErrorRed, requests.RequestException, KeyError) as e:
            resultados[red] = {"error": str(e)}
            print(f"  {red}: ha fallado: {e}", file=sys.stderr)
    return resultados


def textos_de(red, datos, medios):
    if red == "bluesky":
        return texto_bluesky(datos)
    if red == "instagram":
        return texto_instagram(datos)
    if red == "facebook":
        return texto_facebook(datos)
    if red == "threads":
        return texto_threads(datos)
    return f"{titulo_youtube(datos)}\n\n{descripcion_youtube(datos)}\n\n-- Short --\n{descripcion_short(datos, None)}"


# ---------------------------------------------------------------- autorizaciones (una vez, a mano)

def autorizar_youtube():
    """Abre el navegador para dar permiso de subida a YouTube y escribe el refresh token en
    la salida estándar (para pasarlo directo a ops). Los mensajes van a stderr."""
    import http.server
    import secrets
    import urllib.parse
    import webbrowser

    env = cargar_env()
    falta(env, "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET")
    recibido = {}

    class Respuesta(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            recibido.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Listo: ya puedes cerrar esta pestaña.".encode())

        def log_message(self, *args):
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Respuesta)
    redirige = f"http://127.0.0.1:{servidor.server_port}"
    estado = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": env["YOUTUBE_CLIENT_ID"], "redirect_uri": redirige, "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload", "access_type": "offline",
        "prompt": "consent", "state": estado})
    print(f"Abre esto si no se abre solo:\n{url}", file=sys.stderr)
    webbrowser.open(url)
    servidor.handle_request()
    if recibido.get("state", [None])[0] != estado or "code" not in recibido:
        sys.exit(f"No ha llegado el permiso: {recibido.get('error', ['?'])[0]}")
    tokens = pedir("POST", "https://oauth2.googleapis.com/token", data={
        "code": recibido["code"][0], "client_id": env["YOUTUBE_CLIENT_ID"],
        "client_secret": env["YOUTUBE_CLIENT_SECRET"], "redirect_uri": redirige,
        "grant_type": "authorization_code"})
    if "refresh_token" not in tokens:
        sys.exit("Google no ha devuelto refresh token: quita el acceso de la app en tu cuenta y repite.")
    print("Permiso concedido. El refresh token va a la salida estándar.", file=sys.stderr)
    print(tokens["refresh_token"])


def autorizar_meta():
    """Con un token de usuario corto (Graph API Explorer, en el portapapeles por la entrada
    estándar), saca el token largo de la página de Facebook (no caduca) y su ID.
    Instagram no va por aquí: su token sale del panel de la app (ver arriba)."""
    env = cargar_env()
    falta(env, "META_APP_ID", "META_APP_SECRET")
    corto = sys.stdin.readline().strip()
    largo = pedir("GET", f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": env["META_APP_ID"],
        "client_secret": env["META_APP_SECRET"], "fb_exchange_token": corto})["access_token"]
    paginas = pedir("GET", f"{GRAPH}/me/accounts", params={
        "fields": "id,name,access_token", "access_token": largo})["data"]
    if not paginas:
        sys.exit("Ese usuario no administra ninguna página (o falta el permiso pages_show_list).")
    for p in paginas:
        print(f"Página «{p['name']}»: META_PAGE_ID={p['id']}", file=sys.stderr)
    if len(paginas) > 1:
        sys.exit("Hay varias páginas: deja solo la de Cátodo en el permiso y repite.")
    print("El token de la página (no caduca) va a la salida estándar.", file=sys.stderr)
    print(paginas[0]["access_token"])


def autorizar_threads():
    """Abre el permiso de Threads; pega luego la dirección a la que te lleva (catodo.es/?code=...)."""
    import urllib.parse
    import webbrowser

    env = cargar_env()
    falta(env, "THREADS_APP_ID", "THREADS_APP_SECRET")
    redirige = "https://catodo.es/"
    url = "https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": env["THREADS_APP_ID"], "redirect_uri": redirige,
        "scope": "threads_basic,threads_content_publish", "response_type": "code"})
    print(f"Abre esto, acepta y pega aquí la dirección de catodo.es a la que te lleve:\n{url}", file=sys.stderr)
    webbrowser.open(url)
    vuelta = input("> " if sys.stdin.isatty() else "")
    codigo = urllib.parse.parse_qs(urllib.parse.urlparse(vuelta.strip()).query).get("code", [""])[0].split("#")[0]
    corto = pedir("POST", "https://graph.threads.net/oauth/access_token", data={
        "client_id": env["THREADS_APP_ID"], "client_secret": env["THREADS_APP_SECRET"], "code": codigo,
        "grant_type": "authorization_code", "redirect_uri": redirige})
    largo = pedir("GET", "https://graph.threads.net/access_token", params={
        "grant_type": "th_exchange_token", "client_secret": env["THREADS_APP_SECRET"],
        "access_token": corto["access_token"]})
    print(f"THREADS_USER_ID={corto['user_id']}. El token largo va a la salida estándar.", file=sys.stderr)
    print(largo["access_token"])


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("autorizar-"):
        {"autorizar-youtube": autorizar_youtube, "autorizar-meta": autorizar_meta,
         "autorizar-threads": autorizar_threads}.get(sys.argv[1], lambda: sys.exit("¿Qué red?"))()
        return
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fecha", required=True)
    p.add_argument("--simulacro", action="store_true", help="hace los vídeos y enseña los textos; no publica")
    p.add_argument("--solo", help="solo estas redes (separadas por comas)")
    p.add_argument("--salida", help="carpeta para los vídeos (por defecto episodes/FECHA/difusion)")
    args = p.parse_args()
    resultados = difundir(args.fecha, args.simulacro, args.solo.split(",") if args.solo else None, args.salida)
    fallos = {r: v["error"] for r, v in resultados.items() if "error" in v}
    if fallos:
        sys.exit(f"Han fallado: {', '.join(fallos)}.")


if __name__ == "__main__":
    main()
