#!/bin/sh -x
cd `dirname $0`

uv run -m PyInstaller --onefile --hidden-import="googleapiclient" src/module/main.py

TAR_FILES="meta.json ./dist/main"
FIRST_RUN=$(uv run python -c "import json; print(json.load(open('meta.json')).get('first_run', ''))" 2>/dev/null)
if [ -n "$FIRST_RUN" ] && [ -f "$FIRST_RUN" ]; then
    TAR_FILES="$TAR_FILES $FIRST_RUN"
fi
tar -czvf dist/archive.tar.gz $TAR_FILES
