"""V0.3: save 2D frame N/V/M and true deformed-shape PNG figures.

Run from project root:
    python -m examples.diagrams
Optional output directory:
    python -m examples.diagrams --output figures
"""
import argparse
from pathlib import Path

from matrix_displacement import (
    Node, Material, Section, Frame2D, StructuralModel, Mode, LinearStaticSolver,
    MemberResponse2D, plot_force_diagram, plot_deformed_shape, plot_structure,
)


def make_example():
    model = StructuralModel()
    model.add_node(Node(1, 0, 0))
    model.add_node(Node(2, 4, 0))
    model.add_material(Material(1, 210e9))
    model.add_section(Section(1, 0.015, 8e-6))
    model.add_element(Frame2D(1, 1, 2, 1, 1))
    for d in ('ux', 'uy', 'rz'):
        model.constrain(1, d)
    model.add_uniform_load(1, qy=-1200)
    model.add_point_load(1, position=1.7, fy=-700)
    return model


def main():
    parser = argparse.ArgumentParser(description='Export V0.3 diagrams as PNG')
    parser.add_argument('--output',default='figures',help='Output folder for PNGs')
    args=parser.parse_args()
    # Headless-friendly: the example writes PNG, never opens an interactive GUI.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    model=make_example()
    result=LinearStaticSolver(Mode.TEACHING).solve(model)
    response=MemberResponse2D(model,result,1)
    print('Fixed support Fy (N):', result.reaction(1,'uy'))
    print('Fixed support moment (N m):', result.reaction(1,'rz'))
    print('Free tip vertical deflection (mm):',result.displacement(2,'uy')*1000)
    print('Section at x=1.7 m, left: ',response.section(1.7,'left'))
    print('Section at x=1.7 m, right:',response.section(1.7,'right'))
    plotters=[
        ('structure.png',lambda:plot_structure(model)),
        ('axial_N.png',lambda:plot_force_diagram(model,result,'N')),
        ('shear_V.png',lambda:plot_force_diagram(model,result,'V')),
        ('moment_M.png',lambda:plot_force_diagram(model,result,'M')),
        ('deformation.png',lambda:plot_deformed_shape(model,result)),
    ]
    for filename,draw in plotters:
        ax=draw()
        path=out/filename
        ax.figure.savefig(path,dpi=180,bbox_inches='tight')
        plt.close(ax.figure)
        print('Saved:',path.resolve())


if __name__=='__main__':
    main()
