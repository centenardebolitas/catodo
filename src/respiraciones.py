"""Suaviza las inspiraciones de la voz sintética, sin quitarlas.

Uso (lo llama mix.py con cada bloque de voz antes de montarlo):
    python src/respiraciones.py entrada.wav salida.wav [--db 12]

La voz de Gemini coge aire en casi todas las pausas (unas 20 veces por minuto, a unos
15 dB por debajo de la voz), y tras normalizar el volumen se oye demasiado y demasiado
igual. Aquí se busca cada pausa (tramos más de 13 dB por debajo de la voz) que lleve un
ruido de aire (sonido sordo, con muchos cruces por cero) y se baja ese ruido unos dB
(audio.respiraciones_db en settings.yaml; 0 lo desactiva). No se quita: sin ninguna
respiración la voz suena a robot. La voz no se toca, y la duración tampoco (los
capítulos dependen de ella).
"""

import argparse
import array
import math
import wave

TRAMA_S = 0.01            # análisis en tramas de 10 ms
PAUSA_BAJO_VOZ_DB = 13    # una pausa: más de esto por debajo del nivel de la voz
AUDIBLE_BAJO_VOZ_DB = 40  # lo que se oye dentro de la pausa
CRUCES_AIRE = 0.12        # cruces por cero por muestra: el aire es ruido, la voz no
PAUSA_MIN_TRAMAS = 15     # pausas de al menos 150 ms
AIRE_MIN_TRAMAS = 8       # con al menos 80 ms de aire
RAMPA_S = 0.015


def _tramas(muestras, largo):
    """(dB, cruces por cero por muestra) de cada trama."""
    resultado = []
    for i in range(0, len(muestras) - largo + 1, largo):
        seg = muestras[i:i + largo]
        rms = math.sqrt(sum(x * x for x in seg) / largo) or 1e-9
        cruces = sum(1 for j in range(1, largo) if (seg[j - 1] >= 0) != (seg[j] >= 0)) / largo
        resultado.append((20 * math.log10(rms / 32768), cruces))
    return resultado


def tramos_de_aire(tramas):
    """[(trama inicial, trama final)] de las inspiraciones a suavizar."""
    if not tramas:
        return []
    voz = sorted(db for db, _ in tramas)[int(len(tramas) * 0.95)]
    pausa, audible = voz - PAUSA_BAJO_VOZ_DB, voz - AUDIBLE_BAJO_VOZ_DB
    tramos, i = [], 0
    while i < len(tramas):
        if tramas[i][0] >= pausa:
            i += 1
            continue
        j = i
        while j < len(tramas) and tramas[j][0] < pausa:
            j += 1
        aire = [k for k in range(i, j) if tramas[k][0] > audible and tramas[k][1] > CRUCES_AIRE]
        if j - i >= PAUSA_MIN_TRAMAS and len(aire) >= AIRE_MIN_TRAMAS:
            tramos.append((max(i + 1, aire[0] - 2), min(j - 1, aire[-1] + 3)))
        i = j
    return tramos


def suavizar(entrada, salida, db=12.0):
    """Escribe `salida` con las inspiraciones `db` dB más bajas. Devuelve cuántas ha tocado."""
    with wave.open(str(entrada)) as w:
        params = w.getparams()
        muestras = array.array("h", w.readframes(w.getnframes()))
    if params.sampwidth != 2 or params.nchannels != 1:
        raise ValueError(f"{entrada}: se espera WAV mono de 16 bits")
    largo = max(1, int(params.framerate * TRAMA_S))
    tramos = tramos_de_aire(_tramas(muestras, largo)) if db > 0 else []
    ganancia = 10 ** (-db / 20)
    rampa = max(1, int(params.framerate * RAMPA_S))
    for ini, fin in tramos:
        a, b = ini * largo, min(len(muestras), fin * largo)
        for s in range(a, b):
            # rampa de coseno a la entrada y a la salida del tramo, para que no haya chasquidos
            borde = min(s - a, b - 1 - s)
            f = ganancia if borde >= rampa else 1 - (1 - ganancia) * (0.5 - 0.5 * math.cos(math.pi * borde / rampa))
            muestras[s] = int(muestras[s] * f)
    with wave.open(str(salida), "wb") as w:
        w.setparams(params)
        w.writeframes(muestras.tobytes())
    return len(tramos)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("entrada")
    p.add_argument("salida")
    p.add_argument("--db", type=float, default=12.0)
    args = p.parse_args()
    print(f"Inspiraciones suavizadas: {suavizar(args.entrada, args.salida, args.db)}")


if __name__ == "__main__":
    main()
