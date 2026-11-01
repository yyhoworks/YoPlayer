"""Focused offline regressions for media-bound memory and remote navigation.

All preference files are disposable. This is not Kodi/CE UI acceptance.
"""
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'source/skin.yoplayer.infuse'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


for name in ('xbmc', 'xbmcaddon', 'xbmcgui', 'xbmcvfs'):
    sys.modules[name] = types.ModuleType(name)
sys.modules['xbmcgui'].NOTIFICATION_WARNING = 'warning'
sys.path.insert(0, str(SKIN / 'scripts'))
memory = module('infuse_stream_memory', SKIN / 'scripts/infuse_stream_memory.py')
player = module('review_player', SKIN / 'scripts/infuse_player.py')
navigation = module('review_navigation', SKIN / 'scripts/infuse_playback_navigation.py')
streams = module('review_streams', ROOT / 'source/plugin.video.yoplayer.home/resources/lib/player_streams.py')
TOKEN = (1, 'episode', 11, '/synthetic/A.mkv', 1, 1)
OTHER = (1, 'episode', 22, '/synthetic/B.mkv', 2, 1)
TRACK = dict(index=0, language='zho', name='Chinese', codec='aac_lc', channels=2)


class MemoryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'stream-memory.json'
        self.current = TOKEN
        self.state = dict(audiostreams=[copy.deepcopy(TRACK)], currentaudiostream=copy.deepcopy(TRACK),
                          subtitles=[], currentsubtitle={}, subtitleenabled=False)
        self.other = {'subtitle': {'enabled': False}}
        self.before = {'version': 1, 'selections': {'show:2:season:1': copy.deepcopy(self.other)}}
        self.file.write_text(json.dumps(self.before), encoding='utf-8')
        self.raw = self.file.read_bytes()
        for name, value in [('path', lambda: str(self.file)),
                            ('live', lambda: (1, 'show:%s:season:1' % self.current[4], 'scope', self.current)),
                            ('rpc', lambda *args: copy.deepcopy(self.state))]:
            p = patch.object(memory, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_stale_panel_cannot_remove_new_media_preference(self):
        self.current = OTHER
        with self.assertRaises(RuntimeError):
            memory.toggle('subtitle', memory.media_key(TOKEN))
        self.assertEqual(self.file.read_bytes(), self.raw)

    def test_missing_context_rejected_without_write(self):
        with self.assertRaises(RuntimeError):
            memory.toggle('audio', '')
        self.assertEqual(self.file.read_bytes(), self.raw)

    def test_save_remove_keeps_other_scope_and_kind(self):
        key = memory.media_key(TOKEN)
        self.assertFalse(memory.toggle('audio', key)[1])
        self.assertTrue(memory.remembered('show:1:season:1', 'audio', self.state))
        self.assertFalse(memory.toggle('subtitle', key)[1])
        self.assertTrue(memory.toggle('audio', key)[1])
        data = memory.load()['selections']
        self.assertEqual(data['show:2:season:1'], self.other)
        self.assertEqual(set(data['show:1:season:1']), {'subtitle'})

    def test_changed_track_saves_current_choice_instead_of_forgetting(self):
        key = memory.media_key(TOKEN)
        memory.toggle('audio', key)
        self.state['audiostreams'][0]['language'] = 'eng'
        self.assertFalse(memory.toggle('audio', key)[1])
        self.assertEqual(memory.load()['selections']['show:1:season:1']['audio']['identity']['language'], 'eng')

    def test_switch_during_lock_rejected(self):
        from contextlib import contextmanager
        import infuse_filelock
        @contextmanager
        def changed(_):
            self.current = OTHER
            yield
        with patch.object(infuse_filelock, 'exclusive', changed), self.assertRaises(RuntimeError):
            memory.toggle('audio', memory.media_key(TOKEN))
        self.assertEqual(self.file.read_bytes(), self.raw)

    def test_switch_before_atomic_commit_rejected_and_temp_removed(self):
        calls = []
        def rpc(*args):
            calls.append(1)
            if len(calls) == 2:
                self.current = OTHER
            return copy.deepcopy(self.state)
        with patch.object(memory, 'rpc', rpc), self.assertRaises(RuntimeError):
            memory.toggle('audio', memory.media_key(TOKEN))
        self.assertEqual(self.file.read_bytes(), self.raw)
        self.assertEqual(list(Path(self.temp.name).glob('*.tmp')), [])

    def test_command_ignores_stale_window_switch(self):
        self.current = OTHER
        sys.modules['xbmcgui'].Window = lambda _: types.SimpleNamespace(getProperty=lambda _: 'true')
        sys.modules['xbmcgui'].Dialog = lambda: types.SimpleNamespace(notification=lambda *args: None)
        with patch.object(sys, 'argv', ['script', 'remember-subtitle', memory.media_key(TOKEN)]), patch.object(player, 'refresh'):
            player.main()
        self.assertEqual(self.file.read_bytes(), self.raw)


class StreamChecks(unittest.TestCase):
    def test_counts_never_infer_layout(self):
        for n in range(1, 17):
            self.assertEqual(streams.summary(dict(codec='ac3', channels=n), 'audio'), 'AC3 %s 声道' % n)

    def test_aac_profiles(self):
        for value in ('aac_lc', 'aac_he', 'aac_he_v2', 'aac_xhe', 'he_aac_v2'):
            self.assertEqual(streams.codec_name(value), 'AAC')

    def test_ce_raw_commentary_title_is_preserved(self):
        track = dict(TRACK, name='评论', language='eng')
        row = streams.row_text([track], 'audio')[0]
        self.assertEqual(row[0], '评论')
        self.assertEqual(row[2], '评论')
        self.assertIn('英语', row[1])

    def test_duplicates_and_sparse_indexes(self):
        for kind in ('audio', 'subtitle'):
            tracks = [dict(TRACK, index=n) for n in (2, 5, 9)]
            rows = streams.distinguish_rows(streams.row_text(tracks, kind), tracks, kind)
            self.assertEqual(len(set(r[0] for r in rows)), 3)
            for row, index in zip(rows, (3, 6, 10)):
                self.assertTrue(row[0].endswith('轨道 %s' % index))
            reverse = streams.distinguish_rows(streams.row_text(tracks[::-1], kind), tracks[::-1], kind)
            self.assertEqual([r[0] for r in rows], [r[0] for r in reverse[::-1]])

    def test_old_off_row_cannot_touch_new_media(self):
        key = streams.stream_key(1, {'file': 'A'}, 'subtitle', {'index': 'off'})
        writes = []
        with patch.object(streams, 'snapshot', return_value=(1, {'file': 'B'}, {})):
            with self.assertRaises(RuntimeError):
                streams.select_stream(lambda *args: writes.append(args), 'subtitle', 'off', key)
        self.assertEqual(writes, [])


def condition(value, memory_on, tab, count=2):
    def atom(text):
        if 'InfuseStreamTab' in text:
            return text.endswith(',' + tab + ')')
        if any(x in text for x in ('MemoryReady', 'MemoryFile', 'MemoryDBID')):
            return memory_on
        if text.startswith('Integer.IsEqual(Container('):
            return count == 0
        raise ValueError(text)
    value = value or 'True'
    while (m := re.search(r'(?:String.IsEqual|Integer.IsEqual)\(', value)):
        start, pos, depth = m.start(), m.end(), 1
        while depth:
            depth += (value[pos] == '(') - (value[pos] == ')')
            pos += 1
        value = value[:start] + str(atom(value[start:pos])) + value[pos:]
    value = value.replace('Player.HasVideo', 'True').replace('VideoPlayer.HasSubtitles', 'True')
    value = value.replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(value.strip(), {'__builtins__': {}}, {}))


class NavigationChecks(unittest.TestCase):
    def test_audio_chain_with_and_without_memory(self):
        for filename, audio in [('Custom_1144_OSD_subtitles.xml', '2022'), ('Custom_1145_OSD_audio.xml', '2041')]:
            root = ET.parse(SKIN / '1080p' / filename).getroot()
            controls = {c.get('id'): c for c in root.iter('control') if c.get('id')}
            for ready in (False, True):
                def targets(ident, direction, count=2):
                    return [a.text for a in controls[ident].findall(direction)
                            if condition(a.get('condition'), ready, 'audio', count)]
                self.assertEqual(targets(audio, 'ondown'), ['2092' if ready else '2094'])
                self.assertEqual(targets('2071', 'ondown', 0), ['2092' if ready else '2094'])
                self.assertEqual(targets('2091', 'onup'), ['2094'])
                self.assertEqual(targets('2094', 'onup'), ['2092' if ready else audio])
                self.assertEqual(targets('2094', 'ondown'), ['2091'])

    def test_osd_round_trip_and_read_only_details(self):
        r = ET.parse(SKIN / '1080p/VideoOSD.xml').getroot()
        c = {n.get('id'): n for n in r.iter('control') if n.get('id')}
        self.assertEqual(c['88'].findtext('ondown'), 'Dialog.Close(videoosd)')
        self.assertEqual(c['88'].findtext('onup'), '205')
        self.assertEqual(c['89'].findtext('onup'), '205')
        self.assertEqual(c['89'].findtext('ondown'), 'Dialog.Close(videoosd)')
        self.assertEqual(c['89'].findtext('onleft'), 'Action(StepBack)')
        self.assertEqual(c['89'].findtext('onright'), 'Action(StepForward)')
        for ident in ('205', '202', '204', '207'):
            self.assertEqual(c[ident].findtext('ondown'), '89')
            self.assertEqual(c[ident].findtext('onup'), 'Dialog.Close(videoosd)')
        info = ET.parse(SKIN / '1080p/DialogPlayerProcessInfo.xml').getroot()
        focus = info.findtext('defaultcontrol')
        button = next(n for n in info.iter('control') if n.get('id') == focus)
        for direction in ('onup', 'ondown', 'onleft', 'onright'):
            self.assertEqual(button.findtext(direction), 'noop')

    def test_entry_does_not_seek_and_other_skin_and_livetv_keep_native_actions(self):
        effects, props = [], {}
        xbmc = sys.modules['xbmc']
        xbmc.executebuiltin = effects.append
        xbmcgui = sys.modules['xbmcgui']
        xbmcgui.Window = lambda _: types.SimpleNamespace(setProperty=lambda k, v: props.update({k: v}))
        for direction in ('up', 'down'):
            effects.clear()
            xbmc.getSkinDir = lambda: 'skin.yoplayer.infuse'
            xbmc.getCondVisibility = lambda x: x in ('Window.IsActive(fullscreenvideo) + Player.HasVideo', 'Player.SeekEnabled')
            navigation.main(direction)
            self.assertEqual(effects, ['ActivateWindow(videoosd)'])
            self.assertEqual(props['YoPlayer.Infuse.OSDEntry'], direction)
            effects.clear()
            xbmc.getSkinDir = lambda: 'other.skin'
            navigation.main(direction)
            self.assertEqual(effects, ['Action(ChapterOrBigStep%s)' % ('Forward' if direction == 'up' else 'Back')])
        effects.clear()
        xbmc.getSkinDir = lambda: 'skin.yoplayer.infuse'
        xbmc.getCondVisibility = lambda x: x == 'VideoPlayer.Content(livetv)'
        navigation.main('up')
        self.assertEqual(effects, ['Action(ChapterOrBigStepForward)'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
