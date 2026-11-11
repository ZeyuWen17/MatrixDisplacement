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


def _install_force_label_layout(ax, labels):
    """Place text before annotations draw, including resize and savefig renderers."""
    from matplotlib.artist import Artist
    from matplotlib.text import Text
    from .label_layout import LabelRequest, place_labels

    class ForceLabelLayout(Artist):
        _layout_key = None
        _placements = None

        def draw(self, renderer):
            requests=[]
            factor=renderer.points_to_pixels(1)
            for label in labels:
                label.set_position((8, 18))
                label.set_ha('left')
                label.update_positions(renderer)
                box=Text.get_window_extent(label, renderer)
                anchor=ax.transData.transform(label.xy)
                requests.append(LabelRequest(anchor[0],anchor[1],box.width,box.height,
                                             box.x0-anchor[0],box.y0-anchor[1]))
            obstacles=[]
            for text in ax.texts:
                if text not in labels:
                    box=text.get_window_extent(renderer)
                    obstacles.append((box.x0,box.y0,box.x1,box.y1))
            # Reuse only an identical display-space layout. DPI, transforms,
            # text extents and obstacles all participate in invalidation.
            key=(factor, tuple((r.anchor_x,r.anchor_y,r.width,r.height,r.preferred_x,r.preferred_y)
                               for r in requests), tuple(obstacles))
            if key != self._layout_key:
                self._placements=place_labels(requests,obstacles)
                self._layout_key=key
            for label,req,(x,y) in zip(labels,requests,self._placements):
                # Requests use text bounds; retain baseline offset in points.
                label.set_position((8+(x-req.anchor_x-req.preferred_x)/factor,
                                    18+(y-req.anchor_y-req.preferred_y)/factor))
            self.stale=False

    layout=ForceLabelLayout()
    layout.set_zorder(2.5)
    ax.add_artist(layout)


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
    from .supports import support_symbol
    from matplotlib.offsetbox import AnnotationBbox, DrawingArea
    from matplotlib.lines import Line2D
    from matplotlib.patches import Polygon, Circle
    for nid,node in model.nodes.items():
        support=support_symbol(model,nid)
        if support is None:continue
        area=DrawingArea(64,64)
        color='#b45309' if support.prescribed else '#334155'
        def point(x,y):return (x+24,32-y)
        for x1,y1,x2,y2 in support.lines:
            a,b=point(x1,y1),point(x2,y2)
            area.add_artist(Line2D([a[0],b[0]],[a[1],b[1]],color=color,lw=1.2))
        for points in support.polygons:
            area.add_artist(Polygon([point(x,y) for x,y in points],edgecolor=color,facecolor='none' if len(points)==4 else 'white',lw=1.2))
        for x,y,r in support.circles:
            area.add_artist(Circle(point(x,y),r,edgecolor=color,facecolor='white',lw=1.2))
        artist=AnnotationBbox(area,(node.x,node.y),frameon=False,box_alignment=(24/64,32/64),pad=0)
        artist.set_gid(f'support:{nid}')
        artist.set_zorder(4)
        ax.add_artist(artist)
        if support.prescribed:
            ax.annotate(support.detail,(node.x,node.y),xytext=(12,-36),
                        textcoords='offset points',fontsize=7,color=color)
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
                       scale=None, show_node_ids=True, interactive=False,
                       show_values=True, value_mode='all'):
    """Plot axial N, shear V or moment M alongside the member centerlines.

    Positive ordinates point in the local +y direction of each member.
    The supplied scale, if given, is in metres per physical force unit
    (m/N for N,V; m/(N*m) for M). Auto scaling is for display only.
    Discontinuities at point forces are displayed as vertical jumps.
    Labels show member ends and sampled extrema, not analytical extrema.
    """
    key = component.upper()
    if value_mode not in ('none', 'extrema', 'all'):
        raise ValueError('value_mode must be none, extrema or all')
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
    unit = 'N·m' if key == 'M' else 'N'
    label_count = 0
    force_labels = []
    for element, r, samples in diagrams:
        n = model.nodes[element.node_i]
        x = samples.x
        ordinates = getattr(samples,key) * scale
        coords_x = n.x + r.c*x - r.s*ordinates
        coords_y = n.y + r.s*x + r.c*ordinates
        line, = ax.plot(coords_x,coords_y,lw=2,zorder=2)
        if show_values and value_mode != 'none':
            values = getattr(samples,key)
            indices = {int(np.argmin(values)), int(np.argmax(values))}
            if value_mode == 'all':
                indices.update((0, len(x)-1))
            indices = sorted(indices)
            for order, idx in enumerate(indices):
                value = float(values[idx])
                # Hide round-off at free ends, while preserving genuinely small loads.
                if abs(value) < max_force*1e-10:
                    value = 0.0
                label = ax.annotate(f'E{element.id}  x={x[idx]:.3g} m\n{key}={value:.5g} {unit}',
                            (coords_x[idx],coords_y[idx]),
                            xytext=((8 if label_count%4<2 else -8), (18 if label_count%2==0 else -36)),
                            ha=('left' if label_count%4<2 else 'right'),
                            arrowprops=dict(arrowstyle='-',color=line.get_color(),alpha=.5,lw=.6),
                            textcoords='offset points', fontsize=8, color=line.get_color(),
                            bbox=dict(facecolor='white',edgecolor='none',alpha=.8),
                            annotation_clip=False)
                force_labels.append(label)
                label_count += 1
        if interactive:
            # An artist's sample index maps to _response(...).sample_sections(points).
            # In particular, duplicate x values encode the two sides of a point force.
            line.set_gid(f'md-member:{element.id}:{key}')
            line.set_picker(7)  # points; matches dense force diagrams at any zoom
        # Dimensionless diagram supports any member orientation.
    from matplotlib import font_manager
    available = {font.name for font in font_manager.fontManager.ttflist}
    chinese_font = next((name for name in ('Microsoft YaHei','SimHei','Noto Sans CJK SC')
                         if name in available), None)
    font = {'fontfamily': chinese_font} if chinese_font else {}
    title = (f'{dict(N="轴力", V="剪力", M="弯矩")[key]} {key}（局部正号；{unit}）'
             if chinese_font else f'{key} diagram (local sign convention; {unit})')
    ax.set_title(title, **font)
    mode_name = {'none':'隐藏数值','extrema':'每根杆件的采样最大/最小值','all':'端点与采样极值'}[value_mode if show_values else 'none']
    note = (f'几何坐标单位 m；内力按比例绘制，精确数值见截面查询\n{mode_name}；比例 {scale:.3g} m/({unit})'
            if chinese_font else
            f'Geometry axes: m; force values: labels (ends + sampled extrema)\nDisplay scale: {scale:.3g} m/({unit})')
    ax.text(.01,.01,note, transform=ax.transAxes,fontsize=8,alpha=.8,va='bottom', **font)
    ax.relim(); ax.autoscale_view()
    if force_labels:
        _install_force_label_layout(ax, force_labels)
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
