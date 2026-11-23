"""Llamadas a Claude a través de `claude -p` (usa la suscripción de Claude del usuario).

Cada llamada es independiente (sin sesión guardada), con el modelo, el esfuerzo y
las herramientas que se indiquen. Si se pasa un esquema JSON, la respuesta se
valida contra él y se devuelve ya como diccionario.

En ops (trabajo catodo.preparar, ops#118) el token de la suscripción llega por un
descriptor (OPS_CLAUDE_TOKEN_FD), nunca por el entorno: se lee una vez y a cada
`claude` se le pasa por el suyo (CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR), con un
entorno mínimo y las mismas cerraduras que el conector de IA de ops: solo existen
las herramientas que se piden, nada pregunta, ni ajustes del repo ni servidores MCP.
En el Mac, la sesión de `claude` iniciada, como siempre.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

# Herramientas que nunca se permiten: Claude no debe tocar ficheros ni ejecutar nada.
PROHIBIDAS = ["Bash", "Edit", "Write", "NotebookEdit", "Task", "Agent"]


class ErrorClaude(RuntimeError):
    pass


_TOKEN_OPS = {"valor": None}


def token_ops():
    """El token de Claude que da ops por OPS_CLAUDE_TOKEN_FD, o None fuera de ops."""
    if _TOKEN_OPS["valor"] is None:
        fd = os.environ.pop("OPS_CLAUDE_TOKEN_FD", None)
        if fd is None:
            return None
        with os.fdopen(int(fd), "r", encoding="utf-8") as f:
            valor = f.read().strip()
        if not valor:
            raise ErrorClaude("ops no ha pasado el token de Claude (OPS_CLAUDE_TOKEN_FD vacío)")
        _TOKEN_OPS["valor"] = valor
    return _TOKEN_OPS["valor"]


def orden_ops(orden, herramientas):
    """Las cerraduras del conector de IA de ops (executor/src/agent/claudeCli.ts)."""
    return [*orden, "--tools", ",".join(herramientas or []), "--permission-mode", "dontAsk",
            "--permission-prompts", "none", "--setting-sources", "user", "--strict-mcp-config"]


def entorno_ops(fd):
    """Entorno mínimo: ni las claves de R2 ni la de Google llegan a `claude`."""
    casa = os.environ["HOME"]
    configuracion = os.path.join(casa, "claude-catodo")
    os.makedirs(configuracion, mode=0o700, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": casa,
        "LANG": "C.UTF-8",
        "CLAUDE_CONFIG_DIR": configuracion,
        "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR": str(fd),
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
    }


def llamar(prompt, *, modelo, esfuerzo=None, esquema=None, herramientas=None,
           sistema=None, registro=None, tiempo_max=1800, reintentos=2):
    """Ejecuta `claude -p` y devuelve el texto o, con `esquema`, el objeto JSON validado.

    prompt: texto del mensaje (se envía por la entrada estándar).
    herramientas: lista de herramientas permitidas, por ejemplo ["WebFetch", "WebSearch"].
    sistema: texto que se añade al prompt de sistema.
    registro: ruta donde guardar la respuesta completa (para revisar o depurar).
    """
    orden = ["claude", "-p", "--model", modelo, "--no-session-persistence",
             "--output-format", "json", "--disallowedTools", *PROHIBIDAS]
    if esfuerzo:
        orden += ["--effort", esfuerzo]
    if esquema:
        orden += ["--json-schema", json.dumps(esquema, ensure_ascii=False)]
    if herramientas:
        orden += ["--allowedTools", *herramientas]
    if sistema:
        orden += ["--append-system-prompt", sistema]
    token = token_ops()
    if token:
        orden = orden_ops(orden, herramientas)

    ultimo_error = None
    for intento in range(1, reintentos + 2):
        inicio = time.time()
        # Se ejecuta en una carpeta vacía para que no lea ficheros del proyecto.
        with tempfile.TemporaryDirectory() as vacia:
            extra = {}
            if token:
                leer, escribir = os.pipe()
                os.write(escribir, f"{token}\n".encode())
                os.close(escribir)
                extra = {"env": entorno_ops(leer), "pass_fds": (leer,)}
            try:
                proceso = subprocess.run(orden, input=prompt, capture_output=True, text=True,
                                         timeout=tiempo_max, cwd=vacia, **extra)
            except subprocess.TimeoutExpired:
                ultimo_error = f"sin respuesta en {tiempo_max} s"
                continue
            finally:
                if token:
                    os.close(leer)
        try:
            datos = json.loads(proceso.stdout)
        except json.JSONDecodeError:
            ultimo_error = (proceso.stderr or proceso.stdout or "respuesta vacía")[:800]
            continue
        if registro:
            Path(registro).parent.mkdir(parents=True, exist_ok=True)
            Path(registro).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        if datos.get("is_error"):
            ultimo_error = str(datos.get("result"))[:800]
            if "authenticate" in ultimo_error.lower() or "login" in ultimo_error.lower():
                if token:
                    raise ErrorClaude(f"Claude rechaza el token de ops: renuévalo (docs/TRABAJOS.md de ops > Credenciales). ({ultimo_error})")
                raise ErrorClaude(f"Claude no tiene sesión iniciada: ejecuta `claude` y escribe /login. ({ultimo_error})")
            continue
        duracion = time.time() - inicio
        print(f"    Claude ({modelo}) respondió en {duracion:.0f} s")
        if esquema:
            salida = datos.get("structured_output")
            if salida is None:
                ultimo_error = "la respuesta no trae el JSON estructurado"
                continue
            return salida
        return datos.get("result", "")
    raise ErrorClaude(f"Claude falló tras {reintentos + 1} intentos: {ultimo_error}")
