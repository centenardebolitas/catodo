"""Utilidades compartidas: rutas del proyecto, configuración y variables de entorno."""

import os
from datetime import date
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


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def despedida(fecha):
    """La despedida del cierre según el día en que se publica: «Hasta mañana» o, el viernes
    (y si alguna vez sale en fin de semana), «Buen fin de semana»."""
    return "Buen fin de semana." if date.fromisoformat(fecha).weekday() >= 4 else "Hasta mañana."


def persona(fecha):
    """config/persona.md con lo que depende del día del episodio (la despedida)."""
    texto = (CONFIG / "persona.md").read_text(encoding="utf-8")
    dia = DIAS[date.fromisoformat(fecha).weekday()]
    return (f"{texto.rstrip()}\n\n## Este episodio\n\n- Se publica un {dia}. "
            f"La despedida de hoy es exactamente: \"{despedida(fecha)}\"\n")
