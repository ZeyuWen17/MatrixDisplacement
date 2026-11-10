import pytest
from test_save_conflicts_v112 import window
from matrix_displacement.file_revision import FileRevision


def fail(*args,**kwargs):
    raise PermissionError('injected permission failure')


def dirty(w):
    w.history.execute(w.editor.add_node,8,2)
    w._modified()
    w._autosave_if_dirty()


def test_committed_save_survives_draft_cleanup_failure(window,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    dirty(window)
    path=tmp_path/'new.json'
    with monkeypatch.context() as patch:
        patch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),'JSON'))
        patch.setattr(window.recovery,'clear_current',fail)
        assert window.save_model()
        assert path.exists() and window.file_path==path
        assert not window.unsaved and not window.history.is_dirty
        assert window.recovery.current_path.exists()
        assert '旧恢复草稿未能清理' in window.statusBar().currentMessage()
    assert window.save_model()
    assert not window.recovery.current_path.exists()


def test_committed_save_survives_digest_read_failure(window,tmp_path,monkeypatch):
    dirty(window)
    window.file_path=tmp_path/'saved.json'
    with monkeypatch.context() as patch:
        patch.setattr(FileRevision,'capture',fail)
        assert window.save_model()
        assert window.file_path.exists() and not window.unsaved
        assert window._source_revision.conflicts(window.file_path)
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda path:'cancel')
    assert not window.save_model()


def test_failed_write_keeps_dirty_state_and_draft(window,tmp_path,monkeypatch):
    dirty(window)
    window.file_path=tmp_path/'failed.json'
    errors=[]
    monkeypatch.setattr(window,'_error',errors.append)
    monkeypatch.setattr(window.editor,'save',fail)
    assert not window.save_model()
    assert errors and window.unsaved and window.history.is_dirty
    assert window.recovery.current_path.exists()
    assert not window.file_path.exists()
