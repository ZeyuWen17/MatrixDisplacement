"""Crash-recovery checkpoints independent of Qt and the source JSON file.

Checkpoints live in an application-state directory, never overwrite the user's
model, and are written using same-directory temporary files + os.replace().
A checksum catches incomplete/accidental alterations; it is not an auth token.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from .io import model_from_dict, model_to_dict

RECOVERY_FORMAT = 1
MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024
_NAME = re.compile(r"^session-[0-9a-f]{32}\.json$")


def default_recovery_directory() -> Path:
    """Per-user application state; can be isolated for GUI tests via environment."""
    override = os.environ.get('MATRIX_DISPLACEMENT_RECOVERY_DIR')
    if override and Path(override).is_absolute():
        return Path(override)
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA')
        if base:
            return Path(base) / 'MatrixDisplacement' / 'recovery'
        return Path.home() / 'AppData' / 'Local' / 'MatrixDisplacement' / 'recovery'
    xdg = os.environ.get('XDG_STATE_HOME')
    root = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / '.local' / 'state'
    return root / 'matrix_displacement' / 'recovery'


def _canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _checksum(data: dict) -> str:
    return sha256(_canonical(data)).hexdigest()


@dataclass(frozen=True)
class RecoveryEntry:
    path: Path
    saved_at: str
    source_path: str | None
    model: object
    session_id: str


class RecoveryStore:
    """One writable session plus explicitly selectable older recovery entries."""

    def __init__(self, directory=None, session_id=None):
        self.directory = Path(directory) if directory is not None else default_recovery_directory()
        self.session_id = uuid.UUID(str(session_id)).hex if session_id is not None else uuid.uuid4().hex

    @property
    def current_path(self) -> Path:
        return self.directory / f'session-{self.session_id}.json'

    def checkpoint(self, model, source_path=None) -> Path:
        """Persist a snapshot atomically, without editing the source JSON file."""
        data = model_to_dict(model)
        source = str(Path(source_path).resolve()) if source_path is not None else None
        payload = {
            'recovery_format': RECOVERY_FORMAT,
            'session_id': self.session_id,
            'saved_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source_path': source,
            'model': data,
        }
        payload['sha256'] = _checksum(payload)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             indent=2, allow_nan=False).encode('utf-8') + b'\n'
        if len(encoded) > MAX_CHECKPOINT_BYTES:
            raise ValueError('恢复文件过大：超过 64 MiB 限制')
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp_path = None
        try:
            fd, tmp_name = tempfile.mkstemp(prefix='.recovery-', suffix='.tmp', dir=self.directory)
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_path, self.current_path)
            tmp_path = None
            return self.current_path
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    def _checked_path(self, path) -> Path:
        requested = Path(path).resolve()
        if not _NAME.fullmatch(requested.name) or requested.parent != self.directory.resolve():
            raise ValueError('仅允许读取恢复目录中的会话快照')
        return requested

    def read(self, path) -> RecoveryEntry:
        path = self._checked_path(path)
        with path.open('rb') as stream:
            raw = stream.read(MAX_CHECKPOINT_BYTES + 1)
        if len(raw) > MAX_CHECKPOINT_BYTES:
            raise ValueError('恢复文件超过 64 MiB 限制')
        try:
            record = json.loads(raw.decode('utf-8'),
                                parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('恢复文件不是有效的 UTF-8 JSON') from exc
        expected = {'recovery_format', 'session_id', 'saved_at', 'source_path', 'model', 'sha256'}
        if not isinstance(record, dict) or set(record) != expected:
            raise ValueError('恢复文件字段不匹配')
        if type(record['recovery_format']) is not int or record['recovery_format'] != RECOVERY_FORMAT:
            raise ValueError('不支持的恢复格式')
        if type(record['session_id']) is not str or not re.fullmatch('[0-9a-f]{32}', record['session_id']):
            raise ValueError('无效的恢复会话编号')
        if path.name != f"session-{record['session_id']}.json":
            raise ValueError('恢复会话编号与文件名不一致')
        if type(record['saved_at']) is not str:
            raise ValueError('缺少恢复时间')
        try:
            parsed = datetime.fromisoformat(record['saved_at'])
        except ValueError as exc:
            raise ValueError('恢复时间格式错误') from exc
        if parsed.tzinfo is None:
            raise ValueError('恢复时间缺少时区')
        if record['source_path'] is not None and type(record['source_path']) is not str:
            raise ValueError('原始模型路径必须是字符串或 null')
        digest = record.pop('sha256')
        if type(digest) is not str or not re.fullmatch('[a-f0-9]{64}', digest) or _checksum(record) != digest:
            raise ValueError('恢复文件校验失败，可能不完整或已改变')
        model = model_from_dict(record['model'])
        return RecoveryEntry(path, record['saved_at'], record['source_path'], model, record['session_id'])

    def scan(self):
        """Return (valid entries newest-first, invalid files with reasons).

        Invalid checkpoints are never silently deleted. The GUI can warn users.
        """
        if not self.directory.exists():
            return [], []
        valid, invalid = [], []
        for path in self.directory.glob('session-*.json'):
            if not path.is_file():
                continue
            try:
                valid.append(self.read(path))
            except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
                invalid.append((path, str(exc)))
        valid.sort(key=lambda item: (item.saved_at, item.session_id), reverse=True)
        return valid, invalid

    def clear_current(self):
        self.current_path.unlink(missing_ok=True)

    def clear_entry(self, path):
        self._checked_path(path).unlink(missing_ok=True)
