"""PyInstaller GUI launcher with local crash traceback logging."""
from matrix_displacement.gui.startup import main

if __name__ == '__main__':
    raise SystemExit(main())
