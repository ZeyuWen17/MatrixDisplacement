"""V0.6 example: triangular member load, assembly trace, JSON and CSV.

Run from the project root:
  python -m examples.linear_load_v06
  python -m examples.linear_load_v06 --output artifacts_v06
"""
from argparse import ArgumentParser
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from matrix_displacement import (
    Node, Material, Section, Beam2D, StructuralModel, LinearStaticSolver, Mode,
    BeamResponse2D, save_model_json, load_model_json, save_teaching_report,
    export_results_csv, plot_structure, plot_force_diagram, plot_deformed_shape,
)


def make_triangular_beam():
    """Simply supported beam, L=6m, q_i=0 -> q_j=-1500N/m."""
    m = StructuralModel()
    m.add_node(Node(1,0,0))
    m.add_node(Node(2,6,0))
    m.add_material(Material(1,210e9))
    m.add_section(Section(1,0.01,8e-6))
    m.add_element(Beam2D(1,1,2,1,1))
    m.constrain(1,'uy')
    m.constrain(2,'uy')
    m.add_linear_load(1,qy_i=0,qy_j=-1500,system='local')
    return m


def main(argv=None):
    parser=ArgumentParser(description='V0.6 linearly varying beam load demonstration')
    parser.add_argument('--output',default='artifacts_v06')
    args=parser.parse_args(argv)
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    original=make_triangular_beam()
    save_model_json(original,out/'triangular_beam.json')
    model=load_model_json(out/'triangular_beam.json')
    result=LinearStaticSolver(Mode.TEACHING).solve(model)
    fast=LinearStaticSolver(Mode.FAST).solve(model)
    np.testing.assert_allclose(result.displacements,fast.displacements)
    np.testing.assert_allclose(result.reactions,fast.reactions)
    save_teaching_report(model,result,out/'teaching_report.md')
    export_results_csv(model,result,out/'csv',points=101)
    response=BeamResponse2D(model,result,1)
    x=6/np.sqrt(3)
    print('V0.6 | triangular transverse load: q_i=0, q_j=-1.5 kN/m')
    print(f'Support A reaction: {result.reaction(1,"uy")/1000:.6f} kN (expected 1.5)')
    print(f'Support B reaction: {result.reaction(2,"uy")/1000:.6f} kN (expected 3.0)')
    print(f'Max bending moment: {response.section(x).M/1000:.6f} kN*m at x={x:.5f} m')
    figures=[('structure.png',lambda:plot_structure(model,show_loads=True)),
             ('shear.png',lambda:plot_force_diagram(model,result,'V')),
             ('moment.png',lambda:plot_force_diagram(model,result,'M')),
             ('deformation.png',lambda:plot_deformed_shape(model,result))]
    for fname,render in figures:
        ax=render()
        ax.figure.savefig(out/fname,dpi=150,bbox_inches='tight')
        plt.close(ax.figure)
    print(f'Outputs saved to {out.resolve()}')


if __name__ == '__main__':
    main()
