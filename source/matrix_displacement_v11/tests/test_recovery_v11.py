"""Recovery and atomic-source-saving regressions without Qt."""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from matrix_displacement.editor import ModelEditor
from matrix_displacement.history import EditHistory
from matrix_displacement.io import model_to_dict, load_model_json, save_model_json
from matrix_displacement.recovery import (
    RecoveryStore, RECOVERY_FORMAT, MAX_CHECKPOINT_BYTES,
    default_recovery_directory,
)


def model():
    e = ModelEditor()
    e.load_example('cantilever')
    return e.model


def test_autosave_roundtrip_without_overwriting_original(tmp_path):
    original = tmp_path / 'structure.json'
    m = model()
    save_model_json(m, original)
    previous = original.read_bytes()
    e = ModelEditor(m)
    e.add_node(7, 1)
    recovery = RecoveryStore(tmp_path / 'recovery')
    snapshot = recovery.checkpoint(e.model, original)
    assert original.read_bytes() == previous
    entry = recovery.read(snapshot)
    assert entry.source_path == str(original.resolve())
    assert entry.session_id == recovery.session_id
    assert model_to_dict(entry.model) == model_to_dict(e.model)
    assert entry.saved_at.endswith('+00:00')


def test_restored_draft_remains_dirty_until_explicit_save(tmp_path):
    e = ModelEditor(model())
    h = EditHistory(e)
    h.execute(e.add_node, 7, 0)
    recovery = RecoveryStore(tmp_path)
    entry = recovery.read(recovery.checkpoint(e.model))
    new_editor = ModelEditor(entry.model)
    new_history = EditHistory(new_editor)
    new_history.mark_recovered_unsaved()
    assert new_history.is_dirty
    new_history.execute(new_editor.add_node, 8, 0)
    assert new_history.is_dirty
    new_history.undo()
    assert new_history.is_dirty
    save_model_json(new_editor.model, tmp_path / 'save.json')
    new_history.mark_saved()
    assert not new_history.is_dirty


def test_multiple_recovery_sessions_do_not_clobber_each_other(tmp_path):
    a = RecoveryStore(tmp_path)
    b = RecoveryStore(tmp_path)
    assert a.current_path != b.current_path
    a.checkpoint(model())
    b.checkpoint(model())
    valid, invalid = a.scan()
    assert len(valid) == 2 and not invalid
    b.clear_current()
    assert a.current_path.exists()
    assert not b.current_path.exists()
    assert len(a.scan()[0]) == 1


def test_same_session_replaces_only_own_checkpoint(tmp_path):
    store = RecoveryStore(tmp_path)
    first = store.checkpoint(model())
    e = ModelEditor(model())
    e.add_node(7, 0)
    second = store.checkpoint(e.model)
    assert first == second
    assert len(list(tmp_path.glob('session-*.json'))) == 1
    assert len(store.read(second).model.nodes) == len(model().nodes) + 1


def test_corrupt_and_truncated_recovery_is_rejected_not_deleted(tmp_path):
    store = RecoveryStore(tmp_path)
    good = store.checkpoint(model())
    broken = RecoveryStore(tmp_path).current_path
    broken.write_bytes(b'{broken-json')
    valid, invalid = store.scan()
    assert len(valid) == 1 and valid[0].path == good
    assert len(invalid) == 1 and invalid[0][0] == broken
    assert broken.exists()


def test_tampered_digest_is_rejected(tmp_path):
    store = RecoveryStore(tmp_path)
    path = store.checkpoint(model())
    record = json.loads(path.read_text())
    record['model']['nodes'][0]['x'] += 1
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='校验失败'):
        store.read(path)


def test_recovery_rejects_foreign_path_and_invalid_filename(tmp_path):
    store = RecoveryStore(tmp_path / 'recover')
    good = store.checkpoint(model())
    with pytest.raises(ValueError):
        store.read(tmp_path / 'outside.json')
    with pytest.raises(ValueError):
        store.clear_entry(tmp_path / 'outside.json')
    invalid_name = store.directory / 'session-oops.json'
    invalid_name.write_text('{}')
    with pytest.raises(ValueError):
        store.read(invalid_name)
    assert good.exists()


def test_interrupted_autosave_does_not_destroy_previous_copy(tmp_path, monkeypatch):
    import matrix_displacement.recovery as recovery_module
    store = RecoveryStore(tmp_path)
    path = store.checkpoint(model())
    old = path.read_bytes()

    def error_replace(*_):
        raise OSError('power loss simulation')

    monkeypatch.setattr(recovery_module.os, 'replace', error_replace)
    with pytest.raises(OSError, match='power loss'):
        store.checkpoint(model())
    assert path.read_bytes() == old
    assert list(tmp_path.glob('.recovery-*.tmp')) == []


def test_interrupted_manual_save_preserves_existing_json(tmp_path, monkeypatch):
    import matrix_displacement.io as io_module
    path = tmp_path / 'my_model.json'
    save_model_json(model(), path)
    old = path.read_bytes()
    monkeypatch.setattr(io_module.os, 'replace', lambda *_: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError, match='disk failure'):
        save_model_json(model(), path)
    assert path.read_bytes() == old
    assert list(tmp_path.glob('.my_model.json.*.tmp')) == []


def test_recovery_file_max_size_checked(tmp_path, monkeypatch):
    import matrix_displacement.recovery as recovery_module
    store = RecoveryStore(tmp_path)
    path = store.checkpoint(model())
    monkeypatch.setattr(recovery_module, 'MAX_CHECKPOINT_BYTES', 12)
    with pytest.raises(ValueError, match='64 MiB'):
        store.read(path)


def test_bad_snapshot_schema_even_if_digest_recomputed(tmp_path):
    from matrix_displacement.recovery import _checksum
    store=RecoveryStore(tmp_path)
    path=store.checkpoint(model())
    data=json.loads(path.read_text())
    data['model']['schema_version']=999
    data['sha256']=_checksum({k:v for k,v in data.items() if k!='sha256'})
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Unsupported model schema'):
        store.read(path)


def test_checkpoint_path_and_session_id_are_validated(tmp_path):
    with pytest.raises(ValueError):
        RecoveryStore(tmp_path, session_id='bad')
    store=RecoveryStore(tmp_path, session_id=uuid4())
    path=store.checkpoint(model())
    assert store.read(path).session_id==store.session_id
    store.clear_current()
    store.clear_current()   # idempotent
    assert not path.exists()


def test_source_json_is_readable_after_atomic_save(tmp_path):
    path = tmp_path / 'model.json'
    m = model()
    save_model_json(m, path)
    assert model_to_dict(load_model_json(path)) == model_to_dict(m)
    save_model_json(m, path)
    assert model_to_dict(load_model_json(path)) == model_to_dict(m)


def test_default_location_respects_absolute_xdg_state_home(tmp_path, monkeypatch):
    import matrix_displacement.recovery as r
    if os.name == 'nt':
        pytest.skip('XDG is for non-Windows paths')
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    assert r.default_recovery_directory() == tmp_path / 'matrix_displacement' / 'recovery'
    monkeypatch.setenv('XDG_STATE_HOME', 'not/absolute')
    assert r.default_recovery_directory() != Path('not/absolute') / 'matrix_displacement' / 'recovery'
