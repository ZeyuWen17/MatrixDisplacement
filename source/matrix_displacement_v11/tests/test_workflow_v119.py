import time
from copy import deepcopy
import numpy as np
import pytest
from matrix_displacement.units import parse_quantity
from matrix_displacement.editor import ModelEditor
from matrix_displacement.core import LinearStaticSolver, UniformLoad2D, LinearLoad2D, PointLoad2D
from matrix_displacement.io import model_to_dict, model_from_dict, save_model_json, load_model_json
from matrix_displacement.load_cases import capture_case, case_model, combination_model, apply_loads
from matrix_displacement.history import EditHistory


@pytest.mark.parametrize('text,unit,expected', [('210 GPa','Pa',210e9),('10 kN','N',1e4),
    ('-200 mm','m',-.2),('800 cm⁴','m4',8e-6),('10 mm²','m2',1e-5),
    ('2 kN/m','N/m',2000),('2 kN·mm','N*m',2),('180 deg','rad',np.pi),('1e3','N',1000)])
def test_units(text,unit,expected):
    assert parse_quantity(text,unit)==pytest.approx(expected)


@pytest.mark.parametrize('text,unit', [('2 mm','N'),('2 kN','m'),('nan','N'),('1e309 GPa','Pa'),
    ('__import__("os")','m'),('2 MPa','m2'),('1 kN',''),('3 N m extra','N*m')])
def test_invalid_units(text,unit):
    with pytest.raises(ValueError):parse_quantity(text,unit)


def model():
    editor=ModelEditor();editor.load_example('cantilever');return editor.model


def test_cases_combination_roundtrip_superposition_and_history(tmp_path):
    m=model();m.member_loads += [LinearLoad2D(1,qy_i=-100,qy_j=-400)]
    capture_case(m,'G')
    m.loads={(2,'uy'):-2000};m.member_loads=[]
    capture_case(m,'Q')
    m.load_combinations['ULS']={'G':1.2,'Q':1.4}
    solver=LinearStaticSolver()
    g=solver.solve(case_model(m,'G'));q=solver.solve(case_model(m,'Q'))
    c=combination_model(m,m.load_combinations['ULS']);r=solver.solve(c)
    np.testing.assert_allclose(r.displacements,1.2*g.displacements+1.4*q.displacements,atol=1e-12)
    np.testing.assert_allclose(r.reactions,1.2*g.reactions+1.4*q.reactions,atol=1e-8)
    for eid in c.elements:
        np.testing.assert_allclose(r.element_end_forces_local[eid],1.2*g.element_end_forces_local[eid]+1.4*q.element_end_forces_local[eid],atol=1e-8)
    save_model_json(m,tmp_path/'cases.json');restored=load_model_json(tmp_path/'cases.json')
    assert model_to_dict(restored)==model_to_dict(m)
    editor=ModelEditor(restored);history=EditHistory(editor)
    history.execute(apply_loads,editor.model,c)
    assert history.is_dirty
    history.undo();assert model_to_dict(editor.model)==model_to_dict(m)
    history.redo();assert editor.model.loads==c.loads


def test_combination_support_displacement_once_and_stale_case():
    m=model();capture_case(m,'G');m.constraints[(1,'uy')]=-.002
    c=combination_model(m,{'G':-2})
    assert c.constraints==m.constraints
    assert LinearStaticSolver().solve(c).displacement(1,'uy')==pytest.approx(-.002)
    before=model_to_dict(m)
    with pytest.raises(ValueError):combination_model(m,{'G':float('nan')})
    assert before==model_to_dict(m)
    del m.elements[1]
    with pytest.raises((ValueError,KeyError)):case_model(m,'G')


@pytest.fixture
def app(monkeypatch):
    pytest.importorskip('PySide6')
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    app=QApplication.instance() or QApplication([])
    before=set(app.topLevelWidgets())
    yield app
    for widget in set(app.topLevelWidgets())-before:
        if hasattr(widget,'_reset_results'):widget._reset_results();widget.unsaved=False
        widget.close();widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def wait(app,predicate):
    from PySide6.QtTest import QTest
    deadline=time.monotonic()+20
    while not predicate() and time.monotonic()<deadline:
        app.processEvents();QTest.qWait(5)
    assert predicate()


def test_numeric_table_sort_and_copy(app):
    from PySide6.QtCore import Qt
    from matrix_displacement.gui.result_table import ResultTable
    table=ResultTable(['编号','力 N'],[(2,-100.),(10,2.),(1,10.)])
    table.sortItems(0,Qt.SortOrder.AscendingOrder)
    assert [table.item(i,0).text() for i in range(3)]==['1','2','10']
    table.sortItems(1,Qt.SortOrder.AscendingOrder)
    table.selectAll();table.copy_selection()
    assert app.clipboard().text().splitlines()[1].split('\t')==['2','-100']


def test_dialog_units_and_case_cancel(app):
    from matrix_displacement.gui.main import NumericDialog,SupportDialog,MemberLoadDialog
    from matrix_displacement.gui.cases_dialog import CasesDialog
    d=NumericDialog('test',[('uy','Fy (N)',0)])
    d.inputs['uy'].setText('-2 kN');d.accept();assert d.data['uy']==-2000
    s=SupportDialog(1,{'uy'},{(1,'uy'):0})
    s.inputs['uy'][1].setText('-2 mm');s.accept();assert s.data['uy']==-.002
    l=MemberLoadDialog(1,4);l.stacks[0][1]['qy'].setText('-2 kN/m');l.accept();assert l.data['qy']==-2000
    m=model();before=model_to_dict(m);dialog=CasesDialog(m)
    dialog.name.setText('G');dialog.save_case();dialog.reject()
    assert before==model_to_dict(m)


def test_staged_plot_cancel_and_export_atomicity(app,monkeypatch,tmp_path):
    from matrix_displacement.gui.main import MainWindow,QFileDialog
    from PySide6.QtCore import QTimer
    w=MainWindow();errors=[];monkeypatch.setattr(w,'_error',errors.append);w.solve()
    w.force_labels.setCurrentIndex(w.force_labels.findData('none'))
    w._start_plot_job(w._figure_steps('弯矩 M'),'test')
    QTimer.singleShot(0,w.cancel_solve)
    wait(app,lambda:w._plot_job is None)
    assert '弯矩 M' not in w._figure_modes
    assert w.centralWidget().isEnabled()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    original=w.figures['轴力 N'].savefig
    def save_then_cancel(*args,**kwargs):
        original(*args,**kwargs);QTimer.singleShot(0,w.cancel_solve)
    monkeypatch.setattr(w.figures['轴力 N'],'savefig',save_then_cancel)
    w.start_export_all();wait(app,lambda:w._plot_job is None)
    files=list((tmp_path/'result_figures').iterdir())
    assert len(files)==1 and files[0].read_bytes().startswith(b'\x89PNG')
    monkeypatch.setattr(w.figures['轴力 N'],'savefig',original)
    w.start_export_all();wait(app,lambda:w._plot_job is None)
    assert len(list((tmp_path/'result_figures_001').glob('*.png')))==4
    assert files[0].is_file() and not errors
    # Failed save cannot damage an existing image, or leave temporary files.
    existing=tmp_path/'keep.png';existing.write_bytes(b'previous')
    def fail(*args,**kwargs):raise OSError('simulated write failure')
    monkeypatch.setattr(w.figures['轴力 N'],'savefig',fail)
    w._start_plot_job(w._export_steps([('轴力 N',existing)]),'failure')
    wait(app,lambda:w._plot_job is None)
    assert existing.read_bytes()==b'previous' and len(errors)==1
    assert not list(tmp_path.glob('.*.tmp'))


def test_large_model_auto_labels_and_event_loop(app,monkeypatch):
    from scripts.benchmark_models import grid
    from matrix_displacement.gui.main import MainWindow
    from PySide6.QtCore import QTimer
    w=MainWindow();w.editor.model=grid(10,5);w.mode_combo.setCurrentIndex(w.mode_combo.findData('fast'))
    w.solve();assert w._label_mode()=='none'
    ticks=[];timer=QTimer();timer.setInterval(1);timer.timeout.connect(lambda:ticks.append(1));timer.start()
    w._start_plot_job(w._figure_steps('弯矩 M'),'large')
    wait(app,lambda:w._plot_job is None);timer.stop()
    assert len(ticks)>2
    assert not any(t.get_text().startswith('E') for t in w.figures['弯矩 M'].axes[0].texts)
    assert any(line.get_gid()=='md-member:1:M' for line in w.figures['弯矩 M'].axes[0].lines)
    w.force_labels.setCurrentIndex(w.force_labels.findData('all'));assert w._label_mode()=='all'
