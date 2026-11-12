"""Read-only model checks. Warnings are not proofs of instability."""
from dataclasses import dataclass
import math
from .core import DOFManager, UniformLoad2D, LinearLoad2D, PointLoad2D


@dataclass(frozen=True)
class ModelIssue:
    severity: str
    message: str
    nodes: tuple = ()
    elements: tuple = ()


def check_model(model):
    issues=[]
    def add(severity,message,nodes=(),elements=()):
        issues.append(ModelIssue(severity,message,tuple(nodes),tuple(elements)))
    if not model.nodes or not model.elements:
        add('error','尚无可计算的结构：请建立节点和杆件。')
    adjacency={nid:set() for nid in model.nodes}
    positions={}
    topology_valid=True
    for nid,node in model.nodes.items():
        positions.setdefault((node.x,node.y),[]).append(nid)
    for ids in positions.values():
        if len(ids)>1:
            add('warning','节点坐标重合，但编号不同；请确认是否需要连接（不会自动合并）。',ids)
    for eid,element in model.elements.items():
        ids=(element.node_i,element.node_j)
        if any(n not in model.nodes for n in ids):
            add('error',f'杆件 E{eid} 引用了不存在的节点。',
                [n for n in ids if n in model.nodes],[eid])
            topology_valid=False
            continue
        adjacency[ids[0]].add(ids[1]);adjacency[ids[1]].add(ids[0])
        try:
            element.geometry(model)
        except (ValueError,KeyError) as exc:
            add('error',f'杆件 E{eid} 几何无效（零长度或方向不适用）：{exc}',ids,[eid])
        if element.material_id not in model.materials or element.section_id not in model.sections:
            add('error',f'杆件 E{eid} 缺少材料或截面定义。',ids,[eid])
    for nid,neighbors in adjacency.items():
        if not neighbors:
            add('warning',f'节点 {nid} 未连接杆件，请确认是否为多余节点。',[nid])
    visited=set();groups=[]
    for nid,neighbors in adjacency.items():
        if nid in visited or not neighbors:continue
        pending=[nid];component=[];visited.add(nid)
        while pending:
            current=pending.pop();component.append(current)
            for other in adjacency[current]-visited:
                visited.add(other);pending.append(other)
        groups.append(tuple(sorted(component)))
    if len(groups)>1:
        for index,group in enumerate(groups,1):
            add('warning',f'独立结构组 {index}/{len(groups)}：与其他组没有节点连接；独立结构也可能合法。',group)
    for group in groups:
        if not any(n in group for n,d in model.constraints):
            add('warning','此结构组未设置任何约束，请核对支座。',group)
    dm=DOFManager(model) if topology_valid else None
    for label,values in (('节点荷载',model.loads),('给定位移',model.constraints)):
        for (nid,dof),value in values.items():
            try:finite=math.isfinite(float(value))
            except (ValueError,TypeError,OverflowError):finite=False
            if nid not in model.nodes or dof not in ('ux','uy','rz') or not finite:
                add('error',f'{label}引用或数值无效：节点 {nid} / {dof}。',[nid] if nid in model.nodes else [])
            elif dm is not None and value!=0 and ((nid,dof) not in dm.mapping or dm.mapping[(nid,dof)] in dm.inactive):
                add('error',f'{label}作用于无效自由度：节点 {nid} / {dof}。',[nid])
    for index,load in enumerate(model.member_loads,1):
        eid=getattr(load,'element_id',None)
        element=model.elements.get(eid)
        if not isinstance(load,(UniformLoad2D,LinearLoad2D,PointLoad2D)) or element is None:
            add('error',f'第 {index} 项杆件荷载类型无效或引用不存在的杆件。')
            continue
        try:
            element.equivalent_nodal_load(model,load)
        except (ValueError,KeyError,TypeError) as exc:
            add('error',f'杆件 E{eid} 的第 {index} 项荷载无效：{exc}',
                [n for n in (element.node_i,element.node_j) if n in model.nodes],[eid])
    return issues
