"""Shared support symbols in local screen coordinates (x right, y down)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SupportSymbol:
    name: str
    detail: str
    lines: tuple
    polygons: tuple
    circles: tuple
    prescribed: bool


def support_symbol(model, node_id):
    values={d:model.constraints[(node_id,d)] for d in ('ux','uy','rz')
            if (node_id,d) in model.constraints}
    if not values:
        return None
    fixed=set(values)
    active=set()
    for element in model.elements.values():
        half=len(element.local_dofs)//2
        if element.node_i==node_id:active.update(element.local_dofs[:half])
        if element.node_j==node_id:active.update(element.local_dofs[half:])
    beam_fixed=active=={'uy','rz'} and fixed=={'uy','rz'}
    names={frozenset({'ux','uy','rz'}):'固定支座',frozenset({'ux','uy'}):'铰支座',
           frozenset({'uy'}):'竖向约束 · 水平可动',frozenset({'ux'}):'水平约束 · 竖向可动',
           frozenset({'rz'}):'仅转角约束',frozenset({'uy','rz'}):'竖向与转角约束 · 水平可动',
           frozenset({'ux','rz'}):'水平与转角约束 · 竖向可动'}
    name='梁固定支座' if beam_fixed else names[frozenset(fixed)]
    lines=[];polygons=[];circles=[]
    if fixed=={'ux','uy','rz'} or beam_fixed:
        lines.append((-7,-16,-7,16))
        lines.extend((-7,y,-15,y+6) for y in range(-16,15,6))
    elif fixed=={'ux','uy'}:
        polygons.append(((0,4),(-11,18),(11,18)))
        lines.append((-15,21,15,21))
        lines.extend((x,21,x-4,26) for x in range(-10,16,6))
    else:
        if 'ux' in fixed or 'uy' in fixed:
            # Roller triangle on the constrained side. Its base is perpendicular
            # to the blocked translation; rolling is parallel to the base.
            rotate='ux' in fixed
            def point(x,y):return (y,-x) if rotate else (x,y)
            polygons.append(tuple(point(x,y) for x,y in ((0,4),(-11,17),(11,17))))
            circles.extend((*point(x,21),3) for x in (-6,6))
            a,b=point(-15,26),point(15,26)
            lines.append((*a,*b))
        if 'rz' in fixed:
            # A distinct square lock marker, attached above the node.
            lines.append((0,-4,0,-10))
            polygons.append(((-6,-10),(6,-10),(6,-22),(-6,-22)))
            lines.extend(((-4,-12,4,-20),(-4,-20,4,-12)))
    detail=' / '.join(f'{d}={v:.4g} '+('rad' if d=='rz' else 'm') for d,v in values.items())
    return SupportSymbol(name,detail,tuple(lines),tuple(polygons),tuple(circles),any(v!=0 for v in values.values()))
