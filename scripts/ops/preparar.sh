#!/usr/bin/env bash
# catodo.preparar en ops (ops#118): lo que hacía `make noche` en el Mac. Prepara el
# episodio de mañana (noticias, guion en cinco pasadas, voz y montaje), sube el audio
# a una ruta de R2 no enlazada y deja la decisión que ops abre en el móvil. Todo en
# src/ops.py, que es quien lee el token de Claude (solo se puede leer una vez).
source "$(dirname "$0")/lib.sh"

FECHA="${CATODO_FECHA:-$("$PY" -c 'from datetime import date, timedelta; print(date.today() + timedelta(days=1))' 3<&-)}"
echo "== Preparación del episodio del $FECHA ($(date))"
exec "$PY" src/ops.py preparar --fecha "$FECHA"
