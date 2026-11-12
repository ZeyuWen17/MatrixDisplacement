"""PySide6 desktop interface for 2D matrix displacement analysis (V1.1).

All geometry/math/model validation is delegated to the existing model editor
and solver. The canvas is interactive QGraphicsView, while solved plots are
embedded Matplotlib figures. All numerical inputs are SI units.
"""
import math
import time
import os
import tempfile
import sys
from copy import deepcopy
from pathlib import Path
from matrix_displacement import __version__

from PySide6.QtCore import Qt, QRect, QRectF, QLineF, QPointF, Signal, QTimer, QThread
from PySide6.QtGui import QAction, QColor, QPen, QBrush, QPainter, QPolygonF, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsView, QGraphicsScene,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QSplitter, QTabWidget,
    QPlainTextEdit, QLabel, QPushButton, QComboBox, QCheckBox, QLineEdit,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QButtonGroup,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QDoubleSpinBox, QRubberBand, QInputDialog, QProgressBar, QToolBar, QListWidget,
)

from matrix_displacement.editor import ModelEditor, _real
from matrix_displacement.history import EditHistory
from matrix_displacement.inspection import inspect_node, inspect_member
from matrix_displacement.interaction import dimension_info, diagram_pick
from matrix_displacement.diagnostics import explain_error
from matrix_displacement.selection import select_in_rectangle, apply_selection
from matrix_displacement.label_layout import LabelRequest, place_labels
from matrix_displacement.core import UniformLoad2D, LinearLoad2D, PointLoad2D
from matrix_displacement.core import Frame2D, Beam2D, Truss2D, Mode, LinearStaticSolver
from matrix_displacement.io import model_to_dict
from matrix_displacement.reporting import save_teaching_report
from matrix_displacement.exporting import export_results_csv
from matrix_displacement.visualization import plot_force_diagram, plot_deformed_shape
from matrix_displacement.recovery import RecoveryStore
from matrix_displacement.file_revision import FileRevision
from matrix_displacement.supports import support_symbol, support_from_values
from matrix_displacement.preflight import check_model
from matrix_displacement.units import parse_quantity, label_unit

# QGraphicsScene pixels per metre; scene Y is reversed for positive global Y.
PIXELS_PER_METRE = 65.0
NODE_HIT_PIXELS = 12.0
ELEMENT_HIT_PIXELS = 10.0


class SolveThread(QThread):
    """Numerical work only; Qt and Matplotlib stay on the GUI thread."""
    def __init__(self, model, mode, parent=None):
        super().__init__(parent)
        self.model = model
        self.mode = mode
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = LinearStaticSolver(self.mode).solve(self.model)
        except Exception as exc:
            self.error = exc


def _point(node):
    return QPointF(node.x * PIXELS_PER_METRE, -node.y * PIXELS_PER_METRE)


def _point_like(xy):
    return QPointF(xy[0]*PIXELS_PER_METRE, -xy[1]*PIXELS_PER_METRE)


def _display_number(value):
    return f'{value:.6g}'


def _member_load_label(load):
    """Describe actual input magnitudes (signed, in load's chosen axes)."""
    system = '整体' if load.system == 'global' else '局部'
    if isinstance(load, UniformLoad2D):
        return f'均布[{system}] qx={load.qx:.4g}, qy={load.qy:.4g} N/m'
    if isinstance(load, LinearLoad2D):
        return (f'线性[{system}] i:({load.qx_i:.4g},{load.qy_i:.4g})'
                f' j:({load.qx_j:.4g},{load.qy_j:.4g}) N/m')
    if isinstance(load, PointLoad2D):
        return (f'集中[{system}] x={load.position:.4g} m, '
                f'Fx={load.fx:.4g}, Fy={load.fy:.4g} N')
    return type(load).__name__


def _segment_distance(p, a, b):
    dx, dy = b.x()-a.x(), b.y()-a.y()
    l2 = dx*dx+dy*dy
    if l2 == 0:
        return math.hypot(p.x()-a.x(), p.y()-a.y())
    t = max(0.0, min(1.0, ((p.x()-a.x())*dx+(p.y()-a.y())*dy)/l2))
    return math.hypot(p.x()-a.x()-t*dx, p.y()-a.y()-t*dy)


class NumericDialog(QDialog):
    """Reusable finite-valued numeric fields with explicit SI units."""

    def __init__(self, title, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        self.inputs = {}
        self.units = {}
        self.data = {}
        outer = QVBoxLayout(self)
        form = QFormLayout()
        for key, label, default in fields:
            field = QLineEdit(_display_number(default))
            field.setObjectName(key)
            self.units[key] = label_unit(label)
            field.setToolTip('支持单位后缀：如 10 kN、200 mm、210 GPa；不带单位按字段标示的 SI 单位')
            self.inputs[key] = field
            form.addRow(label, field)
        outer.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def accept(self):
        try:
            self.data = {key:parse_quantity(field.text(),self.units[key],key)
                         for key,field in self.inputs.items()}
        except ValueError as exc:
            QMessageBox.warning(self,'数值输入错误',str(exc))
            return
        super().accept()


class PropertiesDialog(NumericDialog):
    def __init__(self, E, A, I, element=None, parent=None):
        super().__init__('材料与截面属性（SI 单位）',[
            ('E','弹性模量 E (Pa)',E),
            ('A','面积 A (m²)',A),
            ('I','惯性矩 I (m⁴)',I),
        ],parent)
        self.release_i = None
        self.release_j = None
        if isinstance(element, Frame2D):
            self.release_i = QCheckBox('杆件 i 端释放转角（铰接）')
            self.release_j = QCheckBox('杆件 j 端释放转角（铰接）')
            self.release_i.setChecked(element.release_i)
            self.release_j.setChecked(element.release_j)
            self.layout().insertWidget(1,self.release_i)
            self.layout().insertWidget(2,self.release_j)
        self.layout().insertWidget(0,QLabel('可输入 210 GPa、100 cm²、800 cm⁴；不带单位按 SI。'))

    def accept(self):
        try:
            values = {key:parse_quantity(field.text(),self.units[key],key) for key,field in self.inputs.items()}
            if any(value <= 0 for value in values.values()):
                raise ValueError('E、A、I 都必须大于 0')
            self.data = values
        except ValueError as exc:
            QMessageBox.warning(self,'参数错误',str(exc))
            return
        QDialog.accept(self)


class SupportPreview(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.symbol=None
        self.setMinimumSize(110,100)
        self.setMaximumHeight(110)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width()/2,self.height()/2)
        painter.setPen(QPen(QColor('#b45309' if self.symbol and self.symbol.prescribed else '#334155'),1.6))
        painter.setBrush(QBrush(QColor('white')))
        if self.symbol:
            for x1,y1,x2,y2 in self.symbol.lines:painter.drawLine(QLineF(x1,y1,x2,y2))
            for points in self.symbol.polygons:
                painter.setBrush(QBrush(QColor('transparent' if len(points)==4 else 'white')))
                painter.drawPolygon(QPolygonF([QPointF(x,y) for x,y in points]))
            painter.setBrush(QBrush(QColor('white')))
            for x,y,r in self.symbol.circles:painter.drawEllipse(QRectF(x-r,y-r,2*r,2*r))
        painter.drawEllipse(QRectF(-4,-4,8,8))
        painter.end()


class SupportDialog(QDialog):
    def __init__(self, node_id, active, constraints, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'节点 {node_id}：位移约束 / 支座')
        self.setMinimumWidth(410)
        self.data = None
        self.inputs = {}
        self.active=set(active)
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel('勾选表示该自由度位移已知；零值为普通支座，也可输入支座沉降。'))
        preset_row=QHBoxLayout()
        self.preset_buttons={}
        presets=[('自由',set()),('固定',self.active),('铰接',{'ux','uy'} & self.active),
                 ('水平可动',{'uy'}),('竖向可动',{'ux'})]
        for name,dofs in presets:
            button=QPushButton(name)
            button.setEnabled(name=='自由' or bool(dofs) and dofs<=self.active)
            button.setToolTip('仅改变约束勾选；保留各自由度已输入的数值。')
            button.clicked.connect(lambda checked=False,selected=dofs:self._apply_preset(selected))
            self.preset_buttons[name]=button
            preset_row.addWidget(button)
        outer.addLayout(preset_row)
        form=QFormLayout()
        for dof, desc in (('ux','水平位移 ux (m)'),('uy','竖向位移 uy (m)'),('rz','转角 rz (rad)')):
            box = QCheckBox('约束')
            box.setEnabled(dof in active)
            box.setChecked(dof in self.active and (node_id,dof) in constraints)
            field = QLineEdit(_display_number(constraints.get((node_id,dof),0.0)))
            field.setEnabled(box.isChecked())
            box.toggled.connect(field.setEnabled)
            wrap = QWidget(); row = QHBoxLayout(wrap)
            row.setContentsMargins(0,0,0,0)
            row.addWidget(box);row.addWidget(field)
            self.inputs[dof]=(box,field)
            form.addRow(desc,wrap)
        outer.addLayout(form)
        self.preview=SupportPreview()
        outer.addWidget(self.preview)
        self.preview_text=QLabel()
        self.preview_text.setWordWrap(True)
        outer.addWidget(self.preview_text)
        outer.addWidget(QLabel('预设按当前单元的有效自由度设置；“固定”约束全部有效自由度。\n'
                               '切换预设保留输入值；普通零位移支座请确认数值为 0。'))
        for box,field in self.inputs.values():
            box.toggled.connect(self._update_preview)
            field.textChanged.connect(self._update_preview)
        self._update_preview()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                 QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _apply_preset(self,dofs):
        for dof,(box,field) in self.inputs.items():
            box.setChecked(box.isEnabled() and dof in dofs)
        self._update_preview()

    def _update_preview(self,*args):
        try:
            values={d:parse_quantity(field.text(),'rad' if d=='rz' else 'm',d) for d,(box,field) in self.inputs.items()
                    if box.isEnabled() and box.isChecked()}
            self.preview.symbol=support_from_values(values,self.active)
            text=(self.preview.symbol.name+'\n'+self.preview.symbol.detail) if values else '自由节点：无位移约束'
            if self.preview.symbol and self.preview.symbol.prescribed:text='给定位移 · '+text
            self.preview_text.setText(text)
        except ValueError:
            self.preview.symbol=None
            self.preview_text.setText('输入尚未有效，无法预览；请输入有限数值。')
        self.preview.update()

    def accept(self):
        try:
            self.data = {dof:parse_quantity(field.text(),'rad' if dof=='rz' else 'm',dof) for dof,(box,field) in self.inputs.items()
                         if box.isEnabled() and box.isChecked()}
        except ValueError as exc:
            QMessageBox.warning(self,'支座输入错误',str(exc));return
        super().accept()


class ModelCheckDialog(QDialog):
    def __init__(self,issues,parent,*,before_solve=False):
        super().__init__(parent)
        self.setWindowTitle('模型检查：点击问题定位')
        self.resize(720,420)
        layout=QVBoxLayout(self)
        label=QLabel('错误必须修正后才能计算；建议需人工核对，可继续计算。\n'
                     '检查不自动修改模型，也不能证明结构稳定。')
        layout.addWidget(label)
        self.issues=list(issues)
        self.list=QListWidget()
        self.list.setWordWrap(True)
        for issue in issues:
            self.list.addItem(('错误' if issue.severity=='error' else '建议')+'：'+issue.message)
        self.list.currentRowChanged.connect(lambda row:parent._locate_issue(issues[row]) if 0<=row<len(issues) else None)
        layout.addWidget(self.list)
        if not issues:layout.addWidget(QLabel('未发现上述检查范围内的问题；仍需求解器检查刚度与稳定性。'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        if before_solve and not any(i.severity=='error' for i in issues):
            proceed=buttons.addButton('已核对，继续计算',QDialogButtonBox.ButtonRole.AcceptRole)
            proceed.clicked.connect(self.accept)
        layout.addWidget(buttons)
        if issues:self.list.setCurrentRow(0)


class MemberLoadDialog(QDialog):
    """Create uniform, point or linear member load in local/global axes."""
    def __init__(self, eid, L, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle(f'杆件 {eid}：添加杆件荷载')
        self.setMinimumWidth(400)
        self.kind = None
        self.system = None
        self.data = None
        outer=QVBoxLayout(self)
        form=QFormLayout()
        self.kind_box=QComboBox()
        for name,code in [('均布荷载','uniform'),('杆内集中力','point'),('线性分布荷载（三角形/梯形）','linear')]:
            self.kind_box.addItem(name,code)
        self.system_box=QComboBox()
        self.system_box.addItem('杆件局部坐标系','local')
        self.system_box.addItem('整体坐标系','global')
        form.addRow('荷载类型',self.kind_box)
        form.addRow('力分量坐标系',self.system_box)
        outer.addLayout(form)
        self.stacks=[]
        for fields in (
            [('qx','轴向 qx (N/m)',0),('qy','横向 qy (N/m)',-1000)],
            [('position',f'距 i 端位置 x (m), 0～{L:.5g}',L/2),
             ('fx','轴向 Fx (N)',0),('fy','横向 Fy (N)',-1000)],
            [('qx_i','i 端 qx (N/m)',0),('qy_i','i 端 qy (N/m)',0),
             ('qx_j','j 端 qx (N/m)',0),('qy_j','j 端 qy (N/m)',-1000)],
        ):
            w=QWidget(); layout=QFormLayout(w); entries={}
            for key,label,default in fields:
                inp=QLineEdit(_display_number(default));entries[key]=inp
                layout.addRow(label,inp)
            self.stacks.append((w,entries))
            outer.addWidget(w)
        self.kind_box.currentIndexChanged.connect(self._switch)
        outer.addWidget(QLabel('支持 10 kN、2 kN/m、200 mm；无后缀按标示单位。\n符号：X 向右、Y 向上；向下荷载取负值。桁架不支持杆件荷载。'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                 QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._switch(0)
        if existing is not None:
            which = 0 if isinstance(existing,UniformLoad2D) else (
                1 if isinstance(existing,PointLoad2D) else 2)
            self.kind_box.setCurrentIndex(which)
            self.system_box.setCurrentIndex(0 if existing.system=='local' else 1)
            for key,field in self.stacks[which][1].items():
                field.setText(_display_number(getattr(existing,key)))

    def _switch(self, index):
        for i,(w,_) in enumerate(self.stacks):
            w.setVisible(i==index)

    def accept(self):
        try:
            self.kind = self.kind_box.currentData()
            self.system = self.system_box.currentData()
            self.data = {key:parse_quantity(widget.text(), 'm' if key=='position' else ('N/m' if key.startswith('q') else 'N'),key)
                         for key,widget in self.stacks[self.kind_box.currentIndex()][1].items()}
        except ValueError as exc:
            QMessageBox.warning(self,'荷载输入错误',str(exc));return
        super().accept()


class ModelCanvas(QGraphicsView):
    box_finished = Signal(QPointF, QPointF)
    plain_released = Signal(QPointF)
    clicked = Signal(QPointF)
    double_clicked = Signal(QPointF)
    pointer_moved = Signal(QPointF)
    drag_started = Signal(QPointF)
    drag_progress = Signal(QPointF)
    drag_finished = Signal(QPointF)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.canvas_scene=QGraphicsScene(self)
        self.setScene(self.canvas_scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)
        self.canvas_scene.setSceneRect(-300,-260,650,520)
        self.setBackgroundBrush(QBrush(QColor('#f8fafc')))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setToolTip('滚轮缩放；按住鼠标中键平移；选择工具拖拽节点')
        self._press_scene = None
        self._drag_active = False
        self._pan_active = False
        self._pan_last = None
        self.pan_mode = False
        self._box_selecting = False
        self._rubber_origin = None
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._rubber.hide()

    def set_pan_mode(self, enabled):
        self.pan_mode = bool(enabled)
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor if enabled
                                  else Qt.CursorShape.ArrowCursor)

    def begin_box_selection(self, scene_origin):
        """Prepare a viewport rubber band after parent confirms blank-space drag."""
        self._box_selecting = True
        self._rubber_origin = self.mapFromScene(scene_origin)
        self._rubber.setGeometry(QRect(self._rubber_origin, self._rubber_origin).normalized())
        self._rubber.show()

    def _update_box_selection(self, scene_point):
        if self._box_selecting:
            opposite = self.mapFromScene(scene_point)
            self._rubber.setGeometry(QRect(self._rubber_origin, opposite).normalized())

    def _begin_pan(self, event):
        self._pan_active = True
        self._pan_last = event.position().toPoint()
        self._press_scene = None
        self._drag_active = False
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def zoom_by(self, factor):
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError('Zoom factor must be finite and positive')
        new_scale = self.transform().m11() * factor
        if 0.10 <= new_scale <= 15:
            self.scale(factor, factor)

    def mousePressEvent(self,event):
        if event.button() == Qt.MouseButton.MiddleButton or (self.pan_mode and event.button() == Qt.MouseButton.LeftButton):
            self._begin_pan(event)
            event.accept()
            return
        if event.button()==Qt.MouseButton.LeftButton:
            self._press_scene = self.mapToScene(event.position().toPoint())
            self._drag_active = False
            self.clicked.emit(self._press_scene)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self,event):
        if self._pan_active and self._pan_last is not None:
            now = event.position().toPoint()
            delta = now - self._pan_last
            self._pan_last = now
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            event.accept()
            return
        p = self.mapToScene(event.position().toPoint())
        if self._press_scene is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            # Threshold is measured in viewport pixels; independent of zoom.
            delta = (p - self._press_scene) * self.transform().m11()
            if not self._drag_active and math.hypot(delta.x(), delta.y()) >= 6:
                self._drag_active = True
                self.drag_started.emit(self._press_scene)
            if self._drag_active:
                self._update_box_selection(p)
                if not self._box_selecting:
                    self.drag_progress.emit(p)
                event.accept()
                return
        self.pointer_moved.emit(p)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._pan_active and event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._pan_active = False
            self._pan_last = None
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor if self.pan_mode
                                      else Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.mapToScene(event.position().toPoint())
            if self._press_scene is not None and not self._drag_active:
                self.plain_released.emit(p)
            if self._press_scene is not None and self._drag_active:
                if self._box_selecting:
                    self._rubber.hide()
                    self._box_selecting = False
                    self.box_finished.emit(self._press_scene, p)
                else:
                    self.drag_finished.emit(p)
            self._press_scene = None
            self._drag_active = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self,event):
        if event.angleDelta().y()==0:
            event.ignore()
            return
        factor = 1.16 if event.angleDelta().y()>0 else 1/1.16
        self.zoom_by(factor)
        event.accept()

    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QBrush(QColor('#f8fafc')))
        step=PIXELS_PER_METRE/2
        if step*self.transform().m11()<7:
            return
        painter.setPen(QPen(QColor('#e5e9ef'),0))
        first_x=math.floor(rect.left()/step)
        last_x=math.ceil(rect.right()/step)
        first_y=math.floor(rect.top()/step)
        last_y=math.ceil(rect.bottom()/step)
        if last_x-first_x>1000 or last_y-first_y>1000:
            return
        for i in range(first_x,last_x+1):
            x=i*step
            painter.drawLine(QLineF(x,rect.top(),x,rect.bottom()))
        for j in range(first_y,last_y+1):
            y=j*step
            painter.drawLine(QLineF(rect.left(),y,rect.right(),y))
        painter.setPen(QPen(QColor('#94a3b8'),0))
        painter.drawLine(QLineF(0,rect.top(),0,rect.bottom()))
        painter.drawLine(QLineF(rect.left(),0,rect.right(),0))

    def redraw(self,model,selected=None,pending_node=None,show_dimensions=True):
        sc=self.canvas_scene
        sc.clear()
        if selected is None:
            selection = set()
        elif isinstance(selected, set):
            selection = selected
        elif isinstance(selected, (tuple, list)) and selected and isinstance(selected[0], tuple):
            selection = set(selected)
        else:
            selection = {selected}
        pending_labels = []
        obstacles = []
        def add_label(text, color, scale, x, y, dx, dy, *, tooltip=None):
            tag = sc.addText(text)
            tag.setDefaultTextColor(QColor(color))
            tag.setScale(scale)
            if tooltip:
                tag.setToolTip(tooltip)
            rect = tag.boundingRect()
            pending_labels.append((tag, LabelRequest(x, y,
                max(1.0, rect.width()*scale), max(1.0, rect.height()*scale), dx, dy)))
            return tag
        for node in model.nodes.values():
            pt = _point(node)
            obstacles.append((pt.x()-7,pt.y()-7,pt.x()+7,pt.y()+7))
        for e in model.elements.values():
            a,b = _point(model.nodes[e.node_i]),_point(model.nodes[e.node_j])
            selected_here = ('element',e.id) in selection
            color = '#ea580c' if selected_here else (
                '#2563eb' if isinstance(e,Frame2D) else
                '#0f766e' if isinstance(e,Truss2D) else '#7c3aed')
            pen=QPen(QColor(color),4 if selected_here else (3 if isinstance(e,Frame2D) else 2.6))
            sc.addLine(QLineF(a,b),pen)
            mid=(a+b)/2
            add_label(f'E{e.id}', color, 1.0, mid.x(), mid.y(), 3, -25)
            if show_dimensions:
                dim = dimension_info(model, e.id, offset=0.36)
                ds, de = (QPointF(dim.offset_start[0]*PIXELS_PER_METRE,
                                  -dim.offset_start[1]*PIXELS_PER_METRE),
                          QPointF(dim.offset_end[0]*PIXELS_PER_METRE,
                                  -dim.offset_end[1]*PIXELS_PER_METRE))
                dim_pen = QPen(QColor('#94a3b8'),1)
                dim_pen.setStyle(Qt.PenStyle.DashLine)
                sc.addLine(QLineF(ds,de),dim_pen)
                extension_pen = QPen(QColor('#cbd5e1'),1)
                sc.addLine(QLineF(a,ds),extension_pen)
                sc.addLine(QLineF(b,de),extension_pen)
                text_pt = _point_like(dim.label_position)
                add_label(dim.label, '#475569', .72, text_pt.x(), text_pt.y(),
                          4, -21, tooltip=f'杆件 E{e.id}: {dim.label}')
            if isinstance(e,Frame2D):
                for node_id,release in ((e.node_i,e.release_i),(e.node_j,e.release_j)):
                    if release:
                        p=_point(model.nodes[node_id])
                        sc.addEllipse(p.x()-5,p.y()-5,10,10,
                                      QPen(QColor('#be123c'),1.4),QBrush(QColor('white')))
        for nid,node in model.nodes.items():
            p=_point(node)
            if ('node',nid) in selection:
                sc.addEllipse(p.x()-10,p.y()-10,20,20,
                              QPen(QColor('#ea580c'),2),QBrush(QColor('#fff7ed')))
            elif pending_node==nid:
                sc.addEllipse(p.x()-10,p.y()-10,20,20,
                              QPen(QColor('#dc2626'),2),QBrush(QColor('#fee2e2')))
            sc.addEllipse(p.x()-4.5,p.y()-4.5,9,9,
                          QPen(QColor('#0f172a'),1),QBrush(QColor('white')))
            add_label(f'{nid}', '#0f172a', 1.0, p.x(), p.y(), 8, 5)
            support=support_symbol(model,nid)
            if support:
                color='#b45309' if support.prescribed else '#334155'
                pen=QPen(QColor(color),1.6)
                tooltip=support.name+'\n'+support.detail
                items=[]
                for x1,y1,x2,y2 in support.lines:
                    items.append(sc.addLine(p.x()+x1,p.y()+y1,p.x()+x2,p.y()+y2,pen))
                for points in support.polygons:
                    items.append(sc.addPolygon(QPolygonF([QPointF(p.x()+x,p.y()+y) for x,y in points]),
                                               pen,QBrush(QColor('transparent' if len(points)==4 else '#f8fafc'))))
                for x,y,r in support.circles:
                    items.append(sc.addEllipse(p.x()+x-r,p.y()+y-r,2*r,2*r,pen,QBrush(QColor('white'))))
                for item in items:
                    item.setToolTip(tooltip)
                    rect=item.sceneBoundingRect()
                    obstacles.append((rect.left(),rect.top(),rect.right(),rect.bottom()))
                text=support.name+'\n'+support.detail
                if support.prescribed:text='给定位移 · '+text
                add_label(text,color,.68,p.x(),p.y(),-15,32,tooltip=tooltip)
            fx,fy,mz=(model.loads.get((nid,d),0.) for d in ('ux','uy','rz'))
            for value,vx,vy,name in ((fx,1,0,'Fx'),(fy,0,-1,'Fy')):
                if value:
                    length=27*(1 if value>0 else -1)
                    self._arrow(sc,p.x()-vx*length,p.y()-vy*length,p.x(),p.y(),'#dc2626')
                    add_label(f'{name}={value:.3g} N', '#b91c1c', .77,
                              p.x(), p.y(), 10 if name=='Fy' else -54,
                              -46 if name=='Fy' else -36)
            if mz:
                add_label(f'{"↶" if mz>0 else "↷"} {mz:.3g} N·m', '#dc2626',
                          .8, p.x(), p.y(), -25, -24)
        for index,load in enumerate(model.member_loads,1):
            e=model.elements[load.element_id]
            L,c,sine=e.geometry(model)
            origin=model.nodes[e.node_i]
            concentrated=isinstance(load,PointLoad2D)
            load_color='#dc2626' if concentrated else ('#0f766e' if isinstance(load,UniformLoad2D) else '#9333ea')
            label=f'E{e.id} · 荷载{index}\n'+_member_load_label(load)
            if isinstance(load,PointLoad2D):
                stations=[(load.position,load.fx,load.fy)]
            else:
                stations=[]
                for k in range(9):
                    t=k/8
                    if isinstance(load,UniformLoad2D):qx,qy=load.qx,load.qy
                    else:qx,qy=(1-t)*load.qx_i+t*load.qx_j,(1-t)*load.qy_i+t*load.qy_j
                    stations.append((t*L,qx,qy))
            vectors=[]
            for position,fx,fy in stations:
                if load.system=='local':fx,fy=c*fx-sine*fy,sine*fx+c*fy
                vectors.append((position,fx,fy))
            maximum=max((math.hypot(fx,fy) for _,fx,fy in vectors),default=0.)
            tails=[]
            for position,fx,fy in vectors:
                px=(origin.x+c*position)*PIXELS_PER_METRE
                py=-(origin.y+sine*position)*PIXELS_PER_METRE
                factor=(58 if concentrated else 32)/maximum if maximum else 0.
                tx,ty=px-factor*fx,py+factor*fy
                if math.hypot(fx,fy)>0:
                    items=self._arrow(sc,tx,ty,px,py,load_color,width=3 if concentrated else 1.5,head_size=11 if concentrated else 6)
                    for item in items:
                        item.setToolTip(label)
                        item.setData(0,'member-load')
                        item.setData(1,index-1)
                    obstacles.append((min(tx,px)-4,min(ty,py)-4,max(tx,px)+4,max(ty,py)+4))
                tails.append(QPointF(tx,ty))
            if not isinstance(load,PointLoad2D):
                for first,last in zip(tails,tails[1:]):
                    item=sc.addLine(QLineF(first,last),QPen(QColor(load_color),1))
                    item.setToolTip(label)
                    item.setData(0,'member-load-envelope')
            anchor=tails[len(tails)//2]
            add_label(label,load_color,.78,anchor.x(),anchor.y(),8,-30,tooltip=label)
        # Resolve annotation collisions *after* all tags are collected.
        if pending_labels:
            requested = [item[1] for item in pending_labels]
            for (tag, _), (x, y) in zip(pending_labels, place_labels(requested, obstacles)):
                tag.setPos(x, y)
        if model.loads or model.member_loads:
            self._draw_load_legend(sc)
        if model.nodes:
            px=[_point(n).x() for n in model.nodes.values()]
            py=[_point(n).y() for n in model.nodes.values()]
            min_x,max_x,min_y,max_y=min(px),max(px),min(py),max(py)
            padding=2*PIXELS_PER_METRE
            geometry_rect=QRectF(min_x-padding,min_y-padding,
                                max(300,max_x-min_x+2*padding),
                                max(260,max_y-min_y+2*padding))
            sc.setSceneRect(geometry_rect.united(sc.itemsBoundingRect().adjusted(-20,-20,20,20)))
        else:
            sc.setSceneRect(-320,-240,640,480)

    def _arrow(self,sc,x0,y0,x1,y1,color,*,width=2,head_size=9):
        line=sc.addLine(x0,y0,x1,y1,QPen(QColor(color),width))
        angle=math.atan2(y1-y0,x1-x0)
        head=QPolygonF([QPointF(x1,y1),
                        QPointF(x1-head_size*math.cos(angle-.45),y1-head_size*math.sin(angle-.45)),
                        QPointF(x1-head_size*math.cos(angle+.45),y1-head_size*math.sin(angle+.45))])
        tip=sc.addPolygon(head,QPen(QColor(color),1),QBrush(QColor(color)))
        return line,tip

    def _draw_load_legend(self,sc):
        bounds=sc.itemsBoundingRect()
        x,y=bounds.left(),bounds.bottom()+24
        items=[]
        for row,(name,color,kind) in enumerate((
                ('集中荷载：单支粗箭头（N）','#dc2626','point'),
                ('均布荷载：等长细箭头 + 直线（N/m）','#0f766e','uniform'),
                ('线性荷载：渐变细箭头 + 斜线（N/m）','#9333ea','linear'))):
            top=y+row*46
            if kind=='point':
                items.extend(self._arrow(sc,x+24,top,x+24,top+30,color,width=3,head_size=9))
            else:
                tails=[]
                for k in range(4):
                    px=x+8+k*12
                    py=top+(0 if kind=='uniform' else 20-k*6)
                    items.extend(self._arrow(sc,px,py,px,top+30,color,width=1.5,head_size=5))
                    tails.append(QPointF(px,py))
                items.append(sc.addLine(QLineF(tails[0],tails[-1]),QPen(QColor(color),1)))
            text=sc.addText(name)
            text.setDefaultTextColor(QColor(color));text.setPos(x+68,top+5)
            items.append(text)
        note=sc.addText('荷载图例 · 箭头长度为示意，大小以标注数值为准')
        note.setPos(x,y+140);note.setDefaultTextColor(QColor('#475569'));items.append(note)
        for item in items:item.setData(0,'load-legend')

    def fit_all(self):
        self.fitInView(self.canvas_scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)


class MainWindow(QMainWindow):
    """Desktop application with opt-in recovery and checked, non-destructive saves."""
    def __init__(self):
        super().__init__()
        self.editor=ModelEditor()
        self.editor.load_example('cantilever')
        self.history=EditHistory(self.editor)
        self.recovery=RecoveryStore()
        self._autosave_periodic=QTimer(self)
        self._autosave_periodic.setInterval(60_000)
        self._autosave_periodic.timeout.connect(self._autosave_if_dirty)
        self._autosave_periodic.start()
        self._autosave_debounce=QTimer(self)
        self._autosave_debounce.setSingleShot(True)
        self._autosave_debounce.setInterval(2_500)
        self._autosave_debounce.timeout.connect(self._autosave_if_dirty)
        self._drag_node=None
        self._drag_initial=None
        self.selected_load_index=None
        self.result=None
        self.file_path=None
        self._export_directory=None
        self._source_revision=None
        self.unsaved=False
        self.selected=None
        self.selection=set()
        self.pending_node=None
        self.tool='select'
        self.figures={}
        self._figure_modes={}
        self._solve_thread=None
        self._plot_job=None
        self._plot_cancelled=False
        self._solve_cancelled=False
        self.show_dimensions = True
        self.setMinimumSize(1080,700)
        self.resize(1400,840)
        self._build()
        self._redraw()
        self.canvas.fit_all()
        self.statusBar().showMessage('已加载悬臂梁示例；点击“计算”可查看结果。')
        self._update_title()
        # Offer recovery only after the window is initialized and the event loop starts.
        self._recovery_offer_timer=QTimer(self)
        self._recovery_offer_timer.setSingleShot(True)
        self._recovery_offer_timer.timeout.connect(self._offer_recovery)
        self._recovery_offer_timer.start(0)

    def _build(self):
        file_menu=self.menuBar().addMenu('文件')
        def action(menu,label,callback,shortcut=None):
            a=QAction(label,self)
            if shortcut:a.setShortcut(shortcut)
            a.triggered.connect(callback)
            menu.addAction(a)
            return a
        action(file_menu,'新建空白模型',self.new_model,'Ctrl+N')
        action(file_menu,'打开 JSON 模型',self.open_model,'Ctrl+O')
        action(file_menu,'保存 JSON 模型',self.save_model,'Ctrl+S')
        action(file_menu,'另存为',lambda:self.save_model(save_as=True),'Ctrl+Shift+S')
        action(file_menu,'恢复自动保存草稿...',self._offer_recovery)
        file_menu.addSeparator()
        action(file_menu,'退出',self.close)
        edit_menu=self.menuBar().addMenu('编辑')
        self.undo_action=action(edit_menu,'撤销',self.undo_model,'Ctrl+Z')
        self.redo_action=action(edit_menu,'重做',self.redo_model,'Ctrl+Y')
        edit_menu.addSeparator()
        action(edit_menu,'重做（备用快捷键）',self.redo_model,'Ctrl+Shift+Z')
        examples=self.menuBar().addMenu('教学算例')
        action(examples,'悬臂梁：杆件均布 + 集中荷载',lambda:self.load_example('cantilever'))
        action(examples,'两跨连续梁',lambda:self.load_example('continuous_beam'))
        action(examples,'三角形平面桁架',lambda:self.load_example('truss'))
        analyze=self.menuBar().addMenu('分析与导出')
        action(analyze,'检查模型并定位问题',self.check_model_dialog)
        action(analyze,'荷载工况与组合',self.manage_load_cases)
        action(analyze,'运行分析',self.start_solve,'Ctrl+R')
        action(analyze,'导出教学报告',self.export_report)
        action(analyze,'导出 CSV 数据',self.export_csv)
        action(analyze,'保存当前结果图',self.start_export_figure)
        action(analyze,'导出全部结果图',self.start_export_all)
        view_menu=self.menuBar().addMenu('视图')
        action(view_menu,'放大',lambda:self.canvas.zoom_by(1.25),'Ctrl++')
        action(view_menu,'缩小',lambda:self.canvas.zoom_by(.8),'Ctrl+-')
        action(view_menu,'全模型适应窗口',lambda:self.canvas.fit_all(),'Ctrl+0')
        self.dimensions_action=action(view_menu,'显示杆件长度和角度',self._toggle_dimensions)
        self.dimensions_action.setCheckable(True)
        self.dimensions_action.setChecked(True)
        edit_menu.addSeparator()
        action(edit_menu,'批量平移所选节点',self.translate_selected_nodes,'Ctrl+M')
        action(edit_menu,'批量修改所选杆件 E/A/I',self.batch_edit_elements)
        action(edit_menu,'删除所有选中对象',self.delete_selected,'Delete')
        action(edit_menu,'全选节点和杆件',self.select_all,'Ctrl+A')
        action(edit_menu,'清除选择',self.clear_selection,'Escape')

        central=QWidget()
        self.setCentralWidget(central)
        layout=QHBoxLayout(central)
        layout.setContentsMargins(5,5,5,5)
        splitter=QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        controls=QWidget()
        controls.setMinimumWidth(255)
        controls.setMaximumWidth(320)
        cbox=QVBoxLayout(controls)
        cbox.setContentsMargins(8,8,8,8)
        heading=QLabel(f'矩阵位移法 · V{__version__}')
        heading.setStyleSheet('font-size:17px;font-weight:600;')
        cbox.addWidget(heading)
        subtitle=QLabel('二维结构建模与教学静力分析 · 自动保存与崩溃恢复')
        subtitle.setWordWrap(True)
        cbox.addWidget(subtitle)
        modes=QGroupBox('鼠标编辑工具')
        mb=QVBoxLayout(modes)
        self.tool_group=QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for code,text in (
            ('select','选择 / Ctrl多选 / 拖拽框选'),('pan','平移画布（按住左键）'),('node','绘制节点（网格 0.5 m）'),
            ('element','连接杆件（连续点两节点）'),('support','设置支座 / 给定位移'),
            ('nodal_load','设置节点荷载'),('member_load','添加杆件荷载'),
            ('delete','删除节点或杆件')):
            b=QPushButton(text)
            b.setCheckable(True)
            b.setChecked(code=='select')
            self.tool_group.addButton(b)
            b.clicked.connect(lambda checked,tool=code:self._set_tool(tool))
            mb.addWidget(b)
        self.snap_checkbox=QCheckBox('节点放置/拖拽时吸附 0.5 m 网格')
        self.snap_checkbox.setChecked(True)
        cbox.addWidget(modes)
        cbox.addWidget(self.snap_checkbox)
        elt=QGroupBox('建模参数')
        ef=QFormLayout(elt)
        self.element_type=QComboBox()
        for label,code in [('平面刚架 Frame2D','Frame2D'),
                           ('连续梁 Beam2D','Beam2D'),('平面桁架 Truss2D','Truss2D')]:
            self.element_type.addItem(label,code)
        ef.addRow('新建杆件类型',self.element_type)
        p_btn=QPushButton('设置默认 E、A、I / 选中杆件属性')
        p_btn.clicked.connect(self.edit_defaults_or_selected)
        ef.addRow(p_btn)
        node_btn=QPushButton('精确输入节点坐标')
        node_btn.clicked.connect(self.add_node_dialog)
        ef.addRow(node_btn)
        fit_btn=QPushButton('适应窗口 / 显示全模型')
        fit_btn.clicked.connect(lambda:self.canvas.fit_all())
        ef.addRow(fit_btn)
        edit_btn=QPushButton('编辑选中的节点 / 杆件')
        edit_btn.clicked.connect(self.edit_selected)
        ef.addRow(edit_btn)
        clear_btn=QPushButton('清空选中杆件的所有荷载')
        clear_btn.clicked.connect(self.clear_selected_member_loads)
        ef.addRow(clear_btn)
        batch_actions=QHBoxLayout()
        batch_move=QPushButton('批量平移节点')
        batch_move.clicked.connect(self.translate_selected_nodes)
        batch_properties=QPushButton('批量改杆件 E/A/I')
        batch_properties.clicked.connect(self.batch_edit_elements)
        batch_actions.addWidget(batch_move)
        batch_actions.addWidget(batch_properties)
        cbox.addLayout(batch_actions)
        cbox.addWidget(elt)
        prop_box=QGroupBox('杆件属性表（单击行选中）')
        prop_layout=QVBoxLayout(prop_box)
        self.prop_table=QTableWidget(0,8)
        self.prop_table.setHorizontalHeaderLabels(['ID','类型','i→j','L(m)','E(Pa)','A(m²)','I(m⁴)','荷载数'])
        self.prop_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.prop_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.prop_table.setMaximumHeight(185)
        self.prop_table.cellClicked.connect(self._property_row_clicked)
        prop_layout.addWidget(self.prop_table)
        cbox.addWidget(prop_box)
        load_box=QGroupBox('杆件荷载表（逐项编辑 / 删除）')
        load_layout=QVBoxLayout(load_box)
        self.load_table=QTableWidget(0,3)
        self.load_table.setHorizontalHeaderLabels(['序号','杆件','荷载值与坐标系'])
        self.load_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.load_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.load_table.setMaximumHeight(145)
        self.load_table.cellClicked.connect(self._load_row_clicked)
        load_layout.addWidget(self.load_table)
        load_actions=QHBoxLayout()
        edit_load_btn=QPushButton('修改所选荷载')
        edit_load_btn.clicked.connect(self.edit_selected_load)
        delete_load_btn=QPushButton('删除所选荷载')
        delete_load_btn.clicked.connect(self.delete_selected_load)
        load_actions.addWidget(edit_load_btn)
        load_actions.addWidget(delete_load_btn)
        load_layout.addLayout(load_actions)
        cbox.addWidget(load_box)
        solver_box=QGroupBox('求解与成果')
        sv=QVBoxLayout(solver_box)
        self.mode_combo=QComboBox()
        self.mode_combo.addItem('教学模式（保留组装矩阵）',Mode.TEACHING.value)
        self.mode_combo.addItem('快速模式（不保留中间矩阵）',Mode.FAST.value)
        toolbar=self.addToolBar('常用操作')
        toolbar.setMovable(False)
        toolbar.addAction('打开',self.open_model)
        toolbar.addAction('保存',lambda:self.save_model())
        toolbar.addSeparator()
        toolbar.addWidget(self.mode_combo)
        toolbar.addAction('计算并显示结果（Ctrl+R）',self.start_solve)
        solve_btn=QPushButton('▶ 计算并显示结果')
        solve_btn.setStyleSheet('font-weight:600; min-height:30px;')
        solve_btn.clicked.connect(self.start_solve)
        sv.addWidget(solve_btn)
        rep_btn=QPushButton('导出教学计算报告 (.md)')
        rep_btn.clicked.connect(self.export_report);sv.addWidget(rep_btn)
        csv_btn=QPushButton('导出结果表格 (.csv)')
        csv_btn.clicked.connect(self.export_csv);sv.addWidget(csv_btn)
        fig_btn=QPushButton('保存当前结果图 (.png)')
        fig_btn.clicked.connect(self.start_export_figure);sv.addWidget(fig_btn)
        all_fig_btn=QPushButton('导出全部结果图 (.png)')
        all_fig_btn.clicked.connect(self.start_export_all);sv.addWidget(all_fig_btn)
        cbox.addWidget(solver_box)
        self.info=QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet('color:#475569;')
        cbox.addWidget(self.info)
        cbox.addStretch(1)
        help_text=QLabel('单位：m / N / Pa / m² / m⁴\n'
                         '滚轮缩放、中键平移；Ctrl增减选择，左→右框选，右→左交叉选。\n'
                         '蓝：刚架  绿：桁架  紫：梁')
        help_text.setWordWrap(True)
        help_text.setStyleSheet('color:#64748b; font-size:11px;')
        cbox.addWidget(help_text)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        splitter.addWidget(scroll)
        self.main_tabs=QTabWidget()
        splitter.addWidget(self.main_tabs)
        self.canvas=ModelCanvas()
        self.canvas.clicked.connect(self._canvas_click)
        self.canvas.plain_released.connect(self._plain_release)
        self.canvas.double_clicked.connect(self._canvas_double)
        self.canvas.pointer_moved.connect(self._mouse_move)
        self.canvas.drag_started.connect(self._begin_drag)
        self.canvas.drag_progress.connect(self._drag_update)
        self.canvas.drag_finished.connect(self._end_drag)
        self.canvas.box_finished.connect(self._finish_box)
        self.main_tabs.addTab(self.canvas,'建模画布')
        self.result_tabs=QTabWidget()
        self.main_tabs.addTab(self.result_tabs,'计算结果')
        splitter.setSizes([295,1050])
        self._reset_results()
        self._update_history_actions()

        labels_bar=self.addToolBar('内力图标注')
        labels_bar.addWidget(QLabel('内力图数值：'))
        self.force_labels=QComboBox()
        for label,value in (('自动（大模型隐藏标注）','auto'),('隐藏数值','none'),('仅采样极值','extrema'),('端点与采样极值','all')):
            self.force_labels.addItem(label,value)
        self.force_labels.setCurrentIndex(0)
        labels_bar.addWidget(self.force_labels)
        self.force_labels.currentIndexChanged.connect(self._refresh_force_labels)
        self.result_tabs.currentChanged.connect(self._show_result_figure)
        self.solve_progress=QProgressBar()
        self.solve_progress.setRange(0,0)
        self.solve_progress.setMaximumWidth(160)
        self.statusBar().addPermanentWidget(self.solve_progress)
        self.cancel_solve_button=QPushButton('取消本次计算')
        self.cancel_solve_button.clicked.connect(self.cancel_solve)
        self.statusBar().addPermanentWidget(self.cancel_solve_button)
        self.solve_progress.hide()
        self.cancel_solve_button.hide()

    def _refresh_force_labels(self, *args):
        if self.result is None:
            return
        self._show_result_figure()

    def _show_result_figure(self, *args):
        if self.result is None:
            return
        title=self.result_tabs.tabText(self.result_tabs.currentIndex())
        if title in self.figures:
            try:
                mode=self._label_mode() if title!='变形图' else 'deformed'
                if self._figure_modes.get(title)!=mode and self._plot_job is None:
                    self._start_plot_job(self._figure_steps(title),f'生成{title}')
            except Exception as exc:
                self._error(exc)

    def _ensure_figure(self, title):
        figure=self.figures[title]
        mode=self._label_mode() if title!='变形图' else 'deformed'
        if self._figure_modes.get(title)==mode:
            return figure
        figure.clear()
        ax=figure.add_subplot(111)
        if title=='变形图':
            plot_deformed_shape(self.editor.model,self.result,ax=ax)
        else:
            component={'轴力 N':'N','剪力 V':'V','弯矩 M':'M'}[title]
            plot_force_diagram(self.editor.model,self.result,component,ax=ax,
                               interactive=True,value_mode=mode,show_node_ids=len(self.editor.model.elements)<=100)
        figure.tight_layout()
        self._figure_modes[title]=mode
        figure.canvas.draw_idle()
        return figure

    def _label_mode(self):
        mode=self.force_labels.currentData()
        return ('none' if len(self.editor.model.elements)>100 else 'all') if mode=='auto' else mode

    def _figure_steps(self,title):
        from matrix_displacement.visualization import force_diagram_steps, deformed_shape_steps
        figure=self.figures[title]
        mode=self._label_mode() if title!='变形图' else 'deformed'
        if self._figure_modes.get(title)==mode:
            return figure
        figure.clear()
        ax=figure.add_subplot(111)
        complete=False
        try:
            options=dict(ax=ax,show_node_ids=len(self.editor.model.elements)<=100)
            if title=='变形图':
                yield from deformed_shape_steps(self.editor.model,self.result,**options)
            else:
                component={'轴力 N':'N','剪力 V':'V','弯矩 M':'M'}[title]
                yield from force_diagram_steps(self.editor.model,self.result,component,
                                               interactive=True,value_mode=mode,**options)
            yield ('布局与显示（完整标注可能较慢）',0,0)
            figure.tight_layout()
            figure.canvas.draw()
            self._figure_modes[title]=mode
            complete=True
            return figure
        finally:
            if not complete:
                figure.clear()
                self._figure_modes.pop(title,None)
                figure.canvas.draw_idle()

    def _start_plot_job(self,steps,label):
        if self._plot_job is not None or self._solve_thread is not None:
            return
        self._plot_job=steps
        self._plot_cancelled=False
        self._plot_label=label
        self._export_completed=0
        self._export_total=0
        self._set_solve_busy(True)
        self.cancel_solve_button.setText('取消绘图 / 导出')
        self.statusBar().showMessage(label)
        QTimer.singleShot(0,self._advance_plot_job)

    def _advance_plot_job(self):
        job=self._plot_job
        if job is None:return
        done=False
        message=None
        try:
            if self._plot_cancelled:
                job.close()
                done=True
                message=self._plot_label+'已取消；已完成图片保留，未完成图片不写入。'
            else:
                deadline=time.perf_counter()+.012
                while True:
                    stage,current,total=next(job)
                    self.solve_progress.setRange(0,total)
                    self.solve_progress.setValue(current)
                    self.statusBar().showMessage(f'{self._plot_label}：{stage} '+(f'{current}/{total}' if total else ''))
                    if time.perf_counter()>=deadline or stage.startswith(('写入','图片已完成','布局')):break
        except StopIteration:
            done=True
            message=self._plot_label+'完成。'
        except Exception as exc:
            done=True
            job.close()
            self._error(exc)
            message=self._plot_label+'失败；已完成图片保留。'
        finally:
            if done:
                self._plot_job=None
                self._set_solve_busy(False)
                self.solve_progress.setRange(0,0)
                self.cancel_solve_button.setText('取消本次计算')
                if self._export_total:message+=f'（图片 {self._export_completed}/{self._export_total}）'
                if message:self.statusBar().showMessage(message,15000)
            else:
                QTimer.singleShot(1,self._advance_plot_job)

    def _export_steps(self,targets,success_directory=None):
        self._export_completed=0
        self._export_total=len(targets)
        for index,(title,path) in enumerate(targets,1):
            figure=yield from self._figure_steps(title)
            yield (f'写入第 {index}/{len(targets)} 张 PNG（本张写入结束后可取消）',index-1,len(targets))
            fd,temp=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
            os.close(fd)
            try:
                figure.savefig(temp,format='png',dpi=160,bbox_inches='tight')
                os.replace(temp,path)
            finally:
                Path(temp).unlink(missing_ok=True)
            # Always return to the event loop between complete images.
            self._export_completed=index
            yield ('图片已完成',index,len(targets))
            yield ('准备下一张',index,len(targets))
        if success_directory is not None:self._export_directory=Path(success_directory).resolve()

    def start_export_all(self):
        if not self._require_result() or self._plot_job is not None:return
        path=QFileDialog.getExistingDirectory(self,'选择全部结果图输出文件夹',str(self._export_start_directory()))
        if not path:return
        try:
            prefix=f'{self.file_path.stem}_' if self.file_path else ''
            directory=self._new_export_directory(path,prefix+'result_figures')
            targets=[(title,directory/f'{prefix}{title}.png') for title in ('轴力 N','剪力 V','弯矩 M','变形图')]
            self._start_plot_job(self._export_steps(targets,path),f'导出到 {directory}')
        except Exception as exc:self._error(exc)

    def start_export_figure(self):
        if not self._require_result() or self._plot_job is not None:return
        title=self.result_tabs.tabText(self.result_tabs.currentIndex())
        if title not in self.figures:
            QMessageBox.information(self,'请选择图形','请先选择一个结果图标签。');return
        path,_=QFileDialog.getSaveFileName(self,'保存结果图',self._export_default_file(f'{title}.png'),'PNG 图片 (*.png)')
        if path:
            target=Path(path)
            self._start_plot_job(self._export_steps([(title,target)],target.parent),f'导出到 {target}')

    def _update_history_actions(self):
        self.undo_action.setEnabled(self.history.can_undo)
        self.redo_action.setEnabled(self.history.can_redo)

    def _edit(self, operation, *args, **kwargs):
        return self.history.execute(operation, *args, **kwargs)

    def undo_model(self):
        if self.history.undo():
            self._modified()

    def redo_model(self):
        if self.history.redo():
            self._modified()

    def _snap(self, x, y):
        if self.snap_checkbox.isChecked():
            return round(x*2)/2, round(y*2)/2
        return x, y

    def _property_row_clicked(self, row, column):
        ident=int(self.prop_table.item(row,0).text())
        self.selected=('element',ident)
        self.selection={self.selected}
        self._redraw()
        self._update_inspector()

    def _load_row_clicked(self, row, column):
        idx=int(self.load_table.item(row,0).text())-1
        self.selected_load_index=idx
        eid=self.editor.model.member_loads[idx].element_id
        self.selected=('element',eid)
        self.selection={self.selected}
        self._redraw()

    def edit_selected_load(self):
        idx=self.selected_load_index
        if idx is None or idx >= len(self.editor.model.member_loads):
            QMessageBox.information(self,'请选择荷载','请先在杆件荷载表中单击一行。')
            return
        old=self.editor.model.member_loads[idx]
        L=self.editor.model.elements[old.element_id].geometry(self.editor.model)[0]
        dialog=MemberLoadDialog(old.element_id,L,self,existing=old)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:
                self._edit(self.editor.replace_member_load,idx,dialog.kind,
                           system=dialog.system,**dialog.data)
                self._modified()
            except Exception as exc:self._error(exc)

    def delete_selected_load(self):
        idx=self.selected_load_index
        if idx is None or idx >= len(self.editor.model.member_loads):
            QMessageBox.information(self,'请选择荷载','请先在杆件荷载表中单击一行。')
            return
        try:
            self._edit(self.editor.delete_member_load,idx)
            self._modified()
        except Exception as exc:self._error(exc)

    def _begin_drag(self, p):
        self._drag_node = None
        self._drag_initial = None
        self._drag_nodes = ()
        if self.tool != 'select':
            return
        found = self._hit(p)
        if found is None:
            self.canvas.begin_box_selection(p)
            return
        if found[0] == 'node':
            self._drag_node = found[1]
            self._drag_initial = self.history.capture()
            self._drag_origin = self._world(p)
            # Drag an already-selected group of nodes together.
            self._drag_nodes = tuple(sorted(nid for typ, nid in self.selection if typ == 'node'))
            if found not in self.selection or not self._drag_nodes:
                self._drag_nodes = (found[1],)

    def _drag_move(self, p, *, snap=False):
        dx = self._world(p)[0] - self._drag_origin[0]
        dy = self._world(p)[1] - self._drag_origin[1]
        if snap:
            # Snap lead node to grid, preserve exact relative geometry.
            start_node = self._drag_initial.model.nodes[self._drag_node]
            target = self._snap(start_node.x + dx, start_node.y + dy)
            dx, dy = target[0]-start_node.x, target[1]-start_node.y
        return self.editor.move_nodes({nid: (
            self._drag_initial.model.nodes[nid].x + dx,
            self._drag_initial.model.nodes[nid].y + dy) for nid in self._drag_nodes})

    def _drag_update(self,p):
        if self._drag_node is None:
            return
        try:
            self._drag_move(p)
            self._redraw()
            self.statusBar().showMessage(f'正在拖动 {len(self._drag_nodes)} 个节点')
        except ValueError as exc:
            self.statusBar().showMessage(f'当前位置不可用：{exc}',3000)

    def _end_drag(self,p):
        if self._drag_node is None:
            return
        before = self._drag_initial
        moved = len(self._drag_nodes)
        try:
            self._drag_move(p, snap=True)
            if self.history.commit(before):
                self._modified()
                self.statusBar().showMessage(f'{moved} 个节点已移动；Ctrl+Z 可撤销',5000)
            else:
                self._redraw()
        except Exception as exc:
            self.history.restore(before)
            self._redraw()
            self._error(exc)
        finally:
            self._drag_node = None
            self._drag_initial = None
            self._drag_nodes = ()

    def _finish_box(self, start, finish):
        """Left-to-right: window. Right-to-left: crossing selection."""
        start_xy, end_xy = self._world(start), self._world(finish)
        hits = select_in_rectangle(self.editor.model, start_xy, end_xy)
        mods = QApplication.keyboardModifiers()
        toggle = bool(mods & Qt.KeyboardModifier.ControlModifier)
        additive = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        self.selection = apply_selection(self.selection, hits, additive=additive,
                                         toggle=toggle)
        self.selected = sorted(self.selection)[-1] if self.selection else None
        self._redraw()
        kind = '窗口选择' if end_xy[0] >= start_xy[0] else '交叉选择'
        self.statusBar().showMessage(f'{kind}：已选 {len(self.selection)} 个对象',5000)

    def _set_tool(self,tool):
        self.tool=tool
        self.canvas.set_pan_mode(tool == 'pan')
        self.pending_node=None
        self._redraw()
        self.statusBar().showMessage({
            'select':'单击选择；Ctrl单击切换、Shift单击追加；左→右框选全包含，右→左交叉选。',
            'pan':'按住鼠标左键拖动画布；任何工具下都可以按住中键平移。',
            'node':'在画布点击创建节点（每格 0.5 m）；可通过精确输入添加节点。',
            'element':'依次点击两个已有节点创建杆件。',
            'support':'点击节点，选择约束的自由度。',
            'nodal_load':'点击节点，设置 Fx、Fy 或 Mz。',
            'member_load':'点击杆件，添加均布 / 集中 / 线性分布荷载。',
            'delete':'点击节点或杆件删除；节点删除会连带删除相邻杆件。',
        }[tool])

    def _toggle_dimensions(self):
        self.show_dimensions = self.dimensions_action.isChecked()
        self._redraw()

    def clear_selection(self):
        self.selected = None
        self.selection.clear()
        self.pending_node = None
        self.selected_load_index = None
        self._redraw()

    def _redraw(self):
        self.selection = {obj for obj in self.selection
                          if obj[1] in (self.editor.model.nodes if obj[0]=='node'
                                        else self.editor.model.elements)}
        if self.selected is not None and self.selected not in self.selection:
            self.selection.add(self.selected)
        self.canvas.redraw(self.editor.model,self.selection,self.pending_node,
                           show_dimensions=self.show_dimensions)
        m=self.editor.model
        if self.selected is None:
            s='当前未选中对象'
        elif self.selected[0]=='node' and self.selected[1] in m.nodes:
            nid=self.selected[1];n=m.nodes[nid]
            support=', '.join(f'{d}={v:.3g}' for (i,d),v in m.constraints.items() if i==nid) or '无'
            loads=', '.join(f'{d}={v:.3g}' for (i,d),v in m.loads.items() if i==nid) or '无'
            s=f'节点 {nid}：({n.x:.4g}, {n.y:.4g}) m\n约束：{support}\n节点荷载：{loads}'
        elif self.selected[0]=='element' and self.selected[1] in m.elements:
            eid=self.selected[1];e=m.elements[eid]
            L=e.geometry(m)[0]
            loads=[load for load in m.member_loads if load.element_id==eid]
            load_text='；'.join(type(load).__name__+': '+', '.join(
                f'{k}={v:.4g}' for k,v in vars(load).items()
                if k not in ('element_id','system')) for load in loads) or '无'
            s=f'单元 {eid}：{type(e).__name__}\n{e.node_i} → {e.node_j}，L={L:.4g}m\n荷载：{load_text}'
        else:
            self.selected=None;s='当前未选中对象'
        self.info.setText(f'节点 {len(m.nodes)} | 杆件 {len(m.elements)} | 已选 {len(self.selection)} | 杆件荷载 {len(m.member_loads)}\n{s}')
        self._refresh_property_table()
        self._refresh_load_table()
        self._update_inspector()

    def _refresh_property_table(self):
        model=self.editor.model
        self.prop_table.blockSignals(True)
        self.prop_table.setRowCount(len(model.elements))
        for row,(eid,e) in enumerate(sorted(model.elements.items())):
            mat=model.materials[e.material_id]
            sec=model.sections[e.section_id]
            values=(eid,type(e).__name__,f'{e.node_i}→{e.node_j}',
                    f'{e.geometry(model)[0]:.5g}',f'{mat.E:.4g}',
                    f'{sec.A:.4g}',f'{sec.I:.4g}',
                    sum(load.element_id==eid for load in model.member_loads))
            for col,value in enumerate(values):
                self.prop_table.setItem(row,col,QTableWidgetItem(str(value)))
            if ('element',eid) in self.selection:
                self.prop_table.selectRow(row)
        self.prop_table.blockSignals(False)

    def _refresh_load_table(self):
        loads=self.editor.model.member_loads
        self.load_table.blockSignals(True)
        self.load_table.setRowCount(len(loads))
        for row,load in enumerate(loads):
            for col,value in enumerate((row+1,load.element_id,_member_load_label(load))):
                item=QTableWidgetItem(str(value))
                item.setToolTip(_member_load_label(load))
                self.load_table.setItem(row,col,item)
            if self.selected_load_index==row:
                self.load_table.selectRow(row)
        self.load_table.blockSignals(False)

    def _world(self,scene_point):
        return scene_point.x()/PIXELS_PER_METRE,-scene_point.y()/PIXELS_PER_METRE

    def _mouse_move(self,point):
        x,y=self._world(point)
        self.statusBar().showMessage(f'画布坐标：x={x:.3f} m，y={y:.3f} m | 当前工具：{self.tool}',2000)

    def _hit(self,p):
        zoom=max(self.canvas.transform().m11(),0.01)
        n_radius=NODE_HIT_PIXELS/zoom
        e_radius=ELEMENT_HIT_PIXELS/zoom
        model=self.editor.model
        closest=(float('inf'),None)
        for nid,node in model.nodes.items():
            q=_point(node)
            d=math.hypot(p.x()-q.x(),p.y()-q.y())
            if d<closest[0]:closest=(d,('node',nid))
        if closest[0]<=n_radius:return closest[1]
        closest=(float('inf'),None)
        for eid,e in model.elements.items():
            a,b=_point(model.nodes[e.node_i]),_point(model.nodes[e.node_j])
            d=_segment_distance(p,a,b)
            if d<closest[0]:closest=(d,('element',eid))
        return closest[1] if closest[0]<=e_radius else None

    def _plain_release(self,p):
        # A normal click collapses a multi-selection; a drag preserves the group.
        if self.tool != 'select' or len(self.selection) <= 1:
            return
        if QApplication.keyboardModifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            return
        found = self._hit(p)
        if found in self.selection:
            self.selection = {found}
            self.selected = found
            self._redraw()

    def _canvas_click(self,p):
        found=self._hit(p)
        if self.tool=='select':
            mods = QApplication.keyboardModifiers()
            toggle = bool(mods & Qt.KeyboardModifier.ControlModifier)
            additive = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            if found is not None and not (toggle or additive) and found in self.selection:
                # Preserve an existing node group so it can be dragged together.
                pass
            else:
                self.selection = apply_selection(self.selection,
                    () if found is None else (found,), additive=additive, toggle=toggle)
            self.selected = found if found in self.selection else (
                sorted(self.selection)[-1] if self.selection else None)
            self._redraw();return
        try:
            if self.tool=='node':
                x,y=self._world(p)
                self._edit(self.editor.add_node,*self._snap(x,y))
                self._modified()
            elif self.tool=='element':
                if found is None or found[0]!='node':
                    self.statusBar().showMessage('请先单击已有节点作为杆件端点。',4000)
                    return
                nid=found[1]
                if self.pending_node is None:
                    self.pending_node=nid
                    self._redraw()
                    self.statusBar().showMessage(f'已选择节点 {nid}，请点击另一个节点。',4000)
                    return
                self._edit(self.editor.add_element,self.pending_node,nid,self.element_type.currentData())
                self.pending_node=None
                self._modified()
            elif self.tool=='support' and found and found[0]=='node':
                self._support_dialog(found[1])
            elif self.tool=='nodal_load' and found and found[0]=='node':
                self._nodal_load_dialog(found[1])
            elif self.tool=='member_load' and found and found[0]=='element':
                self._member_load_dialog(found[1])
            elif self.tool=='delete' and found:
                self.selected=found
                self.selection={found}
                self.delete_selected()
            else:
                self.statusBar().showMessage('请选择对应的节点或杆件。',4000)
        except Exception as exc:
            self._error(exc)

    def _canvas_double(self,p):
        if self.tool!='select':return
        self.selected=self._hit(p)
        self.selection={self.selected} if self.selected else set()
        self._redraw()
        self.edit_selected()

    def _modified(self):
        self.unsaved=self.history.is_dirty
        self._schedule_autosave()
        self.result=None
        self.selected=None
        self.selection.clear()
        self.selected_load_index=None
        self.pending_node=None
        self._reset_results()
        self._redraw()
        self._update_title()
        self._update_history_actions()

    def _reset_results(self):
        if self._plot_job is not None:
            self._plot_job.close()
            self._plot_job=None
            self._set_solve_busy(False)
            self.solve_progress.setRange(0,0)
            self.cancel_solve_button.setText('取消本次计算')
        self.figures.clear()
        self._figure_modes.clear()
        self.result_tabs.blockSignals(True)
        while self.result_tabs.count():
            old_page=self.result_tabs.widget(0)
            self.result_tabs.removeTab(0)
            old_page.deleteLater()
        self.summary=QPlainTextEdit()
        self.summary.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.summary.setReadOnly(True)
        self.summary.setPlainText('模型尚未计算，或已修改。请点击“计算并显示结果”。')
        self.result_tabs.addTab(self.summary,'数值结果')
        self.inspect_text=None
        self.result_tabs.blockSignals(False)

    def _update_title(self):
        label=str(self.file_path.name) if self.file_path else '未命名模型'
        self.setWindowTitle(f'矩阵位移法教学系统 V{__version__} — {label}{" *" if self.unsaved else ""}')

    def _error(self,exc):
        explanation = explain_error(exc)
        QMessageBox.critical(self,explanation.title,explanation.detail)
        self.statusBar().showMessage(explanation.title+': '+str(exc),7000)

    def add_node_dialog(self):
        d=NumericDialog('精确输入节点坐标',[('x','X 坐标 (m)',0),('y','Y 坐标 (m)',0)],self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self._edit(self.editor.add_node,**d.data)
                self._modified()
            except Exception as exc:self._error(exc)

    def edit_defaults_or_selected(self):
        if self.selected and self.selected[0]=='element':
            self.edit_selected()
            return
        d=PropertiesDialog(self.editor.default_E,self.editor.default_A,self.editor.default_I,parent=self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:
                self._edit(self.editor.set_defaults,**d.data)
                self._update_history_actions()
                self.statusBar().showMessage('已设置新建杆件的默认 E、A、I；已有杆件不受影响。',7000)
            except Exception as exc:self._error(exc)

    def edit_selected(self):
        if not self.selected:return
        typ,ident=self.selected
        try:
            if typ=='node':
                node=self.editor.model.nodes[ident]
                d=NumericDialog(f'节点 {ident}：修改坐标',[
                    ('x','X (m)',node.x),('y','Y (m)',node.y)],self)
                if d.exec()==QDialog.DialogCode.Accepted:
                    self._edit(self.editor.move_node,ident,**d.data)
                    self._modified()
            else:
                element=self.editor.model.elements[ident]
                mat=self.editor.model.materials[element.material_id]
                sec=self.editor.model.sections[element.section_id]
                d=PropertiesDialog(mat.E,sec.A,sec.I,element,self)
                if d.exec()==QDialog.DialogCode.Accepted:
                    kwargs={}
                    if isinstance(element,Frame2D):
                        kwargs={'release_i':d.release_i.isChecked(),
                                'release_j':d.release_j.isChecked()}
                    self._edit(self.editor.set_element_properties,ident,**d.data,**kwargs)
                    self._modified()
        except Exception as exc:self._error(exc)

    def _support_dialog(self,nid):
        d=SupportDialog(nid,self.editor.active_dofs(nid),self.editor.model.constraints,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            self._edit(self.editor.set_support,nid,d.data)
            self._modified()

    def _nodal_load_dialog(self,nid):
        active=self.editor.active_dofs(nid)
        fields=[]
        for dof,label in (('ux','Fx (N)'),('uy','Fy (N)'),('rz','Mz (N·m)')):
            if dof in active:
                fields.append((dof,label,self.editor.model.loads.get((nid,dof),0.0)))
        d=NumericDialog(f'节点 {nid}：节点荷载（替换）',fields,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            self._edit(self.editor.set_nodal_load,nid,**d.data)
            self._modified()

    def _member_load_dialog(self,eid):
        element=self.editor.model.elements[eid]
        if isinstance(element,Truss2D):
            raise ValueError('Truss2D 桁架仅支持节点荷载；请先细分杆件。')
        L=element.geometry(self.editor.model)[0]
        d=MemberLoadDialog(eid,L,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            self._edit(self.editor.add_member_load,eid,d.kind,system=d.system,**d.data)
            self._modified()

    def select_all(self):
        self.selection = ({('node', nid) for nid in self.editor.model.nodes} |
                          {('element', eid) for eid in self.editor.model.elements})
        self.selected = sorted(self.selection)[-1] if self.selection else None
        self._redraw()

    def translate_selected_nodes(self):
        ids = sorted(nid for kind, nid in self.selection if kind == 'node')
        if not ids and self.selected and self.selected[0]=='node':
            ids = [self.selected[1]]
        if not ids:
            QMessageBox.information(self,'请选择节点','请先 Ctrl 多选或框选需要平移的节点。')
            return
        dialog = NumericDialog(f'平移 {len(ids)} 个节点',[
            ('dx','Δx (m)',0),('dy','Δy (m)',0)],self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._edit(self.editor.translate_nodes, ids, dialog.data['dx'], dialog.data['dy'])
                self._modified()
            except Exception as exc:
                self._error(exc)

    def batch_edit_elements(self):
        ids = sorted(eid for kind, eid in self.selection if kind == 'element')
        if not ids and self.selected and self.selected[0]=='element':
            ids = [self.selected[1]]
        if not ids:
            QMessageBox.information(self,'请选择杆件','请先选中需要统一修改属性的杆件。')
            return
        element = self.editor.model.elements[ids[0]]
        mat = self.editor.model.materials[element.material_id]
        sec = self.editor.model.sections[element.section_id]
        dialog = NumericDialog(f'统一修改 {len(ids)} 根杆件的 E / A / I（保留铰释放）',[
            ('E','E (Pa)',mat.E),('A','A (m²)',sec.A),('I','I (m⁴)',sec.I)],self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._edit(self.editor.set_elements_properties, ids, **dialog.data)
                self._modified()
            except Exception as exc:
                self._error(exc)

    def delete_selected(self):
        chosen = set(self.selection)
        if not chosen and self.selected is not None:
            chosen.add(self.selected)
        if not chosen:
            return
        nodes = {ident for kind, ident in chosen if kind=='node'}
        elements = {ident for kind, ident in chosen if kind=='element'}
        cascade = {eid for eid, e in self.editor.model.elements.items()
                   if e.node_i in nodes or e.node_j in nodes}
        answer = QMessageBox.question(self,'确认批量删除',
            f'删除 {len(nodes)} 个节点及 {len(elements|cascade)} 根杆件？\n'
            '所涉及的杆件荷载也会删除，此操作可以撤销。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._edit(self.editor.remove_many, node_ids=nodes, element_ids=elements)
            self._modified()
        except Exception as exc:
            self._error(exc)

    def clear_selected_member_loads(self):
        if self.selected is None or self.selected[0]!='element':
            QMessageBox.information(self,'请选择杆件','请先使用“选择”工具点击杆件。')
            return
        eid=self.selected[1]
        self._edit(self.editor.clear_member_loads,eid)
        self._modified()

    def _schedule_autosave(self):
        if self.history.is_dirty:
            self._autosave_debounce.start()
        else:
            self._autosave_debounce.stop()
            self._try_clear_recovery()

    def _try_clear_recovery(self,path=None):
        """Cleanup is ancillary; keep surviving drafts and report failures."""
        try:
            if path is None:
                self.recovery.clear_current()
            else:
                self.recovery.clear_entry(path)
            return True
        except OSError as exc:
            target=path if path is not None else self.recovery.current_path
            self.statusBar().showMessage(
                f'恢复草稿未能清理，文件仍保留，请勿误认为最新版本：{target}；{exc}',0)
            return False

    def _autosave_if_dirty(self):
        if not self.history.is_dirty:
            return
        try:
            self.recovery.checkpoint(self.editor.model, self.file_path)
        except Exception as exc:
            # Avoid modal dialogs every minute: users can still save manually.
            self.statusBar().showMessage(f'自动恢复快照未能保存：{exc}', 12_000)

    def _rotate_recovery(self):
        """Start a new session after a successful document change."""
        self._source_revision=None
        self._autosave_debounce.stop()
        self._try_clear_recovery()
        self.recovery=RecoveryStore(self.recovery.directory)

    def _offer_recovery(self):
        try:
            entries, invalid = self.recovery.scan()
        except OSError as exc:
            self.statusBar().showMessage(f'无法扫描自动恢复目录：{exc}', 12_000)
            return
        # Do not include a live checkpoint belonging to this GUI instance.
        entries=[item for item in entries if item.session_id != self.recovery.session_id]
        if invalid:
            self.statusBar().showMessage(
                f'发现 {len(invalid)} 个损坏的自动恢复文件，已跳过且未删除；位置：{self.recovery.directory}',
                20_000)
        if not entries:
            return
        captions=[]
        for item in entries:
            name=Path(item.source_path).name if item.source_path else '未命名模型'
            captions.append(f'{item.saved_at} | {name} | {item.session_id[:8]}')
        choice, accepted=QInputDialog.getItem(
            self,'选择自动保存的模型',
            '发现意外中断时可能留下的草稿。请选择一份，或取消后稍后从“文件”菜单恢复。',
            captions,0,False)
        if not accepted:
            return
        entry=entries[captions.index(choice)]
        message=QMessageBox(self)
        message.setWindowTitle('恢复未保存的结构模型')
        message.setText(f'快照时间：{entry.saved_at}\n原模型：{entry.source_path or "未命名"}')
        message.setInformativeText('恢复仅载入内存，不会覆盖磁盘上的 JSON。\n'
                                  '选择“删除草稿”会永久删除该份自动保存。')
        restore=message.addButton('恢复草稿',QMessageBox.ButtonRole.AcceptRole)
        discard=message.addButton('删除草稿',QMessageBox.ButtonRole.DestructiveRole)
        message.addButton('暂不处理',QMessageBox.ButtonRole.RejectRole)
        message.exec()
        selected=message.clickedButton()
        if selected is discard:
            self._try_clear_recovery(entry.path)
            return
        if selected is restore:
            self._restore_entry(entry)

    def _restore_entry(self, entry):
        """Restore selected validated entry; never overwrite user's source file."""
        if not self._maybe_save():
            return False
        try:
            # Secure the recovered state in our own session before deleting the old copy.
            self.recovery.checkpoint(entry.model, entry.source_path)
            self.editor.model=entry.model
            self.history.reset()
            self.history.mark_recovered_unsaved()
            self.file_path=Path(entry.source_path) if entry.source_path else None
            # A draft has no trustworthy baseline for the current source file.
            self._source_revision=(FileRevision(self.file_path.resolve(), None)
                                   if self.file_path else None)
            self.selected=None
            self.selection.clear()
            self.pending_node=None
            self.selected_load_index=None
            self.result=None
            self._reset_results()
            self.unsaved=True
            self._redraw()
            self.canvas.fit_all()
            self._update_title()
            self._update_history_actions()
            cleaned=(entry.path == self.recovery.current_path or
                     self._try_clear_recovery(entry.path))
            if cleaned:
                self.statusBar().showMessage('草稿已恢复到内存；请检查后手动保存 JSON。',10000)
            else:
                self.statusBar().showMessage('草稿已恢复到内存，请手动保存；旧恢复草稿未能清理，仍保留在原位置。',0)
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def _maybe_save(self):
        if not self.unsaved:return True
        choice=QMessageBox.question(self,'未保存的修改','是否保存当前结构模型？',
                  QMessageBox.StandardButton.Save |
                  QMessageBox.StandardButton.Discard |
                  QMessageBox.StandardButton.Cancel)
        if choice==QMessageBox.StandardButton.Cancel:return False
        if choice==QMessageBox.StandardButton.Save:return self.save_model()
        return True

    def closeEvent(self,event):
        if self._plot_job is not None:
            # This event runs between generator steps, so cleanup is safe now.
            self._plot_job.close()
            self._plot_job=None
            self._set_solve_busy(False)
            self.solve_progress.setRange(0,0)
            self.cancel_solve_button.setText('取消本次计算')
        if self._solve_thread is not None:
            self.statusBar().showMessage('计算仍在结束中，请稍后关闭；可先取消本次结果。')
            event.ignore()
            return
        if self._maybe_save():
            self._recovery_offer_timer.stop()
            self._autosave_debounce.stop()
            self._autosave_periodic.stop()
            if not self._try_clear_recovery():
                QMessageBox.warning(self,'旧恢复草稿仍保留',
                    '当前保存或放弃操作已完成，但旧恢复草稿无法清理。\n'
                    '下次启动可能再次提示该草稿，请核对时间和内容，勿覆盖最新文件。\n'
                    f'位置：{self.recovery.current_path}')
            event.accept()
        else:
            event.ignore()

    def new_model(self):
        if not self._maybe_save():return
        self.editor.reset()
        self._rotate_recovery()
        self.selected_load_index=None
        self.history.reset()
        self._update_history_actions()
        self.file_path=None
        self.unsaved=False
        self.result=None
        self.selected=None
        self.selection.clear()
        self.pending_node=None
        self._reset_results()
        self._redraw();self.canvas.fit_all();self._update_title()

    def load_example(self,name):
        if not self._maybe_save():return
        try:
            self.editor.load_example(name)
            self._rotate_recovery()
            self.selected_load_index=None
            self.history.reset()
            self._update_history_actions()
            self.file_path=None
            self.unsaved=False
            self.result=None
            self.selected=None
            self.selection.clear()
            self.pending_node=None
            self._reset_results()
            self._redraw();self.canvas.fit_all();self._update_title()
        except Exception as exc:self._error(exc)

    def open_model(self):
        if not self._maybe_save():return
        path,_=QFileDialog.getOpenFileName(self,'打开结构模型','','JSON 模型 (*.json)')
        if not path:return
        try:
            revision=FileRevision.capture(path)
            self.editor.open(path)
            self._rotate_recovery()
            self.selected_load_index=None
            self.history.reset()
            self._update_history_actions()
            self.file_path=Path(path)
            self._source_revision=revision
            self.unsaved=False
            self.result=None
            self.selected=None
            self.selection.clear()
            self.pending_node=None
            self._reset_results()
            self._redraw();self.canvas.fit_all();self._update_title()
        except Exception as exc:self._error(exc)

    def save_model(self,save_as=False):
        path=self.file_path
        if path is None or save_as:
            chosen,_=QFileDialog.getSaveFileName(self,'保存结构模型',
                      str(path or Path.cwd()/'structure.json'),'JSON 模型 (*.json)')
            if not chosen:return False
            path=Path(chosen)
            if path.suffix.lower()!='.json':path=path.with_suffix('.json')
        try:
            if self._source_revision and self._source_revision.conflicts(path):
                choice=self._resolve_save_conflict(path)
                if choice=='save_as':
                    return self.save_model(save_as=True)
                if choice!='overwrite':
                    return False
            self.editor.save(path)
        except Exception as exc:
            self._error(exc)
            return False

        # The model is already committed. Ancillary failures must not turn a
        # successful save into an apparent failure or lose the chosen path.
        self.file_path=path
        self.history.mark_saved()
        self.unsaved=False
        self._autosave_debounce.stop()
        self._update_title()
        warnings=[]
        try:
            self._source_revision=FileRevision.capture(path)
        except OSError as exc:
            # Unknown baseline: require confirmation before replacing an
            # existing source on the next save.
            self._source_revision=FileRevision(Path(path).resolve(),None)
            warnings.append(f'无法读取保存后文件校验信息：{exc}')
        try:
            self.recovery.clear_current()
        except OSError as exc:
            warnings.append(f'旧恢复草稿未能清理，请勿将其误认为最新版本：{exc}')
        message=f'模型已保存：{path}'
        if warnings:
            message+='；'+'；'.join(warnings)
        self.statusBar().showMessage(message,0 if warnings else 5000)
        return True

    def _resolve_save_conflict(self,path):
        dialog=QMessageBox(self)
        dialog.setWindowTitle('文件已被其他程序修改')
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f'磁盘文件已更改或删除，或恢复草稿无法确认原文件版本：\n{path}')
        dialog.setInformativeText('建议另存为保留两份模型。覆盖将替换磁盘版本；取消会保留当前未保存的修改。')
        save_as=dialog.addButton('另存为',QMessageBox.ButtonRole.ActionRole)
        overwrite=dialog.addButton('仍然覆盖',QMessageBox.ButtonRole.DestructiveRole)
        cancel=dialog.addButton('取消',QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(save_as)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        return 'save_as' if dialog.clickedButton() is save_as else (
            'overwrite' if dialog.clickedButton() is overwrite else 'cancel')

    def solve(self):
        """Synchronous entry for scripts/self-test; UI actions use start_solve."""
        if self._solve_thread is not None:
            return
        try:
            mode=Mode(self.mode_combo.currentData())
            self.result=self.editor.solve(mode)
            self._render_results()
            self.main_tabs.setCurrentIndex(1)
            self.statusBar().showMessage('分析完成；切换图形标签时生成对应结果图。',8000)
        except Exception as exc:
            self.result=None
            self._reset_results()
            self._show_solve_error(exc)

    def _show_solve_error(self, exc):
        nodes=set(getattr(exc,'node_ids',())) & set(self.editor.model.nodes)
        if nodes:
            self.selection={('node',n) for n in nodes}
            self.selected=('node',min(nodes))
            self.main_tabs.setCurrentIndex(0)
            self._redraw()
            self.canvas.fit_all()
        self._error(exc)

    def _set_solve_busy(self, busy):
        self.centralWidget().setEnabled(not busy)
        self.menuBar().setEnabled(not busy)
        for toolbar in self.findChildren(QToolBar):
            toolbar.setEnabled(not busy)
        self.solve_progress.setVisible(busy)
        self.cancel_solve_button.setVisible(busy)
        self.cancel_solve_button.setEnabled(busy)

    def start_solve(self):
        if self._solve_thread is not None:
            return
        try:
            issues=check_model(self.editor.model)
            if issues:
                self.result=None
                self._reset_results()
                dialog=ModelCheckDialog(issues,self,before_solve=True)
                if dialog.exec()!=QDialog.DialogCode.Accepted or any(i.severity=='error' for i in issues):
                    return
        except Exception as exc:
            self._error(exc)
            return
        try:
            snapshot=deepcopy(self.editor.model)
            self._solve_snapshot=model_to_dict(snapshot)
            thread=SolveThread(snapshot,Mode(self.mode_combo.currentData()),self)
        except Exception as exc:
            self._show_solve_error(exc)
            return
        self.result=None
        self._reset_results()
        self._solve_cancelled=False
        self._solve_thread=thread
        thread.finished.connect(self._finish_solve)
        self._set_solve_busy(True)
        self.statusBar().showMessage('正在计算，窗口可响应；取消后将丢弃结果并等待当前求解结束。')
        thread.start()

    def manage_load_cases(self):
        from .cases_dialog import CasesDialog
        dialog=CasesDialog(self.editor.model,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            before=self.history.capture()
            self.editor.model=dialog.model
            self.history.commit(before)
            self._modified()

    def check_model_dialog(self):
        if self._solve_thread is not None:return
        try:
            ModelCheckDialog(check_model(self.editor.model),self).exec()
        except Exception as exc:self._error(exc)

    def _locate_issue(self,issue):
        self.selection=({('node',n) for n in issue.nodes if n in self.editor.model.nodes} |
                        {('element',e) for e in issue.elements if e in self.editor.model.elements})
        self.selected=next(iter(sorted(self.selection)),None)
        self.main_tabs.setCurrentIndex(0)
        # Diagnostic rendering must not evaluate the invalid geometry/material
        # that caused the issue. Use a read-only display copy, not editor repair.
        display=deepcopy(self.editor.model)
        display.elements={eid:e for eid,e in display.elements.items()
                          if e.node_i in display.nodes and e.node_j in display.nodes}
        display.member_loads=[]
        display.loads={}
        display.constraints={key:value for key,value in display.constraints.items()
                             if key[0] in display.nodes and key[1] in ('ux','uy','rz')
                             and isinstance(value,(int,float)) and math.isfinite(value)}
        self.canvas.redraw(display,self.selection,show_dimensions=False)
        self.info.setText('问题定位（检查视图暂不显示荷载与尺寸）\n'+issue.message)
        nodes=set(issue.nodes)
        for eid in issue.elements:
            element=self.editor.model.elements.get(eid)
            if element:nodes.update((element.node_i,element.node_j))
        points=[_point(self.editor.model.nodes[n]) for n in nodes if n in self.editor.model.nodes]
        if points:
            left,right=min(p.x() for p in points),max(p.x() for p in points)
            top,bottom=min(p.y() for p in points),max(p.y() for p in points)
            self.canvas.fitInView(QRectF(left-80,top-80,right-left+160,bottom-top+160),Qt.AspectRatioMode.KeepAspectRatio)
        self.statusBar().showMessage(issue.message,10000)

    def cancel_solve(self):
        if self._plot_job is not None:
            self._plot_cancelled=True
            self.cancel_solve_button.setEnabled(False)
            return
        if self._solve_thread is not None:
            self._solve_cancelled=True
            self.cancel_solve_button.setEnabled(False)
            self.statusBar().showMessage('已取消本次结果，等待当前数值求解安全结束…')

    def _finish_solve(self):
        thread=self._solve_thread
        if thread is None:
            return
        self._solve_thread=None
        self._set_solve_busy(False)
        try:
            if self._solve_cancelled:
                self.statusBar().showMessage('本次计算已取消。',8000)
            elif model_to_dict(self.editor.model)!=self._solve_snapshot:
                self.statusBar().showMessage('模型已变化，已丢弃旧计算结果，请重新计算。',8000)
            elif thread.error is not None:
                self._show_solve_error(thread.error)
            else:
                self.result=thread.result
                self._render_results()
                self.main_tabs.setCurrentIndex(1)
                self.statusBar().showMessage('分析完成；切换图形标签时生成对应结果图。',8000)
        except Exception as exc:
            self.result=None
            self._reset_results()
            self._show_solve_error(exc)
        finally:
            thread.deleteLater()

    def _render_results(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        self._reset_results()
        result=self.result
        model=self.editor.model
        lines=['二维线弹性静力计算结果（SI 单位）',
               '='*45,
               f'节点数：{len(model.nodes)}  单元数：{len(model.elements)}  自由度数：{result.dof_manager.ndof}',
               f'模式：{self.mode_combo.currentData()}',
               '', '节点自由度       位移 (m/rad)         反力 (N/N·m)',
               '-'*60]
        for (node_id,dof),idx in sorted(result.dof_manager.mapping.items(),key=lambda pair:pair[1]):
            lines.append(f'{node_id:>5} {dof:<4} {result.displacements[idx]:>20.9g} {result.reactions[idx]:>20.9g}')
        lines.extend(['','单元局部杆端力（N / N·m）','-'*60])
        for eid,force in sorted(result.element_end_forces_local.items()):
            lines.append(f'{eid:>5}: '+', '.join(f'{x:.8g}' for x in force))
        self.summary.setPlainText('\n'.join(lines))
        from .result_table import result_tables
        for title,table in result_tables(model,result):
            self.result_tabs.addTab(table,title)
        self._build_inspector()
        for title in ('轴力 N','剪力 V','弯矩 M','变形图'):
            figure=Figure(figsize=(8,6),dpi=100)
            canvas=FigureCanvasQTAgg(figure)
            if title in ('轴力 N','剪力 V','弯矩 M'):
                canvas.mpl_connect('pick_event',self._on_diagram_pick)
            self.result_tabs.addTab(canvas,title)
            self.figures[title]=figure

    def _on_diagram_pick(self,event):
        """Query a picked Matplotlib force trace at its actual sample station."""
        if self.result is None or self.inspect_text is None:
            return
        artist = getattr(event,'artist',None)
        gid = artist.get_gid() if hasattr(artist,'get_gid') else None
        if not gid or not gid.startswith('md-member:'):
            return
        try:
            _, eid, component = gid.split(':')
            eid = int(eid)
            candidates = list(event.ind)
            if not candidates:
                return
            points = list(zip(artist.get_xdata(),artist.get_ydata()))
            px,py = event.mouseevent.x,event.mouseevent.y
            index = min(candidates,key=lambda i: sum((a-b)**2 for a,b in zip(
                artist.axes.transData.transform(points[int(i)]),(px,py))))
            picked = diagram_pick(self.editor.model,self.result,eid,component,int(index))
            self.selected=('element',eid)
            self.selection={self.selected}
            self._redraw()
            target=self.inspect_element_box.findData(eid)
            if target>=0:
                self.inspect_element_box.setCurrentIndex(target)
            self.inspect_x.setValue(picked.section.x)
            side_idx=self.inspect_side.findData(picked.section.side)
            if side_idx>=0:
                self.inspect_side.setCurrentIndex(side_idx)
            self._update_inspector()
            for tab in range(self.result_tabs.count()):
                if self.result_tabs.tabText(tab)=='杆件截面查询':
                    self.result_tabs.setCurrentIndex(tab)
                    break
            self.statusBar().showMessage(
                f'E{eid} x={picked.section.x:.5g}m ({picked.section.side}), '
                f'{component}={getattr(picked.section,component):.6g}',8000)
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            self.statusBar().showMessage(f'无法查询该图形位置：{exc}',5000)

    def _build_inspector(self):
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.addWidget(QLabel('选择杆件和局部坐标 x，查询截面内力与变形；集中力点可选择左/右极限。'))
        form=QFormLayout()
        self.inspect_element_box=QComboBox()
        for eid in sorted(self.editor.model.elements):
            self.inspect_element_box.addItem(f'E{eid}',eid)
        self.inspect_element_box.currentIndexChanged.connect(self._inspection_element_changed)
        form.addRow('杆件',self.inspect_element_box)
        self.inspect_x=QDoubleSpinBox()
        self.inspect_x.setDecimals(12)
        self.inspect_x.setSingleStep(.1)
        self.inspect_x.setSuffix(' m')
        self.inspect_x.valueChanged.connect(self._update_inspector)
        form.addRow('距 i 端位置 x',self.inspect_x)
        self.inspect_side=QComboBox()
        self.inspect_side.addItem('右侧极限','right')
        self.inspect_side.addItem('左侧极限','left')
        self.inspect_side.currentIndexChanged.connect(self._update_inspector)
        form.addRow('集中力位置',self.inspect_side)
        layout.addLayout(form)
        self.inspect_text=QPlainTextEdit()
        self.inspect_text.setReadOnly(True)
        layout.addWidget(self.inspect_text)
        self.result_tabs.addTab(page,'杆件截面查询')
        self._inspection_element_changed(select=False)

    def _inspection_element_changed(self,*args,select=True):
        if self.result is None or self.inspect_element_box.count()==0:return
        eid=self.inspect_element_box.currentData()
        if select and self.selected != ('element',eid):
            self.selected=('element',eid)
            self.selection={self.selected}
            self._redraw()
        L=self.editor.model.elements[eid].geometry(self.editor.model)[0]
        self.inspect_x.blockSignals(True)
        self.inspect_x.setRange(0,L)
        self.inspect_x.setValue(L/2)
        self.inspect_x.blockSignals(False)
        self._update_inspector()

    def _update_inspector(self,*args):
        if self.result is None or self.inspect_text is None:return
        if self._drag_node is not None:
            self.inspect_text.setPlainText('节点拖动中；松开鼠标后需重新求解，旧结果不适用。')
            return
        try:
            if self.selected and self.selected[0]=='node':
                report=inspect_node(self.editor.model,self.result,self.selected[1])
                lines=[f'节点 {report.node_id} 自由度查询','-'*55]
                for dof,displacement,reaction,known in report.entries:
                    unit='rad' if dof=='rz' else 'm'
                    ru='N·m' if dof=='rz' else 'N'
                    lines.append(f'{dof}: 位移={displacement:.9g} {unit}, '
                                 f'反力={reaction:.9g} {ru}, 已知位移={known}')
                self.inspect_text.setPlainText('\n'.join(lines))
                return
            if self.inspect_element_box.count()==0:return
            if self.selected and self.selected[0]=='element':
                selected_eid=self.selected[1]
                if self.inspect_element_box.currentData()!=selected_eid:
                    target=self.inspect_element_box.findData(selected_eid)
                    if target>=0:
                        self.inspect_element_box.setCurrentIndex(target)
                        return
            eid=self.inspect_element_box.currentData()
            report=inspect_member(self.editor.model,self.result,eid,
                    x=self.inspect_x.value(),side=self.inspect_side.currentData())
            lines=[f'杆件 E{eid}：{report.element_type}',
                   f'杆长 L={report.length:.7g} m；x={report.x:.7g} m ({report.side} 极限)',
                   '-'*56,
                   f'N(x)={report.N:.9g} N',f'V(x)={report.V:.9g} N',
                   f'M(x)={report.M:.9g} N·m',
                   f'ux(global)={report.displacement_global_x:.9g} m',
                   f'uy(global)={report.displacement_global_y:.9g} m',
                   f'转角 θ={report.rotation:.9g} rad',
                   '', '内力范围（基于截面采样，非全局严格极值）：']
            for key,(lo,hi) in report.ranges.items():
                lines.append(f'{key}: 最小={lo:.8g}，最大={hi:.8g}')
            self.inspect_text.setPlainText('\n'.join(lines))
        except Exception as exc:
            self.inspect_text.setPlainText(f'查询失败：{exc}')

    def _require_result(self):
        if self.result is None:
            QMessageBox.information(self,'尚未计算','请先点击“计算并显示结果”，然后导出。')
            return False
        return True

    def _export_start_directory(self):
        if self._export_directory is not None and self._export_directory.is_dir():
            return self._export_directory
        if self.file_path is not None and self.file_path.parent.is_dir():
            return self.file_path.parent
        return Path.cwd()

    def _export_default_file(self, name):
        prefix=f'{self.file_path.stem}_' if self.file_path else ''
        return str(self._export_start_directory()/(prefix+name))

    def export_report(self):
        if not self._require_result():return
        if self.result.trace is None:
            QMessageBox.information(self,'需要教学模式','请切换“教学模式”并重新计算，才能导出组装过程。')
            return
        path,_=QFileDialog.getSaveFileName(self,'导出教学报告',self._export_default_file('teaching_report.md'),
                                          'Markdown 文件 (*.md)')
        if not path:return
        try:
            save_teaching_report(self.editor.model,self.result,path)
            self._export_directory=Path(path).resolve().parent
            self.statusBar().showMessage(f'教学报告已导出：{path}',7000)
        except Exception as exc:self._error(exc)

    @staticmethod
    def _new_export_directory(parent, name):
        index=0
        while True:
            candidate=Path(parent)/(name if index==0 else f'{name}_{index:03d}')
            try:
                candidate.mkdir()
                return candidate
            except FileExistsError:
                index+=1

    def export_csv(self):
        if not self._require_result():return
        path=QFileDialog.getExistingDirectory(self,'选择 CSV 输出文件夹',str(self._export_start_directory()))
        if not path:return
        directory=None
        try:
            directory=self._new_export_directory(path,'csv_results')
            export_results_csv(self.editor.model,self.result,directory,points=101)
            self._export_directory=Path(path).resolve()
            self.statusBar().showMessage(f'结果 CSV 已导出至：{directory}',7000)
        except Exception as exc:
            self._error(exc)
            if directory is not None:
                self.statusBar().showMessage(f'CSV 导出未完成：{directory}（可能包含部分文件，请勿作为完整结果使用）')

    def export_all_figures(self):
        if not self._require_result():return
        titles=('轴力 N','剪力 V','弯矩 M','变形图')
        if any(title not in self.figures for title in titles):
            QMessageBox.information(self,'结果图不完整','请重新计算后再导出全部结果图。')
            return
        path=QFileDialog.getExistingDirectory(self,'选择全部结果图输出文件夹',str(self._export_start_directory()))
        if not path:return
        directory=None
        completed=0
        try:
            prefix=f'{self.file_path.stem}_' if self.file_path else ''
            directory=self._new_export_directory(path,prefix+'result_figures')
            for title in titles:
                self._ensure_figure(title).savefig(directory/f'{prefix}{title}.png',dpi=160,bbox_inches='tight')
                completed+=1
            self._export_directory=Path(path).resolve()
            self.statusBar().showMessage(f'全部 4 张结果图已导出至：{directory}',10000)
        except Exception as exc:
            self._error(exc)
            if directory is not None:
                self.statusBar().showMessage(f'结果图导出未完成（{completed}/4）：{directory}（可能包含不完整文件）')

    def export_figure(self):
        if not self._require_result():return
        key=self.result_tabs.tabText(self.result_tabs.currentIndex())
        if key not in self.figures:
            QMessageBox.information(self,'请选择图形','请先在计算结果页面选择轴力图、剪力图、弯矩图或变形图。')
            return
        path,_=QFileDialog.getSaveFileName(self,'保存结果图',self._export_default_file(f'{key}.png'),'PNG 图片 (*.png)')
        if not path:return
        try:
            self._ensure_figure(key).savefig(path,dpi=160,bbox_inches='tight')
            self._export_directory=Path(path).resolve().parent
            self.statusBar().showMessage(f'已保存结果图：{path}',7000)
        except Exception as exc:self._error(exc)


def main(argv=None):
    """Normal GUI entrypoint, or headless Qt+solver acceptance via --self-test."""
    argv=list(sys.argv if argv is None else argv)
    self_test='--self-test' in argv
    if self_test:
        argv.remove('--self-test')
    app=QApplication(argv)
    app.setApplicationName('矩阵位移法教学系统')
    if self_test:
        from tempfile import TemporaryDirectory
        from matrix_displacement.recovery import RecoveryStore
        import os
        with TemporaryDirectory(prefix='matrix-displacement-smoke-') as folder:
            previous=os.environ.get('MATRIX_DISPLACEMENT_RECOVERY_DIR')
            os.environ['MATRIX_DISPLACEMENT_RECOVERY_DIR']=folder
            window=None
            try:
                window=MainWindow()
                window.show()
                app.processEvents()
                window.solve()
                app.processEvents()
                if window.result is None or len(window.figures) != 4:
                    raise RuntimeError('Qt self-test did not render the four analysis figures')
                solved=window.result
                for mode in ('none','extrema','all'):
                    window.force_labels.setCurrentIndex(window.force_labels.findData(mode))
                    app.processEvents()
                    if window.result is not solved:
                        raise RuntimeError('Label mode changed the analysis result')
                    figure=window._ensure_figure('弯矩 M')
                    labels=[t for t in figure.axes[0].texts if t.get_text().startswith('E')]
                    if bool(labels)!=(mode!='none'):
                        raise RuntimeError('Label mode did not update the diagram')
                    image_path=Path(folder)/f'moment_{mode}.png'
                    figure.savefig(image_path,dpi=160,bbox_inches='tight')
                    if image_path.stat().st_size==0:
                        raise RuntimeError('Diagram export produced an empty file')
                # Exercise the real export handlers without native file dialogs.
                original_directory_dialog=QFileDialog.getExistingDirectory
                try:
                    QFileDialog.getExistingDirectory=lambda *args: folder
                    window.export_csv()
                    window.export_csv()
                    for _ in range(2):
                        window.start_export_all()
                        deadline=time.monotonic()+60
                        while window._plot_job is not None and time.monotonic()<deadline:
                            app.processEvents()
                            time.sleep(.001)
                        if window._plot_job is not None:
                            raise RuntimeError('Incremental export did not finish')
                    for name in ('csv_results','csv_results_001'):
                        if len(list((Path(folder)/name).glob('*.csv')))!=4:
                            raise RuntimeError('CSV export did not preserve both batches')
                    for name in ('result_figures','result_figures_001'):
                        if len(list((Path(folder)/name).glob('*.png')))!=4:
                            raise RuntimeError('Batch figure export failed')
                finally:
                    QFileDialog.getExistingDirectory=original_directory_dialog
                from matrix_displacement.load_cases import capture_case, combination_model
                from matrix_displacement.io import save_model_json, load_model_json
                from .cases_dialog import CasesDialog
                from .result_table import ResultTable
                unit_dialog=PropertiesDialog(210e9,.01,8e-6)
                unit_dialog.inputs['E'].setText('210 GPa')
                unit_dialog.accept()
                if unit_dialog.data['E']!=210e9:raise RuntimeError('Unit conversion failed')
                unit_dialog.deleteLater()
                case_dialog=CasesDialog(window.editor.model)
                case_dialog.name.setText('G');case_dialog.save_case()
                case_dialog.model.load_combinations['2G']={'G':2.0}
                save_model_json(case_dialog.model,Path(folder)/'cases.json')
                loaded=load_model_json(Path(folder)/'cases.json')
                combined=combination_model(loaded,loaded.load_combinations['2G'])
                if abs(LinearStaticSolver().solve(combined).reaction(1,'uy')-11000)>1e-7:
                    raise RuntimeError('Load combination failed')
                case_dialog.deleteLater()
                tables=window.findChildren(ResultTable)
                if len(tables)!=2:raise RuntimeError('Result tables missing')
                tables[0].selectAll();tables[0].copy_selection()
                if not QApplication.clipboard().text():raise RuntimeError('Result copy failed')
                window.history.execute(window.editor.add_node,7.0,2.0)
                window._modified()
                window._autosave_if_dirty()
                if len(RecoveryStore(folder).scan()[0]) != 1:
                    raise RuntimeError('Qt self-test did not create an autosave checkpoint')
                window.history.mark_saved()
                window.unsaved=False
                window.close()
                return 0
            finally:
                if window is not None:
                    window.deleteLater()
                if previous is None:
                    os.environ.pop('MATRIX_DISPLACEMENT_RECOVERY_DIR',None)
                else:
                    os.environ['MATRIX_DISPLACEMENT_RECOVERY_DIR']=previous
    window=MainWindow()
    window.show()
    return app.exec()
