#!/bin/zsh
# Preparación nocturna de Cátodo (la lanza launchd a las 22:00, de domingo a jueves).
# Actualiza el repositorio, prepara el guion y el audio del episodio de mañana y avisa
# con una notificación. Deja el registro en logs/noche-AAAA-MM-DD.log.

set -uo pipefail
RAIZ="${0:A:h:h}"
cd "$RAIZ" || exit 1
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MANANA=$(date -v+1d +%Y-%m-%d)
mkdir -p logs
LOG="logs/noche-$MANANA.log"

avisar() {
  osascript -e "display notification \"$1\" with title \"Cátodo\" sound name \"Glass\"" 2>/dev/null || true
}

{
  echo "== Preparación del episodio del $MANANA ($(date))"
  git pull --ff-only &&
  make preparar FECHA="$MANANA" &&
  make audio FECHA="$MANANA"
} >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
  avisar "Guion y audio de mañana listos. Revisa episodes/$MANANA/revision.md y ejecuta make aprobar y make programar."
else
  avisar "La preparación de mañana ha fallado. Mira $LOG."
  exit 1
fi
