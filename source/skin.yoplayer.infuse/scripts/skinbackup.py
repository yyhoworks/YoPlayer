import os
import shutil
import time
import traceback
import zipfile
import re
import xbmc
import xbmcgui
import xbmcvfs

# --- 配置 ---
SKIN_NAME = xbmc.getSkinDir()
USERDATA_PATH = os.path.normpath(xbmcvfs.translatePath('special://userdata/'))
SKIN_DATA_PATH = os.path.join(USERDATA_PATH, 'addon_data', SKIN_NAME)
SETTINGS_FILE = os.path.join(SKIN_DATA_PATH, 'settings.xml')
BACKUP_PREFIX = "skinsettings-"
BACKUP_SUFFIX = ".xml"
LOG_TAG = "[SkinBackup]"

# 导入/导出相关配置
EXPORT_ROOT = "/storage/backup"  # 导出根目录
IMPORT_TEMP_DIR = "/storage/backup/temp_import"  # 导入临时目录
AUTOSTART_FILE = "/storage/.config/autostart.sh"  # autostart.sh路径
RESTORE_MARKER = os.path.join(SKIN_DATA_PATH, "skin_restore")  # 恢复标记文件
REBOOT_SCRIPT = "special://skin/scripts/rebootoff.py"  # 重启脚本路径

# 路径匹配模式（匹配所有图片文件路径）
PATH_PATTERNS = [
    # 匹配 Linux/Unix 风格路径 (e.g., /storage/path/to/image.png)
    re.compile(r'(/[^"\']+\.(?:png|jpg|jpeg|gif|bmp))'),
    # 匹配 Windows 风格路径 (e.g., D:\path\to\image.png)
    re.compile(r'([A-Za-z]:\\[^"\']+\.(?:png|jpg|jpeg|gif|bmp))'),
]

def show_dialog(message, title="皮肤设置备份与恢复"):
    """显示精简弹窗"""
    dialog = xbmcgui.Dialog()
    dialog.ok(title, message)

def backup_skin_settings():
    """备份当前皮肤设置"""
    try:
        if not os.path.exists(SKIN_DATA_PATH):
            os.makedirs(SKIN_DATA_PATH)
            xbmc.log(f"{LOG_TAG} 创建皮肤目录：{SKIN_DATA_PATH}", xbmc.LOGINFO)
        
        if not os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<settings>\n</settings>')
            xbmc.log(f"{LOG_TAG} 创建空设置文件：{SETTINGS_FILE}", xbmc.LOGWARNING)
        
        timestamp = time.strftime("%Y%m%d%H%M%S")
        backup_filename = f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}"
        backup_path = os.path.join(SKIN_DATA_PATH, backup_filename)
        
        shutil.copy2(SETTINGS_FILE, backup_path)
        show_dialog(f"备份成功\n文件：{backup_filename}")
        xbmc.log(f"{LOG_TAG} 备份完成：{backup_path}", xbmc.LOGINFO)
        
    except Exception as e:
        show_dialog(f"备份失败\n错误：{str(e)}", "备份失败")
        xbmc.log(f"{LOG_TAG} 备份异常：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)

def get_backup_files():
    """获取所有备份文件（按时间从新到旧排序）"""
    xbmc.log(f"{LOG_TAG} [DEBUG] 进入 get_backup_files()")
    xbmc.log(f"{LOG_TAG} [DEBUG] 扫描目录: {SKIN_DATA_PATH}")
    backup_files = []
    try:
        if not os.path.isdir(SKIN_DATA_PATH):
            xbmc.log(f"{LOG_TAG} [DEBUG] 目录不存在: {SKIN_DATA_PATH}", xbmc.LOGWARNING)
            return backup_files
        
        all_items = os.listdir(SKIN_DATA_PATH)
        xbmc.log(f"{LOG_TAG} [DEBUG] 目录下找到 {len(all_items)} 个项目", xbmc.LOGINFO)

        for item in all_items:
            item_path = os.path.join(SKIN_DATA_PATH, item)
            if os.path.isfile(item_path) and item.startswith(BACKUP_PREFIX) and item.endswith(BACKUP_SUFFIX):
                xbmc.log(f"{LOG_TAG} [DEBUG] 发现备份文件: {item}", xbmc.LOGINFO)
                timestamp_str = item.replace(BACKUP_PREFIX, "").replace(BACKUP_SUFFIX, "")
                try:
                    timestamp = time.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    backup_files.append((item, timestamp))
                except ValueError:
                    xbmc.log(f"{LOG_TAG} [DEBUG] 无效时间戳格式，跳过文件: {item}", xbmc.LOGWARNING)
        
        if backup_files:
            backup_files.sort(key=lambda x: x[1], reverse=True)
            sorted_filenames = [file for file, _ in backup_files]
            xbmc.log(f"{LOG_TAG} [DEBUG] 排序后的备份文件: {sorted_filenames}", xbmc.LOGINFO)
            return sorted_filenames
        else:
            xbmc.log(f"{LOG_TAG} [DEBUG] 未找到有效备份文件", xbmc.LOGWARNING)
            return []
            
    except Exception as e:
        xbmc.log(f"{LOG_TAG} [DEBUG] 搜索备份文件时发生严重错误: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return []

def update_autostart(backup_filename):
    """更新autostart.sh，添加/修改恢复逻辑"""
    try:
        # 提取备份时间戳
        backup_timestamp = backup_filename.replace(BACKUP_PREFIX, "").replace(BACKUP_SUFFIX, "")
        # 构建要添加/替换的代码块
        target_code = f'''if [ -f "{RESTORE_MARKER}" ]; then
    rm -f "{SETTINGS_FILE}"
    cp "{os.path.join(SKIN_DATA_PATH, backup_filename)}" "{SETTINGS_FILE}"
    rm "{RESTORE_MARKER}"
fi'''
        
        # 读取现有autostart.sh内容
        if os.path.exists(AUTOSTART_FILE):
            with open(AUTOSTART_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ""
        
        # 检查是否已存在恢复逻辑（匹配标记文件路径）
        marker_pattern = re.escape(f'[ -f "{RESTORE_MARKER}" ]')
        if re.search(marker_pattern, content):
            # 已存在，替换整个代码块
            block_pattern = re.compile(
                r'if ' + marker_pattern + r'; then\n.*?fi',
                re.DOTALL  # 让.匹配换行符
            )
            new_content = block_pattern.sub(target_code, content)
            xbmc.log(f"{LOG_TAG} 已更新autostart.sh中的恢复逻辑", xbmc.LOGINFO)
        else:
            # 不存在，添加到文件末尾（确保换行）
            if content and not content.endswith('\n'):
                content += '\n'
            new_content = content + '\n' + target_code + '\n'
            xbmc.log(f"{LOG_TAG} 已添加恢复逻辑到autostart.sh", xbmc.LOGINFO)
        
        # 写入更新后的内容
        with open(AUTOSTART_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 设置可执行权限
        os.chmod(AUTOSTART_FILE, 0o755)
        xbmc.log(f"{LOG_TAG} 已设置autostart.sh可执行权限", xbmc.LOGINFO)
        
        return True
        
    except Exception as e:
        xbmc.log(f"{LOG_TAG} 更新autostart.sh失败：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return False

def restore_skin_settings(from_import=False):
    """恢复皮肤设置（仅配置autostart.sh，重启后生效）"""
    try:
        backup_files = get_backup_files()
        if not backup_files:
            show_dialog("未找到备份文件", "恢复提示")
            return
        
        dialog = xbmcgui.Dialog()
        choice = dialog.select("选择备份（最新在前）", backup_files)
        if choice == -1:
            if not from_import:
                show_dialog("恢复已取消", "恢复提示")
            return
        
        selected_file = backup_files[choice]
        # 确认弹窗提示重启后生效
        if not dialog.yesno("确认恢复", f"确定恢复备份：{selected_file}？\n\n恢复将在重启设备后自动生效。"):
            if not from_import:
                show_dialog("恢复已取消", "恢复提示")
            return
        
        # 1. 创建恢复标记文件（触发autostart.sh中的恢复逻辑）
        with open(RESTORE_MARKER, 'w') as f:
            f.write("skin restore marker")
        xbmc.log(f"{LOG_TAG} 已创建恢复标记文件：{RESTORE_MARKER}", xbmc.LOGINFO)
        
        # 2. 更新autostart.sh（核心逻辑，仅保留此步骤）
        if update_autostart(selected_file):
            # 询问用户是否现在重启
            if dialog.yesno("恢复配置成功", f"已为您配置重启自动恢复：\n- 备份文件：{selected_file}\n\n是否现在重启？"):
                # 执行重启脚本
                xbmc.log(f"{LOG_TAG} 用户选择立即重启，执行脚本：{REBOOT_SCRIPT}", xbmc.LOGINFO)
                xbmc.executebuiltin(f'RunScript({REBOOT_SCRIPT},reboot)')
            else:
                # 提示下次重启生效
                show_dialog("皮肤设置将在下次重启后生效！", "提示")
                xbmc.log(f"{LOG_TAG} 用户选择不立即重启，设置下次重启生效", xbmc.LOGINFO)
        else:
            # 配置失败提示
            show_dialog(
                f"恢复配置失败！\n\n无法更新autostart.sh启动脚本，\n请检查日志（{LOG_TAG}）获取详细错误信息。",
                "恢复配置失败"
            )
        
    except Exception as e:
        show_dialog(f"恢复操作异常\n错误：{str(e)}", "恢复失败")
        xbmc.log(f"{LOG_TAG} 恢复操作异常：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)

def delete_backup_files():
    """删除皮肤备份文件"""
    try:
        backup_files = get_backup_files()
        if not backup_files:
            show_dialog("未找到备份文件", "删除提示")
            return
        
        delete_options = ["删除所有备份"] + backup_files
        dialog = xbmcgui.Dialog()
        choice = dialog.select("选择要删除的备份（最新在前）", delete_options)
        
        if choice == -1:
            show_dialog("删除已取消", "删除提示")
            return
        
        if choice == 0:
            if not dialog.yesno("警告", "确定要删除所有备份文件吗？\n此操作不可恢复！"):
                show_dialog("删除已取消", "删除提示")
                return
            
            deleted_count = 0
            for backup_file in backup_files:
                file_path = os.path.join(SKIN_DATA_PATH, backup_file)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    xbmc.log(f"{LOG_TAG} 删除备份：{file_path}", xbmc.LOGINFO)
            
            show_dialog(f"删除完成\n共删除 {deleted_count} 个备份文件", "删除成功")
        
        else:
            selected_file = backup_files[choice - 1]
            if not dialog.yesno("确认删除", f"确定删除\n{selected_file}?"):
                show_dialog("删除已取消", "删除提示")
                return
            
            file_path = os.path.join(SKIN_DATA_PATH, selected_file)
            if os.path.exists(file_path):
                os.remove(file_path)
                xbmc.log(f"{LOG_TAG} 删除备份：{file_path}", xbmc.LOGINFO)
                show_dialog(f"删除成功\n文件：{selected_file}", "删除成功")
        
    except Exception as e:
        show_dialog(f"删除失败\n错误：{str(e)}", "删除失败")
        xbmc.log(f"{LOG_TAG} 删除异常：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)

def export_backup_files():
    """导出皮肤备份文件（包含关联的图片文件）"""
    try:
        backup_files = get_backup_files()
        if not backup_files:
            show_dialog("未找到备份文件", "导出提示")
            return
        
        if not os.path.exists(EXPORT_ROOT):
            os.makedirs(EXPORT_ROOT)
            xbmc.log(f"{LOG_TAG} 创建导出根目录：{EXPORT_ROOT}", xbmc.LOGINFO)
        
        export_temp_dir = os.path.join(EXPORT_ROOT, "temp_export")
        if os.path.exists(export_temp_dir):
            shutil.rmtree(export_temp_dir)
        os.makedirs(export_temp_dir)
        xbmc.log(f"{LOG_TAG} 创建临时导出目录：{export_temp_dir}", xbmc.LOGINFO)
        
        total_processed = 0
        total_copied = 0
        
        for backup_file in backup_files:
            total_processed += 1
            backup_path = os.path.join(SKIN_DATA_PATH, backup_file)
            backup_dir_name = backup_file.replace(BACKUP_SUFFIX, "")
            backup_temp_dir = os.path.join(export_temp_dir, backup_dir_name)
            os.makedirs(backup_temp_dir)
            
            shutil.copy2(backup_path, backup_temp_dir)
            xbmc.log(f"{LOG_TAG} 复制备份文件：{backup_path} → {backup_temp_dir}", xbmc.LOGINFO)
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            matched_paths = []
            for pattern in PATH_PATTERNS:
                matches = pattern.findall(content)
                matched_paths.extend(matches)
            
            unique_paths = list(set(matched_paths))
            
            for file_path in unique_paths:
                file_path = file_path.replace('\\\\', '\\').replace('\\/', '/')
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(backup_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    total_copied += 1
                    xbmc.log(f"{LOG_TAG} 复制关联文件：{file_path} → {dest_path}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"{LOG_TAG} 关联文件不存在，跳过：{file_path}", xbmc.LOGWARNING)
        
        zip_timestamp = time.strftime("%Y%m%d%H%M%S")
        zip_filename = f"{BACKUP_PREFIX}{zip_timestamp}.zip"
        zip_path = os.path.join(EXPORT_ROOT, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(export_temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, export_temp_dir)
                    zipf.write(file_path, arcname)
                    xbmc.log(f"{LOG_TAG} 添加到ZIP：{file_path} → {arcname}", xbmc.LOGINFO)
        
        shutil.rmtree(export_temp_dir)
        xbmc.log(f"{LOG_TAG} 清理临时目录：{export_temp_dir}", xbmc.LOGINFO)
        
        show_dialog(
            f"导出成功！\n\n处理备份数：{total_processed}\n复制关联文件数：{total_copied}\nZIP文件：{zip_filename}\n路径：{EXPORT_ROOT}",
            "导出成功"
        )
        xbmc.log(f"{LOG_TAG} 导出完成：{zip_path}", xbmc.LOGINFO)
        
    except Exception as e:
        show_dialog(f"导出失败\n错误：{str(e)}", "导出失败")
        xbmc.log(f"{LOG_TAG} 导出异常：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)

def import_backup_files():
    """导入皮肤备份文件（包含关联的图片文件）"""
    try:
        dialog = xbmcgui.Dialog()
        # 默认打开路径为 /storage/backup/
        zip_path = dialog.browseSingle(
            type=1,
            heading="选择要导入的备份ZIP文件",
            shares="local",
            mask="*.zip",
            useThumbs=False,
            treatAsFolder=False,
            defaultt="/storage/backup/"  # 默认打开路径
        )
        
        if not zip_path:
            show_dialog("未选择文件，导入已取消", "导入提示")
            return
        
        if not os.path.exists(zip_path):
            show_dialog("选择的文件不存在！", "导入失败")
            xbmc.log(f"{LOG_TAG} 导入文件不存在：{zip_path}", xbmc.LOGERROR)
            return
        
        if os.path.exists(IMPORT_TEMP_DIR):
            shutil.rmtree(IMPORT_TEMP_DIR)
        os.makedirs(IMPORT_TEMP_DIR)
        xbmc.log(f"{LOG_TAG} 创建临时导入目录：{IMPORT_TEMP_DIR}", xbmc.LOGINFO)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(IMPORT_TEMP_DIR)
            xbmc.log(f"{LOG_TAG} 解压ZIP文件：{zip_path} → {IMPORT_TEMP_DIR}", xbmc.LOGINFO)
        
        total_processed = 0
        total_restored = 0
        
        for root, dirs, files in os.walk(IMPORT_TEMP_DIR):
            for file in files:
                if file.startswith(BACKUP_PREFIX) and file.endswith(BACKUP_SUFFIX):
                    total_processed += 1
                    backup_file_path = os.path.join(root, file)
                    backup_filename = os.path.basename(backup_file_path)
                    
                    with open(backup_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    matched_paths = []
                    for pattern in PATH_PATTERNS:
                        matches = pattern.findall(content)
                        matched_paths.extend(matches)
                    
                    unique_paths = list(set(matched_paths))
                    
                    for target_path in unique_paths:
                        target_path = target_path.replace('\\\\', '\\').replace('\\/', '/')
                        file_name = os.path.basename(target_path)
                        source_path = os.path.join(root, file_name)
                        
                        if os.path.exists(source_path):
                            target_dir = os.path.dirname(target_path)
                            if not os.path.exists(target_dir):
                                os.makedirs(target_dir)
                                xbmc.log(f"{LOG_TAG} 创建目标目录：{target_dir}", xbmc.LOGINFO)
                            
                            shutil.move(source_path, target_path)
                            total_restored += 1
                            xbmc.log(f"{LOG_TAG} 恢复关联文件：{source_path} → {target_path}", xbmc.LOGINFO)
                        else:
                            xbmc.log(f"{LOG_TAG} 关联文件不存在于ZIP中，跳过：{source_path}", xbmc.LOGWARNING)
                    
                    dest_backup_path = os.path.join(SKIN_DATA_PATH, backup_filename)
                    shutil.move(backup_file_path, dest_backup_path)
                    xbmc.log(f"{LOG_TAG} 恢复备份文件：{backup_file_path} → {dest_backup_path}", xbmc.LOGINFO)
        
        shutil.rmtree(IMPORT_TEMP_DIR)
        xbmc.log(f"{LOG_TAG} 清理临时导入目录：{IMPORT_TEMP_DIR}", xbmc.LOGINFO)
        
        # 导入成功后询问是否恢复
        show_dialog(
            f"导入成功！\n\n处理备份数：{total_processed}\n恢复关联文件数：{total_restored}\n备份文件已恢复到：\n{SKIN_DATA_PATH}",
            "导入成功"
        )
        
        if dialog.yesno("恢复备份", "导入成功，是否立即配置重启恢复备份？"):
            restore_skin_settings(from_import=True)
        
    except Exception as e:
        show_dialog(f"导入失败\n错误：{str(e)}", "导入失败")
        xbmc.log(f"{LOG_TAG} 导入异常：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)

def import_export_backup():
    """导入/导出功能入口"""
    try:
        dialog = xbmcgui.Dialog()
        options = [
            "导入皮肤备份",
            "导出皮肤备份",
            "返回上一级"
        ]
        choice = dialog.select("导入/导出皮肤备份", options)
        
        if choice == 0:
            import_backup_files()
        elif choice == 1:
            export_backup_files()
        elif choice == 2 or choice == -1:
            return
        
    except Exception as e:
        show_dialog(f"操作失败\n错误：{str(e)}", "操作失败")
        xbmc.log(f"{LOG_TAG} 导入/导出异常：{str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)

def main():
    """主函数"""
    dialog = xbmcgui.Dialog()
    # 移除退出选项，最后一个选项是导入/导出
    options = [
        "备份当前皮肤设置",
        "恢复皮肤设置（重启生效）",  # 选项名称添加说明
        "删除皮肤备份文件",
        "导入/导出皮肤备份文件"
    ]
    choice = dialog.select("皮肤设置备份与恢复", options)
    
    if choice == 0:
        backup_skin_settings()
    elif choice == 1:
        restore_skin_settings()
    elif choice == 2:
        delete_backup_files()
    elif choice == 3:
        import_export_backup()
    # 取消时直接退出，不显示提示

if __name__ == "__main__":
    main()