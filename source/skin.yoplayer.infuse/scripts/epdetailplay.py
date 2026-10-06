import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import re
import os
import time
import hashlib
import sys

SCRIPT_NAME = "Resume_Point_Extractor"
COMMON_VIDEO_FORMATS = {"MKV", "MP4", "TS", "M2TS", "AVI", "FLV", "WMV", "MOV", "MPG", "MPEG", "VOB", "ISO"}  # 保留所有格式，不限制
CONTEXTMENU_TIMEOUT = 5  # 等待上下文菜单出现的最长时间（秒）

class ResumeExtractor:
    def __init__(self):
        self.current_file_path = xbmc.getInfoLabel("ListItem.FilenameAndPath").strip()
        self.is_resumable = xbmc.getCondVisibility("ListItem.IsResumable")
        self.video_db_path = self._find_latest_video_db()
        self.resume_time = None
        self.monitor = xbmc.Monitor()  # 用于监控程序退出

    def log(self, message):
        xbmc.log(f"[{SCRIPT_NAME}] {message}", level=xbmc.LOGINFO)

    def _find_latest_video_db(self):
        """查找最新的视频数据库"""
        db_dir = xbmcvfs.translatePath("special://database/")
        if not xbmcvfs.exists(db_dir):
            self.log(f"数据库目录不存在: {db_dir}")
            return None

        db_files = []
        _, files = xbmcvfs.listdir(db_dir)
        for filename in files:
            if filename.startswith("MyVideos") and filename.endswith(".db"):
                try:
                    version = int(filename[8:-3])
                    db_files.append((version, os.path.join(db_dir, filename)))
                except (ValueError, IndexError):
                    continue

        if not db_files:
            self.log("未找到MyVideos系列数据库")
            return None

        db_files.sort(reverse=True, key=lambda x: x[0])
        latest_db = db_files[0][1]
        self.log(f"找到最新视频数据库: {latest_db}")
        return latest_db

    def _get_file_id(self):
        """获取当前文件的数据库ID"""
        if not self.video_db_path or not self.current_file_path:
            return None

        # 标准化文件路径
        normalized_path = self.current_file_path.replace(os.sep, '/')
        filename = os.path.basename(normalized_path)

        try:
            conn = sqlite3.connect(self.video_db_path)
            cursor = conn.cursor()

            # 精确匹配文件名
            cursor.execute("SELECT idFile FROM files WHERE strFilename = ?", (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.log(f"找到文件ID: {result[0]} (文件: {filename})")
                return result[0]
            else:
                self.log(f"未找到匹配的文件ID (文件: {filename})")
                return None
        except Exception as e:
            self.log(f"查询文件ID失败: {str(e)}")
            return None

    def _get_resume_point(self, file_id):
        """从数据库获取续播点"""
        if not self.video_db_path or not file_id:
            return None

        try:
            conn = sqlite3.connect(self.video_db_path)
            cursor = conn.cursor()

            # 查询type=1（播放进度）的续播点
            cursor.execute("""
                SELECT timeInSeconds FROM bookmark 
                WHERE idFile = ? AND timeInSeconds IS NOT NULL AND type = 1
                ORDER BY timeInSeconds DESC LIMIT 1
            """, (file_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                resume_time = round(float(result[0]))
                self.log(f"提取到续播点: {resume_time} 秒")
                return resume_time
            else:
                self.log("未找到有效续播点")
                return None
        except Exception as e:
            self.log(f"查询续播点失败: {str(e)}")
            return None

    def _wait_for_contextmenu(self):
        """等待上下文菜单出现，超时返回False"""
        start_time = time.time()
        self.log(f"开始等待上下文菜单出现（最长{CONTEXTMENU_TIMEOUT}秒）")
        
        while time.time() - start_time < CONTEXTMENU_TIMEOUT:
            # 检查是否需要退出程序
            if self.monitor.abortRequested():
                self.log("程序请求退出，停止等待上下文菜单")
                return False
            
            # 检查上下文菜单是否出现（匹配常见的上下文菜单窗口标识）
            if xbmc.getCondVisibility("Window.IsVisible(contextmenu)") or \
               xbmc.getCondVisibility("Window.IsVisible(DialogContextMenu)") or \
               xbmc.getCondVisibility("Window.IsVisible(DialogContextMenu.xml)"):
                self.log("上下文菜单已呼出")
                return True
            
            time.sleep(0.1)  # 每0.1秒检查一次
        
        self.log(f"等待上下文菜单超时（{CONTEXTMENU_TIMEOUT}秒内未出现）")
        return False

    def _show_resume_menu(self):
        """显示续播选择菜单，按选择执行对应逻辑"""
        # 格式化续播时间为HH:MM:SS
        resume_time_str = time.strftime('%H:%M:%S', time.gmtime(self.resume_time)) if self.resume_time else "上次进度"
        
        dialog = xbmcgui.Dialog()
        choices = [
            f"从 {resume_time_str} 播放",
            "从头播放"
        ]
        choice = dialog.contextmenu(choices)

        if choice == 0:
            # 从续播点播放：关闭所有窗口 → 呼出上下文菜单 → 点击id=1001
            self.log("用户选择: 从续播点播放")
            
            # 关闭所有窗口
            self.log("执行关闭所有窗口...")
            xbmc.executebuiltin("Dialog.Close(all)")
            time.sleep(0.4)  # 等待窗口关闭完成
            
            # 呼出上下文菜单
            self.log("呼出上下文菜单...")
            xbmc.executebuiltin("Action(ContextMenu)")
            
            # 等待上下文菜单出现后点击id=1001
            if self._wait_for_contextmenu():
                self.log("执行点击上下文菜单id=1001（续播选项）")
                xbmc.executebuiltin("SendClick(1001)")
            else:
                self.log("上下文菜单未出现，无法执行续播操作")

        elif choice == 1:
            # 从头播放：关闭所有窗口 → 呼出上下文菜单 → 点击id=1002
            self.log("用户选择: 从头播放")
            
            # 关闭所有窗口
            self.log("执行关闭所有窗口...")
            xbmc.executebuiltin("Dialog.Close(all)")
            time.sleep(0.4)  # 等待窗口关闭完成
            
            # 呼出上下文菜单
            self.log("呼出上下文菜单...")
            xbmc.executebuiltin("Action(ContextMenu)")
            
            # 等待上下文菜单出现后点击id=1002
            if self._wait_for_contextmenu():
                self.log("执行点击上下文菜单id=1002（从头播放选项）")
                xbmc.executebuiltin("SendClick(1002)")
            else:
                self.log("上下文菜单未出现，无法执行从头播放操作")
        else:
            self.log("用户取消了选择")

    def run(self):
        self.log("=" * 50)
        self.log("脚本开始运行")
        self.log(f"当前文件路径: {self.current_file_path}")
        self.log(f"是否可续播: {self.is_resumable}")
        self.log("=" * 50)

        if not self.current_file_path:
            self.log("错误: 未获取到文件路径")
            return

        # 情况1: 可续播，提取续播点并显示菜单
        if self.is_resumable:
            file_id = self._get_file_id()
            if file_id:
                self.resume_time = self._get_resume_point(file_id)
            
            # 显示菜单，按选择执行对应操作
            self._show_resume_menu()
        
        # 情况2: 不可续播，直接执行 → 关闭所有窗口 → 呼出上下文菜单 → 点击id=1001
        else:
            self.log("文件不可续播，执行指定流程：关闭窗口→呼出菜单→点击id=1001")
            
            # 关闭所有窗口
            self.log("执行关闭所有窗口...")
            xbmc.executebuiltin("Dialog.Close(all)")
            time.sleep(0.4)  # 等待窗口关闭完成
            
            # 呼出上下文菜单
            self.log("呼出上下文菜单...")
            xbmc.executebuiltin("Action(ContextMenu)")
            
            # 等待上下文菜单出现后点击id=1001
            if self._wait_for_contextmenu():
                self.log("执行点击上下文菜单id=1001（指定选项）")
                xbmc.executebuiltin("SendClick(1001)")
            else:
                self.log("上下文菜单未出现，无法执行指定操作")

        self.log("脚本运行完成")

if __name__ == "__main__":
    extractor = ResumeExtractor()
    extractor.run()