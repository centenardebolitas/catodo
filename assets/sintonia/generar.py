"""Genera candidatas de sintonía con Lyria 2 (Agent Platform de Google Cloud).

Uso:
    python assets/sintonia/generar.py [techno]

Cada estilo genera dos clips instrumentales de unos 30 segundos (WAV, 48 kHz).
Deja los clips y una página de escucha a ciegas en pruebas/salida/sintonias/.
Lyria 2 (lyria-002) es GA, instrumental y cuesta unos 0,06 dólares por clip.
"""

import base64
import json
import random
import string
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "pruebas"))
import tts  # noqa: E402  (credenciales de gcloud)
from comun import cargar_yaml  # noqa: E402
from prueba_voces import generar_html  # noqa: E402

SALIDA = RAIZ / "pruebas" / "salida" / "sintonias"
NEGATIVO = "vocals, singing, speech, heavy distortion, aggressive, dark, horror, dissonant"

ESTILOS = {
    "mañana-electrónica": "Upbeat, warm morning electronic jingle for a daily technology news podcast. Bright analog "
                          "synth arpeggio, soft plucks, light electronic drums, optimistic and friendly, clean modern "
                          "production, catchy short motif, 110 BPM",
    "synthwave-crt": "Retro-futuristic synthwave intro with a warm cathode-ray tube glow, vintage analog synthesizers, "
                     "gentle pulsing bass, curious and playful, catchy short melodic motif, 100 BPM",
    "electrones": "Minimal and elegant electronic theme: tiny digital blips and sparkling electric textures that "
                  "resolve into a warm major chord, like electrons flowing, fresh morning energy, 115 BPM",
    "café-digital": "Cheerful acoustic-electronic hybrid: light piano and marimba over a subtle synth bass and soft "
                    "beats, sunrise mood, warm, smart and friendly, coffee-shop morning feeling, 105 BPM",
}


TANDA_TECHNO = {
    "techno-minimal": "Minimal techno intro: tight four-on-the-floor kick, crisp closed hi-hats, deep sub bass pulse, "
                      "a single hypnotic synth stab, clean modern Berlin minimal techno production, 124 BPM, short and punchy",
    "tech-house": "Modern minimal tech house sting: clean punchy kick, rolling bassline, short filtered synth chord, "
                  "sleek and confident, contemporary polished production, 122 BPM",
    "logo-minimal": "Minimalist electronic theme: one pulsing analog bass note, glitchy micro clicks, precise digital "
                    "percussion, cool and modern, very sparse and elegant, 120 BPM",
    "zumbido-techno": "Futuristic minimal techno with an electric buzz texture, pulsing sidechained synth, subtle acid "
                      "line, clean kick, bright and forward-looking, 126 BPM",
    "lanzamiento": "Modern electronica intro: crisp minimal beat, short catchy synth motif, warm detuned pad swell, "
                   "bright and optimistic, tech keynote feel, 118 BPM",
    "groove-mañanero": "Minimal techno groove with a short arpeggiated synth loop and clean claps, energetic but "
                       "relaxed morning drive, sleek modern sound design, 125 BPM",
}


def main():
    cfg = cargar_yaml("settings.yaml")["tts"]
    proyecto = cfg["proyecto_gcp"]
    url = (f"https://aiplatform.googleapis.com/v1/projects/{proyecto}/locations/global"
           f"/publishers/google/models/lyria-002:predict")
    tanda = sys.argv[1] if len(sys.argv) > 1 else ""
    estilos = TANDA_TECHNO if tanda == "techno" else ESTILOS
    salida = SALIDA / tanda if tanda else SALIDA
    salida.mkdir(parents=True, exist_ok=True)
    clips = []
    for nombre, prompt in estilos.items():
        print(f"Generando «{nombre}»…", flush=True)
        r = requests.post(url, timeout=600,
                          headers={"Authorization": f"Bearer {tts._token_gcloud()}", "x-goog-user-project": proyecto},
                          json={"instances": [{"prompt": prompt, "negative_prompt": NEGATIVO}],
                                "parameters": {"sample_count": 1}})
        if r.status_code != 200:
            print(f"  fallo HTTP {r.status_code}: {r.text[:300]}")
            continue
        for n, pred in enumerate(r.json()["predictions"], 1):
            ruta = salida / f"{nombre}-{n}.wav"
            ruta.write_bytes(base64.b64decode(pred["bytesBase64Encoded"]))
            clips.append((ruta, f"{nombre} (versión {n})"))
            print(f"  {ruta.name}")
    random.shuffle(clips)
    resultados = []
    for letra, (ruta, descripcion) in zip(string.ascii_uppercase, clips):
        resultados.append({"letra": letra, "fichero": ruta.name, "descripcion": descripcion})
    (salida / "clave.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    generar_html(salida, resultados)
    print(f"Página de escucha: {salida / 'escucha.html'}")


if __name__ == "__main__":
    main()
