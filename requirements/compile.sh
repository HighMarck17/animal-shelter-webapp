#!/bin/sh
# Regenerate the hash-locked requirement files from the *.in sources.
# Run with Python 3.12 (the production runtime) and pip-tools 7.6.2:
#   pip install pip-tools==7.6.2 && requirements/compile.sh
# Extra arguments go to pip-compile, e.g. --upgrade-package django.
# Order matters: test and development are constrained by production.txt.
set -eu
cd "$(dirname "$0")"
for name in production test development; do
    pip-compile --quiet --allow-unsafe --generate-hashes --strip-extras \
        --output-file="$name.txt" "$@" "$name.in"
done
