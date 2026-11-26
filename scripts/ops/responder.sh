#!/usr/bin/env bash
# El `reply` de catodo.preparar en ops (ops#118): lo que corre cuando Ulises elige una
# opción en el aviso del episodio. «Difundir en redes» lo publica en las redes activas
# (src/redes.py); «No difundir» (o «Visto»), nada. Del flujo anterior: «Aprobar y
# programar» es `make aprobar` más `make programar` sin push; «No publicar», nada.
source "$(dirname "$0")/lib.sh"
"$PY" src/ops.py responder
