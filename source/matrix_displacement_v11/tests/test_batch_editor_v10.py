"""Batch model edits: one history entry, structural integrity, atomic rollback."""
import pytest

from matrix_displacement.core import Mode
from matrix_displacement.editor import ModelEditor
from matrix_displacement.history import EditHistory
from matrix_displacement.io import model_to_dict


def make_chain(kind='Frame2D'):
    ed=ModelEditor()
    for x,y in ((0,0),(2,0),(4,0),(6,0)):
        ed.add_node(x,y)
    for i in range(1,4):
        ed.add_element(i,i+1,kind)
    return ed


def test_group_translate_and_single_undo_redo():
    ed=make_chain()
    before=model_to_dict(ed.model)
    h=EditHistory(ed)
    h.execute(ed.translate_nodes,[2,3],0.5,1)
    assert ed.model.nodes[2].x==2.5
    assert ed.model.nodes[3].y==1
    assert ed.model.nodes[1].x==0
    assert h.undo()
    assert model_to_dict(ed.model)==before
    assert not h.can_undo
    assert h.redo()
    assert ed.model.nodes[3].x==4.5


def test_multi_node_move_allows_valid_swap():
    ed=ModelEditor()
    ed.add_node(0,0)
    ed.add_node(1,0)
    ed.move_nodes({1:(1,0),2:(0,0)})
    assert ed.model.nodes[1].x==1 and ed.model.nodes[2].x==0


def test_multi_node_move_invalid_restores_geometry():
    ed=make_chain('Beam2D')
    before=model_to_dict(ed.model)
    with pytest.raises(ValueError):
        ed.move_nodes({2:(2,1),3:(4,1)})
    assert model_to_dict(ed.model)==before


def test_translate_rejects_duplicate_position_without_partial_move():
    ed=make_chain()
    before=model_to_dict(ed.model)
    h=EditHistory(ed)
    with pytest.raises(ValueError):
        h.execute(ed.translate_nodes,[2],2,0)
    assert model_to_dict(ed.model)==before
    assert not h.can_undo


def test_translate_unknown_node_and_nonfinite():
    ed=make_chain()
    with pytest.raises(ValueError):ed.translate_nodes([999],1,0)
    with pytest.raises(ValueError):ed.translate_nodes([1],float('nan'),0)


def test_bulk_properties_preserve_end_releases_and_undo_once():
    ed=make_chain()
    ed.set_element_properties(1,210e9,.02,8e-6,release_i=True)
    h=EditHistory(ed)
    before=model_to_dict(ed.model)
    h.execute(ed.set_elements_properties,[1,2,3],200e9,.03,5e-6)
    assert all(ed.model.materials[e.material_id].E==200e9 for e in ed.model.elements.values())
    assert ed.model.elements[1].release_i is True
    assert h.undo()
    assert model_to_dict(ed.model)==before
    assert not h.can_undo


def test_invalid_bulk_properties_atomic_and_no_history():
    ed=make_chain();h=EditHistory(ed)
    before=model_to_dict(ed.model)
    with pytest.raises(ValueError):h.execute(ed.set_elements_properties,[1,2],0,.02,1e-5)
    assert model_to_dict(ed.model)==before
    assert not h.can_undo
    with pytest.raises(ValueError):h.execute(ed.set_elements_properties,[1,99],210e9,.02,1e-5)
    assert model_to_dict(ed.model)==before


def test_batch_delete_cascades_member_load_and_node_load():
    ed=make_chain()
    ed.add_member_load(2,'uniform',qy=-800)
    ed.set_nodal_load(2,uy=-400)
    ed.set_support(2,{'ux':0})
    h=EditHistory(ed)
    baseline=model_to_dict(ed.model)
    h.execute(ed.remove_many,node_ids={2},element_ids={3})
    assert set(ed.model.nodes)=={1,3,4}
    assert not ed.model.elements
    assert not ed.model.member_loads
    assert not any(k[0]==2 for k in ed.model.constraints)
    assert not any(k[0]==2 for k in ed.model.loads)
    assert h.undo()
    assert model_to_dict(ed.model)==baseline
    assert h.redo()
    assert ed.model.elements=={}


def test_delete_only_elements_keep_unrelated_nodes():
    ed=make_chain()
    ed.remove_many(element_ids=[1,3])
    assert set(ed.model.elements)=={2}
    assert set(ed.model.nodes)=={1,2,3,4}


def test_invalid_delete_atomic():
    ed=make_chain();before=model_to_dict(ed.model)
    with pytest.raises(ValueError):ed.remove_many(node_ids=[2,888],element_ids=[1])
    assert model_to_dict(ed.model)==before
    with pytest.raises(ValueError):ed.remove_many(node_ids=[1],element_ids=[999])
    assert model_to_dict(ed.model)==before


def test_batch_edits_keep_solver_usable():
    ed=ModelEditor();ed.load_example('cantilever')
    ed.translate_nodes([2],1,0)
    ed.set_elements_properties([1],200e9,.02,9e-6)
    result=ed.solve(Mode.TEACHING)
    assert result is not None
    assert result.reactions.size>0


def test_noop_batch_does_not_create_history():
    ed=make_chain();h=EditHistory(ed)
    h.execute(ed.move_nodes,{})
    h.execute(ed.remove_many,node_ids=[],element_ids=[])
    assert not h.can_undo
