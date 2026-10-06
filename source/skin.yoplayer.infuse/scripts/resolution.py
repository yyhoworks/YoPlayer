import xbmc
import json
import time
import threading

LOG_PREFIX = "[ResScript]"

def log(msg):
    """统一日志输出格式"""
    xbmc.log("{} {}".format(LOG_PREFIX, msg), xbmc.LOGINFO)

def get_rpc_payload():
    """构建 JSON-RPC 请求体"""
    return json.dumps({
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {
            "setting": "videoscreen.screenmode",
            "value": "0192001080060.00000pstd"
        },
        "id": 1
    })

def check_resolution():
    """检查当前分辨率是否包含 1080"""
    res = xbmc.getInfoLabel('System.ScreenResolution')
    log("Current System.ScreenResolution: '{}'".format(res))
    return '1080' in res

def send_rpc_async():
    """在后台线程发送 RPC，避免主线程阻塞导致错过弹窗监测"""
    log("Sending JSON-RPC in background thread...")
    
    def _send():
        try:
            resp = xbmc.executeJSONRPC(get_rpc_payload())
            log("RPC background response: {}".format(resp))
        except Exception as e:
            log("RPC background error: {}".format(str(e)))
    
    t = threading.Thread(target=_send)
    t.daemon = True
    t.start()

def monitor_and_confirm():
    """监测 yesnodialog 窗口，当可见时执行焦点和确认操作"""
    log("Starting to monitor for yesnodialog...")
    start_time = time.time()
    timeout = 25.0  # 给予充足的超时时间以应对硬件切换延迟
    
    while time.time() - start_time < timeout:
        # 兼容不同 Kodi 版本的窗口 ID (yesnodialog / 10100 / 100)
        if xbmc.getCondVisibility('Window.IsVisible(yesnodialog) | Window.IsVisible(10100) | Window.IsVisible(100)'):
            log(">>> yesnodialog DETECTED!")
            
            # 延时 0.5 秒执行 setfocus(11)
            log("Waiting 0.5s before SetFocus(11)...")
            time.sleep(0.5)
            xbmc.executebuiltin('SetFocus(11)')
            log("SetFocus(11) executed.")
            
            # 延时 0.3 秒执行 Action(select)
            log("Waiting 0.3s before Action(select)...")
            time.sleep(0.3)
            xbmc.executebuiltin('Action(select)')
            log("Action(select) executed.")
            return True
            
        # 高频轮询，每 0.1 秒检查一次
        time.sleep(0.1)
        
    log("Warning: yesnodialog not detected within {}s timeout.".format(timeout))
    return False

def main():
    log("=== Script Started ===")
    
    # 1. 检查初始分辨率，如果已经是 1080 则直接关闭
    if check_resolution():
        log("Resolution already contains '1080'. Closing script.")
        return
        
    # 2. 第一次执行 RPC 并监测弹窗
    log("--- Attempt 1 ---")
    send_rpc_async()
    monitor_and_confirm()
    
    # 3. 延时 1 秒后检查分辨率
    log("Waiting 1.0s before checking resolution...")
    time.sleep(1.0)
    
    if check_resolution():
        log("Resolution successfully changed to 1080. Closing script.")
        return
        
    # 4. 如果不包含 1080，延时 1 秒后再次执行 RPC
    log("Resolution does not contain '1080'. Waiting 1.0s before retry...")
    time.sleep(1.0)
    
    log("--- Attempt 2 ---")
    send_rpc_async()
    monitor_and_confirm()
    
    log("=== Script Finished ===")

if __name__ == '__main__':
    main()