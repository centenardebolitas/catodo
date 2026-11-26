"""Pruebas de la portada de cada episodio: python -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import feed  # noqa: E402
from comun import cargar_yaml  # noqa: E402

EPISODIO = {"fecha": "2026-11-24", "numero": 1, "titulo": "Prueba", "notas_md": "Notas.", "guion_md": "## Apertura\n\nHola.",
            "url_audio": "https://audio.catodo.es/episodios/catodo-2026-11-24.mp3", "bytes": 10, "duracion_s": 600,
            "publicado_en": "2026-11-24T06:00:00+01:00"}
CON_PORTADA = {**EPISODIO, "url_portada": "https://audio.catodo.es/episodios/catodo-2026-11-24-abc.jpg",
               "url_portada_web": "https://audio.catodo.es/episodios/catodo-2026-11-24-web-def.jpg"}


class Feed(unittest.TestCase):
    def setUp(self):
        self.cfg = cargar_yaml("podcast.yaml")

    def test_el_feed_lleva_la_portada_grande_del_episodio(self):
        xml = feed.generar_feed([CON_PORTADA], self.cfg)
        self.assertIn('<itunes:image href="https://audio.catodo.es/episodios/catodo-2026-11-24-abc.jpg"/>', xml)

    def test_sin_portada_el_episodio_no_lleva_imagen_propia(self):
        xml = feed.generar_feed([EPISODIO], self.cfg)
        self.assertEqual(xml.count("<itunes:image"), 1)  # solo la del programa

    def test_la_web_usa_la_version_ligera(self):
        pagina = feed.generar_pagina_episodio(CON_PORTADA, self.cfg)
        self.assertIn('class="portada-ep" href="https://audio.catodo.es/episodios/catodo-2026-11-24-abc.jpg">'
                      '<img src="https://audio.catodo.es/episodios/catodo-2026-11-24-web-def.jpg"', pagina)
        self.assertIn('og:image" content="https://audio.catodo.es/episodios/catodo-2026-11-24-abc.jpg"', pagina)
        portada = feed.generar_portada([CON_PORTADA], self.cfg)
        self.assertIn('class="mini" href="/episodios/2026-11-24.html"><img src="https://audio.catodo.es/episodios/catodo-2026-11-24-web-def.jpg"', portada)


class Rejilla(unittest.TestCase):
    def setUp(self):
        try:
            import portada_episodio
        except ImportError:
            self.skipTest("Pillow y regex solo hacen falta para generar portadas")
        self.p = portada_episodio

    def test_un_grafema_por_emoji(self):
        self.assertEqual(self.p.emojis_de("👩‍⚖️🇪🇸 ⚡"), ["👩‍⚖️", "🇪🇸", "⚡"])

    def test_rutas_de_noto(self):
        self.assertEqual(self.p.ruta_noto("🇪🇸"), "third_party/region-flags/png/ES.png")
        self.assertEqual(self.p.ruta_noto("🛡️"), "2D/png/128/emoji_u1f6e1.png")
        self.assertEqual(self.p.ruta_noto("👩‍⚖️"), "2D/png/128/emoji_u1f469_200d_2696.png")

    def test_la_marca_no_tiene_emojis_detras(self):
        libres = set(self.p.casillas_libres())
        ancho, alto = self.p.MARCA
        n = self.p.COLUMNAS
        self.assertEqual(len(libres), n * n - ancho * alto)
        self.assertNotIn((n - 1, n - 1), libres)
        self.assertIn((n - ancho - 1, n - 1), libres)

    def test_hueco_entre_parrafos_y_corte_si_no_cabe(self):
        self.assertEqual(list(self.p.secuencia(["⚡⚡", "", "🐛"])), ["⚡", "⚡", None, "🐛"])


if __name__ == "__main__":
    unittest.main()
