# shellcheck shell=bash
# Común a los scripts de Cátodo en ops (trabajo catodo.preparar, ops#118). Se carga
# con `source`; no se ejecuta solo.
#
# Deja el clon como directorio de trabajo, el venv del trabajo en $PY (fuera del
# clon, en el HOME del trabajo: ops limpia el clon con git clean antes de cada
# preparación) y la hora de Madrid (el VPS va en UTC). Las claves de R2 y la de la
# cuenta de servicio de Google llegan del manifiesto de ops por el entorno; el token
# de Claude, por el descriptor 3 (OPS_CLAUDE_TOKEN_FD), que solo se puede leer una vez:
# lo lee src/ops.py. Lo de aquí corre con `3<&-`, para que no lo herede (pip, sobre
# todo, que ejecuta código de terceros al instalar).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export TZ=Europe/Madrid
export R2_BUCKET="${R2_BUCKET:-catodo-audio}"
export R2_PUBLIC_BASE_URL="${R2_PUBLIC_BASE_URL:-https://audio.catodo.es}"
export SITE_URL="${SITE_URL:-https://catodo.es}"
# El commit del episodio programado (lo empuja ops, no este script).
export GIT_AUTHOR_NAME="Cátodo (ops)" GIT_AUTHOR_EMAIL="catodo-bot@users.noreply.github.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

VENV="$HOME/venv"
req_hash=$(python3 -c 'import hashlib; print(hashlib.sha256(open("requirements.txt", "rb").read()).hexdigest()[:16])' 3<&-)
if [ ! -x "$VENV/bin/python" ] || [ "$(cat "$VENV/.requirements" 2>/dev/null)" != "$req_hash" ]; then
  echo "preparando el venv ($req_hash)" >&2
  rm -rf "$VENV"
  python3 -m venv "$VENV" 3<&-
  "$VENV/bin/pip" install --quiet --disable-pip-version-check -r requirements.txt >&2 3<&-
  echo "$req_hash" > "$VENV/.requirements"
fi
PY="$VENV/bin/python"
