"""V0.8 transaction, bounded history and engineering result-inspection tests."""
import pytest
from matrix_displacement.editor import ModelEditor
from matrix_displacement.history import EditHistory
from matrix_displacement.inspection import inspect_node, inspect_member
from matrix_displacement.core import Mode


def setup_frame():
    ed=ModelEditor()
    a=ed.add_node(0,0)
    b=ed.add_node(4,0)
    ed.add_element(a,b)
    ed.set_support(a, {'ux':0,'uy':0,'rz':0})
    return ed, a, b


def test_undo_redo_multi_step():
    ed=ModelEditor(); h=EditHistory(ed)
    h.execute(ed.add_node,0,0)
    h.execute(ed.add_node,4,0)
    assert len(ed.model.nodes)==2
    assert h.can_undo and not h.can_redo
    assert h.undo()
    assert list(ed.model.nodes)==[1]
    assert h.undo()
    assert ed.model.nodes=={}
    assert not h.undo()
    assert h.redo() and h.redo()
    assert len(ed.model.nodes)==2 and not h.can_redo


def test_redo_cleared_after_new_edit():
    ed=ModelEditor();h=EditHistory(ed)
    h.execute(ed.add_node,0,0)
    h.execute(ed.add_node,1,0)
    assert h.undo()
    h.execute(ed.add_node,2,0)
    assert not h.can_redo
    assert ed.model.nodes[2].x==2


def test_invalid_operation_atomic_and_history_unchanged():
    ed=ModelEditor();h=EditHistory(ed)
    h.execute(ed.add_node,0,0)
    with pytest.raises(ValueError):
        h.execute(ed.add_node,0,0)
    assert len(ed.model.nodes)==1
    assert h.undo()
    assert len(ed.model.nodes)==0


def test_transaction_restores_partial_modification():
    ed=ModelEditor();h=EditHistory(ed)
    def broken():
        ed.add_node(1,0)
        raise RuntimeError('deliberate')
    with pytest.raises(RuntimeError):h.execute(broken)
    assert not ed.model.nodes and not h.can_undo


def test_move_node_drag_single_commit():
    ed,a,b=setup_frame();h=EditHistory(ed)
    before=h.capture()
    for x in (4.05,4.15,4.25,4.5):
        ed.move_node(b,x,0)
    assert h.commit(before)
    assert h.undo()
    assert ed.model.nodes[b].x==4
    assert h.redo()
    assert ed.model.nodes[b].x==4.5


def test_invalid_beam_move_preserves_geometry_and_history():
    ed=ModelEditor();a=ed.add_node(0,0);b=ed.add_node(4,0)
    ed.add_element(a,b,'Beam2D');h=EditHistory(ed)
    with pytest.raises(ValueError):h.execute(ed.move_node,b,4,1)
    assert ed.model.nodes[b].y==0 and not h.can_undo


def test_noop_changes_not_recorded():
    ed=ModelEditor();h=EditHistory(ed)
    h.execute(ed.set_defaults,210e9,0.01,8e-6)
    assert not h.can_undo
    assert not h.commit(h.capture())


def test_bounded_history():
    ed=ModelEditor();h=EditHistory(ed,limit=2)
    for x in range(3):h.execute(ed.add_node,x,0)
    assert h.undo() and h.undo() and not h.undo()
    assert len(ed.model.nodes)==1


def test_saved_state_after_undo():
    ed=ModelEditor();h=EditHistory(ed)
    h.execute(ed.add_node,0,0)
    h.mark_saved()
    h.execute(ed.add_node,1,0)
    assert h.is_dirty
    h.undo()
    assert not h.is_dirty
    h.redo()
    assert h.is_dirty


def test_model_replace_clears_history():
    ed=ModelEditor();h=EditHistory(ed)
    h.execute(ed.add_node,0,0)
    ed.reset();h.reset()
    assert not h.can_undo and not h.is_dirty


def test_undo_property_and_member_load_changes():
    ed,a,b=setup_frame();h=EditHistory(ed)
    h.execute(ed.add_member_load,1,'uniform',qy=-1000)
    h.execute(ed.set_element_properties,1,200e9,.03,5e-6)
    assert ed.model.materials[ed.model.elements[1].material_id].E==200e9
    h.undo()
    assert ed.model.materials[ed.model.elements[1].material_id].E==210e9
    h.undo()
    assert ed.model.member_loads==[]
    h.redo();h.redo()
    assert len(ed.model.member_loads)==1


def test_inspection_matches_known_cantilever():
    ed,a,b=setup_frame()
    ed.set_nodal_load(b,uy=-1000)
    r=ed.solve(Mode.FAST)
    node=inspect_node(ed.model,r,b)
    uy=next(item for item in node.entries if item[0]=='uy')
    assert uy[1]==pytest.approx(-1000*4**3/(3*210e9*8e-6))
    assert not uy[3]
    fixed=inspect_node(ed.model,r,a)
    fy=next(item for item in fixed.entries if item[0]=='uy')
    assert fy[2]==pytest.approx(1000)
    member=inspect_member(ed.model,r,1,x=2)
    assert member.V==pytest.approx(1000,abs=1e-6)
    assert member.M==pytest.approx(-2000,abs=1e-6)
    assert member.ranges['M'][0]==pytest.approx(-4000,abs=1e-6)


def test_section_side_query_at_point_force():
    ed,a,b=setup_frame()
    ed.add_member_load(1,'point',position=2,fy=-900)
    r=ed.solve()
    left=inspect_member(ed.model,r,1,x=2,side='left')
    right=inspect_member(ed.model,r,1,x=2,side='right')
    assert right.V-left.V==pytest.approx(-900)
    assert right.M==pytest.approx(left.M)


def test_inspect_truss_and_invalid_element():
    ed=ModelEditor();ed.load_example('truss');r=ed.solve()
    member=inspect_member(ed.model,r,2,x=0)
    assert member.V==0 and member.M==0
    with pytest.raises(KeyError):inspect_member(ed.model,r,999)
    with pytest.raises(KeyError):inspect_node(ed.model,r,999)


def test_invalid_history_limit():
    ed=ModelEditor()
    with pytest.raises(ValueError):EditHistory(ed,0)
    with pytest.raises(ValueError):EditHistory(ed,True)


def test_replace_only_selected_load_and_undo():
    ed,a,b=setup_frame();h=EditHistory(ed)
    h.execute(ed.add_member_load,1,'uniform',qy=-1000)
    h.execute(ed.add_member_load,1,'point',position=2,fy=-500)
    h.execute(ed.replace_member_load,0,'linear',qy_i=-200,qy_j=-700)
    assert type(ed.model.member_loads[0]).__name__=='LinearLoad2D'
    assert ed.model.member_loads[1].fy == -500
    assert h.undo()
    assert ed.model.member_loads[0].qy == -1000
    assert len(ed.model.member_loads)==2


def test_delete_load_by_index_with_history():
    ed,a,b=setup_frame();h=EditHistory(ed)
    h.execute(ed.add_member_load,1,'uniform',qy=-100)
    h.execute(ed.add_member_load,1,'uniform',qy=-200)
    h.execute(ed.delete_member_load,0)
    assert len(ed.model.member_loads)==1 and ed.model.member_loads[0].qy==-200
    h.undo()
    assert [load.qy for load in ed.model.member_loads]==[-100,-200]


def test_replace_load_rejects_invalid_position_atomically():
    ed,a,b=setup_frame();h=EditHistory(ed)
    ed.add_member_load(1,'point',position=2,fy=-500)
    with pytest.raises(ValueError):
        h.execute(ed.replace_member_load,0,'point',position=10,fy=-500)
    assert ed.model.member_loads[0].position==2 and not h.can_undo


def test_delete_missing_load_does_not_change_model():
    ed,a,b=setup_frame();h=EditHistory(ed)
    with pytest.raises(ValueError):h.execute(ed.delete_member_load,0)
    with pytest.raises(ValueError):h.execute(ed.replace_member_load,True,'uniform',qy=-1)
    assert not h.can_undo
