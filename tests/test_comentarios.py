"""Pruebas de los comentarios desde el móvil (ops#118): python -m unittest discover -s tests"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import comentarios  # noqa: E402
import ops  # noqa: E402

GUION = """## Apertura

Hola, esto es Cátodo.

## Noticia 1: Nvidia

La directiva trabajaba para China.

## Cierre

Hasta mañana.
"""


class Puros(unittest.TestCase):
    def test_bloques_cambiados(self):
        nuevo = GUION.replace("trabajaba para China", "presuntamente trabajaba para China, según el NYT")
        self.assertEqual(comentarios.bloques_cambiados(GUION, nuevo), ["Noticia 1: Nvidia"])
        self.assertEqual(comentarios.bloques_cambiados(GUION, GUION), [])
        sin_noticia = GUION.replace("## Noticia 1: Nvidia\n\nLa directiva trabajaba para China.\n\n", "")
        self.assertEqual(comentarios.bloques_cambiados(GUION, sin_noticia), ["Noticia 1: Nvidia"])

    def test_diferencias_solo_lo_cambiado(self):
        nuevo = GUION.replace("trabajaba", "presuntamente trabajaba")
        diff = comentarios.diferencias(GUION, nuevo)
        self.assertIn("-La directiva trabajaba para China.", diff)
        self.assertIn("+La directiva presuntamente trabajaba para China.", diff)
        self.assertNotIn("Hasta mañana", diff)

    def test_comentarios_anteriores_sin_el_ultimo(self):
        hilo = {"messages": [{"author": "job", "body": "v1"}, {"author": "user", "body": "uno"},
                             {"author": "job", "body": "v2"}, {"author": "user", "body": "dos"}]}
        self.assertEqual(comentarios.comentarios_anteriores(hilo), ["uno"])

    def test_mensaje_ronda(self):
        correccion = {"cambios": ["Noticia 1: añadido «presuntamente»"], "no_aplicado": ["Lo de Vance: sin fuente"]}
        problemas = [{"fragmento": "presuntamente trabajaba", "problema": "falta la versión de la empresa"}]
        texto = comentarios.mensaje_ronda("2026-11-25", 2, correccion, problemas, ["Noticia 1: Nvidia"],
                                          "https://a/x.mp3", "https://a/x.txt", 11.2)
        self.assertIn("Versión 2", texto)
        self.assertIn("- Noticia 1: añadido «presuntamente»", texto)
        self.assertIn("## Sin aplicar", texto)
        self.assertIn("falta la versión de la empresa", texto)
        self.assertIn("Voz rehecha en: Noticia 1: Nvidia.", texto)
        self.assertIn("[Escuchar el episodio](https://a/x.mp3)", texto)
        self.assertNotIn("—", texto)

    def test_la_decision_admite_comentarios(self):
        decision = ops.decision_episodio("2026-11-25")
        self.assertTrue(decision["allowFreeText"])
        self.assertEqual(decision["defaultOption"], "no-publicar")


class Corregir(unittest.TestCase):
    """Una ronda entera con Claude, la voz y R2 simulados."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        raiz = Path(self.dir.name)
        self.episodios = raiz / "episodes"
        self.carpeta = self.episodios / "2026-11-25"
        self.carpeta.mkdir(parents=True)
        (self.carpeta / "guion.md").write_text(GUION)
        (self.carpeta / "notas.md").write_text("Notas\n")
        (self.carpeta / "revision.md").write_text("# Revisión\n")
        (self.carpeta / "catodo-2026-11-25.mp3").write_bytes(b"mp3")
        self.ronda = raiz / "ronda.json"
        self.hilo = raiz / "hilo.json"
        self.nota = raiz / "nota.md"
        self.hilo.write_text(json.dumps({"id": "d-1", "title": ops.titulo("2026-11-25"), "messages": [
            {"author": "job", "body": "v1"}, {"author": "user", "body": "Añade presuntamente en la 1"}]}))
        entorno = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(entorno)))
        os.environ.update(OPS_DECISION_TEXT="Añade presuntamente en la 1", OPS_DECISION_JSON=str(self.hilo),
                          OPS_DECISION_ROUND_FILE=str(self.ronda), OPS_REPLY_NOTE_FILE=str(self.nota),
                          OPS_DECISION_ID="d-1")
        os.environ.pop("OPS_DECISION_OPTION", None)
        self.pasos = []
        for nombre, valor in [("EPISODIOS", self.episodios),
                              ("python", lambda *a: self.pasos.append(a[0])),
                              ("subir_revision", lambda *a: ("https://a/v2.mp3", "https://a/v2.txt"))]:
            parche = mock.patch.object(ops, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        parche = mock.patch("publish.duracion", lambda mp3: 660.0)
        parche.start()
        self.addCleanup(parche.stop)

    def llamadas(self, *respuestas):
        parche = mock.patch("claude_cli.llamar", side_effect=list(respuestas))
        llamar = parche.start()
        self.addCleanup(parche.stop)
        return llamar

    def test_aplica_verifica_rehace_la_voz_y_deja_la_ronda(self):
        nuevo = GUION.replace("trabajaba", "presuntamente trabajaba")
        llamar = self.llamadas(
            {"guion": nuevo, "notas": "", "cambios": ["Noticia 1: añadido «presuntamente»"], "no_aplicado": [],
             "hechos_cambiados": True},
            {"problemas": [], "valoracion": "bien"})
        ops.responder()
        self.assertEqual(llamar.call_count, 2)
        self.assertIn("Añade presuntamente en la 1", llamar.call_args_list[0].args[0])
        self.assertIn("+La directiva presuntamente", llamar.call_args_list[1].args[0])
        self.assertEqual((self.carpeta / "guion.md").read_text(), nuevo)
        self.assertEqual((self.carpeta / "notas.md").read_text(), "Notas\n")
        self.assertEqual(self.pasos, ["src/tts.py", "src/mix.py"])
        self.assertIn("Comentario de la revisión (versión 2)", (self.carpeta / "revision.md").read_text())
        ronda = json.loads(self.ronda.read_text())
        self.assertIn("Versión 2", ronda["message"])
        self.assertEqual(ronda["decision"]["defaultOption"], "no-publicar")
        self.assertTrue(ronda["decision"]["allowFreeText"])

    def test_solo_tono_sin_verificacion(self):
        nuevo = GUION.replace("Hasta mañana.", "¡Hasta mañana!")
        llamar = self.llamadas({"guion": nuevo, "notas": "", "cambios": ["Cierre más alegre"], "no_aplicado": [],
                                "hechos_cambiados": False})
        ops.responder()
        self.assertEqual(llamar.call_count, 1)
        self.assertEqual(self.pasos, ["src/tts.py", "src/mix.py"])

    def test_sin_cambios_ni_voz_ni_verificacion(self):
        llamar = self.llamadas({"guion": GUION, "notas": "", "cambios": [], "no_aplicado": ["Era una pregunta: sí"],
                                "hechos_cambiados": True})
        ops.responder()
        self.assertEqual(llamar.call_count, 1)
        self.assertEqual(self.pasos, [])
        self.assertIn("No he cambiado nada", json.loads(self.ronda.read_text())["message"])

    def test_episodio_que_ya_no_esta(self):
        (self.carpeta / "guion.md").unlink()
        self.llamadas()
        ops.responder()
        self.assertIn("ya no está", self.nota.read_text())
        self.assertFalse(self.ronda.exists())


if __name__ == "__main__":
    unittest.main()
