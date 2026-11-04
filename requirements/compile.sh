#!/bin/sh
# Regenerate the hash-locked requirement files from the *.in sources.
# Run on Linux with Python 3.12 (the production runtime) and pip-tools 7.6.2:
#   pip install pip-tools==7.6.2 && requirements/compile.sh
# Extra arguments go to pip-compile, e.g. --upgrade-package django.
# No lock is a -c constraint of another: Dependabot cannot update a package
# that such a lock pins. check_locks.py, run here and in CI, keeps one
# version per package across the locks instead.
set -eu
cd "$(dirname "$0")"
for name in production test development; do
    pip-compile --quiet --allow-unsafe --generate-hashes --strip-extras \
        --output-file="$name.txt" "$@" "$name.in"
done
python3 check_locks.py
