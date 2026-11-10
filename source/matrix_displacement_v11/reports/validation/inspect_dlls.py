import pefile
from pathlib import Path
root = Path('dist/MatrixDisplacement/_internal')
dlls = {p.name.lower(): p for p in root.rglob('*.dll')}
dlls.update({p.name.lower(): p for p in root.glob('*.dll')})
cache = {}
for p in list((root / 'PySide6').glob('*.dll')) + list((root / 'PySide6').glob('*.pyd')):
    pe = pefile.PE(str(p))
    for dep in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
        name = dep.dll.decode().lower()
        if name not in dlls:
            continue
        if name not in cache:
            obj = pefile.PE(str(dlls[name]))
            cache[name] = {s.name for s in obj.DIRECTORY_ENTRY_EXPORT.symbols}
        for symbol in dep.imports:
            if symbol.name and symbol.name not in cache[name]:
                print(p.name, name, symbol.name.decode())
