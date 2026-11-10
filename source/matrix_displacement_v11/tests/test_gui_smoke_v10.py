"""Optional Windows/Qt offscreen smoke for v1.0 selection/annotations.

Run with: $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q tests/test_gui_smoke_v10.py
These tests are skipped here when PySide6 is unavailable. Real DPI/mouse tests remain manual.
"""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from matrix_displacement.gui.main import MainWindow, PIXELS_PER_METRE


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_box_selection_and_toggle(app):
    w=MainWindow()
    try:
        # Box covers the second node only (left-to-right window), not the beam.
        w._finish_box(QPointF(3.8*PIXELS_PER_METRE,15),
                      QPointF(4.2*PIXELS_PER_METRE,-15))
        assert ('node',2) in w.selection
        assert ('element',1) not in w.selection
        w.select_all()
        assert len(w.selection)==3
        w.clear_selection()
        assert w.selection==set()
    finally:
        w.unsaved=False;w.close()


def test_group_drag_and_single_undo(app):
    w=MainWindow()
    try:
        w.selection={('node',1),('node',2)}
        w.selected=('node',2)
        start=QPointF(4*PIXELS_PER_METRE,0)
        end=QPointF(5*PIXELS_PER_METRE,0)
        w._begin_drag(start)
        w._drag_update(end)
        w._end_drag(end)
        assert w.editor.model.nodes[1].x==1
        assert w.editor.model.nodes[2].x==5
        w.undo_model()
        assert w.editor.model.nodes[1].x==0
        assert w.editor.model.nodes[2].x==4
    finally:
        w.unsaved=False;w.close()


def test_version_and_auto_label_placement(app):
    w=MainWindow()
    try:
        assert 'V1.0' in w.windowTitle()
        w._redraw()
        assert len(w.canvas.canvas_scene.items())>0
    finally:
        w.unsaved=False;w.close()
