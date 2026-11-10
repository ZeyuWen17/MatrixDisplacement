"""Matplotlib diagrams for solved 2D frame models (V0.3).

Imports matplotlib lazily so the numerical solver can still be imported
without initializing a graphical backend. Every routine returns an Axes;
call ax.figure.savefig(...) or plt.show() from the application.
"""
import numpy as np

from .postprocessing import MemberResponse2D, TrussResponse2D, BeamResponse2D
from .core import Frame2D, Beam2D, UniformLoad2D, LinearLoad2D, PointLoad2D


def _response(model, result, element_id):
    element = model.elements[element_id]
    cls = MemberResponse2D if isinstance(element, Frame2D) else (
        BeamResponse2D if isinstance(element, Beam2D) else TrussResponse2D)
    return cls(model, result, element_id)


def _axes(ax=None):
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))
    return ax


def _span(model):
    xy = np.array([[node.x, node.y] for node in model.nodes.values()],dtype=float)
    return max(float(np.ptp(xy[:,0])), float(np.ptp(xy[:,1])), 1.0)


def _base(model, ax, *, show_node_ids=True):
    for e in model.elements.values():
        ni, nj = model.nodes[e.node_i], model.nodes[e.node_j]
        ax.plot([ni.x,nj.x],[ni.y,nj.y],color='0.55',lw=1.5,zorder=1)
    coords = np.array([(n.x,n.y) for n in model.nodes.values()])
    ax.scatter(coords[:,0],coords[:,1],s=18,color='0.25',zorder=5)
    if show_node_ids:
        for n in model.nodes.values():
            ax.annotate(str(n.id), (n.x,n.y),xytext=(4,4),textcoords='offset points',fontsize=8)
    fixed_nodes = {
        nid for nid in model.nodes
        if all((nid,d) in model.constraints for d in ('ux','uy','rz'))
    }
    if fixed_nodes:
        ax.scatter([model.nodes[n].x for n in fixed_nodes],
                   [model.nodes[n].y for n in fixed_nodes],
                   marker='s',facecolors='none',edgecolors='0.2',s=70,zorder=4)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel('Global X (m)')
    ax.set_ylabel('Global Y (m)')
    ax.grid(True,alpha=0.2)
    ax.margins(0.15)
    return ax


def _plot_member_load_arrows(model, ax):
    """Draw arrows for linearly varying, constant, and concentrated forces.

    Arrow lengths are normalized per *load*, not physical load magnitudes;
    use numerical result tables for quantitative force values.
    """
    span = _span(model)
    for load in model.member_loads:
        element = model.elements[load.element_id]
        L, c, s = element.geometry(model)
        ni = model.nodes[element.node_i]
        if isinstance(load, PointLoad2D):
            stations = [(load.position,load.fx,load.fy)]
        elif isinstance(load, UniformLoad2D):
            stations = [(L*t,load.qx,load.qy) for t in np.linspace(0.05,0.95,9)]
        elif isinstance(load, LinearLoad2D):
            stations = [(L*t,(1-t)*load.qx_i+t*load.qx_j,
                         (1-t)*load.qy_i+t*load.qy_j) for t in np.linspace(0.05,0.95,9)]
        else:
            continue
        vectors=[]
        for x,fx,fy in stations:
            qx,qy=element._load_vector_in_local_axes(model,fx,fy,load.system)
            vectors.append((x,c*qx-s*qy,s*qx+c*qy))
        maximum=max((float(np.hypot(vx,vy)) for _,vx,vy in vectors),default=0.)
        if maximum <= 0:
            continue
        for x,vx,vy in vectors:
            mag=float(np.hypot(vx,vy))
            if mag <= maximum*1e-10:
                continue
            px,py=ni.x+c*x,ni.y+s*x
            factor=span*0.15/maximum
            ax.annotate('',xy=(px,py),xytext=(px-vx*factor,py-vy*factor),
                        arrowprops={'arrowstyle':'-|>','color':'tab:red','lw':1.1},zorder=3)


def plot_structure(model, *, ax=None, show_node_ids=True, show_loads=False):
    """Undeformed model sketch; optionally show member force arrows.

    Arrows are direction/relative-load illustrations, not a shared force scale.
    """
    ax = _axes(ax)
    _base(model, ax, show_node_ids=show_node_ids)
    if show_loads:
        _plot_member_load_arrows(model,ax)
    ax.set_title('Undeformed 2D frame' + (' (member loads)' if show_loads else ''))
    return ax


def plot_force_diagram(model, result, component, *, ax=None, points=201,
                       scale=None, show_node_ids=True, interactive=False):
    """Plot axial N, shear V or moment M alongside the member centerlines.

    Positive ordinates point in the local +y direction of each member.
    The supplied scale, if given, is in metres per physical force unit
    (m/N for N,V; m/(N*m) for M). Auto scaling is for display only.
    Discontinuities at point forces are displayed as vertical jumps.
    """
    key = component.upper()
    if key not in ('N','V','M'):
        raise ValueError("component must be 'N', 'V' or 'M'")
    ax = _axes(ax)
    if not model.elements:
        raise ValueError('Model has no elements')
    responses = [(e, _response(model,result,e.id)) for e in model.elements.values()]
    diagrams = [(e,r,r.sample_sections(points=points)) for e,r in responses]
    max_force = max((float(np.max(np.abs(getattr(samples,key)))) for _,_,samples in diagrams),default=0.0)
    if scale is None:
        scale = .18*_span(model)/max_force if max_force else 0.0
    if not np.isfinite(scale) or scale < 0:
        raise ValueError('Diagram scale must be a finite nonnegative number')
    _base(model, ax, show_node_ids=show_node_ids)
    for element, r, samples in diagrams:
        n = model.nodes[element.node_i]
        x = samples.x
        ordinates = getattr(samples,key) * scale
        coords_x = n.x + r.c*x - r.s*ordinates
        coords_y = n.y + r.s*x + r.c*ordinates
        line, = ax.plot(coords_x,coords_y,lw=2,zorder=2)
        if interactive:
            # An artist's sample index maps to _response(...).sample_sections(points).
            # In particular, duplicate x values encode the two sides of a point force.
            line.set_gid(f'md-member:{element.id}:{key}')
            line.set_picker(7)  # points; matches dense force diagrams at any zoom
        # Dimensionless diagram supports any member orientation.
    unit = 'N m' if key == 'M' else 'N'
    ax.set_title(f'{key} diagram (local sign convention; {unit})')
    ax.text(.01,.01,'Diagram ordinates auto-scaled' if max_force and scale else 'Zero diagram',
            transform=ax.transAxes,fontsize=8,alpha=.7,va='bottom')
    ax.relim(); ax.autoscale_view()
    return ax


def plot_deformed_shape(model, result, *, ax=None, points=201,
                        scale=None, show_node_ids=True):
    """Plot true within-member Euler--Bernoulli deformation, amplified for display.

    The field includes the effect of distributed / concentrated member forces.
    scale=1 draws actual displacements in metres. Auto scale magnifies the
    maximum translational displacement to about 18% of the model span.
    """
    ax = _axes(ax)
    if not model.elements:
        raise ValueError('Model has no elements')
    fields = [(e, _response(model,result,e.id)) for e in model.elements.values()]
    fields = [(e,r,r.sample_deformation(points=points)) for e,r in fields]
    max_u = max((float(np.max(np.hypot(s.ux_global,s.uy_global))) for _,_,s in fields),default=0.0)
    if scale is None:
        scale = .18*_span(model)/max_u if max_u else 1.0
    if not np.isfinite(scale) or scale < 0:
        raise ValueError('Deformation magnification must be a finite nonnegative number')
    _base(model, ax, show_node_ids=show_node_ids)
    for e, r, samples in fields:
        n = model.nodes[e.node_i]
        x = n.x + r.c*samples.x + scale*samples.ux_global
        y = n.y + r.s*samples.x + scale*samples.uy_global
        ax.plot(x,y,lw=2,zorder=3)
    ax.set_title(f'Deformed shape (magnification ×{scale:.3g})')
    ax.relim(); ax.autoscale_view()
    return ax


def plot_member_section_diagram(model, result, element_id, component, *, ax=None, points=201):
    """Plot a single member's unscaled N(x), V(x) or M(x) against local x."""
    key=component.upper()
    if key not in ('N','V','M'):
        raise ValueError("component must be 'N', 'V' or 'M'")
    ax = _axes(ax)
    samples = _response(model,result,element_id).sample_sections(points)
    ax.plot(samples.x,getattr(samples,key),lw=2)
    ax.axhline(0,color='0.5',lw=1)
    ax.set_xlabel('Local x (m)')
    ax.set_ylabel(f'{key} ({"N m" if key == "M" else "N"})')
    ax.set_title(f'Element {element_id}: {key}(x)')
    ax.grid(True,alpha=.2)
    return ax
