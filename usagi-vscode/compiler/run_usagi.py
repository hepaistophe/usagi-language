"""Stable entry point for the compiler bundled with this extension."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usagi.cli import main

raise SystemExit(main())
