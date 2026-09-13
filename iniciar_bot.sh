#!/usr/bin/env bash

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  PYTHON="$PROJECT_DIR/.venv/Scripts/python.exe"
fi

if [ ! -f "$PYTHON" ]; then
  PYTHON="$PROJECT_DIR/../.venv/bin/python"
fi

if [ ! -f "$PYTHON" ]; then
  PYTHON="$PROJECT_DIR/../.venv/Scripts/python.exe"
fi

SCRIPT="$PROJECT_DIR/main.py"

if [ ! -f "$PYTHON" ]; then
  echo "ERRO: ambiente virtual nao encontrado."
  echo "Esperado em: $PROJECT_DIR/.venv"
  exit 1
fi

if [ ! -f "$SCRIPT" ]; then
  echo "ERRO: main.py nao encontrado."
  exit 1
fi

cd "$PROJECT_DIR" || exit 1
echo "Iniciando o FuteBot..."
"$PYTHON" -u "$SCRIPT"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
  echo
  echo "O bot foi encerrado com erro. Codigo: $STATUS"
fi

exit "$STATUS"
