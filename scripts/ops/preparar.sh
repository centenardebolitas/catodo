#!/usr/bin/env bash
# catodo.preparar en ops (ops#118, ops#122): de lunes a viernes a las 5:00, prepara el
# episodio del día (noticias, guion en cinco pasadas, voz y montaje) y lo publica solo:
# sube el MP3 a R2, regenera feed y web y deja el commit, que ops empuja a main
# (commandGitPush). Deja un aviso con el enlace y los puntos a comprobar. Todo en
# src/ops.py, que es quien lee el token de Claude (solo se puede leer una vez).
# Si falla, relanzarlo retoma desde el paso que falló (lo hecho se guarda en
# $CATODO_ESTADO, fuera del clon que ops limpia).
source "$(dirname "$0")/lib.sh"

FECHA="${CATODO_FECHA:-$(TZ=Europe/Madrid "$PY" -c 'from datetime import date; print(date.today())' 3<&-)}"
echo "== Episodio del $FECHA ($(date))"
exec "$PY" src/ops.py publicar --fecha "$FECHA"
