"""V0.9 user interaction math can be tested without a desktop or Qt."""
import math

import pytest

from matrix_displacement.core import Mode
from matrix_displacement.editor import ModelEditor
from matrix_displacement.interaction import (
    dimension_info, project_to_member, diagram_pick,
)
from matrix_displacement.postprocessing import MemberResponse2D
from matrix_displacement.visualization import plot_force_diagram


def cantilever():
    ed = ModelEditor()
    ed.load_example('cantilever')
    return ed.model, ed.solve(Mode.TEACHING)


def test_dimension_horizontal_length_and_angle():
    model, _ = cantilever()
    d = dimension_info(model, 1)
    assert d.length == 4
    assert d.angle_deg == 0
    assert d.start == (0, 0)
    assert d.end == (4, 0)
    assert d.offset_start == pytest.approx((0, 0.3))
    assert d.offset_end == pytest.approx((4, 0.3))
    assert 'L=4 m' in d.label


def test_dimensions_for_vertical_and_diagonal_members():
    ed = ModelEditor()
    n1 = ed.add_node(0, 0)
    n2 = ed.add_node(0, 3)
    n3 = ed.add_node(4, 0)
    ed.add_element(n1, n2)
    ed.add_element(n1, n3)
    v = dimension_info(ed.model, 1, 0.5)
    assert v.length == 3
    assert v.angle_deg == 90
    assert v.offset_start == pytest.approx((-0.5, 0))
    assert v.offset_end == pytest.approx((-0.5, 3))
    # Reversed member orientation should retain geometric direction.
    ed.add_element(n2, n3)
    diagonal = dimension_info(ed.model, 3)
    assert diagonal.length == 5
    assert diagonal.angle_deg == pytest.approx(-36.86989764584)


@pytest.mark.parametrize('offset', [-1, float('nan'), float('inf'), True])
def test_dimension_invalid_offset(offset):
    model, _ = cantilever()
    with pytest.raises(ValueError):
        dimension_info(model, 1, offset)


def test_dimensions_bad_element_id():
    model, _ = cantilever()
    with pytest.raises(KeyError):
        dimension_info(model, 123)


def test_station_projection_clamps_and_checks_distance():
    model, _ = cantilever()
    s = project_to_member(model, 1, 1.7, 2)
    assert s.station == pytest.approx(1.7)
    assert s.distance == pytest.approx(2)
    assert s.projected == pytest.approx((1.7, 0))
    assert project_to_member(model, 1, -1, 0).station == 0
    assert project_to_member(model, 1, 8, 0).station == 4


def test_project_nonhorizontal_member():
    ed = ModelEditor()
    ed.add_node(0, 0)
    ed.add_node(3, 4)
    ed.add_element(1, 2)
    d = project_to_member(ed.model, 1, 1.5, 2)
    assert d.station == pytest.approx(2.5)
    assert d.distance == 0
    with pytest.raises(ValueError):
        project_to_member(ed.model, 1, float('nan'), 0)


def test_diagram_pick_at_concentrated_load_preserves_jump_sides():
    model, result = cantilever()
    samples = MemberResponse2D(model, result, 1).sample_sections()
    matches = [i for i, x in enumerate(samples.x) if math.isclose(x, 1.7, abs_tol=1e-12)]
    assert len(matches) == 2
    a = diagram_pick(model, result, 1, 'V', matches[0])
    b = diagram_pick(model, result, 1, 'V', matches[1])
    assert a.section.side == 'left'
    assert b.section.side == 'right'
    assert a.section.x == b.section.x == pytest.approx(1.7)
    assert b.section.V - a.section.V == pytest.approx(-700)
    assert a.section.M == pytest.approx(b.section.M)
    assert a.section.V == pytest.approx(samples.V[matches[0]])
    assert b.section.V == pytest.approx(samples.V[matches[1]])


def test_diagram_pick_end_station_uses_left_side():
    model, result = cantilever()
    samples = MemberResponse2D(model, result, 1).sample_sections()
    first = diagram_pick(model, result, 1, 'M', 0)
    last = diagram_pick(model, result, 1, 'M', len(samples.x)-1)
    assert first.section.x == 0
    assert first.section.side == 'right'
    assert last.section.x == 4
    assert last.section.side == 'left'


@pytest.mark.parametrize('bad', [-1, 10000, 1.3, True])
def test_diagram_pick_invalid_index(bad):
    model, result = cantilever()
    with pytest.raises((IndexError, TypeError)):
        diagram_pick(model, result, 1, 'N', bad)


def test_diagram_pick_invalid_component():
    model, result = cantilever()
    with pytest.raises(ValueError):
        diagram_pick(model, result, 1, 'DISP', 0)


def test_plot_force_diagram_interactive_metadata_and_sample_length():
    import matplotlib
    matplotlib.use('Agg', force=True)
    from matplotlib.figure import Figure
    model, result = cantilever()
    fig = Figure()
    ax = fig.add_subplot()
    plot_force_diagram(model, result, 'V', ax=ax, interactive=True)
    interactive = [line for line in ax.lines if line.get_gid() == 'md-member:1:V']
    assert len(interactive) == 1
    line = interactive[0]
    assert line.get_picker() == 7
    expected = MemberResponse2D(model, result, 1).sample_sections()
    assert len(line.get_xdata()) == len(expected.x)
    fig.clear()


def test_default_force_diagram_remains_non_interactive():
    from matplotlib.figure import Figure
    model, result = cantilever()
    fig = Figure()
    ax = fig.add_subplot()
    plot_force_diagram(model, result, 'M', ax=ax)
    assert not any(str(line.get_gid()).startswith('md-member:') for line in ax.lines)
    fig.clear()
