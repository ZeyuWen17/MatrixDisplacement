"""V0.6 regression: linearly varying loads, sectional fields, CSV and assembly trace."""
import csv
import json
from math import sqrt
import numpy as np
import pytest

from matrix_displacement import (
    Node, Material, Section, StructuralModel, Beam2D, Frame2D, Truss2D,
    LinearLoad2D, UniformLoad2D, LinearStaticSolver, Mode,
    MemberResponse2D, BeamResponse2D, render_teaching_report,
    model_to_dict, model_from_dict, save_model_json, load_model_json,
    export_results_csv,
)

E, A, I, L, w = 210e9, 0.01, 8e-6, 4., 1000.


def make_beam():
    m = StructuralModel()
    m.add_node(Node(1, 0, 0));m.add_node(Node(2, L, 0))
    m.add_material(Material(1,E));m.add_section(Section(1,A,I))
    m.add_element(Beam2D(1,1,2,1,1))
    return m


def make_frame(release_i=False, release_j=False, coords=(L,0)):
    m=StructuralModel()
    m.add_node(Node(1,0,0)); m.add_node(Node(2,*coords))
    m.add_material(Material(1,E)); m.add_section(Section(1,A,I))
    m.add_element(Frame2D(1,1,2,1,1,release_i,release_j))
    return m


def solve_simple_triangle(mode=Mode.FAST):
    m=make_beam()
    m.constrain(1,'uy'); m.constrain(2,'uy')
    m.add_linear_load(1,qy_i=0,qy_j=-w)
    return m, LinearStaticSolver(mode).solve(m)


def test_linear_load_exact_equivalent_beam_and_frame():
    b=make_beam()
    f=make_frame()
    b.add_linear_load(1,qy_i=0,qy_j=-w)
    f.add_linear_load(1,qy_i=0,qy_j=-w)
    fb=b.elements[1].equivalent_nodal_load(b,b.member_loads[0])
    ff=f.elements[1].equivalent_nodal_load(f,f.member_loads[0])
    np.testing.assert_allclose(fb, ff[[1,2,4,5]], rtol=1e-13)
    np.testing.assert_allclose(fb,[-3*w*L/20,-2*w*L*L/60,
                                    -7*w*L/20,+3*w*L*L/60],atol=1e-9)


def test_linear_uniform_special_case_matches_uniform():
    for m in (make_beam(),make_frame()):
        elm=m.elements[1]
        uniform=elm.equivalent_nodal_load(m,UniformLoad2D(1, qy=-w))
        linear=elm.equivalent_nodal_load(m,LinearLoad2D(1,qy_i=-w,qy_j=-w))
        np.testing.assert_allclose(uniform,linear,atol=1e-12)


def test_triangular_load_reactions_and_moment_extremum():
    m,r=solve_simple_triangle()
    assert r.reaction(1,'uy') == pytest.approx(w*L/6)
    assert r.reaction(2,'uy') == pytest.approx(w*L/3)
    field=BeamResponse2D(m,r,1)
    assert field.section(0).M == pytest.approx(0,abs=1e-10)
    assert field.section(L).M == pytest.approx(0,abs=1e-9)
    assert field.section(L/2).M == pytest.approx(w*L*L/16)
    root=L/sqrt(3)
    assert field.section(root).V == pytest.approx(0,abs=1e-10)
    assert field.section(root).M == pytest.approx(w*L*L/(9*sqrt(3)))
    sample=field.sample_sections(20)
    assert any(abs(x-root)<1e-10 for x in sample.x)
    assert max(sample.M) == pytest.approx(w*L*L/(9*sqrt(3)))


def test_triangular_load_elastic_line_exact():
    m,r=solve_simple_triangle()
    field=BeamResponse2D(m,r,1)
    assert field.deformation(0).uy_local == pytest.approx(0,abs=1e-12)
    assert field.deformation(L).uy_local == pytest.approx(0,abs=1e-12)
    expected_mid=(-7*w*L**4/(720*E*I) + w*L**4/(288*E*I)
                  - w*L**4/(3840*E*I))
    assert field.deformation(L/2).uy_local == pytest.approx(expected_mid)
    # Central finite-difference EI v'' = M (away from endpoints).
    x=0.4*L;h=0.0005
    fd=(field.deformation(x+h).uy_local-2*field.deformation(x).uy_local+
        field.deformation(x-h).uy_local)/h**2
    assert E*I*fd == pytest.approx(field.section(x).M,rel=5e-7)


def test_frame_linear_load_transforms_global_components():
    m=make_frame(coords=(3.,4.))
    m.add_linear_load(1,qy_i=-100,qy_j=-300,system='global')
    # Global -Y decomposes into local (qx,qy)=(-s*q, -c*q).
    eq=m.elements[1].equivalent_nodal_load(m,m.member_loads[0])
    assert eq[0]+eq[3] == pytest.approx(-0.8*200*5)
    assert eq[1]+eq[4] == pytest.approx(-0.6*200*5)
    assert -1 < eq[0] / (eq[0]+eq[3]) < 1


def test_axial_linear_load_cantilever():
    m=make_frame()
    for dof in ('ux','uy','rz'):m.constrain(1,dof)
    m.add_linear_load(1,qx_i=0,qx_j=w)
    r=LinearStaticSolver().solve(m)
    assert r.reaction(1,'ux') == pytest.approx(-w*L/2)
    assert r.displacement(2,'ux') == pytest.approx(w*L**2/(3*E*A))
    field=MemberResponse2D(m,r,1)
    assert field.section(0).N == pytest.approx(w*L/2)
    assert field.section(L).N == pytest.approx(0,abs=1e-10)
    assert field.deformation(L).ux_local == pytest.approx(w*L**2/(3*E*A))


def test_released_frame_triangular_load_zero_end_moment():
    m=make_frame(release_i=True, release_j=True)
    m.constrain(1,'ux');m.constrain(1,'uy');m.constrain(2,'uy')
    m.add_linear_load(1,qy_i=0,qy_j=-w)
    r=LinearStaticSolver().solve(m)
    assert r.reaction(1,'uy')==pytest.approx(w*L/6)
    assert r.reaction(2,'uy')==pytest.approx(w*L/3)
    assert r.element_end_forces_local[1][2]==pytest.approx(0,abs=1e-8)
    assert r.element_end_forces_local[1][5]==pytest.approx(0,abs=1e-8)
    field=MemberResponse2D(m,r,1)
    assert field.deformation(0).rz != pytest.approx(field.deformation(L).rz)


def test_mix_constant_and_linear_load_superposition():
    m=make_beam()
    m.constrain(1,'uy');m.constrain(2,'uy')
    m.add_uniform_load(1,qy=-100)
    m.add_linear_load(1,qy_i=0,qy_j=-200)
    r=LinearStaticSolver().solve(m)
    assert r.reaction(1,'uy')==pytest.approx(100*L/2+200*L/6)
    assert r.reaction(2,'uy')==pytest.approx(100*L/2+200*L/3)


def test_beam_rejects_axial_linear_load_and_truss_rejects_all_member_loads():
    m=make_beam()
    with pytest.raises(ValueError,match='transverse'):
        m.add_linear_load(1,qx_i=2)
    m2=make_frame();m2.elements[1]=Truss2D(1,1,2,1,1)
    with pytest.raises(ValueError,match='nodal loads only'):
        m2.add_linear_load(1,qy_j=-w)


@pytest.mark.parametrize('field', ['qx_i','qy_i','qx_j','qy_j'])
def test_linear_load_nonfinite_rejected(field):
    with pytest.raises(ValueError,match='finite'):
        LinearLoad2D(1,**{field:float('nan')})


def test_json_v2_roundtrip_with_linear_and_v1_compatibility(tmp_path):
    m,r=solve_simple_triangle()
    path=tmp_path/'model.json'
    save_model_json(m,path)
    data=json.loads(path.read_text())
    assert data['schema_version']==2
    assert data['member_loads'][0]['type']=='LinearLoad2D'
    restored=load_model_json(path)
    restored_result=LinearStaticSolver().solve(restored)
    np.testing.assert_allclose(r.reactions,restored_result.reactions)
    no_linear=make_beam()
    d=model_to_dict(no_linear)
    d['schema_version']=1
    assert isinstance(model_from_dict(d),StructuralModel)
    d['member_loads']=data['member_loads']
    with pytest.raises(ValueError,match='requires schema_version 2'):
        model_from_dict(d)
    d['schema_version']=3
    with pytest.raises(ValueError,match='schema_version'):
        model_from_dict(d)


def test_teaching_assembly_incremental_matrices_and_report():
    m=make_beam()
    m.add_node(Node(3,2*L,0))
    m.add_element(Beam2D(2,2,3,1,1))
    for nid in (1,2,3):m.constrain(nid,'uy')
    m.add_linear_load(1,qy_j=-w)
    r=LinearStaticSolver(Mode.TEACHING).solve(m)
    prev=np.zeros_like(r.stiffness)
    for entry in r.trace['assembly']:
        idx=entry['indices']
        prev[np.ix_(idx,idx)]+=entry['contribution']
        np.testing.assert_allclose(prev,entry['stiffness_after'])
    np.testing.assert_allclose(prev,r.stiffness)
    report=render_teaching_report(m,r)
    assert '按单元叠加的组装过程' in report
    assert '步骤 2 — 单元 2' in report
    assert 'LinearLoad2D' in report
    assert '本步组装完成后的整体矩阵' in report
    assert LinearStaticSolver().solve(m).trace is None


def test_csv_results_encoding_contents_and_two_modes(tmp_path):
    for mode in (Mode.FAST,Mode.TEACHING):
        m,r=solve_simple_triangle(mode)
        out=tmp_path/mode.value
        paths=export_results_csv(m,r,out,points=30)
        assert set(paths)=={'nodal','end_forces','sections','deformations'}
        assert all(v.exists() for v in paths.values())
        assert paths['nodal'].read_bytes().startswith(b'\xef\xbb\xbf')
        with paths['nodal'].open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        assert len(rows)==4
        assert next(row for row in rows if row['node_id']=='1' and row['dof']=='uy')['reaction']==str(w*L/6) or pytest.approx(float(next(row for row in rows if row['node_id']=='1' and row['dof']=='uy')['reaction']))==w*L/6
        with paths['sections'].open(encoding='utf-8-sig', newline='') as f:
            sections=list(csv.DictReader(f))
        assert max(float(row['M_Nm']) for row in sections)==pytest.approx(w*L*L/(9*sqrt(3)))
        with paths['deformations'].open(encoding='utf-8-sig',newline='') as f:
            assert len(list(csv.DictReader(f)))==30


def test_csv_point_jump_records_both_sides(tmp_path):
    m=make_beam()
    m.constrain(1,'uy');m.constrain(2,'uy')
    m.add_point_load(1,L/2,fy=-w)
    r=LinearStaticSolver().solve(m)
    paths=export_results_csv(m,r,tmp_path,points=10)
    with paths['sections'].open(encoding='utf-8-sig',newline='') as f:
        items=[row for row in csv.DictReader(f) if float(row['x_m'])==L/2]
    assert len(items)==2
    assert {i['side'] for i in items}=={'left','right'}
    assert float(items[0]['V_N'])-float(items[1]['V_N'])==pytest.approx(w)


def test_csv_export_minimal_and_validation(tmp_path):
    m,r=solve_simple_triangle()
    assert set(export_results_csv(m,r,tmp_path/'x',include_sections=False))=={'nodal','end_forces'}
    with pytest.raises(ValueError,match='points'):
        export_results_csv(m,r,tmp_path,points=1)
    with pytest.raises(ValueError,match='points'):
        export_results_csv(m,r,tmp_path,points=True)


def test_linear_load_structure_arrows_render(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matrix_displacement import plot_structure
    m, _ = solve_simple_triangle()
    ax=plot_structure(m,show_loads=True)
    assert len(ax.texts) > 0
    png=tmp_path/'triangular_structure.png'
    ax.figure.savefig(png)
    plt.close(ax.figure)
    assert png.stat().st_size > 2000
