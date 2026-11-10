"""Keep automated GUI tests away from the user's recovery drafts."""
import pytest


@pytest.fixture(autouse=True)
def isolated_recovery_directory(monkeypatch, tmp_path):
    monkeypatch.setenv('MATRIX_DISPLACEMENT_RECOVERY_DIR', str(tmp_path / 'recovery'))
