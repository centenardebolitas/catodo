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

    def test_insignias_bajo_la_descripcion_con_apple_primero_y_el_rss(self):
        portada = feed.generar_portada([EPISODIO], self.cfg)
        nav = portada[portada.index('<nav class="insignias"'):]
        nav = nav[:nav.index("</nav>")]
        self.assertLess(portada.index('class="suave">Tecnología'), portada.index('<nav class="insignias"'))
        self.assertLess(nav.index("Apple Podcasts"), nav.index("Spotify"))
        self.assertRegex(nav, r'href="/feed.xml"><img src="/insignias/rss.svg\?v=[0-9a-f]{8}" alt="Suscríbete por RSS"')
        pie = portada[portada.index("<footer>"):]
        self.assertNotIn('href="/feed.xml"', pie)  # las plataformas ya están en las insignias de arriba


class Apple(unittest.TestCase):
    def test_id_del_programa(self):
        self.assertEqual(enlaces.id_apple(cargar_yaml("podcast.yaml")), "6838674796")

    def test_guid_a_enlace(self):
        respuesta = mock.Mock(json=lambda: {"results": [
            {"kind": "podcast", "trackViewUrl": "https://p/id1?uo=4"},
            {"kind": "podcast-episode", "episodeGuid": "catodo-2026-11-24", "trackViewUrl": "https://p/id1?i=9&uo=4"}]})
        with mock.patch("requests.get", return_value=respuesta):
            self.assertEqual(enlaces.episodios_de_apple("1"), {"catodo-2026-11-24": "https://p/id1?i=9"})


class Incrustar(unittest.TestCase):
    def test_el_temporal_va_junto_al_mp3(self):
        """En ops /tmp está en otro disco: el MP3 nuevo se prepara junto al original."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "catodo.mp3"
            mp3.write_bytes(b"viejo")
            salidas = []

            def ffmpeg(*args):
                salida = Path(args[-1])
                salidas.append(salida)
                salida.write_bytes(b"nuevo")

            with mock.patch.object(capitulos.mix, "duracion", return_value=600), \
                    mock.patch.object(capitulos.mix, "ffmpeg", side_effect=ffmpeg):
                capitulos.incrustar(mp3, {"chapters": CAPITULOS})
            self.assertEqual(salidas[0].parent.parent, mp3.parent)
            self.assertEqual(mp3.read_bytes(), b"nuevo")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["catodo.mp3"])


if __name__ == "__main__":
    unittest.main()
