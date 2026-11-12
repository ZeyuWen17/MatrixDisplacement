"""Actual Qt event-loop checks for deferred plots and worker lifecycle."""
import os
import time
from threading import Event

import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from matrix_displacement.gui import main as gui


def wait_until(app, predicate):
    deadline=time.monotonic()+10
    while not predicate() and time.monotonic()<deadline:
        app.processEvents()
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def window(monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=gui.MainWindow()
    errors=[]
    monkeypatch.setattr(w,'_error',errors.append)
    yield app,w,errors
    if w._solve_thread is not None:
        w.cancel_solve()
        wait_until(app,lambda:w._solve_thread is None)
    w.unsaved=False
    w.close()


def test_plots_are_lazy_cached_and_invalidate_on_mode_or_model(window,monkeypatch):
    app,w,errors=window
    calls=[]
    import matrix_displacement.visualization as viz
    original=viz.force_diagram_steps
    def plot(*args,**kwargs):
        calls.append((args[2],kwargs['value_mode']))
        return original(*args,**kwargs)
    monkeypatch.setattr(viz,'force_diagram_steps',plot)
    w.solve()
    assert w.result is not None and not calls
    assert all(not f.axes for f in w.figures.values())
    select=lambda title: w.result_tabs.setCurrentIndex(next(i for i in range(w.result_tabs.count()) if w.result_tabs.tabText(i)==title))
    select('弯矩 M')
    wait_until(app,lambda:w._plot_job is None)
    assert calls==[('M','all')]
    w.result_tabs.setCurrentIndex(0)
    select('弯矩 M')
    assert len(calls)==1
    w.force_labels.setCurrentIndex(w.force_labels.findData('none'))
    wait_until(app,lambda:w._plot_job is None)
    assert calls[-1]==('M','none') and len(calls)==2
    select('轴力 N')
    wait_until(app,lambda:w._plot_job is None)
    assert calls[-1]==('N','none') and len(calls)==3
    w.history.execute(w.editor.add_node,8,2)
    w._modified()
    assert not w.figures and w.result is None and not w._figure_modes
    assert not errors


@pytest.mark.parametrize('outcome',['success','cancel','stale','error'])
def test_worker_keeps_event_loop_alive_and_cleans_up(window,monkeypatch,outcome):
    app,w,errors=window
    entered,release=Event(),Event()
    original=gui.LinearStaticSolver.solve
    snapshots=[]
    def slow(solver,model):
        snapshots.append(model)
        entered.set()
        assert release.wait(5)
        if outcome=='error':
            raise ValueError('test worker failure')
        return original(solver,model)
    monkeypatch.setattr(gui.LinearStaticSolver,'solve',slow)
    try:
        w.start_solve()
        thread=w._solve_thread
        w.start_solve()
        assert w._solve_thread is thread  # no duplicate jobs
        wait_until(app,entered.is_set)
        ticks=[]
        QTimer.singleShot(0,lambda:ticks.append(1))
        wait_until(app,lambda:bool(ticks))
        assert not w.centralWidget().isEnabled()
        assert snapshots[0] is not w.editor.model
        if outcome=='cancel':
            w.cancel_solve()
            assert not w.close()  # never destroy a running QThread
        elif outcome=='stale':
            w.editor.add_node(8,2)
        release.set()
        wait_until(app,lambda:w._solve_thread is None)
        assert w.centralWidget().isEnabled() and w.menuBar().isEnabled()
        if outcome=='success':
            assert w.result.reaction(1,'uy')==pytest.approx(5500)
            assert not w._figure_modes
        else:
            assert w.result is None
        assert len(errors)==(1 if outcome=='error' else 0)
    finally:
        release.set()


def test_instability_highlights_problem_node(window):
    app,w,errors=window
    node=w.editor.add_node(8,2)
    w.solve()
    assert w.result is None and len(errors)==1
    assert ('node',node) in w.selection
    assert w.main_tabs.currentIndex()==0
