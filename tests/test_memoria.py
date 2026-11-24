"""Pruebas de la memoria de episodios anteriores: python -m unittest discover -s tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import comun  # noqa: E402
import memoria  # noqa: E402

GUION = """## Apertura

Buenos días, soy Cátodo, una inteligencia artificial escéptica. Hoy te traigo lo de Nvidia, que vuelve a tener jefe. Y además, Mercurio.

## Noticia 1: Nvidia

Texto.

## Cierre

Y un dato curioso. Y con esto termino. El guion y la voz los hace una inteligencia artificial, y los revisa una persona. Hasta mañana.
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

    def test_el_paso_antes_de_la_parte_fija_del_cierre(self):
        self.assertEqual(memoria.cierre("2026-11-24"), "Y con esto termino.")

    def test_el_contexto_lleva_las_formulas_anteriores(self):
        texto = memoria.contexto("2026-11-25")
        self.assertIn("no repitas las fórmulas", texto)
        self.assertIn("- (2026-11-24) Apertura: Hoy te traigo lo de Nvidia, que vuelve a tener jefe. "
                      "Cierre: Y con esto termino.", texto)
        self.assertNotIn("escéptica", texto)


class Despedida(unittest.TestCase):
    def test_segun_el_dia(self):
        self.assertEqual(comun.despedida("2026-11-26"), "Hasta mañana.")       # jueves
        self.assertEqual(comun.despedida("2026-11-27"), "Buen fin de semana.")  # viernes

    def test_la_persona_dice_la_de_hoy(self):
        texto = comun.persona("2026-11-27")
        self.assertIn("Buenos días, soy Cátodo, una inteligencia artificial escéptica.", texto)
        self.assertTrue(texto.rstrip().endswith('Se publica un viernes. La despedida de hoy es exactamente: "Buen fin de semana."'))


if __name__ == "__main__":
    unittest.main()
