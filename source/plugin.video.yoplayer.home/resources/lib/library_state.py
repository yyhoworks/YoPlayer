"""Scoped browse state and exact filters; no settings/history mutations."""
import copy

SORTS = (('标题', 'title'), ('年份', 'year'), ('评分', 'rating'), ('添加时间', 'dateadded'))


def normalize(value, content='movies'):
    value = copy.deepcopy(value)
    value.setdefault('title', '资料库')
    value.setdefault('content', content)
    value.setdefault('method', 'episode' if value['content'] == 'episodes' else 'title')
    if value['method'] in ('', 'douban'):
        value['method'] = 'rating' if value['method'] == 'douban' else ('episode' if value['content'] == 'episodes' else 'title')
    value.setdefault('order', 'ascending')
    value.setdefault('query', '')
    value.setdefault('watched', 'all')
    value.setdefault('genre', '')
    value.setdefault('year', '')
    if value['method'] not in {x[1] for x in SORTS} | {'episode'} or value['order'] not in ('ascending', 'descending'):
        raise ValueError('Unsupported ordering')
    if value['watched'] not in ('all', 'unwatched', 'watched'):
        raise ValueError('Unsupported watched filter')
    if not isinstance(value.get('origin'), str) or not value['origin'] or 'route=native-browse' in value['origin']:
        raise ValueError('Invalid original directory')
    for key in ('query', 'genre', 'year'):
        if not isinstance(value[key], str):
            raise ValueError('Invalid text filter')
    return value


def filtered(rows, state):
    from genres import canonical
    result = []
    for row in rows:
        if state['query'].casefold() not in (row.get('title') or row.get('label') or '').casefold():
            continue
        if state['genre'] and state['genre'] not in {canonical(g) for g in row.get('genre', [])}:
            continue
        if state['year'] and str(row.get('year') or '') != state['year']:
            continue
        watched = bool(row.get('playcount'))
        if row.get('type') == 'tvshow' and row.get('episode'):
            watched = int(row.get('watchedepisodes') or 0) >= int(row['episode'])
        if state['watched'] != 'all' and watched != (state['watched'] == 'watched'):
            continue
        result.append(row)
    return result


def summary(state):
    title = dict((key, name) for name, key in SORTS).get(state['method'], '集数')
    parts = [title + ' · ' + ('升序' if state['order'] == 'ascending' else '降序')]
    parts += [x for x in (dict(all='', watched='已看', unwatched='未看')[state['watched']], state['genre'], state['year']) if x]
    if state['query']:
        parts.append('搜索：' + state['query'])
    return ' · '.join(parts)
