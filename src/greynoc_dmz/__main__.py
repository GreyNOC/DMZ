from __future__ import annotations

import sys

from greynoc_dmz.cli import app, launch_desktop


def main() -> None:
    if len(sys.argv) == 1:
        launch_desktop()
        return
    app()

if __name__ == "__main__":
    main()
