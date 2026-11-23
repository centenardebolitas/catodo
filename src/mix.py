"""Fase 3, paso 2: monta el episodio con ffmpeg.

Uso:
    python src/mix.py [--fecha AAAA-MM-DD]

Dos etapas:
  1. Voz: une los bloques de episodes/AAAA-MM-DD/bloques/ (los genera tts.py) con una
     pausa breve entre ellos y assets/separador.wav (el «bzz») al final de cada noticia,
     y normaliza el volumen (por defecto -16 LUFS, en dos pasadas).
  2. Sintonía: assets/sintonia_intro.wav suena al principio y la voz entra a los
     SOLAPE_INTRO_S segundos mientras se funde; assets/sintonia_outro.wav suena al final.
     Un limitador evita que nada pase de -1,5 dB.
Exporta episodes/AAAA-MM-DD/catodo-AAAA-MM-DD.mp3 en mono con las etiquetas del episodio.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date

from comun import EPISODIOS, RAIZ, cargar_yaml

FRECUENCIA = 44100
PAUSA_ENTRE_BLOQUES_S = 0.7
PAUSA_ANTES_OUTRO_S = 0.6
SOLAPE_INTRO_S = 5.0
PAUSA_ANTES_SEPARADOR_S = 0.35
PAUSA_TRAS_SEPARADOR_S = 0.45
PICO_MAXIMO_DB = -1.5
AVISO_IA = "Guion y voz generados con inteligencia artificial y revisados por una persona."


def ffmpeg(*argumentos):
    proceso = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", *argumentos],
                             capture_output=True, text=True)
    if proceso.returncode != 0:
        sys.exit(f"ffmpeg ha fallado:\n{proceso.stderr[-1500:]}")
    return proceso.stderr


def duracion(ruta):
    salida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(ruta)], capture_output=True, text=True)
    return float(salida.stdout.strip() or 0)


def medir_y_normalizar(entrada, objetivo):
    """Devuelve (filtro loudnorm de segunda pasada, datos medidos) para llevar `entrada` al objetivo."""
    medida = ffmpeg("-i", str(entrada), "-af", f"loudnorm={objetivo}:print_format=json", "-f", "null", "-")
    datos = json.loads(medida[medida.rindex("{"):medida.rindex("}") + 1])
    filtro = (f"loudnorm={objetivo}:measured_I={datos['input_i']}:measured_TP={datos['input_tp']}"
              f":measured_LRA={datos['input_lra']}:measured_thresh={datos['input_thresh']}"
              f":offset={datos['target_offset']}:linear=true")
    return filtro, datos


def main():
    parser = argparse.ArgumentParser(description="Monta el audio del episodio de Cátodo")
    parser.add_argument("--fecha", default=date.today().isoformat())
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("Falta ffmpeg: instálalo con `brew install ffmpeg`.")

    audio = cargar_yaml("settings.yaml")["audio"]
    carpeta = EPISODIOS / args.fecha
    guion = (carpeta / "guion.md").read_text(encoding="utf-8")
    titulos = re.findall(r"(?m)^## (.+)$", guion)
    n_bloques = len(titulos)
    bloques = [carpeta / "bloques" / f"{n:02d}.wav" for n in range(1, n_bloques + 1)]
    faltan = [b.name for b in bloques if not b.exists()]
    if faltan:
        sys.exit(f"Faltan bloques de audio ({', '.join(faltan)}): ejecuta antes `make voz FECHA={args.fecha}`.")

    intro = RAIZ / "assets" / "sintonia_intro.wav"
    outro = RAIZ / "assets" / "sintonia_outro.wav"
    piezas = []  # (ruta o None para silencio, segundos de silencio)
    separador = RAIZ / "assets" / "separador.wav"
    for n, b in enumerate(bloques):
        piezas.append((b, 0))
        if n == len(bloques) - 1:
            continue
        if separador.exists() and titulos[n].lower().startswith("noticia"):
            # El «bzz» marca el final de cada noticia.
            piezas += [(None, PAUSA_ANTES_SEPARADOR_S), (separador, 0), (None, PAUSA_TRAS_SEPARADOR_S)]
        else:
            piezas.append((None, PAUSA_ENTRE_BLOQUES_S))

    # Todas las piezas al mismo formato (44,1 kHz, mono) y unidas en orden.
    entradas, filtros, etiquetas = [], [], []
    for i, (ruta, segundos) in enumerate(piezas):
        if ruta is None:
            entradas += ["-f", "lavfi", "-t", str(segundos), "-i", f"anullsrc=r={FRECUENCIA}:cl=mono"]
        else:
            entradas += ["-i", str(ruta)]
        filtros.append(f"[{i}:a]aresample={FRECUENCIA},aformat=sample_fmts=fltp:channel_layouts=mono[p{i}]")
        etiquetas.append(f"[p{i}]")
    union = ";".join(filtros) + f";{''.join(etiquetas)}concat=n={len(piezas)}:v=0:a=1[unido]"
    crudo = carpeta / "montaje-sin-normalizar.wav"
    ffmpeg(*entradas, "-filter_complex", union, "-map", "[unido]", str(crudo))

    # Normalización de volumen en dos pasadas: primero se mide y luego se ajusta.
    objetivo = f"I={audio['loudness_lufs']}:TP={PICO_MAXIMO_DB}:LRA=11"
    segunda, datos = medir_y_normalizar(crudo, objetivo)

    voz = carpeta / "montaje-voz.wav"
    ffmpeg("-i", str(crudo), "-af", segunda, "-ar", str(FRECUENCIA), str(voz))
    crudo.unlink()

    # Etapa 2: sintonía de entrada solapada con el saludo y sintonía de salida al final.
    entradas, filtros, cadena = ["-i", str(voz)], [], "[0:a]"
    if intro.exists():
        entradas += ["-i", str(intro)]
        retraso = int(SOLAPE_INTRO_S * 1000)
        filtros.append(f"[{len(entradas) // 2 - 1}:a]aresample={FRECUENCIA},aformat=channel_layouts=mono[intro]")
        filtros.append(f"[0:a]adelay={retraso}[vozr]")
        filtros.append("[intro][vozr]amix=inputs=2:duration=longest:normalize=0[conintro]")
        cadena = "[conintro]"
    else:
        print("Aviso: no hay assets/sintonia_intro.wav; el episodio empieza sin sintonía.")
    if outro.exists():
        entradas += ["-i", str(outro)]
        filtros.append(f"[{len(entradas) // 2 - 1}:a]aresample={FRECUENCIA},aformat=channel_layouts=mono[outro]")
        filtros.append(f"anullsrc=r={FRECUENCIA}:cl=mono:d={PAUSA_ANTES_OUTRO_S}[pausa]")
        filtros.append(f"{cadena}[pausa][outro]concat=n=3:v=0:a=1[conoutro]")
        cadena = "[conoutro]"
    else:
        print("Aviso: no hay assets/sintonia_outro.wav; el episodio termina sin sintonía.")
    filtros.append(f"{cadena}anull[final]")
    mezcla = carpeta / "montaje-mezcla.wav"
    ffmpeg(*entradas, "-filter_complex", ";".join(filtros), "-map", "[final]", str(mezcla))
    voz.unlink()

    # Normalización final de la mezcla completa, con margen para la compresión MP3.
    # El modo lineal de loudnorm se queda ~1 dB corto por el límite de pico: se compensa
    # pidiendo 1 dB más y el limitador final recoge los picos.
    objetivo_final = f"I={audio['loudness_lufs'] + 1}:TP={PICO_MAXIMO_DB - 0.5}:LRA=11"
    final, _ = medir_y_normalizar(mezcla, objetivo_final)
    limite = 10 ** ((PICO_MAXIMO_DB - 0.5) / 20)
    mp3 = carpeta / f"catodo-{args.fecha}.mp3"
    ffmpeg("-i", str(mezcla), "-af", f"{final},alimiter=limit={limite:.3f}:level=disabled",
           "-ar", str(FRECUENCIA), "-ac", str(audio["canales"]), "-c:a", "libmp3lame", "-b:a", f"{audio['bitrate_kbps']}k",
           "-metadata", f"title=Cátodo · {args.fecha}", "-metadata", "artist=Cátodo",
           "-metadata", "album=Cátodo", "-metadata", "genre=Podcast",
           "-metadata", f"date={args.fecha[:4]}", "-metadata", f"comment={AVISO_IA}", str(mp3))
    mezcla.unlink()

    segundos = duracion(mp3)
    print(f"Episodio: {mp3.relative_to(EPISODIOS.parent)} — {int(segundos // 60)} min {int(segundos % 60)} s, "
          f"{mp3.stat().st_size / 1e6:.1f} MB, volumen de entrada {datos['input_i']} LUFS → {audio['loudness_lufs']} LUFS.")


if __name__ == "__main__":
    main()
