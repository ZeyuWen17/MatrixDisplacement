"""V0.4 pinned-end beam and triangular truss with PNG exports.

Run:
    python -m examples.release_and_truss --output figures_v04
"""
import argparse
from pathlib import Path
from matrix_displacement import (
    Node, Material, Section, Frame2D, Truss2D, StructuralModel,
    LinearStaticSolver, Mode, MemberResponse2D, TrussResponse2D,
    plot_structure, plot_force_diagram, plot_deformed_shape,
)


def build_fixed_pinned_beam():
    m=StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,4,0))
    m.add_material(Material(1,210e9));m.add_section(Section(1,.012,8e-6))
    # Right-end hinge: end moment M_j=0, rotational DOF removed by condensation.
    m.add_element(Frame2D(1,1,2,1,1,release_j=True))
    for d in ('ux','uy','rz'):m.constrain(1,d)
    for d in ('ux','uy'):m.constrain(2,d)
    m.add_uniform_load(1,qy=-1000)
    return m


def build_triangle_truss():
    m=StructuralModel()
    for nid,x,y in [(1,0,0),(2,4,0),(3,2,3)]:
        m.add_node(Node(nid,x,y))
    m.add_material(Material(1,210e9))
    m.add_section(Section(1,.012,8e-6))  # I is ignored for Truss2D
    for eid,ni,nj in [(1,1,2),(2,1,3),(3,2,3)]:
        m.add_element(Truss2D(eid,ni,nj,1,1))
    m.constrain(1,'ux');m.constrain(1,'uy');m.constrain(2,'uy')
    m.add_load(3,'uy',-3000)
    return m


def main():
    parser=argparse.ArgumentParser(description='Export V0.4 released beam and truss figures')
    parser.add_argument('--output',default='figures_v04')
    args=parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    beam=build_fixed_pinned_beam()
    br=LinearStaticSolver(Mode.TEACHING).solve(beam)
    print('Fixed-pinned beam: support Ay=',br.reaction(1,'uy'),'N')
    print('Fixed-pinned beam: support By=',br.reaction(2,'uy'),'N')
    print('Fixed-pinned beam: released end Mj=',br.element_end_forces_local[1][5],'N m')
    print('Fixed-pinned beam: physical hinge slope=',MemberResponse2D(beam,br,1).deformation(4).rz,'rad')
    truss=build_triangle_truss()
    tr=LinearStaticSolver(Mode.FAST).solve(truss)
    for eid in truss.elements:
        print(f'Triangle truss: member {eid} axial force=',TrussResponse2D(truss,tr,eid).N,'N')
    figures=(
        ('hinged_beam_moment.png',lambda:plot_force_diagram(beam,br,'M')),
        ('hinged_beam_deformation.png',lambda:plot_deformed_shape(beam,br)),
        ('triangle_truss_axial.png',lambda:plot_force_diagram(truss,tr,'N')),
        ('triangle_truss_deformation.png',lambda:plot_deformed_shape(truss,tr)),
        ('triangle_truss_structure.png',lambda:plot_structure(truss)),
    )
    for filename,draw in figures:
        ax=draw()
        ax.figure.savefig(out/filename,dpi=150,bbox_inches='tight')
        plt.close(ax.figure)
        print('Saved:',(out/filename).resolve())


if __name__=='__main__':
    main()
