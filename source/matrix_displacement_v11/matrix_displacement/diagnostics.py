"""Clear user-facing hints for common educational solver/model errors.

These hints supplement the original exception rather than silently changing
an invalid model or inventing a stable solution.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorExplanation:
    title: str
    detail: str


def explain_error(exc):
    """Map known errors to actionable Chinese guidance; retain exact details."""
    detail = str(exc)
    original = f'{type(exc).__name__}: {detail}'
    text = detail.lower()
    if 'singular stiffness' in text or 'near-singular stiffness' in text or 'non-positive diagonal' in text:
        locations = getattr(exc, 'dofs', ())
        hint = ''
        if locations:
            heading = ('近零刚度模态涉及的候选自由度（不代表唯一故障原因）' if getattr(exc, 'suspected', False)
                       else '刚度对角项非正的自由度')
            hint = '\n\n' + heading + '：\n' + '、'.join(f'节点 {n} / {d}' for n, d in locations)
        return ErrorExplanation('结构不稳定或约束不足',
            '刚度矩阵无法可靠求解。请检查支座约束、未连接节点、零刚度自由度及杆端释放是否形成机构。'+hint+'\n\n'+original)
    if 'beam2d' in text or 'transverse loads only' in text:
        return ErrorExplanation('连续梁单元输入不适用',
            'Beam2D 仅用于从左到右的水平梁及横向荷载；斜梁或轴向变形应采用 Frame2D。\n\n'+original)
    if 'zero length' in text or 'duplicate node' in text or 'same coordinate' in text:
        return ErrorExplanation('结构几何输入错误',
            '请检查重合节点、零长度杆件和坐标输入。\n\n'+original)
    if 'non-finite' in text or 'finite real' in text or '有限数值' in text:
        return ErrorExplanation('非法数值输入',
            '请检查是否存在 NaN、Inf、空值、溢出及不一致的单位。\n\n'+original)
    if 'model must contain' in text or 'no elements' in text:
        return ErrorExplanation('尚无可计算的结构',
            '请至少建立节点、杆件与必要支座，再运行分析。\n\n'+original)
    if 'point load position' in text:
        return ErrorExplanation('杆内集中荷载位置错误',
            '集中力的位置必须介于杆件 i 端与 j 端之间，使用 m 为单位。\n\n'+original)
    return ErrorExplanation('操作或计算失败', original)
