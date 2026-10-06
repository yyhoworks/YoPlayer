import sys
import os
import time
import json
import xbmc
import xbmcgui

def get_setting(setting_name):
    """通过JSON-RPC获取Kodi设置项的值"""
    try:
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "Settings.GetSettingValue",
            "params": {"setting": setting_name},
            "id": 1
        })
        response = xbmc.executeJSONRPC(request)
        result = json.loads(response)
        if 'result' in result and 'value' in result['result']:
            return result['result']['value']
    except Exception:
        pass
    return None

def set_setting(setting_name, value):
    """通过JSON-RPC设置Kodi设置项的值"""
    request = json.dumps({
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {"setting": setting_name, "value": value},
        "id": 1
    })
    xbmc.executeJSONRPC(request)

def trigger_dvtype_detect():
    """执行dvtype.py检测脚本"""
    xbmc.executebuiltin('RunScript(special://skin/scripts/dvtype.py,detect)')

def check_and_optimize(target_settings, special_logic=None, is_option_mode=False):
    """
    检查设置项是否符合要求。
    is_option_mode: True表示由option参数触发，False表示由start参数触发
    
    优化逻辑：
    如果读取设置项失败（返回None），则视为该设置项“相符”，不进行优化标记。
    """
    needs_optimize = False
    
    # 检查常规设置项
    for key, val in target_settings.items():
        current = get_setting(key)
        
        # 【核心修改】如果读取失败 (current is None)，视为相符，跳过此项检查
        if current is None:
            continue
            
        if isinstance(val, list):
            if current not in val:
                needs_optimize = True
                break
        else:
            if current != val:
                needs_optimize = True
                break
                
    # 检查特殊逻辑（如 max.luminance 阈值）
    # 注意：特殊逻辑内部通常也有自己的读取判断，如果特殊逻辑依赖的项读取失败，
    # 需要在 special_logic 函数内部处理，或者在这里判断。
    # 根据原代码逻辑，special_logic 返回 True 表示需要优化。
    # 如果 special_logic 内部读取失败返回 None，通常会被判定为 < 阈值从而返回 True。
    # 如果希望特殊逻辑的读取失败也视为“不需优化”，则需要修改 special_logic 的实现。
    # 但通常亮度等关键项如果读不到，可能意味着功能不可用或默认值，这里保持原特殊逻辑行为，
    # 除非特殊逻辑本身也依赖 get_setting 且我们希望它容错。
    # 鉴于题目主要强调“示范设置项”，这里主要处理 target_settings 循环部分。
    # 如果 special_logic 也受此规则影响，需在其内部实现类似判断。此处暂保持原样，仅处理常规项。
    
    if special_logic and not needs_optimize:
        if special_logic():
            needs_optimize = True
            
    dialog = xbmcgui.Dialog()
    
    if not needs_optimize:
        # 情况A: 设置已符合最优化（包括读取失败被视为相符的情况）
        if is_option_mode:
            # option模式下，弹窗提示并执行dvoption.py
            dialog.ok("杜比视界设置检查", "当前杜比视界基本设置项为最优化设置，无需修改！")
            xbmc.executebuiltin('RunScript(special://skin/scripts/dvoption.py,set)')
        else:
            # start模式下，直接触发dvtype检测并退出
            trigger_dvtype_detect()
        return
        
    # 情况B: 设置不符合最优化
    # 无论是start还是option模式，只要不相符，都按原逻辑执行优化询问
    msg = "检测到你的杜比视界关键设置项并非最优设置! \n选择“是”一键完成设置，选择“否”无需理会。\n(可以在设置中关闭开机检测)。"
    
    if dialog.yesno("杜比视界设置优化", msg):
        # 应用常规设置
        for key, val in target_settings.items():
            current = get_setting(key)
            
            # 同样，在应用设置时，如果读取失败，我们仍然应该尝试写入推荐值吗？
            # 题目说“读取失败的应该被视为相符”，这意味着不需要修改。
            # 但如果用户强制点击“是”进行优化，我们是否应该强行写入？
            # 通常“优化”意味着强制修正。但如果该项被隐藏（读取失败），强行写入可能会报错或无效。
            # 为了安全起见，如果读取失败，我们跳过写入，因为既然视为“相符”，就不需要“修正”。
            if current is None:
                continue

            if isinstance(val, list):
                if current not in val:
                    set_setting(key, val[0])
            else:
                if current != val:
                    set_setting(key, val)
                    
        # 应用特殊逻辑设置
        if special_logic:
            special_logic(apply=True)
            
        dialog.ok("设置完成", "已完成杜比视界关键设置项最优化！")
        
        # 优化完成后，无论哪种模式，都触发dvtype检测
        trigger_dvtype_detect()
    else:
        # 用户选择否，触发dvtype检测并退出
        trigger_dvtype_detect()

def main():
    # 1. 检查参数
    if len(sys.argv) < 2:
        sys.exit()
        
    arg = sys.argv[1]
    
    # 2. 延时2秒 (仅针对start参数)
    if arg == 'start':
        time.sleep(2)
    elif arg != 'option':
        # 未知参数退出
        sys.exit()

    # 3. 确认 /etc/os-release 文件是否存在
    os_release_path = '/etc/os-release'
    if not os.path.exists(os_release_path):
        if arg == 'start':
            trigger_dvtype_detect()
        sys.exit()

    # 读取 PRETTY_NAME
    pretty_name = ""
    try:
        with open(os_release_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    pretty_name = line.split('=', 1)[1].strip().strip('"')
                    break
    except Exception:
        if arg == 'start':
            trigger_dvtype_detect()
        sys.exit()

    if not pretty_name:
        if arg == 'start':
            trigger_dvtype_detect()
        sys.exit()

    pretty_name_lower = pretty_name.lower()
    
    # 如果包含 "official" 或 "nightly"，直接退出
    if 'official' in pretty_name_lower or 'nightly' in pretty_name_lower:
        if arg == 'start':
            trigger_dvtype_detect()
        sys.exit()

    # 4. 确认是否包含 "F9"
    is_f9 = 'f9' in pretty_name_lower
    
    # 获取 System.SupportedHDRTypes 并判断是否包含 "Vision"
    hdr_types = xbmc.getInfoLabel('System.SupportedHDRTypes').lower()
    has_vision = 'vision' in hdr_types

    # 定义各情况的示范设置项
    target_1_1 = {
        "coreelec.amlogic.dolbyvision.mode": 1,
        "coreelec.amlogic.dolbyvision.type": 0,
        "coreelec.amlogic.dolbyvision.vsvdb.inject": False,
        "coreelec.amlogic.dolbyvision.vs10.sdr8": 5,
        "coreelec.amlogic.dolbyvision.vs10.sdr10": 5,
        "coreelec.amlogic.dolbyvision.vs10.hdr10": 5,
        "coreelec.amlogic.dolbyvision.vs10.hdr10plus": 5,
        "coreelec.amlogic.dolbyvision.vs10.hdrhlg": 5,
        "coreelec.amlogic.dolbyvision.vs10.dv": 0,
        "videoplayer.convertdovi": 0
    }

    target_1_2 = {
        "coreelec.amlogic.dolbyvision.mode": 1,
        "coreelec.amlogic.dolbyvision.type": 2,
        "coreelec.amlogic.dolbyvision.vsvdb.inject": True,
        "coreelec.amlogic.dolbyvision.vsvdb.colour.space": 1,
        "coreelec.amlogic.dolbyvision.vsvdb.min.luminance": 1,
        "coreelec.amlogic.dolbyvision.vs10.sdr8": 5,
        "coreelec.amlogic.dolbyvision.vs10.sdr10": 5,
        "coreelec.amlogic.dolbyvision.vs10.hdr10": 5,
        "coreelec.amlogic.dolbyvision.vs10.hdr10plus": 5,
        "coreelec.amlogic.dolbyvision.vs10.hdrhlg": 5,
        "coreelec.amlogic.dolbyvision.vs10.dv": 0,
        "videoplayer.convertdovi": 0
    }

    target_2_1 = {
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

    target_2_2 = {
        "coreelec.amlogic.dolbyvision.mode": 1,
        "coreelec.amlogic.dolbyvision.type": [2, 4], # 2或者4均符合
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

    # 特殊逻辑定义
    def special_logic_1_2(apply=False):
        current_max = get_setting("coreelec.amlogic.dolbyvision.vsvdb.max.luminance")
        # 如果读取失败 (None)，视为相符，不需要优化，返回 False
        if current_max is None:
            return False
        if current_max < 25:
            if apply:
                set_setting("coreelec.amlogic.dolbyvision.vsvdb.max.luminance", 25)
                set_setting("coreelec.amlogic.dolbyvision.vsvdb.payload", "490BC85698A953")
            return True
        return False

    def special_logic_2_2(apply=False):
        current_max = get_setting("coreelec.amlogic.dolbyvision.vsvdb.max.luminance")
        # 如果读取失败 (None)，视为相符，不需要优化，返回 False
        if current_max is None:
            return False
        if current_max < 4000:
            if apply:
                set_setting("coreelec.amlogic.dolbyvision.vsvdb.max.luminance", 4000)
            return True
        return False

    # 5. 根据条件分发执行
    is_option_mode = (arg == 'option')
    
    if not is_f9:
        if has_vision:
            # 情况1.1
            check_and_optimize(target_1_1, is_option_mode=is_option_mode)
        else:
            # 情况1.2
            check_and_optimize(target_1_2, special_logic_1_2, is_option_mode=is_option_mode)
    else:
        if has_vision:
            # 情况2.1
            check_and_optimize(target_2_1, is_option_mode=is_option_mode)
        else:
            # 情况2.2
            check_and_optimize(target_2_2, special_logic_2_2, is_option_mode=is_option_mode)

if __name__ == '__main__':
    main()
    sys.exit()