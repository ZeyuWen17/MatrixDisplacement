"""Regression tests for V0.1.1 validation and mechanism detection."""
import numpy as np
import pytest
from matrix_displacement import (
    Node, Material, Section, Frame2D, StructuralModel, LinearStaticSolver,
    Mode,
)


def make_beam():
    model = StructuralModel()
    model.add_node(Node(1, 0, 0))
    model.add_node(Node(2, 3, 0))
    model.add_material(Material(1, 210e9))
    model.add_section(Section(1, .01, 8e-6))
    model.add_element(Frame2D(1, 1, 2, 1, 1))
    return model


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_non_finite_coordinates_material_sections_rejected(bad):
    with pytest.raises(ValueError, match='finite'):
        Node(1, bad, 0)
    with pytest.raises(ValueError, match='finite'):
        Material(1, bad)
    with pytest.raises(ValueError, match='finite'):
        Section(1, .1, bad)


def test_non_finite_nodal_load_rejected():
    m = make_beam()
    with pytest.raises(ValueError, match='finite'):
        m.add_load(2, 'uy', float('nan'))
    with pytest.raises(ValueError, match='finite'):
        m.add_load(2, 'uy', float('inf'))


def test_non_finite_prescribed_displacement_rejected():
    m = make_beam()
    with pytest.raises(ValueError, match='finite'):
        m.constrain(1, 'uy', float('-inf'))


def test_load_accumulation_overflow_rejected():
    m = make_beam()
    m.add_load(2, 'uy', 1e308)
    with pytest.raises(ValueError, match='finite'):
        m.add_load(2, 'uy', 1e308)


def test_hinge_free_beam_is_mechanism_even_with_zero_external_load():
    m = make_beam()
    m.constrain(1,'ux')
    m.constrain(1,'uy')
    for mode in (Mode.FAST, Mode.TEACHING):
        with pytest.raises(ValueError, match='Singular or near-singular'):
            LinearStaticSolver(mode).solve(m)


def test_unattached_node_detected_as_mechanism():
    m = make_beam()
    m.add_node(Node(3,5,5))
    for dof in ('ux','uy','rz'):
        m.constrain(1,dof)
    with pytest.raises(ValueError, match='Singular'):
        LinearStaticSolver().solve(m)


def test_directly_modified_nodal_load_checked_at_solve_time():
    m = make_beam()
    for dof in ('ux','uy','rz'):
        m.constrain(1,dof)
    m.loads[(2,'uy')] = np.nan
    with pytest.raises(ValueError, match='finite'):
        LinearStaticSolver().solve(m)


def test_directly_modified_constraint_checked_at_solve_time():
    m = make_beam()
    for dof in ('ux','uy','rz'):
        m.constrain(1,dof)
    m.constraints[(1,'ux')] = np.inf
    with pytest.raises(ValueError, match='finite'):
        LinearStaticSolver().solve(m)


def test_valid_nonzero_prescribed_displacement():
    m = make_beam()
    for dof in ('ux','uy','rz'):
        m.constrain(1,dof)
        m.constrain(2,dof)
    m.constrain(2,'ux',0.001)
    res = LinearStaticSolver().solve(m)
    assert res.displacement(2, 'ux') == pytest.approx(0.001)
    assert res.reaction(1, 'ux') == pytest.approx(-700000, rel=1e-12)
    assert res.reaction(2, 'ux') == pytest.approx(700000, rel=1e-12)


def test_constrained_single_node_without_free_dofs_is_supported():
    m = make_beam()
    for node_id in (1, 2):
        for dof in ('ux', 'uy', 'rz'):
            m.constrain(node_id, dof)
    m.add_load(2,'uy', -1000)
    res = LinearStaticSolver().solve(m)
    assert res.reaction(2,'uy') == pytest.approx(1000)
