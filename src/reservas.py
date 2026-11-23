"""Reservas de los medios frente a la lectura por IA (robots.txt y TDMRep).

Uso:
    python src/reservas.py            # revisa los dominios de todas las fuentes

Un artículo no se abre con IA (redacción y verificación) si:
  - su fuente está marcada con leer_con_ia: false en sources.yaml, o
  - el robots.txt de su dominio prohíbe esa URL a Claude-User o claude-code (o a todos,
    con *, si no tienen regla propia), o
  - su /.well-known/tdmrep.json reserva la minería de textos (tdm-reservation: 1).
Sigue contando para la regla de dos grupos y se enlaza en las notas.
Los resultados se guardan en cache/reservas_ia.json durante unos días.
"""

import json
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from comun import RAIZ, cargar_yaml

CACHE = RAIZ / "cache" / "reservas_ia.json"
DIAS_CACHE = 7
# Cada agente usa su propia regla del robots.txt y, si no la tiene, la de "*".
AGENTES = ["Claude-User", "claude-code"]
CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; catodo-feeds/0.1; +https://catodo.es)"}


def _dominio(url):
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _leer_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _guardar_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _robots(origen):
    """Devuelve un RobotFileParser, o None si no se puede leer el robots.txt."""
    try:
        r = requests.get(origen + "/robots.txt", headers=CABECERAS, timeout=15)
    except requests.RequestException:
        return None
    rp = RobotFileParser()
    if r.status_code == 404:
        rp.parse([])  # sin robots.txt: todo permitido
        return rp
    if r.status_code != 200:
        return None
    rp.parse(r.text.splitlines())
    return rp


def _tdm_reservado(origen, url):
    try:
        r = requests.get(origen + "/.well-known/tdmrep.json", headers=CABECERAS, timeout=15)
        if r.status_code != 200:
            return False
        reglas = r.json()
    except (requests.RequestException, ValueError):
        return False
    ruta = urlparse(url).path or "/"
    for regla in reglas if isinstance(reglas, list) else []:
        patron = str(regla.get("location", "/*")).rstrip("*")
        if ruta.startswith(patron or "/") and str(regla.get("tdm-reservation")) == "1":
            return True
    return False


def comprobar(url, cache):
    """Comprueba una URL y devuelve {'bloqueado': bool, 'motivo': str}. Usa y actualiza la caché."""
    dom = _dominio(url)
    entrada = cache.get(dom)
    if entrada and time.time() - entrada["t"] < DIAS_CACHE * 86400 and "robots" in entrada:
        robots_txt = entrada["robots"]
        tdm = entrada["tdm"]
    else:
        origen = f"{urlparse(url).scheme or 'https'}://{urlparse(url).netloc}"
        rp = _robots(origen)
        # Guardamos el robots.txt "resuelto" como reglas por agente para la ruta raíz y la del ejemplo.
        robots_txt = None if rp is None else {
            "ejemplo": url,
            "bloquea": [a for a in AGENTES if not rp.can_fetch(a, url)],
        }
        tdm = _tdm_reservado(origen, url)
        cache[dom] = {"t": time.time(), "robots": robots_txt, "tdm": tdm,
                      "comprobado": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    if robots_txt and robots_txt["bloquea"]:
        return {"bloqueado": True, "motivo": f"robots.txt bloquea a {', '.join(robots_txt['bloquea'])}"}
    if tdm:
        return {"bloqueado": True, "motivo": "TDMRep reserva la minería de textos"}
    return {"bloqueado": False, "motivo": "sin reservas detectadas" if robots_txt is not None
            else "no se pudo leer robots.txt"}


class Reservas:
    """Decide qué URL se pueden abrir con IA."""

    def __init__(self):
        config = cargar_yaml("sources.yaml")
        self.manual = {}
        for f in config["fuentes"]:
            if f.get("leer_con_ia") is False:
                for d in f.get("dominios", []):
                    self.manual[d] = f"{f['nombre']}: marcada a mano en sources.yaml"
        self.cache = _leer_cache()

    def motivo_bloqueo(self, url):
        """Devuelve el motivo si la URL no se debe abrir con IA, o None si se puede."""
        dom = _dominio(url)
        for d, motivo in self.manual.items():
            if dom == d or dom.endswith("." + d):
                return motivo
        if "news.google.com" in dom:
            return None  # redirección de Google News: el destino se comprueba al abrirlo
        resultado = comprobar(url, self.cache)
        return resultado["motivo"] if resultado["bloqueado"] else None

    def guardar(self):
        _guardar_cache(self.cache)


def main():
    config = cargar_yaml("sources.yaml")
    reservas = Reservas()
    print(f"{'Fuente':32} {'¿Leer con IA?':14} Motivo")
    for f in config["fuentes"]:
        if f.get("agregador") or not f.get("dominios"):
            continue
        url = f"https://{f['dominios'][0]}/"
        motivo = reservas.motivo_bloqueo(url)
        print(f"{f['nombre'][:31]:32} {'NO' if motivo else 'sí':14} {motivo or ''}")
    reservas.guardar()


if __name__ == "__main__":
    main()
