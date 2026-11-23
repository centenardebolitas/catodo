"""Fase 1, paso 2: agrupa la misma noticia publicada en varias fuentes y la ordena.

Uso:
    python src/rank.py [--fecha AAAA-MM-DD] [--metodo claude|estadistico] [--detalle]

Lee episodes/AAAA-MM-DD/articulos.json y escribe news.json con las mejores
candidatas. Una noticia solo pasa si la cubren al menos
noticias.grupos_minimos grupos editoriales independientes.

Dos métodos para agrupar (noticias.agrupacion en settings.yaml):
- claude: Claude lee los titulares y junta los que cuentan la misma historia,
  aunque estén en idiomas distintos, y marca lo que no es noticia.
- estadistico: sin IA. Compara titulares por las palabras poco frecuentes que
  comparten (pesos IDF). Se usa como respaldo si Claude falla.
La regla de dos grupos y la puntuación siempre las aplica el código.
"""

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone

import claude_cli
from comun import EPISODIOS, cargar_yaml

PROMPT_AGRUPAR = """Eres el documentalista de Cátodo, un podcast diario de noticias de tecnología en español.

Abajo tienes los artículos publicados en las últimas horas por muchos medios, uno por línea:
número | idioma | grupo editorial | fuente | titular — arranque del resumen

Tu tarea es agrupar los artículos que cuentan la misma historia:
- Junta los artículos sobre el mismo hecho o la misma historia en curso, aunque estén en idiomas distintos o la cuenten con enfoques diferentes (por ejemplo, una dimisión, las reacciones y lo que se sabe después van juntos).
- No juntes historias distintas solo porque compartan empresa o tema (dos noticias diferentes sobre Apple son dos historias).
- Cada artículo puede estar como mucho en una historia.
- Devuelve SOLO las historias que tengan dos o más artículos. Los artículos sueltos no hace falta devolverlos.
- Para cada historia, escribe un titular y un resumen de una o dos frases en español de España, con tus palabras y solo con lo que dicen los titulares y resúmenes (no inventes datos).
- Marca es_noticia = false si la historia no es una noticia de tecnología para el podcast: ofertas o descuentos, reseñas de productos, guías y tutoriales, listas ("los mejores..."), contenido promocional, o temas sin componente tecnológico (deportes, política o cine sin relación con la tecnología). Explica brevemente el motivo en ese caso.

Artículos:
{articulos}
"""

ESQUEMA_AGRUPAR = {
    "type": "object",
    "properties": {
        "historias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "integer"}},
                    "titular": {"type": "string"},
                    "resumen": {"type": "string"},
                    "es_noticia": {"type": "boolean"},
                    "motivo": {"type": "string"},
                },
                "required": ["ids", "titular", "resumen", "es_noticia"],
            },
        }
    },
    "required": ["historias"],
}

# Palabras vacías en inglés y español, más palabras de titular demasiado genéricas.
VACIAS = set("""
a about after against all also an and any are as at be been before being but by can could did do
does for from had has have how if in into is it its just more most new no not now of off on one
only or other our out over says said so some than that the their them then there these they this
those through to under up us was we were what when where which while who why will with would you
your yes get gets got make makes made use uses used launch launches launched update updates report
reports reportedly week today year years first could people company companies now its it's
el la los las un una unos unas de del al a ante bajo con contra desde en entre hacia hasta para por
segun sin sobre tras y e o u ni que como cuando donde quien cual cuales es son ser sido fue fueron
era han ha he hay hace hacer esta este esto estos estas ese esa eso esos esas lo le les se su sus
mas muy ya no si sí tambien pero porque asi aqui todo todos toda todas nuevo nueva nuevos nuevas
puede pueden tiene tienen va van dice dicen año años hoy ahora mejor gran primer primera solo
""".split())


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.replace("'s", " ").replace("’s", " ")


def fichas(articulo):
    """Conjunto de palabras significativas del titular y el arranque del resumen."""
    texto = articulo["titulo"] + " " + articulo["resumen"][:160]
    palabras = re.findall(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*", normalizar(texto))
    return {p for p in palabras if p not in VACIAS and (len(p) >= 3 or any(c.isdigit() for c in p))}


def calcular_idf(articulos):
    conjuntos = [fichas(a) for a in articulos]
    df = Counter(p for c in conjuntos for p in c)
    return {p: math.log(len(articulos) / df[p]) for p in df}


def similitudes(articulos):
    """Matriz de similitud coseno con pesos IDF (presencia, no frecuencia)."""
    conjuntos = [fichas(a) for a in articulos]
    n = len(articulos)
    idf = calcular_idf(articulos)
    normas = [math.sqrt(sum(idf[p] ** 2 for p in c)) or 1.0 for c in conjuntos]
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            comunes = conjuntos[i] & conjuntos[j]
            if articulos[i]["url"] == articulos[j]["url"]:
                s = 1.0
            elif len(comunes) < 2:
                s = 0.0
            else:
                s = sum(idf[p] ** 2 for p in comunes) / (normas[i] * normas[j])
            sim[i][j] = sim[j][i] = s
    return sim


def agrupar(articulos, umbral):
    """Agrupamiento aglomerativo por enlace medio: junta mientras la media supere el umbral."""
    sim = similitudes(articulos)
    grupos = {i: [i] for i in range(len(articulos))}
    suma = {i: {j: sim[i][j] for j in range(len(articulos)) if j != i} for i in grupos}
    while True:
        mejor, par = umbral, None
        for i in grupos:
            for j, s in suma[i].items():
                if j > i:
                    media = s / (len(grupos[i]) * len(grupos[j]))
                    if media >= mejor:
                        mejor, par = media, (i, j)
        if not par:
            break
        i, j = par
        grupos[i].extend(grupos.pop(j))
        del suma[j]
        suma[i].pop(j, None)
        for k in grupos:
            if k != i:
                suma[i][k] = suma[i].get(k, 0) + suma[k].pop(j, 0)
                suma[k][i] = suma[i][k]
    return [[articulos[k] for k in miembros] for miembros in grupos.values()]


def fusionar_temas(noticias, idf, umbral):
    """Segunda pasada: une noticias que comparten protagonistas (por ejemplo, varios
    enfoques de la misma historia o la versión en inglés y en español)."""

    def vector(noticia):
        cuenta = Counter(p for a in noticia for p in fichas(a))
        v = {p: c * idf[p] for p, c in cuenta.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {p: x / norma for p, x in v.items()}

    noticias = [list(n) for n in noticias]
    vectores = [vector(n) for n in noticias]
    while True:
        mejor, par = umbral, None
        for i in range(len(noticias)):
            for j in range(i + 1, len(noticias)):
                comunes = vectores[i].keys() & vectores[j].keys()
                s = sum(vectores[i][p] * vectores[j][p] for p in comunes)
                if s >= mejor:
                    mejor, par = s, (i, j)
        if not par:
            return noticias
        i, j = par
        noticias[i].extend(noticias.pop(j))
        vectores.pop(j)
        vectores[i] = vector(noticias[i])


def agrupar_con_claude(articulos, ajustes_claude, registro):
    """Devuelve (noticias, metadatos): listas de artículos y, por noticia, titular,
    resumen y si es noticia según Claude. Los artículos sueltos van como noticias de uno."""
    lineas = [
        f"{n} | {a['idioma']} | {a['grupo']} | {a['fuente']} | {a['titulo']} — {a['resumen'][:150]}"
        for n, a in enumerate(articulos)
    ]
    respuesta = claude_cli.llamar(
        PROMPT_AGRUPAR.format(articulos="\n".join(lineas)),
        modelo=ajustes_claude["modelo_agrupar"],
        esfuerzo=ajustes_claude.get("esfuerzo_agrupar"),
        esquema=ESQUEMA_AGRUPAR,
        registro=registro,
    )
    usados, noticias, metadatos = set(), [], []
    for h in respuesta["historias"]:
        ids = [i for i in dict.fromkeys(h["ids"]) if 0 <= i < len(articulos) and i not in usados]
        if len(ids) < 2:
            continue
        usados.update(ids)
        noticias.append([articulos[i] for i in ids])
        metadatos.append({"titular": h["titular"], "resumen": h["resumen"],
                          "es_noticia": h["es_noticia"], "motivo": h.get("motivo", "")})
    for i, a in enumerate(articulos):
        if i not in usados:
            noticias.append([a])
            metadatos.append(None)
    return noticias, metadatos


def grupos_de(noticia):
    """Grupos editoriales que cubren la noticia (las redes sociales no cuentan)."""
    return {a["grupo"] for a in noticia if not a["grupo"].startswith("(")}


def puntuar(noticia, pesos):
    grupos = grupos_de(noticia)
    fuentes_propias = {a["fuente"] for a in noticia if not a["agregador"]}
    techmeme = any(a["fuente"] == "Techmeme" for a in noticia)
    puntos_hn = max((a["puntos_hn"] or 0 for a in noticia), default=0)
    return round(
        pesos["por_grupo"] * len(grupos)
        + pesos["por_fuente"] * sum(next(a["peso"] for a in noticia if a["fuente"] == f) for f in fuentes_propias)
        + (pesos["techmeme"] if techmeme else 0)
        + pesos["hacker_news"] * min(puntos_hn / 500, 1),
        2,
    )


def ficha_noticia(noticia, puntuacion, meta=None):
    # Titular representativo: el de Claude si lo hay; si no, el de una fuente propia
    # (no agregador) en español.
    orden = sorted(noticia, key=lambda a: (a["agregador"], a["idioma"] != "es", -a["peso"], a["fecha"]))
    principal = orden[0]
    return {
        "titular": meta["titular"] if meta else principal["titulo"],
        "resumen": meta["resumen"] if meta else principal["resumen"],
        "grupos": sorted(grupos_de(noticia)),
        "fuentes": sorted({a["fuente"] for a in noticia}),
        "fecha": min(a["fecha"] for a in noticia),
        "puntuacion": puntuacion,
        "enlaces": [
            {k: a[k] for k in ("fuente", "grupo", "medio", "idioma", "titulo", "url", "fecha")}
            for a in sorted(noticia, key=lambda a: a["fecha"])
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Agrupa y ordena las noticias de Cátodo")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--metodo", choices=["claude", "estadistico"],
                        help="cómo agrupar (por defecto, noticias.agrupacion en settings.yaml)")
    parser.add_argument("--detalle", action="store_true", help="muestra los titulares de cada noticia")
    args = parser.parse_args()

    config = cargar_yaml("settings.yaml")
    ajustes = config["noticias"]
    metodo = args.metodo or ajustes.get("agrupacion", "claude")
    carpeta = EPISODIOS / args.fecha
    articulos = json.loads((carpeta / "articulos.json").read_text(encoding="utf-8"))

    metadatos = None
    if metodo == "claude":
        print(f"Agrupando {len(articulos)} artículos con Claude…")
        try:
            noticias, metadatos = agrupar_con_claude(articulos, config["claude"],
                                                     carpeta / "pasadas" / "00-agrupar.json")
        except claude_cli.ErrorClaude as e:
            print(f"  Aviso: {e}\n  Uso el método estadístico como respaldo.")
            metodo = "estadistico"
    if metodo == "estadistico":
        noticias = agrupar(articulos, ajustes["umbral_similitud"])
        noticias = fusionar_temas(noticias, calcular_idf(articulos), ajustes["umbral_tema"])
        metadatos = [None] * len(noticias)

    validas, de_un_grupo, no_noticias = [], [], []
    for noticia, meta in zip(noticias, metadatos):
        p = puntuar(noticia, ajustes["pesos"])
        if meta and not meta["es_noticia"]:
            no_noticias.append((p, noticia, meta))
        elif len(grupos_de(noticia)) >= ajustes["grupos_minimos"]:
            validas.append((p, noticia, meta))
        else:
            de_un_grupo.append((p, noticia, meta))
    for lista in (validas, de_un_grupo, no_noticias):
        lista.sort(key=lambda x: -x[0])
    candidatas = [ficha_noticia(n, p, m) for p, n, m in validas[: ajustes["candidatas"]]]

    salida = {
        "fecha": args.fecha,
        "generado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "metodo": metodo,
        "articulos": len(articulos),
        "noticias_distintas": len(noticias),
        "con_varios_grupos": len(validas),
        "candidatas": candidatas,
    }
    (carpeta / "news.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{len(articulos)} artículos -> {len(noticias)} noticias distintas ({metodo}); "
          f"{len(validas)} cubiertas por {ajustes['grupos_minimos']} o más grupos.\n")
    for n, c in enumerate(candidatas, 1):
        print(f"{n:2}. [{c['puntuacion']:5}] {c['titular'][:90]}")
        print(f"      {len(c['grupos'])} grupos: {', '.join(c['grupos'][:8])}{'…' if len(c['grupos']) > 8 else ''}")
        if args.detalle:
            for e in c["enlaces"]:
                print(f"        - {e['fuente']} ({e['medio']}): {e['titulo'][:80]}")
    if no_noticias:
        print("\nDescartadas por no ser noticia (según Claude):")
        for p, n, m in no_noticias[:6]:
            print(f"   {m['titular'][:70]} ({m['motivo'][:50]})")
    if de_un_grupo:
        print("\nDescartadas por tener un solo grupo (las más fuertes):")
        for p, n, m in de_un_grupo[:5]:
            print(f"   [{p:5}] {n[0]['titulo'][:80]} ({n[0]['grupo']}, {len(n)} art.)")
    print(f"\n-> {(carpeta / 'news.json').relative_to(EPISODIOS.parent)}")


if __name__ == "__main__":
    main()
