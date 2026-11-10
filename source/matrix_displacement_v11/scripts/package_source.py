"""Create a source-only release ZIP, excluding environments and build caches."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys
import os

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from matrix_displacement import __version__

destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root.parent
destination.mkdir(parents=True, exist_ok=True)
archive = destination / f'MatrixDisplacement_V{__version__}_Full_Source.zip'
excluded = {'.venv', '__pycache__', '.pytest_cache', '.git', 'build', 'dist', 'outputs'}
with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
    for directory, dirs, files in os.walk(root):
        # Prune before traversal: never enter environments, build outputs or
        # test scratch directories (which may have restricted permissions).
        dirs[:]=sorted(d for d in dirs if d not in excluded)
        if Path(directory)==root/'reports'/'validation':
            dirs[:]=[]
        for name in sorted(files):
            path=Path(directory)/name
            if path.suffix in {'.pyc', '.zip', '.spec'}:
                continue
            z.write(path, Path(f'matrix_displacement_v{__version__}') / path.relative_to(root))
with ZipFile(archive) as z:
    assert z.testzip() is None
print(archive)
