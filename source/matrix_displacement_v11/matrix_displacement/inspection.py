"""Query exact solved node DOFs and member section responses without Qt.

Member N/V/M conventions follow postprocessing.py. At a concentrated force,
section(..., side='left'/'right') provides the corresponding one-sided limit.
"""
from dataclasses import dataclass

from .postprocessing import MemberResponse2D, TrussResponse2D
from .core import Truss2D


@dataclass(frozen=True)
class NodeInspection:
    node_id: int
    entries: tuple  # (dof, displacement, reaction, prescribed)


@dataclass(frozen=True)
class MemberInspection:
    element_id: int
    element_type: str
    length: float
    x: float
    side: str
    N: float
    V: float
    M: float
    displacement_global_x: float
    displacement_global_y: float
    rotation: float
    ranges: dict  # sampled extrema: force -> (min, max)


def inspect_node(model, result, node_id):
    if node_id not in model.nodes:
        raise KeyError(f'Unknown node {node_id}')
    entries = []
    for (nid, dof), idx in sorted(result.dof_manager.mapping.items(), key=lambda p: p[1]):
        if nid == node_id and idx not in result.dof_manager.inactive:
            entries.append((dof, float(result.displacements[idx]),
                            float(result.reactions[idx]),
                            (nid, dof) in model.constraints))
    return NodeInspection(node_id, tuple(entries))


def inspect_member(model, result, element_id, x=None, *, side='right', points=201):
    if element_id not in model.elements:
        raise KeyError(f'Unknown element {element_id}')
    element = model.elements[element_id]
    response = (TrussResponse2D if isinstance(element, Truss2D) else MemberResponse2D)(
        model, result, element_id)
    L = response.L
    if x is None:
        x = L / 2
    section = response.section(x, side=side)
    deformation = response.deformation(x)
    samples = response.sample_sections(points=points)
    ranges = {
        key: (float(getattr(samples,key).min()), float(getattr(samples,key).max()))
        for key in ('N','V','M')
    }
    return MemberInspection(element_id, type(element).__name__, L, float(x), side,
                            section.N, section.V, section.M,
                            deformation.ux_global, deformation.uy_global,
                            deformation.rz, ranges)
