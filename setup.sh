#!/bin/sh
cd `dirname $0`

if ! command -v uv; then
	curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv sync
