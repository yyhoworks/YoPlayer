"""Read-only display labels derived from the library's existing resume data."""
import math


def remaining_label(resume):
    if not isinstance(resume, dict):
        return ''
    try:
        if isinstance(resume.get('position'), bool) or isinstance(resume.get('total'), bool):
            return ''
        position = float(resume.get('position') or 0)
        total = float(resume.get('total') or 0)
    except (TypeError, ValueError, OverflowError):
        return ''
    if not math.isfinite(position) or not math.isfinite(total) or not 0 < position < total:
        return ''
    seconds = total - position
    if seconds < 60:
        return '剩余不足 1 分钟'
    return '剩余 {} 分钟'.format(int(math.ceil(seconds / 60)))
