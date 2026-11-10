"""Qt-free geometry and diagram picking helpers for V0.9.

All geometry uses the structural model's global coordinates in metres.
Stations are measured from the member's *i* end; a force diagram jump has
left- and right-hand values at the exact same station.
"""
from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite

from .inspection import inspect_member
from .postprocessing import MemberResponse2D, TrussResponse2D
from .core import Truss2D


@dataclass(frozen=True)
class DimensionInfo:
    element_id: int
    length: float
    angle_deg: float
    start: tuple[float, float]
    end: tuple[float, float]
    offset_start: tuple[float, float]
    offset_end: tuple[float, float]
    label_position: tuple[float, float]
    label: str


@dataclass(frozen=True)
class ProjectedStation:
    element_id: int
    station: float
    distance: float
    projected: tuple[float, float]


@dataclass(frozen=True)
class DiagramPick:
    element_id: int
    component: str
    sample_index: int
    section: object  # MemberInspection


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite number') from exc
    if not isfinite(result):
        raise ValueError(f'{name} must be a finite number')
    return result


def dimension_info(model, element_id, offset=0.3):
    """Dimension line and label for an arbitrary-oriented straight member."""
    if element_id not in model.elements:
        raise KeyError(f'Unknown element {element_id}')
    offset = _finite(offset, 'offset')
    if offset < 0:
        raise ValueError('offset must be nonnegative')
    element = model.elements[element_id]
    ni, nj = model.nodes[element.node_i], model.nodes[element.node_j]
    length = hypot(nj.x-ni.x, nj.y-ni.y)
    if length <= 0 or not isfinite(length):
        raise ValueError('Invalid member length')
    dx = (nj.x-ni.x)/length
    dy = (nj.y-ni.y)/length
    # Global +90-degree normal. Annotation is outside the member for any angle.
    nx, ny = -dy, dx
    a = (ni.x+offset*nx, ni.y+offset*ny)
    b = (nj.x+offset*nx, nj.y+offset*ny)
    mid = ((a[0]+b[0])/2, (a[1]+b[1])/2)
    angle = degrees(atan2(dy, dx))
    return DimensionInfo(element_id, length, angle,
                         (ni.x,ni.y), (nj.x,nj.y), a, b, mid,
                         f'L={length:.5g} m  θ={angle:.1f}°')


def project_to_member(model, element_id, x, y):
    """Clamp an arbitrary world point onto the undeformed member centreline."""
    x, y = _finite(x, 'x'), _finite(y, 'y')
    info = dimension_info(model, element_id, 0)
    dx = (info.end[0]-info.start[0])/info.length
    dy = (info.end[1]-info.start[1])/info.length
    station = min(info.length, max(0.0, (x-info.start[0])*dx + (y-info.start[1])*dy))
    px, py = info.start[0]+station*dx, info.start[1]+station*dy
    return ProjectedStation(element_id, station, hypot(x-px,y-py), (px,py))


def _samples(model, result, element_id, points):
    if element_id not in model.elements:
        raise KeyError(f'Unknown element {element_id}')
    element = model.elements[element_id]
    cls = TrussResponse2D if isinstance(element, Truss2D) else MemberResponse2D
    return cls(model, result, element_id).sample_sections(points=points)


def diagram_pick(model, result, element_id, component, index, *, points=201):
    """Exact section query for a plotted sample including point-force sides.

    In a sample with duplicate x at a point load, the *first* duplicate
    represents the left limit and the second represents the right limit.
    A single terminal x=L represents the left interior limit.
    """
    component = str(component).upper()
    if component not in ('N', 'V', 'M'):
        raise ValueError("component must be N, V or M")
    if not isinstance(index,int) or isinstance(index,bool):
        raise TypeError('sample index must be an integer')
    samples = _samples(model, result, element_id, points)
    if index < 0 or index >= len(samples.x):
        raise IndexError('diagram sample index out of range')
    x = float(samples.x[index])
    tol = 1e-12 * max(1., float(samples.x[-1]))
    if index+1 < len(samples.x) and abs(float(samples.x[index+1])-x)<=tol:
        side = 'left'
    elif index == len(samples.x)-1:
        side = 'left'
    else:
        side = 'right'
    return DiagramPick(element_id,component,index,
                       inspect_member(model,result,element_id,x,side=side,points=points))
