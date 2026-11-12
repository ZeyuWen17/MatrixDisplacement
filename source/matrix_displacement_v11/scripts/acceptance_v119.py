"""Qt offscreen acceptance, heartbeat measurements and reviewable screenshots."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QTimer, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from matrix_displacement.gui.main import MainWindow
from matrix_displacement.gui.cases_dialog import CasesDialog
from matrix_displacement.load_cases import capture_case
from benchmark_models import grid


def run():
    root = Path(__file__).resolve().parents[1]
    output = root/'docs/assets/v119'
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font = Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        QFontDatabase.addApplicationFont(str(font)); app.setFont(QFont('Microsoft YaHei', 9))
    with tempfile.TemporaryDirectory(prefix='v119-acceptance-') as folder:
        os.environ['MATRIX_DISPLACEMENT_RECOVERY_DIR'] = folder
        w = MainWindow(); w.show(); app.processEvents()
        w.solve()
        w.result_tabs.setCurrentIndex(1); app.processEvents()
        w.grab().save(str(output/'result-table.png'))
        capture_case(w.editor.model, 'G 恒载')
        w.editor.model.loads = {(2, 'uy'): -2000}; w.editor.model.member_loads = []
        capture_case(w.editor.model, 'Q 活载')
        w.editor.model.load_combinations['基本组合'] = {'G 恒载': 1.2, 'Q 活载': 1.4}
        dialog = CasesDialog(w.editor.model)
        dialog.combinations.setCurrentText('基本组合'); dialog.show(); app.processEvents()
        dialog.grab().save(str(output/'load-combinations.png'))
        dialog.close(); dialog.deleteLater()
        w.editor.model = grid(15, 10)
        w.mode_combo.setCurrentIndex(w.mode_combo.findData('fast'))
        w.solve(); rows = []
        for mode in ('auto', 'all'):
            w.force_labels.setCurrentIndex(w.force_labels.findData(mode))
            w.result_tabs.setCurrentIndex(0)
            ticks = []; timer = QTimer(); timer.setInterval(10)
            timer.timeout.connect(lambda: ticks.append(time.perf_counter())); timer.start()
            start = time.perf_counter()
            w._start_plot_job(w._figure_steps('弯矩 M'), mode)
            while w._plot_job is not None:
                app.processEvents(); time.sleep(.001)
                if time.perf_counter()-start > 120: raise RuntimeError('Plot timed out')
            end = time.perf_counter(); timer.stop()
            points = [start]+ticks+[end]
            rows.append(dict(elements=310, mode=mode, effective_mode=w._label_mode(),
                             seconds=round(end-start,4), heartbeat_count=len(ticks),
                             max_event_gap_seconds=round(max(b-a for a,b in zip(points,points[1:])),4)))
            if mode=='auto':
                w.figures['弯矩 M'].savefig(output/'large-model-auto.png',dpi=100)
        (output/'performance.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps(rows,indent=2),flush=True)
        w.unsaved=False; w.close(); w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


if __name__ == '__main__': run()
