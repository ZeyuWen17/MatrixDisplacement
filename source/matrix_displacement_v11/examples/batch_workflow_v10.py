"""V1.0 Qt-free end-to-end demonstration: batch edits, single-step undo,
JSON roundtrip, analysis, and a Chinese verification summary.

Run from project root: python -m examples.batch_workflow_v10
"""
from pathlib import Path
import numpy as np

from matrix_displacement.editor import ModelEditor
from matrix_displacement.history import EditHistory
from matrix_displacement.core import Mode
from matrix_displacement.io import load_model_json, model_to_dict


def main(directory=None):
    out = Path(directory) if directory else Path(__file__).resolve().parents[1] / 'outputs/examples/artifacts_v10'
    out.mkdir(parents=True, exist_ok=True)
    editor = ModelEditor()
    editor.load_example('cantilever')
    third = editor.add_node(6, 0)
    second_element = editor.add_element(2, third, 'Frame2D')
    history = EditHistory(editor)
    before = model_to_dict(editor.model)

    # Two modified nodes; one undo step.
    history.execute(editor.translate_nodes, [2, third], 0.5, 0.0)
    assert editor.model.nodes[2].x == 4.5
    assert editor.model.nodes[third].x == 6.5
    assert history.undo()
    assert model_to_dict(editor.model) == before
    assert history.redo()

    # Update both elements in one history step.
    history.execute(editor.set_elements_properties, [1, second_element], 200e9, 0.02, 9e-6)
    assert all(editor.model.materials[e.material_id].E == 200e9
               for e in editor.model.elements.values())

    # Delete one element and restore it using a single undo.
    history.execute(editor.remove_many, element_ids=[second_element])
    assert second_element not in editor.model.elements
    assert history.undo()
    assert second_element in editor.model.elements

    model_path = out / 'model_v10.json'
    editor.save(model_path)
    reloaded = ModelEditor(load_model_json(model_path))
    assert model_to_dict(reloaded.model) == model_to_dict(editor.model)

    fast = reloaded.solve(Mode.FAST)
    teaching = reloaded.solve(Mode.TEACHING)
    np.testing.assert_allclose(fast.displacements, teaching.displacements)
    np.testing.assert_allclose(fast.reactions, teaching.reactions)
    assert teaching.trace is not None

    content = [
        'MatrixDisplacement V1.0 端到端验证',
        '批量移动：通过；单步撤销/重做：通过',
        '杆件批量属性更新：通过；批量删除回滚：通过',
        'JSON 保存/读取：通过；教学/快速结果一致：通过',
        f'节点数：{len(reloaded.model.nodes)}',
        f'杆件数：{len(reloaded.model.elements)}',
        f'最大节点位移绝对值：{max(abs(v) for v in fast.displacements):.8g}',
        '注意：此示例没有运行或验证 Qt / Windows EXE。',
    ]
    report = out / 'batch_validation_v10.txt'
    report.write_text('\n'.join(content)+'\n', encoding='utf-8')
    print('\n'.join(content))
    return report


if __name__ == '__main__':
    main()
