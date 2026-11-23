#!/usr/bin/env bash
# El `reply` de catodo.preparar en ops (ops#118): lo que corre cuando Ulises elige una
# opción en la decisión del episodio. «Aprobar y programar» es `make aprobar` más
# `make programar` sin push (lo empuja ops a la rama programado); «No publicar», nada.
source "$(dirname "$0")/lib.sh"
"$PY" src/ops.py responder
