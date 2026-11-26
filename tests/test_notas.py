"""Pruebas del formato de las notas y la navegación entre episodios: python -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import feed  # noqa: E402
from comun import enlaces_en_linea  # noqa: E402


class EnlacesEnLinea(unittest.TestCase):
    def test_lista_a_linea(self):
        notas = ("## Noticia\nResumen.\n\n- [TechCrunch](https://a.com/1)\n* [The Verge](https://b.com/2)\n\n"
                 "## Otra\nResumen.\n\n- [Xataka](https://c.com/3)\n")
        self.assertEqual(enlaces_en_linea(notas),
                         "## Noticia\nResumen.\n\n[TechCrunch](https://a.com/1) · [The Verge](https://b.com/2)\n\n"
                         "## Otra\nResumen.\n\n[Xataka](https://c.com/3)\n")

    def test_en_linea_no_cambia(self):
        notas = "## Noticia\nResumen.\n\n[A](https://a.com) · [B](https://b.com)\n\n---\n\nAviso.\n"
        self.assertEqual(enlaces_en_linea(notas), notas)

    def test_listas_de_texto_no_se_tocan(self):
        notas = "- Un punto con [enlace](https://a.com) dentro.\n- Otro punto.\n"
        self.assertEqual(enlaces_en_linea(notas), notas)


class Vecinos(unittest.TestCase):
    EP = {"fecha": "2026-11-25", "titulo": "Huang & Tidal"}

    def test_sin_vecinos(self):
        self.assertEqual(feed.navegacion_episodios(None, None), "")

    def test_anterior_y_siguiente(self):
        html = feed.navegacion_episodios({"fecha": "2026-11-24", "titulo": "Uno"}, self.EP)
        self.assertIn('rel="prev" href="/episodios/2026-11-24.html"', html)
        self.assertIn('rel="next" href="/episodios/2026-11-25.html"', html)
        self.assertIn("Huang &amp; Tidal", html)

    def test_solo_anterior(self):
        html = feed.navegacion_episodios(self.EP, None)
        self.assertIn('rel="prev"', html)
        self.assertNotIn('rel="next"', html)


if __name__ == "__main__":
    unittest.main()
