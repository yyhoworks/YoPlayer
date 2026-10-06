import xbmc
import xbmcgui
import xbmcvfs
import os
import re

try:
    # Python 3
    from urllib.parse import unquote
except ImportError:
    # Python 2
    from urllib import unquote

class BDMVMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.last_folder = ""
        self.last_file_path = ""
        self.recorded_folder_path = None  # 记录的ISO/BDMV路径
        self.iso_folder = None  # ISO文件所在目录路径
        self.play_flag = False
        self.processing = False
        self.enabled = not xbmc.getCondVisibility("Skin.HasSetting(bdmvplay)")
        self.waiting_for_select_dialog = False
        self.iso_mode = False  # 标记是否处于ISO模式
        self.TARGET_WINDOW = 10003  # 文件管理器窗口

    def onSettingsChanged(self):
        new_enabled = not xbmc.getCondVisibility("Skin.HasSetting(bdmvplay)")
        if new_enabled != self.enabled:
            self.enabled = new_enabled

    def onNotification(self, sender, method, data):
        if self.waiting_for_select_dialog:
            if method == "Input.OnInputRequested" or method == "Dialog.Select" or "DialogSelect" in method:
                self._reset_iso_state()
                self.play_flag = False
                self.waiting_for_select_dialog = False

    def _reset_iso_state(self):
        """重置与ISO播放相关的状态变量"""
        self.recorded_folder_path = None
        self.iso_folder = None
        self.iso_mode = False

    def _is_dir(self, path):
        """
        兼容旧版本Kodi的目录判断函数。
        使用 xbmcvfs.listdir() 来判断路径是否为目录。
        """
        if not path:
            return False
        try:
            dirs, files = xbmcvfs.listdir(path)
            return True
        except Exception as e:
            xbmc.log(f"BDMVMonitor Error: _is_dir 判断失败 for path: {path}, error: {e}", xbmc.LOGERROR)
            return False

    def normalize_path_for_comparison(self, path):
        """规范化路径用于比较（统一大小写、分隔符、协议头）"""
        if not path:
            return ""
        normalized = path.replace("\\", "/")
        normalized = normalized.rstrip("/")
        normalized = normalized.lower()
        return normalized

    def normalize_network_path(self, path):
        """规范化网络路径协议头（nfs://、smb:// 等）"""
        path = path.replace("\\", "/")
        protocols = [("nfs:/", "nfs://"), ("smb:/", "smb://"), ("webdav:/", "webdav://"), ("dav:/", "dav://")]
        for proto, correct_proto in protocols:
            if path.startswith(proto) and not path.startswith(correct_proto):
                path = correct_proto + path[len(proto):]
                break
        return path

    def find_index_bdmv(self, folder_path):
        """查找 BDMV 文件夹下的 index.bdmv"""
        try:
            local_path = self.normalize_path_for_comparison(folder_path)
            
            if local_path.startswith(("nfs://", "smb://", "webdav://", "dav://")):
                check_path = local_path
            else:
                if hasattr(xbmc, 'translatePath'):
                    check_path = xbmc.translatePath(folder_path)
                else:
                    check_path = folder_path
                if check_path.startswith("file://"):
                    check_path = check_path[7:]
                check_path = self.normalize_path_for_comparison(check_path)

            check_path = check_path.rstrip("/") + "/"

            if check_path.upper().endswith("BDMV/"):
                index_path = f"{check_path}index.bdmv"
                if xbmcvfs.exists(index_path):
                    parent_path = os.path.dirname(check_path.rstrip("/"))
                    return index_path, parent_path
                else:
                    return None, None

            dirs, _ = xbmcvfs.listdir(check_path)
            if "BDMV" in dirs:
                index_path = f"{check_path}BDMV/index.bdmv"
                if xbmcvfs.exists(index_path):
                    parent_path = check_path.rstrip("/")
                    return index_path, parent_path
                else:
                    return None, None
            
            return None, None
        except Exception as e:
            xbmc.log(f"BDMVMonitor Error: 查找 index.bdmv 出错 - 输入路径: {folder_path}, error: {e}", xbmc.LOGERROR)
            return None, None

    def compare_paths(self, new_path, recorded_path):
        """比较两个路径的关系（相同、子目录、父目录、无关联）"""
        new_norm = self.normalize_path_for_comparison(new_path)
        rec_norm = self.normalize_path_for_comparison(recorded_path)

        if new_norm == rec_norm:
            return {"is_same": True, "is_subdirectory": False, "is_parent": False, "depth_diff": 0}

        if new_norm.startswith(f"{rec_norm}/"):
            relative_path = new_norm[len(rec_norm) + 1:]
            depth_diff = len([p for p in relative_path.split("/") if p])
            return {"is_same": False, "is_subdirectory": True, "is_parent": False, "depth_diff": depth_diff}

        if rec_norm.startswith(f"{new_norm}/"):
            relative_path = rec_norm[len(new_norm) + 1:]
            depth_diff = len([p for p in relative_path.split("/") if p])
            return {"is_same": False, "is_subdirectory": False, "is_parent": True, "depth_diff": depth_diff}

        return {"is_same": False, "is_subdirectory": False, "is_parent": False, "depth_diff": 0}

    def parse_iso_path_from_udf_url(self, udf_url):
        """从 UDF 路径解析 ISO 原始路径"""
        if not udf_url.startswith('udf://'):
            return None

        match = re.search(r'^(udf://)(.*?\.iso)(/.*)?$', udf_url, re.IGNORECASE)
        if not match:
            return None
            
        iso_path_encoded = match.group(2)
        if not iso_path_encoded:
            return None

        try:
            iso_path = unquote(iso_path_encoded)
            iso_path = iso_path.replace('/', '\\')
            return iso_path
        except Exception as e:
            xbmc.log(f"BDMVMonitor Error: 解码 ISO 路径失败 - 编码路径: {iso_path_encoded}, error: {e}", xbmc.LOGERROR)
            return None

    def is_iso_file(self, file_path):
        """检查路径是否为 ISO 文件"""
        return file_path and file_path.lower().endswith('.iso')

    def perform_post_back_action_check(self):
        """Action(Down) 后检查路径"""
        try:
            if xbmcgui.getCurrentWindowId() != self.TARGET_WINDOW:
                self._reset_iso_state()
                return

            xbmc.sleep(200) 

            updated_file_path = xbmc.getInfoLabel('ListItem.FilenameAndPath')

            if not updated_file_path or updated_file_path.startswith("sources://"):
                self._reset_iso_state()
                return

            parsed_original_path = self.parse_iso_path_from_udf_url(updated_file_path)
            if parsed_original_path:
                if self.normalize_path_for_comparison(parsed_original_path) == self.normalize_path_for_comparison(self.recorded_folder_path):
                    xbmc.executebuiltin('Action(Back)')
                    xbmc.sleep(100)
                    xbmc.executebuiltin(f'PlayMedia({self.recorded_folder_path})')
                    self.play_flag = True
                    self.waiting_for_select_dialog = True
                else:
                    self._reset_iso_state()
                return

            if not self.iso_mode and self.recorded_folder_path:
                if updated_file_path.startswith(("nfs://", "smb://", "webdav://", "dav://")):
                    updated_folder_path = os.path.dirname(updated_file_path) if "." in os.path.basename(updated_file_path) else updated_file_path
                else:
                    local_path = xbmc.translatePath(updated_file_path) if hasattr(xbmc, 'translatePath') else updated_file_path
                    if local_path.startswith("file://"):
                        local_path = local_path[7:]
                    local_path = self.normalize_path_for_comparison(local_path)
                    updated_folder_path = os.path.dirname(local_path) if "." in os.path.basename(local_path) else local_path

                comparison = self.compare_paths(updated_folder_path, self.recorded_folder_path)
                if comparison['is_subdirectory'] and comparison['depth_diff'] == 1:
                    xbmc.executebuiltin('Action(Back)')
                    xbmc.sleep(100)
                    index_path_to_play = os.path.join(self.recorded_folder_path, "BDMV", "index.bdmv").replace("\\", "/")
                    xbmc.executebuiltin(f'PlayMedia({index_path_to_play})')
                    self.play_flag = True
                    self.waiting_for_select_dialog = True
                else:
                    self.recorded_folder_path = None
        except Exception as e:
            xbmc.log(f"BDMVMonitor Error: perform_post_back_action_check 出错 - error: {e}", xbmc.LOGERROR)

    def run(self):
        """主循环"""
        while not self.abortRequested():
            try:
                if not self.enabled:
                    self.waitForAbort(1)
                    continue

                current_window_id = xbmcgui.getCurrentWindowId()
                if current_window_id != self.TARGET_WINDOW:
                    self.waitForAbort(1)
                    continue

                current_file_path = xbmc.getInfoLabel('ListItem.FilenameAndPath')
                current_label = xbmc.getInfoLabel('ListItem.Label')

                if not current_file_path or current_file_path.startswith("sources://"):
                    if current_file_path != self.last_file_path:
                        self.last_file_path = current_file_path
                        self.last_folder = ""
                    self.waitForAbort(1)
                    continue

                if current_file_path != self.last_file_path and not self.processing:
                    self.last_file_path = current_file_path
                    self.play_flag = False
                    self.processing = True

                    if self.is_iso_file(current_file_path):
                        self.recorded_folder_path = current_file_path
                        self.iso_folder = os.path.dirname(current_file_path)
                        self.iso_mode = True
                        self.processing = False
                        continue

                    if self.iso_mode and self.recorded_folder_path and self.iso_folder:
                        parsed_path = self.parse_iso_path_from_udf_url(current_file_path)
                        if parsed_path:
                            if self.normalize_path_for_comparison(parsed_path) in self.normalize_path_for_comparison(self.recorded_folder_path):
                                xbmc.executebuiltin('Action(Back)')
                                xbmc.sleep(100)
                                xbmc.executebuiltin(f'PlayMedia({self.recorded_folder_path})')
                                self.play_flag = True
                                self.waiting_for_select_dialog = True
                            else:
                                self._reset_iso_state()
                            self.processing = False
                            continue

                        if current_file_path.startswith(("nfs://", "smb://", "webdav://", "dav://")):
                            if current_file_path.endswith('/'):
                                folder_path = current_file_path
                            else:
                                folder_path = os.path.dirname(current_file_path)
                        else:
                            local_path = xbmc.translatePath(current_file_path) if hasattr(xbmc, 'translatePath') else current_file_path
                            if local_path.startswith("file://"):
                                local_path = local_path[7:]
                            
                            if self._is_dir(local_path):
                                folder_path = current_file_path
                            else:
                                folder_path = os.path.dirname(current_file_path)

                        folder_path_norm = self.normalize_path_for_comparison(folder_path)
                        iso_folder_norm = self.normalize_path_for_comparison(self.iso_folder)

                        if folder_path_norm == iso_folder_norm and current_label == "..":
                            xbmc.executebuiltin('Action(Down)')
                            self.perform_post_back_action_check()
                            self.processing = False
                            continue

                        self._reset_iso_state()
                        self.processing = False
                        continue

                    index_path, parent_path = self.find_index_bdmv(current_file_path)
                    if index_path and parent_path:
                        self.recorded_folder_path = parent_path
                        self.processing = False
                        continue

                    if self.recorded_folder_path and not self.iso_mode:
                        if current_file_path.startswith(("nfs://", "smb://", "webdav://", "dav://")):
                            folder_path = os.path.dirname(current_file_path) if "." in os.path.basename(current_file_path) else current_file_path
                        else:
                            local_path = xbmc.translatePath(current_file_path) if hasattr(xbmc, 'translatePath') else current_file_path
                            if local_path.startswith("file://"):
                                local_path = local_path[7:]
                            local_path = self.normalize_path_for_comparison(local_path)
                            folder_path = os.path.dirname(local_path) if "." in os.path.basename(local_path) else local_path

                        if folder_path != self.last_folder:
                            self.last_folder = folder_path
                            comparison = self.compare_paths(folder_path, self.recorded_folder_path)
                            if comparison['is_parent'] and comparison['depth_diff'] == 1 and current_label == "..":
                                xbmc.executebuiltin('Action(Down)')
                                self.perform_post_back_action_check()

                    self.processing = False

            except Exception as e:
                xbmc.log(f"BDMVMonitor Error: 主循环出错 - error: {e}", xbmc.LOGERROR)
                self.processing = False

            self.waitForAbort(0.5)

if __name__ == '__main__':
    monitor = BDMVMonitor()
    monitor.run()