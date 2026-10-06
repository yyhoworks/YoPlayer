import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import re
import os
import time
import threading
import hashlib
import sys
from tempfile import gettempdir

SCRIPT_NAME = "ISO_Resume_Point_Extractor"
SCRIPT_PATH = "special://skin/scripts/resumeplay.py"
SKIN_HASH_PART1 = "24e1ffea6808546f"
SKIN_HASH_PART2 = "e033a3e943a0eddd"
COMMON_VIDEO_FORMATS = {"MKV", "MP4", "TS", "M2TS", "AVI", "FLV", "WMV", "MOV", "MPG", "MPEG", "VOB"}
WINDOW_HOME_ID = 10000
WINDOW_HOME_FILE = "Home.xml"
RESUME_TEMP_FILE = os.path.join(gettempdir(), "resume.txt")
FULLSCREEN_TIMEOUT_TICKS = 400  # 400 * 0.1s = 40s
SELECT_DIALOG_ID = 12000
SELECT_DIALOG_XML = "DialogSelect.xml"

class ISOResumeExtractor:
    def __init__(self):
        self.args = sys.argv[1:] if len(sys.argv) > 1 else []
        self.is_folder_play = "folderplay" in self.args
        
        self._skin_auth_passed = False
        self._init_skin_auth()
        
        self.info_delay = self._get_info_delay_param()
        
        self.current_filename = xbmc.getInfoLabel("ListItem.Filename").strip()
        self.current_file_path = self._get_file_path()
        self.in_video_info = self._check_video_info_window()
        self.is_iso = self._check_iso_file()
        self.is_resumable = self._check_resumable()
        self.video_db_path = self._find_latest_video_db()
        self.resume_time = None  # 初始续播点
        self.resume_time_hhmmss = ""
        self.monitor = xbmc.Monitor()  # 保留monitor对象
        self.theoretical_time = self._calc_theoretical_resume_time()
        self.theoretical_time_failed = self.theoretical_time is None
        self.seek_executed = False  # 标记seek是否已执行
        
        # 初始化临时文件
        self._init_resume_temp_file()

    def log(self, message):
        xbmc.log(f"[{SCRIPT_NAME}] {message}", level=xbmc.LOGINFO)

    # 初始化续播点临时文件
    def _init_resume_temp_file(self):
        try:
            if not os.path.exists(RESUME_TEMP_FILE):
                with open(RESUME_TEMP_FILE, 'w') as f:
                    f.write("0")
                self.log(f"创建临时文件: {RESUME_TEMP_FILE}")
            else:
                self.log(f"临时文件已存在: {RESUME_TEMP_FILE}")
        except Exception as e:
            self.log(f"初始化临时文件失败: {str(e)}")

    # 写入续播点到临时文件
    def _write_resume_to_temp(self, value):
        try:
            with open(RESUME_TEMP_FILE, 'w') as f:
                f.write(str(value))
            self.log(f"临时文件更新续播点: {value} 秒")
        except Exception as e:
            self.log(f"写入临时文件失败: {str(e)}")

    # 从临时文件读取续播点
    def _read_resume_from_temp(self):
        try:
            if not os.path.exists(RESUME_TEMP_FILE):
                self.log("临时文件不存在，返回0")
                return 0
            with open(RESUME_TEMP_FILE, 'r') as f:
                content = f.read().strip()
                return int(content) if content.isdigit() else 0
        except Exception as e:
            self.log(f"读取临时文件失败: {str(e)}")
            return 0

    def _get_skin_config(self):
        try:
            skin_path = xbmcvfs.translatePath("special://skin/")
            addon_xml = os.path.join(skin_path, "addon.xml")
            if not xbmcvfs.exists(addon_xml):
                self.log("Skin config file missing")
                return ""
            with open(addon_xml, 'r', encoding='utf-8') as f:
                content = f.read()
            match = re.search(r'<addon\s+id="([^"]+?)"', content, re.I)
            return match.group(1).strip() if match else ""
        except Exception as e:
            self.log(f"Failed to read skin config: {str(e)}")
            return ""

    def _encode_str(self, text):
        if not text:
            return ""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _build_auth_key(self):
        return f"{SKIN_HASH_PART1}{SKIN_HASH_PART2}"

    def _init_skin_auth(self):
        skin_id = self._get_skin_config()
        current_key = self._encode_str(skin_id)
        target_key = self._build_auth_key()
        if current_key != target_key:
            self.clean_up()
            raise SystemExit()
        self._skin_auth_passed = True

    def _get_info_delay_param(self):
        try:
            param_val = xbmc.getInfoLabel("Skin.String(info_delay)").strip()
            if not param_val:
                self.log("Skin.String(info_delay) parameter does not exist or is empty")
                return ""
            self.log(f"Read Skin.String(info_delay): {param_val}")
            return param_val
        except Exception as e:
            self.log(f"Failed to read Skin.String(info_delay): {str(e)}, treated as empty value")
            return ""

    def _set_info_delay_param(self, value):
        try:
            value_str = str(value).strip()
            xbmc.executebuiltin(f'Skin.SetString(info_delay,{value_str})')
            self.log(f"Skin.String(info_delay) set to: {value_str}")
        except Exception as e:
            self.log(f"Failed to set Skin.String(info_delay): {str(e)}")

    def _set_resumeselect_param(self, value):
        try:
            value_str = str(value).strip()
            xbmc.executebuiltin(f'Skin.SetString(resumeselect,{value_str})')
            self.log(f"Skin.String(resumeselect) set to: {value_str}")
        except Exception as e:
            self.log(f"Failed to set Skin.String(resumeselect): {str(e)}")

    def _check_video_info_window(self):
        is_info_window = xbmc.getCondVisibility("Window.IsVisible(MovieInformation)") or \
                        xbmc.getCondVisibility("Window.IsVisible(DialogVideoInfo.xml)")
        self.log(f"Is in video info window: {is_info_window}")
        return is_info_window

    def _check_iso_file(self):
        is_match = re.search(r'\.iso$', self.current_filename, re.IGNORECASE) is not None
        self.log(f"ISO file check result: {is_match} (File: {self.current_filename})")
        return is_match

    def _check_resumable(self):
        is_resumable = xbmc.getCondVisibility("ListItem.IsResumable")
        self.log(f"File resumable check result: {is_resumable}")
        return is_resumable

    def _find_latest_video_db(self):
        db_dir = xbmcvfs.translatePath("special://database/")
        if not xbmcvfs.exists(db_dir):
            self.log(f"Error: Database directory does not exist - {db_dir}")
            return None

        db_files = []
        _, files = xbmcvfs.listdir(db_dir)
        for filename in files:
            if filename.startswith("MyVideos") and filename.endswith(".db"):
                try:
                    version = int(filename[8:-3])
                    db_files.append((version, os.path.join(db_dir, filename)))
                except (ValueError, IndexError):
                    self.log(f"Skipping invalid database file: {filename}")
                    continue

        if not db_files:
            self.log("Error: No MyVideos series database found")
            return None

        db_files.sort(reverse=True, key=lambda x: x[0])
        latest_db = db_files[0][1]
        self.log(f"Found latest video database: {latest_db}")
        return latest_db

    def _time_str_to_seconds(self, time_str):
        if not time_str:
            self.log("Error: Time string is empty, cannot convert")
            return None
        try:
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 2:
                parts = [0] + parts
            elif len(parts) != 3:
                self.log(f"Error: Invalid time format (need HH:MM:SS or MM:SS) - {time_str}")
                return None

            hours, minutes, seconds = parts
            if minutes >= 60 or seconds >= 60:
                self.log(f"Error: Invalid time value (minutes/seconds cannot be ≥60) - {time_str}")
                return None
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            self.log(f"Time conversion: {time_str} → {total_seconds} seconds")
            return total_seconds
        except (ValueError, AttributeError) as e:
            self.log(f"Time conversion failed: {str(e)} (Input: {time_str})")
            return None

    def _get_file_ids(self):
        if not self.video_db_path or not xbmcvfs.exists(self.video_db_path):
            self.log("Error: Invalid database path")
            return []

        normalized_filename = self.current_filename.replace(os.sep, '/')
        file_ids = []

        try:
            conn = sqlite3.connect(self.video_db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT idFile FROM files WHERE strFilename = ?", (normalized_filename,))
            results = cursor.fetchall()

            if not results:
                cursor.execute(
                    "SELECT idFile FROM files WHERE strFilename LIKE ? COLLATE NOCASE",
                    (f'%{re.escape(normalized_filename)}%',)
                )
                results = cursor.fetchall()

            file_ids = [item[0] for item in results] if results else []
            conn.close()
            self.log(f"Queried idFile list: {file_ids} (Matching file: {normalized_filename})")
        except Exception as e:
            self.log(f"Failed to query idFile: {str(e)}")

        return file_ids

    def _get_resume_points_by_file_ids(self, file_ids):
        resume_points = []
        if not self.video_db_path or not file_ids:
            self.log("Error: Invalid database path or empty idFile")
            return resume_points

        try:
            conn = sqlite3.connect(self.video_db_path)
            cursor = conn.cursor()

            for file_id in file_ids:
                cursor.execute(
                    "SELECT timeInSeconds FROM bookmark WHERE idFile = ? AND timeInSeconds IS NOT NULL AND type = 1",
                    (file_id,)
                )
                results = cursor.fetchall()
                if results:
                    for result in results:
                        if result[0] is not None:
                            resume_time = round(float(result[0]))
                            resume_points.append(resume_time)
                            self.log(f"idFile={file_id} Found type=1 resume point: {resume_time} seconds")

            conn.close()
        except Exception as e:
            self.log(f"Failed to query resume points: {str(e)}")

        return resume_points

    def _calc_theoretical_resume_time(self):
        try:
            percent_str = xbmc.getInfoLabel("ListItem.PercentPlayed").strip()
            if not percent_str or percent_str == "NaN":
                self.log(f"Error: Invalid progress - {percent_str}")
                return None
            percent_played = float(percent_str) / 100

            duration_str = xbmc.getInfoLabel("ListItem.Duration").strip()
            if not duration_str:
                self.log("Error: Video duration is empty (ListItem.Duration returned empty)")
                return None
            
            total_seconds = self._time_str_to_seconds(duration_str)
            if not total_seconds:
                return None

            theoretical_time = round(percent_played * total_seconds)
            self.log(f"Theoretical resume time: {percent_str}% × {total_seconds} seconds = {theoretical_time} seconds")
            return theoretical_time
        except (ValueError, TypeError) as e:
            self.log(f"Failed to calculate theoretical resume time: {str(e)}")
            return None

    def _select_closest_resume_point(self, resume_points):
        if len(resume_points) == 0:
            self.log("No available resume points")
            return None
        elif len(resume_points) == 1:
            selected = resume_points[0]
            self.log(f"Only 1 type=1 resume point, selected directly: {selected} seconds")
            return selected

        if self.theoretical_time_failed:
            shortest_time = min(resume_points)
            self.log(f"Theoretical resume time calculation failed, selecting shortest resume point: {shortest_time} seconds")
            return shortest_time

        if not self.theoretical_time:
            self.log("Error: Invalid theoretical resume time, cannot filter multiple resume points")
            return None

        closest_time = min(resume_points, key=lambda x: abs(x - self.theoretical_time))
        diff = abs(closest_time - self.theoretical_time)
        self.log(f"Multiple type=1 resume points filtered: Theoretical {self.theoretical_time} seconds → Selected {closest_time} seconds (Difference: {diff} seconds)")
        return closest_time

    def _handle_error(self, error_msg):
        self.log(f"Error handling: {error_msg}")
        # 错误时清空临时文件
        self._write_resume_to_temp(0)
        
        if self.in_video_info:
            self.log("In video info window, execute SendClick(8)")
            xbmc.executebuiltin('SendClick(8)')
        
        self.log("Cannot get valid resume point, exiting after 1 second")
        time.sleep(1)
        # 移除清理调用，避免提前删除monitor
        raise SystemExit()

    def wait_for_fullscreen(self):
        """
        等待全屏播放窗口出现，最长等待40秒
        期间如果检测到DialogSelect窗口，暂停计时，窗口消失后重新计时
        """
        timeout_ticks = 0
        select_dialog_visible = False
        
        self.log(f"开始等待全屏播放窗口（最长{int(FULLSCREEN_TIMEOUT_TICKS * 0.1)}秒）")
        
        while timeout_ticks < FULLSCREEN_TIMEOUT_TICKS:
            # 检查是否需要退出
            if self.monitor.abortRequested():
                self.log("程序请求退出，停止等待全屏")
                return False
            
            # 检查全屏窗口是否已出现
            if xbmc.getCondVisibility("Window.IsVisible(FullscreenVideo)"):
                self.log("全屏播放窗口已显示")
                return True
            
            # 检查DialogSelect窗口状态
            current_select_visible = xbmc.getCondVisibility(f"Window.IsVisible({SELECT_DIALOG_ID})") or \
                                    xbmc.getCondVisibility(f"Window.IsVisible({SELECT_DIALOG_XML})")
            
            if current_select_visible:
                if not select_dialog_visible:
                    select_dialog_visible = True
                    self.log(f"检测到{SELECT_DIALOG_XML}(id={SELECT_DIALOG_ID})，暂停等待计时")
            else:
                if select_dialog_visible:
                    select_dialog_visible = False
                    self.log(f"{SELECT_DIALOG_XML}(id={SELECT_DIALOG_ID})已关闭，恢复等待计时")
            
            if not current_select_visible:
                timeout_ticks += 1
                if timeout_ticks % 100 == 0:
                    elapsed_seconds = timeout_ticks * 0.1
                    self.log(f"等待全屏中... 已等待{elapsed_seconds:.1f}秒")
            
            time.sleep(0.1)
        
        self.log(f"等待全屏播放窗口超时（已等待{int(FULLSCREEN_TIMEOUT_TICKS * 0.1)}秒）")
        return False

    def _check_fullscreen_and_seek(self):
        temp_resume = self._read_resume_from_temp()
        
        if self.seek_executed or temp_resume == 0:
            self.log("Seek操作已执行或续播点已清零，跳过")
            return

        if self.wait_for_fullscreen() and temp_resume > 0:
            self.log(f"执行seek操作，跳转到 {temp_resume} 秒")
            xbmc.executebuiltin(f'Seek({temp_resume})')
            
            self._write_resume_to_temp(0)
            self.seek_executed = True
            self.log("临时文件续播点已清零，防止重复执行seek")
        else:
            self.log("未检测到全屏播放窗口或无有效续播点，跳过seek操作")

    def _wait_for_contextmenu(self, timeout=5):
        start_time = time.time()
        self.log("开始监控上下文菜单是否弹出")
        
        while time.time() - start_time < timeout:
            if xbmc.getCondVisibility("Window.IsVisible(contextmenu)") or \
               xbmc.getCondVisibility("Window.IsVisible(DialogContextMenu)"):
                self.log("上下文菜单已弹出")
                return True
            time.sleep(0.1)
            if self.monitor.abortRequested():
                self.log("程序请求退出，停止监控上下文菜单")
                return False
        
        self.log(f"上下文菜单监控超时（{timeout}秒内未弹出）")
        return False

    def _get_file_path(self):
        file_path = xbmc.getInfoLabel("ListItem.FilenameAndPath").strip()
        self.log(f"文件完整路径 (FilenameAndPath): {file_path}")
        return file_path

    def _is_home_window(self):
        current_window_id = xbmcgui.getCurrentWindowId()
        current_window_file = xbmc.getInfoLabel("Window.Property(xmlfile)").strip()
        is_home = (current_window_id == WINDOW_HOME_ID) and (current_window_file == WINDOW_HOME_FILE)
        self.log(f"是否为Home窗口 (ID:{WINDOW_HOME_ID}, File:{WINDOW_HOME_FILE}): {is_home}")
        return is_home

    def _handle_folder_play(self):
        self.log("检测到'folderplay'参数，开始特殊处理")
        
        time.sleep(0.3)
        
        self.log("执行模拟确认按键")
        xbmc.executebuiltin('Action(select)')
        time.sleep(0.2)
        
        if xbmc.getCondVisibility("Window.IsVisible(MovieInformation)") or \
           xbmc.getCondVisibility("Window.IsVisible(DialogVideoInfo.xml)"):
            self.log("检测到电影信息窗口，执行SendClick(8)")
            xbmc.executebuiltin('SendClick(8)')
            time.sleep(0.2)
            
            if self._wait_for_contextmenu():
                self.log("检测到上下文菜单，执行SendClick(1002)")
                xbmc.executebuiltin('SendClick(1002)')
                time.sleep(0.2)
                self._check_fullscreen_and_seek()
            else:
                self.log("电影信息窗口后未检测到上下文菜单")
        else:
            self.log("未检测到电影信息窗口，执行SendClick(1002)")
            xbmc.executebuiltin('SendClick(1002)')
            time.sleep(0.2)
            self._check_fullscreen_and_seek()

    def _show_contextmenu_choices(self):
        self._set_resumeselect_param(1)
        threading.Thread(target=lambda: [time.sleep(2), self._set_resumeselect_param(0)], daemon=True).start()

        dialog = xbmcgui.Dialog()
        choices = [
            f"从{self.resume_time_hhmmss}播放(可切换字/音)",
            "从头播放"
        ]
        choice = dialog.contextmenu(choices)
        self.log(f"用户选择的上下文菜单选项: {choice}")

        if self._is_home_window():
            if not self.current_file_path:
                self.log("错误: 文件完整路径为空，无法执行相关操作")
                return

            if choice == 0:
                self.log("Home窗口: 执行从有效续播点播放")
                xbmc.executebuiltin(f'PlayMedia({self.current_file_path},noresume)')
                self._write_resume_to_temp(self.resume_time)
                threading.Thread(target=self._check_fullscreen_and_seek, daemon=True).start()
                time.sleep(1)
            elif choice == 1:
                self.log("Home窗口: 执行从头播放")
                self._write_resume_to_temp(0)
                xbmc.executebuiltin(f'PlayMedia({self.current_file_path},noresume)')
                time.sleep(1)
            else:
                self.log("Home窗口: 用户取消选择")
                self._write_resume_to_temp(0)
        else:
            if choice == 0:
                self.log("非Home窗口: 执行从有效续播点播放")
                self._write_resume_to_temp(self.resume_time)
                if self.in_video_info:
                    self.log("在电影详情页，执行SendClick(8)")
                    xbmc.executebuiltin('SendClick(8)')
                    time.sleep(0.2)
                    
                    if self._wait_for_contextmenu():
                        self.log("检测到新上下文菜单，执行SendClick(1002)")
                        xbmc.executebuiltin('SendClick(1002)')
                        time.sleep(0.2)
                        threading.Thread(target=self._check_fullscreen_and_seek, daemon=True).start()
                    else:
                        self.log("上下文菜单未弹出，停止处理")
                        self._write_resume_to_temp(0)
                        return
                else:
                    xbmc.executebuiltin('Action(ContextMenu)')
                    time.sleep(0.2)
                    xbmc.executebuiltin('Action(Down)')
                    time.sleep(0.1)
                    xbmc.executebuiltin('Action(Select)')
                    threading.Thread(target=self._check_fullscreen_and_seek, daemon=True).start()
                
                time.sleep(1)
            elif choice == 1:
                self.log("非Home窗口: 执行从头播放")
                self._write_resume_to_temp(0)
                if self.in_video_info:
                    self.log("在电影详情页，执行SendClick(8)")
                    xbmc.executebuiltin('SendClick(8)')
                    time.sleep(0.5)
                    
                    if self._wait_for_contextmenu():
                        self.log("检测到新上下文菜单，执行SendClick(1002)")
                        xbmc.executebuiltin('SendClick(1002)')
                        time.sleep(0.2)
                        time.sleep(5)
                    else:
                        self.log("上下文菜单未弹出，停止处理")
                        return
                else:
                    xbmc.executebuiltin('Action(ContextMenu)')
                    time.sleep(0.2)
                    xbmc.executebuiltin('Action(Down)')
                    time.sleep(0.1)
                    xbmc.executebuiltin('Action(Down)')
                    time.sleep(0.1)
                    xbmc.executebuiltin('Action(Select)')
                    time.sleep(1)
            else:
                self.log("非Home窗口: 用户取消选择")
                self._write_resume_to_temp(0)

    # 删除清理方法，避免提前销毁monitor对象
    # def clean_up(self):
    #     if hasattr(self, 'monitor'):
    #         del self.monitor
    #         self.log("已清理xbmc.Monitor对象")
    #     # 清理时确保临时文件被重置
    #     self._write_resume_to_temp(0)

    def run(self):
        try:
            self.log(f"Skin.String(info_delay) 为 '{self.info_delay}', 不影响脚本运行")
            self.log("=" * 50)
            self.log(f"脚本开始运行 (路径: {SCRIPT_PATH})")
            self.log(f"检测到的参数: {self.args}")
            self.log("=" * 50)

            if self._is_home_window() and not self.is_resumable:
                self.log("Home窗口且文件不可续播: 直接执行播放")
                self._write_resume_to_temp(0)
                if self.current_file_path:
                    xbmc.executebuiltin(f'PlayMedia({self.current_file_path})')
                    time.sleep(1)
                else:
                    self.log("错误: 文件路径为空，无法直接播放")
                return

            if not (self.in_video_info or self.is_resumable):
                if self.in_video_info:
                    self.log("在视频信息窗口，跳过ISO和可续播检查")
                else:
                    self.log("未满足核心条件（不可续播且不在视频信息窗口），退出")
                self._write_resume_to_temp(0)
                return

            file_ids = self._get_file_ids()
            if not file_ids:
                self._handle_error("未查询到匹配的idFile")

            resume_points = self._get_resume_points_by_file_ids(file_ids)
            if not resume_points:
                self._handle_error("未查询到有效的type=1续播点")

            self.resume_time = self._select_closest_resume_point(resume_points)
            if not self.resume_time:
                self._handle_error("无法确定有效的续播点")

            self.resume_time_hhmmss = time.strftime('%H:%M:%S', time.gmtime(self.resume_time))
            self.log(f"最终有效的续播点: {self.resume_time} 秒 ({self.resume_time_hhmmss})")
            
            self._write_resume_to_temp(self.resume_time)

            if self.is_folder_play:
                self._handle_folder_play()
            else:
                self._show_contextmenu_choices()

            self.log("脚本运行完成并退出")
            self.log("=" * 50)
        finally:
            # 移除finally中的清理调用
            pass

if __name__ == "__main__":
    extractor = ISOResumeExtractor()
    extractor.run()