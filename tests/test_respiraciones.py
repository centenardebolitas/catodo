"""Pruebas del suavizado de inspiraciones: python -m unittest discover -s tests"""

import array
import math
import random
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import respiraciones  # noqa: E402

SR = 24000


def escribir(ruta, muestras):
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(array.array("h", muestras).tobytes())


def leer(ruta):
    with wave.open(str(ruta)) as w:
        return array.array("h", w.readframes(w.getnframes()))


def voz(segundos):
    """Un tono grave fuerte: «voz» sonora, con pocos cruces por cero."""
    return [int(9000 * math.sin(2 * math.pi * 140 * n / SR)) for n in range(int(SR * segundos))]


def aire(segundos, amplitud=700):
    """Ruido blanco flojo: una inspiración."""
    rnd = random.Random(1)
    return [int(rnd.uniform(-amplitud, amplitud)) for _ in range(int(SR * segundos))]


def rms(seg):
    return math.sqrt(sum(x * x for x in seg) / len(seg))


class Suavizar(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # voz 1 s, pausa con aire 0,4 s, voz 1 s
        self.original = voz(1) + aire(0.4) + voz(1)
        escribir(self.tmp / "e.wav", self.original)

    def test_baja_el_aire_y_no_toca_la_voz_ni_la_duracion(self):
        n = respiraciones.suavizar(self.tmp / "e.wav", self.tmp / "s.wav", 12)
        salida = leer(self.tmp / "s.wav")
        self.assertEqual(n, 1)
        self.assertEqual(len(salida), len(self.original))
        centro = slice(int(SR * 1.1), int(SR * 1.3))
        bajada = 20 * math.log10(rms(salida[centro]) / rms(self.original[centro]))
        self.assertAlmostEqual(bajada, -12, delta=0.5)
        self.assertEqual(list(salida[:int(SR * 0.9)]), list(self.original[:int(SR * 0.9)]))
        self.assertEqual(list(salida[int(SR * 1.5):]), list(self.original[int(SR * 1.5):]))

    def test_con_cero_db_no_cambia_nada(self):
        respiraciones.suavizar(self.tmp / "e.wav", self.tmp / "s.wav", 0)
        self.assertEqual(list(leer(self.tmp / "s.wav")), list(self.original))

    def test_una_pausa_en_silencio_no_se_toca(self):
        escribir(self.tmp / "e.wav", voz(1) + [0] * int(SR * 0.4) + voz(1))
        self.assertEqual(respiraciones.suavizar(self.tmp / "e.wav", self.tmp / "s.wav", 12), 0)


if __name__ == "__main__":
    unittest.main()
