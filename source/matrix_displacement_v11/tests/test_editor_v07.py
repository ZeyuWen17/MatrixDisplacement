"""V0.7 model-editor validation and solver integration; requires no Qt."""
import numpy as np
import pytest
from matrix_displacement import Mode, LinearStaticSolver, model_to_dict, model_from_dict
from matrix_displacement.editor import ModelEditor


def test_add_nodes_and_elements_and_dofs():
    e = ModelEditor()
    assert e.add_node(0,0) == 1
    assert e.add_node(2,1) == 2
    assert e.add_element(1,2,'Frame2D') == 1
    assert e.active_dofs(1) == {'ux','uy','rz'}
    with pytest.raises(ValueError,match='相同坐标'):
        e.add_node(0,0)


def test_beam_auto_direction_and_dofs():
    e=ModelEditor()
    e.add_node(3,0);e.add_node(0,0)
    i=e.add_element(1,2,'Beam2D')
    assert (e.model.elements[i].node_i,e.model.elements[i].node_j)==(2,1)
    assert e.active_dofs(2)=={'uy','rz'}
    with pytest.raises(ValueError):
        e.set_nodal_load(1,ux=1)
    with pytest.raises(ValueError):
        e.set_support(1,{'ux':0})


def test_truss_dof_and_support_validation():
    e=ModelEditor();e.load_example('truss')
    assert e.active_dofs(3)=={'ux','uy'}
    with pytest.raises(ValueError):e.set_support(3,{'rz':0})
    with pytest.raises(ValueError):e.add_member_load(1,'uniform',qy=-1000)
    r=e.solve(Mode.FAST)
    assert r.reaction(1,'uy')==pytest.approx(1500)


def test_frame_solve_two_modes():
    e=ModelEditor();e.load_example('cantilever')
    a=e.solve(Mode.FAST); b=e.solve(Mode.TEACHING)
    np.testing.assert_allclose(a.displacements,b.displacements)
    assert a.trace is None and b.trace is not None
    assert a.reaction(1,'uy')==pytest.approx(5500)
    assert a.reaction(1,'rz')==pytest.approx(10790)


def test_continuous_beam_example():
    e=ModelEditor();e.load_example('continuous_beam')
    r=e.solve()
    assert r.reaction(1,'uy')==pytest.approx(1500)
    assert r.reaction(2,'uy')==pytest.approx(5000)
    assert r.reaction(3,'uy')==pytest.approx(1500)


def test_support_replacement_and_prescribed():
    e=ModelEditor();e.load_example('cantilever')
    e.set_support(1,{'ux':0,'uy':0.001,'rz':0})
    assert e.model.constraints[(1,'uy')]==pytest.approx(0.001)
    e.set_support(1,{'uy':0})
    assert (1,'ux') not in e.model.constraints


def test_nodal_load_replaces_not_accumulates():
    e=ModelEditor();e.load_example('cantilever')
    e.set_nodal_load(2,uy=-1000)
    e.set_nodal_load(2,uy=-2000)
    assert e.model.loads[(2,'uy')]==-2000
    e.set_nodal_load(2,uy=0)
    assert (2,'uy') not in e.model.loads


def test_edit_element_copy_on_write():
    e=ModelEditor();e.load_example('continuous_beam')
    orig=e.model.elements[2]
    orig_I=e.model.sections[orig.section_id].I
    e.set_element_properties(1,210e9,.01,9e-6)
    assert e.model.sections[orig.section_id].I==orig_I
    assert e.model.sections[e.model.elements[1].section_id].I==9e-6
    assert e.model.elements[2].section_id==orig.section_id


def test_update_hinge_changes_element():
    e=ModelEditor();e.load_example('cantilever')
    e.set_element_properties(1,210e9,.01,8e-6,release_j=True)
    assert e.model.elements[1].release_j
    assert 'rz' not in e.active_dofs(2)


def test_invalid_coordinates_and_element_type():
    e=ModelEditor();e.add_node(0,0);e.add_node(1,1)
    with pytest.raises(ValueError):e.add_node(float('nan'),3)
    with pytest.raises(ValueError):e.add_element(1,2,'Beam2D')
    with pytest.raises(ValueError):e.add_element(1,2,'Hologram')
    with pytest.raises(ValueError):e.set_defaults(210e9,-1,8e-6)


def test_move_node_transaction_and_load_range():
    e=ModelEditor();e.load_example('cantilever')
    with pytest.raises(ValueError):e.move_node(2,0,0)
    assert e.model.nodes[2].x==4
    e.move_node(2,3,0)
    assert e.model.nodes[2].x==3
    with pytest.raises(ValueError):e.add_member_load(1,'point',position=4,fy=-1000)
    assert len(e.model.member_loads)==2
    # Old 1.7m point load still belongs to length-3 element.
    e.solve()


def test_move_node_keeps_model_unchanged_on_load_out_of_range():
    e=ModelEditor();e.load_example('cantilever')
    with pytest.raises(ValueError):e.move_node(2,1,0)
    assert e.model.nodes[2].x==4


def test_delete_node_cascades_and_prunes():
    e=ModelEditor();e.load_example('continuous_beam')
    e.remove_node(2)
    assert len(e.model.elements)==0
    assert len(e.model.member_loads)==0
    assert all(k[0]!=2 for k in e.model.constraints)


def test_delete_element_prunes_loads():
    e=ModelEditor();e.load_example('cantilever')
    e.remove_element(1)
    assert not e.model.member_loads


def test_clear_member_loads():
    e=ModelEditor();e.load_example('cantilever')
    e.clear_member_loads(1)
    assert not e.model.member_loads
    assert e.solve().reaction(1,'uy')==pytest.approx(0)


def test_roundtrip_and_legacy_model_schema(tmp_path):
    e=ModelEditor();e.load_example('cantilever')
    file=tmp_path/'struct.json'
    e.save(file)
    fresh=ModelEditor();fresh.open(file)
    assert model_to_dict(fresh.model)==model_to_dict(e.model)
    np.testing.assert_allclose(fresh.solve().displacements,e.solve().displacements)


def test_invalid_open_does_not_clobber_model(tmp_path):
    e=ModelEditor();e.load_example('truss')
    before=model_to_dict(e.model)
    file=tmp_path/'broken.json';file.write_text('{not json',encoding='utf-8')
    with pytest.raises(ValueError):e.open(file)
    assert model_to_dict(e.model)==before


def test_invalid_support_atomic():
    e=ModelEditor();e.load_example('cantilever')
    before=dict(e.model.constraints)
    with pytest.raises(ValueError):e.set_support(1,{'ux':0,'uy':float('nan')})
    assert e.model.constraints==before


def test_invalid_nodal_load_atomic():
    e=ModelEditor();e.load_example('cantilever')
    before=dict(e.model.loads)
    with pytest.raises(ValueError):e.set_nodal_load(2,uy=-1000,rz=float('inf'))
    assert e.model.loads==before


def test_element_release_for_truss_disallowed():
    e=ModelEditor();e.load_example('truss')
    with pytest.raises(ValueError):e.add_element(1,2,'Truss2D',release_i=True)
    with pytest.raises(ValueError):e.set_element_properties(1,210e9,.01,8e-6,release_i=True)


def test_example_reset_and_model_json():
    e=ModelEditor();e.load_example('truss')
    e.reset()
    assert not e.model.nodes and not e.model.elements
    e.load_example('continuous_beam')
    obj=model_from_dict(model_to_dict(e.model))
    assert len(obj.elements)==2


def test_incompatible_dofs_pruned_when_element_created():
    e=ModelEditor()
    e.add_node(0,0);e.add_node(2,0)
    e.set_support(1,{'ux':0,'uy':0,'rz':0})
    e.add_element(1,2,'Beam2D')
    assert (1,'ux') not in e.model.constraints
    assert (1,'uy') in e.model.constraints


def test_rotational_dof_pruned_after_hinge():
    e=ModelEditor();e.load_example('cantilever')
    e.set_support(2,{'rz':0})
    e.set_element_properties(1,210e9,.01,8e-6,release_j=True)
    assert (2,'rz') not in e.model.constraints


def test_editor_linear_load_roundtrip(tmp_path):
    e=ModelEditor();e.load_example('continuous_beam')
    e.clear_member_loads(1)
    e.add_member_load(1,'linear',qx_i=0.,qy_i=0.,qx_j=0.,qy_j=-1500.)
    r=e.solve()
    assert np.isfinite(r.displacements).all()
    path=tmp_path/'linear.json';e.save(path)
    fresh=ModelEditor();fresh.open(path)
    np.testing.assert_allclose(fresh.solve().displacements,r.displacements)


def test_invalid_beam_axial_load_not_added():
    e=ModelEditor();e.load_example('continuous_beam')
    before=len(e.model.member_loads)
    with pytest.raises(ValueError):e.add_member_load(1,'uniform',qx=1200)
    assert len(e.model.member_loads)==before
