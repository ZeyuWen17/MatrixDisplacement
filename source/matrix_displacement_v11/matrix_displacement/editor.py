"""Qt-independent model editing services for the V0.7 desktop interface.

All GUI actions go through this layer.  The core solver is deliberately
untouched, and users can exercise this API without installing a GUI toolkit.
Units: m, N, Pa, m^2, m^4, rad.
"""
from dataclasses import replace
from pathlib import Path
from math import isfinite

from .core import (
    Node, Material, Section, Frame2D, Truss2D, Beam2D, StructuralModel,
    DOFManager, Mode, LinearStaticSolver, UniformLoad2D, LinearLoad2D,
    PointLoad2D,
)
from .io import save_model_json, load_model_json

ELEMENT_TYPES = {'Frame2D': Frame2D, 'Truss2D': Truss2D, 'Beam2D': Beam2D}
DOFS = ('ux', 'uy', 'rz')


def _real(value, name):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} 必须是有限数值') from exc
    if not isfinite(value):
        raise ValueError(f'{name} 必须是有限数值')
    return value


def _next_id(items):
    return max(items, default=0) + 1


class ModelEditor:
    """Mutable model editor with simple validated CRUD and example builders."""

    def __init__(self, model=None):
        self.model = model if model is not None else StructuralModel()
        self.default_E = 210e9
        self.default_A = 0.01
        self.default_I = 8e-6

    @property
    def next_node_id(self):
        return _next_id(self.model.nodes)

    @property
    def next_element_id(self):
        return _next_id(self.model.elements)

    def set_defaults(self, E, A, I):
        # Constructor validation is the same validation used by the core.
        material = Material(-1, E)
        section = Section(-1, A, I)
        self.default_E, self.default_A, self.default_I = material.E, section.A, section.I

    def add_node(self, x, y):
        x, y = _real(x, 'x'), _real(y, 'y')
        if any(abs(node.x-x) < 1e-9 and abs(node.y-y) < 1e-9
               for node in self.model.nodes.values()):
            raise ValueError('相同坐标已经存在节点；请选中已有节点。')
        node = Node(self.next_node_id, x, y)
        self.model.add_node(node)
        return node.id

    def move_node(self, node_id, x, y):
        if node_id not in self.model.nodes:
            raise ValueError('节点不存在')
        x, y = _real(x, 'x'), _real(y, 'y')
        if any(nid != node_id and abs(n.x-x) < 1e-9 and abs(n.y-y) < 1e-9
               for nid, n in self.model.nodes.items()):
            raise ValueError('目标位置已经存在节点')
        old = self.model.nodes[node_id]
        self.model.nodes[node_id] = replace(old, x=x, y=y)
        try:
            # A move must keep every adjacent element geometrically valid,
            # including Beam2D's left-to-right horizontal requirement.
            for element in self.model.elements.values():
                if node_id in (element.node_i, element.node_j):
                    element.geometry(self.model)
            for load in self.model.member_loads:
                element = self.model.elements[load.element_id]
                if node_id in (element.node_i, element.node_j):
                    element.equivalent_nodal_load(self.model, load)
        except Exception:
            self.model.nodes[node_id] = old
            raise

    def _material_and_section(self, E=None, A=None, I=None):
        mat_id, sec_id = _next_id(self.model.materials), _next_id(self.model.sections)
        mat = Material(mat_id, self.default_E if E is None else E)
        sec = Section(sec_id, self.default_A if A is None else A,
                      self.default_I if I is None else I)
        return mat, sec

    def add_element(self, node_i, node_j, element_type='Frame2D', *,
                    E=None, A=None, I=None, release_i=False, release_j=False):
        if element_type not in ELEMENT_TYPES:
            raise ValueError(f'不支持的单元类型：{element_type}')
        if node_i not in self.model.nodes or node_j not in self.model.nodes:
            raise ValueError('杆件端点必须是已有节点')
        if node_i == node_j:
            raise ValueError('杆件不能连接同一个节点')
        if element_type != 'Frame2D' and (release_i or release_j):
            raise ValueError('只有 Frame2D 支持杆端转角释放')
        if element_type == 'Beam2D':
            a, b = self.model.nodes[node_i], self.model.nodes[node_j]
            if b.x < a.x and a.y == b.y:
                node_i, node_j = node_j, node_i
        mat, sec = self._material_and_section(E, A, I)
        kwargs = {'release_i': bool(release_i), 'release_j': bool(release_j)} if element_type == 'Frame2D' else {}
        element = ELEMENT_TYPES[element_type](self.next_element_id, node_i, node_j, mat.id, sec.id, **kwargs)
        # Prevalidate before changing data; geometry only needs node data.
        element.geometry(self.model)
        self.model.add_material(mat)
        self.model.add_section(sec)
        self.model.add_element(element)
        self._prune_incompatible_dofs()
        return element.id

    def set_element_properties(self, element_id, E, A, I, *, release_i=None, release_j=None):
        """Copy-on-write section/material prevents edits to other elements."""
        old = self.model.elements[element_id]
        mat, sec = self._material_and_section(E, A, I)
        if isinstance(old, Frame2D):
            ri = old.release_i if release_i is None else bool(release_i)
            rj = old.release_j if release_j is None else bool(release_j)
            changed = replace(old, material_id=mat.id, section_id=sec.id, release_i=ri, release_j=rj)
        else:
            if release_i or release_j:
                raise ValueError('当前单元不能设置杆端转角释放')
            changed = replace(old, material_id=mat.id, section_id=sec.id)
        # Revalidate existing member loads with replacement properties.
        # Geometry is unchanged, so relevant load consistency is preserved.
        changed.geometry(self.model)
        self.model.add_material(mat)
        self.model.add_section(sec)
        self.model.elements[element_id] = changed
        self._prune_incompatible_dofs()

    def active_dofs(self, node_id):
        if node_id not in self.model.nodes:
            raise ValueError('节点不存在')
        if not self.model.elements:
            return set(DOFS)
        dm = DOFManager(self.model)
        return {d for d in DOFS if (node_id,d) in dm.mapping
                and dm.mapping[(node_id,d)] not in dm.inactive}

    def set_support(self, node_id, prescribed):
        """Set (replace) node supports; map contains dof -> known displacement."""
        if node_id not in self.model.nodes:
            raise ValueError('节点不存在')
        available = self.active_dofs(node_id)
        new_values = {}
        for dof, value in prescribed.items():
            if dof not in available:
                raise ValueError(f'节点 {node_id} 不具有有效 {dof} 自由度')
            new_values[(node_id,dof)] = _real(value, '给定位移')
        self.model.constraints = {
            **{key: value for key,value in self.model.constraints.items() if key[0] != node_id},
            **new_values,
        }

    def set_nodal_load(self, node_id, *, ux=0.0, uy=0.0, rz=0.0):
        """Replace, rather than accidentally accumulate, GUI values."""
        available = self.active_dofs(node_id)
        new_values = {}
        for dof, value in (('ux',ux),('uy',uy),('rz',rz)):
            value = _real(value, '节点荷载')
            if dof not in available and value != 0:
                raise ValueError(f'节点 {node_id} 不具有有效 {dof} 自由度')
            if value != 0:
                new_values[(node_id,dof)] = value
        self.model.loads = {
            **{key: value for key,value in self.model.loads.items() if key[0] != node_id},
            **new_values,
        }

    def add_member_load(self, element_id, kind, *, system='local', **values):
        if element_id not in self.model.elements:
            raise ValueError('杆件不存在')
        if isinstance(self.model.elements[element_id], Truss2D):
            raise ValueError('桁架杆件只支持节点荷载；请先细分杆件。')
        if kind == 'uniform':
            load = UniformLoad2D(element_id, system=system, **values)
        elif kind == 'linear':
            load = LinearLoad2D(element_id, system=system, **values)
        elif kind == 'point':
            load = PointLoad2D(element_id, system=system, **values)
        else:
            raise ValueError('不支持的杆件荷载类型')
        self.model.add_member_load(load)
        return load

    def replace_member_load(self, index, kind, *, system='local', **values):
        """Replace one load by its zero-based global list index, without touching others."""
        if type(index) is not int or not 0 <= index < len(self.model.member_loads):
            raise ValueError('荷载序号不存在')
        eid = self.model.member_loads[index].element_id
        if kind == 'uniform':
            new_load = UniformLoad2D(eid, system=system, **values)
        elif kind == 'linear':
            new_load = LinearLoad2D(eid, system=system, **values)
        elif kind == 'point':
            new_load = PointLoad2D(eid, system=system, **values)
        else:
            raise ValueError('不支持的杆件荷载类型')
        self.model.elements[eid].equivalent_nodal_load(self.model, new_load)
        self.model.member_loads[index] = new_load
        return new_load

    def delete_member_load(self, index):
        """Delete one indexed member load, preserving all other loads."""
        if type(index) is not int or not 0 <= index < len(self.model.member_loads):
            raise ValueError('荷载序号不存在')
        return self.model.member_loads.pop(index)

    def clear_member_loads(self, element_id):
        if element_id not in self.model.elements:
            raise ValueError('杆件不存在')
        self.model.member_loads = [load for load in self.model.member_loads if load.element_id != element_id]

    def remove_element(self, element_id):
        if element_id not in self.model.elements:
            raise ValueError('杆件不存在')
        del self.model.elements[element_id]
        self.model.member_loads = [load for load in self.model.member_loads if load.element_id != element_id]
        self._prune_incompatible_dofs()

    def remove_node(self, node_id):
        if node_id not in self.model.nodes:
            raise ValueError('节点不存在')
        for eid in [eid for eid,e in self.model.elements.items() if node_id in (e.node_i,e.node_j)]:
            del self.model.elements[eid]
        self.model.member_loads = [load for load in self.model.member_loads if load.element_id in self.model.elements]
        del self.model.nodes[node_id]
        self.model.constraints = {k:v for k,v in self.model.constraints.items() if k[0] != node_id}
        self.model.loads = {k:v for k,v in self.model.loads.items() if k[0] != node_id}
        self._prune_incompatible_dofs()

    def move_nodes(self, positions):
        """Move several nodes simultaneously; validate final geometry atomically.

        ``positions`` maps node_id -> (x, y). Valid coordinate swaps are allowed.
        The caller should wrap the whole operation in EditHistory.execute().
        """
        positions = dict(positions)
        if not positions:
            return
        unknown = set(positions) - set(self.model.nodes)
        if unknown:
            raise ValueError(f'待移动节点不存在：{sorted(unknown)}')
        new_nodes = dict(self.model.nodes)
        for nid, xy in positions.items():
            if len(xy) != 2:
                raise ValueError('节点新坐标必须为 (x, y)')
            x, y = _real(xy[0], 'x'), _real(xy[1], 'y')
            new_nodes[nid] = replace(new_nodes[nid], x=x, y=y)
        coordinates = [(node.x, node.y) for node in new_nodes.values()]
        for i, (x, y) in enumerate(coordinates):
            for xx, yy in coordinates[i+1:]:
                if abs(x-xx) < 1e-9 and abs(y-yy) < 1e-9:
                    raise ValueError('移动后存在重合节点')
        old_nodes = self.model.nodes
        self.model.nodes = new_nodes
        try:
            affected = {e.id for e in self.model.elements.values()
                        if e.node_i in positions or e.node_j in positions}
            for eid in affected:
                self.model.elements[eid].geometry(self.model)
            for load in self.model.member_loads:
                if load.element_id in affected:
                    self.model.elements[load.element_id].equivalent_nodal_load(self.model, load)
        except Exception:
            self.model.nodes = old_nodes
            raise

    def translate_nodes(self, node_ids, dx, dy):
        """Shift selected nodes; structural changes are committed once by history."""
        ids = tuple(dict.fromkeys(node_ids))
        dx, dy = _real(dx, 'Δx'), _real(dy, 'Δy')
        if any(nid not in self.model.nodes for nid in ids):
            raise ValueError('待移动节点不存在')
        self.move_nodes({nid: (self.model.nodes[nid].x+dx,
                                self.model.nodes[nid].y+dy) for nid in ids})

    def set_elements_properties(self, element_ids, E, A, I):
        """Apply a common E/A/I to several elements, preserving end releases."""
        ids = tuple(dict.fromkeys(element_ids))
        if any(eid not in self.model.elements for eid in ids):
            raise ValueError('待修改杆件不存在')
        # Validate all scalar inputs before any modification.
        Material(-1, E)
        Section(-1, A, I)
        for eid in ids:
            self.set_element_properties(eid, E, A, I)

    def remove_many(self, *, node_ids=(), element_ids=()):
        """Delete selected nodes/elements as one operation; nodes cascade to members.

        Validate *all* ids first, avoiding partial deletion on invalid inputs.
        """
        node_ids, element_ids = set(node_ids), set(element_ids)
        if node_ids - self.model.nodes.keys():
            raise ValueError('待删除节点不存在')
        if element_ids - self.model.elements.keys():
            raise ValueError('待删除杆件不存在')
        element_ids |= {eid for eid, element in self.model.elements.items()
                        if element.node_i in node_ids or element.node_j in node_ids}
        for eid in element_ids:
            del self.model.elements[eid]
        self.model.member_loads = [load for load in self.model.member_loads
                                   if load.element_id not in element_ids]
        for nid in node_ids:
            del self.model.nodes[nid]
        self.model.constraints = {k: v for k, v in self.model.constraints.items()
                                  if k[0] not in node_ids}
        self.model.loads = {k: v for k, v in self.model.loads.items()
                            if k[0] not in node_ids}
        self._prune_incompatible_dofs()

    def _prune_incompatible_dofs(self):
        if not self.model.elements:
            return
        dm = DOFManager(self.model)
        allowed = {key for key,idx in dm.mapping.items() if idx not in dm.inactive}
        self.model.constraints = {k:v for k,v in self.model.constraints.items() if k in allowed}
        self.model.loads = {k:v for k,v in self.model.loads.items() if k in allowed}

    def solve(self, mode=Mode.FAST):
        return LinearStaticSolver(Mode(mode)).solve(self.model)

    def save(self, path):
        return save_model_json(self.model, path)

    def open(self, path):
        # No partial load on malformed JSON.
        new_model = load_model_json(path)
        self.model = new_model
        if self.model.elements:
            last = next(iter(self.model.elements.values()))
            self.default_E = self.model.materials[last.material_id].E
            self.default_A = self.model.sections[last.section_id].A
            self.default_I = self.model.sections[last.section_id].I
        return self.model

    def reset(self):
        self.model = StructuralModel()

    def load_example(self, name):
        if name == 'cantilever':
            new = _cantilever()
        elif name == 'continuous_beam':
            new = _continuous_beam()
        elif name == 'truss':
            new = _truss()
        else:
            raise ValueError(f'未知算例：{name}')
        self.model = new
        first = next(iter(new.elements.values()))
        self.default_E = new.materials[first.material_id].E
        self.default_A = new.sections[first.section_id].A
        self.default_I = new.sections[first.section_id].I
        return new


def _cantilever():
    ed = ModelEditor()
    a, b = ed.add_node(0,0), ed.add_node(4,0)
    ed.add_element(a,b,'Frame2D')
    ed.set_support(a,{'ux':0,'uy':0,'rz':0})
    ed.add_member_load(1,'uniform',qy=-1200)
    ed.add_member_load(1,'point',position=1.7,fy=-700)
    return ed.model


def _continuous_beam():
    ed = ModelEditor()
    n = [ed.add_node(x,0) for x in (0,4,8)]
    ed.add_element(n[0],n[1],'Beam2D')
    ed.add_element(n[1],n[2],'Beam2D')
    for nid in n:
        ed.set_support(nid,{'uy':0})
    for eid in (1,2):
        ed.add_member_load(eid,'uniform',qy=-1000)
    return ed.model


def _truss():
    ed = ModelEditor()
    a, b, c = ed.add_node(0,0), ed.add_node(4,0), ed.add_node(2,3)
    for i,j in ((a,b),(a,c),(b,c)):
        ed.add_element(i,j,'Truss2D')
    ed.set_support(a,{'ux':0,'uy':0})
    ed.set_support(b,{'uy':0})
    ed.set_nodal_load(c,uy=-3000)
    return ed.model
