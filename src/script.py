"""Fase 2: prepara el guion del episodio en cinco pasadas con Claude.

Uso:
    python src/script.py [--fecha AAAA-MM-DD] [--desde N]

Pasadas (cada una es una llamada independiente a `claude -p`):
  1. Editor: con news.json y la memoria de días anteriores, decide la escaleta.
  2. Redacción: lee los artículos originales y escribe el guion con la voz de Cátodo.
  3. Verificación: contrasta cada dato con las fuentes.
  4. Abogado del diablo: rebate el guion.
  5. Versión final: aplica las correcciones.

Deja en episodes/AAAA-MM-DD/: escaleta.json, guion.md, notas.md, emojis.txt (el guion en
emojis, para la portada del episodio), revision.md (lo que
tiene que mirar el humano), revision-detalle.md (el trabajo de los revisores), memoria.json y, en pasadas/, la respuesta completa de cada pasada.
Con --desde N se repite a partir de la pasada N reutilizando las anteriores.
"""

import argparse
import json
import re
import sys
from datetime import date

import claude_cli
import memoria
from reservas import Reservas
from comun import CONFIG, EPISODIOS, cargar_yaml
from comun import persona as persona_del_dia

LEER_FUENTES = ["WebFetch", "WebSearch"]

# ---------------------------------------------------------------- esquemas

ESQUEMA_ESCALETA = {
    "type": "object",
    "properties": {
        "dia_flojo": {"type": "boolean"},
        "comentario": {"type": "string"},
        "escaleta": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "orden": {"type": "integer"},
                    "tipo": {"type": "string", "enum": ["nueva", "seguimiento", "pendiente", "profundizacion"]},
                    "candidata": {"type": ["integer", "null"]},
                    "titulo": {"type": "string"},
                    "angulo": {"type": "string"},
                    "puntos_clave": {"type": "array", "items": {"type": "string"}},
                    "conexion_con_anteriores": {"type": "string"},
                    "duracion_seg": {"type": "integer"},
                    "enlaces": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["orden", "tipo", "titulo", "angulo", "duracion_seg", "enlaces"],
            },
        },
        "pendientes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidata": {"type": "integer"},
                    "titulo": {"type": "string"},
                    "resumen": {"type": "string"},
                    "motivo": {"type": "string"},
                },
                "required": ["titulo", "motivo"],
            },
        },
    },
    "required": ["dia_flojo", "comentario", "escaleta", "pendientes"],
}

ESQUEMA_GUION = {
    "type": "object",
    "properties": {
        "guion": {"type": "string"},
        "fuentes_leidas": {"type": "array", "items": {"type": "string"}},
        "avisos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["guion", "fuentes_leidas"],
}

ESQUEMA_VERIFICACION = {
    "type": "object",
    "properties": {
        "problemas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fragmento": {"type": "string"},
                    "tipo": {"type": "string", "enum": ["error", "dudoso", "sin_fuente", "exagerado",
                                                         "demasiado_cercano_al_original", "atribucion"]},
                    "problema": {"type": "string"},
                    "correccion": {"type": "string"},
                    "fuente": {"type": "string"},
                },
                "required": ["fragmento", "tipo", "problema", "correccion"],
            },
        },
        "valoracion": {"type": "string"},
    },
    "required": ["problemas", "valoracion"],
}

ESQUEMA_CRITICA = {
    "type": "object",
    "properties": {
        "criticas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "aspecto": {"type": "string"},
                    "fragmento": {"type": "string"},
                    "critica": {"type": "string"},
                    "propuesta": {"type": "string"},
                },
                "required": ["aspecto", "critica", "propuesta"],
            },
        },
        "lo_mejor": {"type": "string"},
    },
    "required": ["criticas", "lo_mejor"],
}

ESQUEMA_FINAL = {
    "type": "object",
    "properties": {
        "guion": {"type": "string"},
        "notas": {"type": "string"},
        "cambios": {"type": "array", "items": {"type": "string"}},
        "dudas_para_revisor": {"type": "array", "items": {"type": "string"}},
        "contadas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "resumen": {"type": "string"},
                    "asuntos_abiertos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["titulo", "resumen", "asuntos_abiertos"],
            },
        },
        "emojis": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["guion", "notas", "cambios", "dudas_para_revisor", "contadas", "emojis"],
}

# ---------------------------------------------------------------- prompts

EDITOR = """Eres el editor jefe de Cátodo. Esta noche preparas la escaleta del episodio de mañana.

{persona}

# Objetivo de duración
Unos {minutos} minutos en total: entre {palabras_min} y {palabras_max} palabras de guion (unas 150 palabras por minuto). Entre {noticias_min} y {noticias_max} noticias, salvo en días flojos.

# Memoria de episodios anteriores
{memoria}

# Candidatas de hoy
Cada candidata ya cumple la regla de al menos dos grupos editoriales independientes. Están ordenadas por relevancia estimada (más grupos y fuentes, más arriba), pero la decisión es tuya.

{candidatas}

# Tu tarea
1. Elige y ordena las noticias del episodio. La más importante primero.
2. Para cada una, define el ángulo: qué contar, por qué le importa al oyente de España, y la pregunta escéptica (quién paga, quién controla, si de verdad funciona).
3. Usa la memoria: si una candidata continúa una historia ya contada, márcala como "seguimiento" y explica la conexión. No repitas lo ya contado salvo lo necesario para entender la novedad.
4. Las pendientes de días anteriores pueden entrar (tipo "pendiente") si siguen siendo relevantes; sus enlaces están en la memoria.
5. Si el día es flojo, en vez de rellenar, profundiza en una noticia o cuenta su contexto (tipo "profundizacion").
6. En "enlaces" pon las URL de la noticia: al menos dos de grupos distintos, preferiblemente artículos originales y no agregadores ni redes sociales. Los enlaces marcados "NO LEER CON IA" son de medios que no permiten que una IA lea sus artículos: cuentan como cobertura y se citan en las notas, pero la redacción no podrá abrirlos. Asegúrate de que cada noticia tenga al menos un enlace legible (mejor dos).
7. En "pendientes", las candidatas buenas que no caben hoy y podrían contarse mañana, con su motivo.
8. En "candidata", el número de la candidata (o null si es un seguimiento o pendiente de otro día).
9. Si la memoria trae correcciones que hay que mencionar, inclúyelas: una frase breve y clara en la apertura o antes de la noticia relacionada, reconociendo el error y dando el dato correcto. Indícalo en el comentario.
"""

REDACCION = """Eres el redactor de Cátodo. Escribe el guion completo del episodio a partir de la escaleta.

{persona}

# Duración
Entre {palabras_min} y {palabras_max} palabras en total. Respeta aproximadamente la duración de cada bloque de la escaleta (unas 150 palabras por minuto).

# Memoria de episodios anteriores
{memoria}

# Escaleta aprobada por el editor
{escaleta}

# Cómo trabajar
1. Antes de escribir cada noticia, lee con WebFetch al menos dos de sus "enlaces_para_leer", de grupos distintos si es posible. Si un enlace falla o tiene muro de pago, prueba con otro o busca la noticia con WebSearch en otro medio solvente.
   NUNCA abras con WebFetch los "enlaces_solo_citar" ni otros artículos de esos mismos dominios: son medios que no permiten que una IA lea su contenido. Puedes mencionarlos y atribuirles datos solo si esos datos los recoge otra fuente que sí hayas leído. Si WebFetch te dice que un sitio no permite el acceso, respétalo y no busques copias.
   Nunca uses copias que saltan muros de pago (archive.today, 12ft y similares).
   Los enlaces de news.google.com son redirecciones de Google News: no los abras. Si te hacen falta, busca con WebSearch el artículo original en el medio que indica (por el titular) y usa esa URL.
   En "fuentes_leidas" pon siempre la URL original de cada artículo, nunca la de Google News.
2. Escribe con palabras propias. No copies frases de los artículos, ni siquiera traducidas literalmente.
3. Usa solo datos que aparezcan en las fuentes que has leído. Atribuye lo que venga de un medio concreto.
4. Sigue las reglas de fechas y cifras: solo las imprescindibles.
5. Escribe la apertura y el cierre tal y como dice la persona: la firma y la parte fija del cierre palabra por palabra, el enlace y el paso de cada día sin repetir los de la memoria, y la despedida de hoy.

Devuelve el guion en "guion" (Markdown con los bloques indicados), las URL que has leído de verdad en "fuentes_leidas" y en "avisos" lo que no hayas podido comprobar.
"""

VERIFICACION = """Eres el verificador de datos de Cátodo. Tu trabajo es contrastar el guion antes de que se grabe. Sé exigente: un error emitido es mucho peor que un aviso de más.

# Reglas del podcast
{persona}

# Escaleta (con los enlaces de cada noticia)
{escaleta}

# Guion a verificar
{guion}

# Cómo trabajar
1. Para cada afirmación de hecho (datos, cifras, fechas, nombres, cargos, declaraciones, relaciones de causa), compruébala con WebFetch en los "enlaces_para_leer" de la escaleta y, si hace falta, con WebSearch en otros medios solventes. NUNCA abras los "enlaces_solo_citar" ni otros artículos de esos dominios, ni copias que salten muros de pago.
2. Señala: errores, datos dudosos o no confirmados, afirmaciones sin fuente, exageraciones, rumores presentados como hechos, atribuciones que faltan o son incorrectas, y frases demasiado cercanas al texto original de un artículo.
3. Personas con nombre y apellidos: revisa con especial cuidado todo lo que se diga de ellas. Situación judicial exacta (investigado no es acusado, acusado no es condenado), ningún hecho negativo sobre una persona que no esté en al menos dos fuentes, nada de humor a costa de particulares (personas que no son públicas) y ningún detalle íntimo que no sea necesario para la noticia.
   Acusaciones: marca como "atribucion" cualquier acusación de delito, espionaje, fraude, acoso u otra conducta ilícita o grave contra una persona o empresa identificable que no lleve a la vez la atribución a quien la hace, "presuntamente" o "supuestamente" junto a la acusación y la versión de la otra parte si existe. También si aparece en el gancho, en el título o con humor. Propón la frase corregida.
4. Copia: señala como "demasiado_cercano_al_original" cualquier frase que traduzca o calque una frase de un artículo, cualquier cita literal de un periodista (solo se permiten declaraciones públicas breves y atribuidas) y cualquier noticia que siga el orden y la estructura de un artículo concreto.
5. Para cada problema, propone una corrección concreta y la fuente que lo justifica.
6. Si todo está bien, devuelve la lista vacía y dilo en la valoración.
"""

CRITICA = """Eres el abogado del diablo de Cátodo. Tu trabajo es rebatir el guion para que salga mejor. No verifiques datos (de eso ya se encarga otro); critica el enfoque y la forma.

{persona}

# Memoria de episodios anteriores
{memoria}

# Guion
{guion}

# Qué revisar
- Equilibrio y sesgo: ¿se dan las posturas relevantes?, ¿se separan hechos de opiniones?
- La pregunta escéptica: ¿se plantea quién paga, quién controla, si de verdad funciona?
- Contexto que falta para un oyente de España; tecnicismos sin explicar.
- Exceso de fechas o cifras; frases difíciles de seguir al oído.
- Calcos del inglés y expresiones que suenan a traducción o a doblaje ("con una pizca de sal", "al final del día", "hacer sentido"…): señálalos todos con su alternativa natural en español de España.
- Humor: ¿funciona?, ¿sobra?, ¿falta?, ¿es geek sin ser forzado?
- Memoria: ¿se aprovechan los episodios anteriores?, ¿se repite algo ya contado?, ¿se finge recordar algo que no está en la memoria?
- Ritmo, transiciones, gancho de la apertura, duración de cada bloque y del total.
- Cumplimiento de la estructura, del cierre (sin nombrar a quienes revisan) y de las reglas de formato.
Para cada crítica, propone un cambio concreto. Di también qué es lo mejor del guion, para no estropearlo.
"""

FINAL = """Eres el editor final de Cátodo. Prepara la versión definitiva del guion.

{persona}

# Duración
Entre {palabras_min} y {palabras_max} palabras. Es un límite: si el guion se pasa, recorta.

# Escaleta
{escaleta}

# Guion actual
{guion}

# Informe del verificador (obligatorio corregir todos los errores; los dudosos, corregir, matizar o quitar)
{verificacion}

# URL originales que ha leído la redacción (úsalas en las notas en lugar de las de Google News)
{fuentes_leidas}

# Críticas del abogado del diablo (aplica las que mejoren el guion; ignora las que no, y di por qué en "cambios")
{critica}

# Qué devolver
- "guion": el guion final, en el mismo formato de bloques.
- "notas": las notas del episodio en Markdown, para publicar. Empiezan con una línea "# " con el título del episodio tal y como se verá en las apps de podcasts: corto (máximo unos 80 caracteres), con las dos o tres noticias principales y sin número de episodio ni fecha (por ejemplo, "# Huang vuelve a Nvidia, Riemann pasa por Lean y un día de bugs"). Después, un título propio por noticia, una frase de resumen con tus palabras y los enlaces a las fuentes (de la escaleta, tanto los leídos como los "solo citar"). El texto de cada enlace es SOLO el nombre del medio, por ejemplo [Bloomberg](url) o [Xataka](url); nunca copies el titular del artículo. No pongas nunca enlaces de news.google.com: usa la URL original del artículo (está en las URL leídas por la redacción) y, si no la tienes, deja ese medio fuera de las notas. Al final, el aviso: "Guion y voz generados con inteligencia artificial (Claude y Gemini) y revisados por personas, que escuchan cada episodio y corrigen lo que haga falta. Si ves un error, escríbenos a hola@catodo.es."
- "cambios": lista breve de lo que has cambiado respecto al guion anterior.
- "dudas_para_revisor": lo que el humano que revisa debería mirar con atención (datos que no se pudieron confirmar del todo, decisiones discutibles).
- "contadas": para la memoria de próximos episodios, una entrada por noticia contada con un resumen de lo que se dijo y los asuntos abiertos (lo que puede pasar después y conviene seguir).
- "emojis": el guion final escrito en emojis, para la portada del episodio. Una cadena por párrafo, siguiendo estas reglas:

{reglas_emojis}
"""


def reglas_emojis():
    """Las reglas de config/emojis.md, con el número de emojis de settings.yaml (portada)."""
    objetivo = cargar_yaml("settings.yaml")["portada"]["emojis_objetivo"]
    texto = (CONFIG / "emojis.md").read_text(encoding="utf-8")
    return re.sub(r"(?m)^# .*\n+", "", texto).replace("{objetivo}", str(objetivo)).strip()


def escribir_emojis(carpeta, lineas):
    """episodes/FECHA/emojis.txt, de donde sale la portada del episodio."""
    limpias = [l.strip() for l in lineas if l.strip()]
    if limpias:
        (carpeta / "emojis.txt").write_text("\n".join(limpias) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- utilidades


def json_bonito(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def marca(url, reservas):
    motivo = reservas.motivo_bloqueo(url)
    return f" (NO LEER CON IA: {motivo})" if motivo else ""


def texto_candidatas(news, reservas):
    partes = []
    for n, c in enumerate(news["candidatas"]):
        enlaces = "\n".join(f"   - [{e['grupo']}] {e['titulo']} — {e['url']}{marca(e['url'], reservas)}"
                             for e in c["enlaces"][:12])
        partes.append(f"## Candidata {n}: {c['titular']}\n{c['resumen']}\n"
                      f"Grupos ({len(c['grupos'])}): {', '.join(c['grupos'])}\nEnlaces:\n{enlaces}")
    return "\n\n".join(partes)


def preparar_escaleta(escaleta, reservas):
    """Separa los enlaces de cada noticia en los que se pueden leer con IA y los que solo se citan."""
    salida = []
    for e in escaleta["escaleta"]:
        e = dict(e)
        leer, citar = [], []
        for url in e.pop("enlaces"):
            motivo = reservas.motivo_bloqueo(url)
            (citar if motivo else leer).append(url if not motivo else f"{url} ({motivo})")
        e["enlaces_para_leer"] = leer
        e["enlaces_solo_citar"] = citar
        salida.append(e)
    return salida


def contar_palabras(guion):
    texto = re.sub(r"^#+ .*$", "", guion, flags=re.M)
    return len(re.findall(r"\w+", texto))


def informe_revision(escaleta, verificacion, critica, final, palabras, ajustes, fecha):
    """Devuelve (revision, detalle): lo que tiene que mirar el humano y todo el trabajo de los revisores."""
    dudas = final["dudas_para_revisor"]
    r = [f"# Revisión del episodio del {fecha}", ""]
    r.append(f"**Duración:** {palabras} palabras, unos {palabras / 150:.0f} minutos "
             f"(objetivo {ajustes['palabras_min']}-{ajustes['palabras_max']} palabras).")
    r.append(f"**Revisores automáticos:** el verificador encontró {len(verificacion['problemas'])} problemas y el "
             f"abogado del diablo hizo {len(critica['criticas'])} críticas; la versión final ya los ha corregido "
             f"o ha explicado por qué no (ver `revision-detalle.md`).")
    if escaleta.get("dia_flojo"):
        r.append("**El editor ha considerado que hoy es un día flojo.**")
    r += ["", "## Qué tienes que hacer", "",
          "1. Leer el guion (`guion.md`).",
          f"2. Comprobar los {len(dudas)} puntos de abajo: datos que no se han podido confirmar del todo o "
          "decisiones discutibles. Corrige `guion.md` si hace falta.",
          "3. Aprobar: `make aprobar NOTA=\"qué has comprobado\"`.", "",
          "## Puntos a comprobar", ""]
    r += [f"{n}. {d}" for n, d in enumerate(dudas, 1)] or ["Nada destacado."]
    r += ["", "## Orden del episodio", ""]
    r += [f"{e['orden']}. {e['titulo']} ({e['tipo']})" for e in escaleta["escaleta"]]
    if escaleta["pendientes"]:
        r += ["", "## Se queda para otro día", ""]
        r += [f"- {p['titulo']}" for p in escaleta["pendientes"]]

    d = [f"# Detalle de la revisión automática del {fecha}", "",
         "Trabajo de los revisores automáticos. No hace falta leerlo: lo importante está en `revision.md`.", "",
         "## Criterio del editor", "", escaleta["comentario"], ""]
    for e in escaleta["escaleta"]:
        d.append(f"{e['orden']}. **{e['titulo']}** ({e['tipo']}, {e['duracion_seg']} s): {e['angulo']}")
    if escaleta["pendientes"]:
        d += ["", "### Pendientes", ""]
        d += [f"- {p['titulo']}: {p['motivo']}" for p in escaleta["pendientes"]]
    d += ["", "## Verificación", "", verificacion["valoracion"], ""]
    for p in verificacion["problemas"]:
        d.append(f"- **{p['tipo']}**: «{p['fragmento'][:120]}» → {p['problema']} "
                 f"Corrección: {p['correccion']}" + (f" ({p['fuente']})" if p.get("fuente") else ""))
    d += ["", "## Abogado del diablo", "", f"Lo mejor: {critica['lo_mejor']}", ""]
    for c in critica["criticas"]:
        d.append(f"- **{c['aspecto']}**: {c['critica']} Propuesta: {c['propuesta']}")
    d += ["", "## Cambios en la versión final", ""]
    d += [f"- {c}" for c in final["cambios"]]
    return "\n".join(r) + "\n", "\n".join(d) + "\n"


# ---------------------------------------------------------------- principal


def main():
    parser = argparse.ArgumentParser(description="Prepara el guion de Cátodo en cinco pasadas")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--desde", type=int, default=1, choices=range(1, 6),
                        help="repite a partir de esta pasada, reutilizando las anteriores")
    args = parser.parse_args()

    ajustes = cargar_yaml("settings.yaml")
    ep, cl, mem = ajustes["episodio"], ajustes["claude"], ajustes["memoria"]
    carpeta = EPISODIOS / args.fecha
    pasadas = carpeta / "pasadas"
    news_ruta = carpeta / "news.json"
    if not news_ruta.exists():
        sys.exit(f"No existe {news_ruta}: ejecuta antes `make noticias FECHA={args.fecha}`.")
    news = json.loads(news_ruta.read_text(encoding="utf-8"))
    persona = persona_del_dia(args.fecha)
    reservas = Reservas()
    contexto = memoria.contexto(args.fecha, mem["dias"], mem["dias_pendientes"])
    comunes = {"persona": persona, "memoria": contexto, "minutos": ep["duracion_objetivo_min"],
               "palabras_min": ep["palabras_min"], "palabras_max": ep["palabras_max"],
               "noticias_min": ep["noticias_min"], "noticias_max": ep["noticias_max"]}

    def pasada(n, nombre, prompt, esquema, herramientas=None):
        ruta = pasadas / f"{n:02d}-{nombre}.json"
        if n < args.desde and ruta.exists():
            print(f"[{n}/5] {nombre}: reutilizo la pasada anterior")
            return json.loads(ruta.read_text(encoding="utf-8"))["structured_output"]
        print(f"[{n}/5] {nombre}…", flush=True)
        return claude_cli.llamar(prompt, modelo=cl["modelo_guion"], esfuerzo=cl.get("esfuerzo_guion"),
                                 esquema=esquema, herramientas=herramientas, registro=ruta,
                                 tiempo_max=cl["tiempo_max_pasada_s"])

    try:
        escaleta = pasada(1, "editor", EDITOR.format(candidatas=texto_candidatas(news, reservas), **comunes),
                          ESQUEMA_ESCALETA)
        # Las pendientes guardan los enlaces de su candidata para poder contarlas otro día.
        for p in escaleta["pendientes"]:
            c = p.get("candidata")
            if isinstance(c, int) and 0 <= c < len(news["candidatas"]):
                p["enlaces"] = [e["url"] for e in news["candidatas"][c]["enlaces"][:5]]
                p.setdefault("resumen", news["candidatas"][c]["resumen"])
        (carpeta / "escaleta.json").write_text(json_bonito(escaleta), encoding="utf-8")
        texto_escaleta = json_bonito(preparar_escaleta(escaleta, reservas))
        reservas.guardar()

        borrador = pasada(2, "redaccion", REDACCION.format(escaleta=texto_escaleta, **comunes),
                          ESQUEMA_GUION, LEER_FUENTES)
        verificacion = pasada(3, "verificacion",
                              VERIFICACION.format(escaleta=texto_escaleta, guion=borrador["guion"], **comunes),
                              ESQUEMA_VERIFICACION, LEER_FUENTES)
        critica = pasada(4, "critica", CRITICA.format(guion=borrador["guion"], **comunes), ESQUEMA_CRITICA)
        final = pasada(5, "final", FINAL.format(escaleta=texto_escaleta, guion=borrador["guion"],
                                                verificacion=json_bonito(verificacion),
                                                critica=json_bonito(critica),
                                                fuentes_leidas="\n".join(borrador.get("fuentes_leidas", [])) or "(ninguna)",
                                                reglas_emojis=reglas_emojis(), **comunes), ESQUEMA_FINAL)
    except claude_cli.ErrorClaude as e:
        sys.exit(f"\nNo se ha podido preparar el guion: {e}")

    palabras = contar_palabras(final["guion"])
    (carpeta / "guion.md").write_text(final["guion"].strip() + "\n", encoding="utf-8")
    (carpeta / "notas.md").write_text(final["notas"].strip() + "\n", encoding="utf-8")
    escribir_emojis(carpeta, final.get("emojis", []))
    revision, detalle = informe_revision(escaleta, verificacion, critica, final, palabras, ep, args.fecha)
    (carpeta / "revision.md").write_text(revision, encoding="utf-8")
    (carpeta / "revision-detalle.md").write_text(detalle, encoding="utf-8")
    (carpeta / "memoria.json").write_text(json_bonito({
        "fecha": args.fecha,
        "publicado": False,
        "contadas": final["contadas"],
        "pendientes": escaleta["pendientes"],
    }), encoding="utf-8")

    print(f"\nGuion listo: {palabras} palabras (unos {palabras / 150:.1f} minutos).")
    if not ep["palabras_min"] <= palabras <= ep["palabras_max"]:
        print(f"Aviso: fuera del rango de {ep['palabras_min']}-{ep['palabras_max']} palabras.")
    print(f"Problemas detectados por el verificador: {len(verificacion['problemas'])}; "
          f"críticas: {len(critica['criticas'])}; dudas para revisar: {len(final['dudas_para_revisor'])}.")
    print(f"Revisa {(carpeta / 'guion.md').relative_to(EPISODIOS.parent)} "
          f"y {(carpeta / 'revision.md').relative_to(EPISODIOS.parent)}.")


if __name__ == "__main__":
    main()
