"""Cátodo en ops (trabajo catodo.preparar, ops#118): la decisión y la respuesta.

Uso (lo lanzan scripts/ops/preparar.sh y scripts/ops/responder.sh):
    python src/ops.py preparar --fecha AAAA-MM-DD
    python src/ops.py decision --fecha AAAA-MM-DD
    python src/ops.py responder

preparar: lo de `make noche`, paso a paso. El token de Claude que da ops por el
descriptor de OPS_CLAUDE_TOKEN_FD solo se puede leer una vez: se lee aquí, lo
primero, y a los pasos que llaman a Claude (rank y script) se les pasa por un
descriptor nuevo cada vez. Los demás no lo ven.

decision: tras preparar el episodio, sube el MP3 y el guion a una ruta de R2 no
enlazada (revision/<fecha>-<aleatorio>), y deja en OPS_DECISION_FILE la decisión
que ops abre en el móvil: resumen, puntos a comprobar, orden del episodio y los
enlaces para escucharlo y leerlo. Opciones: «Aprobar y programar» y «No publicar»,
que es la de por defecto porque no cambia nada.

responder: lo corre ops cuando Ulises elige una opción (OPS_DECISION_OPTION). Con
«aprobar» deja la aprobación humana en la memoria del episodio y lo programa como
`make programar`, pero sin push: deja el commit y lo empuja ops a la rama
programado. En los dos casos borra el audio y el guion de revisión de R2. Lo que
cuenta va a OPS_REPLY_NOTE_FILE, que ops pone como nota en el hilo.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import claude_cli
import memoria
from comun import EPISODIOS, RAIZ, cargar_env

CARPETA_REVISION = "revision"
OPCION_APROBAR = "aprobar"
OPCION_NO_PUBLICAR = "no-publicar"
OPCIONES = [
    {"key": OPCION_APROBAR, "label": "Aprobar y programar"},
    {"key": OPCION_NO_PUBLICAR, "label": "No publicar"},
]
# Lo que admite ops en el cuerpo de una decisión.
MAX_CUERPO = 10_000
FECHA = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


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


def cuerpo_decision(fecha, revision_md, url_audio, url_guion, minutos):
    """El cuerpo de la decisión: lo que hay que mirar, sin «Qué tienes que hacer» (es del Mac)."""
    partes = secciones(revision_md)
    cabecera = re.sub(r"(?m)^# .*\n?", "", partes.get("", "")).strip()
    lineas = [
        f"Episodio del **{fecha}**, unos {minutos:.0f} minutos.",
        "",
        f"- [Escuchar el episodio]({url_audio})",
        f"- [Leer el guion]({url_guion})",
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
    lineas += ["", "«Aprobar y programar» deja constancia de tu revisión y lo publica a las 6:00. "
                   "«No publicar» no cambia nada."]
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
    for script, con_claude in PASOS:
        print(f"== {script}", flush=True)
        paso(script, fecha, token if con_claude else None)
    decision(fecha)


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
    bucket = env.get("R2_BUCKET", "catodo-audio")
    prefijo = f"{CARPETA_REVISION}/{fecha}-{secrets.token_urlsafe(16)}"
    claves = {"audio": f"{prefijo}.mp3", "guion": f"{prefijo}-guion.txt"}
    r2 = cliente_r2(env)
    # Sin caché: es una ruta de un solo uso, y se borra al contestar.
    r2.upload_file(str(mp3), bucket, claves["audio"], ExtraArgs={
        "ContentType": "audio/mpeg", "CacheControl": "private, no-store"})
    r2.upload_file(str(guion), bucket, claves["guion"], ExtraArgs={
        "ContentType": "text/plain; charset=utf-8", "CacheControl": "private, no-store"})
    (carpeta / "revision-ops.json").write_text(json.dumps(claves), encoding="utf-8")
    url_audio = f"{base_publica(env)}/{claves['audio']}"
    publish.comprobar_url(url_audio, mp3.stat().st_size)

    datos = {
        "message": cuerpo_decision(fecha, revision.read_text(encoding="utf-8"), url_audio,
                                   f"{base_publica(env)}/{claves['guion']}", publish.duracion(mp3) / 60),
        "decision": {"title": titulo(fecha), "options": OPCIONES, "defaultOption": OPCION_NO_PUBLICAR},
    }
    Path(destino).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(f"Decisión lista para ops: {titulo(fecha)}")


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


def responder():
    opcion = os.environ.get("OPS_DECISION_OPTION")
    id_decision = os.environ.get("OPS_DECISION_ID", "?")
    nota_ruta = os.environ.get("OPS_REPLY_NOTE_FILE")
    with open(os.environ["OPS_DECISION_JSON"], encoding="utf-8") as f:
        hilo = json.load(f)
    if not opcion or not nota_ruta:
        sys.exit("Faltan OPS_DECISION_OPTION u OPS_REPLY_NOTE_FILE: esto lo lanza ops.")

    def nota(texto):
        Path(nota_ruta).write_text(texto, encoding="utf-8")
        print(texto)

    fecha = fecha_de_titulo(hilo.get("title"))
    if not fecha:
        nota(f"No sé de qué episodio es «{hilo.get('title')}»: no he hecho nada.")
        return
    carpeta = EPISODIOS / fecha
    env = cargar_env()

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
    memoria.aprobar(fecha, f"Aprobado en ops (decisión {id_decision}), "
                           "tras revisar los puntos a comprobar y escuchar el audio.")
    # Como `make programar`, sin push: el commit lo empuja ops a la rama programado.
    python("src/tts.py", "--fecha", fecha)
    python("src/mix.py", "--fecha", fecha)
    python("src/publish.py", "--fecha", fecha, "--programar", "--sin-push")
    borrar_revision(carpeta, env)
    publicacion = json.loads((carpeta / "publicacion.json").read_text(encoding="utf-8"))
    rama = os.environ.get("OPS_GIT_PUSH", "programado")
    nota(f"Aprobado y listo. Episodio {publicacion['numero']} ({fecha}), "
         f"[audio definitivo]({publicacion['url_audio']}). ops lo empuja a `{rama}` y "
         f"`publicar.yml` lo pasa a main el {publicacion['publicado_en'][:16].replace('T', ' a las ')} "
         "(hora de Madrid). Si esa hora ya ha pasado, lánzalo a mano: Actions > "
         "Publicar episodio programado > Run workflow, con «forzar».")


def main():
    parser = argparse.ArgumentParser(description="Cátodo en ops: decisión y respuesta")
    ordenes = parser.add_subparsers(dest="orden", required=True)
    todo = ordenes.add_parser("preparar", help="prepara el episodio y deja la decisión para ops")
    todo.add_argument("--fecha", required=True)
    abrir = ordenes.add_parser("decision", help="sube el audio de revisión y deja la decisión para ops")
    abrir.add_argument("--fecha", required=True)
    ordenes.add_parser("responder", help="aplica la opción que ha elegido Ulises")
    args = parser.parse_args()
    if args.orden == "preparar":
        preparar(args.fecha)
    elif args.orden == "decision":
        decision(args.fecha)
    else:
        responder()


if __name__ == "__main__":
    main()
