"""Versioned, JSON-only persistence for the educational structural model.

No Python code evaluation, pickle, or implicit object deserialization is used.
The schema is intentionally explicit to make saved models auditable.
"""
import json
import os
import tempfile
from pathlib import Path

from .core import (
    Node, Material, Section, Frame2D, Truss2D, Beam2D,
    UniformLoad2D, PointLoad2D, LinearLoad2D, StructuralModel,
)

SCHEMA_VERSION = 2
ELEMENT_TYPES = {'Frame2D': Frame2D, 'Truss2D': Truss2D, 'Beam2D': Beam2D}
LOAD_TYPES = {'UniformLoad2D': UniformLoad2D, 'PointLoad2D': PointLoad2D, 'LinearLoad2D': LinearLoad2D}
TOP_KEYS = {'schema_version', 'units', 'nodes', 'materials', 'sections',
            'elements', 'constraints', 'nodal_loads', 'member_loads'}


def _keys(record, expected, label):
    if not isinstance(record, dict) or set(record) != set(expected):
        raise ValueError(f'{label} must have exactly these keys: {sorted(expected)}')


def _entries(data, key):
    entries = data[key]
    if not isinstance(entries, list):
        raise ValueError(f'{key} must be a JSON array')
    return entries


def _integer_id(value, label):
    if type(value) is not int:
        raise ValueError(f'{label} must be a JSON integer (not boolean or string)')
    return value


def _number(value, label):
    if type(value) not in (int, float):
        raise ValueError(f'{label} must be a finite JSON number')
    from .core import _finite_float
    return _finite_float(value, label)


def model_to_dict(model):
    """Return a portable, explicit JSON-compatible dictionary."""
    if not isinstance(model, StructuralModel):
        raise TypeError('Expected StructuralModel')
    elements = []
    for e in sorted(model.elements.values(), key=lambda x: x.id):
        if type(e).__name__ not in ELEMENT_TYPES or type(e) is not ELEMENT_TYPES[type(e).__name__]:
            raise TypeError(f'Cannot serialize element type {type(e).__name__}')
        record = {'type': type(e).__name__, 'id': e.id, 'node_i': e.node_i,
                  'node_j': e.node_j, 'material_id': e.material_id,
                  'section_id': e.section_id}
        if isinstance(e, Frame2D):
            record.update(release_i=e.release_i, release_j=e.release_j)
        elements.append(record)
    member_loads = []
    for load in model.member_loads:
        if isinstance(load, UniformLoad2D):
            member_loads.append({'type':'UniformLoad2D','element_id':load.element_id,
                                 'qx':load.qx,'qy':load.qy,'system':load.system})
        elif isinstance(load, LinearLoad2D):
            member_loads.append({'type':'LinearLoad2D','element_id':load.element_id,
                                 'qx_i':load.qx_i,'qy_i':load.qy_i,
                                 'qx_j':load.qx_j,'qy_j':load.qy_j,'system':load.system})
        elif isinstance(load, PointLoad2D):
            member_loads.append({'type':'PointLoad2D','element_id':load.element_id,
                                 'position':load.position, 'fx':load.fx, 'fy':load.fy,
                                 'system':load.system})
        else:
            raise TypeError(f'Cannot serialize member load {type(load).__name__}')
    return {
        'schema_version': SCHEMA_VERSION, 'units': 'SI',
        'nodes': [{'id':n.id,'x':n.x,'y':n.y} for n in sorted(model.nodes.values(),key=lambda n:n.id)],
        'materials': [{'id':m.id,'E':m.E} for m in sorted(model.materials.values(),key=lambda m:m.id)],
        'sections': [{'id':sec.id,'A':sec.A,'I':sec.I} for sec in sorted(model.sections.values(),key=lambda s:s.id)],
        'elements': elements,
        'constraints': [{'node_id':nid,'dof':dof,'value':v}
                        for (nid,dof),v in sorted(model.constraints.items())],
        'nodal_loads': [{'node_id':nid,'dof':dof,'value':v}
                        for (nid,dof),v in sorted(model.loads.items())],
        'member_loads': member_loads,
    }


def model_from_dict(data):
    """Validate and rebuild one model; reject unknown schema/type/field data."""
    _keys(data, TOP_KEYS, 'Model')
    if type(data['schema_version']) is not int or data['schema_version'] not in (1, SCHEMA_VERSION):
        raise ValueError(f'Unsupported model schema_version (expected 1 or {SCHEMA_VERSION})')
    if data['units'] != 'SI':
        raise ValueError("Model units must be 'SI'")
    m = StructuralModel()
    for row in _entries(data,'nodes'):
        _keys(row, ('id','x','y'), 'Node')
        m.add_node(Node(_integer_id(row['id'],'Node id'),_number(row['x'],'Node x'),_number(row['y'],'Node y')))
    for row in _entries(data,'materials'):
        _keys(row, ('id','E'), 'Material')
        m.add_material(Material(_integer_id(row['id'],'Material id'), _number(row['E'],'E')))
    for row in _entries(data,'sections'):
        _keys(row, ('id','A','I'), 'Section')
        m.add_section(Section(_integer_id(row['id'],'Section id'),_number(row['A'],'A'),_number(row['I'],'I')))
    for row in _entries(data,'elements'):
        if not isinstance(row,dict) or row.get('type') not in ELEMENT_TYPES:
            raise ValueError('Unknown or missing element type')
        typ = row['type']
        expected = ('type','id','node_i','node_j','material_id','section_id')
        if typ == 'Frame2D':
            expected += ('release_i','release_j')
        _keys(row,expected,f'{typ} element')
        args = [_integer_id(row[key], f'Element {key}') for key in
                ('id','node_i','node_j','material_id','section_id')]
        if typ == 'Frame2D':
            for key in ('release_i','release_j'):
                if type(row[key]) is not bool:
                    raise ValueError(f'{key} must be a JSON boolean')
            args.extend((row['release_i'],row['release_j']))
        m.add_element(ELEMENT_TYPES[typ](*args))
    for key, method in (('constraints',m.constrain),('nodal_loads',m.add_load)):
        seen = set()
        for row in _entries(data,key):
            _keys(row,('node_id','dof','value'),key)
            nid = _integer_id(row['node_id'], 'DOF node_id')
            dof = row['dof']
            if type(dof) is not str:
                raise ValueError('DOF name must be a string')
            if (nid,dof) in seen:
                raise ValueError(f'Duplicate {key} DOF entry {(nid,dof)}')
            seen.add((nid,dof))
            method(nid,dof,_number(row['value'], f'{key} value'))
    for row in _entries(data,'member_loads'):
        if not isinstance(row,dict) or row.get('type') not in LOAD_TYPES:
            raise ValueError('Unknown or missing member load type')
        typ = row['type']
        if typ == 'LinearLoad2D' and data['schema_version'] == 1:
            raise ValueError('LinearLoad2D requires schema_version 2')
        if typ == 'UniformLoad2D':
            expected = ('type','element_id','system','qx','qy')
        elif typ == 'LinearLoad2D':
            expected = ('type','element_id','system','qx_i','qy_i','qx_j','qy_j')
        else:
            expected = ('type','element_id','system','position','fx','fy')
        _keys(row,expected,typ)
        if type(row['system']) is not str:
            raise ValueError('Load coordinate system must be a string')
        eid = _integer_id(row['element_id'],'Member load element_id')
        if typ == 'UniformLoad2D':
            load=UniformLoad2D(eid,_number(row['qx'],'qx'),_number(row['qy'],'qy'),row['system'])
        elif typ == 'LinearLoad2D':
            load=LinearLoad2D(eid,*(_number(row[key],key) for key in
                               ('qx_i','qy_i','qx_j','qy_j')),row['system'])
        else:
            load=PointLoad2D(eid,_number(row['position'],'position'),
                             _number(row['fx'],'fx'),_number(row['fy'],'fy'),row['system'])
        m.add_member_load(load)
    return m


def save_model_json(model, path):
    """Save readable UTF-8 JSON; return Path. Does not save numerical results."""
    path = Path(path)
    text = json.dumps(model_to_dict(model), ensure_ascii=False, indent=2,
                      sort_keys=True, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    # Prevent process interruption from truncating the user's existing JSON.
    tmp = None
    try:
        fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
        tmp = Path(name)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return path


def load_model_json(path):
    """Load a model from JSON, with no executable object construction."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'),
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ValueError(f'JSON must not contain {value}')))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON in {path}: {exc}') from exc
    return model_from_dict(data)
