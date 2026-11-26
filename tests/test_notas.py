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


class Pie(unittest.TestCase):
    CFG = {"email": "hola@catodo.es", "redes": [{"nombre": "Bluesky", "url": "https://bsky.app/profile/catodo.es",
                                                "icono": "bluesky"}]}

    def test_sin_aviso_ni_plataformas(self):
        pie = feed.pie(self.CFG)
        self.assertIn('href="/sobre.html"', pie)
        self.assertIn('aria-label="Cátodo en Bluesky"', pie)
        self.assertIn('target="_blank" rel="noopener"', pie)
        self.assertIn('fill="currentColor"', pie)
        self.assertNotIn("inteligencia artificial", pie)
        self.assertNotIn("Spotify", pie)

    def test_pagina_estatica(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "sobre.html"
            ruta.write_text("<style>\n  a { x }\n  footer { viejo }\n  footer a { viejo }\n</style>\n<main>\n"
                            "  <footer>Aviso viejo<br>enlaces</footer>\n</main>\n", encoding="utf-8")
            feed.actualizar_pie(ruta, self.CFG)
            texto = ruta.read_text(encoding="utf-8")
            self.assertNotIn("viejo", texto)
            self.assertIn("  a { x }", texto)
            self.assertIn("footer .redes", texto)
            self.assertEqual(texto.count("<footer>"), 1)
            antes = texto
            feed.actualizar_pie(ruta, self.CFG)
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)


class Cabecera(unittest.TestCase):
    EP = {"fecha": "2026-11-26", "numero": 3, "titulo": "S&P y 1Password", "duracion_s": 696.3,
          "url_portada": "https://a/grande.jpg", "url_portada_web": "https://a/web.jpg"}

    def test_ficha_con_portada(self):
        c = feed.cabecera_episodio(self.EP)
        self.assertIn("Episodio\u00a03 · 26\u00a0nov\u00a02026 · 11\u00a0min", c)
        self.assertIn('href="https://a/grande.jpg"><img src="https://a/web.jpg"', c)
        self.assertIn("<h1>S&amp;P y 1Password</h1>", c)

    def test_sin_portada(self):
        c = feed.cabecera_episodio({k: v for k, v in self.EP.items() if not k.startswith("url_portada")})
        self.assertNotIn("<img", c)
        self.assertNotIn("con-portada", c)


class Sitemap(unittest.TestCase):
    CFG = {"web": "https://catodo.es/"}
    EPS = [{"fecha": "2026-11-26", "publicado_en": "2026-11-26T09:28:35+01:00"},
           {"fecha": "2026-11-25", "publicado_en": "2026-11-25T07:00:00+01:00"}]

    def test_paginas_y_fechas(self):
        s = feed.generar_sitemap(self.EPS, self.CFG)
        self.assertIn("<url><loc>https://catodo.es/</loc><lastmod>2026-11-26</lastmod></url>", s)
        self.assertIn("<url><loc>https://catodo.es/sobre.html</loc></url>", s)
        self.assertIn("<loc>https://catodo.es/episodios/2026-11-25.html</loc><lastmod>2026-11-25</lastmod>", s)
        self.assertNotIn("legal.html", s)

    def test_sin_episodios(self):
        self.assertIn("<url><loc>https://catodo.es/</loc></url>", feed.generar_sitemap([], self.CFG))
