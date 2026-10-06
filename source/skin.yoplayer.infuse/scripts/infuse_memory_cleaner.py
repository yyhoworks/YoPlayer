"""Capability-checked cleaning with truthful step results; no forced fallback."""
import subprocess

import xbmcgui


class MemoryCleaner:
    def __init__(self):
        self.dialog = xbmcgui.Dialog()

    def get_memory_info(self):
        try:
            with open('/proc/meminfo') as f:
                return {k: int(v.split()[0]) for k, v in
                        (line.split(':', 1) for line in f if ':' in line)}
        except (OSError, ValueError):
            return None

    def sync(self):
        try:
            subprocess.run(['sync'], check=True, timeout=15, capture_output=True)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def write_kernel(self, name, value):
        try:
            with open('/proc/sys/vm/' + name, 'w') as f:
                f.write(str(value) + '\n')
            return True
        except OSError:
            return False

    def clean_swap(self):
        try:
            with open('/proc/swaps') as f:
                devices = [line.split()[0] for line in list(f)[1:] if line.strip()]
            for device in devices:
                subprocess.run(['swapoff', device], check=True, timeout=30, capture_output=True)
                subprocess.run(['swapon', device], check=True, timeout=30, capture_output=True)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def perform_cleanup(self, clean_swap=False, compact=False, show_dialog=True):
        from infuse_device import capabilities
        if not capabilities()['clean']:
            if show_dialog:
                self.dialog.ok('内存清理不可用', '当前设备不支持此操作，或没有内核缓存写入权限。')
            return False
        before = self.get_memory_info()
        progress = xbmcgui.DialogProgress() if show_dialog else None
        results = []
        try:
            if progress:
                progress.create('内存清理', '正在同步文件系统')
            synced = self.sync()
            results.append(('文件系统同步', synced))
            if not synced or (progress and progress.iscanceled()):
                results.append(('内核缓存清理', False))
            else:
                if progress:
                    progress.update(40, '正在清理内核缓存')
                results.append(('内核缓存清理', self.write_kernel('drop_caches', 3)))
                if clean_swap:
                    results.append(('交换分区重置', self.clean_swap()))
                if compact:
                    results.append(('内存规整', self.write_kernel('compact_memory', 1)))
        finally:
            if progress:
                progress.close()
        success = bool(results) and all(ok for _, ok in results)
        after = self.get_memory_info()
        text = '\n'.join('{}：{}'.format(name, '成功' if ok else '未完成') for name, ok in results)
        if before and after and 'MemAvailable' in before and 'MemAvailable' in after:
            delta = (after['MemAvailable'] - before['MemAvailable']) / 1024
            text += '\n\n可用内存变化：{:+.1f} MB（不作为操作成功依据）'.format(delta)
        text += '\n\n未清理缩略图缓存。'
        if not success:
            text += '\n请检查设备权限或稍后重试。'
        if show_dialog:
            self.dialog.ok('清理完成' if success else '清理未完成', text)
        return success
