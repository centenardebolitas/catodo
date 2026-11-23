"""Fase 4: publica un episodio aprobado.

Uso:
    python src/publish.py [--fecha AAAA-MM-DD] [--simulacro] [--sin-push] [--programar]

Pasos:
  1. Comprueba que el episodio está aprobado (make aprobar) y que existe su MP3 (make audio).
  2. Limpia las notas: las redirecciones de Google News se quedan solo con el nombre del medio.
  3. Sube el MP3 a Cloudflare R2 y comprueba que se descarga desde la URL pública.
  4. Escribe publicacion.json y regenera docs/feed.xml, docs/index.html y docs/episodios/.
  5. Marca el episodio como publicado en la memoria.
  6. Commit y push de lo público: docs/ y guion, notas, memoria y publicación del episodio.

Con --simulacro no sube nada, no toca la memoria ni git, y genera el feed y la web en
una carpeta temporal para revisarlos.

Con --programar el episodio queda listo pero no se publica: el audio se sube a R2, el
commit se hace en local y se envía a la rama `programado`, con fecha de publicación a la
HORA_PUBLICACION de Madrid. A esa hora, la tarea de GitHub (.github/workflows/publicar.yml)
pasa la rama a main y GitHub Pages actualiza la web y el feed. Si esa hora ya ha pasado,
se publica en el momento.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import feed
import memoria
from comun import EPISODIOS, RAIZ, cargar_env

CARPETA_R2 = "episodios"
ZONA = ZoneInfo("Europe/Madrid")
HORA_PUBLICACION = time(6, 0)
RAMA_PROGRAMADA = "programado"


def duracion(ruta):
    salida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(ruta)], capture_output=True, text=True)
    try:
        return float(salida.stdout.strip())
    except ValueError:
        sys.exit(f"No se ha podido leer la duración de {ruta} (¿está instalado ffmpeg?).")


def limpiar_notas(ruta):
    """Los enlaces de Google News son redirecciones: se deja el nombre del medio sin enlace."""
    texto = ruta.read_text(encoding="utf-8")
    limpio = re.sub(r"\[([^\]]+)\]\(https?://news\.google\.com/[^)]*\)", r"\1", texto)
    if limpio != texto:
        ruta.write_text(limpio, encoding="utf-8")
        print("  Notas: quitados los enlaces de redirección de Google News.")


def subir_a_r2(mp3, clave_r2, env):
    import boto3  # solo hace falta al publicar de verdad

    faltan = [v for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
              if not env.get(v)]
    if faltan:
        sys.exit(f"Faltan en .env: {', '.join(faltan)} (Fase 0.2).")
    cliente = boto3.client(
        "s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"], aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto")
    cliente.upload_file(str(mp3), env["R2_BUCKET"], clave_r2, ExtraArgs={
        "ContentType": "audio/mpeg", "CacheControl": "public, max-age=31536000, immutable"})


def comprobar_url(url, bytes_esperados):
    import requests
    r = requests.head(url, timeout=30, allow_redirects=True)
    if r.status_code != 200:
        sys.exit(f"El audio no se descarga desde {url} (HTTP {r.status_code}). Revisa el dominio de R2.")
    tamano = int(r.headers.get("Content-Length", 0))
    if tamano and tamano != bytes_esperados:
        sys.exit(f"El tamaño publicado ({tamano}) no coincide con el del MP3 ({bytes_esperados}).")


def git(*argumentos):
    subprocess.run(["git", *argumentos], cwd=RAIZ, check=True)


def main():
    parser = argparse.ArgumentParser(description="Publica un episodio de Cátodo")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--simulacro", action="store_true", help="prueba sin subir nada ni tocar git")
    parser.add_argument("--sin-push", action="store_true", help="hace commit pero no push")
    parser.add_argument("--programar", action="store_true",
                        help="deja el episodio listo para que GitHub lo publique a las 6:00 de Madrid")
    args = parser.parse_args()

    carpeta = EPISODIOS / args.fecha
    mem = memoria.leer(args.fecha)
    if mem is None:
        sys.exit(f"No hay guion para {args.fecha}.")
    if not mem.get("revision_humana", {}).get("aprobado"):
        if args.simulacro:
            print("Aviso: el episodio no está aprobado (en un simulacro se permite).")
        else:
            sys.exit(f"El episodio no está aprobado: revísalo y ejecuta `make aprobar FECHA={args.fecha}`.")
    mp3 = carpeta / f"catodo-{args.fecha}.mp3"
    if not mp3.exists():
        sys.exit(f"No existe {mp3.name}: ejecuta antes `make audio FECHA={args.fecha}`.")

    env = cargar_env()
    clave_r2 = f"{CARPETA_R2}/{mp3.name}"
    url_audio = f"{env.get('R2_PUBLIC_BASE_URL', 'https://audio.catodo.es').rstrip('/')}/{clave_r2}"
    bytes_mp3 = mp3.stat().st_size

    publicacion = carpeta / "publicacion.json"
    anteriores = [p for p in EPISODIOS.glob("*/publicacion.json") if p != publicacion]
    numero = (json.loads(publicacion.read_text())["numero"] if publicacion.exists() else len(anteriores) + 1)
    datos = {
        "fecha": args.fecha,
        "numero": numero,
        "url_audio": url_audio,
        "bytes": bytes_mp3,
        "duracion_s": round(duracion(mp3), 1),
        "publicado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    programado = False
    if args.programar:
        hora = datetime.combine(date.fromisoformat(args.fecha), HORA_PUBLICACION, ZONA)
        if hora > datetime.now(ZONA):
            programado = True
            datos["publicado_en"] = hora.isoformat(timespec="seconds")
        else:
            print(f"Las {HORA_PUBLICACION:%H:%M} del {args.fecha} ya han pasado: se publica ahora.")

    if args.simulacro:
        temporal = Path(tempfile.mkdtemp(prefix="catodo-simulacro-"))
        copia_notas = (carpeta / "notas.md").read_text(encoding="utf-8")
        try:
            limpiar_notas(carpeta / "notas.md")
            publicacion.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            shutil.copy(RAIZ / "docs" / "legal.html", temporal / "legal.html")
            episodios = feed.generar_todo(temporal)
        finally:
            publicacion.unlink(missing_ok=True)
            (carpeta / "notas.md").write_text(copia_notas, encoding="utf-8")
        print(f"Simulacro: {len(episodios)} episodios. Feed y web en {temporal}")
        print(f"  (el audio se publicaría en {url_audio}, {bytes_mp3 / 1e6:.1f} MB)")
        return

    print(f"{'Programando' if programado else 'Publicando'} el episodio {numero} ({args.fecha})…")
    limpiar_notas(carpeta / "notas.md")
    print(f"  Subiendo {mp3.name} a R2…")
    subir_a_r2(mp3, clave_r2, env)
    comprobar_url(url_audio, bytes_mp3)
    print(f"  Audio disponible en {url_audio}")
    publicacion.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    feed.generar_todo()
    memoria.marcar_publicado(args.fecha)
    print("  Feed, web y memoria actualizados.")

    publicos = ["docs", f"episodes/{args.fecha}/guion.md", f"episodes/{args.fecha}/notas.md",
                f"episodes/{args.fecha}/memoria.json", f"episodes/{args.fecha}/publicacion.json"]
    publicos += [str(p.relative_to(RAIZ)) for p in EPISODIOS.glob("*/memoria.json")]  # correcciones saldadas
    git("add", *publicos)
    git("commit", "-q", "-m", f"Episodio {numero} ({args.fecha})")
    if args.sin_push:
        return
    if programado:
        # main se queda en local; la tarea de GitHub lo publicará desde la rama programada.
        git("push", "-q", "-f", "origin", f"HEAD:refs/heads/{RAMA_PROGRAMADA}")
        print(f"  Programado: se publicará el {args.fecha} a las {HORA_PUBLICACION:%H:%M} (hora de Madrid).")
    else:
        git("push", "-q")
        print("  Publicado: GitHub Pages actualizará catodo.es/feed.xml en uno o dos minutos.")


if __name__ == "__main__":
    main()
