"""Read-only numeric sorting and Excel-compatible clipboard tables."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView


class NumericItem(QTableWidgetItem):
    def __init__(self, value):
        super().__init__(format(value, '.15g'))
        self.value = value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self.value < other.value
        return super().__lt__(other)


class ResultTable(QTableWidget):
    def __init__(self, headers, rows, parent=None):
        rows = list(rows)
        super().__init__(len(rows), len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                item = NumericItem(value) if isinstance(value, (int, float)) else QTableWidgetItem(str(value))
                self.setItem(r, c, item)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.setToolTip('点击表头按数值排序；Ctrl+C 复制所选单元格（含表头），Ctrl+A 全选。')

    def copy_selection(self):
        selected = {(i.row(), i.column()) for i in self.selectedIndexes()}
        if not selected:
            return
        rows = sorted({r for r, _ in selected})
        columns = sorted({c for _, c in selected})
        text = ['\t'.join(self.horizontalHeaderItem(c).text() for c in columns)]
        def cell(r, c):
            item = self.item(r, c)
            return format(item.value, '.17g') if isinstance(item, NumericItem) else item.text()
        text += ['\t'.join(cell(r, c) if (r, c) in selected else '' for c in columns) for r in rows]
        QApplication.clipboard().setText('\n'.join(text))

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)


def result_tables(model, result):
    nodes = []
    for (nid, dof), i in result.dof_manager.mapping.items():
        nodes.append((nid, dof, float(result.displacements[i]), 'rad' if dof == 'rz' else 'm',
                      float(result.reactions[i]), 'N·m' if dof == 'rz' else 'N'))
    ends = []
    from matrix_displacement.core import Beam2D, Truss2D
    for eid, element in model.elements.items():
        labels = (('Fy_i', 'M_i', 'Fy_j', 'M_j') if isinstance(element, Beam2D) else
                  ('Fx_i', 'Fy_i', 'Fx_j', 'Fy_j') if isinstance(element, Truss2D) else
                  ('Fx_i', 'Fy_i', 'M_i', 'Fx_j', 'Fy_j', 'M_j'))
        ends.extend((eid, label, float(value), 'N·m' if label.startswith('M') else 'N')
                    for label, value in zip(labels, result.element_end_forces_local[eid]))
    return [('位移与反力表', ResultTable(['节点', '自由度', '位移', '位移单位', '反力', '反力单位'], nodes)),
            ('杆端力表', ResultTable(['杆件', '局部分量', '数值', '单位'], ends))]
