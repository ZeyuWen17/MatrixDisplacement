"""Optional V0.8 Qt offscreen tests, skipped when PySide6 is not installed.

Run in Windows PowerShell with Python from .venv (PySide6 installed):
  $env:QT_QPA_PLATFORM = 'offscreen'; python -m pytest -q tests/test_gui_smoke_v08.py
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
    app=QApplication.instance() or QApplication([])
    yield app


def test_v08_table_and_inspector(app):
    window=MainWindow()
    try:
        assert window.prop_table.rowCount()==1
        assert window.load_table.rowCount()==2
        window.solve()
        assert window.result_tabs.count()==8
        assert 'N(x)=' in window.inspect_text.toPlainText()
        assert window.inspect_element_box.count()==1
        window.inspect_x.setValue(1.7)
        assert 'x=1.7 m' in window.inspect_text.toPlainText()
    finally:
        window.unsaved=False
        window.close()


def test_v08_drag_move_and_undo(app):
    window=MainWindow()
    try:
        assert window.editor.model.nodes[2].x==4
        start=QPointF(4*PIXELS_PER_METRE,0)
        end=QPointF(5*PIXELS_PER_METRE,0)
        window._begin_drag(start)
        window._drag_update(end)
        window._end_drag(end)
        assert window.editor.model.nodes[2].x==5
        assert window.history.can_undo
        window.undo_model()
        assert window.editor.model.nodes[2].x==4
        window.redo_model()
        assert window.editor.model.nodes[2].x==5
    finally:
        window.unsaved=False
        window.close()


def test_v08_edit_member_load(app):
    window=MainWindow()
    try:
        window._load_row_clicked(0,0)
        assert window.selected_load_index==0
        assert window.selected==('element',1)
        # Test the actual model-backed operation without opening modal dialog.
        window._edit(window.editor.replace_member_load,0,'uniform',qy=-2500)
        window._modified()
        assert window.editor.model.member_loads[0].qy==-2500
        window.undo_model()
        assert window.editor.model.member_loads[0].qy==-1200
    finally:
        window.unsaved=False
        window.close()
