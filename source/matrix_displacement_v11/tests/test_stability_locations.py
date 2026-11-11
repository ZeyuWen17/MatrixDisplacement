import pytest
from matrix_displacement.core import LinearStaticSolver, Node, StabilityError
from matrix_displacement.editor import ModelEditor
from matrix_displacement.diagnostics import explain_error


def test_disconnected_node_reports_exact_dofs():
    editor=ModelEditor()
    editor.load_example('cantilever')
    editor.model.add_node(Node(99,8,2))
    with pytest.raises(StabilityError) as info:
        editor.solve()
    assert info.value.dofs==((99,'ux'),(99,'uy'),(99,'rz'))
    assert not info.value.suspected
    assert '节点 99 / uy' in explain_error(info.value).detail


def test_free_frame_reports_candidates_without_claiming_unique_cause():
    editor=ModelEditor()
    editor.load_example('cantilever')
    editor.model.constraints.clear()
    with pytest.raises(StabilityError) as info:
        LinearStaticSolver().solve(editor.model)
    assert info.value.suspected and info.value.dofs
    message=explain_error(info.value)
    assert message.title=='结构不稳定或约束不足'
    assert '不代表唯一故障原因' in message.detail
