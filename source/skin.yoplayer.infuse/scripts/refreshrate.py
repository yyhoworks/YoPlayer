import xbmc
import xbmcgui
import json
import sys
import time

# 刷新率自动调整设置ID
SETTING_ID_REFRESH = "videoplayer.adjustrefreshrate"

# 选项
options_refresh = [
    "关闭(取消握手解决播放黑屏问题)",             # 值: 0
    "在开始播放/停止播放时"                      # 值: 2
]

# 刷新率值到中文描述的映射
VALUE_TO_DESC = {
    0: "关闭",
    1: "始终",
    2: "自适应",
    3: "仅起播时"
}

def set_system_refresh_rate(value):
    """仅设置系统刷新率设置项"""
    set_refresh_request = {
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {"setting": SETTING_ID_REFRESH, "value": value},
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(set_refresh_request))

def update_skin_variables(value):
    """
    延时检测实际值，并更新皮肤变量 refreshrate (中文描述)
    注意：此函数不包含 ratechange 的逻辑
    """
    # 延时等待设置生效
    time.sleep(0.5)
    
    # 使用 JSON-RPC 检测设置项的实际值
    get_refresh_request = {
        "jsonrpc": "2.0",
        "method": "Settings.GetSettingValue",
        "params": {"setting": SETTING_ID_REFRESH},
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(get_refresh_request))
    try:
        result = json.loads(response)
        current_value = result.get('result', {}).get('value', 0)
        
        # 获取对应的中文描述
        desc = VALUE_TO_DESC.get(current_value, "未知")
        
        # 设置新的皮肤变量 refreshrate
        xbmc.executebuiltin(f'Skin.SetString(refreshrate,{desc})')
    except Exception as e:
        xbmc.log(f"Failed to get refresh rate setting for skin var: {str(e)}", xbmc.LOGWARNING)

def apply_silent_mode(value):
    """
    静默模式专用逻辑：
    1. 设置系统刷新率
    2. 设置旧皮肤变量 ratechange (原有逻辑)
    3. 设置新皮肤变量 refreshrate (新增逻辑)
    """
    # 1. 设置系统刷新率
    set_system_refresh_rate(value)
    
    # 2. 设置旧皮肤变量 ratechange
    # 原逻辑：value=2 -> ratechange=0; 其他(value=0) -> ratechange=1
    if value == 2:
        xbmc.executebuiltin('Skin.SetString(ratechange,0)')
    else:
        xbmc.executebuiltin('Skin.SetString(ratechange,1)')
        
    # 3. 设置新皮肤变量 refreshrate (复用通用更新逻辑)
    update_skin_variables(value)

def main():
    # 检查命令行参数
    args = sys.argv[1:]  # 获取传递给脚本的参数
    
    if len(args) > 0:
        param = args[0].lower()
        
        if param == "off":
            # 静默设置为关闭模式 (value=0)
            apply_silent_mode(0)
            return
        elif param == "on":
            # 静默设置为播放时调整模式 (value=2)
            apply_silent_mode(2)
            return
    
    # --- 交互模式逻辑 ---
    # 没有参数或参数无效时，执行原交互逻辑
    
    dialog = xbmcgui.Dialog()
    selected_index = dialog.select("刷新率自动调整", options_refresh)

    if selected_index != -1:
        new_refresh_value = 0 if selected_index == 0 else 2

        # 1. 仅设置系统刷新率 (不触碰 ratechange)
        set_system_refresh_rate(new_refresh_value)
        
        # 2. 更新新的皮肤变量 refreshrate (中文描述)
        update_skin_variables(new_refresh_value)

        dialog.ok("设置完成", f"刷新率自动调整 已设为:\n{options_refresh[selected_index]}")

    else:
        dialog.ok("已取消", "未做任何更改")

if __name__ == "__main__":
    main()