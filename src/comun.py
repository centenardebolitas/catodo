"""Utilidades compartidas: rutas del proyecto, configuración y variables de entorno."""

import os
import re
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
    proximo = "el lunes" if date.fromisoformat(fecha).weekday() >= 4 else "mañana"
    return (f"{texto.rstrip()}\n\n## Este episodio\n\n- Se publica un {dia}. "
            f"La despedida de hoy es exactamente: \"{despedida(fecha)}\"\n"
            f"- El próximo episodio sale {proximo}.\n")


_LINEA_ENLACE = re.compile(r"^\s*[-*]\s+(\[[^\]]+\]\([^)\s]+\))\s*$")


def enlaces_en_linea(notas):
    """Las fuentes de cada noticia van en una sola línea separadas por « · », nunca en lista.

    El formato de notas.md (lo que acaba en la web, el feed y las apps): tras el título y el
    resumen de cada noticia, «[Medio](url) · [Medio](url) · …». Si llegan como lista de
    Markdown (una línea «- [Medio](url)» por enlace), se juntan en una línea."""
    lineas, grupo = [], []
    for linea in notas.splitlines():
        m = _LINEA_ENLACE.match(linea)
        if m:
            grupo.append(m.group(1))
            continue
        if grupo:
            lineas.append(" · ".join(grupo))
            grupo = []
        lineas.append(linea)
    if grupo:
        lineas.append(" · ".join(grupo))
    return "\n".join(lineas) + ("\n" if notas.endswith("\n") else "")
