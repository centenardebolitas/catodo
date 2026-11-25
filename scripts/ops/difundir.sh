#!/usr/bin/env bash
# catodo.difundir en ops: de lunes a viernes a media mañana, cuando el episodio del día ya
# está en catodo.es, lo publica en las redes activas (redes.activas de config/settings.yaml):
# Bluesky, Instagram, Facebook, Threads y YouTube (src/redes.py). Lo ya publicado se apunta
# en R2 (difusion/FECHA.json): si se repite, no publica dos veces. No hace commit.
source "$(dirname "$0")/lib.sh"
# Lo que tiene que durar entre ejecuciones (el token renovado de Threads), fuera del clon.
export CATODO_ESTADO="${CATODO_ESTADO:-$HOME/estado}"

FECHA="${CATODO_FECHA:-$(TZ=Europe/Madrid "$PY" -c 'from datetime import date; print(date.today())')}"
echo "== Difusión del episodio del $FECHA ($(date))"
exec "$PY" src/ops.py difundir --fecha "$FECHA"
