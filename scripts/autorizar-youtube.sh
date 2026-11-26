#!/usr/bin/env bash
# Da permiso a Cátodo para subir vídeos al canal de YouTube (@catodo_es) y lo guarda en ops.
# Una vez, en el Mac (src/redes.py autorizar-youtube, catodo-proyecto.md › Redes).
#
#   scripts/autorizar-youtube.sh [client_secret_….json]
#
# Lee el JSON del cliente OAuth «catodo-youtube» del proyecto de Google Cloud catodo (por
# defecto, el client_secret_*.json más reciente de ~/Downloads), guarda su ID y su secreto en
# ops y abre el navegador para autorizar: hay que entrar con la cuenta de Google que
# administra el canal y elegir el canal **Cátodo**. El refresh token va directo a ops por
# tubería. Ningún secreto pasa por la pantalla ni por un fichero nuevo.
set -euo pipefail
cd "$(dirname "$0")/.."

JSON="${1:-$(ls -t "$HOME"/Downloads/client_secret_*.json 2>/dev/null | head -1)}"
[ -f "$JSON" ] || { echo "No encuentro el JSON del cliente OAuth (Descargar JSON en Google Cloud)." >&2; exit 1; }
campo() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["installed"][sys.argv[2]])' "$JSON" "$1"; }

campo client_id | ssh ops 'sudo ops-jobs secret set catodo-youtube-client-id'
campo client_secret | ssh ops 'sudo ops-jobs secret set catodo-youtube-client-secret'

echo "Se abre el navegador: entra con la cuenta del canal y elige «Cátodo»." >&2
YOUTUBE_CLIENT_ID="$(campo client_id)" YOUTUBE_CLIENT_SECRET="$(campo client_secret)" \
  .venv/bin/python src/redes.py autorizar-youtube | ssh ops 'sudo ops-jobs secret set catodo-youtube-refresh-token'

rm -f "$JSON"
echo "Hecho: cliente y permiso de YouTube guardados en ops; borrado $JSON." >&2
