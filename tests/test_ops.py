"""Pruebas de Cátodo en ops (ops#118): python -m unittest discover -s tests"""

import json
import os
import stat
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import claude_cli  # noqa: E402
import ops  # noqa: E402

REVISION = """# Revisión del episodio del 2026-11-25

**Duración:** 1700 palabras, unos 11 minutos (objetivo 1500-2000 palabras).
**Revisores automáticos:** el verificador encontró 3 problemas.

## Qué tienes que hacer

1. Leer el guion (`guion.md`).
3. Aprobar: `make aprobar NOTA="qué has comprobado"`.

## Puntos a comprobar

1. La cifra de ventas de la noticia 2.

## Orden del episodio

1. Uno (noticia)
2. Dos (noticia)

## Se queda para otro día

- Tres
"""


class Decision(unittest.TestCase):
    def test_titulo_lleva_la_fecha_y_la_respuesta_la_saca(self):
        self.assertEqual(ops.fecha_de_titulo(ops.titulo("2026-11-25")), "2026-11-25")
        self.assertIsNone(ops.fecha_de_titulo("sin fecha"))
        self.assertIsNone(ops.fecha_de_titulo(None))

    def test_cuerpo_con_lo_que_hay_que_mirar_y_sin_lo_del_mac(self):
        cuerpo = ops.cuerpo_decision("2026-11-25", REVISION, "https://a/x.mp3", "https://a/x.txt", 11.4)
        self.assertIn("[Escuchar el episodio](https://a/x.mp3)", cuerpo)
        self.assertIn("[Leer el guion](https://a/x.txt)", cuerpo)
        self.assertIn("1. La cifra de ventas de la noticia 2.", cuerpo)
        self.assertIn("2. Dos (noticia)", cuerpo)
        self.assertIn("- Tres", cuerpo)
        self.assertIn("**Duración:** 1700 palabras", cuerpo)
        self.assertNotIn("make aprobar", cuerpo)
        self.assertNotIn("# Revisión del episodio", cuerpo)
        self.assertNotIn("—", cuerpo)

    def test_cuerpo_cabe_en_una_decision_de_ops(self):
        larga = REVISION.replace("1. La cifra", "1. " + "x" * 20_000 + " La cifra")
        cuerpo = ops.cuerpo_decision("2026-11-25", larga, "https://a/x.mp3", "https://a/x.txt", 11)
        self.assertLessEqual(len(cuerpo), ops.MAX_CUERPO)
        self.assertTrue(cuerpo.endswith("revision.md del estado del trabajo.)"))

    def test_por_defecto_no_publicar(self):
        self.assertEqual([o["key"] for o in ops.OPCIONES], ["aprobar", "no-publicar"])
        self.assertEqual(ops.OPCION_NO_PUBLICAR, "no-publicar")


class PublicacionSola(unittest.TestCase):
    """Desde el 26 de noviembre de 2026 el episodio sale solo y se revisa después (ops#122)."""

    def test_aviso_con_el_enlace_y_lo_que_hay_que_mirar(self):
        publicacion = {"numero": 2, "url_audio": "https://a/x-1234abcd.mp3", "duracion_s": 610}
        cuerpo = ops.cuerpo_aviso("2026-11-26", REVISION, publicacion, "main")
        self.assertIn("Episodio 2 del **2026-11-26**, unos 10 minutos. Publicado solo", cuerpo)
        self.assertIn("[Escuchar el episodio](https://a/x-1234abcd.mp3)", cuerpo)
        self.assertIn("https://catodo.es/episodios/2026-11-26.html", cuerpo)
        self.assertIn("1. La cifra de ventas de la noticia 2.", cuerpo)
        self.assertIn("make corregir", cuerpo)
        self.assertNotIn("make aprobar", cuerpo)

    def test_aviso_en_el_fichero_de_ops_con_una_sola_opcion(self):
        with tempfile.TemporaryDirectory() as dir:
            carpeta = Path(dir) / "2026-11-26"
            carpeta.mkdir()
            (carpeta / "revision.md").write_text(REVISION)
            (carpeta / "publicacion.json").write_text(json.dumps({"numero": 2, "url_audio": "u", "duracion_s": 60}))
            destino = Path(dir) / "decision.json"
            entorno = dict(os.environ)
            self.addCleanup(lambda: (os.environ.clear(), os.environ.update(entorno)))
            os.environ["OPS_DECISION_FILE"] = str(destino)
            with unittest.mock.patch.object(ops, "EPISODIOS", Path(dir)), \
                    unittest.mock.patch.object(ops, "redes_activas", return_value=[]):
                ops.aviso_publicado("2026-11-26")
            datos = json.loads(destino.read_text())
            self.assertEqual(datos["decision"]["options"], [{"key": "visto", "label": "Visto"}])
            self.assertEqual(datos["decision"]["defaultOption"], "visto")
            self.assertFalse(datos["decision"]["allowFreeText"])
            self.assertEqual(ops.fecha_de_titulo(datos["decision"]["title"]), "2026-11-26")

    def test_se_puede_publicar_aprobado_o_solo(self):
        import memoria
        self.assertTrue(memoria.se_puede_publicar({"revision_humana": {"aprobado": True}}))
        self.assertTrue(memoria.se_puede_publicar({"revision_humana": {"aprobado": False, "publicacion_automatica": True}}))
        self.assertFalse(memoria.se_puede_publicar({}))
        self.assertFalse(memoria.se_puede_publicar(None))


class Respuesta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.nota = Path(self.dir.name) / "nota.md"
        self.hilo = Path(self.dir.name) / "hilo.json"
        self.entorno = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self.entorno)))
        os.environ.update(OPS_REPLY_NOTE_FILE=str(self.nota), OPS_DECISION_JSON=str(self.hilo),
                          OPS_DECISION_ID="d-1")

    def responder(self, opcion, titulo):
        self.hilo.write_text(json.dumps({"id": "d-1", "title": titulo}))
        os.environ["OPS_DECISION_OPTION"] = opcion
        ops.responder()
        return self.nota.read_text()

    def test_sin_fecha_en_el_titulo_no_hace_nada(self):
        self.assertIn("no he hecho nada", self.responder("aprobar", "otra cosa"))

    def test_aprobar_un_episodio_que_ya_no_esta_no_programa_nada(self):
        nota = self.responder("aprobar", ops.titulo("1999-01-01"))
        self.assertIn("ya no está en ops", nota)

    def test_visto(self):
        self.assertIn("Visto el episodio del 2026-11-26", self.responder("visto", "Cátodo 2026-11-26: publicado"))

    def test_opcion_desconocida(self):
        self.assertIn("Opción desconocida", self.responder("otra", ops.titulo("1999-01-01")))


class Preparar(unittest.TestCase):
    """El token se lee una vez y llega a cada paso que llama a Claude por un descriptor nuevo."""

    def test_cada_paso_con_claude_recibe_el_token_y_los_demas_no(self):
        with tempfile.TemporaryDirectory() as dir:
            visto = Path(dir) / "visto.txt"
            paso = Path(dir) / "paso.py"
            paso.write_text(f"""import os
fd = os.environ.get("OPS_CLAUDE_TOKEN_FD")
token = os.read(int(fd), 100).decode().strip() if fd else "-"
with open({str(visto)!r}, "a") as f:
    f.write(token + "\\n")
""")
            for con_claude in (True, True, False):
                ops.paso(str(paso), "2026-11-25", "tok" if con_claude else None)
            self.assertEqual(visto.read_text().split(), ["tok", "tok", "-"])

    def test_un_paso_que_falla_para_la_preparacion(self):
        with tempfile.TemporaryDirectory() as dir:
            falla = Path(dir) / "falla.py"
            falla.write_text("import sys; sys.exit(3)\n")
            with self.assertRaises(SystemExit) as salida:
                ops.paso(str(falla), "2026-11-25", None)
            self.assertIn("código 3", str(salida.exception))

    def test_la_decision_enlaza_la_portada_si_la_hay(self):
        cuerpo = ops.cuerpo_decision("2026-11-25", REVISION, "https://a/x.mp3", "https://a/x.txt", 11,
                                     "https://a/x-portada.jpg")
        self.assertIn("[Ver la portada](https://a/x-portada.jpg)", cuerpo)
        self.assertNotIn("portada", ops.cuerpo_decision("2026-11-25", REVISION, "https://a/x.mp3", "https://a/x.txt", 11))

    def test_sin_portada_el_episodio_sigue(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "2026-11-25"
            carpeta.mkdir()
            (carpeta / "portada.jpg").write_bytes(b"vieja")
            fallo = mock.Mock(returncode=1)
            with mock.patch.object(ops, "EPISODIOS", Path(tmp)), mock.patch("subprocess.run", return_value=fallo):
                ops.portada("2026-11-25")  # no lanza
            self.assertFalse((carpeta / "portada.jpg").exists())

    def test_los_pasos_son_los_de_make_noche(self):
        self.assertEqual([p for p, _ in ops.PASOS],
                         ["src/fetch.py", "src/rank.py", "src/script.py", "src/tts.py", "src/mix.py"])
        self.assertEqual([p for p, claude in ops.PASOS if claude], ["src/rank.py", "src/script.py"])


class ClaudeEnOps(unittest.TestCase):
    """El token por descriptor y las cerraduras, con un `claude` falso en el PATH."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        raiz = Path(self.dir.name)
        self.visto = raiz / "visto.json"
        falso = raiz / "bin" / "claude"
        falso.parent.mkdir()
        falso.write_text(f"""#!{sys.executable}
import json, os, sys
fd = int(os.environ["CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR"])
token = os.read(fd, 1000).decode()
json.dump({{"args": sys.argv[1:], "token": token, "env": dict(os.environ)}}, open({str(self.visto)!r}, "w"))
print(json.dumps({{"is_error": False, "result": "hola"}}))
""")
        falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
        self.entorno = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self.entorno)))
        leer, escribir = os.pipe()
        os.write(escribir, b"sk-ant-oat-prueba\n")
        os.close(escribir)
        claude_cli._TOKEN_OPS["valor"] = None
        self.addCleanup(lambda: claude_cli._TOKEN_OPS.update(valor=None))
        os.environ.update(OPS_CLAUDE_TOKEN_FD=str(leer), PATH=f"{falso.parent}:{os.environ['PATH']}",
                          HOME=str(raiz), R2_SECRET_ACCESS_KEY="no-debe-llegar")

    def test_token_por_descriptor_entorno_minimo_y_cerraduras(self):
        for _ in range(2):  # el token se lee una vez y vale para todas las llamadas
            self.assertEqual(claude_cli.llamar("hola", modelo="opus", herramientas=["WebFetch", "WebSearch"]), "hola")
            visto = json.loads(self.visto.read_text())
            self.assertEqual(visto["token"], "sk-ant-oat-prueba\n")
        self.assertNotIn("OPS_CLAUDE_TOKEN_FD", os.environ)
        self.assertNotIn("R2_SECRET_ACCESS_KEY", visto["env"])
        self.assertNotIn("sk-ant-oat-prueba", json.dumps(visto["env"]))
        args = visto["args"]
        self.assertEqual(args[args.index("--tools") + 1], "WebFetch,WebSearch")
        self.assertEqual(args[args.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(args[args.index("--setting-sources") + 1], "user")
        self.assertIn("--strict-mcp-config", args)
        self.assertNotIn("--dangerously-skip-permissions", args)
        self.assertEqual(visto["env"]["CLAUDE_CONFIG_DIR"], os.path.join(os.environ["HOME"], "claude-catodo"))

    def test_sin_herramientas_no_existe_ninguna(self):
        claude_cli.llamar("hola", modelo="opus")
        args = json.loads(self.visto.read_text())["args"]
        self.assertEqual(args[args.index("--tools") + 1], "")


if __name__ == "__main__":
    unittest.main()
