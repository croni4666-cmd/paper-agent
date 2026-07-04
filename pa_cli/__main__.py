"""paper-agent CLI entry point — `python -m pa_cli <command>`."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())