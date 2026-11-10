"""V0.5 example: a two-span beam + JSON + teaching Markdown + plots.

Run from project root:
    python -m examples.continuous_beam
    python -m examples.continuous_beam --output my_results
"""
from argparse import ArgumentParser
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from matrix_displacement import (
    Node, Material, Section, Beam2D, StructuralModel,
    Mode, LinearStaticSolver, BeamResponse2D,
    save_model_json, load_model_json, save_teaching_report,
    plot_structure, plot_force_diagram, plot_deformed_shape,
)


def make_two_span_beam():
    """Equal spans, constant EI, downward q=1 kN/m on each span."""
    m = StructuralModel()
    for nid, x in ((1,0.0),(2,4.0),(3,8.0)):
        m.add_node(Node(nid,x,0.0))
    m.add_material(Material(1,210e9))
    m.add_section(Section(1,0.012,8e-6))
    m.add_element(Beam2D(1,1,2,1,1))
    m.add_element(Beam2D(2,2,3,1,1))
    for nid in (1,2,3):
        m.constrain(nid,'uy')
    for eid in (1,2):
        m.add_uniform_load(eid,qy=-1000)
    return m


def main(argv=None):
    parser=ArgumentParser(description='Two-span beam: model, report, and plots')
    parser.add_argument('--output',default='outputs/examples/artifacts_v05',help='output directory')
    args=parser.parse_args(argv)
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)

    original=make_two_span_beam()
    save_model_json(original,out/'continuous_beam_model.json')
    model=load_model_json(out/'continuous_beam_model.json')
    result=LinearStaticSolver(Mode.TEACHING).solve(model)
    fast=LinearStaticSolver(Mode.FAST).solve(model)
    np.testing.assert_allclose(result.displacements,fast.displacements)
    np.testing.assert_allclose(result.reactions,fast.reactions)
    save_teaching_report(model,result,out/'teaching_report.md')

    print('V0.5: two-span continuous beam, equal L=4 m, q=1 kN/m downward')
    for nid in (1,2,3):
        print(f'  Support {nid}: R_uy={result.reaction(nid,"uy")/1000:.6f} kN')
    moment=BeamResponse2D(model,result,1).section(4).M
    print(f'  Interior support B: M={moment/1000:.6f} kN*m')
    print(f'  Number of global DOFs: {result.dof_manager.ndof}')

    figs=[('structure.png',lambda:plot_structure(model)),
          ('moment.png',lambda:plot_force_diagram(model,result,'M')),
          ('shear.png',lambda:plot_force_diagram(model,result,'V')),
          ('deformed.png',lambda:plot_deformed_shape(model,result))]
    for filename,draw in figs:
        ax=draw()
        ax.figure.savefig(out/filename,dpi=160,bbox_inches='tight')
        plt.close(ax.figure)
    print('Written files:')
    for p in sorted(out.iterdir()):
        print(f'  {p}')


if __name__=='__main__':
    main()
