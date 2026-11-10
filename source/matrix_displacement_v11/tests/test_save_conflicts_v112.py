import os
import pytest
from matrix_displacement.file_revision import FileRevision


def test_changed_content_with_same_size_and_timestamp(tmp_path):
    path=tmp_path/'model.json'
    path.write_bytes(b'first')
    revision=FileRevision.capture(path)
    stamp=path.stat()
    path.write_bytes(b'other')
    os.utime(path, ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    assert revision.conflicts(path)
    path.write_bytes(b'first')
    assert not revision.conflicts(path)
    path.unlink()
    assert revision.conflicts(path)
    assert not revision.conflicts(tmp_path/'another.json')


@pytest.fixture
def window(monkeypatch):
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from matrix_displacement.gui.main import MainWindow
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    def fail_on_error(exc):
        raise AssertionError(f'Unexpected GUI error: {exc}') from exc
    monkeypatch.setattr(w,'_error',fail_on_error)
    yield w
    w.unsaved=False
    w.close()


def saved_and_changed(w,path):
    w.file_path=path
    assert w.save_model()
    w.history.execute(w.editor.add_node,8,2)
    w._modified()
    w._autosave_if_dirty()
    path.write_bytes(b'external edit')


def test_cancel_keeps_external_file_and_unsaved_draft(window,tmp_path,monkeypatch):
    path=tmp_path/'original.json'
    saved_and_changed(window,path)
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda p:'cancel')
    assert not window.save_model()
    assert path.read_bytes()==b'external edit'
    assert window.unsaved and window.history.is_dirty
    assert window.recovery.current_path.exists()


def test_save_as_preserves_both_versions(window,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path=tmp_path/'original.json'
    target=tmp_path/'copy.json'
    saved_and_changed(window,path)
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda p:'save_as')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(target),'JSON'))
    assert window.save_model()
    assert path.read_bytes()==b'external edit'
    assert target.exists() and window.file_path==target
    assert not window.unsaved


def test_explicit_overwrite_refreshes_baseline(window,tmp_path,monkeypatch):
    path=tmp_path/'original.json'
    saved_and_changed(window,path)
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda p:'overwrite')
    assert window.save_model()
    assert not window._source_revision.conflicts(path)
    assert not window.recovery.current_path.exists()


def test_save_as_same_source_cannot_bypass_conflict(window,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path=tmp_path/'original.json'
    saved_and_changed(window,path)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),'JSON'))
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda p:'cancel')
    assert not window.save_model(save_as=True)
    assert path.read_bytes()==b'external edit'


def test_opened_file_and_new_document_baselines(window,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path=tmp_path/'original.json'
    window.editor.save(path)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(path),'JSON'))
    window.open_model()
    assert window._source_revision.path==path.resolve()
    path.unlink()
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda p:'cancel')
    assert not window.save_model()
    window.new_model()
    assert window._source_revision is None


def test_restored_draft_does_not_trust_current_source(window,tmp_path,monkeypatch):
    from matrix_displacement.recovery import RecoveryStore
    path=tmp_path/'original.json'
    window.editor.save(path)
    store=RecoveryStore(window.recovery.directory)
    draft=store.checkpoint(window.editor.model,path)
    assert window._restore_entry(store.read(draft))
    monkeypatch.setattr(window,'_resolve_save_conflict',lambda p:'cancel')
    assert not window.save_model()
    assert window.unsaved
