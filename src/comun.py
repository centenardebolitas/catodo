"""Utilidades compartidas: rutas del proyecto, configuración y variables de entorno."""

import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config"
EPISODIOS = RAIZ / "episodes"


def cargar_yaml(nombre):
    """Lee un fichero de config/ (por ejemplo, 'settings.yaml')."""
    with open(CONFIG / nombre, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cargar_env():
    """Lee .env y lo combina con las variables de entorno (estas tienen prioridad)."""
    valores = {}
    ruta = RAIZ / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return {**valores, **os.environ}
