"""GUI launcher and bounded crash diagnostics; safe to import without Qt."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from matrix_displacement.recovery import default_recovery_directory


def create_error_logger(directory=None):
    """Log tracebacks to user-local storage; never serialize model contents."""
    location = Path(directory) if directory is not None else default_recovery_directory().parent / 'logs'
    location.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('matrix_displacement.gui.crash')
    logger.setLevel(logging.ERROR)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    handler = RotatingFileHandler(location / 'gui_errors.log', maxBytes=1_000_000,
                                  backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    return logger, location / 'gui_errors.log'


def main(argv=None):
    logger = None
    try:
        logger, _ = create_error_logger()
    except OSError:
        # A readonly home directory must not make the app impossible to start.
        pass

    def record_unhandled(exc_type, exc_value, traceback):
        if logger is not None:
            logger.error('Unhandled GUI callback error',
                         exc_info=(exc_type, exc_value, traceback))
        sys.__excepthook__(exc_type, exc_value, traceback)

    previous_hook = sys.excepthook
    sys.excepthook = record_unhandled
    try:
        from .main import main as gui_main
        return gui_main(argv)
    except ModuleNotFoundError as exc:
        if exc.name == 'PySide6':
            if sys.stderr is not None:
                print('缺少 PySide6；请先安装 requirements-gui.txt', file=sys.stderr)
        else:
            if logger is not None:
                logger.exception('GUI import error')
            if sys.stderr is not None:
                print(f'启动失败：{exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        if logger is not None:
            logger.exception('GUI startup or self-test failure')
        if sys.stderr is not None:
            print(f'GUI 启动或自检失败：{exc}', file=sys.stderr)
        return 1
    finally:
        sys.excepthook = previous_hook
