"""Entry for one detail preview; all async stages share its owner."""
import sys
import xbmc
from infuse_trailer_session import Preview


def main():
    if len(sys.argv) < 3 or sys.argv[1] != 'info':
        return
    preview = Preview(sys.argv[2])
    if not preview.begin():
        # Do not replace playback that was already active on entry.
        if (preview.window.getProperty('YoPlayer.Trailer.Active') == 'true'
                and preview.detail.getProperty('YoPlayer.Detail.Identity') == preview.expected
                and not preview.window.getProperty('YoPlayer.Trailer.Token')):
            preview.window.setProperty('YoPlayer.Trailer.Error',
                                       '请先停止当前播放，再重新打开预告片。')
        return
    try:
        url = preview.url
        if not url:
            from trailer import find_local
            url = find_local(preview)
        if not preview.valid():
            return
        if not url:
            from bili import prepare_preview
            if not prepare_preview(preview):
                return
            from bilitrailer import search_bili, clean_url
            url = search_bili(preview.title + ' 预告') if preview.title else None
            if url:
                url = clean_url(url)
        if not preview.valid():
            return
        if url:
            preview.play_preview(url)
        else:
            preview.error('未找到预告片，请返回后重试或检查来源。')
    except Exception as exc:
        xbmc.log('YoPlayer preview: ' + type(exc).__name__, xbmc.LOGWARNING)
        preview.error('预告片加载失败，请返回后重试。')
    finally:
        preview.close()


if __name__ == '__main__':
    main()
