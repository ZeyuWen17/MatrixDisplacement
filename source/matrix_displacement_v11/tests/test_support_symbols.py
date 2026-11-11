import os
from itertools import combinations
import pytest
from matrix_displacement import StructuralModel,Node,Material,Section,Beam2D,Frame2D
from matrix_displacement.supports import support_symbol


def model_with_support(dofs):
    model=StructuralModel()
    model.add_node(Node(1,0,0))
    for dof in dofs:model.constrain(1,dof)
    return model


def test_all_seven_constraint_sets_have_distinct_symbols():
    symbols=[]
    for count in (1,2,3):
        for dofs in combinations(('ux','uy','rz'),count):
            model=model_with_support(dofs)
            symbol=support_symbol(model,1)
            symbols.append((symbol.lines,symbol.polygons,symbol.circles))
            assert all(d in symbol.detail for d in dofs)
    assert len(set(symbols))==7
    assert support_symbol(model_with_support(()),1) is None


def test_rollers_rotate_with_blocked_direction():
    vertical=support_symbol(model_with_support(('uy',)),1)
    horizontal=support_symbol(model_with_support(('ux',)),1)
    assert horizontal.circles==tuple((y,-x,r) for x,y,r in vertical.circles)
    assert '水平可动' in vertical.name and '竖向可动' in horizontal.name


@pytest.mark.parametrize('element_type,expected',[(Beam2D,'梁固定支座'),(Frame2D,'竖向与转角约束 · 水平可动')])
def test_beam_and_frame_uy_rz_are_not_confused(element_type,expected):
    model=model_with_support(('uy','rz'))
    model.add_node(Node(2,4,0))
    model.add_material(Material(1,2e11));model.add_section(Section(1,.01,8e-6))
    model.add_element(element_type(1,1,2,1,1))
    assert support_symbol(model,1).name==expected


def test_prescribed_values_visible_without_changing_model():
    model=model_with_support(('uy','rz'))
    model.constraints[(1,'uy')]=-.002
    model.constraints[(1,'rz')]=.001
    before=dict(model.constraints)
    symbol=support_symbol(model,1)
    assert symbol.prescribed
    assert 'uy=-0.002 m' in symbol.detail and 'rz=0.001 rad' in symbol.detail
    assert model.constraints==before


def test_qt_and_export_show_supports(tmp_path):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from matrix_displacement.gui.main import ModelCanvas
    from matrix_displacement.visualization import plot_structure
    import matplotlib.pyplot as plt
    app=QApplication.instance() or QApplication([])
    model=model_with_support(('ux',))
    model.constraints[(1,'ux')]=.003
    canvas=ModelCanvas()
    canvas.redraw(model)
    tips=[item.toolTip() for item in canvas.canvas_scene.items()]
    assert any('水平约束' in tip and 'ux=0.003 m' in tip for tip in tips)
    ax=plot_structure(model)
    try:
        assert any(item.get_gid()=='support:1' for item in ax.artists)
        assert any('ux=0.003 m' in text.get_text() for text in ax.texts)
        ax.figure.savefig(tmp_path/'supports.png',dpi=160)
        assert (tmp_path/'supports.png').stat().st_size>0
    finally:
        plt.close(ax.figure)
        canvas.close()
