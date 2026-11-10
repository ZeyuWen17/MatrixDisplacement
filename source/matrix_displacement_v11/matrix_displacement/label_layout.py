"""Qt-independent best-effort collision reduction for structure canvas annotations.

All geometry is expressed in scene pixels, not physical engineering units.
The greedy placement prioritizes labels supplied first and never silently
suppresses a label. Dense/over-constrained views may still overlap.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class LabelRequest:
    anchor_x: float
    anchor_y: float
    width: float
    height: float
    preferred_x: float = 0.0
    preferred_y: float = 0.0


def rectangles_overlap(a, b, gap=2.0):
    return not (a[2]+gap <= b[0] or b[2]+gap <= a[0] or
                a[3]+gap <= b[1] or b[3]+gap <= a[1])


def place_labels(requests, obstacles=(), *, gap=3.0):
    """Return top-left scene positions matching request order.

    Each request is positioned near its preferred top-left. A finite, ordered
    candidate grid is searched; clashes have a heavy penalty and displacement
    has a smaller penalty. The result is deterministic and bounded.
    """
    requests = tuple(requests)
    placed = []
    reserved = []
    obstacles = tuple(tuple(float(v) for v in r) for r in obstacles)
    for r in obstacles:
        if len(r) != 4 or not all(isfinite(v) for v in r) or r[2] < r[0] or r[3] < r[1]:
            raise ValueError('文字避让障碍物必须为有限矩形')
    if not isfinite(gap) or gap < 0:
        raise ValueError('gap must be finite and nonnegative')
    for req in requests:
        if not isinstance(req, LabelRequest):
            raise TypeError('Expected LabelRequest')
        args = (req.anchor_x, req.anchor_y, req.width, req.height, req.preferred_x, req.preferred_y)
        if not all(isfinite(v) for v in args) or req.width <= 0 or req.height <= 0:
            raise ValueError('文字尺寸和位置必须为有限数值，宽高必须大于零')
        base_x = req.anchor_x + req.preferred_x
        base_y = req.anchor_y + req.preferred_y
        # Try near positions first, then move outwards with at most 4 rings.
        step_x = max(14.0, req.width * 0.55)
        step_y = max(12.0, req.height + gap)
        offsets = [(0, 0)]
        for ring in range(1, 5):
            for iy in range(-ring, ring+1):
                for ix in range(-ring, ring+1):
                    if max(abs(ix), abs(iy)) == ring:
                        offsets.append((ix, iy))
        best = None
        best_cost = float('inf')
        for ix, iy in offsets:
            x, y = base_x + ix*step_x, base_y + iy*step_y
            rect = (x, y, x+req.width, y+req.height)
            occupied = sum(rectangles_overlap(rect, other, gap) for other in reserved)
            obstacle_hits = sum(rectangles_overlap(rect, other, gap) for other in obstacles)
            # Preserve readability near structural nodes and existing labels.
            cost = 10000*(occupied + obstacle_hits) + 2*(ix*ix+iy*iy) + 0.01*(abs(ix)+abs(iy))
            if cost < best_cost:
                best_cost = cost
                best = (x, y, rect)
                if cost == 0:
                    break
        placed.append((best[0], best[1]))
        reserved.append(best[2])
    return tuple(placed)
