"""Continuous-beam V0.5 analytical and compatibility checks."""
import numpy as np
import pytest
from matrix_displacement import (
    Node, Material, Section, Beam2D, Frame2D, Truss2D, StructuralModel,
    BeamResponse2D, MemberResponse2D, LinearStaticSolver, Mode,
    plot_force_diagram, plot_deformed_shape,
)

E = 210e9
I = 8e-6
Q = 1000.0
L = 4.0


def beam_model(spans=1):
    m=StructuralModel()
    for k in range(spans+1): m.add_node(Node(k+1,L*k,0.0))
    m.add_material(Material(1,E))
    m.add_section(Section(1,0.01,I))
    for k in range(spans): m.add_element(Beam2D(k+1,k+1,k+2,1,1))
    return m


def test_single_span_uniform_analytical():
    m=beam_model()
    m.constrain(1,'uy'); m.constrain(2,'uy')
    m.add_uniform_load(1,qy=-Q)
    r=LinearStaticSolver(Mode.TEACHING).solve(m)
    assert r.dof_manager.ndof == 4
    assert r.dof_manager.mapping == {(1,'uy'):0,(1,'rz'):1,(2,'uy'):2,(2,'rz'):3}
    assert r.reaction(1,'uy') == pytest.approx(Q*L/2)
    assert r.reaction(2,'uy') == pytest.approx(Q*L/2)
    assert r.displacement(1,'rz') == pytest.approx(-Q*L**3/(24*E*I))
    assert r.displacement(2,'rz') == pytest.approx(Q*L**3/(24*E*I))
    field=BeamResponse2D(m,r,1)
    assert field.section(L/2).M == pytest.approx(Q*L*L/8)
    assert field.deformation(L/2).uy_global == pytest.approx(-5*Q*L**4/(384*E*I))
    assert r.element_end_forces_local[1] == pytest.approx([Q*L/2,0,Q*L/2,0],abs=1e-7)
    assert r.trace['elements'][1]['local_stiffness'].shape==(4,4)


def test_two_span_uniform_analytical():
    m=beam_model(2)
    for nid in (1,2,3):m.constrain(nid,'uy')
    for eid in (1,2):m.add_uniform_load(eid,qy=-Q)
    r=LinearStaticSolver(Mode.TEACHING).solve(m)
    assert r.dof_manager.ndof==6
    assert r.reaction(1,'uy') == pytest.approx(3*Q*L/8)
    assert r.reaction(2,'uy') == pytest.approx(5*Q*L/4)
    assert r.reaction(3,'uy') == pytest.approx(3*Q*L/8)
    left=BeamResponse2D(m,r,1)
    right=BeamResponse2D(m,r,2)
    assert left.section(L).M == pytest.approx(-Q*L*L/8)
    assert right.section(0).M == pytest.approx(-Q*L*L/8)
    assert r.reaction(1,'uy')+r.reaction(2,'uy')+r.reaction(3,'uy')==pytest.approx(2*Q*L)
    assert r.displacement(2,'rz') == pytest.approx(0,abs=1e-12)


def test_point_load_midspan_and_section_jumps():
    m=beam_model()
    for nid in (1,2):m.constrain(nid,'uy')
    m.add_point_load(1,position=L/2,fy=-Q)
    r=LinearStaticSolver().solve(m)
    assert r.reaction(1,'uy')==pytest.approx(Q/2)
    assert r.reaction(2,'uy')==pytest.approx(Q/2)
    f=BeamResponse2D(m,r,1)
    assert f.section(L/2,side='left').V==pytest.approx(Q/2)
    assert f.section(L/2,side='right').V==pytest.approx(-Q/2)
    assert f.section(L/2).M==pytest.approx(Q*L/4)
    assert f.deformation(L/2).uy_local==pytest.approx(-Q*L**3/(48*E*I))


def test_beam_matrix_matches_frame_bending_block():
    m=beam_model()
    m.add_element(Frame2D(2,1,2,1,1))
    b=m.elements[1];f=m.elements[2]
    np.testing.assert_allclose(b.local_stiffness(m),f.local_stiffness(m)[np.ix_([1,2,4,5],[1,2,4,5])])
    m.add_uniform_load(1,qy=-Q)
    m.add_uniform_load(2,qy=-Q)
    np.testing.assert_allclose(b.equivalent_nodal_load(m,m.member_loads[0]),f.equivalent_nodal_load(m,m.member_loads[1])[[1,2,4,5]])


def test_fast_teaching_match():
    m=beam_model(2)
    for nid in (1,2,3):m.constrain(nid,'uy')
    m.add_uniform_load(1,qy=-500)
    m.add_point_load(2,1.7,fy=-600)
    a=LinearStaticSolver(Mode.TEACHING).solve(m)
    b=LinearStaticSolver(Mode.FAST).solve(m)
    np.testing.assert_allclose(a.displacements,b.displacements)
    np.testing.assert_allclose(a.reactions,b.reactions)
    assert b.trace is None and a.trace is not None


def test_settlement_already_supported():
    m=beam_model(2)
    m.constrain(1,'uy',0)
    m.constrain(2,'uy',-0.001)
    m.constrain(3,'uy',0)
    r=LinearStaticSolver().solve(m)
    assert r.displacement(2,'uy') == pytest.approx(-0.001)
    assert r.reaction(1,'uy')+r.reaction(2,'uy')+r.reaction(3,'uy')==pytest.approx(0,abs=1e-6)


def test_beam_does_not_offer_ux():
    m=beam_model()
    m.constrain(1,'uy');m.constrain(1,'rz')
    m.add_load(2,'uy',-100)
    r=LinearStaticSolver().solve(m)
    with pytest.raises(ValueError,match='not present'):
        r.displacement(1,'ux')
    m.add_load(2,'ux',1)
    with pytest.raises(ValueError,match='not active'):
        LinearStaticSolver().solve(m)


def test_beam_rejects_axial_and_nonhorizontal():
    m=beam_model()
    with pytest.raises(ValueError,match='transverse'):
        m.add_uniform_load(1,qx=1)
    with pytest.raises(ValueError,match='transverse'):
        m.add_point_load(1,1.0,fx=1)
    with pytest.raises(ValueError,match='position'):
        m.add_point_load(1,L+0.1,fy=-1)
    m.nodes[2]=Node(2,L,0.1)
    with pytest.raises(ValueError,match='horizontal'):
        m.elements[1].local_stiffness(m)
    with pytest.raises(ValueError,match='horizontal'):
        m.add_element(Beam2D(3,2,1,1,1))


def test_beam_invalid_reverse_orientation():
    m=beam_model()
    with pytest.raises(ValueError,match='horizontal'):
        m.add_element(Beam2D(2,2,1,1,1))


def test_render_diagrams_for_beam(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m=beam_model(2)
    for nid in (1,2,3):m.constrain(nid,'uy')
    m.add_uniform_load(1,qy=-Q)
    m.add_uniform_load(2,qy=-Q)
    r=LinearStaticSolver().solve(m)
    for key in ('N','V','M'):
        ax=plot_force_diagram(m,r,key)
        out=tmp_path/f'{key}.png';ax.figure.savefig(out)
        assert out.stat().st_size > 1500
        plt.close(ax.figure)
    ax=plot_deformed_shape(m,r)
    ax.figure.savefig(tmp_path/'deformation.png')
    assert (tmp_path/'deformation.png').stat().st_size > 1500
    plt.close(ax.figure)


def test_mixed_beam_frame_truss_dofs():
    m=beam_model()
    m.add_node(Node(3,4,3))
    m.add_element(Truss2D(2,2,3,1,1))
    m.add_element(Frame2D(3,1,3,1,1))
    from matrix_displacement import DOFManager
    dm=DOFManager(m)
    assert all((nid,'uy') in dm.mapping for nid in (1,2,3))
    assert (2,'ux') in dm.mapping
    assert (2,'rz') in dm.mapping
    assert (1,'ux') in dm.mapping
    assert (3,'rz') in dm.mapping
