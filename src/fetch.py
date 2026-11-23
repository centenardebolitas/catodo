"""Fase 1, paso 1: descarga los feeds y guarda los artículos recientes.

Uso:
    python src/fetch.py [--fecha AAAA-MM-DD] [--incluir-inactivas]

Lee config/sources.yaml y deja en episodes/AAAA-MM-DD/articulos.json los artículos
publicados en las últimas N horas (noticias.horas_atras en settings.yaml).
Los artículos que llegan por un agregador (Techmeme, Hacker News) se atribuyen
al medio original al que enlazan.
"""

import argparse
import calendar
import hashlib
import html
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests

from comun import EPISODIOS, cargar_yaml

CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; catodo-feeds/0.1; +https://catodo.es)"}
MAX_RESUMEN = 500
SIN_GRUPO = "(red social, no cuenta)"


def texto_plano(fragmento):
    """Quita etiquetas HTML y espacios sobrantes."""
    sin_etiquetas = re.sub(r"<[^>]+>", " ", fragmento or "")
    return re.sub(r"\s+", " ", html.unescape(sin_etiquetas)).strip()


def dominio(url):
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


class Grupos:
    """Deduce el grupo editorial de una URL a partir de su dominio."""

    def __init__(self, config):
        self.mapa = {}
        for fuente in config["fuentes"]:
            for d in fuente.get("dominios", []):
                self.mapa[d] = fuente["grupo"]
        self.mapa.update(config.get("grupos_por_dominio") or {})
        for d in config.get("dominios_que_no_cuentan") or []:
            self.mapa[d] = SIN_GRUPO

    def de_url(self, url):
        host = dominio(url)
        partes = host.split(".")
        # Prueba el dominio completo y luego sus sufijos (blog.ejemplo.com -> ejemplo.com).
        for i in range(len(partes) - 1):
            candidato = ".".join(partes[i:])
            if candidato in self.mapa:
                return self.mapa[candidato]
        if len(partes) >= 3 and partes[-2] in ("co", "com", "org", "net", "gob", "gov"):
            return ".".join(partes[-3:])
        return ".".join(partes[-2:])


def fecha_entrada(entrada):
    t = entrada.get("published_parsed") or entrada.get("updated_parsed")
    return calendar.timegm(t) if t else None


def articulo_enlace_en_resumen(entrada, propio):
    """Techmeme, Slashdot: el enlace al medio original va dentro del resumen."""
    enlaces = re.findall(r'href="([^"]+)"', entrada.get("summary", ""))
    original = next((u for u in enlaces if propio not in dominio(u)
                     and not u.startswith(("mailto:", "#"))), None)
    titulo = entrada.get("title", "")
    # El título termina en "(Autor/Medio)": lo quitamos.
    titulo = re.sub(r"\s*\([^()]*\)\s*$", "", titulo)
    resumen = texto_plano(entrada.get("summary", ""))
    resumen = resumen.split(":", 1)[-1].strip() if ":" in resumen[:120] else resumen
    return original, titulo, resumen, None


def articulo_google_news(entrada):
    """Google News: el enlace es una redirección; el medio original va en <source>."""
    fuente = entrada.get("source") or {}
    origen = fuente.get("href") if hasattr(fuente, "get") else None
    titulo = entrada.get("title", "")
    medio = fuente.get("title") if hasattr(fuente, "get") else None
    if medio and titulo.endswith(" - " + medio):
        titulo = titulo[: -len(" - " + medio)]
    return entrada.get("link"), titulo, "", None, origen


def articulo_hn(entrada):
    """Hacker News (hnrss): el enlace es el artículo; los puntos van en el resumen."""
    puntos = re.search(r"Points:\s*(\d+)", entrada.get("summary", ""))
    return entrada.get("link"), entrada.get("title", ""), "", int(puntos.group(1)) if puntos else None


def descargar(fuente, desde, grupos):
    respuesta = requests.get(fuente["feed"], headers=CABECERAS, timeout=30)
    respuesta.raise_for_status()
    feed = feedparser.parse(respuesta.content)
    articulos = []
    for entrada in feed.entries:
        cuando = fecha_entrada(entrada)
        if cuando is None or cuando < desde:
            continue
        puntos, origen = None, None
        if fuente.get("agregador"):
            tipo = fuente.get("tipo_agregador", "enlace_directo")
            if tipo == "enlace_en_resumen":
                url, titulo, resumen, puntos = articulo_enlace_en_resumen(entrada, dominio(fuente["feed"]).split(".")[-2])
            elif tipo == "google_news":
                url, titulo, resumen, puntos, origen = articulo_google_news(entrada)
            else:
                url, titulo, resumen, puntos = articulo_hn(entrada)
            if not url:
                continue
            grupo = grupos.de_url(origen or url)
        else:
            url = entrada.get("link")
            titulo = entrada.get("title", "")
            resumen = texto_plano(entrada.get("summary", ""))
            grupo = fuente["grupo"]
        articulos.append({
            "id": hashlib.sha1(url.encode()).hexdigest()[:12],
            "fuente": fuente["nombre"],
            "agregador": bool(fuente.get("agregador")),
            "grupo": grupo,
            "medio": dominio(origen or url),
            "idioma": fuente["idioma"],
            "peso": fuente.get("peso", 1),
            "titulo": texto_plano(titulo),
            "resumen": resumen[:MAX_RESUMEN],
            "url": url,
            "fecha": datetime.fromtimestamp(cuando, timezone.utc).isoformat(timespec="minutes"),
            "puntos_hn": puntos,
        })
    return articulos


def main():
    parser = argparse.ArgumentParser(description="Descarga los feeds de Cátodo")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--incluir-inactivas", action="store_true",
                        help="incluye también las fuentes con activa: false (para pruebas)")
    args = parser.parse_args()

    config = cargar_yaml("sources.yaml")
    ajustes = cargar_yaml("settings.yaml")["noticias"]
    grupos = Grupos(config)
    desde = time.time() - ajustes["horas_atras"] * 3600

    excluir = [p.lower() for p in ajustes.get("excluir_si_contiene", [])]
    todos, fallos, vistos, excluidos = [], [], set(), 0
    for fuente in config["fuentes"]:
        if not fuente.get("activa", True) and not args.incluir_inactivas:
            continue
        try:
            articulos = descargar(fuente, desde, grupos)
            nuevos = []
            for a in articulos:
                clave = (a["fuente"], a["url"])
                if clave in vistos:  # algunos feeds repiten el mismo artículo
                    continue
                vistos.add(clave)
                if any(p in a["titulo"].lower() for p in excluir):
                    excluidos += 1
                    continue
                nuevos.append(a)
            print(f"  {fuente['nombre']:28} {len(nuevos):3} artículos")
            todos.extend(nuevos)
        except Exception as e:  # una fuente caída no debe parar el resto
            print(f"  {fuente['nombre']:28} FALLO: {e}")
            fallos.append(fuente["nombre"])

    carpeta = EPISODIOS / args.fecha
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = carpeta / "articulos.json"
    salida.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(todos)} artículos de las últimas {ajustes['horas_atras']} h -> {salida.relative_to(EPISODIOS.parent)}"
          f" ({excluidos} descartados por ser ofertas o similares)")
    if fallos:
        print(f"Aviso: no se han podido leer {len(fallos)} fuentes: {', '.join(fallos)}")
    if not todos:
        sys.exit("No hay artículos: revisa la conexión o los feeds.")


if __name__ == "__main__":
    main()
