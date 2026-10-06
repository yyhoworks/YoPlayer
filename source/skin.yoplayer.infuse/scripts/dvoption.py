import xbmc
import xbmcgui
import json
import os
import re
import sys

# 定义常量
SKIN_PATH = "special://skin/scripts/"

# 定义可以忽略错误的设置项列表
IGNORE_ERROR_KEYS = [
    "coreelec.amlogic.dolbyvision.vs10.hdr10plus",
    "coreelec.amlogic.dolbyvision.vs10.hdrhlg"
]

def get_setting(setting_name):
    """通过 JSON-RPC 获取设置值"""
    query = {
        "jsonrpc": "2.0",
        "method": "Settings.GetSettingValue",
        "params": {"setting": setting_name},
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(response)
    if 'result' in result and 'value' in result['result']:
        return result['result']['value']
    return None

def set_setting(setting_name, value):
    """通过 JSON-RPC 设置值，返回是否成功"""
    query = {
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {
            "setting": setting_name,
            "value": value
        },
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(response)
    
    # 修复点：CoreELEC/Kodi 成功时通常返回 boolean True，有时也可能返回 "OK"
    res_value = result.get('result')
    return res_value is True or res_value == 'OK'

def check_hdr_support(keyword):
    """检查 System.SupportedHDRTypes 是否包含指定关键字（不区分大小写）"""
    supported_types = xbmc.getInfoLabel("System.SupportedHDRTypes")
    if not supported_types:
        return False
    return keyword.lower() in supported_types.lower()

def show_yes_no_dialog(header, message):
    """显示是/否对话框，返回 True (Yes) 或 False (No)"""
    dialog = xbmcgui.Dialog()
    ret = dialog.yesno(header, message, nolabel="否", yeslabel="是")
    return ret

def show_info_dialog(header, message):
    """显示信息确认对话框"""
    dialog = xbmcgui.Dialog()
    dialog.ok(header, message)

def run_script(path, args=""):
    """运行指定的 Kodi 脚本"""
    cmd = f"RunScript({path}"
    if args:
        cmd += f",{args}"
    cmd += ")"
    xbmc.executebuiltin(cmd)

def apply_settings(settings_dict):
    """
    批量应用设置。
    1. 遇到 IGNORE_ERROR_KEYS 中的项失败时，忽略错误并继续。
    2. 遇到其他项失败时，记录错误但继续设置剩余项（不中断）。
    3. 返回最终状态：如果有任何非忽略项失败，返回 False，否则返回 True。
    """
    all_success = True
    
    for key, value in settings_dict.items():
        is_ignored = key in IGNORE_ERROR_KEYS
        success = set_setting(key, value)
        
        if not success:
            if is_ignored:
                xbmc.log(f"[dvoption] Ignored failure for setting: {key}", xbmc.LOGDEBUG)
            else:
                xbmc.log(f"[dvoption] Failed to set critical setting: {key}", xbmc.LOGERROR)
                all_success = False
        # 无论成功与否，都继续循环处理下一项
        
    return all_success

def main():
    # 检查参数
    if len(sys.argv) < 2 or sys.argv[1] != "set":
        return

    # 定义选项列表
    options = [
        "自动检测/设置杜比视界基本设置项",
        "设置为电视主导DV-std杜比视界",
        "设置为播放器主导DV-LL杜比视界",
        "设置为播放器主导HDR-444杜比视界",
        "设置为播放器主导HDR-422杜比视界"
    ]

    dialog = xbmcgui.Dialog()
    select = dialog.select("杜比视界设置选项", options)

    if select == -1:
        return

    # 选项 1: 自动检测
    if select == 0:
        run_script(os.path.join(SKIN_PATH, "dvautoset.py"), "option")
        return

    # 选项 2: 电视主导 DV-std
    elif select == 1:
        mode_name = "电视主导DV-std"
        supported_vision = check_hdr_support("Vision")
        
        if not supported_vision:
            if not show_yes_no_dialog("提示", "检测到你的设备不支持杜比视界，选择“是”尝试强制设置，选择“否”退出返回。"):
                return 
        
        settings = {
            "coreelec.amlogic.dolbyvision.mode": 1,
            "coreelec.amlogic.dolbyvision.type": 0,
            "coreelec.amlogic.dolbyvision.vs10.sdr8": 5,
            "coreelec.amlogic.dolbyvision.vs10.sdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10plus": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdrhlg": 5,
            "coreelec.amlogic.dolbyvision.vs10.dv": 0,
            "videoplayer.convertdovi": 0
        }
        
        if apply_settings(settings):
            show_info_dialog("成功", f"已成功设置{mode_name}杜比视界！")
        else:
            show_info_dialog("完成", f"{mode_name}设置已应用（部分非关键项可能跳过）。")
        
        run_script(os.path.join(SKIN_PATH, "dvtype.py"), "detect")

    # 选项 3: 播放器主导 DV-LL
    elif select == 2:
        mode_name = "播放器主导DV-LL"
        supported_vision = check_hdr_support("Vision")
        
        if not supported_vision:
            if not show_yes_no_dialog("提示", "检测到你的设备不支持杜比视界，选择“是”尝试强制设置，选择“否”退出返回。"):
                return
        
        settings = {
            "coreelec.amlogic.dolbyvision.mode": 1,
            "coreelec.amlogic.dolbyvision.type": 1,
            "coreelec.amlogic.dolbyvision.vs10.sdr8": 5,
            "coreelec.amlogic.dolbyvision.vs10.sdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10plus": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdrhlg": 5,
            "coreelec.amlogic.dolbyvision.vs10.dv": 0,
            "videoplayer.convertdovi": 0
        }
        
        if apply_settings(settings):
            show_info_dialog("成功", f"已成功设置{mode_name}杜比视界！")
        else:
            show_info_dialog("完成", f"{mode_name}设置已应用（部分非关键项可能跳过）。")
            
        run_script(os.path.join(SKIN_PATH, "dvtype.py"), "detect")

    # 选项 4: 播放器主导 HDR-444
    elif select == 3:
        mode_name = "播放器主导HDR-444"
        supported_hdr = check_hdr_support("HDR")
        
        if not supported_hdr:
            if not show_yes_no_dialog("提示", "检测到你的设备不支持HDR，选择“是”尝试强制设置，选择“否”退出返回。"):
                return
        
        settings = {
            "coreelec.amlogic.dolbyvision.mode": 1,
            "coreelec.amlogic.dolbyvision.type": 2,
            "coreelec.amlogic.dolbyvision.vsvdb.inject": True,
            "coreelec.amlogic.dolbyvision.vsvdb.colour.space": 1,
            "coreelec.amlogic.dolbyvision.vs10.sdr8": 5,
            "coreelec.amlogic.dolbyvision.vs10.sdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10plus": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdrhlg": 5,
            "coreelec.amlogic.dolbyvision.vs10.dv": 0,
            "videoplayer.convertdovi": 0
        }
        
        # 处理 OS Release 逻辑
        try:
            with open("/etc/os-release", "r") as f:
                os_content = f.read()
            match = re.search(r'^PRETTY_NAME=(.*)', os_content, re.MULTILINE)
            pretty_name = ""
            if match:
                pretty_name = match.group(1).strip().strip('"').strip("'")
            
            current_luminance = get_setting("coreelec.amlogic.dolbyvision.vsvdb.max.luminance")
            try:
                current_lum_val = float(current_luminance) if current_luminance is not None else 0
            except:
                current_lum_val = 0

            if "F9" not in pretty_name:
                if current_lum_val < 25:
                    settings["coreelec.amlogic.dolbyvision.vsvdb.max.luminance"] = 25
                    settings["coreelec.amlogic.dolbyvision.vsvdb.payload"] = "490BC85698A953"
            else: # Contains F9
                if current_lum_val < 4000:
                    settings["coreelec.amlogic.dolbyvision.vsvdb.max.luminance"] = 4000
                    
        except Exception as e:
            xbmc.log(f"[dvoption] Error processing os-release for option 4: {e}", xbmc.LOGERROR)

        if apply_settings(settings):
            show_info_dialog("成功", f"已成功设置{mode_name}杜比视界！")
        else:
            show_info_dialog("完成", f"{mode_name}设置已应用（部分非关键项可能跳过）。")
            
        run_script(os.path.join(SKIN_PATH, "dvtype.py"), "detect")

    # 选项 5: 播放器主导 HDR-422
    elif select == 4:
        mode_name = "播放器主导HDR-422"
        supported_hdr = check_hdr_support("HDR")
        
        if not supported_hdr:
            if not show_yes_no_dialog("提示", "检测到你的设备不支持HDR，选择“是”尝试强制设置，选择“否”退出返回。"):
                return
        
        settings = {
            "coreelec.amlogic.dolbyvision.mode": 1,
            "coreelec.amlogic.dolbyvision.type": 4,
            "coreelec.amlogic.dolbyvision.vsvdb.inject": True,
            "coreelec.amlogic.dolbyvision.vsvdb.colour.space": 1,
            "coreelec.amlogic.dolbyvision.vs10.sdr8": 5,
            "coreelec.amlogic.dolbyvision.vs10.sdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdr10plus": 5,
            "coreelec.amlogic.dolbyvision.vs10.hdrhlg": 5,
            "coreelec.amlogic.dolbyvision.vs10.dv": 0,
            "videoplayer.convertdovi": 0
        }

        # 处理 OS Release 逻辑 (同选项4)
        try:
            with open("/etc/os-release", "r") as f:
                os_content = f.read()
            match = re.search(r'^PRETTY_NAME=(.*)', os_content, re.MULTILINE)
            pretty_name = ""
            if match:
                pretty_name = match.group(1).strip().strip('"').strip("'")
            
            current_luminance = get_setting("coreelec.amlogic.dolbyvision.vsvdb.max.luminance")
            try:
                current_lum_val = float(current_luminance) if current_luminance is not None else 0
            except:
                current_lum_val = 0

            if "F9" not in pretty_name:
                if current_lum_val < 25:
                    settings["coreelec.amlogic.dolbyvision.vsvdb.max.luminance"] = 25
                    settings["coreelec.amlogic.dolbyvision.vsvdb.payload"] = "490BC85698A953"
            else: # Contains F9
                if current_lum_val < 4000:
                    settings["coreelec.amlogic.dolbyvision.vsvdb.max.luminance"] = 4000
                    
        except Exception as e:
            xbmc.log(f"[dvoption] Error processing os-release for option 5: {e}", xbmc.LOGERROR)

        if apply_settings(settings):
            show_info_dialog("成功", f"已成功设置{mode_name}杜比视界！")
        else:
            show_info_dialog("完成", f"{mode_name}设置已应用（部分非关键项可能跳过）。")
            
        run_script(os.path.join(SKIN_PATH, "dvtype.py"), "detect")

if __name__ == "__main__":
    main()