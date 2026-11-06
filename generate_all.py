#!/usr/bin/env python3
"""Run all section generators (builds, guides, tierlists).

index.html is maintained by hand and is not generated.

Usage (from repo root):
  python generate_all.py

Individual sections:
  python -m sitegen.generate_builds
  python -m sitegen.generate_guides
  python -m sitegen.generate_tierlists
"""


from __future__ import annotations

from sitegen.common import ensure_nojekyll
from sitegen.generate_builds import generate_all_builds
from sitegen.generate_guides import generate_all_guides
from sitegen.generate_tierlists import generate_all_tierlists


def main() -> None:
    ensure_nojekyll()
    generate_all_builds()
    generate_all_guides()
    generate_all_tierlists()


if __name__ == "__main__":
    main()
