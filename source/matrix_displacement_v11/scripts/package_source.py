"""Create a source-only release ZIP, excluding environments and build caches."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from matrix_displacement import __version__

destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root.parent
destination.mkdir(parents=True, exist_ok=True)
archive = destination / f'MatrixDisplacement_V{__version__}_Full_Source.zip'
excluded = {'.venv', '__pycache__', '.pytest_cache', '.git', 'build', 'dist'}
with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in excluded for part in relative.parts):
            continue
        if relative.parts[0] == 'validation' and (len(relative.parts) > 1 and relative.parts[1] in {'mplconfig', 'pyinstaller-cache', 'recovery', 'logs'}):
            continue
        if path.suffix in {'.pyc', '.zip', '.spec'}:
            continue
        z.write(path, Path(f'matrix_displacement_v{__version__}') / relative)
with ZipFile(archive) as z:
    assert z.testzip() is None
print(archive)
