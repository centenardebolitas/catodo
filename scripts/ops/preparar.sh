#!/usr/bin/env bash
# catodo.preparar en ops (ops#118): lo que hacía `make noche` en el Mac. Prepara el
# episodio de mañana (noticias, guion en cinco pasadas, voz y montaje), sube el audio
# a una ruta de R2 no enlazada y deja la decisión que ops abre en el móvil.
source "$(dirname "$0")/lib.sh"

FECHA="${CATODO_FECHA:-$("$PY" -c 'from datetime import date, timedelta; print(date.today() + timedelta(days=1))')}"
echo "== Preparación del episodio del $FECHA ($(date))"
"$PY" src/fetch.py --fecha "$FECHA"
"$PY" src/rank.py --fecha "$FECHA"
"$PY" src/script.py --fecha "$FECHA"
"$PY" src/tts.py --fecha "$FECHA"
"$PY" src/mix.py --fecha "$FECHA"
"$PY" src/ops.py decision --fecha "$FECHA"
