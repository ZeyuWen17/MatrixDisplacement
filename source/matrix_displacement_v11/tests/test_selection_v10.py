"""Geometry and deterministic selection tests without Qt."""
import pytest

from matrix_displacement.editor import ModelEditor
from matrix_displacement.selection import (
    box_from_corners, select_in_rectangle, apply_selection,
)


def model():
    editor = ModelEditor()
    for x,y in ((0,0),(4,0),(4,3),(8,3),(6,6)):
        editor.add_node(x,y)
    editor.add_element(1,2)
    editor.add_element(2,3)
    editor.add_element(3,4)
    editor.add_element(3,5)
    return editor.model


def test_box_normalization():
    assert box_from_corners((4,6),(-1,-3)) == (-1.,-3.,4.,6.)
    assert box_from_corners((-1,-3),(4,6)) == (-1.,-3.,4.,6.)


@pytest.mark.parametrize('bad', [float('nan'),float('inf'),-float('inf')])
def test_box_rejects_nonfinite(bad):
    with pytest.raises(ValueError):
        box_from_corners((bad,0),(1,2))


def test_window_requires_both_endpoints():
    m = model()
    hits = select_in_rectangle(m,(3.9,-1),(5,3.1),mode='window')
    assert ('node',2) in hits and ('node',3) in hits
    assert ('element',2) in hits
    assert ('element',1) not in hits
    assert ('element',3) not in hits
    assert ('element',4) not in hits


def test_crossing_includes_intersecting_segment_even_without_endpoint():
    m = model()
    # This window crosses the middle of horizontal element 1.
    hits = select_in_rectangle(m,(1,-.5),(2,.5),mode='crossing')
    assert hits == (('element',1),)


def test_right_to_left_auto_crosses_left_to_right_auto_contains():
    m=model()
    assert ('element',1) in select_in_rectangle(m,(2,0.5),(1,-0.5))
    assert ('element',1) not in select_in_rectangle(m,(1,-0.5),(2,0.5))


def test_boundary_touch_selects():
    m=model()
    hits=select_in_rectangle(m,(3.5,0),(4.5,1),mode='crossing')
    assert ('node',2) in hits
    assert ('element',2) in hits


def test_selection_add_toggle_replace():
    a={('node',1),('node',2)}
    b={('node',2),('element',3)}
    assert apply_selection(a,b,additive=True)==a|b
    assert apply_selection(a,b,toggle=True)==a^b
    assert apply_selection(a,b)==b
    assert apply_selection(a,[])==set()


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        select_in_rectangle(model(),(0,0),(1,1),mode='guess')


def test_deterministic_order():
    m=model()
    first=select_in_rectangle(m,(-1,-1),(10,10))
    assert first==select_in_rectangle(m,(-1,-1),(10,10))
    assert first[:5]==tuple(('node',nid) for nid in range(1,6))
    assert first[5:]==tuple(('element',eid) for eid in range(1,5))
