"""Optional Qt offscreen smoke tests; run after installing requirements-gui.txt."""
import os
import pytest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from matrix_displacement.gui.main import MainWindow, PIXELS_PER_METRE


@pytest.fixture(scope='module')
def app():
    a=QApplication.instance()
    if a is None:a=QApplication([])
    return a


def test_main_window_solve_and_plots(app):
    window=MainWindow()
    assert len(window.editor.model.elements)==1
    window.solve()
    assert window.result is not None
    assert window.result_tabs.count()==8
    assert len(window.figures)==4
    window.close()


def test_mouse_add_node_and_element(app):
    window=MainWindow()
    window.new_model()  # no save dialog required on initial clean state
    window._set_tool('node')
    window._canvas_click(QPointF(0,0))
    window._canvas_click(QPointF(2*PIXELS_PER_METRE,0))
    assert len(window.editor.model.nodes)==2
    window._set_tool('element')
    window._canvas_click(QPointF(0,0))
    window._canvas_click(QPointF(2*PIXELS_PER_METRE,0))
    assert len(window.editor.model.elements)==1
    # programmatic cleanup avoids unsaved close dialog.
    window.unsaved=False
    window.close()
