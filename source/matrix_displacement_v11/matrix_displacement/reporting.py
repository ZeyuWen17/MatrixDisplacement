"""Educational, human-readable Markdown report from a teaching-mode solve."""
from pathlib import Path
import numpy as np
from .core import UniformLoad2D, PointLoad2D, LinearLoad2D


def _array(value, digits):
    arr = np.asarray(value)
    return np.array2string(arr, precision=digits, threshold=100_000,
                           max_line_width=140, suppress_small=False,
                           formatter={'float_kind': lambda x: f'{x:.{digits}g}'})


def _fmt(value, digits):
    return f'{float(value):.{digits}g}'


def render_teaching_report(model, result, *, digits=6, max_dofs=80):
    """Render solver matrices and intermediate results (Markdown string).

    Designed for course-size examples. The report requires a teaching-mode
    AnalysisResult and retains the actual stiffness values (SI units).
    """
    if result.trace is None:
        raise ValueError('Teaching report requires LinearStaticSolver(Mode.TEACHING)')
    if type(digits) is not int or not 2 <= digits <= 12:
        raise ValueError('digits must be an integer between 2 and 12')
    dm = result.dof_manager
    if max_dofs is not None and (type(max_dofs) is not int or max_dofs <= 0):
        raise ValueError('max_dofs must be a positive integer or None')
    if max_dofs is not None and dm.ndof > max_dofs:
        raise ValueError(f'Report has {dm.ndof} DOFs, exceeding max_dofs={max_dofs}')
    trace = result.trace
    lines = [
        '# 矩阵位移法教学计算报告', '',
        '**计算类型：** 二维线弹性、小变形静力分析  ',
        '**计算模式：** 教学模式（Teaching）  ',
        '**单位体系：** SI；长度 m、力 N、力矩 N·m、弹性模量 Pa、转角 rad', '',
        '## 1. 模型概况', '',
        f'- 节点数量：{len(model.nodes)}',
        f'- 单元数量：{len(model.elements)}',
        f'- 总自由度数量：{dm.ndof}',
        '', '| 节点 | x (m) | y (m) |', '|---:|---:|---:|',
    ]
    for n in sorted(model.nodes.values(),key=lambda a:a.id):
        lines.append(f'| {n.id} | {_fmt(n.x,digits)} | {_fmt(n.y,digits)} |')
    lines.extend(['', '| 单元 | 类型 | i → j | E (Pa) | A (m²) | I (m⁴) |',
                  '|---:|---|---|---:|---:|---:|'])
    for e in sorted(model.elements.values(),key=lambda e:e.id):
        mat, sec = model.materials[e.material_id], model.sections[e.section_id]
        lines.append(f'| {e.id} | {type(e).__name__} | {e.node_i} → {e.node_j} | '
                     f'{_fmt(mat.E,digits)} | {_fmt(sec.A,digits)} | {_fmt(sec.I,digits)} |')
    lines += ['', '### 模型外荷载输入', '',
              '| 节点 | 自由度 | 荷载（N 或 N·m） |', '|---:|---|---:|']
    for (nid,dof),value in sorted(model.loads.items()):
        lines.append(f'| {nid} | {dof} | {_fmt(value,digits)} |')
    if not model.loads:
        lines.append('| — | — | 无节点荷载 |')
    lines += ['', '| 单元 | 荷载类型 | 作用位置/分量（SI） | 坐标系 |',
              '|---:|---|---|---|']
    for load in model.member_loads:
        if isinstance(load, UniformLoad2D):
            label=f'qx={_fmt(load.qx,digits)} N/m, qy={_fmt(load.qy,digits)} N/m'
        elif isinstance(load, LinearLoad2D):
            label=(f'i: (qx={_fmt(load.qx_i,digits)}, qy={_fmt(load.qy_i,digits)}), '
                   f'j: (qx={_fmt(load.qx_j,digits)}, qy={_fmt(load.qy_j,digits)}) N/m')
        elif isinstance(load, PointLoad2D):
            label=(f'x={_fmt(load.position,digits)} m, '
                   f'fx={_fmt(load.fx,digits)} N, fy={_fmt(load.fy,digits)} N')
        else:
            label='不支持的类型'
        lines.append(f'| {load.element_id} | {type(load).__name__} | {label} | {load.system} |')
    if not model.member_loads:
        lines.append('| — | — | 无杆件荷载 | — |')
    lines += ['', '## 2. 自由度编号与边界条件', '',

              '| 全局编号（从 0 开始） | 节点 | 自由度 | 已知位移 |',
              '|---:|---:|---|---:|']
    for (nid,dof), idx in sorted(dm.mapping.items(),key=lambda item:item[1]):
        val = model.constraints.get((nid,dof))
        label = '自由' if val is None else _fmt(val,digits)
        if idx in dm.inactive:
            label = '非活跃（铰端转角）'
        lines.append(f'| {idx} | {nid} | {dof} | {label} |')
    lines += ['', '## 3. 单元刚度与等效荷载', '']
    for eid, entry in sorted(trace['elements'].items()):
        lines += [f'### 单元 {eid}', '',
                  f'全局自由度索引：`{entry["indices"].tolist()}`', '',
                  '局部刚度矩阵 `k_local`：', '```text', _array(entry['local_stiffness'],digits), '```',
                  '坐标转换矩阵 `T`：', '```text',_array(entry['transformation'],digits),'```',
                  '整体坐标单元刚度矩阵 `k_global = T^T k_local T`：',
                  '```text',_array(entry['global_stiffness'],digits),'```',
                  '局部一致等效节点荷载 `f_eq`：',
                  '```text',_array(entry['equivalent_nodal_load_local'],digits),'```',
                  '局部固端抗力 `-f_eq`：',
                  '```text',_array(entry['fixed_end_forces_local'],digits),'```', '']
    lines += ['## 4. 整体刚度矩阵和荷载列阵', '',
              '### 4.1 按单元叠加的组装过程', '',
              r'组装规则：$K_{I_a I_b} \leftarrow K_{I_a I_b} + (k_e^{global})_{ab}$，'
              '其中 `I` 为当前单元的全局自由度映射；同一位置的多个单元贡献相加。', '']
    for step_id, entry in enumerate(trace['assembly'],1):
        idx = entry['indices'].tolist()
        lines += [f'**步骤 {step_id} — 单元 {entry["element_id"]}**', '',
                  f'局部自由度 → 全局索引：`{idx}`', '',
                  '本单元叠加的 `k_global`：', '```text',
                  _array(entry['contribution'],digits), '```',
                  '本步组装完成后的整体矩阵 `K`：', '```text',
                  _array(entry['stiffness_after'],digits), '```', '']
    lines += ['### 4.2 完整整体矩阵', '',
              '整体刚度矩阵 `K`：','```text',_array(trace['global_stiffness'],digits),'```',
              '节点外荷载 `F_nodal`：','```text',_array(trace['nodal_load'],digits),'```',
              '杆件等效节点荷载 `F_member`：','```text',_array(trace['member_load'],digits),'```',
              '总荷载 `F = F_nodal + F_member`：','```text',_array(trace['global_load'],digits),'```',
              '', '## 5. 约束处理与求解', '',
              f'自由索引：`{trace["free_dofs"].tolist()}`  ',
              f'已知位移索引：`{trace["fixed_dofs"].tolist()}`', '',
              '缩减刚度矩阵 `K_ff`：','```text',_array(trace['reduced_stiffness'],digits),'```',
              '缩减右端 `F_f - K_fc d_c`：','```text',_array(trace['reduced_rhs'],digits),'```',
              '整体位移列阵 `d`：','```text',_array(result.displacements,digits),'```',
              '整体反力列阵 `R = Kd - F`：','```text',_array(result.reactions,digits),'```',
              '', '## 6. 节点位移与支座反力', '',
              '| 节点 | 自由度 | 位移（m 或 rad） | 反力（N 或 N·m） |',
              '|---:|---|---:|---:|']
    for (nid,dof), idx in sorted(dm.mapping.items(),key=lambda item:item[1]):
        lines.append(f'| {nid} | {dof} | {_fmt(result.displacements[idx],digits)} '
                     f'| {_fmt(result.reactions[idx],digits)} |')
    lines += ['', '## 7. 杆端抗力（局部坐标）', '']
    for eid, q in sorted(result.element_end_forces_local.items()):
        labels = '[Fx_i,Fy_i,Mi,Fx_j,Fy_j,Mj]' if len(q)==6 else (
                 '[Fy_i,Mi,Fy_j,Mj]' if len(q)==4 and model.elements[eid].local_dofs[0]=='uy'
                 else '[Fx_i,Fy_i,Fx_j,Fy_j]')
        lines += [f'**单元 {eid}**：`{labels}`', '```text', _array(q,digits),'```','']
    lines += ['---', '',
              '> 注：单元杆端抗力采用局部坐标与程序正负号约定。梁端杆力、'
              '支座反力与内力图正负号应结合上述规定解释。'
              '本报告保留中间矩阵，但不代表非线性或动力分析过程。', '']
    return '\n'.join(lines)


def save_teaching_report(model, result, path, **kwargs):
    """Write a UTF-8 Markdown report to path and return Path."""
    content = render_teaching_report(model,result,**kwargs)
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content,encoding='utf-8')
    return path
