import xbmc
import xbmcgui
import xbmcvfs
import os
import shutil
import xml.etree.ElementTree as ET
import glob
import re

# 配置路径
FONTS_DIR = "/storage/.kodi/media/Fonts"
FONT_CACHE_XML = os.path.join(FONTS_DIR, "fontcache.xml")
GUI_SETTINGS_XML = "/storage/.kodi/userdata/guisettings.xml"
REBOOT_SCRIPT = "special://skin/scripts/rebootoff.py"

class SubFontManager:
    def __init__(self):
        self.fonts_dir = FONTS_DIR
        self.cache_xml = FONT_CACHE_XML
        self.gui_settings = GUI_SETTINGS_XML
        self.current_font_name = self._get_current_gui_font()

    def _get_current_gui_font(self):
        """从 guisettings.xml 获取当前使用的字幕字体名称"""
        try:
            if not xbmcvfs.exists(self.gui_settings):
                return "DEFAULT"
            
            # 读取文件内容
            f = xbmcvfs.File(self.gui_settings)
            content = f.read()
            f.close()
            
            # 使用正则表达式查找 subtitles.fontname
            # 匹配 <setting id="subtitles.fontname" ...>VALUE</setting>
            match = re.search(r'<setting\s+id="subtitles\.fontname"[^>]*>(.*?)</setting>', content)
            if match:
                val = match.group(1).strip()
                return val if val else "DEFAULT"
            return "DEFAULT"
        except Exception as e:
            xbmc.log(f"[SubMan] Error reading gui settings: {str(e)}", xbmc.LOGERROR)
            return "DEFAULT"

    def _parse_font_cache(self):
        """解析 fontcache.xml，返回字体列表 [{'filename': '..', 'familyname': '..'}, ...]"""
        fonts = []
        try:
            if not xbmcvfs.exists(self.cache_xml):
                return fonts
            
            f = xbmcvfs.File(self.cache_xml)
            content = f.read()
            f.close()
            
            if not content:
                return fonts

            root = ET.fromstring(content)
            for font_elem in root.findall('font'):
                filename_elem = font_elem.find('filename')
                familyname_elem = font_elem.find('familyname')
                
                if filename_elem is not None and familyname_elem is not None:
                    fname = filename_elem.text
                    famname = familyname_elem.text
                    if fname and famname:
                        fonts.append({
                            'filename': fname,
                            'familyname': famname
                        })
        except Exception as e:
            xbmc.log(f"[SubMan] Error parsing cache xml: {str(e)}", xbmc.LOGERROR)
        
        return fonts

    def _update_cache_xml(self, action, filename=None, familyname=None):
        """
        更新 fontcache.xml
        action: 'add' or 'remove'
        """
        root = None
        if xbmcvfs.exists(self.cache_xml):
            try:
                f = xbmcvfs.File(self.cache_xml)
                content = f.read()
                f.close()
                if content:
                    root = ET.fromstring(content)
                else:
                    root = ET.Element("fonts")
            except:
                root = ET.Element("fonts")
        else:
            root = ET.Element("fonts")

        if action == 'add':
            # 检查是否已存在
            exists = False
            for font_elem in root.findall('font'):
                fn = font_elem.find('filename')
                if fn is not None and fn.text == filename:
                    exists = True
                    break
            
            if not exists:
                new_font = ET.SubElement(root, "font")
                fn_elem = ET.SubElement(new_font, "filename")
                fn_elem.text = filename
                fam_elem = ET.SubElement(new_font, "familyname")
                fam_elem.text = familyname
                
                # 写入文件
                xml_str = ET.tostring(root, encoding='unicode')
                # 美化输出可选，这里直接写入
                f = xbmcvfs.File(self.cache_xml, 'w')
                f.write(xml_str)
                f.close()

        elif action == 'remove':
            if filename:
                for font_elem in root.findall('font'):
                    fn = font_elem.find('filename')
                    if fn is not None and fn.text == filename:
                        root.remove(font_elem)
                
                # 写入文件
                xml_str = ET.tostring(root, encoding='unicode')
                f = xbmcvfs.File(self.cache_xml, 'w')
                f.write(xml_str)
                f.close()

    def _execute_json_rpc(self, setting, value):
        """执行 JSON-RPC 命令设置字幕字体"""
        import json
        payload = {
            "jsonrpc": "2.0",
            "method": "Settings.SetSettingValue",
            "params": {
                "setting": setting,
                "value": value
            },
            "id": 1
        }
        xbmc.executeJSONRPC(json.dumps(payload))

    def _reboot_kodi(self):
        """执行重启脚本"""
        xbmc.executebuiltin(f"RunScript({REBOOT_SCRIPT},noask)")

    def show_main_menu(self):
        """显示主选择窗口"""
        options = [
            "添加字幕字体文件",
            "切换字幕字体文件",
            "删除字幕字体文件"
        ]
        
        dialog = xbmcgui.Dialog()
        select = dialog.select("字幕字体管理", options)
        
        if select == 0:
            self.add_font()
        elif select == 1:
            self.switch_font()
        elif select == 2:
            self.delete_font()
        
        # 如果未选择或操作完成，通常脚本结束。
        # 如果需要循环回到主菜单，可以在这里递归调用 show_main_menu()，
        # 但根据需求描述，“返回”通常意味着关闭对话框或回到上一级。
        # 这里我们让每次操作结束后脚本自然结束或根据用户选择决定是否重启。

    def add_font(self):
        """添加字体文件逻辑"""
        dialog = xbmcgui.Dialog()
        
        # 弹出 .ttf 文件选择窗口
        # browse(type, heading, shares, mask, useThumbs, treatAsFolder, defaultText, enableMultiple)
        # type 1 = file
        selected_file = dialog.browse(1, "选择字幕字体文件 (.ttf)", "files", ".ttf", False, False, "")
        
        if not selected_file:
            return # 用户取消

        # 确保目标文件夹存在
        if not xbmcvfs.exists(self.fonts_dir + "/"):
            xbmcvfs.mkdirs(self.fonts_dir)

        # 获取文件名
        filename = os.path.basename(selected_file)
        dest_path = os.path.join(self.fonts_dir, filename)

        # 复制文件
        try:
            # xbmcvfs.copy 支持特殊协议路径到本地路径
            xbmcvfs.copy(selected_file, dest_path)
        except Exception as e:
            dialog.ok("错误", f"复制文件失败: {str(e)}")
            return

        # 提取字体家族名称 (简单处理：去掉扩展名，或者尝试解析字体头，这里为了稳定性使用文件名去后缀作为默认FamilyName，
        # 实际上 Kodi 的 fontcache.xml 通常由系统扫描生成，但既然我们要手动管理，我们需要一个名字。
        # 更好的方式是让用户输入名字，或者简单地使用文件名。
        # 题目要求 fontcache.xml 格式，我们假设 familyname 可以暂时用文件名代替，或者提示用户输入。
        # 为了简化体验，这里使用文件名（不含扩展名）作为 Family Name，并在后续允许用户知道它是哪个文件。
        family_name = os.path.splitext(filename)[0]
        
        # 更新 cache xml
        self._update_cache_xml('add', filename, family_name)

        # 弹出确认窗口
        ret = dialog.yesno("提示", "已完成添加字体文件，重启后生效！\n点击“是”立即重启，点击“否”返回。")
        if ret:
            self._reboot_kodi()
        else:
            # 返回主选择窗口 (通过重新调用主菜单实现，或者仅仅退出当前函数)
            # 题目说“返回主选择窗口”，我们可以递归调用
            self.show_main_menu()

    def switch_font(self):
        """切换字体逻辑"""
        dialog = xbmcgui.Dialog()

        # 检查文件夹和文件
        has_fonts = False
        if xbmcvfs.exists(self.fonts_dir + "/"):
            # 检查是否有 ttf 文件
            files = xbmcvfs.listdir(self.fonts_dir)
            # files[1] 是文件列表
            for f in files[1]:
                if f.lower().endswith('.ttf'):
                    has_fonts = True
                    break
        
        if not has_fonts:
            dialog.ok("提示", "你系统里没有添加字幕字体文件，请重新添加。")
            self.show_main_menu()
            return

        # 构建选项列表
        options = ["系统默认字幕"]
        font_data_map = {} # index -> {'filename':..., 'familyname':...}
        
        cached_fonts = self._parse_font_cache()
        
        for idx, font in enumerate(cached_fonts):
            label = f"{font['filename']} - {font['familyname']}"
            options.append(label)
            # 映射索引到实际数据 (注意 options[0] 是默认，所以数据索引要偏移)
            font_data_map[idx + 1] = font

        select = dialog.select("切换字幕字体", options)
        
        if select == -1:
            return # 取消

        if select == 0:
            # 系统默认
            self._execute_json_rpc("subtitles.fontname", "DEFAULT")
            dialog.ok("成功", "已将字幕字体设置为系统默认字体！")
        else:
            # 用户选择的字体
            selected_font_info = font_data_map.get(select)
            if selected_font_info:
                target_family = selected_font_info['familyname']
                display_label = f"{selected_font_info['filename']} - {selected_font_info['familyname']}"
                
                self._execute_json_rpc("subtitles.fontname", target_family)
                dialog.ok("成功", f"已将字幕字体设置为“{display_label}”！")
        
        # 关闭脚本 (函数结束即关闭)

    def delete_font(self):
        """删除字体逻辑"""
        dialog = xbmcgui.Dialog()
        
        cached_fonts = self._parse_font_cache()
        if not cached_fonts:
            dialog.ok("提示", "没有可删除的字体文件。")
            self.show_main_menu()
            return

        # 构建多选列表
        options = []
        font_indices_map = [] # 存储原始列表索引，以便后续操作
        
        current_font = self.current_font_name

        for i, font in enumerate(cached_fonts):
            label = f"{font['filename']} - {font['familyname']}"
            # 检查是否是当前正在使用的字体
            # 注意：guisettings 里存的是 familyname
            if font['familyname'] == current_font:
                label += " [COLOR green][当前选择][/COLOR]"
            
            options.append(label)
            font_indices_map.append(i)

        # multiselect 返回选中的索引列表
        selected_indices = dialog.multiselect("删除字幕字体文件 (可多选)", options)
        
        if not selected_indices:
            return # 用户取消

        deleted_any_current = False
        files_to_delete = []

        for idx in selected_indices:
            original_idx = font_indices_map[idx]
            font_info = cached_fonts[original_idx]
            filename = font_info['filename']
            familyname = font_info['familyname']
            
            # 标记是否需要重置为默认
            if familyname == current_font:
                deleted_any_current = True
            
            files_to_delete.append({
                'filename': filename,
                'path': os.path.join(self.fonts_dir, filename),
                'familyname': familyname
            })

        # 执行删除
        for item in files_to_delete:
            try:
                if xbmcvfs.exists(item['path']):
                    xbmcvfs.delete(item['path'])
                # 从 cache xml 中移除
                self._update_cache_xml('remove', filename=item['filename'])
            except Exception as e:
                xbmc.log(f"[SubMan] Error deleting {item['filename']}: {str(e)}", xbmc.LOGERROR)

        # 如果删除了当前使用的字体，重置为默认
        if deleted_any_current:
            self._execute_json_rpc("subtitles.fontname", "DEFAULT")

        # 弹出确认窗口
        ret = dialog.yesno("提示", "已删除选择的字体文件，重启后生效！\n点击“是”立即重启，点击“否”返回。")
        if ret:
            self._reboot_kodi()
        else:
            # 关闭脚本
            pass

if __name__ == '__main__':
    manager = SubFontManager()
    manager.show_main_menu()