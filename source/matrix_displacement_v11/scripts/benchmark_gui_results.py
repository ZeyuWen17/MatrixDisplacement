"""Measure deferred result preparation and repeated plotting in a real Qt canvas."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import json
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from benchmark_models import grid
from matrix_displacement.gui.main import MainWindow
from matrix_displacement.core import Mode
from tempfile import TemporaryDirectory


def main():
    app=QApplication.instance() or QApplication([])
    measurements=[]
    with TemporaryDirectory(prefix='matrix-benchmark-') as folder:
        os.environ['MATRIX_DISPLACEMENT_RECOVERY_DIR']=folder
        for bays,stories in ((5,5),(15,10)):
            w=MainWindow()
            w.editor.model=grid(bays,stories)
            w.mode_combo.setCurrentIndex(w.mode_combo.findData(Mode.FAST.value))
            try:
                start=time.perf_counter()
                w.solve()
                preparation=time.perf_counter()-start
                assert w.result is not None
                assert not any(f.axes for f in w.figures.values())
                start=time.perf_counter()
                figure=w._ensure_figure('弯矩 M')
                figure.canvas.draw()
                first=time.perf_counter()-start
                repeats=[]
                for _ in range(3):
                    start=time.perf_counter()
                    w._ensure_figure('弯矩 M').canvas.draw()
                    repeats.append(time.perf_counter()-start)
                row=dict(elements=len(w.editor.model.elements),mode='all',
                         solve_and_summary_s=round(preparation,4),
                         first_moment_plot_s=round(first,4),
                         cached_redraw_s=[round(x,4) for x in repeats])
                measurements.append(row)
                print(json.dumps(row),flush=True)
            finally:
                w.unsaved=False
                w.close()
                w.deleteLater()
                app.processEvents()
    destination=Path('reports/validation/gui-performance-v117.json')
    destination.write_text(json.dumps(measurements,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
