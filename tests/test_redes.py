"""Pruebas de la difusión en redes (src/difusion.py y src/redes.py): python -m unittest discover -s tests"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import difusion  # noqa: E402
import ops  # noqa: E402
import redes  # noqa: E402

CAPITULOS = [{"startTime": 0, "title": "Apertura"},
             {"startTime": 23.6, "title": "Huang pide perdón y le espera Washington"},
             {"startTime": 164.7, "title": "Veredicto contra Huawei en Estados Unidos, que recurrirá"},
             {"startTime": 252.1, "title": "Tidal echa la música hecha solo con IA"},
             {"startTime": 592.6, "title": "Cierre"}]
DATOS = {"fecha": "2026-11-25", "titulo": "Huang pide perdón, Tidal veta la música hecha con IA y Microsoft en código rojo",
         "capitulos": CAPITULOS,
         "publicacion": {"numero": 2, "url_audio": "https://audio.catodo.es/e.mp3",
                         "url_portada_web": "https://audio.catodo.es/p.jpg"}}


class Subtitulos(unittest.TestCase):
    def test_frases_y_trozos(self):
        texto = "¿Te acuerdas de lo de Jensen Huang? Ayer te contaba que volvía.\n\nPues *su vuelta* no es tranquila."
        self.assertEqual(difusion.frases(texto), ["¿Te acuerdas de lo de Jensen Huang?", "Ayer te contaba que volvía.",
                                                  "Pues su vuelta no es tranquila."])
        larga = "Según el New York Times y TechCrunch, en su primera reunión con toda la plantilla desde que volvió, Huang pidió perdón."
        partes = difusion.trozos(larga)
        self.assertEqual(" ".join(partes), larga)
        self.assertTrue(all(len(p.split()) <= difusion.PALABRAS_SUBTITULO + 2 for p in partes))

    def test_los_cortes_van_a_las_pausas_cercanas(self):
        tiempos = difusion.repartir(["aaaa", "aaaa"], 0, 10, pausas=[5.8, 9.5])
        self.assertEqual(tiempos, [(0, 5.8), (5.8, 10)])
        lejos = difusion.repartir(["aaaa", "aaaa"], 0, 10, pausas=[8.0])
        self.assertEqual(lejos, [(0, 5.0), (5.0, 10)])

    def test_el_clip_acaba_en_una_frase_y_no_se_pasa(self):
        texto = " ".join(f"Frase número {i} con unas cuantas palabras más." for i in range(40))
        plan = difusion.plan_clip(texto, 100.0, 400.0, pausas=[])
        self.assertLessEqual(plan[-1][2], difusion.CLIP_MAX_S + 0.01)
        self.assertGreaterEqual(plan[-1][2], difusion.CLIP_MIN_S)
        self.assertTrue(plan[-1][0].endswith("."))
        self.assertEqual(plan[0][1], 0)

    def test_la_voz_acaba_antes_del_bzz(self):
        with mock.patch.object(difusion.mix, "duracion", return_value=0.4):
            fin = difusion.fin_de_voz(CAPITULOS, 1, 635.5, noticia=True)
        esperado = 164.7 - (difusion.mix.PAUSA_ANTES_SEPARADOR_S + 0.4 + difusion.mix.PAUSA_TRAS_SEPARADOR_S)
        self.assertAlmostEqual(fin, esperado)
        self.assertEqual(difusion.fin_de_voz(CAPITULOS, 4, 635.5), 635.5)


class Textos(unittest.TestCase):
    def test_bluesky_cabe_en_300(self):
        datos = {**DATOS, "capitulos": CAPITULOS + [{"startTime": 600 + i, "title": "x" * 80} for i in range(5)]}
        texto = redes.texto_bluesky(datos)
        self.assertLessEqual(redes.graphemes(texto), 300)
        self.assertTrue(texto.startswith(DATOS["titulo"]))
        self.assertNotIn("Apertura", texto)

    def test_textos_con_enlace_y_aviso_de_ia(self):
        self.assertIn("https://catodo.es/episodios/2026-11-25.html", redes.texto_threads(DATOS))
        self.assertLessEqual(len(redes.texto_threads(DATOS)), 500)
        self.assertIn("IA", redes.texto_instagram(DATOS))
        self.assertIn("• Tidal echa la música hecha solo con IA", redes.texto_facebook(DATOS))

    def test_youtube_titulo_corto_y_capitulos(self):
        datos = {**DATOS, "titulo": "Un titular <muy> largo " * 10}
        titulo = redes.titulo_youtube(datos)
        self.assertLessEqual(len(titulo), 100)
        self.assertNotIn("<", titulo)
        self.assertTrue(titulo.endswith("| Cátodo 2"))
        descripcion = redes.descripcion_youtube(DATOS)
        self.assertIn("0:00 Apertura\n0:23 Huang pide perdón", descripcion)


class Difundir(unittest.TestCase):
    def setUp(self):
        self.estado = {}
        self.guardados = []
        parches = [
            mock.patch.object(redes, "AJUSTES", {"activas": ["bluesky", "instagram"]}),
            mock.patch.object(redes, "cargar_env", return_value={}),
            mock.patch.object(redes, "esta_publicado", return_value=None),
            mock.patch.object(redes, "cliente_r2", return_value=mock.Mock()),
            mock.patch.object(redes, "leer_estado", side_effect=lambda *a: self.estado),
            mock.patch.object(redes, "guardar_estado",
                              side_effect=lambda c, b, f, e: self.guardados.append(json.loads(json.dumps(e)))),
            mock.patch.object(redes, "subir_clip", return_value="https://audio.catodo.es/clip.mp4"),
            mock.patch.object(difusion, "datos_episodio", return_value=DATOS),
            mock.patch.object(difusion, "generar", return_value=(DATOS, {
                "clip": Path("clip.mp4"), "clip_info": {"noticia": "Huang"}})),
            mock.patch.object(Path, "exists", return_value=True),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)

    def test_si_una_red_falla_las_demas_salen_y_se_apuntan(self):
        bien = mock.Mock(return_value={"id": "1", "url": "https://bsky.app/x"})
        mal = mock.Mock(side_effect=redes.ErrorRed("HTTP 400"))
        with mock.patch.dict(redes.PUBLICAR, {"bluesky": bien, "instagram": mal}):
            resultados = redes.difundir("2026-11-25")
        self.assertEqual(resultados["bluesky"]["url"], "https://bsky.app/x")
        self.assertIn("HTTP 400", resultados["instagram"]["error"])
        self.assertEqual(list(self.guardados[-1]["redes"]), ["bluesky"])
        self.assertEqual(mal.call_args.args[2]["url_clip"], "https://audio.catodo.es/clip.mp4")

    def test_no_publica_dos_veces(self):
        self.estado = {"redes": {"bluesky": {"url": "https://bsky.app/x"}}}
        bluesky, instagram = mock.Mock(), mock.Mock(return_value={"id": "2"})
        with mock.patch.dict(redes.PUBLICAR, {"bluesky": bluesky, "instagram": instagram}):
            redes.difundir("2026-11-25")
        bluesky.assert_not_called()
        instagram.assert_called_once()

    def test_sin_redes_activas_no_hace_nada(self):
        with mock.patch.object(redes, "AJUSTES", {"activas": []}):
            self.assertEqual(redes.difundir("2026-11-25"), {})
        difusion.generar.assert_not_called()

    def test_si_el_episodio_no_esta_en_la_web_no_publica(self):
        with mock.patch.object(redes, "esta_publicado", return_value="HTTP 404"):
            with self.assertRaises(SystemExit):
                redes.difundir("2026-11-25")

    def test_espera_a_que_salga_en_la_web(self):
        respuestas = iter(["HTTP 404", "HTTP 404", None])
        with mock.patch.object(redes, "esta_publicado", side_effect=lambda d: next(respuestas)), \
                mock.patch.object(redes.time, "sleep") as dormir:
            self.assertIsNone(redes.esperar_publicado(DATOS, 900, cada=30))
        self.assertEqual(dormir.call_count, 2)
        with mock.patch.object(redes, "esta_publicado", return_value="HTTP 404"), \
                mock.patch.object(redes.time, "sleep"):
            self.assertEqual(redes.esperar_publicado(DATOS, 0), "HTTP 404")


class TokenThreads(unittest.TestCase):
    def test_renueva_y_guarda_y_respeta_una_credencial_nueva(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"CATODO_ESTADO": d, "THREADS_TOKEN": "viejo"}
            with mock.patch.object(redes, "pedir", return_value={"access_token": "renovado"}) as pedir:
                self.assertEqual(redes.token_threads(env), "renovado")
                self.assertEqual(redes.token_threads(env), "renovado")  # recién renovado: no vuelve a pedir
                self.assertEqual(pedir.call_count, 1)
            self.assertEqual(oct(os.stat(Path(d) / "threads-token.json").st_mode & 0o777), "0o600")
            env["THREADS_TOKEN"] = "nuevo"
            with mock.patch.object(redes, "pedir", side_effect=redes.ErrorRed("caducado")):
                self.assertEqual(redes.token_threads(env), "nuevo")


class Instagram(unittest.TestCase):
    def test_va_por_graph_instagram_y_renueva_su_token_aparte(self):
        llamadas = []

        def pedir(metodo, url, **kw):
            llamadas.append((metodo, url, kw))
            if "refresh_access_token" in url:
                return {"access_token": "ig-renovado"}
            if url.endswith("/me"):
                return {"user_id": "1784"}
            if url.endswith("/media"):
                return {"id": "c1"}
            if url.endswith("/media_publish"):
                return {"id": "m1"}
            if url.endswith("/c1"):
                return {"status_code": "FINISHED"}
            return {"permalink": "https://www.instagram.com/reel/x/"}

        with tempfile.TemporaryDirectory() as d, mock.patch.object(redes, "pedir", side_effect=pedir):
            env = {"CATODO_ESTADO": d, "INSTAGRAM_TOKEN": "ig"}
            hecho = redes.instagram(DATOS, env, {"url_clip": "https://audio.catodo.es/c.mp4"})
            self.assertTrue((Path(d) / "instagram-token.json").exists())
            self.assertFalse((Path(d) / "threads-token.json").exists())
        self.assertEqual(hecho, {"id": "m1", "url": "https://www.instagram.com/reel/x/"})
        renovar = llamadas[0]
        self.assertEqual(renovar[2]["params"]["grant_type"], "ig_refresh_token")
        publicar = [c for c in llamadas if c[1].endswith("/media")][0]
        self.assertTrue(publicar[1].startswith("https://graph.instagram.com/"))
        self.assertIn("/1784/media", publicar[1])
        self.assertEqual(publicar[2]["data"]["access_token"], "ig-renovado")


class AvisoDeOps(unittest.TestCase):
    def test_difundir_solo_con_redes_activas_y_por_defecto_no(self):
        with mock.patch.object(redes, "AJUSTES", {"activas": []}):
            self.assertEqual([o["key"] for o in ops.opciones_aviso()], ["visto"])
        with mock.patch.object(redes, "AJUSTES", {"activas": ["bluesky"]}):
            opciones = ops.opciones_aviso()
        self.assertEqual([o["key"] for o in opciones], ["difundir", "visto"])
        self.assertEqual(opciones[1]["label"], "No difundir")
        cuerpo = ops.cuerpo_aviso("2026-11-26", "", {"numero": 3, "url_audio": "https://a/x.mp3"}, "main",
                                  ["bluesky", "youtube"])
        self.assertIn("«Difundir en redes» lo publica en Bluesky, YouTube", cuerpo)

    def responder(self, opcion, **parches):
        with tempfile.TemporaryDirectory() as d:
            hilo = Path(d) / "hilo.json"
            hilo.write_text(json.dumps({"title": "Cátodo 2026-11-26: publicado", "messages": []}))
            nota = Path(d) / "nota.md"
            entorno = {"OPS_DECISION_OPTION": opcion, "OPS_DECISION_JSON": str(hilo),
                       "OPS_REPLY_NOTE_FILE": str(nota), "OPS_DECISION_ID": "7"}
            with mock.patch.dict(os.environ, entorno), mock.patch.object(ops, "cargar_env", return_value={}), \
                    mock.patch.object(redes, "difundir", **parches) as difundir:
                ops.responder()
            return difundir, (nota.read_text() if nota.exists() else None)

    def test_responder_difundir_publica_y_lo_cuenta(self):
        difundir, nota = self.responder("difundir", return_value={"bluesky": {"url": "https://bsky.app/x"}})
        self.assertEqual(difundir.call_args.args[0], "2026-11-26")
        self.assertEqual(difundir.call_args.kwargs["esperar"], ops.ESPERA_WEB_S)
        self.assertIn("- Bluesky: https://bsky.app/x", nota)

    def test_responder_difundir_falla_sin_nota_para_que_ops_lo_reintente(self):
        with self.assertRaises(SystemExit):
            self.responder("difundir", return_value={"bluesky": {"error": "HTTP 500"}})

    def test_no_difundir_no_publica(self):
        difundir, nota = self.responder("visto")
        difundir.assert_not_called()
        self.assertIn("Visto", nota)


if __name__ == "__main__":
    unittest.main()
