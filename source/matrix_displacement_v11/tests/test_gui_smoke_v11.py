"""Optional Qt-only real widget smoke; do not count skip as acceptance."""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from matrix_displacement.gui.main import MainWindow
from matrix_displacement.recovery import RecoveryStore


@pytest.fixture
def app_and_recovery(monkeypatch, tmp_path):
    monkeypatch.setenv('MATRIX_DISPLACEMENT_RECOVERY_DIR', str(tmp_path))
    app=QApplication.instance() or QApplication([])
    yield app, tmp_path


def test_gui_autosave_manual_save_and_cleanup(app_and_recovery, tmp_path):
    app, folder = app_and_recovery
    w=MainWindow()
    try:
        w.history.execute(w.editor.add_node,8,2)
        w._modified()
        assert w.unsaved
        w._autosave_if_dirty()
        assert w.recovery.current_path.exists()
        assert len(RecoveryStore(folder).scan()[0]) == 1
        w.file_path=tmp_path / 'manual.json'
        assert w.save_model()
        assert not w.unsaved
        assert not w.recovery.current_path.exists()
    finally:
        w.unsaved=False
        w.close()


def test_gui_recovery_scan_and_restore_marked_dirty(app_and_recovery, tmp_path):
    app, folder=app_and_recovery
    from matrix_displacement.editor import ModelEditor
    previous = ModelEditor()
    previous.load_example('cantilever')
    previous.add_node(9,2)
    old=RecoveryStore(folder)
    path=old.checkpoint(previous.model)
    w=MainWindow()
    try:
        assert w._restore_entry(old.read(path))
        assert w.unsaved
        assert len(w.editor.model.nodes)==len(previous.model.nodes)
        assert w.history.is_dirty
        assert not path.exists()
        assert w.recovery.current_path.exists()
    finally:
        w.unsaved=False
        w.close()
