"""V0.2 regression: consistent member loads, end forces, coordinates and validation."""
import numpy as np
import pytest
from matrix_displacement import (
    Node, Material, Section, Frame2D, UniformLoad2D, PointLoad2D,
    StructuralModel, LinearStaticSolver, Mode,
)

L = 4.0
E = 210e9
I = 8e-6
A = .015


def make_beam(*, length=L, angle=None):
    m = StructuralModel()
    x, y = (length, 0) if angle is None else angle
    m.add_node(Node(1, 0, 0))
    m.add_node(Node(2, x, y))
    m.add_material(Material(1, E))
    m.add_section(Section(1, A, I))
    m.add_element(Frame2D(1, 1, 2, 1, 1))
    return m


def fix_node(m, node_id):
    for dof in ('ux', 'uy', 'rz'):
        m.constrain(node_id, dof)


def simple_supports(m):
    m.constrain(1, 'ux')
    m.constrain(1, 'uy')
    m.constrain(2, 'uy')


def test_uniform_load_equivalent_vector_and_fixed_end_sign():
    m = make_beam()
    e = m.elements[1]
    w = 1500
    f = e.equivalent_nodal_load(m, UniformLoad2D(1, qy=-w))
    np.testing.assert_allclose(f, [0,-w*L/2,-w*L**2/12,0,-w*L/2,w*L**2/12])
    fix_node(m, 1); fix_node(m, 2)
    m.add_uniform_load(1, qy=-w)
    r = LinearStaticSolver(Mode.TEACHING).solve(m)
    np.testing.assert_allclose(r.element_end_forces_local[1], -f)
    np.testing.assert_allclose(r.element_fixed_end_forces_local[1], -f)
    np.testing.assert_allclose(r.load_vector, r.member_load_vector)
    np.testing.assert_allclose(r.trace['elements'][1]['fixed_end_forces_local'], -f)


def test_cantilever_downward_uniform_analytical_tip_and_reactions():
    m = make_beam()
    fix_node(m, 1)
    w = 1200.0
    m.add_uniform_load(1, qy=-w)
    r = LinearStaticSolver().solve(m)
    assert r.displacement(2, 'uy') == pytest.approx(-w*L**4/(8*E*I))
    assert r.displacement(2, 'rz') == pytest.approx(-w*L**3/(6*E*I))
    assert r.reaction(1, 'uy') == pytest.approx(w*L)
    assert r.reaction(1, 'rz') == pytest.approx(w*L**2/2)
    np.testing.assert_allclose(r.element_end_forces_local[1][3:], np.zeros(3), atol=1e-8)


def test_simply_supported_uniform_and_zero_end_moments():
    m = make_beam()
    simple_supports(m)
    w = 1500
    m.add_uniform_load(1, qy=-w)
    r = LinearStaticSolver().solve(m)
    assert r.reaction(1, 'uy') == pytest.approx(w*L/2)
    assert r.reaction(2, 'uy') == pytest.approx(w*L/2)
    assert r.displacement(1, 'rz') == pytest.approx(-w*L**3/(24*E*I))
    assert r.displacement(2, 'rz') == pytest.approx(w*L**3/(24*E*I))
    assert r.element_end_forces_local[1][2] == pytest.approx(0, abs=1e-8)
    assert r.element_end_forces_local[1][5] == pytest.approx(0, abs=1e-8)


def test_cantilever_internal_point_force_analytical_tip():
    m = make_beam()
    fix_node(m, 1)
    a, P = 1.7, 700
    m.add_point_load(1, a, fy=-P)
    r = LinearStaticSolver().solve(m)
    assert r.displacement(2, 'uy') == pytest.approx(-P*a*a*(3*L-a)/(6*E*I))
    assert r.displacement(2, 'rz') == pytest.approx(-P*a*a/(2*E*I))
    assert r.reaction(1, 'uy') == pytest.approx(P)
    assert r.reaction(1, 'rz') == pytest.approx(P*a)
    np.testing.assert_allclose(r.element_end_forces_local[1][3:], np.zeros(3), atol=1e-8)


def test_simply_supported_midspan_point_force():
    m = make_beam()
    simple_supports(m)
    P = 1500
    m.add_point_load(1, L/2, fy=-P)
    r = LinearStaticSolver().solve(m)
    assert r.reaction(1, 'uy') == pytest.approx(P/2)
    assert r.reaction(2, 'uy') == pytest.approx(P/2)
    assert r.displacement(1, 'rz') == pytest.approx(-P*L*L/(16*E*I))
    assert r.displacement(2, 'rz') == pytest.approx(P*L*L/(16*E*I))
    assert r.element_end_forces_local[1][2] == pytest.approx(0, abs=1e-8)
    assert r.element_end_forces_local[1][5] == pytest.approx(0, abs=1e-8)


def test_cantilever_uniform_axial_force():
    m = make_beam()
    fix_node(m, 1)
    q = 250
    m.add_uniform_load(1, qx=q)
    r = LinearStaticSolver().solve(m)
    assert r.displacement(2,'ux') == pytest.approx(q*L**2/(2*E*A))
    assert r.reaction(1,'ux') == pytest.approx(-q*L)
    assert r.element_end_forces_local[1][3] == pytest.approx(0, abs=1e-8)


def test_cantilever_internal_axial_point_force():
    m = make_beam()
    fix_node(m, 1)
    P, a = 1200, L*.32
    m.add_point_load(1, a, fx=P)
    r = LinearStaticSolver().solve(m)
    assert r.displacement(2,'ux') == pytest.approx(P*a/(E*A))
    assert r.reaction(1,'ux') == pytest.approx(-P)


def test_local_and_global_load_systems_agree_on_inclined_member():
    m_local = make_beam(angle=(3,4))
    m_global = make_beam(angle=(3,4))
    for m in (m_local, m_global):
        fix_node(m, 1)
    # (X,Y) = (0,-1000) -> local (x,y) = (-800,-600)
    m_local.add_uniform_load(1, qx=-800, qy=-600)
    m_global.add_uniform_load(1, qx=0, qy=-1000, system='global')
    m_local.add_point_load(1, 2.3, fx=-800, fy=-600)
    m_global.add_point_load(1, 2.3, fx=0, fy=-1000, system='global')
    a = LinearStaticSolver().solve(m_local)
    b = LinearStaticSolver().solve(m_global)
    np.testing.assert_allclose(a.member_load_vector,b.member_load_vector, rtol=1e-12,atol=1e-9)
    np.testing.assert_allclose(a.displacements,b.displacements,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(a.reactions,b.reactions,rtol=1e-12,atol=1e-7)


def test_additive_member_and_nodal_loads_with_mode_equality():
    m = make_beam()
    fix_node(m, 1)
    m.add_uniform_load(1, qy=-800)
    m.add_uniform_load(1, qy=-400)
    m.add_point_load(1, 2.0, fy=-200)
    m.add_load(2, 'uy', -300)
    a = LinearStaticSolver(Mode.TEACHING).solve(m)
    b = LinearStaticSolver(Mode.FAST).solve(m)
    np.testing.assert_allclose(a.displacements, b.displacements)
    np.testing.assert_allclose(a.reactions,b.reactions)
    np.testing.assert_allclose(a.load_vector, a.nodal_load_vector + a.member_load_vector)
    np.testing.assert_allclose(a.element_end_forces_local[1], b.element_end_forces_local[1])
    assert a.trace['elements'][1]['equivalent_nodal_load_local'].shape == (6,)
    assert a.trace['element_end_forces_local'][1].shape == (6,)
    assert b.trace is None
    assert a.reaction(1,'uy') == pytest.approx((800+400)*L + 200 + 300)
    assert a.reaction(1,'rz') == pytest.approx((800+400)*L**2/2 + 200*2 + 300*L)


def test_two_element_and_one_element_uniform_cantilevers_agree():
    one = make_beam()
    fix_node(one,1)
    one.add_uniform_load(1,qy=-950)
    r1 = LinearStaticSolver().solve(one)
    two = StructuralModel()
    for nid,x in ((1,0),(2,L/2),(3,L)):
        two.add_node(Node(nid,x,0))
    two.add_material(Material(1,E));two.add_section(Section(1,A,I))
    two.add_element(Frame2D(1,1,2,1,1))
    two.add_element(Frame2D(2,2,3,1,1))
    fix_node(two,1)
    two.add_uniform_load(1,qy=-950)
    two.add_uniform_load(2,qy=-950)
    r2 = LinearStaticSolver().solve(two)
    assert r2.displacement(3,'uy') == pytest.approx(r1.displacement(2,'uy'),rel=1e-11)
    assert r2.displacement(3,'rz') == pytest.approx(r1.displacement(2,'rz'),rel=1e-11)
    assert r2.reaction(1,'uy') == pytest.approx(r1.reaction(1,'uy'),rel=1e-11)
    assert r2.reaction(1,'rz') == pytest.approx(r1.reaction(1,'rz'),rel=1e-11)


@pytest.mark.parametrize('position',[-.01, L+.01, np.inf, np.nan])
def test_bad_point_position_rejected(position):
    m = make_beam()
    with pytest.raises(ValueError):
        m.add_point_load(1,position,fy=-100)


@pytest.mark.parametrize('kind', ['uniform','point'])
def test_bad_member_load_element_rejected(kind):
    m = make_beam()
    with pytest.raises(ValueError,match='unknown element'):
        if kind=='uniform': m.add_uniform_load(99, qy=-10)
        else: m.add_point_load(99, 1, fy=-10)


@pytest.mark.parametrize('bad', [np.nan,np.inf,-np.inf])
def test_bad_member_force_rejected(bad):
    m = make_beam()
    with pytest.raises(ValueError,match='finite'):
        m.add_uniform_load(1,qy=bad)
    with pytest.raises(ValueError,match='finite'):
        m.add_point_load(1,2,fy=bad)


def test_bad_coordinate_system_rejected():
    m = make_beam()
    with pytest.raises(ValueError,match='coordinate system'):
        m.add_uniform_load(1,qy=-10,system='world')
    with pytest.raises(ValueError,match='coordinate system'):
        m.add_point_load(1,1,fy=-10,system='world')


def test_direct_mutation_member_list_checked_during_solve():
    m = make_beam()
    fix_node(m,1)
    m.member_loads.append(PointLoad2D(1,position=L+1,fy=-30))
    with pytest.raises(ValueError,match='position'):
        LinearStaticSolver().solve(m)


def test_bad_member_load_type_rejected():
    m = make_beam()
    with pytest.raises(TypeError):
        m.add_member_load('not a load')


def test_equivalent_point_at_element_ends_matches_nodal_force():
    m = make_beam()
    e=m.elements[1]
    np.testing.assert_allclose(
        e.equivalent_nodal_load(m, PointLoad2D(1,0,fy=-100)),
        [0,-100,0,0,0,0])
    np.testing.assert_allclose(
        e.equivalent_nodal_load(m, PointLoad2D(1,L,fy=-100)),
        [0,0,0,0,-100,0])
