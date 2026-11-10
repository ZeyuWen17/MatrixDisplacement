"""Qt-independent, bounded undo/redo history for structural model edits.

History stores structural data snapshots, not widget state. A drag is committed
once on release; a failed edit restores its entire pre-edit model atomically.
History intentionally is not serialized into project JSON files.
"""
from copy import deepcopy
from dataclasses import dataclass

from .editor import ModelEditor
from .io import model_to_dict


@dataclass(frozen=True)
class EditorState:
    model: object
    defaults: tuple[float, float, float]


class EditHistory:
    def __init__(self, editor: ModelEditor, limit: int = 100):
        if not isinstance(editor, ModelEditor):
            raise TypeError('editor must be a ModelEditor')
        if type(limit) is not int or limit < 1:
            raise ValueError('limit must be an integer >= 1')
        self.editor = editor
        self.limit = limit
        self._undo = []
        self._redo = []
        self.mark_saved()

    def capture(self):
        return EditorState(
            deepcopy(self.editor.model),
            (self.editor.default_E, self.editor.default_A, self.editor.default_I),
        )

    def restore(self, state: EditorState):
        # Never reuse the snapshot object: future edits must not mutate history.
        self.editor.model = deepcopy(state.model)
        self.editor.default_E, self.editor.default_A, self.editor.default_I = state.defaults

    def _signature(self, state):
        return (model_to_dict(state.model), state.defaults)

    def same(self, left, right):
        return self._signature(left) == self._signature(right)

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    @property
    def is_dirty(self):
        # Default values are UI preferences, not part of JSON model persistence.
        return model_to_dict(self.editor.model) != self._saved_model

    def mark_saved(self):
        self._saved_model = deepcopy(model_to_dict(self.editor.model))

    def mark_recovered_unsaved(self):
        """A recovered draft must never be treated as an on-disk saved model."""
        self._saved_model = None

    def reset(self):
        """Call after opening/replacing model; no cross-document history."""
        self._undo.clear()
        self._redo.clear()
        self.mark_saved()

    def commit(self, before: EditorState):
        """Record a successful change once. Returns True only when changed."""
        if self.same(before, self.capture()):
            return False
        self._undo.append(before)
        if len(self._undo) > self.limit:
            self._undo.pop(0)
        self._redo.clear()
        return True

    def execute(self, operation, *args, **kwargs):
        """Execute model mutation atomically and create one undo entry."""
        before = self.capture()
        try:
            result = operation(*args, **kwargs)
            self.commit(before)
        except Exception:
            self.restore(before)
            raise
        return result

    def undo(self):
        if not self._undo:
            return False
        current = self.capture()
        previous = self._undo.pop()
        self._redo.append(current)
        self.restore(previous)
        return True

    def redo(self):
        if not self._redo:
            return False
        current = self.capture()
        upcoming = self._redo.pop()
        self._undo.append(current)
        self.restore(upcoming)
        return True
