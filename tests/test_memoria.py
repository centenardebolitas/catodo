"""Pruebas de la memoria de episodios anteriores: python -m unittest discover -s tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import memoria  # noqa: E402

GUION = """## Apertura

Buenos días, soy Cátodo, una inteligencia artificial escéptica. Hoy te traigo lo de Nvidia, que vuelve a tener jefe. Y además, Mercurio.

## Noticia 1: Nvidia

Texto.
"""


class Aperturas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        dia = self.raiz / "2026-11-24"
        dia.mkdir()
        (dia / "guion.md").write_text(GUION, encoding="utf-8")
        (dia / "memoria.json").write_text(json.dumps({"publicado": True, "contadas": []}), encoding="utf-8")
        self.parche = mock.patch.object(memoria, "EPISODIOS", self.raiz)
        self.parche.start()

    def tearDown(self):
        self.parche.stop()
        self.tmp.cleanup()

    def test_solo_el_enlace_sin_la_firma(self):
        self.assertEqual(memoria.apertura("2026-11-24"), "Hoy te traigo lo de Nvidia, que vuelve a tener jefe.")
        self.assertIsNone(memoria.apertura("2026-11-20"))

    def test_el_contexto_lleva_los_enlaces_anteriores(self):
        texto = memoria.contexto("2026-11-25")
        self.assertIn("no repitas la fórmula", texto)
        self.assertIn("- (2026-11-24) Hoy te traigo lo de Nvidia", texto)
        self.assertNotIn("escéptica", texto)


if __name__ == "__main__":
    unittest.main()
