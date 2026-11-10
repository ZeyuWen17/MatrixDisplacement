import pytest
from test_save_conflicts_v112 import window
from test_save_completion_v113 import dirty, fail


@pytest.mark.parametrize('operation',['new','example','open'])
def test_switch_with_locked_draft_completes_consistently(window,tmp_path,monkeypatch,operation):
    from PySide6.QtWidgets import QFileDialog
    path=tmp_path/'target.json'
    window.editor.save(path)
    dirty(window)
    old=window.recovery.current_path
    with monkeypatch.context() as patch:
        patch.setattr(window,'_maybe_save',lambda:True)
        patch.setattr(window.recovery,'clear_current',fail)
        patch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(path),'JSON'))
        if operation=='new': window.new_model()
        elif operation=='example': window.load_example('cantilever')
        else: window.open_model()
    assert old.exists()
    assert window.recovery.current_path!=old
    assert not window.unsaved and not window.history.is_dirty
    assert window.file_path==(path if operation=='open' else None)
    assert len(window.editor.model.nodes)==(0 if operation=='new' else 2)
    assert '未能清理' in window.statusBar().currentMessage()


def test_close_cleanup_failure_warns_and_accepts(window,monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox
    dirty(window)
    warnings=[]
    event=QCloseEvent()
    with monkeypatch.context() as patch:
        patch.setattr(window,'_maybe_save',lambda:True)
        patch.setattr(window.recovery,'clear_current',fail)
        patch.setattr(QMessageBox,'warning',lambda *a:warnings.append(a))
        window.closeEvent(event)
    assert event.isAccepted() and warnings
    assert window.recovery.current_path.exists()
    assert not window._autosave_periodic.isActive()


def test_cancel_close_keeps_autosave_and_draft(window,monkeypatch):
    from PySide6.QtGui import QCloseEvent
    dirty(window)
    event=QCloseEvent()
    with monkeypatch.context() as patch:
        patch.setattr(window,'_maybe_save',lambda:False)
        window.closeEvent(event)
    assert not event.isAccepted()
    assert window._autosave_periodic.isActive()
    assert window.recovery.current_path.exists()


def test_undo_to_clean_handles_cleanup_failure(window,monkeypatch):
    dirty(window)
    with monkeypatch.context() as patch:
        patch.setattr(window.recovery,'clear_current',fail)
        window.undo_model()
    assert not window.history.is_dirty and not window.unsaved
    assert window.recovery.current_path.exists()


def test_restore_success_even_if_old_draft_cannot_be_deleted(window,monkeypatch):
    from matrix_displacement.recovery import RecoveryStore
    store=RecoveryStore(window.recovery.directory)
    old=store.checkpoint(window.editor.model)
    with monkeypatch.context() as patch:
        patch.setattr(window.recovery,'clear_entry',fail)
        assert window._restore_entry(store.read(old))
    assert old.exists() and window.recovery.current_path.exists()
    assert window.unsaved and window.history.is_dirty
    assert '已恢复到内存' in window.statusBar().currentMessage()


def test_explicit_cleanup_failure_returns_false(window,monkeypatch):
    dirty(window)
    with monkeypatch.context() as patch:
        patch.setattr(window.recovery,'clear_entry',fail)
        assert not window._try_clear_recovery(window.recovery.current_path)
    assert window.recovery.current_path.exists()
