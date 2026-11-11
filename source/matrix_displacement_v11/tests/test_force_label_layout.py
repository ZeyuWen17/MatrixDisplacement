import itertools
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matrix_displacement import Node,Material,Section,Frame2D,StructuralModel,LinearStaticSolver,plot_force_diagram


def portal_grid():
    model=StructuralModel()
    model.add_material(Material(1,210e9))
    model.add_section(Section(1,.01,8e-6))
    for row in range(3):
        for col in range(3):
            nid=row*3+col+1
            model.add_node(Node(nid,col*3,row*3))
            if row==0:
                for dof in ('ux','uy','rz'): model.constrain(nid,dof)
            else:
                model.add_load(nid,'ux',1000)
                model.add_load(nid,'uy',-2000)
    pairs=[(r*3+c+1,(r+1)*3+c+1) for r in range(2) for c in range(3)]
    pairs += [(r*3+c+1,r*3+c+2) for r in (1,2) for c in range(2)]
    for eid,(i,j) in enumerate(pairs,1):model.add_element(Frame2D(eid,i,j,1,1))
    return model


def test_dense_frame_labels_resize_and_export(tmp_path):
    model=portal_grid()
    result=LinearStaticSolver().solve(model)
    ax=plot_force_diagram(model,result,'M',value_mode='all')
    fig=ax.figure
    try:
        for size in ((8,6),(11,8)):
            fig.set_size_inches(*size)
            fig.canvas.draw()
            renderer=fig.canvas.get_renderer()
            labels=[t for t in ax.texts if t.get_text().startswith('E')]
            assert len(labels)>=20
            boxes=[Text.get_window_extent(t,renderer) for t in labels]
            assert not any(a.overlaps(b) for a,b in itertools.combinations(boxes,2))
            positions=[t.get_position() for t in labels]
            fig.canvas.draw()
            assert positions==[t.get_position() for t in labels]
        fig.savefig(tmp_path/'dense.png',dpi=160,bbox_inches='tight')
    finally:
        plt.close(fig)


def test_layout_cache_invalidates_for_geometry_text_and_export(monkeypatch,tmp_path):
    from matrix_displacement import label_layout
    calls=[]
    original=label_layout.place_labels
    def tracked(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr(label_layout,'place_labels',tracked)
    model=portal_grid()
    ax=plot_force_diagram(model,LinearStaticSolver().solve(model),'M')
    fig=ax.figure
    try:
        fig.canvas.draw()
        count=len(calls)
        assert count>0
        fig.canvas.draw()
        assert len(calls)==count
        fig.set_size_inches(11,8)
        fig.canvas.draw()
        assert len(calls)>count
        count=len(calls)
        label=next(t for t in ax.texts if t.get_text().startswith('E'))
        label.set_fontsize(label.get_fontsize()+4)
        fig.canvas.draw()
        assert len(calls)>count
        count=len(calls)
        fig.savefig(tmp_path/'different-dpi.png',dpi=160,bbox_inches='tight')
        assert len(calls)>count
        fig.canvas.draw()
        count=len(calls)
        fig.canvas.draw()
        assert len(calls)==count
    finally:
        plt.close(fig)
