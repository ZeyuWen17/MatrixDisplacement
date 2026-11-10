"""Best-effort external modification detection; not a cross-process lock."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


def file_digest(path):
    try:
        with Path(path).open('rb') as stream:
            digest = sha256()
            for block in iter(lambda: stream.read(65536), b''):
                digest.update(block)
            return digest.hexdigest()
    except FileNotFoundError:
        return None


@dataclass(frozen=True)
class FileRevision:
    path: Path
    digest: str | None

    @classmethod
    def capture(cls, path):
        path = Path(path).resolve()
        return cls(path, file_digest(path))

    def conflicts(self, path):
        return Path(path).resolve() == self.path and file_digest(path) != self.digest
