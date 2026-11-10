"""Deterministic, Qt-independent window/crossing selection of 2D structural objects.

A left-to-right drag uses *window* semantics (both element endpoints inside).
A right-to-left drag uses *crossing* semantics (any segment intersection).
Coordinates are in global metres; tolerances are geometric, not screen pixels.
"""
from math import isfinite


def box_from_corners(a, b):
    """Return (xmin, ymin, xmax, ymax) from two finite XY pairs."""
    values = tuple(float(v) for pt in (a, b) for v in pt)
    if len(values) != 4 or not all(isfinite(v) for v in values):
        raise ValueError('选框坐标必须是有限的二维数值')
    x1, y1, x2, y2 = values
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _inside(x, y, box, tol=1e-10):
    return (box[0]-tol <= x <= box[2]+tol and
            box[1]-tol <= y <= box[3]+tol)


def _segment_intersects_box(a, b, box):
    """Liang-Barsky segment clipping, inclusive of borders."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = x1-x0, y1-y0
    p = (-dx, dx, -dy, dy)
    q = (x0-box[0], box[2]-x0, y0-box[1], box[3]-y0)
    lo, hi = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-15:
            if qi < -1e-10:
                return False
        else:
            t = qi/pi
            if pi < 0:
                lo = max(lo, t)
            else:
                hi = min(hi, t)
            if lo > hi+1e-12:
                return False
    return True


def select_in_rectangle(model, start, finish, *, mode='auto'):
    """Return stable tuple of ('node' | 'element', id) hit by a drag rectangle.

    ``auto`` chooses window when finish.x >= start.x and crossing otherwise.
    No mutation is performed and no graphics library is imported.
    """
    if mode not in ('auto', 'window', 'crossing'):
        raise ValueError('选框模式必须为 auto / window / crossing')
    box = box_from_corners(start, finish)
    if mode == 'auto':
        mode = 'window' if float(finish[0]) >= float(start[0]) else 'crossing'
    hits = []
    for nid, node in sorted(model.nodes.items()):
        if _inside(node.x, node.y, box):
            hits.append(('node', nid))
    for eid, element in sorted(model.elements.items()):
        a = model.nodes[element.node_i]
        b = model.nodes[element.node_j]
        pa, pb = (a.x, a.y), (b.x, b.y)
        if (mode == 'window' and _inside(*pa, box) and _inside(*pb, box)) or (
                mode == 'crossing' and _segment_intersects_box(pa, pb, box)):
            hits.append(('element', eid))
    return tuple(hits)


def apply_selection(current, hits, *, additive=False, toggle=False):
    """Pure set operation; Qt caller tracks its own primary selection."""
    current, hits = set(current), set(hits)
    if toggle:
        return current ^ hits
    return current | hits if additive else hits
