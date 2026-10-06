# special://skin/scripts/videozoom.py
import xbmc
import json
import sys
import time

def get_skin_string(property_name):
    """获取皮肤字符串属性值"""
    return xbmc.getInfoLabel(f'Skin.String({property_name})')

def set_skin_string(property_name, value):
    """设置皮肤字符串属性值"""
    xbmc.executebuiltin(f'Skin.SetString({property_name},{value})')

def execute_set_numeric(property_name):
    """执行设置数值的内置函数"""
    xbmc.executebuiltin(f'Skin.SetNumeric({property_name})')

def show_notification(message, time=3000):
    """显示通知消息"""
    xbmc.executebuiltin(f'Notification(视频缩放, {message}, {time}, )')

def execute_zoom_rpc(zoom_value):
    """执行缩放的JSON-RPC命令"""
    target_zoom = zoom_value / 100.0  # 转换为小数形式
    
    # 构建 JSON-RPC 请求（Player.SetViewMode）
    request = {
        "jsonrpc": "2.0",
        "method": "Player.SetViewMode",
        "params": {
            "viewmode": {
                "zoom": target_zoom
            }
        },
        "id": 1
    }
    
    # 通过 xbmc 执行 JSON 命令
    xbmc.executeJSONRPC(json.dumps(request))

def wait_for_valid_input():
    """等待有效的输入值"""
    while True:
        xbmc.sleep(500)  # 等待0.5秒
        zoom_ratio_str = get_skin_string('zoomratio')
        
        # 处理空值情况
        if not zoom_ratio_str or zoom_ratio_str.strip() == '':
            zoom_ratio = 100
        else:
            try:
                zoom_ratio = int(float(zoom_ratio_str))
            except ValueError:
                zoom_ratio = 100  # 默认值
                
        if zoom_ratio != 100 and zoom_ratio != 0:
            # 找到非100的有效值，先清空zoomed状态，然后执行remote模式
            set_skin_string('zoomed', '')
            xbmc.executebuiltin('RunScript(special://skin/scripts/videozoom.py,remote)')
            break

def main():
    # 获取参数
    args = sys.argv[1:]
    mode = args[0] if args else None
    
    if mode == 'remote':
        # 获取皮肤设置的缩放比例
        zoom_ratio_str = get_skin_string('zoomratio')
        
        # 处理空值情况
        if not zoom_ratio_str or zoom_ratio_str.strip() == '':
            zoom_ratio = 100
        else:
            try:
                zoom_ratio = int(float(zoom_ratio_str))
            except ValueError:
                zoom_ratio = 100  # 默认值
        
        if zoom_ratio == 100:
            # 情况1：未设置一键缩放比例
            # 在显示数字输入窗口之前，先设置zoomnumber为1
            set_skin_string('zoomnumber', '1')
            execute_set_numeric('zoomratio')
            show_notification('请设置一键缩放比例', 3000)
            wait_for_valid_input()
            return
        elif 50 <= zoom_ratio <= 200:
            # 情况2：缩放比例在有效范围内
            zoomed_status = get_skin_string('zoomed')
            
            if zoomed_status != '1':
                # 情况2.1：未处于缩放状态
                execute_zoom_rpc(zoom_ratio)
                set_skin_string('zoomed', '1')
                show_notification(f'已将画面比例调整为{zoom_ratio}%', 3000)
                return
            else:
                # 情况2.2：已处于缩放状态，恢复原始比例
                execute_zoom_rpc(100)
                set_skin_string('zoomed', '0')
                show_notification('已将画面调整回原始比例', 3000)
                return
        else:
            # 情况3：缩放比例超限
            set_skin_string('zoomratio', '')
            # 在显示数字输入窗口之前，先设置zoomnumber为1
            set_skin_string('zoomnumber', '1')
            execute_set_numeric('zoomratio')
            show_notification('原设置超限，请重新设置', 3000)
            wait_for_valid_input()
            return
            
    elif mode == 'auto':
        # 获取皮肤设置的缩放比例
        zoom_ratio_str = get_skin_string('zoomratio')
        
        # 处理空值情况
        if not zoom_ratio_str or zoom_ratio_str.strip() == '':
            zoom_ratio = 100
        else:
            try:
                zoom_ratio = int(float(zoom_ratio_str))
            except ValueError:
                zoom_ratio = 100  # 默认值
        
        if zoom_ratio == 100:
            # 缩放比例为100%，直接退出
            return
        elif 50 <= zoom_ratio <= 200:
            # 缩放比例在有效范围内，执行缩放并设置状态为原始比例
            execute_zoom_rpc(100)
            set_skin_string('zoomed', '0')
            return
        else:
            # 缩放比例超限，直接退出
            return
            
    elif mode == 'set':
        # 清空当前值后设置数值
        set_skin_string('zoomratio', '')
        set_skin_string('zoomed', '')
        # 在显示数字输入窗口之前，先设置zoomnumber为1
        set_skin_string('zoomnumber', '1')
        execute_set_numeric('zoomratio')
        show_notification('请设置一键缩放比例', 3000)
        wait_for_valid_input()
        return

if __name__ == "__main__":
    main()