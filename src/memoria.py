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


def marcar_publicado(fecha, valor=True):
    ruta = _ruta(fecha)
    m = json.loads(ruta.read_text(encoding="utf-8"))
    if valor and not m.get("revision_humana", {}).get("aprobado"):
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
