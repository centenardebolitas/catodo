"""Vídeos para las redes a partir de un episodio publicado.

Uso:
    python src/difusion.py --fecha AAAA-MM-DD [--salida carpeta]

Deja en episodes/FECHA/difusion/ (o en --salida):
  - clip.mp4: vertical (1080x1920), de unos 45-60 s, con la primera noticia del episodio:
    la portada del episodio, el título de la noticia, la forma de onda y subtítulos. Para
    Instagram (Reels), Facebook, Threads y YouTube Shorts.
  - episodio.mp4: horizontal (1920x1080), el episodio entero con la portada y el título de
    cada capítulo mientras suena. Para YouTube.

Parte de lo que ya está publicado (publicacion.json, capitulos.json, guion.md y el MP3 de
R2), así que se puede rehacer en cualquier momento y en cualquier máquina con ffmpeg. Los
subtítulos son el texto del guion: cada frase se coloca en proporción a su longitud y se
ajusta al silencio más cercano del audio (la voz hace una pausa al terminar cada frase).
Los textos se dibujan con Pillow (no hace falta un ffmpeg con libass ni freetype).
"""

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import mix
from comun import EPISODIOS, RAIZ

FUENTE = RAIZ / "assets" / "fuentes" / "TiltNeon.ttf"
NOCHE, CIAN, NUCLEO, GRIS = "#0e0d13", "#22d3ee", "#e8feff", "#9aa4b2"
CLIP_MIN_S, CLIP_MAX_S = 20.0, 58.0
PALABRAS_SUBTITULO = 9          # palabras como mucho en cada subtítulo
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


# ---------------------------------------------------------------- datos del episodio

def fecha_larga(fecha):
    d = date.fromisoformat(fecha)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def leer_json(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def titulo_episodio(carpeta):
    """El titular del episodio: la primera línea («# ...») de las notas."""
    notas = (carpeta / "notas.md").read_text(encoding="utf-8")
    encontrado = re.search(r"(?m)^# (.+)$", notas)
    return encontrado.group(1).strip() if encontrado else "Cátodo"


def bloques_guion(carpeta):
    """[(cabecera, texto)] de cada bloque del guion, en orden."""
    guion = (carpeta / "guion.md").read_text(encoding="utf-8")
    partes = re.split(r"(?m)^## (.+)$", guion)
    return [(partes[i].strip(), partes[i + 1].strip()) for i in range(1, len(partes) - 1, 2)]


def limpiar(texto):
    """El texto tal cual se oye: sin marcas de Markdown ni saltos de línea."""
    texto = re.sub(r"[*_`#>]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def frases(texto):
    return [f for f in re.split(r"(?<=[.!?…])\s+(?=[¿¡«\"A-ZÁÉÍÓÚÑ0-9])", limpiar(texto)) if f]


def trozos(frase, maximo=PALABRAS_SUBTITULO):
    """Una frase larga en trozos de pocas palabras, cortando mejor tras una coma."""
    palabras = frase.split()
    if len(palabras) <= maximo:
        return [frase]
    resultado, actual = [], []
    for p in palabras:
        actual.append(p)
        quedan = len(palabras) - sum(len(r.split()) for r in resultado) - len(actual)
        if len(actual) >= maximo or (len(actual) >= maximo // 2 and p.endswith((",", ":", ";")) and quedan > 2):
            resultado.append(" ".join(actual))
            actual = []
    if actual:
        if resultado and len(actual) <= 2:
            resultado[-1] += " " + " ".join(actual)
        else:
            resultado.append(" ".join(actual))
    return resultado


# ---------------------------------------------------------------- tiempos

def silencios(mp3, desde, hasta, umbral_db=-35, minimo_s=0.18):
    """Los centros de los silencios entre `desde` y `hasta` (segundos del MP3)."""
    proceso = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{desde:.3f}", "-t", f"{hasta - desde:.3f}", "-i", str(mp3),
         "-af", f"silencedetect=noise={umbral_db}dB:d={minimo_s}", "-f", "null", "-"],
        capture_output=True, text=True)
    inicios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", proceso.stderr)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proceso.stderr)]
    return [desde + (a + b) / 2 for a, b in zip(inicios, finales)]


def repartir(textos, inicio, fin, pausas=(), margen=1.2):
    """[(inicio, fin)] de cada texto: en proporción a su longitud entre `inicio` y `fin`, y
    cada corte llevado a la pausa más cercana si hay una a menos de `margen` segundos."""
    total = sum(len(t) for t in textos) or 1
    cortes, acumulado = [], 0
    for t in textos[:-1]:
        acumulado += len(t)
        estimado = inicio + (fin - inicio) * acumulado / total
        cercana = min(pausas, key=lambda p: abs(p - estimado), default=None)
        corte = cercana if cercana is not None and abs(cercana - estimado) <= margen else estimado
        cortes.append(max(corte, cortes[-1] + 0.3 if cortes else inicio + 0.3))
    limites = [inicio, *cortes, fin]
    return list(zip(limites[:-1], limites[1:]))


def fin_de_voz(capitulos, n, total, noticia=True):
    """Dónde acaba la voz del capítulo n: antes del «bzz» y sus pausas si es una noticia."""
    if n + 1 >= len(capitulos):
        return total
    siguiente = capitulos[n + 1]["startTime"]
    separador = RAIZ / "assets" / "separador.wav"
    if noticia and separador.exists():
        siguiente -= mix.PAUSA_ANTES_SEPARADOR_S + mix.duracion(separador) + mix.PAUSA_TRAS_SEPARADOR_S
    return siguiente


def plan_clip(texto, inicio, fin, pausas):
    """Las frases del clip y sus subtítulos: [(texto, desde, hasta)] relativos al inicio del clip.

    Se queda con las primeras frases de la noticia que quepan en CLIP_MAX_S, y termina siempre
    al final de una frase."""
    lista = frases(texto)
    tiempos = repartir(lista, inicio, fin, pausas)
    elegidas = []
    for frase, (a, b) in zip(lista, tiempos):
        if b - inicio > CLIP_MAX_S and elegidas and elegidas[-1][2] - inicio >= CLIP_MIN_S:
            break
        elegidas.append((frase, a, min(b, inicio + CLIP_MAX_S)))
        if b - inicio >= CLIP_MAX_S:
            break
    subtitulos = []
    for frase, a, b in elegidas:
        partes = trozos(frase)
        for parte, (x, y) in zip(partes, repartir(partes, a, b)):
            subtitulos.append((parte, round(x - inicio, 2), round(y - inicio, 2)))
    return subtitulos


# ---------------------------------------------------------------- dibujo

def fuente(tam):
    return ImageFont.truetype(str(FUENTE), tam)


def lineas(texto, letra, ancho):
    dibujo = ImageDraw.Draw(Image.new("L", (1, 1)))
    resultado, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if dibujo.textlength(prueba, font=letra) <= ancho or not actual:
            actual = prueba
        else:
            resultado.append(actual)
            actual = palabra
    if actual:
        resultado.append(actual)
    return resultado


def texto_centrado(lienzo, texto, y, tam, color, ancho, max_lineas=3, interlineado=1.2):
    """Escribe `texto` centrado a partir de `y`, reduciendo la letra si no cabe. Devuelve la y final."""
    while True:
        letra = fuente(tam)
        partes = lineas(texto, letra, ancho)
        if len(partes) <= max_lineas or tam <= 28:
            break
        tam -= 4
    dibujo = ImageDraw.Draw(lienzo)
    for linea in partes[:max_lineas]:
        x = (lienzo.width - dibujo.textlength(linea, font=letra)) / 2
        dibujo.text((x, y), linea, font=letra, fill=color)
        y += round(tam * interlineado)
    return y


def con_halo(lienzo, dibujar, radio=18):
    """Dibuja en una capa aparte y la pega con un halo de neón debajo."""
    capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    dibujar(capa)
    for r in (radio, radio // 2):
        lienzo.alpha_composite(capa.filter(ImageFilter.GaussianBlur(r)))
    lienzo.alpha_composite(capa)


def cargar_portada(publicacion):
    """La portada del episodio (o la del programa si no hay), como imagen RGB."""
    for url in (publicacion.get("url_portada"), "https://catodo.es/portada.jpg"):
        if not url:
            continue
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        except (requests.RequestException, OSError):
            continue
    local = RAIZ / "docs" / "portada.jpg"
    return Image.open(local).convert("RGB")


def fondo_vertical(portada, titulo_noticia, publicacion, fecha):
    lienzo = Image.new("RGBA", (1080, 1920), NOCHE)
    lienzo.paste(portada.resize((840, 840), Image.LANCZOS), (120, 150))
    texto_centrado(lienzo, f"Episodio {publicacion['numero']} · {fecha_larga(fecha)}", 1030, 40, GRIS, 960, 1)
    con_halo(lienzo, lambda capa: texto_centrado(capa, titulo_noticia, 1100, 68, CIAN, 960, 3))
    texto_centrado(lienzo, "catodo.es · tecnología cada mañana", 1820, 38, GRIS, 960, 1)
    return lienzo


def subtitulo(texto):
    capa = Image.new("RGBA", (1080, 260), (0, 0, 0, 0))
    texto_centrado(capa, texto, 10, 58, NUCLEO, 980, 3)
    return capa


def fotograma_horizontal(portada, titulo_capitulo, publicacion, fecha, titulo):
    lienzo = Image.new("RGBA", (1920, 1080), NOCHE)
    lienzo.paste(portada.resize((900, 900), Image.LANCZOS), (90, 90))
    derecha = Image.new("RGBA", (860, 1080), (0, 0, 0, 0))
    texto_centrado(derecha, f"Cátodo · episodio {publicacion['numero']}", 150, 44, GRIS, 780, 1)
    texto_centrado(derecha, fecha_larga(fecha), 210, 44, GRIS, 780, 1)
    con_halo(derecha, lambda capa: texto_centrado(capa, titulo_capitulo, 420, 76, CIAN, 780, 4))
    texto_centrado(derecha, titulo, 820, 34, GRIS, 780, 3)
    lienzo.alpha_composite(derecha, (1030, 0))
    return lienzo


# ---------------------------------------------------------------- vídeos

def ffmpeg(*argumentos):
    return mix.ffmpeg(*argumentos)


def descargar(url, destino):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for trozo in r.iter_content(1 << 20):
                f.write(trozo)
    return destino


def hacer_clip(datos, mp3, portada, salida, tmp):
    """El clip vertical de la primera noticia."""
    capitulos = datos["capitulos"]
    n = next((i for i, (cab, _) in enumerate(datos["bloques"]) if cab.lower().startswith("noticia")), 1)
    cabecera, texto = datos["bloques"][n]
    inicio = capitulos[n]["startTime"]
    fin = fin_de_voz(capitulos, n, datos["duracion"], cabecera.lower().startswith("noticia"))
    plan = plan_clip(texto, inicio, fin, silencios(mp3, inicio, fin))
    duracion = plan[-1][2] + 0.6
    fondo_vertical(portada, capitulos[n]["title"], datos["publicacion"], datos["fecha"]).convert("RGB").save(tmp / "fondo.png")
    entradas = ["-ss", f"{inicio:.3f}", "-t", f"{duracion:.3f}", "-i", str(mp3), "-loop", "1", "-i", str(tmp / "fondo.png")]
    filtros = [f"[0:a]afade=t=in:d=0.2,afade=t=out:st={duracion - 0.6:.2f}:d=0.6,asplit[a][w]",
               "[w]showwaves=s=960x200:mode=cline:rate=30:colors=0x22d3ee@0.85:scale=sqrt:draw=full,format=rgba[onda]",
               "[1:v][onda]overlay=60:1330[v0]"]
    for i, (parte, a, b) in enumerate(plan):
        ruta = tmp / f"sub{i:03d}.png"
        subtitulo(parte).save(ruta)
        entradas += ["-loop", "1", "-i", str(ruta)]
        filtros.append(f"[v{i}][{i + 2}:v]overlay=0:1560:enable='between(t,{a},{b})'[v{i + 1}]")
    ffmpeg(*entradas, "-filter_complex", ";".join(filtros), "-map", f"[v{len(plan)}]", "-map", "[a]",
           "-t", f"{duracion:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(salida))
    return {"noticia": capitulos[n]["title"], "inicio": inicio, "duracion": round(duracion, 2),
            "subtitulos": len(plan)}


def hacer_video(datos, mp3, portada, salida, tmp):
    """El episodio entero en horizontal: un fotograma por capítulo."""
    capitulos = datos["capitulos"]
    lista = []
    for i, c in enumerate(capitulos):
        ruta = tmp / f"cap{i:02d}.png"
        fotograma_horizontal(portada, c["title"], datos["publicacion"], datos["fecha"], datos["titulo"]).convert("RGB").save(ruta)
        fin = capitulos[i + 1]["startTime"] if i + 1 < len(capitulos) else datos["duracion"]
        lista += [f"file '{ruta}'", f"duration {max(fin - c['startTime'], 0.5):.3f}"]
    lista.append(f"file '{tmp / f'cap{len(capitulos) - 1:02d}.png'}'")  # el concat necesita repetir el último
    (tmp / "lista.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(tmp / "lista.txt"), "-i", str(mp3),
           "-map", "0:v", "-map", "1:a", "-r", "5", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-t", f"{datos['duracion']:.3f}",
           "-movflags", "+faststart", str(salida))


def datos_episodio(fecha):
    carpeta = EPISODIOS / fecha
    publicacion = leer_json(carpeta / "publicacion.json")
    return {"fecha": fecha, "carpeta": carpeta, "publicacion": publicacion,
            "capitulos": leer_json(carpeta / "capitulos.json")["chapters"],
            "bloques": bloques_guion(carpeta), "titulo": titulo_episodio(carpeta),
            "duracion": publicacion.get("duracion_s", 0)}


def generar(fecha, salida=None, mp3=None, video=True):
    """Hace clip.mp4 (y episodio.mp4) en `salida`. Devuelve los datos del episodio y lo hecho."""
    datos = datos_episodio(fecha)
    salida = Path(salida or datos["carpeta"] / "difusion")
    salida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="catodo-difusion-") as t:
        tmp = Path(t)
        if mp3 is None:
            local = datos["carpeta"] / f"catodo-{fecha}.mp3"
            mp3 = local if local.exists() else descargar(datos["publicacion"]["url_audio"], tmp / "episodio.mp3")
        datos["duracion"] = datos["duracion"] or mix.duracion(mp3)
        portada = cargar_portada(datos["publicacion"])
        hecho = {"clip": salida / "clip.mp4"}
        hecho["clip_info"] = hacer_clip(datos, mp3, portada, hecho["clip"], tmp)
        if video:
            hecho["video"] = salida / "episodio.mp4"
            hacer_video(datos, mp3, portada, hecho["video"], tmp)
    return datos, hecho


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fecha", required=True)
    p.add_argument("--salida", help="carpeta de salida (por defecto episodes/FECHA/difusion)")
    p.add_argument("--sin-video", action="store_true", help="solo el clip vertical")
    args = p.parse_args()
    if not (EPISODIOS / args.fecha / "publicacion.json").exists():
        sys.exit(f"El episodio del {args.fecha} no está publicado (falta publicacion.json).")
    _, hecho = generar(args.fecha, args.salida, video=not args.sin_video)
    info = hecho["clip_info"]
    print(f"Clip: {hecho['clip']} ({info['duracion']} s, «{info['noticia']}», {info['subtitulos']} subtítulos)")
    if "video" in hecho:
        print(f"Vídeo: {hecho['video']} ({mix.duracion(hecho['video']):.0f} s)")


if __name__ == "__main__":
    main()
