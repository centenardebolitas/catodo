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

Buenos días, soy Cátodo, una inteligencia artificial. Hoy te traigo lo de Nvidia, que vuelve a tener jefe. Y además, Mercurio.

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


class Anuncios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.parche = mock.patch.object(memoria, "EPISODIOS", self.raiz)
        self.parche.start()

    def tearDown(self):
        self.parche.stop()
        self.tmp.cleanup()

    def episodio(self, fecha, contadas=(), pendientes=(), publicado=True):
        (self.raiz / fecha).mkdir()
        (self.raiz / fecha / "memoria.json").write_text(json.dumps(
            {"publicado": publicado, "contadas": list(contadas), "pendientes": list(pendientes)}), encoding="utf-8")

    def test_lo_anunciado_ayer_hay_que_contarlo_hoy(self):
        self.episodio("2026-11-27", pendientes=[{"titulo": "Tidal", "resumen": "R.", "motivo": "M.", "anunciar": True},
                                                {"titulo": "Otra", "motivo": "M."}])
        texto = memoria.contexto("2026-11-30")  # lunes: lo anunciado el viernes
        self.assertIn("## Anunciado en el episodio del 2026-11-27 para hoy (hay que contarlo)\n- **Tidal**: R.", texto)
        self.assertNotIn("- **Otra**", texto.split("para hoy")[1].split("\n\n")[0])
        self.assertIn("se anunció algo para el día siguiente 1 vez", texto)

    def test_sin_anuncio_no_hay_seccion(self):
        self.episodio("2026-11-27", pendientes=[{"titulo": "Otra", "motivo": "M."}])
        self.assertNotIn("Anunciado en", memoria.contexto("2026-11-30"))


class IndiceDeTemas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.parche = mock.patch.object(memoria, "EPISODIOS", self.raiz)
        self.parche.start()
        self.guardar("2025-11-20", [{"titulo": "La CNMC multa a Telefónica", "resumen": "Multa.",
                                     "temas": ["CNMC", "Telefónica", "IA"]}])
        self.guardar("2026-11-24", [{"titulo": "Huang vuelve a Nvidia", "resumen": "Vuelve."}])
        self.guardar("2026-11-27", [{"titulo": "Telefónica, otra vez", "resumen": "Reciente.",
                                     "temas": ["Telefónica"]}])
        self.guardar("2025-10-01", [{"titulo": "Sin publicar", "resumen": "No.", "temas": ["Telefónica"]}], False)

    def tearDown(self):
        self.parche.stop()
        self.tmp.cleanup()

    def guardar(self, fecha, contadas, publicado=True):
        (self.raiz / fecha).mkdir()
        (self.raiz / fecha / "memoria.json").write_text(
            json.dumps({"publicado": publicado, "contadas": contadas}), encoding="utf-8")

    def test_encuentra_lo_antiguo_por_tema_sin_tildes(self):
        texto = memoria.antecedentes("2026-11-30", "Candidata 0: telefonica sube precios")
        self.assertIn("(2025-11-20, por Telefónica) **La CNMC multa a Telefónica**: Multa.", texto)
        self.assertNotIn("Reciente", texto)       # de esta semana: ya está en la memoria normal
        self.assertNotIn("Sin publicar", texto)

    def test_temas_genericos_y_palabras_sueltas_no_cuentan(self):
        self.assertEqual(memoria.antecedentes("2026-11-30", "La IA en Europa"), "")
        self.assertEqual(memoria.antecedentes("2026-11-30", "Una candidata sobre cnmcx"), "")

    def test_sin_temas_usa_los_nombres_del_titulo(self):
        self.assertEqual(memoria.temas({"titulo": "Huang vuelve a Nvidia"}), ["Nvidia"])
        self.assertIn("Huang vuelve a Nvidia", memoria.antecedentes("2026-12-10", "Nvidia presenta resultados"))


class Despedida(unittest.TestCase):
    def test_segun_el_dia(self):
        self.assertEqual(comun.despedida("2026-11-26"), "Hasta mañana.")       # jueves
        self.assertEqual(comun.despedida("2026-11-27"), "Buen fin de semana.")  # viernes

    def test_la_persona_dice_la_de_hoy(self):
        texto = comun.persona("2026-11-27")
        self.assertIn("Buenos días, soy Cátodo, una inteligencia artificial que sigue la tecnología muy de cerca.", texto)
        self.assertIn('Se publica un viernes. La despedida de hoy es exactamente: "Buen fin de semana."', texto)
        self.assertTrue(texto.rstrip().endswith("El próximo episodio sale el lunes."))
        self.assertTrue(comun.persona("2026-11-26").rstrip().endswith("El próximo episodio sale mañana."))


if __name__ == "__main__":
    unittest.main()
