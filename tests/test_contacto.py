"""Pruebas del formulario de contacto del pie: python -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import feed  # noqa: E402
from comun import cargar_yaml  # noqa: E402


class Contacto(unittest.TestCase):
    def setUp(self):
        self.cfg = cargar_yaml("podcast.yaml")

    def con_clave(self):
        return {**self.cfg, "contacto": {**self.cfg["contacto"], "web3forms": "clave-de-prueba"}}

    def test_con_clave_el_correo_no_sale(self):
        pie = feed.pie(self.con_clave())
        self.assertNotIn(self.cfg["email"], pie)
        self.assertIn('<a href="#contacto">Contacto</a>', pie)
        self.assertIn('<dialog id="contacto"', pie)
        self.assertIn('name="access_key" value="clave-de-prueba"', pie)
        self.assertIn('name="botcheck"', pie)
        self.assertEqual(pie.count('name="asunto"'), len(self.cfg["contacto"]["asuntos"]))
        self.assertEqual(pie.count(" checked"), 1)

    def test_sin_clave_vuelve_el_mailto(self):
        cfg = {**self.cfg, "contacto": {**self.cfg["contacto"], "web3forms": ""}}
        pie = feed.pie(cfg)
        self.assertIn(f'href="mailto:{self.cfg["email"]}"', pie)
        self.assertNotIn("<dialog", pie)

    def test_el_pie_se_sustituye_entero(self):
        """actualizar_pie cambia el pie de sobre.html y legal.html con su diálogo, sin dejar restos."""
        pagina = f"<style>\n  footer {{ x }}\n</style>\n<main>\n  {feed.pie(self.con_clave())}\n</main>"
        nuevo = feed.re.sub(r"<footer>.*?</footer>", lambda _: feed.pie(self.cfg), pagina, count=1, flags=feed.re.S)
        self.assertEqual(nuevo.count("<footer>"), 1)
        self.assertEqual(nuevo.count("</footer>"), 1)


if __name__ == "__main__":
    unittest.main()
