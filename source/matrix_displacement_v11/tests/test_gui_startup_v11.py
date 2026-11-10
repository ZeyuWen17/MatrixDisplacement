"""Launcher crash logging and Qt-independent startup checks."""
from matrix_displacement.gui.startup import create_error_logger


def test_rotating_log_is_written_to_configured_directory(tmp_path):
    logger,path=create_error_logger(tmp_path)
    logger.error('example failure (no model data)')
    assert path.exists()
    assert 'example failure' in path.read_text('utf-8')
    for handler in logger.handlers:
        handler.flush()


def test_gui_launcher_handles_missing_qt_without_crashing_python(monkeypatch, tmp_path):
    import matrix_displacement.gui.startup as startup
    monkeypatch.setattr(startup,'create_error_logger',lambda: (None,None))
    try:
        import PySide6
    except ImportError:
        assert startup.main(['gui_launcher','--self-test']) == 1
