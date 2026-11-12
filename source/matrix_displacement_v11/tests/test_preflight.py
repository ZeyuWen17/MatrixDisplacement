from copy import deepcopy
import os
import pytest
from matrix_displacement.editor import ModelEditor
from matrix_displacement.core import Node,Frame2D,PointLoad2D
from matrix_displacement.preflight import check_model


def example():
    editor=ModelEditor();editor.load_example('cantilever')
    return editor.model


def test_valid_examples_and_no_mutation():
    for name in ('cantilever','continuous_beam','truss'):
        editor=ModelEditor();editor.load_example(name)
        before=deepcopy(editor.model)
        assert check_model(editor.model)==[]
        assert editor.model==before


def test_isolated_and_coincident_nodes_are_advice():
    model=example()
    model.nodes[9]=Node(9,0,0)
    issues=check_model(model)
    assert any('重合' in i.message and 9 in i.nodes for i in issues)
    assert any('未连接' in i.message and i.nodes==(9,) for i in issues)
    assert all(i.severity=='warning' for i in issues)


def test_independent_supported_groups_not_errors():
    model=example()
    model.nodes[3]=Node(3,10,0);model.nodes[4]=Node(4,14,0)
    model.elements[2]=Frame2D(2,3,4,1,1)
    for d in ('ux','uy','rz'):model.constraints[(3,d)]=0
    issues=check_model(model)
    assert len([i for i in issues if '独立结构组' in i.message])==2
    assert all(i.severity=='warning' for i in issues)


@pytest.mark.parametrize('mutation,fragment',[
    (lambda m:m.nodes.update({2:Node(2,0,0)}),'几何无效'),
    (lambda m:m.nodes.pop(2),'不存在的节点'),
    (lambda m:m.materials.clear(),'缺少材料'),
    (lambda m:m.loads.update({(99,'uy'):10}),'引用或数值无效'),
    (lambda m:m.loads.update({(2,'uy'):float('nan')}),'引用或数值无效'),
    (lambda m:m.member_loads.append(PointLoad2D(1,100,0,-1)),'荷载无效'),
])
def test_invalid_inputs_are_blocking(mutation,fragment):
    model=example();mutation(model)
    assert any(i.severity=='error' and fragment in i.message for i in check_model(model))


def test_truss_rotation_load_invalid():
    editor=ModelEditor();editor.load_example('truss')
    editor.model.loads[(1,'rz')]=5
    assert any('无效自由度' in i.message for i in check_model(editor.model))


def test_missing_support_is_advice():
    model=example();model.constraints.clear()
    assert any(i.severity=='warning' and '未设置任何约束' in i.message for i in check_model(model))


@pytest.fixture
def app():
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    application=QApplication.instance() or QApplication([])
    before=set(application.topLevelWidgets())
    yield application
    # Dispose test dialogs while Qt is alive, not during interpreter shutdown.
    for widget in set(application.topLevelWidgets())-before:
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


@pytest.mark.parametrize('active',[{'ux','uy','rz'},{'ux','uy'},{'uy','rz'}])
def test_support_presets_preview_and_cancel(app,active):
    from matrix_displacement.gui.main import SupportDialog
    original={(1,'uy'):-.002}
    dialog=SupportDialog(1,active,original)
    dialog.preset_buttons['固定'].click()
    assert {d for d,(box,_) in dialog.inputs.items() if box.isChecked()}==active
    assert dialog.inputs['uy'][1].text()=='-0.002'
    assert dialog.preview.symbol.prescribed
    assert '给定位移' in dialog.preview_text.text()
    if active=={'uy','rz'}:
        assert not dialog.preset_buttons['竖向可动'].isEnabled()
        assert dialog.preview.symbol.name=='梁固定支座'
    dialog.preset_buttons['水平可动'].click()
    assert len(dialog.preview.symbol.circles)==2
    dialog.inputs['uy'][1].setText('bad')
    assert dialog.preview.symbol is None
    dialog.reject()
    assert dialog.data is None and original=={(1,'uy'):-.002}


def test_support_custom_values_committed_only_on_accept(app):
    from matrix_displacement.gui.main import SupportDialog
    dialog=SupportDialog(1,{'ux','uy','rz'},{})
    dialog.preset_buttons['铰接'].click()
    dialog.inputs['uy'][1].setText('-0.01')
    dialog.accept()
    assert dialog.data=={'ux':0.,'uy':-.01}


def test_issue_selection_and_blocking_before_worker(app,monkeypatch):
    from matrix_displacement.gui import main as gui
    w=gui.MainWindow()
    try:
        w.editor.model.nodes[9]=Node(9,10,1)
        issues=check_model(w.editor.model)
        dialog=gui.ModelCheckDialog(issues,w,before_solve=True)
        row=next(i for i,x in enumerate(issues) if x.nodes==(9,))
        dialog.list.setCurrentRow(row)
        assert w.selection=={('node',9)}
        assert w.main_tabs.currentIndex()==0
        dialog.reject()
        w.editor.model.nodes[2]=Node(2,0,0)
        invalid=check_model(w.editor.model)
        geometry=next(i for i in invalid if '几何无效' in i.message)
        w._locate_issue(geometry)
        assert ('element',1) in w.selection
        assert w.editor.model.nodes[2].x==0
        monkeypatch.setattr(gui.ModelCheckDialog,'exec',lambda self:gui.QDialog.DialogCode.Accepted)
        w.start_solve()
        assert w._solve_thread is None and w.result is None
    finally:
        w.unsaved=False;w.close()


def test_warning_cancel_does_not_start_worker(app,monkeypatch):
    from matrix_displacement.gui import main as gui
    w=gui.MainWindow()
    try:
        w.editor.model.nodes[9]=Node(9,10,1)
        monkeypatch.setattr(gui.ModelCheckDialog,'exec',lambda self:gui.QDialog.DialogCode.Rejected)
        w.start_solve()
        assert w._solve_thread is None
    finally:
        w.unsaved=False;w.close()


def test_warning_continue_uses_real_worker(app,monkeypatch):
    import time
    from PySide6.QtTest import QTest
    from matrix_displacement.gui import main as gui
    w=gui.MainWindow()
    try:
        w.editor.model.nodes[9]=Node(9,10,1)
        for dof in ('ux','uy','rz'):w.editor.model.constraints[(9,dof)]=0
        monkeypatch.setattr(gui.ModelCheckDialog,'exec',lambda self:gui.QDialog.DialogCode.Accepted)
        errors=[];monkeypatch.setattr(w,'_error',errors.append)
        w.start_solve()
        assert w._solve_thread is not None
        deadline=time.monotonic()+10
        while w._solve_thread is not None and time.monotonic()<deadline:
            app.processEvents();QTest.qWait(10)
        assert w._solve_thread is None
        assert w.result is not None and not errors
        assert w.result.reaction(1,'uy')==pytest.approx(5500)
    finally:
        w.unsaved=False;w.close()
