"""Memoria de Cátodo: lo que se contó en episodios anteriores y lo que quedó pendiente.

Cada episodio guarda episodes/AAAA-MM-DD/memoria.json (lo escribe script.py):
    {"fecha", "publicado", "contadas": [{"titulo", "resumen", "asuntos_abiertos"}],
     "pendientes": [{"titulo", "resumen", "motivo", "enlaces"}]}

Solo cuentan los episodios marcados como publicados: lo que no se emitió no se
puede dar por contado. La Fase 4 los marcará al publicar; mientras tanto:
    python src/memoria.py --publicado AAAA-MM-DD

Revisión humana y correcciones:
    python src/memoria.py --aprobar AAAA-MM-DD [--nota "qué se ha revisado"]
    python src/memoria.py --correccion AAAA-MM-DD --texto "qué estaba mal y qué es lo correcto"
Un episodio no se puede marcar como publicado sin la aprobación humana. Las
correcciones se añaden a las notas del episodio afectado y el siguiente episodio
las menciona.
"""

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta

from comun import EPISODIOS, cargar_yaml


def leer(fecha):
    ruta = EPISODIOS / fecha / "memoria.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def _frases(fecha, bloque):
    """Las frases de un bloque del guion de un episodio («Apertura», «Cierre»), o []."""
    ruta = EPISODIOS / fecha / "guion.md"
    if not ruta.exists():
        return []
    m = re.search(rf"(?ms)^## {bloque}\s*\n(.*?)(?=^## |\Z)", ruta.read_text(encoding="utf-8"))
    return re.split(r"(?<=[.:!?])\s+", " ".join(m.group(1).split())) if m else []


def apertura(fecha):
    """La frase que sigue a la firma en la apertura de un episodio (el enlace al gancho), o None."""
    frases = _frases(fecha, "Apertura")
    return frases[1] if len(frases) > 1 else None


def cierre(fecha):
    """El paso que precede a la parte fija del cierre («Y con esto termino.»), o None."""
    frases = _frases(fecha, "Cierre")
    for n, f in enumerate(frases):
        if n and f.lower().startswith("el guion y la voz"):
            return frases[n - 1]
    return None


def contexto(fecha, dias=7, dias_pendientes=3):
    """Texto en Markdown con la memoria de los días anteriores a `fecha`, para el editor."""
    hoy = date.fromisoformat(fecha)
    episodios = []
    for n in range(1, dias + 1):
        dia = (hoy - timedelta(days=n)).isoformat()
        m = leer(dia)
        if m and m.get("publicado"):
            episodios.append((n, dia, m))
    if not episodios:
        return "No hay episodios anteriores publicados: este es el primero (o el primero tras una pausa)."

    partes = ["## Lo que Cátodo contó en episodios anteriores"]
    for n, dia, m in episodios:
        cuando = "ayer" if n == 1 else f"hace {n} días"
        partes.append(f"\n### Episodio del {dia} ({cuando})")
        for c in m.get("contadas", []):
            linea = f"- **{c['titulo']}**: {c['resumen']}"
            if c.get("asuntos_abiertos"):
                linea += " Asuntos abiertos: " + "; ".join(c["asuntos_abiertos"]) + "."
            partes.append(linea)

    correcciones = [(dia, c) for n, dia, m in episodios for c in m.get("correcciones", [])
                    if not c.get("mencionada")]
    if correcciones:
        partes.append("\n## Correcciones que hay que mencionar en este episodio")
        for dia, c in correcciones:
            partes.append(f"- Sobre el episodio del {dia}: {c['texto']}")

    anunciadas = [p for p in episodios[0][2].get("pendientes", []) if p.get("anunciar")]
    if anunciadas:
        partes.append(f"\n## Anunciado en el episodio del {episodios[0][1]} para hoy (hay que contarlo)")
        for p in anunciadas:
            partes.append(f"- **{p['titulo']}**: {p.get('resumen', '')}"
                          + (f" Enlaces: {', '.join(p['enlaces'][:3])}" if p.get("enlaces") else ""))
    n_anuncios = sum(1 for n, dia, m in episodios[:5] for p in m.get("pendientes", []) if p.get("anunciar"))
    partes.append(f"\n(En los últimos {min(len(episodios), 5)} episodios se anunció algo para el día "
                  f"siguiente {n_anuncios} {'vez' if n_anuncios == 1 else 'veces'}.)")

    formulas = [(dia, apertura(dia), cierre(dia)) for n, dia, m in episodios[:5]]
    formulas = [(dia, a, c) for dia, a, c in formulas if a or c]
    if formulas:
        partes.append("\n## Cómo enlazaron la apertura y el cierre en episodios anteriores (no repitas las fórmulas)")
        for dia, a, c in formulas:
            partes.append(f"- ({dia}) Apertura: {a or '(sin dato)'} Cierre: {c or '(sin dato)'}")

    pendientes = [(n, dia, p) for n, dia, m in episodios if n <= dias_pendientes
                  for p in m.get("pendientes", [])]
    if pendientes:
        partes.append("\n## Noticias que quedaron pendientes (no se contaron)")
        for n, dia, p in pendientes:
            partes.append(f"- ({dia}) **{p['titulo']}**: {p.get('resumen', '')} Motivo: {p.get('motivo', '')}"
                          + (f" Enlaces: {', '.join(p['enlaces'][:3])}" if p.get("enlaces") else ""))
    return "\n".join(partes)


# Temas demasiado generales para enlazar episodios: casarían con casi todo.
GENERICOS = {"ia", "inteligencia artificial", "tecnologia", "internet", "empresas", "gobierno",
             "estados unidos", "eeuu", "europa", "china", "espana", "bolsa", "apps", "moviles"}


def _normal(texto):
    """Minúsculas y sin tildes, para comparar temas."""
    sin = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin if not unicodedata.combining(c))


def temas(contada):
    """Los temas de una noticia contada. Si es de antes de que se guardaran, los nombres
    propios de su título (salvo la primera palabra, que va en mayúscula igualmente)."""
    if contada.get("temas"):
        return [t for t in contada["temas"] if _normal(t) not in GENERICOS and len(t) >= 3]
    palabras = re.findall(r"\w[\w.&-]*", contada.get("titulo", ""))
    return [w for w in palabras[1:] if w[0].isupper() and len(w) >= 3 and _normal(w) not in GENERICOS]


def antecedentes(fecha, texto, dias=7, maximo=8):
    """Índice de temas: lo que se contó hace más de `dias` días sobre algo que aparece en
    `texto` (las candidatas o la escaleta de hoy). Texto en Markdown, o "" si no hay nada."""
    hoy = date.fromisoformat(fecha)
    limite = (hoy - timedelta(days=dias)).isoformat()
    buscado = _normal(texto)
    encontradas = []
    for ruta in sorted(EPISODIOS.glob("*/memoria.json"), reverse=True):
        dia = ruta.parent.name
        if dia >= limite:
            continue
        m = json.loads(ruta.read_text(encoding="utf-8"))
        if not m.get("publicado"):
            continue
        for c in m.get("contadas", []):
            coinciden = [t for t in temas(c) if re.search(rf"\b{re.escape(_normal(t))}\b", buscado)]
            if coinciden:
                encontradas.append((dia, c, coinciden))
    if not encontradas:
        return ""
    partes = ["## Antecedentes de hace más de una semana (índice de temas)",
              "Noticias antiguas que comparten tema con las de hoy. Úsalas solo si la de hoy depende de "
              "ellas o las completa, con una mención breve dentro de la frase. Lo normal es no usarlas."]
    for dia, c, coinciden in encontradas[:maximo]:
        partes.append(f"- ({dia}, por {', '.join(coinciden)}) **{c['titulo']}**: {c['resumen']}")
    return "\n".join(partes)


def _ruta(fecha):
    ruta = EPISODIOS / fecha / "memoria.json"
    if not ruta.exists():
        sys.exit(f"No existe {ruta}: ese episodio no tiene guion.")
    return ruta


def _guardar(ruta, m):
    ruta.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def aprobar(fecha, nota=""):
    """Deja constancia de que un humano ha revisado el guion (Reglamento de IA y diligencia)."""
    ruta = _ruta(fecha)
    m = json.loads(ruta.read_text(encoding="utf-8"))
    m["revision_humana"] = {"aprobado": True, "cuando": datetime.now().isoformat(timespec="minutes"),
                            "nota": nota}
    _guardar(ruta, m)
    revision = EPISODIOS / fecha / "revision.md"
    if revision.exists():
        with open(revision, "a", encoding="utf-8") as f:
            f.write(f"\n## Revisión humana\n\nAprobado el {m['revision_humana']['cuando']}."
                    + (f" {nota}" if nota else "") + "\n")


def publicacion_automatica(fecha, nota=""):
    """Deja constancia de que se publica solo, sin revisión humana previa: tras las
    comprobaciones automáticas, y lo revisan personas después, al escucharlo (decidido
    el 25 de noviembre de 2026)."""
    ruta = _ruta(fecha)
    m = json.loads(ruta.read_text(encoding="utf-8"))
    m["revision_humana"] = {"aprobado": False, "publicacion_automatica": True,
                            "cuando": datetime.now().isoformat(timespec="minutes"), "nota": nota}
    _guardar(ruta, m)


def se_puede_publicar(m):
    """Aprobado por una persona o publicado solo (publicacion_automatica)."""
    revision = (m or {}).get("revision_humana", {})
    return bool(revision.get("aprobado") or revision.get("publicacion_automatica"))


def marcar_publicado(fecha, valor=True):
    ruta = _ruta(fecha)
    m = json.loads(ruta.read_text(encoding="utf-8"))
    if valor and not se_puede_publicar(m):
        sys.exit(f"El episodio {fecha} no está aprobado: revísalo y ejecuta `make aprobar FECHA={fecha}`.")
    m["publicado"] = valor
    _guardar(ruta, m)
    if valor:
        # Las correcciones de episodios anteriores se mencionan en este, así que quedan saldadas.
        hoy = date.fromisoformat(fecha)
        for n in range(1, 31):
            dia = (hoy - timedelta(days=n)).isoformat()
            ruta_ant = EPISODIOS / dia / "memoria.json"
            if ruta_ant.exists():
                ant = json.loads(ruta_ant.read_text(encoding="utf-8"))
                cambiado = False
                for c in ant.get("correcciones", []):
                    if not c.get("mencionada"):
                        c["mencionada"] = fecha
                        cambiado = True
                if cambiado:
                    _guardar(ruta_ant, ant)


def corregir(fecha, texto):
    """Registra una corrección: se añade a las notas del episodio y se menciona en el siguiente."""
    ruta = _ruta(fecha)
    m = json.loads(ruta.read_text(encoding="utf-8"))
    hoy = date.today().isoformat()
    m.setdefault("correcciones", []).append({"fecha": hoy, "texto": texto, "mencionada": False})
    _guardar(ruta, m)
    notas = EPISODIOS / fecha / "notas.md"
    if notas.exists():
        with open(notas, "a", encoding="utf-8") as f:
            f.write(f"\n**Corrección ({hoy}):** {texto}\n")


def main():
    parser = argparse.ArgumentParser(description="Memoria de Cátodo")
    parser.add_argument("--fecha", default=date.today().isoformat(), help="muestra la memoria vista desde esta fecha")
    parser.add_argument("--publicado", metavar="FECHA", help="marca el episodio de esa fecha como publicado")
    parser.add_argument("--aprobar", metavar="FECHA", help="deja constancia de la revisión humana")
    parser.add_argument("--nota", default="", help="con --aprobar: qué se ha revisado")
    parser.add_argument("--correccion", metavar="FECHA", help="registra una corrección del episodio de esa fecha")
    parser.add_argument("--texto", help="con --correccion: qué estaba mal y qué es lo correcto")
    args = parser.parse_args()
    if args.aprobar:
        aprobar(args.aprobar, args.nota)
        print(f"Episodio {args.aprobar} aprobado por un humano.")
        return
    if args.correccion:
        if not args.texto:
            sys.exit("Falta --texto con la corrección.")
        corregir(args.correccion, args.texto)
        print(f"Corrección añadida a las notas del {args.correccion}; el próximo episodio la mencionará.")
        return
    if args.publicado:
        marcar_publicado(args.publicado)
        print(f"Episodio {args.publicado} marcado como publicado: entra en la memoria.")
        return
    ajustes = cargar_yaml("settings.yaml")["memoria"]
    print(contexto(args.fecha, ajustes["dias"], ajustes["dias_pendientes"]))


if __name__ == "__main__":
    main()
