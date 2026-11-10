import numpy as np
import pytest
from matrix_displacement import *

def cantilever(mode=Mode.FAST):
    m = StructuralModel()
    m.add_node(Node(1,0,0)); m.add_node(Node(2,3,0))
    m.add_material(Material(1,210e9)); m.add_section(Section(1,0.01,8e-6))
    m.add_element(Frame2D(1,1,2,1,1))
    for dof in ('ux','uy','rz'): m.constrain(1,dof)
    m.add_load(2,'uy',-1000)
    return m, LinearStaticSolver(mode).solve(m)

def test_cantilever_analytical():
    m,r = cantilever()
    L,E,I,P = 3,210e9,8e-6,1000
    assert r.displacement(2,'uy') == pytest.approx(-P*L**3/(3*E*I))
    assert r.displacement(2,'rz') == pytest.approx(-P*L**2/(2*E*I))
    assert r.reaction(1,'uy') == pytest.approx(P)
    assert r.reaction(1,'rz') == pytest.approx(P*L)
    assert r.reaction(1,'ux') == pytest.approx(0,abs=1e-8)

def test_teaching_fast_identical():
    _,a = cantilever(Mode.TEACHING)
    _,b = cantilever(Mode.FAST)
    np.testing.assert_allclose(a.displacements,b.displacements)
    np.testing.assert_allclose(a.reactions,b.reactions)
    assert a.trace is not None and b.trace is None

def test_stiffness_symmetry_and_rigid_translation():
    m,_ = cantilever()
    e = m.elements[1]
    k = e.local_stiffness(m)
    np.testing.assert_allclose(k,k.T)
    np.testing.assert_allclose(k @ np.array([1,0,0,1,0,0]), np.zeros(6),atol=1e-7)
    np.testing.assert_allclose(k @ np.array([0,1,0,0,1,0]), np.zeros(6),atol=1e-7)

def test_inclined_transformation_orthogonal():
    m = StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,3,4))
    m.add_material(Material(1,200e9));m.add_section(Section(1,.01,1e-5))
    e = Frame2D(1,1,2,1,1);m.add_element(e)
    T = e.transformation_matrix(m)
    np.testing.assert_allclose(T.T @ T,np.eye(6),atol=1e-14)
    np.testing.assert_allclose(e.global_stiffness(m),e.global_stiffness(m).T,atol=1e-6)

def test_dof_mapping_sorted_node_ids():
    m = StructuralModel()
    m.add_node(Node(9,1,0));m.add_node(Node(2,0,0))
    d = DOFManager(m)
    assert d.mapping[(2,'ux')] == 0
    assert d.mapping[(9,'rz')] == 5

def test_zero_length_rejected():
    m = StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,0,0))
    m.add_material(Material(1,200e9));m.add_section(Section(1,.01,1e-5))
    with pytest.raises(ValueError,match='zero length'):
        m.add_element(Frame2D(1,1,2,1,1))

def test_singular_structure_rejected():
    m = StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,1,0))
    m.add_material(Material(1,200e9));m.add_section(Section(1,.01,1e-5))
    m.add_element(Frame2D(1,1,2,1,1))
    with pytest.raises(ValueError,match='Singular'):
        LinearStaticSolver().solve(m)

def test_two_element_cantilever_matches_one_element():
    m = StructuralModel()
    for n,x in [(1,0),(2,1.5),(3,3)]: m.add_node(Node(n,x,0))
    m.add_material(Material(1,210e9));m.add_section(Section(1,.01,8e-6))
    m.add_element(Frame2D(1,1,2,1,1));m.add_element(Frame2D(2,2,3,1,1))
    for dof in DOF_LIST: m.constrain(1,dof)
    m.add_load(3,'uy',-1000)
    r = LinearStaticSolver().solve(m)
    assert r.displacement(3,'uy') == pytest.approx(-1000*3**3/(3*210e9*8e-6))
    assert r.reaction(1,'rz') == pytest.approx(3000)

DOF_LIST = ('ux','uy','rz')
