import pytest
from matrix_displacement.label_layout import LabelRequest, place_labels, rectangles_overlap


def rect(pos, size):
    return pos[0], pos[1], pos[0]+size[0], pos[1]+size[1]


def test_identical_anchors_do_not_overlap_when_space_available():
    req=[LabelRequest(20,20,70,16,0,-20) for _ in range(4)]
    result=place_labels(req)
    assert len(result)==4
    boxes=[rect(p,(70,16)) for p in result]
    for i,a in enumerate(boxes):
        for b in boxes[i+1:]:
            assert not rectangles_overlap(a,b,gap=3)


def test_avoids_structural_node_obstacle():
    req=[LabelRequest(0,0,18,14,0,0)]
    obstacles=[(-10,-10,10,10)]
    pos=place_labels(req,obstacles)
    assert not rectangles_overlap(rect(pos[0],(18,14)),obstacles[0],gap=3)


def test_no_collision_keeps_preferred_offset():
    r=LabelRequest(40,60,20,10,5,-15)
    assert place_labels([r])==((45,45),)


def test_deterministic_output():
    inputs=[LabelRequest(0,0,40,14) for _ in range(6)]
    assert place_labels(inputs)==place_labels(inputs)


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_invalid_label_sizes_rejected(bad):
    with pytest.raises(ValueError):place_labels([LabelRequest(0,0,bad,12)])
    with pytest.raises(ValueError):place_labels([LabelRequest(0,0,12,0)])


def test_invalid_obstacle_rejected():
    with pytest.raises(ValueError):place_labels([],[(3,4,1,5)])


def test_empty_layout():
    assert place_labels([])==()
