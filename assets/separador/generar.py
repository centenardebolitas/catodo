"""Sintetiza variantes del separador entre noticias: un «bzz» eléctrico grave y corto.

Uso:
    python assets/separador/generar.py [FECHA]

Todo se genera aquí con matemáticas (sin muestras ni licencias de terceros).
Deja en esta carpeta separador-*.wav y, si existe el episodio de FECHA con sus bloques,
demos en pruebas/salida/separadores/ con el final de una noticia, el separador y el
principio de la siguiente.
"""

import math
import random
import struct
import subprocess
import sys
import wave
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[1]
FRECUENCIA = 44100
PICO = 10 ** (-16 / 20)  # pico a -16 dBFS: presente pero discreto bajo la voz


def zumbido(fase, armonicos=7, brillo=1.0):
    """Onda tipo diente de sierra suave (suma de armónicos): suena a transformador."""
    return sum(math.sin(k * fase) / (k ** (1.15 / brillo)) for k in range(1, armonicos + 1))


def escribir(nombre, muestras):
    maximo = max(abs(m) for m in muestras) or 1
    datos = b"".join(struct.pack("<h", int(32767 * PICO * m / maximo)) for m in muestras)
    ruta = CARPETA / f"separador-{nombre}.wav"
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(datos)
    return ruta


def generar():
    rnd = random.Random(7)
    variantes = {}

    # 1. Zumbido: 55 Hz con armónicos, ataque rápido y caída suave.
    n = int(0.6 * FRECUENCIA)
    variantes["1-zumbido"] = [
        zumbido(2 * math.pi * 55 * (i / FRECUENCIA)) * min(1, (i / FRECUENCIA) / 0.015) * math.exp(-4.5 * i / FRECUENCIA)
        for i in range(n)]

    # 2. Arco: 60 Hz que parpadea (modulación a 120 Hz) con algún chasquido eléctrico.
    n = int(0.5 * FRECUENCIA)
    muestras = []
    for i in range(n):
        t = i / FRECUENCIA
        base = zumbido(2 * math.pi * 60 * t, 8, 1.2) * (0.65 + 0.35 * math.sin(2 * math.pi * 120 * t))
        chispa = (rnd.uniform(-1, 1) * 1.5) if rnd.random() > 0.996 else 0
        muestras.append((base + chispa) * min(1, t / 0.008) * math.exp(-5.5 * t))
    variantes["2-arco"] = muestras

    # 3. Apagado: el zumbido baja de 110 a 40 Hz, como un aparato que se apaga.
    n, k = int(0.75 * FRECUENCIA), math.log(110 / 40) / 0.75
    variantes["3-apagado"] = [
        zumbido(2 * math.pi * 110 * (1 - math.exp(-k * t)) / k) * min(1, t / 0.01) * math.exp(-2.8 * t)
        for t in (i / FRECUENCIA for i in range(n))]

    # 4. Chispa: zumbido corto de 50 Hz con un pequeño «zap» agudo al principio.
    n = int(0.4 * FRECUENCIA)
    muestras, fase_zap = [], 0.0
    for i in range(n):
        t = i / FRECUENCIA
        f_zap = 2600 * math.exp(-t / 0.02) + 500
        fase_zap += 2 * math.pi * f_zap / FRECUENCIA
        zap = 0.35 * math.sin(fase_zap) * math.exp(-t / 0.025)
        muestras.append((zumbido(2 * math.pi * 50 * t) * min(1, t / 0.01) * math.exp(-7 * t)) + zap)
    variantes["4-chispa"] = muestras

    # 5. Doble: dos pulsos cortos, «bzz-bzz».
    n = int(0.48 * FRECUENCIA)
    muestras = []
    for i in range(n):
        t = i / FRECUENCIA
        env = (math.exp(-9 * t) * min(1, t / 0.008) if t < 0.18 else 0) + \
              (math.exp(-9 * (t - 0.26)) * min(1, (t - 0.26) / 0.008) if 0.26 <= t < 0.44 else 0)
        muestras.append(zumbido(2 * math.pi * 58 * t) * env)
    variantes["5-doble"] = muestras

    return [escribir(nombre, m) for nombre, m in variantes.items()]


def demos(separadores, fecha):
    bloques = RAIZ / "episodes" / fecha / "bloques"
    fin, inicio = bloques / "02.wav", bloques / "03.wav"
    if not (fin.exists() and inicio.exists()):
        print("No hay bloques para las demos; solo se han generado los separadores.")
        return
    salida = RAIZ / "pruebas" / "salida" / "separadores"
    salida.mkdir(parents=True, exist_ok=True)
    for sep in separadores:
        destino = salida / f"demo-{sep.stem.replace('separador-', '')}.mp3"
        filtro = ("[0:a]aresample=44100,aformat=channel_layouts=mono[a];"
                  "[1:a]aresample=44100,aformat=channel_layouts=mono[b];"
                  "[2:a]aresample=44100,aformat=channel_layouts=mono[c];"
                  "aevalsrc=0:d=0.35:s=44100[s1];aevalsrc=0:d=0.45:s=44100[s2];"
                  "[a][s1][b][s2][c]concat=n=5:v=0:a=1,loudnorm=I=-16:TP=-1.5[out]")
        subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-sseof", "-7", "-i", str(fin),
                        "-i", str(sep), "-t", "5", "-i", str(inicio), "-filter_complex", filtro,
                        "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k", str(destino)],
                       check=True, capture_output=True)
        print("Demo:", destino.relative_to(RAIZ))


def main():
    separadores = generar()
    for s in separadores:
        print("Separador:", s.relative_to(RAIZ))
    demos(separadores, sys.argv[1] if len(sys.argv) > 1 else "2026-11-23")


if __name__ == "__main__":
    main()
