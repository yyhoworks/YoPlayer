"""Stable ordered homepage genre choices; no UI or library mutations."""
import copy

RECOMMENDED = ('动作', '科幻', '悬疑', '喜剧', '剧情', '动画', '犯罪', '惊悚', '爱情', '纪录片')
# Explicit equivalents only; never substring/fuzzy matching or metadata edits.
ALIASES = {
    '动作': ('action', '動作'), '科幻': ('science fiction', 'sci-fi', '科學幻想', '科幻片'),
    '悬疑': ('mystery', '懸疑'), '喜剧': ('comedy', '喜劇'), '剧情': ('drama', '劇情'),
    '动画': ('animation', '動畫'), '犯罪': ('crime',), '惊悚': ('thriller', '驚悚'),
    '爱情': ('romance', '愛情'), '纪录片': ('documentary', '紀錄片', '纪录'),
    '战争': ('war', '戰爭'), '冒险': ('adventure', '冒險'), '奇幻': ('fantasy',),
    '恐怖': ('horror',), '家庭': ('family',),
}
CANONICAL = {alias.casefold(): name for name, aliases in ALIASES.items() for alias in (name,) + aliases}


DISPLAY_NAMES = {'--NO INFO--': '未分类', 'Sci-Fi & Fantasy': '科幻与奇幻', 'War & Politics': '战争与政治'}


def display_name(name):
    """Display only: preserve exact names, IDs, grouping and route payloads."""
    return DISPLAY_NAMES.get(name, name)


def canonical(name):
    return CANONICAL.get(name.strip().casefold(), name)


def grouped(values, populated=None):
    """Exact alias unions retain every source ID/name for native filtering."""
    result = {}
    for row in rows(values):
        if populated is not None and row['name'] not in populated:
            continue
        name = canonical(row['name'])
        entry = result.setdefault(name, {'id': row['id'], 'name': name, 'ids': [], 'names': []})
        entry['ids'].append(row['id']); entry['names'].append(row['name'])
    return list(result.values())


def recommended(available):
    return [copy.deepcopy(row) for name in RECOMMENDED for row in available if canonical(row['name']) == name]


def rows(values):
    result, seen = [], set()
    for value in values:
        ident, label = value.get('genreid'), value.get('label')
        if type(ident) is not int or ident < 0 or not isinstance(label, str) or not label or ident in seen:
            continue
        result.append({'id': ident, 'name': label})
        seen.add(ident)
    return result


def resolve(saved, available):
    """Keep exact identity, or remap a unique name after a library rebuild."""
    result, missing = [], []
    for item in saved:
        exact = [r for r in available if (r['id'] == item.get('id') or item.get('id') in r.get('ids', []))
                 and canonical(r['name']) == canonical(item.get('name', ''))]
        named = [r for r in available if canonical(r['name']) == canonical(item.get('name', ''))]
        match = exact or (named if len(named) == 1 else [])
        if match and match[0] not in result:
            result.append(copy.deepcopy(match[0]))
        elif not match:
            missing.append(item)
    return result, missing


def selected(config, available):
    # An explicitly saved empty list stays empty; no truthiness fallback.
    if 'selected' not in config:
        return recommended(available), []
    return resolve(config['selected'], available)


def reselect(previous, available, picked):
    chosen = {available[i]['id'] for i in picked if 0 <= i < len(available)}
    old, _ = resolve(previous, available)
    result = [r for r in old if r['id'] in chosen]
    result += [copy.deepcopy(r) for r in available if r['id'] in chosen and r not in result]
    return result


def move(items, index, offset):
    target = index + offset
    if not 0 <= index < len(items) or not 0 <= target < len(items):
        return index
    items[index], items[target] = items[target], items[index]
    return target
