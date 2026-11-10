"""V0.7 GUI-model bridge and teaching report example (runs without PySide6).

Run from project root:
  python -m examples.editor_workflow_v07 --output outputs/examples/artifacts_v07
"""
from argparse import ArgumentParser
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure

from matrix_displacement.editor import ModelEditor
from matrix_displacement import (
    Mode, render_teaching_report, export_results_csv,
    plot_structure, plot_force_diagram, plot_deformed_shape,
)


def main(argv=None):
    parser=ArgumentParser()
    parser.add_argument('--output',default='outputs/examples/artifacts_v07')
    args=parser.parse_args(argv)
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    editor=ModelEditor()
    editor.load_example('continuous_beam')
    editor.save(out/'continuous_beam.json')
    other=ModelEditor()
    other.open(out/'continuous_beam.json')
    fast=other.solve(Mode.FAST)
    teaching=other.solve(Mode.TEACHING)
    np.testing.assert_allclose(fast.displacements,teaching.displacements)
    np.testing.assert_allclose(fast.reactions,teaching.reactions)
    (out/'teaching_report.md').write_text(
        render_teaching_report(other.model,teaching),encoding='utf-8')
    export_results_csv(other.model,fast,out/'csv',points=121)
    for name,plotter in (
        ('structure',lambda ax:plot_structure(other.model,ax=ax,show_loads=True)),
        ('axial_N',lambda ax:plot_force_diagram(other.model,fast,'N',ax=ax)),
        ('shear_V',lambda ax:plot_force_diagram(other.model,fast,'V',ax=ax)),
        ('moment_M',lambda ax:plot_force_diagram(other.model,fast,'M',ax=ax)),
        ('deformed',lambda ax:plot_deformed_shape(other.model,fast,ax=ax)),
    ):
        fig=Figure(figsize=(8,5),dpi=115)
        plotter(fig.add_subplot(111))
        fig.tight_layout()
        fig.savefig(out/f'{name}.png',dpi=150)
    print(f'V0.7 model/controller round-trip: {len(other.model.nodes)} nodes, {len(other.model.elements)} elements')
    print(f'Center support reaction = {fast.reaction(2,"uy"):.6f} N (expected 5000 N)')
    print('Teaching/fast modes agree. JSON, CSV, report and PNG outputs:',out.resolve())


if __name__=='__main__':
    main()
