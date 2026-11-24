"""Pruebas de capítulos, insignias y enlaces por episodio: python -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import capitulos  # noqa: E402
import enlaces  # noqa: E402
import feed  # noqa: E402
from comun import cargar_yaml  # noqa: E402

CAPITULOS = [{"startTime": 0, "title": "Apertura"}, {"startTime": 34.3, "title": "Huang & \"Nvidia\""},
             {"startTime": 3725.5, "title": "Cierre"}]
EPISODIO = {"fecha": "2026-11-24", "numero": 1, "titulo": "Prueba", "notas_md": "Notas.", "guion_md": "## Apertura\n\nHola.",
            "url_audio": "https://audio.catodo.es/episodios/x.mp3", "bytes": 10, "duracion_s": 600,
            "publicado_en": "2026-11-24T06:00:00+01:00", "capitulos": CAPITULOS,
            "url_apple": "https://podcasts.apple.com/es/podcast/x/id6838674796?i=1"}


class Marcas(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(feed.marca(34.3), "0:34")
        self.assertEqual(feed.marca(3725.5), "1:02:05")
        self.assertEqual(feed.hms(34.3), "00:00:34.300")

    def test_titulo_sin_numero_de_noticia(self):
        self.assertEqual(capitulos.titulo_capitulo("Noticia 2: CrowdStrike compra Zscaler"), "CrowdStrike compra Zscaler")
        self.assertEqual(capitulos.titulo_capitulo("Cierre"), "Cierre")


class Feed(unittest.TestCase):
    def setUp(self):
        self.cfg = cargar_yaml("podcast.yaml")

    def test_capitulos_en_el_feed(self):
        xml = feed.generar_feed([EPISODIO], self.cfg)
        self.assertIn('<podcast:chapters url="https://catodo.es/episodios/2026-11-24-capitulos.json" '
                      'type="application/json+chapters"/>', xml)
        self.assertIn('<psc:chapter start="00:00:34.300" title="Huang &amp; &quot;Nvidia&quot;"/>', xml)
        self.assertIn("0:34 Huang &amp; &quot;Nvidia&quot;", xml)  # y en las notas
        self.assertIn('xmlns:psc="http://podlove.org/simple-chapters"', xml)

    def test_sin_capitulos_no_hay_etiquetas(self):
        xml = feed.generar_feed([{**EPISODIO, "capitulos": []}], self.cfg)
        self.assertNotIn("<psc:chapters", xml)
        self.assertNotIn("<podcast:chapters", xml)

    def test_la_web_salta_al_capitulo_y_enlaza_el_episodio_en_apple(self):
        pagina = feed.generar_pagina_episodio(EPISODIO, self.cfg)
        self.assertIn('data-t="34.3">0:34</button>', pagina)
        self.assertIn('href="https://podcasts.apple.com/es/podcast/x/id6838674796?i=1"', pagina)
        self.assertNotIn("<strong>Capítulos</strong>", pagina)  # en la web van como botones

    def test_apple_va_primero_en_la_cabecera(self):
        portada = feed.generar_portada([EPISODIO], self.cfg)
        cabecera = portada[portada.index('class="cabecera"'):portada.index("</header>")]
        self.assertLess(cabecera.index("Apple Podcasts"), cabecera.index("Spotify"))


class Apple(unittest.TestCase):
    def test_id_del_programa(self):
        self.assertEqual(enlaces.id_apple(cargar_yaml("podcast.yaml")), "6838674796")

    def test_guid_a_enlace(self):
        respuesta = mock.Mock(json=lambda: {"results": [
            {"kind": "podcast", "trackViewUrl": "https://p/id1?uo=4"},
            {"kind": "podcast-episode", "episodeGuid": "catodo-2026-11-24", "trackViewUrl": "https://p/id1?i=9&uo=4"}]})
        with mock.patch("requests.get", return_value=respuesta):
            self.assertEqual(enlaces.episodios_de_apple("1"), {"catodo-2026-11-24": "https://p/id1?i=9"})


if __name__ == "__main__":
    unittest.main()
