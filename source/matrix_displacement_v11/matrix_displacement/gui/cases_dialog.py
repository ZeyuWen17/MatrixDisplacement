"""Transactional case library editor. Cancel leaves the document untouched."""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QDialogButtonBox, QMessageBox)
from PySide6.QtCore import Qt
from matrix_displacement.load_cases import capture_case, case_model, combination_model, apply_loads, checked_name
from matrix_displacement.units import parse_quantity


class CasesDialog(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = deepcopy(model)
        self.setWindowTitle('荷载工况与线性组合')
        self.resize(680, 540)
        layout = QVBoxLayout(self)
        note = QLabel('共享几何、材料和支座。当前荷载是可编辑副本；修改后需重新保存到工况。\n'
                      '组合仅叠加荷载；给定位移属于共享支座，求解时施加一次。\n'
                      '应用会替换当前荷载，请先保存需保留的工况；取消对话框放弃本次全部操作。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.name = QLineEdit()
        self.name.setPlaceholderText('工况名称，例如恒载 G、活载 Q')
        layout.addWidget(self.name)
        row = QHBoxLayout()
        for label, callback in [('保存当前荷载为工况', self.save_case), ('清空当前荷载并返回建模', self.clear_loads)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, cb=callback: self.run(cb)); row.addWidget(button)
        layout.addLayout(row)
        self.cases = QComboBox(); layout.addWidget(self.cases)
        row = QHBoxLayout()
        for label, callback in [('应用所选工况并返回', self.apply_case), ('删除所选工况', self.delete_case)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, cb=callback: self.run(cb)); row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(QLabel('组合系数（允许零和负值；不自动套用规范）：'))
        self.factors = QTableWidget(0, 2)
        self.factors.setHorizontalHeaderLabels(['工况', '系数'])
        self.factors.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.factors)
        self.combo_name = QLineEdit(); self.combo_name.setPlaceholderText('组合名称，例如 1.2G+1.4Q')
        layout.addWidget(self.combo_name)
        self.combinations = QComboBox()
        self.combinations.currentTextChanged.connect(self.show_combination)
        layout.addWidget(self.combinations)
        row = QHBoxLayout()
        for label, callback in [('保存系数为组合', self.save_combination), ('应用表中系数并返回', self.apply_combination), ('删除所选组合', self.delete_combination)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, cb=callback: self.run(cb)); row.addWidget(button)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def run(self, callback):
        try: callback()
        except (ValueError, KeyError, TypeError) as exc:
            QMessageBox.warning(self, '工况操作失败', str(exc))

    def overwrite(self, name, library):
        return name not in library or QMessageBox.question(self, '覆盖已有内容', f'覆盖“{name}”？') == QMessageBox.StandardButton.Yes

    def refresh(self):
        self.cases.clear(); self.cases.addItems(sorted(self.model.load_cases))
        self.factors.setRowCount(len(self.model.load_cases))
        for row, name in enumerate(sorted(self.model.load_cases)):
            item = QTableWidgetItem(name); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.factors.setItem(row, 0, item); self.factors.setItem(row, 1, QTableWidgetItem('0'))
        self.combinations.clear(); self.combinations.addItem('（手动输入系数）')
        self.combinations.addItems(sorted(self.model.load_combinations))

    def save_case(self):
        name = checked_name(self.name.text())
        if self.overwrite(name, self.model.load_cases):
            capture_case(self.model, name); self.refresh(); self.cases.setCurrentText(name)

    def apply_case(self):
        apply_loads(self.model, case_model(self.model, self.cases.currentText())); self.accept()

    def clear_loads(self):
        self.model.loads = {}; self.model.member_loads = []; self.accept()

    def delete_case(self):
        name = self.cases.currentText()
        if any(name in factors for factors in self.model.load_combinations.values()):
            raise ValueError('组合仍引用此工况，请先删除相关组合。')
        self.model.load_cases.pop(name, None); self.refresh()

    def values(self):
        factors = {self.factors.item(r, 0).text(): parse_quantity(self.factors.item(r, 1).text(), '', '组合系数')
                   for r in range(self.factors.rowCount())}
        if not factors or not any(factors.values()):
            raise ValueError('请至少输入一个非零系数')
        return factors

    def save_combination(self):
        name = checked_name(self.combo_name.text()); factors = self.values()
        combination_model(self.model, factors)
        if self.overwrite(name, self.model.load_combinations):
            self.model.load_combinations[name] = factors; self.refresh(); self.combinations.setCurrentText(name)

    def show_combination(self, name):
        factors = self.model.load_combinations.get(name)
        if factors is not None:
            self.combo_name.setText(name)
            for r in range(self.factors.rowCount()):
                self.factors.item(r, 1).setText(str(factors.get(self.factors.item(r, 0).text(), 0)))

    def apply_combination(self):
        apply_loads(self.model, combination_model(self.model, self.values())); self.accept()

    def delete_combination(self):
        self.model.load_combinations.pop(self.combinations.currentText(), None); self.refresh()
