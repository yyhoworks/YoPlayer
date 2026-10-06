import subprocess
import xbmc
import xbmcgui
import xbmcaddon
import os
import sys
import time
from datetime import datetime
import platform

def log_message(message):
    """记录日志消息"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] Network Speed Detector: {message}"
    xbmc.log(log_msg, level=xbmc.LOGINFO)

def set_skin_string(key, value):
    """
    设置皮肤字符串
    """
    try:
        xbmc.executebuiltin(f'Skin.SetString({key},{value})')
        log_message(f"已执行 Skin.SetString({key}, {value})")
    except Exception as e:
        log_message(f"设置皮肤字符串失败: {str(e)}")

def get_current_skin_speed():
    """
    获取当前皮肤字符串 netspeed 的值
    Returns:
        str: 当前皮肤字符串的值
    """
    try:
        val = xbmc.getInfoLabel('Skin.String(netspeed)')
        log_message(f"当前 Skin.String(netspeed) 值: {val}")
        return val
    except Exception as e:
        log_message(f"获取 Skin.String 失败: {str(e)}")
        return ""

def check_system_is_coreelec():
    """
    检测当前系统是否为 CoreELEC
    Returns:
        bool: True 是 CoreELEC, False 不是
    """
    try:
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                if 'coreelec' in content:
                    log_message("检测到系统为 CoreELEC")
                    return True
        log_message("检测到系统非 CoreELEC")
        return False
    except Exception as e:
        log_message(f"检测系统失败: {str(e)}")
        return False

def check_kodi_network_state():
    """
    检测 Kodi 系统层面的网络连接状态
    """
    try:
        link_state = xbmc.getInfoLabel('Network.LinkState')
        # 这里不打印日志，避免等待循环时刷屏
        return link_state
    except Exception as e:
        log_message(f"获取 Network.LinkState 失败: {str(e)}")
        return ""

def check_gitee_connection():
    """
    检查与 gitee.com 的连接状态
    Returns:
        bool: True 表示连接正常, False 表示连接失败
    """
    try:
        log_message("正在 Ping gitee.com ...")
        # -c 1: 发送1个包, -W 5: 超时5秒
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '5', 'gitee.com'], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            log_message("Ping gitee.com 成功")
            return True
        else:
            log_message(f"Ping gitee.com 失败: {result.stderr}")
            return False
    except Exception as e:
        log_message(f"Ping 测试发生异常: {str(e)}")
        return False

def is_physical_interface(interface_name):
    """
    判断接口是否为物理接口
    1. 检查 /sys/class/net/{iface}/device 是否存在 (最可靠的方法)
    2. 检查常见虚拟接口前缀黑名单
    """
    # 黑名单前缀
    virtual_prefixes = ['docker', 'veth', 'br-', 'tun', 'tap', 'virbr', 'vmnet']
    for prefix in virtual_prefixes:
        if interface_name.startswith(prefix):
            return False
            
    # 白名单/常见物理接口前缀 (如果 device 检查失败，可以作为辅助判断，但 device 检查优先)
    # physical_prefixes = ['eth', 'en', 'wlan', 'wl'] 
    
    # 核心判断：物理网卡通常在 /sys/class/net/{iface}/ 下有一个 'device' 符号链接指向硬件驱动
    device_path = f'/sys/class/net/{interface_name}/device'
    if os.path.exists(device_path):
        return True
   
    physical_name_patterns = ['eth', 'en', 'wlan', 'wl', 'ra']
    for pattern in physical_name_patterns:
        if interface_name.startswith(pattern):
            return True
            
    return False

def get_network_interfaces():
    """获取所有物理网络接口列表"""
    interfaces = []
    try:
        if platform.system().lower() == 'linux':
            # 方法1: ls /sys/class/net/
            result = subprocess.run(['ls', '/sys/class/net/'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split()
                for interface in lines:
                    interface = interface.strip()
                    if not interface:
                        continue
                    
                    # 跳过回环
                    if interface == 'lo':
                        continue
                    
                    # 关键优化：只保留物理接口
                    if is_physical_interface(interface):
                        interfaces.append(interface)
                        log_message(f"识别到物理接口: {interface}")
                    else:
                        log_message(f"忽略虚拟/非物理接口: {interface}")
            else:
                # 备用方法: ip link show
                result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ':' in line and 'state' in line:
                            parts = line.split(':')
                            if len(parts) > 1:
                                interface = parts[1].strip()
                                # 清理可能的 @ifN 后缀
                                if '@' in interface:
                                    interface = interface.split('@')[0]
                                
                                if interface and interface != 'lo':
                                    if is_physical_interface(interface):
                                        interfaces.append(interface)
                                        log_message(f"识别到物理接口 (ip link): {interface}")
                                    else:
                                        log_message(f"忽略虚拟/非物理接口 (ip link): {interface}")
    except Exception as e:
        log_message(f"获取网络接口失败: {str(e)}")
    return interfaces

def get_wireless_speed():
    """获取无线网络速度"""
    wireless_speeds = []
    try:
        interfaces = get_network_interfaces()
        for interface in interfaces:
            is_wireless = False
            try:
                result = subprocess.run(['ls', f'/sys/class/net/{interface}/wireless'], capture_output=True, text=True)
                if result.returncode == 0:
                    is_wireless = True
            except:
                if any(x in interface for x in ['wlan', 'wl', 'ra', 'wlp']):
                    is_wireless = True

            if is_wireless:
                log_message(f"检测无线接口 {interface}")
                try:
                    result = subprocess.run(['iw', 'dev', interface, 'link'], capture_output=True, text=True)
                    if result.returncode == 0:
                        output = result.stdout
                        lines = output.split('\n')
                        for line in lines:
                            line_lower = line.lower()
                            if 'tx bitrate:' in line_lower or 'rx bitrate:' in line_lower:
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if 'bitrate' in part.lower() and i+1 < len(parts):
                                        rate_value = parts[i+1]
                                        if 'G' in rate_value.upper():
                                            rate = float(rate_value.replace('G', '').replace('/', '').strip()) * 1000
                                        elif 'M' in rate_value.upper():
                                            rate = float(rate_value.replace('M', '').replace('/', '').strip())
                                        elif 'K' in rate_value.upper():
                                            rate = float(rate_value.replace('K', '').replace('/', '').strip()) / 1000
                                        else:
                                            digits = ''.join(filter(lambda x: x.isdigit() or x == '.', rate_value))
                                            if digits:
                                                rate = float(digits)
                                            else:
                                                continue
                                        rate_int = int(rate)
                                        wireless_speeds.append((interface, rate_int, f"{interface}: {rate_int}mbps (WiFi)"))
                                        break
                except Exception as e:
                    log_message(f"获取无线接口 {interface} 速度失败: {str(e)}")
    except Exception as e:
        log_message(f"获取无线网络速度失败: {str(e)}")
    return wireless_speeds

def get_network_speed():
    """获取网络速度"""
    system = platform.system().lower()
    log_message(f"检测系统: {system}")
    
    if system != 'linux':
        return None, "non_linux_system"

    interfaces = get_network_interfaces()
    log_message(f"发现的物理网络接口: {interfaces}")
    
    if not interfaces:
        return None, "no_interfaces"

    detected_speeds = []

    for interface in interfaces:
        log_message(f"正在检测物理接口 {interface} 的速度")
        
        is_wireless = False
        try:
            result = subprocess.run(['ls', f'/sys/class/net/{interface}/wireless'], capture_output=True, text=True)
            if result.returncode == 0:
                is_wireless = True
        except:
            if any(x in interface for x in ['wlan', 'wl', 'ra', 'wlp']):
                is_wireless = True
                
        if is_wireless:
            continue
            
        speed = None
        source_method = "unknown"
        
        # 1. 优先尝试从 /sys/class/net/{interface}/speed 读取
        speed_file_path = f'/sys/class/net/{interface}/speed'
        if os.path.exists(speed_file_path):
            try:
                with open(speed_file_path, 'r') as f:
                    raw_speed = f.read().strip()
                if raw_speed.isdigit():
                    speed = int(raw_speed)
                    source_method = "sysfs"
                    log_message(f"成功从 {speed_file_path} 读取速度: {speed}mbps")
                elif raw_speed.lower() == 'unknown':
                    log_message(f"接口 {interface} 速度文件内容为 'unknown'，将尝试 ethtool")
                else:
                    log_message(f"接口 {interface} 速度文件内容无效: {raw_speed}，将尝试 ethtool")
            except Exception as e:
                log_message(f"读取 {speed_file_path} 失败: {str(e)}，将尝试 ethtool")
        
        # 2. 只有当 sysfs 读取失败或无效时，才使用 ethtool
        if speed is None:
            try:
                result = subprocess.run(['ethtool', interface], capture_output=True, text=True)
                if result.returncode == 0 and 'No data available' not in result.stdout:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if line.startswith('Speed:'):
                            speed_str = line.split(':')[1].strip()
                            if '1000Mb/s' in speed_str or '1000baseT' in speed_str or '1G' in speed_str:
                                speed = 1000
                            elif '100Mb/s' in speed_str or '100baseT' in speed_str or '100M' in speed_str:
                                speed = 100
                            elif '2.5Gb/s' in speed_str or '2.5G' in speed_str:
                                speed = 2500
                            elif '5Gb/s' in speed_str or '5G' in speed_str:
                                speed = 5000
                            elif '10Gb/s' in speed_str or '10G' in speed_str:
                                speed = 10000
                            elif '10Mb/s' in speed_str or '10baseT' in speed_str or '10M' in speed_str:
                                speed = 10
                            
                            if speed is not None:
                                source_method = "ethtool"
                            break
            except Exception as e:
                log_message(f"执行 ethtool {interface} 失败: {str(e)}")
        
        if speed is not None:
            display_text = f"{interface}: {speed}mbps ({source_method})"
            detected_speeds.append((speed, display_text))
        else:
            log_message(f"无法获取接口 {interface} 的有效速度")

    wireless_speeds = get_wireless_speed()
    for ws in wireless_speeds:
        detected_speeds.append((ws[1], ws[2]))

    if not detected_speeds:
        return None, f"无法检测到网络速度。检测到的接口: {', '.join(interfaces) if interfaces else '无'}"

    # ==========================================
    # 优化逻辑：过滤大于 2600Mbps 的结果，然后在剩余结果中取最大值
    # ==========================================
    log_message(f"原始检测到的速度列表: {detected_speeds}")
    
    # 过滤掉大于 2600Mbps 的速度（目前家用网络极少超过此值，通常是误报或内部高速互联）
    valid_speeds = [item for item in detected_speeds if item[0] <= 2600]
    
    if not valid_speeds:
       
        log_message("警告：所有检测到的接口速度均超过 2600Mbps，已将其全部过滤。")
        return None, "所有接口速度异常 (>2600Mbps)"
        
    log_message(f"过滤后有效的速度列表 (<=2600Mbps): {valid_speeds}")
    
    # 在有效速度中选择最大值
    max_speed_item = max(valid_speeds, key=lambda x: x[0])
    return max_speed_item[0], [ds[1] for ds in valid_speeds]

def run_detection_logic():
    """
    封装具体的检测和判断逻辑，供 start 模式循环调用
    Returns:
        bool: True 表示检测通过（速度>100 且非未连接），False 表示需要重试
    """
    # 1. 检测 Kodi 网络状态
    network_status = check_kodi_network_state()
    
    # --- 情况 B1: 包含"未连接" ---
    if "未连接" in network_status:
        log_message("网络状态包含'未连接'。")
        set_skin_string('netspeed', '未连接')
        # 返回 False 表示需要重试
        return False

    # --- 情况 B2: 包含"已连接" ---
    if "已连接" in network_status:
        log_message("网络状态包含'已连接'，开始检测速度和 Ping。")
        
        # 2. 获取网速
        speed, info = get_network_speed()
        
        # 如果无法获取速度，视为失败，需要重试
        if speed is None:
            return False
            
        speed_text = f"{speed}mbps"
        log_message(f"检测到最高速度: {speed_text}")
        
        # 3. Ping 测试
        gitee_connected = check_gitee_connection()
        
        # 4. 逻辑判断
        is_slow = (speed <= 100)
        is_ping_fail = (not gitee_connected)
        
        # 设置基础皮肤字符串
        set_skin_string('netspeed', speed_text)
        
        # --- 情况 优：速度 > 100 且 Ping 正常 ---
        if not is_slow and not is_ping_fail:
            log_message("网络状况优良。")
            set_skin_string('pingfail', '0')
            return True # 检测通过，无需重试
            
        # --- 情况 差：速度 <= 100 ---
        if is_slow and not is_ping_fail:
            log_message("网速过低 (<=100mbps)。")
            # 返回 False 表示需要重试
            return False
            
        # --- 情况 断：Ping 失败 ---
        if not is_slow and is_ping_fail:
            log_message("Ping 失败。")
            set_skin_string('pingfail', '1')
            return True 
            
        # --- 情况 差+断：速度 <= 100 且 Ping 失败 ---
        if is_slow and is_ping_fail:
            log_message("网速低且 Ping 失败。")
            set_skin_string('pingfail', '1')
            return False # 需要重试

    return False

def main(mode):
    """
    主函数
    Args:
        mode: 运行模式，'start' 或 'refresh'
    """
    log_message(f"开始网络检测流程... (模式: {mode})")
    
    # ==========================================
    # 新增逻辑：等待 Network.LinkState 就绪
    # ==========================================
    log_message("正在等待 Network.LinkState 就绪 (最多等待300秒)...")
    timeout = 300
    elapsed_time = 0
    
    while elapsed_time < timeout:
        current_state = check_kodi_network_state()
        if current_state and current_state != "":
            log_message(f"Network.LinkState 已就绪: {current_state}")
            break
        
        time.sleep(1)
        elapsed_time += 1
        
        # 每60秒打印一次等待日志，避免日志刷屏
        if elapsed_time % 60 == 0:
            log_message(f"等待网络状态中... 已等待 {elapsed_time} 秒")

    if elapsed_time >= timeout:
        log_message(f"错误：等待 Network.LinkState 超时 ({timeout}秒)，脚本退出。")
        return
    # ==========================================
    
    # 1. 检测是否为 CoreELEC 系统
    is_coreelec = check_system_is_coreelec()
    
    # --- 分支 A: 非 CoreELEC 系统 ---
    if not is_coreelec:
        log_message("非 CoreELEC 系统，仅判断连接状态。")
        # 在非CoreELEC系统中增加10秒延迟，让网络完全就绪
        log_message("等待10秒让网络完全就绪...")
        time.sleep(5)
        network_status = check_kodi_network_state()
        log_message(f"获取到的网络状态: {network_status}")
        
        if "已连接" in network_status or ("busy" not in network_status.lower() and network_status != ""):
            set_skin_string('netspeed', '已连接')
        else:
            set_skin_string('netspeed', '未连接')
        
        if mode == "refresh":
             dialog = xbmcgui.Dialog()
             dialog.ok('网络状态刷新', '网络状态已刷新。')
        return

    # --- 分支 B: CoreELEC 系统 ---
    log_message("CoreELEC 系统，执行详细检测。")
    
    # 3. 执行检测逻辑
    if mode == "start":
        # --- start 模式：带重试逻辑 ---
        max_retries = 3
        current_retry = 0
        
        while current_retry < max_retries:
            log_message(f"第 {current_retry + 1} 次尝试检测...")
            
            # 执行检测
            passed = run_detection_logic()
            
            # 检测后，检查皮肤字符串的值
            current_skin_val = get_current_skin_speed()
            
            # 判断是否需要重试
            need_retry = False
            
            if not passed:
                need_retry = True
            elif current_skin_val == "未连接":
                need_retry = True
            elif "mbps" in current_skin_val:
                # 提取数字
                try:
                    speed_num = int(current_skin_val.replace("mbps", "").strip())
                    if speed_num <= 100:
                        need_retry = True
                except:
                    pass
            
            if need_retry and current_retry < max_retries - 1:
                log_message(f"检测结果不理想 ({current_skin_val})，10秒后重试...")
                time.sleep(10)
                current_retry += 1
            else:
                # 成功或者达到最大重试次数，退出循环
                if current_retry == max_retries - 1 and need_retry:
                     log_message("已达到最大重试次数 (3次)，退出脚本。")
                else:
                     log_message("检测完成，退出脚本。")
                break
                
    elif mode == "refresh":
        # --- refresh 模式：直接运行一次，不重试 ---
        run_detection_logic()
        
        # 获取结果用于弹窗
        final_speed_str = get_current_skin_speed()
        is_ping_fail = xbmc.getInfoLabel('Skin.String(pingfail)') == '1'
        
        dialog = xbmcgui.Dialog()
        if "未连接" in final_speed_str:
             dialog.ok('网络状态刷新', '网络未连接，请排查网络问题！')
        elif "mbps" in final_speed_str:
             ping_status = "正常" if not is_ping_fail else "失败"
             dialog.ok('网络状态刷新成功', f'当前网络速度: {final_speed_str}\nGitee 连通: {ping_status}')
        else:
             dialog.ok('网络状态刷新', '网络状态已刷新。')

# --- 脚本入口 ---
if __name__ == '__main__':
    # 检查参数
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # 如果是 start 或 refresh，都执行主逻辑
        if arg == "start":
            main("start")
        elif arg == "refresh":
            main("refresh")
        else:
            xbmc.log("[Network Speed Detector] 未知参数，已静默退出。", level=xbmc.LOGINFO)
    else:
        # 如果没有参数，静默退出
        xbmc.log("[Network Speed Detector] 脚本未通过参数触发，已静默退出。", level=xbmc.LOGINFO) 
