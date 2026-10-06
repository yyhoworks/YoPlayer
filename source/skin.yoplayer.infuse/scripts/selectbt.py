import sys
import re
import subprocess
import xbmc
import xbmcgui
import time

def get_hciconfig_output():
    """执行 hciconfig -a 并返回输出结果"""
    try:
        result = subprocess.run(['hciconfig', '-a'], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        xbmc.log(f"[selectbt.py] Error executing hciconfig: {str(e)}", xbmc.LOGERROR)
        return ""

def get_rfkill_index(hci_id):
    """根据 hci_id 获取 rfkill 列表中的数字序号"""
    try:
        result = subprocess.run(['rfkill', 'list'], capture_output=True, text=True, check=True)
        rfkill_output = result.stdout
        
        lines = rfkill_output.split('\n')
        for line in lines:
            # 查找包含 hci_id 的行，例如 "1: hci0: bluetooth"
            if hci_id in line:
                match = re.match(r'^\s*(\d+):', line)
                if match:
                    return match.group(1)
    except Exception as e:
        xbmc.log(f"[selectbt.py] Error executing rfkill list: {str(e)}", xbmc.LOGERROR)
    
    return None

def handle_setup():
    """处理 setup 参数：交互式选择并设置/禁用蓝牙（支持循环操作与状态同步）"""
    dialog = xbmcgui.Dialog()
    
    # 外层循环：确保持续显示一级菜单，直到用户主动退出
    while True:
        hciconfig_output = get_hciconfig_output()
        
        if not hciconfig_output:
            dialog.ok("错误", "无法获取蓝牙适配器信息。")
            return

        # 解析 hciconfig 输出
        adapter_blocks = re.split(r'(?=^hci\d+:)', hciconfig_output, flags=re.MULTILINE)
        adapter_blocks = [block.strip() for block in adapter_blocks if block.strip()]

        parsed_adapters = []
        for block in adapter_blocks:
            hci_match = re.match(r'(hci\d+):', block)
            if not hci_match:
                continue
            
            hci_id = hci_match.group(1)
            
            bus_match = re.search(r'Bus:\s*(\S+)', block)
            bus = bus_match.group(1) if bus_match else "Unknown"
            
            has_name = 'Name: ' in block
            
            parsed_adapters.append({
                'hci_id': hci_id,
                'bus': bus,
                'has_name': has_name
            })

        if not parsed_adapters:
            dialog.ok("提示", "未检测到任何蓝牙适配器。")
            return

        # 构建选项列表
        options = []
        for adapter in parsed_adapters:
            status = "[COLOR green]可用[/COLOR]" if adapter['has_name'] else "[COLOR red]已禁用[/COLOR]"
            display_bus = "内置" if adapter['bus'].upper() == "UART" else adapter['bus']
            option_str = f"{status}{adapter['hci_id']}-{display_bus}蓝牙适配器"
            options.append(option_str)

        # 弹出一级选择窗口
        selected_index = dialog.select("选择蓝牙适配器 (按返回键退出)", options)
        
        # 如果用户在一级菜单按返回键 (-1)，则退出整个脚本
        if selected_index == -1:
            break

        selected_adapter = parsed_adapters[selected_index]
        rfkill_idx = get_rfkill_index(selected_adapter['hci_id'])

        if rfkill_idx is None:
            dialog.ok("错误", f"未在 rfkill 列表中找到 {selected_adapter['hci_id']}。")
            # 错误处理后继续循环，回到一级菜单
            continue

        # 构建二级菜单选项
        if selected_adapter['has_name']:
            # 当前可用 -> 提供禁用选项
            sub_options = [
                "长期禁用 (重启后仍然禁用)", 
                "临时禁用 (重启后恢复)", 
                "取消"
            ]
            title = f"操作: {selected_adapter['hci_id']} (当前: 可用)"
        else:
            # 当前已禁用 -> 提供启用选项
            sub_options = [
                "长期启用 (重启仍然可用)", 
                "临时启用 (重启后恢复禁用)", 
                "取消"
            ]
            title = f"操作: {selected_adapter['hci_id']} (当前: 已禁用)"

        # 弹出二级选择窗口
        sub_selected_index = dialog.select(title, sub_options)
        
        # 无论用户选择什么，如果不执行操作，直接回到一级菜单
        if sub_selected_index == -1 or sub_selected_index == 2:
            continue
        
        # --- 执行实际操作 ---
        action_desc = ""
        if selected_adapter['has_name']:
            # 执行禁用逻辑
            if sub_selected_index == 0:
                # 长期禁用
                subprocess.run(['rfkill', 'block', rfkill_idx])
                xbmc.executebuiltin('Skin.SetString(btdisable,1)')
                xbmc.executebuiltin(f'Skin.SetString(bttype,{selected_adapter["bus"]})')
                action_desc = "已长期禁用"
            elif sub_selected_index == 1:
                # 临时禁用
                subprocess.run(['rfkill', 'block', rfkill_idx])
                action_desc = "已临时禁用"
        else:
            # 执行启用逻辑
            if sub_selected_index == 0:
                # 长期启用
                subprocess.run(['rfkill', 'unblock', rfkill_idx])
                xbmc.executebuiltin('Skin.SetString(btdisable,0)')
                xbmc.executebuiltin('Skin.SetString(bttype,)')
                action_desc = "已长期启用"
            elif sub_selected_index == 1:
                # 临时启用
                subprocess.run(['rfkill', 'unblock', rfkill_idx])
                action_desc = "已临时启用"

        if action_desc:
            # 显示操作成功提示
            dialog.notification("提示", action_desc, time=1000)
            
            # 【关键优化】等待系统状态同步
            # rfkill 执行后，蓝牙协议栈需要时间更新状态（如 Name 字段的消失/出现）
            # 这里等待 2 秒，确保下次循环获取 hciconfig 时能读到最新状态
            xbmc.sleep(700)

def handle_start():
    """处理 start 参数：根据 Skin.String(bttype) 自动阻断对应蓝牙"""
    # 获取 Skin 中设置的 bttype
    target_bus = xbmc.getInfoLabel('Skin.String(bttype)').strip()
    
    # 如果未找到或为空，静默关闭
    if not target_bus:
        return

    hciconfig_output = get_hciconfig_output()
    if not hciconfig_output:
        return

    # 解析 hciconfig 输出，寻找 Bus 字段匹配 target_bus 的条目
    adapter_blocks = re.split(r'(?=^hci\d+:)', hciconfig_output, flags=re.MULTILINE)
    
    target_hci_id = None
    for block in adapter_blocks:
        if not block.strip():
            continue
            
        # 检查 Bus 字段
        bus_match = re.search(r'Bus:\s*(\S+)', block)
        if bus_match and bus_match.group(1) == target_bus:
            # 提取 hci 序号
            hci_match = re.match(r'(hci\d+):', block)
            if hci_match:
                target_hci_id = hci_match.group(1)
                break

    # 如果未找到匹配的适配器，静默关闭
    if not target_hci_id:
        return

    # 获取 rfkill 序号
    rfkill_idx = get_rfkill_index(target_hci_id)
    
    if rfkill_idx:
        # 执行 rfkill block
        subprocess.run(['rfkill', 'block', rfkill_idx])
        xbmc.log(f"[selectbt.py] Blocked Bluetooth adapter {target_hci_id} (rfkill index {rfkill_idx})", xbmc.LOGINFO)

def main():
    if len(sys.argv) < 2:
        return

    action = sys.argv[1]
    
    if action == 'setup':
        handle_setup()
    elif action == 'start':
        handle_start()

if __name__ == '__main__':
    main()
