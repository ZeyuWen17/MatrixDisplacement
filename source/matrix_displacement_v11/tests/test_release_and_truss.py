"""V0.4: checks analytical hinge and plane-truss responses and mixed systems."""
import math
import numpy as np
import pytest
from matrix_displacement import (
    Node, Material, Section, Frame2D, Truss2D,
    StructuralModel, DOFManager, LinearStaticSolver, Mode,
    MemberResponse2D, TrussResponse2D,
    plot_force_diagram, plot_deformed_shape,
)

E, A, I, L = 210e9, 0.012, 8e-6, 4.0


def beam(*, release_i=False, release_j=False):
    m = StructuralModel()
    m.add_node(Node(1,0,0))
    m.add_node(Node(2,L,0))
    m.add_material(Material(1,E))
    m.add_section(Section(1,A,I))
    m.add_element(Frame2D(1,1,2,1,1,release_i,release_j))
    return m


def truss():
    m = StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,L,0))
    m.add_material(Material(1,E));m.add_section(Section(1,A,I))
    m.add_element(Truss2D(1,1,2,1,1))
    return m


def test_frame_unreleased_legacy_matrix_identical():
    m=beam()
    e=m.elements[1]
    np.testing.assert_allclose(e.local_stiffness(m),e._raw_local_stiffness(m))
    assert e.released_indices==()


@pytest.mark.parametrize('release_i,release_j,at',[(True,False,2),(False,True,5),(True,True,2)])
def test_release_matrix_zero_rows_and_symmetric(release_i,release_j,at):
    m=beam(release_i=release_i,release_j=release_j)
    k=m.elements[1].local_stiffness(m)
    np.testing.assert_allclose(k,k.T,atol=1e-10)
    np.testing.assert_allclose(k[at],0,atol=1e-9)
    assert np.linalg.eigvalsh(k).min()>-1e-5


@pytest.mark.parametrize('mode',[Mode.TEACHING,Mode.FAST])
def test_pinned_pinned_uniform_beam_exact_reactions_and_deflection(mode):
    m=beam(release_i=True,release_j=True)
    w=1200
    for n in (1,2):
        m.constrain(n,'ux');m.constrain(n,'uy')
        # A redundant prescribed rz=0 on a fully released node is harmless.
        m.constrain(n,'rz')
    m.add_uniform_load(1,qy=-w)
    res=LinearStaticSolver(mode).solve(m)
    q=res.element_end_forces_local[1]
    assert q[2]==pytest.approx(0,abs=1e-9)
    assert q[5]==pytest.approx(0,abs=1e-9)
    assert res.reaction(1,'uy')==pytest.approx(w*L/2)
    assert res.reaction(2,'uy')==pytest.approx(w*L/2)
    r=MemberResponse2D(m,res,1)
    assert r.deformation(L/2).uy_local==pytest.approx(-5*w*L**4/(384*E*I),rel=1e-10)
    assert r.section(L/2).M==pytest.approx(w*L**2/8)
    assert r.deformation(0).rz==pytest.approx(-w*L**3/(24*E*I),rel=1e-10)
    assert r.deformation(L).rz==pytest.approx(+w*L**3/(24*E*I),rel=1e-10)
    assert res.displacement(1,'rz')==0.0   # Not the physical released slope.
    if mode==Mode.TEACHING:
        assert res.trace['inactive_rotations']==[2,5]
    else:
        assert res.trace is None


def test_fixed_pinned_uniform_beam_reaction_and_end_moment():
    m=beam(release_j=True)
    for d in ('ux','uy','rz'):m.constrain(1,d)
    for d in ('ux','uy'):m.constrain(2,d)
    w=1000
    m.add_uniform_load(1,qy=-w)
    res=LinearStaticSolver().solve(m)
    q=res.element_end_forces_local[1]
    assert q[2]==pytest.approx(w*L**2/8)
    assert q[5]==pytest.approx(0,abs=1e-9)
    assert res.reaction(1,'uy')==pytest.approx(5*w*L/8)
    assert res.reaction(2,'uy')==pytest.approx(3*w*L/8)
    r=MemberResponse2D(m,res,1)
    assert r.section(0).M==pytest.approx(-w*L**2/8)
    assert r.section(L).M==pytest.approx(0,abs=1e-8)
    assert r.deformation(L).uy_local==pytest.approx(0,abs=1e-12)


def test_fixed_pinned_central_point_load():
    m=beam(release_j=True)
    for d in ('ux','uy','rz'):m.constrain(1,d)
    for d in ('ux','uy'):m.constrain(2,d)
    P=2000
    m.add_point_load(1,L/2,fy=-P)
    r=LinearStaticSolver().solve(m)
    assert r.reaction(1,'uy')==pytest.approx(11*P/16)
    assert r.reaction(2,'uy')==pytest.approx(5*P/16)
    assert r.element_end_forces_local[1][2]==pytest.approx(3*P*L/16)
    assert r.element_end_forces_local[1][5]==pytest.approx(0,abs=1e-9)


def test_node_rotation_not_same_as_released_cross_section_slope():
    m=beam(release_j=True)
    for d in ('ux','uy','rz'):m.constrain(1,d)
    for d in ('ux','uy'):m.constrain(2,d)
    m.add_uniform_load(1,qy=-750)
    r=LinearStaticSolver().solve(m)
    assert r.displacement(2,'rz')==0.0
    physical=MemberResponse2D(m,r,1)
    assert physical.deformation(L).rz != 0.0
    assert physical.deformation(L).uy_local == pytest.approx(0,abs=1e-12)


def test_released_nodal_moment_rejected():
    m=beam(release_j=True)
    for d in ('ux','uy','rz'):m.constrain(1,d)
    m.constrain(2,'uy')
    m.add_load(2,'rz',100)
    with pytest.raises(ValueError,match='rotational stiffness'):
        LinearStaticSolver().solve(m)


def test_released_prescribed_nonzero_rotation_rejected():
    m=beam(release_j=True)
    for d in ('ux','uy','rz'):m.constrain(1,d)
    m.constrain(2,'uy');m.constrain(2,'rz',0.03)
    with pytest.raises(ValueError,match='inactive'):
        LinearStaticSolver().solve(m)


def test_hinged_cantilever_mechanism_still_detected():
    m=beam(release_i=True)
    m.constrain(1,'ux');m.constrain(1,'uy')
    m.add_load(2,'uy',-500)
    with pytest.raises(ValueError,match='Singular'):
        LinearStaticSolver().solve(m)


def test_simple_horizontal_truss_analytical():
    m=truss()
    for d in ('ux','uy'):m.constrain(1,d)
    m.constrain(2,'uy')
    P=1350
    m.add_load(2,'ux',P)
    r=LinearStaticSolver().solve(m)
    dm=r.dof_manager
    assert dm.ndof==4
    assert (2,'rz') not in dm.mapping
    assert r.displacement(2,'ux')==pytest.approx(P*L/(E*A))
    assert r.reaction(1,'ux')==pytest.approx(-P)
    assert r.reaction(1,'uy')==pytest.approx(0,abs=1e-10)
    assert r.element_end_forces_local[1] == pytest.approx([-P,0,P,0])
    sec=TrussResponse2D(m,r,1)
    assert sec.section(L/2).N==pytest.approx(P)
    assert sec.section(L/2).V==0.0
    assert sec.section(L/2).M==0.0


def test_inclined_truss_global_kinematics():
    m=truss()
    m.nodes[2]=Node(2,3,4)
    for d in ('ux','uy'):m.constrain(1,d)
    m.constrain(2,'uy')
    P=1000
    m.add_load(2,'ux',P)
    e=m.elements[1]
    assert e.geometry(m)==pytest.approx((5,.6,.8))
    T=e.transformation_matrix(m)
    np.testing.assert_allclose(T.T@T,np.eye(4),atol=1e-14)
    r=LinearStaticSolver().solve(m)
    assert r.displacement(2,'ux')==pytest.approx(P*5/(E*A*.6**2))
    assert TrussResponse2D(m,r,1).N==pytest.approx(P/.6)


def test_triangle_truss_analytical_diagonal_compression_and_base_tension():
    m=StructuralModel()
    for n,x,y in [(1,0,0),(2,4,0),(3,2,3)]:m.add_node(Node(n,x,y))
    m.add_material(Material(1,E));m.add_section(Section(1,A,I))
    for i,ni,nj in [(1,1,2),(2,1,3),(3,2,3)]:m.add_element(Truss2D(i,ni,nj,1,1))
    for d in ('ux','uy'):m.constrain(1,d)
    m.constrain(2,'uy')
    P=3000
    m.add_load(3,'uy',-P)
    r=LinearStaticSolver(Mode.TEACHING).solve(m)
    assert r.dof_manager.ndof==6
    assert r.reaction(1,'uy')==pytest.approx(P/2)
    assert r.reaction(2,'uy')==pytest.approx(P/2)
    assert TrussResponse2D(m,r,1).N==pytest.approx(P/3)
    assert TrussResponse2D(m,r,2).N==pytest.approx(-P*math.sqrt(13)/6)
    assert TrussResponse2D(m,r,3).N==pytest.approx(-P*math.sqrt(13)/6)
    assert r.trace['elements'][2]['local_stiffness'].shape==(4,4)


def test_truss_only_node_has_no_rotation_and_moment_rejected():
    m=truss()
    m.add_load(2,'rz',200)
    for d in ('ux','uy'):m.constrain(1,d)
    m.constrain(2,'uy')
    with pytest.raises(ValueError,match='rotational stiffness'):
        LinearStaticSolver().solve(m)
    m.loads.clear()
    m.constrain(2,'rz',0.12)
    with pytest.raises(ValueError,match='inactive'):
        LinearStaticSolver().solve(m)


def test_truss_member_loads_rejected_with_message():
    m=truss()
    with pytest.raises(ValueError,match='nodal loads only'):
        m.add_uniform_load(1,qy=-100)
    with pytest.raises(ValueError,match='nodal loads only'):
        m.add_point_load(1,L/2,fy=-100)


def test_truss_only_rz_result_access_rejected():
    m=truss()
    for d in ('ux','uy'):m.constrain(1,d)
    m.constrain(2,'uy')
    r=LinearStaticSolver().solve(m)
    with pytest.raises(ValueError,match='not present'):
        r.displacement(2,'rz')


def test_mixed_frame_truss_compared_to_frame_only_stiffening():
    m=beam()
    m.add_node(Node(3,L,3))
    m.add_element(Truss2D(2,2,3,1,1))
    for d in ('ux','uy','rz'):m.constrain(1,d)
    for d in ('ux','uy'):m.constrain(3,d)
    m.add_load(2,'uy',-500)
    res1=LinearStaticSolver(Mode.FAST).solve(m)
    res2=LinearStaticSolver(Mode.TEACHING).solve(m)
    assert res1.dof_manager.ndof==8
    assert res1.displacement(2,'uy')<0
    np.testing.assert_allclose(res1.displacements,res2.displacements)
    np.testing.assert_allclose(res1.reactions,res2.reactions)
    pure=beam()
    for d in ('ux','uy','rz'):pure.constrain(1,d)
    pure.add_load(2,'uy',-500)
    pref=LinearStaticSolver().solve(pure)
    assert abs(res1.displacement(2,'uy')) < abs(pref.displacement(2,'uy'))


def test_mixed_diagrams_and_deformation_plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m=beam()
    m.add_node(Node(3,L,3));m.add_element(Truss2D(2,2,3,1,1))
    for d in ('ux','uy','rz'):m.constrain(1,d)
    for d in ('ux','uy'):m.constrain(3,d)
    m.add_load(2,'uy',-500)
    r=LinearStaticSolver().solve(m)
    ax=plot_force_diagram(m,r,'N');assert len(ax.lines)>=3;plt.close(ax.figure)
    ax=plot_force_diagram(m,r,'M');assert len(ax.lines)>=3;plt.close(ax.figure)
    ax=plot_deformed_shape(m,r);assert len(ax.lines)>=3;plt.close(ax.figure)


def test_invalid_truss_geometry_rejected():
    m=StructuralModel()
    m.add_node(Node(1,0,0));m.add_node(Node(2,0,0))
    m.add_material(Material(1,E));m.add_section(Section(1,A,I))
    with pytest.raises(ValueError,match='zero length'):
        m.add_element(Truss2D(1,1,2,1,1))


def test_singular_unrestrained_truss_rejected():
    m=truss()
    m.constrain(1,'ux');m.constrain(1,'uy')
    with pytest.raises(ValueError,match='Singular'):
        LinearStaticSolver().solve(m)


def test_two_released_elements_same_unconstrained_node_stable_under_support():
    m=StructuralModel()
    for nid,x in [(1,0),(2,L),(3,2*L)]:m.add_node(Node(nid,x,0))
    m.add_material(Material(1,E));m.add_section(Section(1,A,I))
    m.add_element(Frame2D(1,1,2,1,1,release_j=True))
    m.add_element(Frame2D(2,2,3,1,1,release_i=True))
    for d in ('ux','uy','rz'):m.constrain(1,d)
    m.constrain(2,'uy')
    m.constrain(3,'uy')
    m.add_uniform_load(1,qy=-400);m.add_uniform_load(2,qy=-600)
    res=LinearStaticSolver().solve(m)
    assert res.element_end_forces_local[1][5]==pytest.approx(0,abs=1e-9)
    assert res.element_end_forces_local[2][2]==pytest.approx(0,abs=1e-9)
    assert res.reaction(1,'uy')+res.reaction(2,'uy')+res.reaction(3,'uy')==pytest.approx(400*L+600*L)
