#!/bin/sh
cd `dirname $0`

if ! command -v uv &>/dev/null; then
	echo 'uv not found, installing...'
	curl -LsSf https://astral.sh/uv/install.sh | sh
fi
