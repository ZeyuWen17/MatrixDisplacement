"""Named load snapshots and linear combinations on shared geometry/supports.

Prescribed displacements belong to the shared support model, and are applied
once when a combination is solved, not multiplied by load factors.
"""
from copy import deepcopy
import math


def checked_name(name):
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError('工况名称须为 1～80 个字符')
    return name.strip()


def capture_case(model, name):
    from .io import model_to_dict
    name = checked_name(name)
    data = model_to_dict(model)
    model.load_cases[name] = {key: deepcopy(data[key]) for key in ('nodal_loads', 'member_loads')}


def case_model(model, name):
    from .io import model_to_dict, model_from_dict
    if name not in model.load_cases:
        raise ValueError(f'工况不存在：{name}')
    data = model_to_dict(model)
    data.pop('load_cases', None)
    data.pop('load_combinations', None)
    data['schema_version'] = 2
    data.update(deepcopy(model.load_cases[name]))
    return model_from_dict(data)


def combination_model(model, factors):
    from dataclasses import replace
    if not isinstance(factors, dict) or not factors:
        raise ValueError('组合至少需要一个工况')
    combined = deepcopy(model)
    combined.loads = {}
    combined.member_loads = []
    for name, factor in factors.items():
        if type(factor) not in (float, int) or not math.isfinite(factor):
            raise ValueError('组合系数必须为有限数值')
        source = case_model(model, name)
        for key, value in source.loads.items():
            combined.loads[key] = combined.loads.get(key, 0.) + factor * value
        for load in source.member_loads:
            keys = ('qx', 'qy') if hasattr(load, 'qx') else (
                ('qx_i', 'qy_i', 'qx_j', 'qy_j') if hasattr(load, 'qx_i') else ('fx', 'fy'))
            combined.member_loads.append(replace(load, **{key: getattr(load, key)*factor for key in keys}))
    if any(not math.isfinite(v) for v in combined.loads.values()):
        raise ValueError('组合荷载超出有限数值范围')
    return combined


def apply_loads(model, source):
    model.loads = deepcopy(source.loads)
    model.member_loads = deepcopy(source.member_loads)
