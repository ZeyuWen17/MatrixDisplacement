"""Optional offscreen Qt regression; execute on Windows with PySide6 installed."""
import os
from types import SimpleNamespace
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from matrix_displacement.gui.main import MainWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_pan_zoom_dimension_visibility_and_selection(app):
    window = MainWindow()
    try:
        assert window.show_dimensions is True
        assert window.canvas.pan_mode is False
        window._set_tool('pan')
        assert window.canvas.pan_mode is True
        window._set_tool('select')
        assert window.canvas.pan_mode is False
        old_zoom = window.canvas.transform().m11()
        window.canvas.zoom_by(1.25)
        assert window.canvas.transform().m11() == pytest.approx(old_zoom*1.25)
        window.dimensions_action.setChecked(False)
        window._toggle_dimensions()
        assert window.show_dimensions is False
        window.clear_selection()
        assert window.selected is None
    finally:
        window.unsaved=False
        window.close()


def test_pick_force_diagram_opens_member_inspector(app):
    window = MainWindow()
    try:
        window.solve()
        figure = window._ensure_figure('剪力 V')
        line = next(l for l in figure.axes[0].lines
                    if l.get_gid() == 'md-member:1:V')
        artist_index = min(range(len(line.get_xdata())),
                           key=lambda i: abs(window.editor.model.nodes[1].x - line.get_xdata()[i]))
        # Simulate a pick at an actual artist point (no mouse event automation required).
        pixel = line.axes.transData.transform((line.get_xdata()[artist_index],
                                               line.get_ydata()[artist_index]))
        event = SimpleNamespace(artist=line, ind=[artist_index],
                                mouseevent=SimpleNamespace(x=pixel[0], y=pixel[1]))
        window._on_diagram_pick(event)
        assert window.selected == ('element',1)
        assert window.result_tabs.tabText(window.result_tabs.currentIndex()) == '杆件截面查询'
        assert 'N(x)=' in window.inspect_text.toPlainText()
    finally:
        window.unsaved=False
        window.close()
