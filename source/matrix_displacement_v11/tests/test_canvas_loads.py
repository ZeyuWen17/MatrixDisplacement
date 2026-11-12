import pytest
from matrix_displacement.core import StructuralModel,Node,Material,Section,Frame2D,UniformLoad2D,LinearLoad2D,PointLoad2D


@pytest.mark.parametrize('load,arrows,tip',[
    (PointLoad2D(1,2,fy=-1000),1,(0,-130)),
    (PointLoad2D(1,2,fy=-1000,system='global'),1,(0,-130)),
    (UniformLoad2D(1,qy=-1000),9,None),
    (LinearLoad2D(1,qy_i=0,qy_j=-1000),8,None),
    (LinearLoad2D(1,qy_i=1000,qy_j=-1000),8,None),
])
def test_canvas_member_load_positions_and_directions(load,arrows,tip,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication,QGraphicsLineItem
    from PySide6.QtCore import QCoreApplication,QEvent
    from matrix_displacement.gui.main import ModelCanvas
    app=QApplication.instance() or QApplication([])
    m=StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,0,4))
    m.add_material(Material(1,210e9));m.add_section(Section(1,.01,8e-6))
    m.add_element(Frame2D(1,1,2,1,1));m.add_member_load(load)
    canvas=ModelCanvas()
    try:
        canvas.redraw(m)
        scene=canvas.canvas_scene
        lines=[i for i in scene.items() if isinstance(i,QGraphicsLineItem) and i.data(0)=='member-load']
        assert len(lines)==arrows
        assert any('E1 · 荷载1' in i.toPlainText() for i in scene.items() if hasattr(i,'toPlainText'))
        assert scene.sceneRect().contains(scene.itemsBoundingRect())
        assert canvas.sceneRect()==scene.sceneRect()
        if tip:
            line=lines[0].line()
            assert (line.x2(),line.y2())==pytest.approx(tip)
            if load.system=='local':assert line.x2()>line.x1()  # local -y points right on vertical member
            else:assert line.y2()>line.y1()  # global -Y points down on screen
        canvas.redraw(m)
        assert len([i for i in scene.items() if i.data(0)=='member-load'])==2*arrows
    finally:
        canvas.close();canvas.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
