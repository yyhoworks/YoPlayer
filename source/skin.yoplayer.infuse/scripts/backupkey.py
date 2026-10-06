"""Compatible keymaps-only backup/restore, with validation and rollback.

Archive format remains flat XML files inside userdata/keymaps/backup/*.zip.
No skin settings, hardware mappings, databases or system files are included.
"""
from pathlib import Path
import os
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
import xbmc
import xbmcgui
import xbmcvfs

MAX_FILES = 256
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
EMPTY_ROLLBACK_MARKER = b'YoPlayer: verified empty keymaps rollback v1'


def paths():
    keymaps = Path(xbmcvfs.translatePath('special://userdata/keymaps/'))
    return keymaps, keymaps / 'backup'


def current_files(keymaps):
    if not keymaps.exists():
        return {}
    if keymaps.is_symlink() or not keymaps.is_dir():
        raise ValueError('按键目录不是可用的普通目录')
    result = {}
    for path in sorted(keymaps.iterdir()):
        if path.suffix.lower() == '.xml':
            if path.is_symlink() or not path.is_file():
                raise ValueError('按键目录包含非普通 XML 文件')
            result[path.name] = path.read_bytes()
    return result


def validate_archive(path):
    """Validate everything before touching current keymaps. No extractall."""
    result = {}
    folded = set()
    total = 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if not members and archive.comment == EMPTY_ROLLBACK_MARKER:
            return {}
        if not members or len(members) > MAX_FILES:
            raise ValueError('备份为空或文件数量超出限制')
        for member in members:
            name = member.filename
            if (member.is_dir() or '/' in name or '\\' in name or ':' in name
                    or name in ('.', '..') or not name.lower().endswith('.xml')
                    or name.rstrip(' .') != name or name.casefold() in folded):
                raise ValueError('备份必须仅包含不重复的顶层 XML 文件')
            # Symlinks and encrypted archives are not valid keymap backups.
            if (member.external_attr >> 16) & 0o170000 == 0o120000 or member.flag_bits & 1:
                raise ValueError('备份包含链接或加密文件')
            total += member.file_size
            if member.file_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise ValueError('备份内容超出按键配置大小限制')
            data = archive.read(member)
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                raise ValueError('按键 XML 不能包含外部声明')
            root = ET.fromstring(data)
            if root.tag != 'keymap':
                raise ValueError('XML 不是 Kodi keymap 配置')
            folded.add(name.casefold())
            result[name] = data
    return result


def unique_archive(folder, prefix='遥控器备份_'):
    return folder / (prefix + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8] + '.zip')


def write_archive(path, files):
    if path.parent.is_symlink():
        raise ValueError('备份目录不能是符号链接')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids replacing delivered or older user backups.
    created = False
    try:
        with open(path, 'xb') as stream:
            created = True
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                if not files:
                    archive.comment = EMPTY_ROLLBACK_MARKER
                for name, data in files.items():
                    archive.writestr(name, data)
    except Exception:
        # Our generated destination was absent before this attempt.
        if created and path.exists():
            path.unlink()
        raise


def backup_config(keymaps, folder):
    files = current_files(keymaps)
    if not files:
        raise ValueError('没有可备份的顶层按键 XML 文件')
    output = unique_archive(folder)
    write_archive(output, files)
    return output


def replace_file(path, data):
    fd, temp = tempfile.mkstemp(prefix='.yoplayer-keymap-', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def restore_config(keymaps, folder, archive_path, confirm):
    incoming = validate_archive(archive_path)
    previous = current_files(keymaps)
    if os.name == 'nt':
        existing_case = {name.casefold():name for name in previous}
        incoming = {existing_case.get(name.casefold(),name):data for name,data in incoming.items()}
    if not confirm(archive_path.name, len(incoming), len(previous)):
        return None
    keymaps.mkdir(parents=True, exist_ok=True)
    rollback = unique_archive(folder, '恢复前_')
    write_archive(rollback, previous)
    # Recheck after modal confirmation, before modifying files changed externally.
    if current_files(keymaps) != previous:
        raise RuntimeError('按键配置已被其他操作修改；请重新选择备份')
    try:
        for name, data in incoming.items():
            replace_file(keymaps / name, data)
        for name in previous.keys() - incoming.keys():
            (keymaps / name).unlink()
        if current_files(keymaps) != incoming:
            raise RuntimeError('恢复后的文件校验失败')
    except Exception as error:
        try:
            for name, data in previous.items():
                replace_file(keymaps / name, data)
            for name in incoming.keys() - previous.keys():
                target = keymaps / name
                if target.exists(): target.unlink()
        except Exception as rollback_error:
            raise RuntimeError('恢复和自动回退均未完成；恢复前备份：{}'.format(rollback)) from rollback_error
        raise RuntimeError('恢复失败，原按键文件已恢复；备份：{}'.format(rollback)) from error
    return rollback


def backups(folder):
    if folder.is_symlink(): raise ValueError('备份目录不能是符号链接')
    if not folder.is_dir(): return []
    # Keep date-only, original Chinese-prefix and imported names compatible.
    return sorted((p for p in folder.iterdir() if p.is_file() and not p.is_symlink()
                   and p.suffix.lower() == '.zip'), key=lambda p:p.stat().st_mtime, reverse=True)


def choose_backup(dialog, folder, heading):
    items = backups(folder)
    if not items:
        dialog.ok(heading, '未找到遥控器配置备份。')
        return None
    selected = dialog.select(heading, [p.name for p in items])
    return items[selected] if 0 <= selected < len(items) else None


def import_export(dialog, folder):
    choice = dialog.select('导入/导出遥控器配置备份', ['导出备份', '导入备份'])
    if choice == 0:
        items = backups(folder)
        if not items:
            dialog.ok('导出备份', '未找到备份文件。'); return
        destination = dialog.browseSingle(3, '请选择导出目录', 'files')
        if not destination: return
        destination = Path(xbmcvfs.translatePath(destination))
        if not destination.is_dir(): raise ValueError('请选择已存在的本地导出目录')
        for source in items:
            target = destination / source.name
            if target.exists():
                # Do not silently overwrite a different external archive.
                raise ValueError('导出目录存在同名备份，未覆盖：'+source.name)
        for source in items:
            with open(destination / source.name, 'xb') as stream:
                stream.write(source.read_bytes())
        dialog.ok('导出完成', '已导出 {} 个备份。'.format(len(items)))
    elif choice == 1:
        source = dialog.browseSingle(1, '选择按键备份 ZIP', 'files', '.zip')
        if not source: return
        source = Path(xbmcvfs.translatePath(source))
        incoming = validate_archive(source)
        output = unique_archive(folder)
        write_archive(output, incoming)
        dialog.ok('导入完成', '备份已保存，尚未恢复按键配置。\n'+output.name)


def main():
    dialog = xbmcgui.Dialog()
    keymaps, folder = paths()
    choice = dialog.select('遥控器配置文件管理', ['备份当前遥控器配置文件', '恢复遥控器配置文件',
                           '删除遥控器配置备份文件', '导入/导出遥控器配置备份文件'])
    try:
        if choice == 0:
            output = backup_config(keymaps, folder)
            dialog.ok('备份完成', str(output))
        elif choice == 1:
            archive = choose_backup(dialog, folder, '选择要恢复的备份')
            if archive is None: return
            def confirm(name, incoming_count, old_count):
                effect = ('快照为空，将清除当前 {} 个按键 XML。'.format(old_count) if not incoming_count else
                          '将用 {} 个 XML 替换当前 {} 个按键 XML。'.format(incoming_count,old_count))
                return dialog.yesno('确认恢复按键配置', '{}\n{}\n恢复前会另存当前文件；其他设置不变。'.format(name,effect),
                                    nolabel='取消', yeslabel='恢复')
            rollback = restore_config(keymaps, folder, archive, confirm)
            if rollback is not None:
                xbmc.executebuiltin('Action(reloadkeymaps)')
                dialog.ok('恢复完成', '按键文件已校验并重新载入。\n恢复前备份：'+rollback.name)
        elif choice == 2:
            # Preserve the historical single/all deletion choices, with explicit
            # confirmation for either and only enumerated backup ZIP files.
            items = backups(folder)
            if not items: dialog.ok('删除备份','未找到备份文件。'); return
            selected = dialog.select('选择要删除的备份', ['删除全部备份']+[p.name for p in items])
            if not 0 <= selected <= len(items): return
            targets = items if selected == 0 else [items[selected-1]]
            if not dialog.yesno('确认删除备份', '删除 {} 个备份 ZIP？当前按键配置不变。'.format(len(targets)),
                                nolabel='取消',yeslabel='删除'): return
            for target in targets: target.unlink()
            dialog.ok('删除完成','已删除 {} 个备份。'.format(len(targets)))
        elif choice == 3:
            import_export(dialog, folder)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, ET.ParseError) as error:
        xbmc.log('YoPlayer keymap operation failed: {}'.format(type(error).__name__), xbmc.LOGERROR)
        dialog.ok('操作未完成', str(error))


if __name__ == '__main__':
    main()
