#!/bin/sh
# Regenera todo el audio: efectos, voces y batería (make_sfx.py) y los
# módulos de música (make_music.py). Necesita un python3 con numpy y scipy;
# probamos varios porque env.sh pone primero el python de brew.
set -e
cd "$(dirname "$0")/.."
for PY in "${PYTHON_AUDIO:-}" python3 "$HOME/.pyenv/shims/python3" /usr/bin/python3; do
  [ -n "$PY" ] || continue
  if "$PY" -c "import numpy, scipy" 2>/dev/null; then break; fi
  PY=""
done
[ -n "$PY" ] || { echo "make_sfx.sh: falta un python3 con numpy y scipy (PYTHON_AUDIO=...)"; exit 1; }
"$PY" tools/make_sfx.py
"$PY" tools/make_music.py
echo "audio listo"
