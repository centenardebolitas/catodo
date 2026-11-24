"""Enlace de cada episodio en Apple Podcasts, para la web.

Uso:
    python src/enlaces.py

Apple tarda unas horas en indexar cada episodio nuevo. Su búsqueda pública (iTunes
Lookup, sin cuenta ni clave) devuelve los episodios del programa con el guid de nuestro
feed (catodo-AAAA-MM-DD), así que se puede saber el enlace exacto de cada uno. Este
script lo busca para los episodios publicados que aún no lo tienen y lo guarda en su
publicacion.json (url_apple); feed.py lo usa en la insignia de la página del episodio.
Si Apple no lo tiene todavía o no responde, no pasa nada: se queda el enlace al programa.

publish.py lo llama antes de regenerar la web, así que el enlace del episodio de ayer
llega con la publicación de hoy.
"""

import json

import requests

from comun import EPISODIOS, cargar_yaml

LOOKUP = "https://itunes.apple.com/lookup"


def id_apple(cfg):
    """El id del programa en Apple, sacado de su enlace en config/podcast.yaml."""
    for p in cfg.get("escuchar") or []:
        if p["nombre"] == "Apple Podcasts" and "/id" in p["url"]:
            return p["url"].rsplit("/id", 1)[1].split("?")[0]
    return None


def episodios_de_apple(id_programa, pais="es"):
    """{guid: enlace} de los episodios que Apple tiene indexados."""
    r = requests.get(LOOKUP, params={"id": id_programa, "entity": "podcastEpisode", "country": pais, "limit": 200},
                     timeout=20)
    r.raise_for_status()
    return {e["episodeGuid"]: e["trackViewUrl"].replace("&uo=4", "").replace("?uo=4", "")
            for e in r.json().get("results", []) if e.get("kind") == "podcast-episode" and e.get("episodeGuid")}


def actualizar():
    """Rellena url_apple donde falte. Devuelve las fechas actualizadas. Nunca falla."""
    pendientes = [p for p in sorted(EPISODIOS.glob("*/publicacion.json"))
                  if "url_apple" not in json.loads(p.read_text(encoding="utf-8"))]
    if not pendientes:
        return []
    id_programa = id_apple(cargar_yaml("podcast.yaml"))
    if not id_programa:
        return []
    try:
        enlaces = episodios_de_apple(id_programa)
    except (requests.RequestException, ValueError) as e:
        print(f"  Aviso: no he podido consultar Apple Podcasts ({e}); sigo sin los enlaces de episodio.")
        return []
    hechas = []
    for ruta in pendientes:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        enlace = enlaces.get(f"catodo-{datos['fecha']}")
        if enlace:
            datos["url_apple"] = enlace
            ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            hechas.append(datos["fecha"])
    return hechas


if __name__ == "__main__":
    hechas = actualizar()
    print(f"Enlaces de Apple Podcasts nuevos: {', '.join(hechas) or 'ninguno'}")
