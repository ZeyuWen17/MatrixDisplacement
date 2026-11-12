"""Explicit dimensional input; bare numbers retain the field's SI unit."""
import math
import re

UNITS = {
    'm': {'m': 1, 'mm': 1e-3, 'cm': 1e-2},
    'N': {'N': 1, 'kN': 1e3, 'MN': 1e6},
    'Pa': {'Pa': 1, 'kPa': 1e3, 'MPa': 1e6, 'GPa': 1e9},
    'm2': {'m2': 1, 'cm2': 1e-4, 'mm2': 1e-6},
    'm4': {'m4': 1, 'cm4': 1e-8, 'mm4': 1e-12},
    'N*m': {'N*m': 1, 'kN*m': 1e3, 'N*mm': 1e-3, 'kN*mm': 1},
    'N/m': {'N/m': 1, 'kN/m': 1e3, 'N/mm': 1e3, 'kN/mm': 1e6},
    'rad': {'rad': 1, 'deg': math.pi/180, '°': math.pi/180},
    '': {'': 1},
}


def normalize(unit):
    return unit.replace('²', '2').replace('⁴', '4').replace('^', '').replace('·', '*').replace(' ', '')


def parse_quantity(text, unit, name='数值'):
    unit = normalize(unit)
    match = re.fullmatch(r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*?)\s*', str(text))
    if not match:
        raise ValueError(f'{name}：请输入有限数值，可附单位，如 10 kN、200 mm、210 GPa')
    suffix = normalize(match[2]) or unit
    choices = UNITS[unit]
    if suffix not in choices:
        raise ValueError(f'{name}：单位不匹配；允许 {", ".join(choices)}，不带单位时按 {unit or "无量纲"}')
    value = float(match[1]) * choices[suffix]
    if not math.isfinite(value):
        raise ValueError(f'{name} 必须是有限数值')
    return value


def label_unit(label):
    match = re.search(r'\(([^()]*)\)', label)
    return match[1] if match else ''
