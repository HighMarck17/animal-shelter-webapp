"""Fail when a package has different versions in two lock files.

The locks are compiled independently (none is a -c constraint of another,
so Dependabot can update them), yet production.txt and test.txt are
installed together and development.txt must match both.

Usage: python requirements/check_locks.py [LOCK ...]
"""

import re
import sys
from pathlib import Path

LOCKS = ("production.txt", "test.txt", "development.txt")
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")


def read_pins(path):
    """Return {normalized name: version} for the pins of a lock file."""
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line)
        if match:
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            pins[name] = match.group(2)
    return pins


def main(args):
    here = Path(__file__).resolve().parent
    paths = [Path(arg) for arg in args] or [here / lock for lock in LOCKS]
    versions = {}
    for path in paths:
        for name, version in read_pins(path).items():
            versions.setdefault(name, {})[path.name] = version

    shared = {name: locks for name, locks in versions.items() if len(locks) > 1}
    drifted = {
        name: locks for name, locks in shared.items() if len(set(locks.values())) > 1
    }
    for name, locks in sorted(drifted.items()):
        found = ", ".join(f"{lock} {version}" for lock, version in locks.items())
        print(f"{name}: {found}", file=sys.stderr)
    if drifted:
        print(
            "Regenerate with: requirements/compile.sh --upgrade-package <name>",
            file=sys.stderr,
        )
        return 1

    print(f"Lock files consistent: {len(shared)} packages shared")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
