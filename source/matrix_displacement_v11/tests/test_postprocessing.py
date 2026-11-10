"""V0.3 regression: equilibrium section diagrams and exact beam deflection."""
import numpy as np
import pytest

from matrix_displacement import (
    Node, Material, Section, Frame2D, StructuralModel, Mode, LinearStaticSolver,
    MemberResponse2D, plot_force_diagram, plot_deformed_shape,
    plot_member_section_diagram, plot_structure,
)

L, E, A, I = 4.0, 210e9, .015, 8e-6


def beam(x=L, y=0, fix_i=True, fix_j=False):
    m = StructuralModel()
    m.add_node(Node(1,0,0))
    m.add_node(Node(2,x,y))
    m.add_material(Material(1,E)); m.add_section(Section(1,A,I))
    m.add_element(Frame2D(1,1,2,1,1))
    if fix_i:
        for d in ('ux','uy','rz'): m.constrain(1,d)
    if fix_j:
        for d in ('ux','uy','rz'): m.constrain(2,d)
    return m


def solve(m,mode=Mode.FAST):
    result=LinearStaticSolver(mode).solve(m)
    return result, MemberResponse2D(m,result,1)


def test_empty_member_unloaded_sections_zero():
    m=beam()
    result,r=solve(m)
    for x in (0, L/4, L):
        f=r.section(x)
        assert (f.N,f.V,f.M)==pytest.approx((0.,0.,0.))
        d=r.deformation(x)
        assert (d.ux_local,d.uy_local,d.rz)==pytest.approx((0.,0.,0.))


def test_force_labels_use_physical_values_and_can_be_hidden():
    import matplotlib.pyplot as plt
    m=beam()
    m.add_load(2,'uy',-1000)
    result,_=solve(m)
    ax=plot_force_diagram(m,result,'M',scale=0)
    try:
        labels=[t.get_text() for t in ax.texts if t.get_text().startswith('E1 ')]
        assert len(labels)==2
        assert any('M=-4000 N·m' in t for t in labels)
        assert any('M=0 N·m' in t for t in labels)
    finally:
        plt.close(ax.figure)
    ax=plot_force_diagram(m,result,'M',show_values=False)
    try:
        assert not any(t.get_text().startswith('E1 ') for t in ax.texts)
    finally:
        plt.close(ax.figure)


def test_cantilever_node_force_shear_moment_and_displacement():
    m=beam()
    P=1000
    m.add_load(2,'uy',-P)
    result,r=solve(m)
    for x in (0,1.1,2.,L):
        q=r.section(x)
        assert q.N==pytest.approx(0,abs=1e-8)
        assert q.V==pytest.approx(P)
        assert q.M==pytest.approx(-P*(L-x))
        d=r.deformation(x)
        assert d.uy_local==pytest.approx(-P*x*x*(3*L-x)/(6*E*I),abs=1e-12)
        assert d.rz==pytest.approx(-P*x*(2*L-x)/(2*E*I),abs=1e-12)


def test_uniform_cantilever_shear_moment_and_deflection():
    m=beam();w=1200
    m.add_uniform_load(1,qy=-w)
    _,r=solve(m)
    for x in (0,.4,L/2,3.1,L):
        assert r.section(x).V==pytest.approx(w*(L-x))
        assert r.section(x).M==pytest.approx(-w*(L-x)**2/2,abs=1e-8)
        assert r.deformation(x).uy_local==pytest.approx(
            -w*x*x*(6*L*L-4*L*x+x*x)/(24*E*I),abs=1e-12)


def test_fixed_fixed_uniform_nonzero_midspan_deflection_zero_nodal_dof():
    m=beam(fix_j=True);w=1400
    m.add_uniform_load(1,qy=-w)
    result,r=solve(m)
    np.testing.assert_allclose(result.displacements,0,atol=0)
    assert r.section(0).M==pytest.approx(-w*L**2/12)
    assert r.section(L/2).M==pytest.approx(w*L**2/24)
    assert r.section(L).M==pytest.approx(-w*L**2/12)
    assert r.deformation(L/2).uy_local==pytest.approx(-w*L**4/(384*E*I))
    assert r.deformation(L).uy_local==pytest.approx(0.,abs=1e-12)
    assert r.deformation(L).rz==pytest.approx(0.,abs=1e-12)


def test_fixed_fixed_central_concentrated_load_midspan_deflection():
    m=beam(fix_j=True);P=1700
    m.add_point_load(1,L/2,fy=-P)
    _,r=solve(m)
    assert r.deformation(L/2).uy_local==pytest.approx(-P*L**3/(192*E*I))
    assert r.section(L/2,'left').V==pytest.approx(P/2)
    assert r.section(L/2,'right').V==pytest.approx(-P/2)
    assert r.section(L/2,'left').M==pytest.approx(r.section(L/2,'right').M)


def test_point_load_cantilever_shear_discontinuity_and_moment_continuity():
    m=beam();P=700;a=1.7
    m.add_point_load(1,a,fy=-P)
    _,r=solve(m)
    assert r.section(a,'left').V==pytest.approx(P)
    assert r.section(a,'right').V==pytest.approx(0,abs=1e-8)
    assert r.section(a,'left').M==pytest.approx(-P*(a-a),abs=1e-8)
    assert r.section(a,'right').M==pytest.approx(0,abs=1e-8)
    for x in (0,a/2,a,a+.1,L):
        want=-P*x*x*(3*a-x)/(6*E*I) if x<=a else -P*a*a*(3*x-a)/(6*E*I)
        assert r.deformation(x).uy_local==pytest.approx(want,abs=1e-12)


def test_axial_uniform_redistributed_section_and_displacement():
    m=beam();q=300
    m.add_uniform_load(1,qx=q)
    _,r=solve(m)
    for x in (0,1,2.5,L):
        assert r.section(x).N==pytest.approx(q*(L-x))
        assert r.deformation(x).ux_local==pytest.approx(q*(L*x-x*x/2)/(E*A))
        assert r.section(x).V==pytest.approx(0,abs=1e-9)


def test_axial_point_jump_and_piecewise_displacement():
    m=beam();P=1200;a=1.3
    m.add_point_load(1,a,fx=P)
    _,r=solve(m)
    assert r.section(a,'left').N==pytest.approx(P)
    assert r.section(a,'right').N==pytest.approx(0,abs=1e-8)
    for x in (.2,a,3.6):
        assert r.deformation(x).ux_local==pytest.approx(P*min(x,a)/(E*A))


def test_combined_member_load_example_section_diagram():
    m=beam();w=1200;P=700;a=1.7
    m.add_uniform_load(1,qy=-w)
    m.add_point_load(1,a,fy=-P)
    _,r=solve(m)
    assert r.section(0).V==pytest.approx(w*L+P)
    assert r.section(0).M==pytest.approx(-w*L*L/2-P*a)
    assert r.section(a,'left').V==pytest.approx(w*(L-a)+P)
    assert r.section(a,'right').V==pytest.approx(w*(L-a))
    assert r.section(L,'left').M==pytest.approx(0,abs=1e-8)
    assert r.section(L,'left').V==pytest.approx(0,abs=1e-8)


def test_local_and_global_input_equivalent_deformation_and_diagrams():
    local=beam(x=3,y=4);global_=beam(x=3,y=4)
    local.add_uniform_load(1,qx=-800,qy=-600)
    global_.add_uniform_load(1,qx=0,qy=-1000,system='global')
    local.add_point_load(1,2.1,fx=-800,fy=-600)
    global_.add_point_load(1,2.1,fx=0,fy=-1000,system='global')
    _,r1=solve(local)
    _,r2=solve(global_)
    for x in (0,1.,2.1,4.,5.):
        np.testing.assert_allclose(
            list(vars(r1.section(x)).values()),list(vars(r2.section(x)).values()),rtol=1e-11,atol=1e-8)
        np.testing.assert_allclose(
            list(vars(r1.deformation(x)).values()),list(vars(r2.deformation(x)).values()),rtol=1e-11,atol=1e-11)


def test_inclined_member_global_displacement_transform():
    m=beam(x=3,y=4)
    m.add_load(2,'uy',-800)
    _,r=solve(m)
    for x in (1,2.5,5):
        d=r.deformation(x)
        assert d.ux_global==pytest.approx(.6*d.ux_local-.8*d.uy_local)
        assert d.uy_global==pytest.approx(.8*d.ux_local+.6*d.uy_local)


def test_section_end_forces_with_no_end_point_load():
    m=beam(x=3,y=4)
    m.add_uniform_load(1,qx=90,qy=-150)
    m.add_point_load(1,2.3,fx=100,fy=-300)
    result,r=solve(m)
    q=result.element_end_forces_local[1]
    beginning=r.section(0)
    ending=r.section(r.L,'left')
    assert beginning.N==pytest.approx(-q[0]); assert beginning.V==pytest.approx(q[1]); assert beginning.M==pytest.approx(-q[2])
    assert ending.N==pytest.approx(q[3],abs=1e-7)
    assert ending.V==pytest.approx(-q[4],abs=1e-7)
    assert ending.M==pytest.approx(q[5],abs=1e-7)


def test_end_point_load_diagram_limit_excludes_end_load():
    m=beam();m.add_point_load(1,L,fy=-300)
    _,r=solve(m)
    assert r.section(L,'left').V==pytest.approx(300)
    assert r.section(L,'right').V==pytest.approx(0)
    samples=r.sample_sections(points=10)
    assert samples.V[-1]==pytest.approx(300)


def test_beginning_point_load_included_in_element_cut():
    m=beam();m.add_point_load(1,0,fx=250)
    _,r=solve(m)
    assert r.section(0,'left').N==pytest.approx(250)
    assert r.section(0,'right').N==pytest.approx(0,abs=1e-10)


def test_sampling_duplicates_jump_and_contains_exact_stationary_moment():
    m=beam(fix_j=True)
    m.add_uniform_load(1,qy=-1200)
    m.add_point_load(1,1.7,fy=-500)
    _,r=solve(m)
    samples=r.sample_sections(points=22)
    ids=np.where(np.isclose(samples.x,1.7,rtol=0,atol=1e-12))[0]
    assert len(ids)==2
    assert samples.V[ids[1]]-samples.V[ids[0]]==pytest.approx(-500)
    # A no-point-load fixed beam has maximum positive bending at L/2.
    mm=beam(fix_j=True);mm.add_uniform_load(1,qy=-1000)
    _,rr=solve(mm)
    ss=rr.sample_sections(points=10)
    assert np.any(np.isclose(ss.x,L/2,atol=1e-12))
    assert max(ss.M)==pytest.approx(1000*L**2/24)


def test_many_concentrated_loads_at_same_point_add_exactly():
    m=beam();m.add_point_load(1,2,fy=-100);m.add_point_load(1,2,fy=-200)
    _,r=solve(m)
    assert r.section(2,'right').V-r.section(2,'left').V==pytest.approx(-300)
    s=r.sample_sections(points=10)
    assert len(np.where(np.isclose(s.x,2,atol=1e-12))[0])==2


def test_deformation_matches_ends_even_with_member_loads():
    m=beam()
    m.add_uniform_load(1,qx=250,qy=-1300)
    m.add_point_load(1,1.6,fx=-70,fy=-320)
    result,r=solve(m)
    di=r.d_local
    left=r.deformation(0)
    right=r.deformation(L)
    np.testing.assert_allclose([left.ux_local,left.uy_local,left.rz],di[:3],atol=1e-12)
    np.testing.assert_allclose([right.ux_local,right.uy_local,right.rz],di[3:],atol=1e-11)


def test_section_force_balance_derivatives_away_from_jumps():
    m=beam();m.add_uniform_load(1,qx=120,qy=-350)
    m.add_point_load(1,2.1,fx=-100,fy=280)
    _,r=solve(m)
    x=1.6;h=1e-5
    f0,f1,f2=r.section(x-h),r.section(x),r.section(x+h)
    assert (f2.N-f0.N)/(2*h)==pytest.approx(-120,rel=1e-9)
    assert (f2.V-f0.V)/(2*h)==pytest.approx(-350,rel=1e-9)
    assert (f2.M-f0.M)/(2*h)==pytest.approx(f1.V,rel=1e-9)


def test_modes_have_identical_section_results():
    m=beam();m.add_uniform_load(1,qx=200,qy=-450);m.add_point_load(1,2,fy=-210)
    _,ra=solve(m,Mode.FAST)
    _,rb=solve(m,Mode.TEACHING)
    for x in (0,.5,2,3,L):
        assert ra.section(x)==rb.section(x)
        assert ra.deformation(x)==rb.deformation(x)


@pytest.mark.parametrize('x',[-1,5,np.nan,np.inf,-np.inf])
def test_bad_section_position_rejected(x):
    _,r=solve(beam())
    with pytest.raises(ValueError): r.section(x)
    with pytest.raises(ValueError): r.deformation(x)


def test_bad_side_and_sample_count_rejected():
    _,r=solve(beam())
    with pytest.raises(ValueError):r.section(2,side='top')
    for points in (0,1,True,12.3,'10'):
        with pytest.raises(ValueError):r.sample_sections(points)
        with pytest.raises(ValueError):r.sample_deformation(points)


def test_plotting_creates_all_figure_types(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m=beam();m.add_uniform_load(1,qy=-600);m.add_point_load(1,2,fy=-200)
    result,_=solve(m)
    funcs=[
        lambda:plot_structure(m),
        lambda:plot_force_diagram(m,result,'N'),
        lambda:plot_force_diagram(m,result,'V'),
        lambda:plot_force_diagram(m,result,'M'),
        lambda:plot_deformed_shape(m,result),
        lambda:plot_member_section_diagram(m,result,1,'M'),
    ]
    for i,func in enumerate(funcs):
        ax=func()
        path=tmp_path/f'diagram_{i}.png'
        ax.figure.savefig(path)
        assert path.is_file() and path.stat().st_size>4000
        plt.close(ax.figure)


def test_bad_plot_component_and_scale_rejected():
    import matplotlib
    matplotlib.use('Agg')
    m=beam();result,_=solve(m)
    with pytest.raises(ValueError):plot_force_diagram(m,result,'stress')
    with pytest.raises(ValueError):plot_member_section_diagram(m,result,1,'bad')
    with pytest.raises(ValueError):plot_force_diagram(m,result,'M',scale=-1)
    with pytest.raises(ValueError):plot_deformed_shape(m,result,scale=np.nan)


def test_simple_support_uniform_midspan_deflection_and_bending_peak():
    m=beam(fix_i=False)
    m.constrain(1,'ux');m.constrain(1,'uy');m.constrain(2,'uy')
    w=1500
    m.add_uniform_load(1,qy=-w)
    _,r=solve(m)
    assert r.deformation(L/2).uy_local==pytest.approx(-5*w*L**4/(384*E*I))
    assert r.section(L/2).M==pytest.approx(w*L**2/8)


def test_two_element_uniform_cantilever_section_and_deformation_are_continuous():
    m=StructuralModel()
    for i,x in ((1,0),(2,2),(3,4)):
        m.add_node(Node(i,x,0))
    m.add_material(Material(1,E));m.add_section(Section(1,A,I))
    m.add_element(Frame2D(1,1,2,1,1))
    m.add_element(Frame2D(2,2,3,1,1))
    for d in ('ux','uy','rz'):m.constrain(1,d)
    m.add_uniform_load(1,qy=-500)
    m.add_uniform_load(2,qy=-500)
    result=LinearStaticSolver().solve(m)
    left,right=MemberResponse2D(m,result,1),MemberResponse2D(m,result,2)
    lsec,rsec=left.section(2,'left'),right.section(0,'right')
    assert lsec.V==pytest.approx(rsec.V,abs=1e-9)
    assert lsec.M==pytest.approx(rsec.M,abs=1e-9)
    ld,rd=left.deformation(2),right.deformation(0)
    np.testing.assert_allclose([ld.ux_global,ld.uy_global,ld.rz],
                               [rd.ux_global,rd.uy_global,rd.rz],atol=1e-12)
