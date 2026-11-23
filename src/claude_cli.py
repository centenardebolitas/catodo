"""Llamadas a Claude a través de `claude -p` (usa la suscripción de Claude del usuario).

Cada llamada es independiente (sin sesión guardada), con el modelo, el esfuerzo y
las herramientas que se indiquen. Si se pasa un esquema JSON, la respuesta se
valida contra él y se devuelve ya como diccionario.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path

# Herramientas que nunca se permiten: Claude no debe tocar ficheros ni ejecutar nada.
PROHIBIDAS = ["Bash", "Edit", "Write", "NotebookEdit", "Task", "Agent"]


class ErrorClaude(RuntimeError):
    pass


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

    ultimo_error = None
    for intento in range(1, reintentos + 2):
        inicio = time.time()
        # Se ejecuta en una carpeta vacía para que no lea ficheros del proyecto.
        with tempfile.TemporaryDirectory() as vacia:
            try:
                proceso = subprocess.run(orden, input=prompt, capture_output=True, text=True,
                                         timeout=tiempo_max, cwd=vacia)
            except subprocess.TimeoutExpired:
                ultimo_error = f"sin respuesta en {tiempo_max} s"
                continue
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
