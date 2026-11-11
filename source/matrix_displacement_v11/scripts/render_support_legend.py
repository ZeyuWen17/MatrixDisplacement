"""Render the actual Qt canvas support symbols for documentation and visual review."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter,QFont,QFontDatabase
from PySide6.QtWidgets import QApplication
from matrix_displacement import StructuralModel,Node,Material,Section,Beam2D
from matrix_displacement.gui.main import ModelCanvas

app=QApplication.instance() or QApplication([])
# Qt's offscreen platform may not enumerate Windows system fonts.
font_path=Path(os.environ.get('SYSTEMROOT','C:/Windows'))/'Fonts/msyh.ttc'
if font_path.exists():QFontDatabase.addApplicationFont(str(font_path))
app.setFont(QFont('Microsoft YaHei',10))
model=StructuralModel()
cases=[('ux','uy','rz'),('ux','uy'),('uy',),('ux',),('rz',),('uy','rz'),('ux','rz'),('uy','rz')]
for nid,dofs in enumerate(cases,1):
    model.add_node(Node(nid,((nid-1)%4)*5,-((nid-1)//4)*4))
    for dof in dofs:model.constrain(nid,dof)
model.constraints[(7,'ux')]=.002
model.add_node(Node(9,17,-4))
model.add_material(Material(1,2e11));model.add_section(Section(1,.01,8e-6))
model.add_element(Beam2D(1,8,9,1,1))
canvas=ModelCanvas()
canvas.redraw(model,show_dimensions=False)
scene=canvas.canvas_scene
for item in scene.items():
    if hasattr(item,'setFont'):item.setFont(QFont('Microsoft YaHei',10))
image=QImage(1600,700,QImage.Format.Format_ARGB32)
image.fill('white')
painter=QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
scene.render(painter,QRectF(20,20,1560,660),scene.itemsBoundingRect().adjusted(-30,-55,50,30))
painter.end()
target=Path('docs/assets/support-symbols-v118.png')
assert image.save(str(target))
print(target.resolve())
