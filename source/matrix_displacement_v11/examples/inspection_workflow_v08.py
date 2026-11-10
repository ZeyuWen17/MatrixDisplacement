"""V0.8 no-Qt inspection + undo/redo workflow; execute from project root.

python -m examples.inspection_workflow_v08
"""
from pathlib import Path
from matrix_displacement.editor import ModelEditor
from matrix_displacement.history import EditHistory
from matrix_displacement.inspection import inspect_node,inspect_member
from matrix_displacement.core import Mode
from matrix_displacement.io import save_model_json,load_model_json


def main():
    directory=Path('outputs/examples/artifacts_v08')
    directory.mkdir(exist_ok=True)
    editor=ModelEditor()
    editor.load_example('cantilever')
    history=EditHistory(editor)
    result=editor.solve(Mode.TEACHING)
    report=[]
    report.append('V0.8: 无 Qt 的交互查询示例（SI 单位）')
    report.append('节点 2:')
    node=inspect_node(editor.model,result,2)
    for dof,displacement,reaction,known in node.entries:
        report.append(f'  {dof}: displacement={displacement:.9g}, reaction={reaction:.9g}, fixed={known}')
    report.append('杆件 1: x=1.7 m 集中力两侧')
    left=inspect_member(editor.model,result,1,x=1.7,side='left')
    right=inspect_member(editor.model,result,1,x=1.7,side='right')
    report.append(f'  V(left)={left.V:.9g} N; V(right)={right.V:.9g} N')
    report.append(f'  M(left)={left.M:.9g} N*m; M(right)={right.M:.9g} N*m')
    assert abs(right.V-left.V+700)<1e-7
    history.execute(editor.move_node,2,5,0)
    assert editor.model.nodes[2].x==5
    history.undo()
    assert editor.model.nodes[2].x==4
    history.redo()
    assert editor.model.nodes[2].x==5
    history.undo()
    history.mark_saved()
    model_path=directory/'structure_v08.json'
    save_model_json(editor.model,model_path)
    assert load_model_json(model_path).nodes[2].x==4
    output=directory/'inspection_report_v08.txt'
    output.write_text('\n'.join(report)+'\n',encoding='utf-8')
    print('\n'.join(report))
    print(f'已导出: {model_path}, {output}')


if __name__=='__main__':
    main()
