"""The eight Home rows share visibility, freshness and completion semantics."""
PREFIX = 'YoPlayer.Infuse.'
ROWS = {
    'continue': (301, 'InfuseHideContinue'),
    'libraries': (302, 'InfuseHideLibraries'),
    'daily': (309, 'InfuseHidePicks'),
    'recent-movies': (304, 'InfuseHideRecentMovies'),
    'recent-episodes': (303, 'InfuseHideRecentEpisodes'),
    'genres': (305, 'InfuseHideGenres'),
    'tvshow-genres': (308, 'InfuseHideShowGenres'),
    'unwatched': (307, 'InfuseHideUnwatched'),
}


def hidden(route, visible):
    return route in ROWS and visible('Skin.HasSetting(' + ROWS[route][1] + ')')


def finish(window, route, revision, count, error=''):
    """A late directory result must not overwrite the next refresh's status."""
    if route not in ROWS or window.getProperty(PREFIX + 'RowRevision.' + route) != revision:
        return False
    window.setProperty(PREFIX + 'Count.' + route, str(count))
    window.setProperty(PREFIX + 'Loaded.' + route, revision or 'initial')
    if error:
        window.setProperty(PREFIX + 'Error.' + route, error)
    else:
        window.clearProperty(PREFIX + 'Error.' + route)
    return True
