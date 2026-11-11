"""Optional Qt-only real widget smoke; do not count skip as acceptance."""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from matrix_displacement.gui.main import MainWindow
from matrix_displacement.recovery import RecoveryStore


@pytest.fixture
def app_and_recovery(monkeypatch, tmp_path):
    monkeypatch.setenv('MATRIX_DISPLACEMENT_RECOVERY_DIR', str(tmp_path))
    app=QApplication.instance() or QApplication([])
    yield app, tmp_path


def test_all_figures_export_preserves_view_and_existing_files(app_and_recovery,tmp_path,monkeypatch):
    from matrix_displacement.gui import main as gui
    from PIL import Image
    monkeypatch.setattr(gui.QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    w=MainWindow()
    try:
        w.file_path=tmp_path/'刚架.json'
        w.solve()
        w.force_labels.setCurrentIndex(w.force_labels.findData('none'))
        w.result_tabs.setCurrentIndex(0)
        result=w.result
        w.export_all_figures()
        first=tmp_path/'刚架_result_figures'
        original={p.name:p.read_bytes() for p in first.iterdir()}
        assert len(original)==4
        for p in first.iterdir():
            with Image.open(p) as image:
                image.verify()
        w.export_all_figures()
        assert len(list((tmp_path/'刚架_result_figures_001').glob('*.png')))==4
        assert original=={p.name:p.read_bytes() for p in first.iterdir()}
        assert w.result is result
        assert w.result_tabs.currentIndex()==0
        assert w.force_labels.currentData()=='none'
        assert not any(t.get_text().startswith('E') for t in w.figures['弯矩 M'].axes[0].texts)
    finally:
        w.unsaved=False;w.close()


def test_all_figures_cancel_and_partial_failure(app_and_recovery,tmp_path,monkeypatch):
    from matrix_displacement.gui import main as gui
    w=MainWindow()
    try:
        w.solve()
        monkeypatch.setattr(gui.QFileDialog,'getExistingDirectory',lambda *a:'')
        w.export_all_figures()
        assert not (tmp_path/'result_figures').exists()
        monkeypatch.setattr(gui.QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
        def fail(*args,**kwargs):raise OSError('disk full')
        monkeypatch.setattr(w.figures['剪力 V'],'savefig',fail)
        errors=[]
        monkeypatch.setattr(w,'_error',errors.append)
        w.export_all_figures()
        assert len(errors)==1
        assert '未完成（1/4）' in w.statusBar().currentMessage()
        assert (tmp_path/'result_figures'/'轴力 N.png').is_file()
        assert w._export_directory is None
    finally:
        w.unsaved=False;w.close()


def test_export_directory_shared_only_after_success(app_and_recovery,tmp_path,monkeypatch):
    from pathlib import Path
    from matrix_displacement.gui import main as gui
    model_dir=tmp_path/'models'
    output_dir=tmp_path/'exports'
    model_dir.mkdir();output_dir.mkdir()
    w=MainWindow()
    try:
        w.file_path=model_dir/'中文模型.json'
        w.solve()
        defaults=[]
        def save_dialog(*args):
            defaults.append(Path(args[2]))
            return str(output_dir/'report.md'),'Markdown'
        monkeypatch.setattr(gui.QFileDialog,'getSaveFileName',save_dialog)
        w.export_report()
        assert defaults[0]==model_dir/'中文模型_teaching_report.md'
        assert (output_dir/'report.md').is_file()
        assert w._export_start_directory()==output_dir
        seen=[]
        def cancel_directory(*args):
            seen.append(Path(args[2]));return ''
        monkeypatch.setattr(gui.QFileDialog,'getExistingDirectory',cancel_directory)
        w.export_csv()
        assert seen==[output_dir]
        assert w._export_directory==output_dir
        for i in range(w.result_tabs.count()):
            if w.result_tabs.tabText(i)=='弯矩 M':w.result_tabs.setCurrentIndex(i)
        def image_dialog(*args):
            defaults.append(Path(args[2]))
            return str(output_dir/'moment.png'),'PNG'
        monkeypatch.setattr(gui.QFileDialog,'getSaveFileName',image_dialog)
        w.export_figure()
        assert defaults[-1]==output_dir/'中文模型_弯矩 M.png'
        assert (output_dir/'moment.png').stat().st_size>0
        def fail(*args):raise OSError('denied')
        monkeypatch.setattr(gui,'save_teaching_report',fail)
        monkeypatch.setattr(w,'_error',lambda exc:None)
        monkeypatch.setattr(gui.QFileDialog,'getSaveFileName',lambda *a:(str(model_dir/'failed.md'),''))
        w.export_report()
        assert w._export_directory==output_dir
        w._export_directory=tmp_path/'missing'
        assert w._export_start_directory()==model_dir
    finally:
        w.unsaved=False;w.close()


def test_csv_repeat_export_preserves_previous_results(app_and_recovery, tmp_path, monkeypatch):
    from matrix_displacement.gui import main as gui
    monkeypatch.setattr(gui.QFileDialog,'getExistingDirectory',lambda *a: str(tmp_path))
    w=MainWindow()
    try:
        w.solve()
        w.export_csv()
        first=tmp_path/'csv_results'
        original={p.name:p.read_bytes() for p in first.iterdir()}
        # A file can also occupy a candidate name.
        (tmp_path/'csv_results_001').write_text('keep')
        w.export_csv()
        second=tmp_path/'csv_results_002'
        assert {p.name:p.read_bytes() for p in second.iterdir()}==original
        assert {p.name:p.read_bytes() for p in first.iterdir()}==original
        assert (tmp_path/'csv_results_001').read_text()=='keep'
        assert str(second) in w.statusBar().currentMessage()
    finally:
        w.unsaved=False
        w.close()


def test_csv_partial_failure_identifies_incomplete_directory(app_and_recovery,tmp_path,monkeypatch):
    from matrix_displacement.gui import main as gui
    monkeypatch.setattr(gui.QFileDialog,'getExistingDirectory',lambda *a: str(tmp_path))
    def fail(model,result,directory,**kwargs):
        (directory/'nodal_results.csv').write_text('partial')
        raise OSError('disk full')
    monkeypatch.setattr(gui,'export_results_csv',fail)
    w=MainWindow()
    try:
        w.solve()
        errors=[]
        monkeypatch.setattr(w,'_error',errors.append)
        w.export_csv()
        assert len(errors)==1
        assert '未完成' in w.statusBar().currentMessage()
        assert str(tmp_path/'csv_results') in w.statusBar().currentMessage()
    finally:
        w.unsaved=False
        w.close()


@pytest.mark.parametrize('example', ['continuous_beam', 'truss'])
def test_force_label_modes_preserve_solution_and_export(app_and_recovery, tmp_path, example):
    w=MainWindow()
    try:
        w.editor.load_example(example)
        w.solve()
        result=w.result
        assert result is not None
        for mode in ('none','extrema','all'):
            w.force_labels.setCurrentIndex(w.force_labels.findData(mode))
            assert w.result is result
            for title in ('轴力 N','剪力 V','弯矩 M'):
                fig=w._ensure_figure(title)
                labels=[t for t in fig.axes[0].texts if t.get_text().startswith('E')]
                assert bool(labels)==(mode!='none')
                if mode=='extrema':
                    assert len(labels)<=2*len(w.editor.model.elements)
                fig.savefig(tmp_path / f'{example}_{mode}_{title}.png')
    finally:
        w.unsaved=False
        w.close()


def test_gui_autosave_manual_save_and_cleanup(app_and_recovery, tmp_path):
    app, folder = app_and_recovery
    w=MainWindow()
    try:
        w.history.execute(w.editor.add_node,8,2)
        w._modified()
        assert w.unsaved
        w._autosave_if_dirty()
        assert w.recovery.current_path.exists()
        assert len(RecoveryStore(folder).scan()[0]) == 1
        w.file_path=tmp_path / 'manual.json'
        assert w.save_model()
        assert not w.unsaved
        assert not w.recovery.current_path.exists()
    finally:
        w.unsaved=False
        w.close()


def test_gui_recovery_scan_and_restore_marked_dirty(app_and_recovery, tmp_path):
    app, folder=app_and_recovery
    from matrix_displacement.editor import ModelEditor
    previous = ModelEditor()
    previous.load_example('cantilever')
    previous.add_node(9,2)
    old=RecoveryStore(folder)
    path=old.checkpoint(previous.model)
    w=MainWindow()
    try:
        assert w._restore_entry(old.read(path))
        assert w.unsaved
        assert len(w.editor.model.nodes)==len(previous.model.nodes)
        assert w.history.is_dirty
        assert not path.exists()
        assert w.recovery.current_path.exists()
    finally:
        w.unsaved=False
        w.close()
