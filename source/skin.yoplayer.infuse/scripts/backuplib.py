import xbmc
import xbmcgui
import xbmcvfs
import os
import shutil
from datetime import datetime

class MediaLibraryBackup:
    def __init__(self):
        # 获取Kodi路径 - 使用xbmcvfs.translatePath替代xbmc.translatePath
        self.userdata_path = xbmcvfs.translatePath('special://userdata/')
        self.database_path = os.path.join(self.userdata_path, 'Database', 'MyVideos131.db')
        self.backup_path = xbmcvfs.translatePath('special://home/') + 'storage/backup/'
        
        # 确保备份目录存在
        if not xbmcvfs.exists(self.backup_path):
            xbmcvfs.mkdir(self.backup_path)

    def get_backup_files(self):
        """获取备份目录下的所有媒体库备份文件"""
        backup_files = []
        if xbmcvfs.exists(self.backup_path):
            directory_list = xbmcvfs.listdir(self.backup_path)
            files = directory_list[1]  # [dirs, files]
            
            for file in files:
                if file.startswith('媒体库-') and file.endswith('.db'):
                    backup_files.append(file)
        
        return sorted(backup_files, reverse=True)  # 按时间倒序排列

    def format_datetime(self):
        """格式化当前日期时间为字符串 YYYYMMDDHHMMSS"""
        now = datetime.now()
        return now.strftime('%Y%m%d%H%M%S')

    def backup_library(self):
        """备份当前媒体库"""
        # 弹出目录选择窗口 - 修正参数顺序
        selected_path = xbmcgui.Dialog().browseSingle(
            type=3,  # 3 表示目录选择
            heading='选择备份位置',
            shares='',  # shares参数不能为空字符串，对于本地路径可以留空或设为''
            mask='',
            useThumbs=False,
            treatAsFolder=False,
            defaultt=self.backup_path
        )
        
        if not selected_path:
            return
        
        # 构建备份文件名
        timestamp = self.format_datetime()
        backup_filename = f'媒体库-{timestamp}.db'
        backup_full_path = os.path.join(selected_path, backup_filename)
        
        try:
            # 复制数据库文件
            if hasattr(shutil, 'copyfile'):
                shutil.copyfile(self.database_path, backup_full_path)
            else:
                # 如果shutil.copyfile不可用，使用xbmcvfs
                with open(self.database_path, 'rb') as src:
                    with open(backup_full_path, 'wb') as dst:
                        dst.write(src.read())
            
            # 显示成功信息
            xbmcgui.Dialog().ok('备份完成', f'媒体库已备份至:\n{backup_full_path}')
        except Exception as e:
            xbmcgui.Dialog().ok('备份失败', f'备份过程中发生错误:\n{str(e)}')

    def restore_manual_selection(self):
        """手动选择备份文件进行恢复"""
        # 弹出文件选择窗口 - 修正参数顺序
        selected_file = xbmcgui.Dialog().browseSingle(
            type=1,  # 1 表示文件选择
            heading='选择要恢复的备份文件',
            shares='',
            mask='.db',
            useThumbs=False,
            treatAsFolder=False,
            defaultt=self.backup_path
        )
        
        if not selected_file:
            return
        
        try:
            # 复制并覆盖数据库文件
            if hasattr(shutil, 'copyfile'):
                shutil.copyfile(selected_file, self.database_path)
            else:
                # 如果shutil.copyfile不可用，使用xbmcvfs
                with open(selected_file, 'rb') as src:
                    with open(self.database_path, 'wb') as dst:
                        dst.write(src.read())
            
            # 显示成功信息
            xbmcgui.Dialog().ok('恢复完成', '已恢复备份的媒体库！')
            
            # 重载皮肤并设置焦点
            xbmc.executebuiltin('ReloadSkin()')
            xbmc.sleep(500)
            xbmc.executebuiltin('SetFocus(9000)')
        except Exception as e:
            xbmcgui.Dialog().ok('恢复失败', f'恢复过程中发生错误:\n{str(e)}')

    def restore_from_list(self, filename):
        """从列表中选择的文件进行恢复"""
        source_path = os.path.join(self.backup_path, filename)
        
        try:
            # 复制并覆盖数据库文件
            if hasattr(shutil, 'copyfile'):
                shutil.copyfile(source_path, self.database_path)
            else:
                # 如果shutil.copyfile不可用，使用xbmcvfs
                with open(source_path, 'rb') as src:
                    with open(self.database_path, 'wb') as dst:
                        dst.write(src.read())
            
            # 提取时间戳用于显示
            timestamp = filename.replace('媒体库-', '').replace('.db', '')
            
            # 显示成功信息
            xbmcgui.Dialog().ok('恢复完成', f'已恢复{timestamp}备份的媒体库！')
            
            # 重载皮肤并设置焦点
            xbmc.executebuiltin('ReloadSkin()')
            xbmc.sleep(500)
            xbmc.executebuiltin('SetFocus(9000)')
        except Exception as e:
            xbmcgui.Dialog().ok('恢复失败', f'恢复过程中发生错误:\n{str(e)}')

    def delete_all_backups(self):
        """删除所有备份文件"""
        # 确认删除操作
        confirm = xbmcgui.Dialog().yesno('确认删除', '确定要删除所有备份文件吗？')
        
        if not confirm:
            return
        
        backup_files = self.get_backup_files()
        deleted_count = 0
        
        for filename in backup_files:
            file_path = os.path.join(self.backup_path, filename)
            try:
                xbmcvfs.delete(file_path)
                deleted_count += 1
            except Exception as e:
                xbmcgui.Dialog().ok('删除失败', f'删除文件 {filename} 时发生错误:\n{str(e)}')
        
        # 显示删除结果
        xbmcgui.Dialog().ok('删除完成', f'已删除 {deleted_count} 个备份文件')

    def delete_single_backup(self, filename):
        """删除单个备份文件"""
        file_path = os.path.join(self.backup_path, filename)
        
        try:
            xbmcvfs.delete(file_path)
            xbmcgui.Dialog().ok('删除成功', f'已删除备份文件:\n{filename}')
        except Exception as e:
            xbmcgui.Dialog().ok('删除失败', f'删除文件时发生错误:\n{str(e)}')

    def show_restore_options(self):
        """显示恢复选项"""
        options = ['手动选择备份文件']
        
        # 获取备份文件列表
        backup_files = self.get_backup_files()
        
        # 添加备份文件到选项列表
        for filename in backup_files:
            options.append(filename)
        
        if len(options) == 1:
            # 如果没有找到备份文件，只显示手动选择选项
            choice = xbmcgui.Dialog().select('选择恢复选项', options)
            
            if choice == 0:
                self.restore_manual_selection()
        else:
            # 显示所有选项
            choice = xbmcgui.Dialog().select('选择恢复选项', options)
            
            if choice == 0:
                # 手动选择
                self.restore_manual_selection()
            elif choice > 0:
                # 从列表中选择的文件
                self.restore_from_list(options[choice])

    def show_delete_options(self):
        """显示删除选项"""
        options = ['删除所有备份文件']
        
        # 获取备份文件列表
        backup_files = self.get_backup_files()
        
        # 添加备份文件到选项列表
        for filename in backup_files:
            options.append(filename)
        
        if len(options) == 1:
            # 如果没有找到备份文件，提示并返回
            xbmcgui.Dialog().ok('提示', '没有找到备份文件')
            return
        
        # 显示所有选项
        choice = xbmcgui.Dialog().select('选择删除选项', options)
        
        if choice == 0:
            # 删除所有备份
            self.delete_all_backups()
            # 执行清理脚本
            xbmc.executebuiltin('RunScript(special://skin/scripts/clearlibrary.py)')
        elif choice > 0:
            # 删除单个备份
            self.delete_single_backup(options[choice])

    def run(self):
        """主运行函数"""
        while True:
            # 主菜单选项
            main_options = [
                '备份当前媒体库',
                '恢复之前备份的媒体库',
                '删除之前备份的媒体库'
            ]
            
            choice = xbmcgui.Dialog().select('媒体库管理', main_options)
            
            if choice == -1:  # 用户取消
                break
            elif choice == 0:  # 备份当前媒体库
                self.backup_library()
            elif choice == 1:  # 恢复之前备份的媒体库
                self.show_restore_options()
            elif choice == 2:  # 删除之前备份的媒体库
                self.show_delete_options()

if __name__ == '__main__':
    backup_manager = MediaLibraryBackup()
    backup_manager.run()