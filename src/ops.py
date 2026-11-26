"""Cátodo en ops (trabajo catodo.preparar, ops#118 y ops#122): publicación, decisión y respuesta.

Uso (lo lanzan scripts/ops/preparar.sh y scripts/ops/responder.sh):
    python src/ops.py publicar --fecha AAAA-MM-DD
    python src/ops.py preparar --fecha AAAA-MM-DD
    python src/ops.py decision --fecha AAAA-MM-DD
    python src/ops.py responder
    python src/ops.py difundir --fecha AAAA-MM-DD

publicar: lo de cada mañana desde el 26 de noviembre de 2026. Prepara el episodio
del día como preparar y lo publica solo, sin revisión previa: lo deja como
publicación automática en su memoria, sube el MP3 a R2, regenera feed y web y deja el
commit, que ops empuja a main (commandGitPush). Las personas lo revisan después, al
escucharlo, y se corrige con `make corregir`. Abre un aviso con el enlace y los puntos
a comprobar. Con redes activas, sus opciones son «Difundir en redes» y «No difundir»
(la de por defecto); sin ellas, solo «Visto».
Si una ejecución falla, la siguiente de la misma fecha retoma desde el paso que
falló: lo hecho se guarda fuera del clon, que ops limpia (CATODO_ESTADO; ver pasos).

preparar: lo de `make noche`, paso a paso. El token de Claude que da ops por el
descriptor de OPS_CLAUDE_TOKEN_FD solo se puede leer una vez: se lee aquí, lo
primero, y a los pasos que llaman a Claude (rank y script) se les pasa por un
descriptor nuevo cada vez. Los demás no lo ven.

decision: tras preparar el episodio, sube el MP3 y el guion a una ruta de R2 no
enlazada (revision/<fecha>-<aleatorio>), y deja en OPS_DECISION_FILE la decisión
que ops abre en el móvil: resumen, puntos a comprobar, orden del episodio y los
enlaces para escucharlo y leerlo. Opciones: «Aprobar y programar» y «No publicar»,
que es la de por defecto porque no cambia nada.

difundir: el episodio en las redes activas (src/redes.py). Lo hace responder al elegir
«Difundir en redes»; a mano, para repetirlo (solo publica en las redes que falten).

responder: lo corre ops cuando Ulises contesta. Con un texto (OPS_DECISION_TEXT, sin
opción) aplica el comentario al guion y deja una versión nueva para revisar
(corregir; ver src/comentarios.py). Con una opción (OPS_DECISION_OPTION). Con
«aprobar» deja la aprobación humana en la memoria del episodio y lo programa como
`make programar`, pero sin push: deja el commit y lo empuja ops a la rama
programado. En los dos casos borra el audio y el guion de revisión de R2. Lo que
cuenta va a OPS_REPLY_NOTE_FILE, que ops pone como nota en el hilo. Con «difundir»
publica el episodio en las redes activas; si alguna falla, sale con error y ops lo
reintenta (las ya publicadas no se repiten).
"""

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import claude_cli
import comentarios
import memoria
from comun import EPISODIOS, RAIZ, cargar_env
from comun import persona as persona_del_dia

CARPETA_REVISION = "revision"
OPCION_VISTO = "visto"
OPCION_DIFUNDIR = "difundir"
OPCION_NO_DIFUNDIR = "no-difundir"
OPCION_APROBAR = "aprobar"
OPCION_NO_PUBLICAR = "no-publicar"
OPCIONES = [
    {"key": OPCION_APROBAR, "label": "Aprobar y programar"},
    {"key": OPCION_NO_PUBLICAR, "label": "No publicar"},
]
# Lo que admite ops en el cuerpo de una decisión.
MAX_CUERPO = 10_000
FECHA = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
# Lo que espera «Difundir en redes» a que el episodio esté en catodo.es (GitHub Pages tarda
# unos minutos tras el push): si se elige nada más llegar el aviso, no falla por eso.
ESPERA_WEB_S = 900


def titulo(fecha):
    """Lo que sale en el push del móvil. Lleva la fecha ISO: la respuesta la saca de aquí."""
    return f"Cátodo {fecha}: revisar y aprobar"


def fecha_de_titulo(texto):
    encontrada = FECHA.search(texto or "")
    return encontrada.group(1) if encontrada else None


def secciones(markdown):
    """{título de sección ##: texto} de un markdown."""
    partes = re.split(r"(?m)^## ", markdown)
    resultado = {"": partes[0].strip()}
    for parte in partes[1:]:
        cabecera, _, cuerpo = parte.partition("\n")
        resultado[cabecera.strip()] = cuerpo.strip()
    return resultado


def cuerpo_decision(fecha, revision_md, url_audio, url_guion, minutos, url_portada=None):
    """El cuerpo de la decisión: lo que hay que mirar, sin «Qué tienes que hacer» (es del Mac)."""
    partes = secciones(revision_md)
    cabecera = re.sub(r"(?m)^# .*\n?", "", partes.get("", "")).strip()
    lineas = [
        f"Episodio del **{fecha}**, unos {minutos:.0f} minutos.",
        "",
        f"- [Escuchar el episodio]({url_audio})",
        f"- [Leer el guion]({url_guion})",
        *([f"- [Ver la portada]({url_portada}) (el guion en emojis)"] if url_portada else []),
        "",
        cabecera,
        "",
        "## Puntos a comprobar",
        "",
        partes.get("Puntos a comprobar", "Nada destacado."),
        "",
        "## Orden del episodio",
        "",
        partes.get("Orden del episodio", ""),
    ]
    if partes.get("Se queda para otro día"):
        lineas += ["", "## Se queda para otro día", "", partes["Se queda para otro día"]]
    lineas += ["", "«Aprobar y programar» deja constancia de tu revisión y lo deja en la rama `programado`. "
                   "«No publicar» no cambia nada. También puedes responder con comentarios "
                   "(«en la noticia 1 añade “presuntamente”»): los aplico y te paso la versión nueva."]
    texto = "\n".join(lineas).strip()
    if len(texto) > MAX_CUERPO:
        aviso = "\n\n(Recortado: el resto, en revision.md del estado del trabajo.)"
        texto = texto[:MAX_CUERPO - len(aviso)].rstrip() + aviso
    return texto


def cliente_r2(env):
    import boto3

    faltan = [v for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY") if not env.get(v)]
    if faltan:
        sys.exit(f"Faltan las credenciales de R2: {', '.join(faltan)}.")
    return boto3.client(
        "s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"], aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto")


def base_publica(env):
    return env.get("R2_PUBLIC_BASE_URL", "https://audio.catodo.es").rstrip("/")


# (script, si llama a Claude): lo de `make preparar` y `make audio`.
PASOS = [("src/fetch.py", False), ("src/rank.py", True), ("src/script.py", True),
         ("src/tts.py", False), ("src/mix.py", False)]

# Lo ya hecho de cada episodio, fuera del clon: ops lo deja limpio (git reset --hard y
# git clean -ffdx) antes de cada ejecución, y episodes/<fecha>/ desaparecería con todo lo
# que no está en git (noticias, pasadas, bloques de voz). Va en el HOME del trabajo
# (CATODO_ESTADO, ver scripts/ops/lib.sh), que ops conserva. Fuera de ops no se usa.
ESTADO = os.environ.get("CATODO_ESTADO")
HECHOS = ".pasos-hechos.json"
DIAS_ESTADO = 7


def carpeta_estado(fecha):
    return Path(ESTADO) / fecha if ESTADO else None


def podar_estado():
    """Borra lo guardado de episodios de hace más de DIAS_ESTADO días."""
    if not ESTADO or not Path(ESTADO).is_dir():
        return
    limite = (date.today() - timedelta(days=DIAS_ESTADO)).isoformat()
    for vieja in Path(ESTADO).iterdir():
        if vieja.is_dir() and FECHA.fullmatch(vieja.name) and vieja.name < limite:
            shutil.rmtree(vieja, ignore_errors=True)


def restaurar(fecha):
    """Si una ejecución anterior de esta fecha falló, devuelve su carpeta del episodio a
    episodes/<fecha>/ y la lista de pasos que terminó. Si no, []."""
    guardada = carpeta_estado(fecha)
    if not guardada or not guardada.is_dir():
        return []
    hechos = json.loads((guardada / HECHOS).read_text(encoding="utf-8")) if (guardada / HECHOS).exists() else []
    shutil.copytree(guardada, EPISODIOS / fecha, dirs_exist_ok=True, ignore=shutil.ignore_patterns(HECHOS))
    print(f"Retomo el {fecha} de una ejecución anterior: hechos {', '.join(hechos) or 'ninguno'}.", flush=True)
    return hechos


def guardar(fecha, hechos):
    """Copia episodes/<fecha>/ fuera del clon con los pasos terminados. Se copia entero en
    una carpeta nueva y luego se cambia por la anterior: si se corta a medias, la de antes
    sigue entera."""
    guardada = carpeta_estado(fecha)
    origen = EPISODIOS / fecha
    if not guardada or not origen.is_dir():
        return
    nueva = guardada.with_name(f"{fecha}.nueva")
    shutil.rmtree(nueva, ignore_errors=True)
    shutil.copytree(origen, nueva)
    (nueva / HECHOS).write_text(json.dumps(hechos), encoding="utf-8")
    shutil.rmtree(guardada, ignore_errors=True)
    nueva.rename(guardada)


def olvidar(fecha):
    """El episodio salió bien: relanzar el trabajo vuelve a empezar de cero."""
    guardada = carpeta_estado(fecha)
    if guardada:
        shutil.rmtree(guardada, ignore_errors=True)


def pasos(fecha, token):
    """Los pasos de la preparación, retomando donde se quedó una ejecución anterior que falló:
    los pasos que terminó no se repiten (si falla el montaje, no se rehacen noticias, guion
    ni voz). Lo hecho se guarda aunque el paso falle: tts.py se salta los bloques ya hechos."""
    podar_estado()
    hechos = restaurar(fecha)
    rehacer = False  # rehecho un paso, se rehacen también los siguientes
    try:
        for script, con_claude in PASOS:
            if script in hechos and not rehacer:
                print(f"== {script}: hecho en una ejecución anterior", flush=True)
                continue
            rehacer = True
            hechos = [h for h in hechos if h != script]
            print(f"== {script}", flush=True)
            paso(script, fecha, token if con_claude else None)
            hechos.append(script)
    finally:
        guardar(fecha, hechos)


def paso(script, fecha, token):
    """Un paso de la preparación, en su proceso. Con token, por un descriptor suyo."""
    env = {k: v for k, v in os.environ.items() if k != "OPS_CLAUDE_TOKEN_FD"}
    extra = {}
    leer = None
    if token:
        leer, escribir = os.pipe()
        os.write(escribir, f"{token}\n".encode())
        os.close(escribir)
        env["OPS_CLAUDE_TOKEN_FD"] = str(leer)
        extra["pass_fds"] = (leer,)
    try:
        resultado = subprocess.run([sys.executable, script, "--fecha", fecha], cwd=RAIZ, env=env, **extra)
    finally:
        if leer is not None:
            os.close(leer)
    if resultado.returncode != 0:
        sys.exit(f"{script} ha fallado (código {resultado.returncode}).")


def preparar(fecha):
    token = claude_cli.token_ops()  # lo primero: luego ya no se puede leer
    pasos(fecha, token)
    portada(fecha)
    decision(fecha)
    olvidar(fecha)


def publicar(fecha):
    """Prepara el episodio del día y lo publica solo (commit sin push: lo empuja ops)."""
    token = claude_cli.token_ops()  # lo primero: luego ya no se puede leer
    pasos(fecha, token)
    portada(fecha)
    memoria.publicacion_automatica(fecha, "Publicado solo tras las comprobaciones automáticas; "
                                          "lo revisan personas después, al escucharlo.")
    print("== src/publish.py", flush=True)
    python("src/publish.py", "--fecha", fecha, "--sin-push")
    aviso_publicado(fecha)
    olvidar(fecha)


def difundir(fecha, esperar=ESPERA_WEB_S):
    """El episodio en las redes activas (src/redes.py). Falla si alguna red falla, para que
    ops lo avise y lo reintente; las demás se publican igual. Devuelve los resultados."""
    import redes
    resultados = redes.difundir(fecha, esperar=esperar)
    fallos = {r: v["error"] for r, v in resultados.items() if "error" in v}
    if fallos:
        sys.exit("Han fallado: " + "; ".join(f"{r}: {e}" for r, e in fallos.items()))
    return resultados


def cuerpo_aviso(fecha, revision_md, publicacion, rama, redes_activas=()):
    """El aviso de un episodio que ya ha salido: el enlace y lo que conviene mirar al escucharlo."""
    partes = secciones(revision_md)
    cabecera = re.sub(r"(?m)^# .*\n?", "", partes.get("", "")).strip()
    minutos = publicacion.get("duracion_s", 0) / 60
    lineas = [
        f"Episodio {publicacion['numero']} del **{fecha}**, unos {minutos:.0f} minutos. "
        f"Publicado solo: ops lo empuja a `{rama}` y en unos minutos está en catodo.es y en las apps.",
        "",
        f"- [Escuchar el episodio]({publicacion['url_audio']})",
        f"- [Página del episodio](https://catodo.es/episodios/{fecha}.html)",
        "",
        cabecera,
        "",
        *([f"«Difundir en redes» lo publica en {', '.join(nombre_red(r) for r in redes_activas)}; "
           "«No difundir» no hace nada.", ""] if redes_activas else []),
        "## Puntos a comprobar al escucharlo",
        "",
        partes.get("Puntos a comprobar", "Nada destacado."),
        "",
        "## Orden del episodio",
        "",
        partes.get("Orden del episodio", ""),
        "",
        "Si algo no cuadra, corrígelo con `make corregir`: va a las notas del episodio y se menciona en el siguiente.",
    ]
    texto = "\n".join(lineas).strip()
    if len(texto) > MAX_CUERPO:
        aviso = "\n\n(Recortado: el resto, en revision.md del estado del trabajo.)"
        texto = texto[:MAX_CUERPO - len(aviso)].rstrip() + aviso
    return texto


def nombre_red(red):
    return {"youtube": "YouTube"}.get(red, red.capitalize())


def redes_activas():
    try:  # el episodio ya está publicado: nada de aquí puede tumbar el aviso
        import redes
        return redes.activas()
    except Exception as e:  # noqa: BLE001
        print(f"Aviso: no se han podido leer las redes activas ({e}).")
        return []


def opciones_aviso(activas=None):
    """Con redes activas, «Difundir en redes» y «No difundir» (la de por defecto, que no
    cambia nada); sin ellas, solo «Visto»."""
    activas = redes_activas() if activas is None else activas
    if not activas:
        return [{"key": OPCION_VISTO, "label": "Visto"}]
    return [{"key": OPCION_DIFUNDIR, "label": "Difundir en redes"},
            {"key": OPCION_VISTO, "label": "No difundir"}]


def aviso_publicado(fecha):
    """Deja en OPS_DECISION_FILE el aviso del episodio publicado (ver opciones_aviso)."""
    destino = os.environ.get("OPS_DECISION_FILE")
    if not destino:
        print("Sin OPS_DECISION_FILE: no dejo aviso (fuera de ops).")
        return
    carpeta = EPISODIOS / fecha
    revision = carpeta / "revision.md"
    publicacion = json.loads((carpeta / "publicacion.json").read_text(encoding="utf-8"))
    activas = redes_activas()
    datos = {
        "message": cuerpo_aviso(fecha, revision.read_text(encoding="utf-8") if revision.exists() else "",
                                publicacion, os.environ.get("OPS_GIT_PUSH", "main"), activas),
        "decision": {"title": f"Cátodo {fecha}: publicado", "options": opciones_aviso(activas),
                     "defaultOption": OPCION_VISTO, "allowFreeText": False},
    }
    Path(destino).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(f"Aviso listo para ops: Cátodo {fecha}: publicado")


def portada(fecha):
    """La portada del episodio (src/portada_episodio.py). Si falla, el episodio sigue sin ella:
    no es motivo para quedarse sin programa (publish.py solo la sube si existe)."""
    carpeta = EPISODIOS / fecha
    print("== src/portada_episodio.py", flush=True)
    resultado = subprocess.run([sys.executable, "src/portada_episodio.py", "--fecha", fecha], cwd=RAIZ)
    if resultado.returncode != 0:
        print(f"Aviso: no se ha podido hacer la portada (código {resultado.returncode}); el episodio irá sin ella.",
              flush=True)
        for nombre in ("portada.jpg", "portada-web.jpg"):
            (carpeta / nombre).unlink(missing_ok=True)


def decision(fecha):
    import publish  # ffprobe y la comprobación de la URL

    carpeta = EPISODIOS / fecha
    mp3 = carpeta / f"catodo-{fecha}.mp3"
    revision = carpeta / "revision.md"
    guion = carpeta / "guion.md"
    for ruta in (mp3, revision, guion):
        if not ruta.exists():
            sys.exit(f"Falta {ruta.relative_to(RAIZ)}: la preparación no ha terminado.")
    destino = os.environ.get("OPS_DECISION_FILE")
    if not destino:
        sys.exit("Falta OPS_DECISION_FILE: esto lo lanza ops (scripts/ops/preparar.sh).")

    env = cargar_env()
    url_audio, url_guion = subir_revision(carpeta, fecha, env)
    datos = {
        "message": cuerpo_decision(fecha, revision.read_text(encoding="utf-8"), url_audio, url_guion,
                                   publish.duracion(mp3) / 60, url_portada_revision(carpeta, env)),
        "decision": decision_episodio(fecha),
    }
    Path(destino).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(f"Decisión lista para ops: {titulo(fecha)}")


def decision_episodio(fecha):
    """Las opciones de siempre, y texto libre para los comentarios (ops los atiende con responder)."""
    return {"title": titulo(fecha), "options": OPCIONES, "defaultOption": OPCION_NO_PUBLICAR,
            "allowFreeText": True}


def subir_revision(carpeta, fecha, env):
    """Sube el MP3 y el guion a una ruta nueva no enlazada de R2 (borra la anterior). Devuelve sus URL."""
    import publish

    borrar_revision(carpeta, env)
    mp3 = carpeta / f"catodo-{fecha}.mp3"
    bucket = env.get("R2_BUCKET", "catodo-audio")
    prefijo = f"{CARPETA_REVISION}/{fecha}-{secrets.token_urlsafe(16)}"
    claves = {"audio": f"{prefijo}.mp3", "guion": f"{prefijo}-guion.txt"}
    r2 = cliente_r2(env)
    # Sin caché: es una ruta de un solo uso, y se borra al contestar.
    r2.upload_file(str(mp3), bucket, claves["audio"], ExtraArgs={
        "ContentType": "audio/mpeg", "CacheControl": "private, no-store"})
    r2.upload_file(str(carpeta / "guion.md"), bucket, claves["guion"], ExtraArgs={
        "ContentType": "text/plain; charset=utf-8", "CacheControl": "private, no-store"})
    if (carpeta / "portada-web.jpg").exists():
        claves["portada"] = f"{prefijo}-portada.jpg"
        r2.upload_file(str(carpeta / "portada-web.jpg"), bucket, claves["portada"], ExtraArgs={
            "ContentType": "image/jpeg", "CacheControl": "private, no-store"})
    (carpeta / "revision-ops.json").write_text(json.dumps(claves), encoding="utf-8")
    url_audio = f"{base_publica(env)}/{claves['audio']}"
    publish.comprobar_url(url_audio, mp3.stat().st_size)
    return url_audio, f"{base_publica(env)}/{claves['guion']}"


def url_portada_revision(carpeta, env):
    """La URL de la portada que subió subir_revision, o None si no hay."""
    ruta = carpeta / "revision-ops.json"
    clave = json.loads(ruta.read_text(encoding="utf-8")).get("portada") if ruta.exists() else None
    return f"{base_publica(env)}/{clave}" if clave else None


def borrar_revision(carpeta, env):
    """Borra de R2 el audio y el guion de revisión, si los hay. No falla si ya no están."""
    ruta = carpeta / "revision-ops.json"
    if not ruta.exists():
        return
    claves = json.loads(ruta.read_text(encoding="utf-8"))
    r2 = cliente_r2(env)
    for clave in claves.values():
        r2.delete_object(Bucket=env.get("R2_BUCKET", "catodo-audio"), Key=clave)
    ruta.unlink()


def python(*argumentos):
    subprocess.run([sys.executable, *argumentos], cwd=RAIZ, check=True)


def corregir(fecha, comentario, hilo, nota):
    """Aplica un comentario de Ulises y deja la ronda nueva en OPS_DECISION_ROUND_FILE.

    Se puede repetir: si systemd lo reintenta (falló la voz, R2 u ops), el comentario
    ya aplicado no se vuelve a aplicar (comentarios-ops/<mensaje>.json), y la voz, el
    montaje y la subida se rehacen siempre (tts.py y mix.py van por caché): lo que se
    enseña es siempre lo que hay en guion.md.
    """
    import publish
    import script
    from comun import CONFIG, cargar_yaml
    from reservas import Reservas

    carpeta = EPISODIOS / fecha
    guion_ruta, notas_ruta = carpeta / "guion.md", carpeta / "notas.md"
    if not guion_ruta.exists() or not (carpeta / f"catodo-{fecha}.mp3").exists():
        nota(f"El episodio del {fecha} ya no está en ops (lo ha limpiado una preparación posterior): "
             "no puedo aplicar el comentario.")
        return
    anteriores = comentarios.comentarios_anteriores(hilo)
    version = len(anteriores) + 2  # la 1 es la de la preparación
    hecho_ruta = carpeta / "comentarios-ops" / f"{comentarios.clave_comentario(hilo)}.json"
    if hecho_ruta.exists():
        print("Comentario ya aplicado en un intento anterior: rehago la voz y la subida.", flush=True)
        hecho = json.loads(hecho_ruta.read_text(encoding="utf-8"))
    else:
        ajustes = cargar_yaml("settings.yaml")
        cl = ajustes["claude"]
        persona = persona_del_dia(fecha)
        escaleta_ruta = carpeta / "escaleta.json"
        escaleta = (script.json_bonito(script.preparar_escaleta(json.loads(escaleta_ruta.read_text(encoding="utf-8")),
                                                                Reservas()))
                    if escaleta_ruta.exists() else "(no está)")
        guion = guion_ruta.read_text(encoding="utf-8")
        notas = notas_ruta.read_text(encoding="utf-8") if notas_ruta.exists() else ""
        emojis_ruta = carpeta / "emojis.txt"
        emojis = emojis_ruta.read_text(encoding="utf-8").strip() if emojis_ruta.exists() else ""

        print("Aplicando el comentario…", flush=True)
        correccion = claude_cli.llamar(
            comentarios.CORRECCION.format(persona=persona, escaleta=escaleta, comentario=comentario,
                                          anteriores="\n\n".join(anteriores) or "(ninguno)", guion=guion, notas=notas,
                                          emojis=emojis or "(no hay)", reglas_emojis=script.reglas_emojis()),
            modelo=cl["modelo_guion"], esfuerzo=cl.get("esfuerzo_guion"), esquema=comentarios.ESQUEMA_CORRECCION,
            herramientas=script.LEER_FUENTES, registro=carpeta / "pasadas" / f"comentario-{version}.json",
            tiempo_max=cl["tiempo_max_pasada_s"])
        nuevo = correccion["guion"].strip() + "\n"
        notas_nuevas = (correccion["notas"].strip() + "\n") if correccion["notas"].strip() else notas
        cambios_texto = comentarios.diferencias(guion, nuevo) + "\n" + comentarios.diferencias(notas, notas_nuevas)
        problemas = []
        # Siempre que cambie algo: lo que diga el modelo de sí mismo no basta.
        if cambios_texto.strip():
            print("Verificando lo que ha cambiado…", flush=True)
            verificacion = claude_cli.llamar(
                script.VERIFICACION.format(persona=persona, escaleta=escaleta, guion=nuevo)
                + comentarios.VERIFICAR_CAMBIOS.format(diferencias=cambios_texto),
                modelo=cl["modelo_guion"], esfuerzo=cl.get("esfuerzo_guion"), esquema=script.ESQUEMA_VERIFICACION,
                herramientas=script.LEER_FUENTES,
                registro=carpeta / "pasadas" / f"comentario-{version}-verificacion.json",
                tiempo_max=cl["tiempo_max_pasada_s"])
            problemas = verificacion["problemas"]
        hecho = {"version": version, "correccion": correccion, "problemas": problemas,
                 "bloques": comentarios.bloques_cambiados(guion, nuevo),
                 "notas_cambiadas": comentarios.diferencias(notas, notas_nuevas)}
        guion_ruta.write_text(nuevo, encoding="utf-8")
        notas_ruta.write_text(notas_nuevas, encoding="utf-8")
        script.escribir_emojis(carpeta, correccion.get("emojis", []))
        comentarios.actualizar_memoria(carpeta / "memoria.json", correccion)
        with open(carpeta / "revision.md", "a", encoding="utf-8") as f:
            f.write(comentarios.apunte_revision(version, comentario, correccion, problemas))
        hecho_ruta.parent.mkdir(exist_ok=True)
        hecho_ruta.write_text(json.dumps(hecho, ensure_ascii=False), encoding="utf-8")

    # Siempre: tts.py solo rehace los bloques cuyo texto ha cambiado.
    python("src/tts.py", "--fecha", fecha)
    python("src/mix.py", "--fecha", fecha)
    portada(fecha)  # por si el comentario ha cambiado el guion en emojis
    env = cargar_env()
    url_audio, url_guion = subir_revision(carpeta, fecha, env)
    mp3 = carpeta / f"catodo-{fecha}.mp3"
    ronda = {
        "message": comentarios.mensaje_ronda(fecha, hecho["version"], hecho["correccion"], hecho["problemas"],
                                             hecho["bloques"], url_audio, url_guion, publish.duracion(mp3) / 60,
                                             hecho["notas_cambiadas"], url_portada_revision(carpeta, env)),
        "decision": decision_episodio(fecha),
    }
    Path(os.environ["OPS_DECISION_ROUND_FILE"]).write_text(json.dumps(ronda, ensure_ascii=False), encoding="utf-8")
    print(ronda["message"])


def nota_de_aprobacion(hilo, id_decision):
    """La nota de la aprobación: lo que haya escrito Ulises junto a la opción, como NOTA= en el Mac."""
    texto = next((m.get("body") for m in reversed(hilo.get("messages", []))
                  if m.get("author") == "user" and m.get("optionKey") and (m.get("body") or "").strip()), None)
    base = f"Aprobado en ops (decisión {id_decision}), tras revisar los puntos a comprobar y escuchar el audio."
    return f"{base} {texto.strip()}" if texto else base


def responder():
    opcion = os.environ.get("OPS_DECISION_OPTION")
    texto = os.environ.get("OPS_DECISION_TEXT")
    id_decision = os.environ.get("OPS_DECISION_ID", "?")
    nota_ruta = os.environ.get("OPS_REPLY_NOTE_FILE")
    with open(os.environ["OPS_DECISION_JSON"], encoding="utf-8") as f:
        hilo = json.load(f)
    if not (opcion or texto) or not nota_ruta:
        sys.exit("Faltan OPS_DECISION_OPTION (o OPS_DECISION_TEXT) u OPS_REPLY_NOTE_FILE: esto lo lanza ops.")

    def nota(texto):
        Path(nota_ruta).write_text(texto, encoding="utf-8")
        print(texto)

    fecha = fecha_de_titulo(hilo.get("title"))
    if not fecha:
        nota(f"No sé de qué episodio es «{hilo.get('title')}»: no he hecho nada.")
        return
    carpeta = EPISODIOS / fecha
    env = cargar_env()

    if opcion == OPCION_VISTO:
        nota(f"Visto el episodio del {fecha}.")
        return
    if opcion == OPCION_NO_DIFUNDIR:  # avisos abiertos antes de que la difusión dependiera de la decisión
        nota(f"No se difunde el episodio del {fecha} en redes.")
        return
    if opcion == OPCION_DIFUNDIR:
        # Si alguna red falla, sale con error: ops lo reintenta y solo se repiten las que faltan.
        resultados = difundir(fecha)
        lineas = [f"- {nombre_red(r)}: {v['url']}" if v.get("url") else f"- {nombre_red(r)}: publicado"
                  for r, v in resultados.items()]
        nota(f"Episodio del {fecha} difundido en redes.\n\n" + "\n".join(lineas) if lineas
             else f"El episodio del {fecha} ya estaba en todas las redes activas: no he publicado nada.")
        return
    if not opcion:
        # Un comentario: el texto no autoriza a publicar, solo a preparar otra versión.
        corregir(fecha, texto, hilo, nota)
        return
    if opcion == OPCION_NO_PUBLICAR:
        borrar_revision(carpeta, env)
        nota(f"No se publica el episodio del {fecha}. Se ha borrado el audio de revisión.")
        return
    if opcion != OPCION_APROBAR:
        nota(f"Opción desconocida «{opcion}»: no he hecho nada.")
        return

    mem = memoria.leer(fecha)
    if mem is None or not (carpeta / f"catodo-{fecha}.mp3").exists():
        # Lo limpió una preparación posterior: repetir no lo arregla.
        nota(f"El episodio del {fecha} ya no está en ops (lo ha limpiado una preparación posterior): "
             "no se ha programado nada.")
        return
    memoria.aprobar(fecha, nota_de_aprobacion(hilo, id_decision))
    # Como `make programar`, sin push: el commit lo empuja ops a la rama programado.
    python("src/tts.py", "--fecha", fecha)
    python("src/mix.py", "--fecha", fecha)
    python("src/publish.py", "--fecha", fecha, "--programar", "--sin-push")
    borrar_revision(carpeta, env)
    publicacion = json.loads((carpeta / "publicacion.json").read_text(encoding="utf-8"))
    rama = os.environ.get("OPS_GIT_PUSH", "programado")
    nota(f"Aprobado y listo. Episodio {publicacion['numero']} ({fecha}), "
         f"[audio definitivo]({publicacion['url_audio']}). ops lo empuja a `{rama}`; para publicarlo, "
         "pásalo a main a mano: Actions › Publicar episodio programado › Run workflow.")


def main():
    parser = argparse.ArgumentParser(description="Cátodo en ops: decisión y respuesta")
    ordenes = parser.add_subparsers(dest="orden", required=True)
    solo = ordenes.add_parser("publicar", help="prepara el episodio del día y lo publica solo (lo empuja ops)")
    solo.add_argument("--fecha", required=True)
    todo = ordenes.add_parser("preparar", help="prepara el episodio y deja la decisión para ops")
    todo.add_argument("--fecha", required=True)
    abrir = ordenes.add_parser("decision", help="sube el audio de revisión y deja la decisión para ops")
    abrir.add_argument("--fecha", required=True)
    ordenes.add_parser("responder", help="aplica la opción que ha elegido Ulises")
    redes_ = ordenes.add_parser("difundir", help="publica el episodio del día en las redes activas")
    redes_.add_argument("--fecha", required=True)
    args = parser.parse_args()
    if args.orden == "publicar":
        publicar(args.fecha)
    elif args.orden == "preparar":
        preparar(args.fecha)
    elif args.orden == "decision":
        decision(args.fecha)
    elif args.orden == "difundir":
        difundir(args.fecha)
    else:
        responder()


if __name__ == "__main__":
    main()
