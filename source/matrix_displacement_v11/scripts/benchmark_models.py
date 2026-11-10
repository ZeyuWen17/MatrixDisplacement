"""Reproducible grid-frame solve and drawing benchmark; no speed assertions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,time,platform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matrix_displacement import Node,Material,Section,Frame2D,StructuralModel,LinearStaticSolver,Mode,plot_force_diagram

def grid(bays,stories):
    model=StructuralModel()
    model.add_material(Material(1,210e9));model.add_section(Section(1,.02,8e-5))
    for row in range(stories+1):
        for col in range(bays+1):
            nid=row*(bays+1)+col+1
            model.add_node(Node(nid,col*4,row*3))
            if row==0:
                for dof in ('ux','uy','rz'):model.constrain(nid,dof)
            else:
                model.add_load(nid,'ux',1000);model.add_load(nid,'uy',-10000)
    pairs=[(r*(bays+1)+c+1,(r+1)*(bays+1)+c+1) for r in range(stories) for c in range(bays+1)]
    pairs += [(r*(bays+1)+c+1,r*(bays+1)+c+2) for r in range(1,stories+1) for c in range(bays)]
    for eid,(i,j) in enumerate(pairs,1):model.add_element(Frame2D(eid,i,j,1,1))
    return model

if __name__=='__main__':
    destination=Path(sys.argv[1] if len(sys.argv)>1 else 'reports/validation/performance-v116.json')
    rows=[]
    for bays,stories in ((5,5),(10,10),(15,10)):
        model=grid(bays,stories)
        start=time.perf_counter();result=LinearStaticSolver(Mode.FAST).solve(model);solve=time.perf_counter()-start
        for mode in ('none','extrema','all'):
            start=time.perf_counter()
            ax=plot_force_diagram(model,result,'M',value_mode=mode,points=101)
            ax.figure.canvas.draw()
            elapsed=time.perf_counter()-start
            rows.append(dict(nodes=len(model.nodes),elements=len(model.elements),dofs=result.dof_manager.ndof,mode=mode,solve_s=round(solve,4),plot_s=round(elapsed,4)))
            plt.close(ax.figure)
            print(rows[-1],flush=True)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(dict(python=platform.python_version(),platform=platform.platform(),measurements=rows),ensure_ascii=False,indent=2),encoding='utf-8')
