"""Comentarios de Ulises a un episodio desde el móvil (ops#118): prompt, esquema y textos.

Ulises contesta a la decisión del episodio con un texto («en la noticia 1 añade
"presuntamente" y quita el chiste de Bessent»). ops corre scripts/ops/responder.sh con
ese texto (OPS_DECISION_TEXT) y src/ops.py:corregir aplica el comentario al guion con
Claude, vuelve a verificar si cambian hechos, rehace solo los bloques de voz que
cambian y le devuelve la versión nueva con las mismas opciones. Aquí, lo que no toca
ficheros ni red, para poder probarlo.
"""

import difflib
import re

ESQUEMA_CORRECCION = {
    "type": "object",
    "properties": {
        "guion": {"type": "string"},
        "notas": {"type": "string"},
        "cambios": {"type": "array", "items": {"type": "string"}},
        "no_aplicado": {"type": "array", "items": {"type": "string"}},
        "hechos_cambiados": {"type": "boolean"},
    },
    "required": ["guion", "notas", "cambios", "no_aplicado", "hechos_cambiados"],
}

CORRECCION = """Eres el editor final de Cátodo. Ulises, el humano que revisa cada episodio antes de publicarlo, ha leído y escuchado el guion y te deja un comentario. Aplícalo.

# Reglas del podcast
{persona}

# Escaleta (con los enlaces de cada noticia)
{escaleta}

# Comentarios anteriores de Ulises a este episodio (ya aplicados)
{anteriores}

# Comentario de Ulises que tienes que aplicar ahora
{comentario}

# Guion actual
{guion}

# Notas del episodio actuales
{notas}

# Cómo trabajar
1. Aplica el comentario con los cambios mínimos: no reescribas lo que no te pide tocar. Mantén los encabezados "## " de cada bloque tal cual, salvo que el comentario pida quitar o añadir una noticia.
2. Las reglas del podcast mandan sobre el comentario. Si algo del comentario las incumple (por ejemplo, una acusación sin «presuntamente» ni atribución), aplícalo cumpliéndolas y explícalo en "cambios"; si no se puede, déjalo en "no_aplicado" con el motivo.
3. Si el comentario pide añadir o cambiar un dato, compruébalo antes con WebFetch en los "enlaces_para_leer" de la escaleta o con WebSearch en medios solventes. NUNCA abras los "enlaces_solo_citar" ni otros artículos de esos dominios. Si no puedes confirmarlo, no lo añadas y dilo en "no_aplicado".
4. Si el comentario es una pregunta o no pide cambios, devuelve el guion y las notas sin tocar, "cambios" vacío y la respuesta en "no_aplicado".
5. Ajusta las notas solo si cambian las fuentes o lo que se cuenta.
6. "cambios": una frase por cambio, en lenguaje llano ("Noticia 1: añadido «presuntamente» a la acusación de espionaje"). "hechos_cambiados": true si has añadido, quitado o cambiado algún dato, cifra, nombre, atribución o afirmación de hecho; false si solo son cambios de tono, orden o estilo.
"""


def comentarios_anteriores(hilo):
    """Lo que Ulises ha escrito antes en el hilo, sin el último comentario (que llega aparte)."""
    textos = [m.get("body") for m in hilo.get("messages", []) if m.get("author") == "user" and m.get("body")]
    return textos[:-1]


def bloques_cambiados(antes, despues):
    """Títulos de los bloques "## " que han cambiado, se han añadido o se han quitado."""
    def por_titulo(texto):
        bloques = {}
        for parte in re.split(r"(?m)^## ", texto)[1:]:
            titulo, _, cuerpo = parte.partition("\n")
            bloques[titulo.strip()] = cuerpo.strip()
        return bloques
    a, d = por_titulo(antes), por_titulo(despues)
    return [t for t in dict.fromkeys([*a, *d]) if a.get(t) != d.get(t)]


def diferencias(antes, despues, limite=3000):
    """Las líneas cambiadas del guion, para que el verificador mire solo eso."""
    lineas = [l for l in difflib.unified_diff(antes.splitlines(), despues.splitlines(), lineterm="", n=0)
              if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    texto = "\n".join(lineas)
    return texto if len(texto) <= limite else texto[:limite] + "\n…"


def mensaje_ronda(fecha, version, correccion, problemas, bloques, url_audio, url_guion, minutos):
    """El mensaje de la ronda nueva: qué ha cambiado, qué no y lo que hay que volver a mirar."""
    lineas = [f"Versión {version} del episodio del **{fecha}**, con tu comentario. Unos {minutos:.0f} minutos.", "",
              f"- [Escuchar el episodio]({url_audio})", f"- [Leer el guion]({url_guion})", ""]
    if correccion["cambios"]:
        lineas += ["## Cambios", "", *[f"- {c}" for c in correccion["cambios"]], ""]
    else:
        lineas += ["No he cambiado nada del guion.", ""]
    if correccion["no_aplicado"]:
        lineas += ["## Sin aplicar", "", *[f"- {c}" for c in correccion["no_aplicado"]], ""]
    if problemas:
        lineas += ["## Puntos a comprobar tras el cambio", "",
                   *[f"{n}. «{p['fragmento'][:120]}»: {p['problema']}" for n, p in enumerate(problemas, 1)], ""]
    if bloques:
        lineas += [f"Voz rehecha en: {', '.join(bloques)}.", ""]
    lineas += ["«Aprobar y programar» lo publica a las 6:00; «No publicar» no cambia nada. "
               "Puedes volver a responder con más comentarios."]
    return "\n".join(lineas).strip()


def apunte_revision(version, comentario, correccion, problemas):
    """Lo que queda en revision.md de cada ronda: constancia de la revisión humana."""
    lineas = [f"\n## Comentario de la revisión (versión {version})", "", comentario.strip(), ""]
    lineas += [f"- {c}" for c in correccion["cambios"]] or ["- Sin cambios en el guion."]
    lineas += [f"- Sin aplicar: {c}" for c in correccion["no_aplicado"]]
    lineas += [f"- Verificación: {p['problema']}" for p in problemas]
    return "\n".join(lineas) + "\n"
