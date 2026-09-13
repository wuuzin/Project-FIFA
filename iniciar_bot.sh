#!/usr/bin/env bash

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$PROJECT_DIR/main.py"
PYTHON=""

for CANDIDATE in \
  "$PROJECT_DIR/.venv/bin/python" \
  "$PROJECT_DIR/../.venv/bin/python"
do
  if [ -x "$CANDIDATE" ]; then
    PYTHON="$CANDIDATE"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "ERRO: ambiente virtual Linux nao encontrado."
  echo "Crie um ambiente em:"
  echo "  $PROJECT_DIR/.venv"
  echo "ou:"
  echo "  $PROJECT_DIR/../.venv"
  echo "Depois instale as dependencias com: python3 -m pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "$SCRIPT" ]; then
  echo "ERRO: main.py nao encontrado em $PROJECT_DIR."
  exit 1
fi

cd "$PROJECT_DIR" || exit 1
echo "Iniciando o FuteBot com $PYTHON..."
"$PYTHON" -u "$SCRIPT"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
  echo
  echo "O bot foi encerrado com erro. Codigo: $STATUS"
fi

exit "$STATUS"
