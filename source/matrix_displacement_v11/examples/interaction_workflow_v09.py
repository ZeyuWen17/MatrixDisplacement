"""V0.9 geometry and diagram picking end-to-end demonstration (no GUI)."""
from pathlib import Path
from matrix_displacement.core import Mode
from matrix_displacement.editor import ModelEditor
from matrix_displacement.interaction import dimension_info, project_to_member, diagram_pick
from matrix_displacement.postprocessing import MemberResponse2D


def main():
    ed = ModelEditor()
    ed.load_example('cantilever')
    model = ed.model
    result = ed.solve(Mode.TEACHING)
    dim = dimension_info(model, 1)
    station = project_to_member(model, 1, 1.7, 0.5)
    sample = MemberResponse2D(model, result, 1).sample_sections()
    indexes = [i for i, x in enumerate(sample.x) if abs(x-1.7) < 1e-12]
    if len(indexes) != 2:
        raise RuntimeError('Concentrated load jump samples not found')
    left = diagram_pick(model, result, 1, 'V', indexes[0]).section
    right = diagram_pick(model, result, 1, 'V', indexes[1]).section
    assert abs((right.V-left.V)+700) < 1e-7
    assert abs(right.M-left.M) < 1e-7
    lines = [
        'V0.9 UI interaction math workflow (without Qt)',
        f'Member dimension: {dim.label}',
        f'Projected station x={station.station:.4f} m; lateral distance={station.distance:.4f} m',
        f'Point force at x={left.x:.4f} m, left V={left.V:.6g} N, right V={right.V:.6g} N',
        f'V jump={right.V-left.V:.6g} N, left M={left.M:.6g} N*m, right M={right.M:.6g} N*m',
        'No claim of Windows GUI validation is made by this example.',
    ]
    folder = Path('outputs/examples/artifacts_v09')
    folder.mkdir(exist_ok=True)
    (folder/'interaction_validation.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
