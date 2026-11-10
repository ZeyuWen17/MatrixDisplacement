"""Qt-independent, auditable V1.1 crash recovery demonstration."""
from pathlib import Path
import json

from matrix_displacement.editor import ModelEditor
from matrix_displacement.history import EditHistory
from matrix_displacement.io import save_model_json, load_model_json, model_to_dict
from matrix_displacement.recovery import RecoveryStore


def run(output_dir=Path('artifacts_v11')):
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints=output_dir / 'recovery'

    editor=ModelEditor()
    editor.load_example('cantilever')
    saved_path=output_dir / 'original_model.json'
    save_model_json(editor.model, saved_path)
    original_bytes=saved_path.read_bytes()

    history=EditHistory(editor)
    history.execute(editor.add_node,8.0,1.0)
    assert history.is_dirty
    store=RecoveryStore(checkpoints)
    snapshot=store.checkpoint(editor.model, saved_path)

    # Simulate the process exiting without a manual save. A new session starts.
    recovered=RecoveryStore(checkpoints).read(snapshot)
    restored_editor=ModelEditor(recovered.model)
    restored_history=EditHistory(restored_editor)
    restored_history.mark_recovered_unsaved()
    assert restored_history.is_dirty
    assert model_to_dict(restored_editor.model)!=model_to_dict(load_model_json(saved_path))
    assert saved_path.read_bytes()==original_bytes

    # Only a *conscious explicit* save writes a restored model to disk.
    restored_path=output_dir / 'restored_model.json'
    save_model_json(restored_editor.model, restored_path)
    restored_history.mark_saved()
    assert not restored_history.is_dirty
    assert saved_path.read_bytes()==original_bytes

    lines=[
        'MatrixDisplacement V1.1 recovery walkthrough',
        f'Original model unchanged: {saved_path}',
        f'Crash snapshot (kept as demo): {snapshot}',
        f'Explicitly restored model: {restored_path}',
        f'Original nodes: {len(load_model_json(saved_path).nodes)}',
        f'Restored nodes: {len(load_model_json(restored_path).nodes)}',
    ]
    result=output_dir / 'recovery_demo.txt'
    result.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    return result


if __name__ == '__main__':
    run()
