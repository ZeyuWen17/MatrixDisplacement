"""Persistence roundtrips, strict schema checks, and teaching report tests."""
from copy import deepcopy
import json
import numpy as np
import pytest
from matrix_displacement import (
    StructuralModel, Node, Material, Section, Frame2D, Truss2D, Beam2D,
    Mode, LinearStaticSolver, model_to_dict, model_from_dict,
    save_model_json, load_model_json, render_teaching_report, save_teaching_report,
)


def make_model():
    m=StructuralModel()
    for args in [(1,0,0),(2,4,0),(3,8,0),(4,6,3)]:m.add_node(Node(*args))
    m.add_material(Material(1,210e9))
    m.add_section(Section(1,0.012,8e-6))
    m.add_element(Beam2D(1,1,2,1,1))
    m.add_element(Beam2D(2,2,3,1,1))
    m.add_element(Truss2D(3,2,4,1,1))
    m.add_element(Frame2D(4,1,4,1,1,release_j=True))
    for d in ('ux','uy','rz'):m.constrain(1,d)
    m.constrain(2,'uy')
    m.constrain(3,'uy')
    m.constrain(4,'ux')
    m.add_load(3,'uy',-100)
    m.add_load(2,'rz',20)
    m.add_uniform_load(1,qy=-1100,system='global')
    m.add_point_load(2,position=2.3,fy=-250)
    return m


def test_round_trip_all_element_types_and_loads(tmp_path):
    m=make_model()
    p=tmp_path/'model.json'
    save_model_json(m,p)
    loaded=load_model_json(p)
    assert model_to_dict(m)==model_to_dict(loaded)
    assert p.read_text(encoding='utf8').startswith('{')
    original=LinearStaticSolver(Mode.TEACHING).solve(m)
    restored=LinearStaticSolver(Mode.TEACHING).solve(loaded)
    np.testing.assert_allclose(original.displacements,restored.displacements)
    np.testing.assert_allclose(original.reactions,restored.reactions)
    for eid in m.elements:
        np.testing.assert_allclose(original.element_end_forces_local[eid],restored.element_end_forces_local[eid])


def test_json_is_stable_in_different_insertion_order():
    m=make_model()
    data=model_to_dict(m)
    m2=model_from_dict(data)
    assert data==model_to_dict(m2)


@pytest.mark.parametrize('edit,pattern',[
    (lambda d:d.update(schema_version=99),'schema_version'),
    (lambda d:d.update(units='kN'),'SI'),
    (lambda d:d.update(other='bad'),'keys'),
    (lambda d:d['elements'][0].update(type='Unknown'),'Unknown'),
    (lambda d:d['elements'][0].update(extra=1),'keys'),
    (lambda d:d['nodes'][0].update(id=True),'integer'),
    (lambda d:d['nodes'][0].update(x=float('nan')),'finite'),
    (lambda d:d['materials'][0].update(E=0),'positive'),
    (lambda d:d['elements'][3].update(release_j='true'),'boolean'),
    (lambda d:d['member_loads'][0].update(qy='bad'),'number'),
    (lambda d:d['member_loads'][0].update(type='InjectedLoad'),'Unknown'),
    (lambda d:d['member_loads'][1].update(position=99),'position'),
    (lambda d:d['constraints'].append(deepcopy(d['constraints'][0])),'Duplicate'),
    (lambda d:d['nodal_loads'].append(deepcopy(d['nodal_loads'][0])),'Duplicate'),
])
def test_json_rejects_malformed_or_unknown(edit,pattern):
    d=model_to_dict(make_model())
    edit(d)
    with pytest.raises(ValueError,match=pattern):model_from_dict(d)


def test_json_rejects_nonstandard_nan(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"x":NaN}',encoding='utf8')
    with pytest.raises(ValueError,match='NaN'):load_model_json(p)


def test_json_rejects_invalid_json(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{',encoding='utf8')
    with pytest.raises(ValueError,match='Invalid JSON'):load_model_json(p)


def test_teaching_report_contains_real_matrices(tmp_path):
    m=make_model()
    r=LinearStaticSolver(Mode.TEACHING).solve(m)
    report=render_teaching_report(m,r)
    for key in ('矩阵位移法教学计算报告','自由度编号','局部刚度矩阵','整体刚度矩阵',
                '缩减刚度矩阵','等效节点荷载','节点位移','支座反力','Beam2D','Truss2D','Frame2D'):
        assert key in report
    assert str(r.dof_manager.ndof) in report
    p=tmp_path/'reports'/'calculation.md'
    assert save_teaching_report(m,r,p)==p
    assert p.read_text(encoding='utf8')==report


def test_fast_mode_report_rejected():
    m=make_model();r=LinearStaticSolver(Mode.FAST).solve(m)
    with pytest.raises(ValueError,match='TEACHING'):
        render_teaching_report(m,r)


def test_report_limits():
    m=make_model();r=LinearStaticSolver(Mode.TEACHING).solve(m)
    with pytest.raises(ValueError,match='max_dofs'):
        render_teaching_report(m,r,max_dofs=1)
    with pytest.raises(ValueError,match='digits'):
        render_teaching_report(m,r,digits=20)
    assert len(render_teaching_report(m,r,max_dofs=None))>1000
