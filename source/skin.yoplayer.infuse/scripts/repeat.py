import xbmc
import xbmcgui
import json

def get_active_player_id():
    """
    通过 JSON-RPC 获取当前活跃的播放器 ID。
    如果有多个，优先返回音频播放器。
    如果没有，返回 None。
    """
    json_request = {
        "jsonrpc": "2.0",
        "method": "Player.GetActivePlayers",
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(json_request))
    response_data = json.loads(response)

    if "result" in response_data and response_data["result"]:
        # 优先选择音频播放器
        for player in response_data["result"]:
            if player["type"] == "audio":
                xbmc.log(f"[repeat.py] 检测到活跃的音频播放器，ID: {player['playerid']}", level=xbmc.LOGINFO)
                return player["playerid"]
        # 如果没有音频播放器，则返回第一个视频播放器
        xbmc.log(f"[repeat.py] 检测到活跃的视频播放器，ID: {response_data['result'][0]['playerid']}", level=xbmc.LOGINFO)
        return response_data["result"][0]["playerid"]
    
    xbmc.log(f"[repeat.py] 未检测到任何活跃的播放器", level=xbmc.LOGWARNING)
    return None

# 主逻辑
if __name__ == "__main__":
    xbmc.log(f"[repeat.py] 脚本开始执行", level=xbmc.LOGINFO)
    
    # 步骤1: 执行循环模式切换
    xbmc.executebuiltin("PlayerControl(Repeat)")
    xbmc.log(f"[repeat.py] 已发送 PlayerControl(Repeat) 切换指令", level=xbmc.LOGINFO)
    
    # 步骤2: 等待状态更新
    delay_ms = 300
    xbmc.sleep(delay_ms)
    xbmc.log(f"[repeat.py] 等待 {delay_ms}ms 后获取状态", level=xbmc.LOGINFO)

    # 步骤3: 获取当前活跃的播放器 ID
    player_id = get_active_player_id()
    if player_id is None:
        xbmcgui.Dialog().notification("循环模式", "没有活跃的播放器", xbmcgui.NOTIFICATION_ERROR, 2000)
        xbmc.log(f"[repeat.py] 脚本执行中止：没有活跃的播放器", level=xbmc.LOGINFO)
        # 退出脚本
        exit()

    # 步骤4: 使用正确的 PlayerID 通过 JSON-RPC 获取循环状态
    json_request = {
        "jsonrpc": "2.0",
        "method": "Player.GetProperties",
        "params": {
            "playerid": player_id,
            "properties": ["repeat"]
        },
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(json_request))
    
    # 步骤5: 解析响应并显示通知
    try:
        response_data = json.loads(response)
        repeat_state = response_data['result']['repeat']
        
        message_map = {'all': '播放列表整体循环', 'one': '单曲循环', 'off': '循环已关闭'}
        message = message_map.get(repeat_state, '循环状态未知')
        
        xbmc.log(f"[repeat.py] 获取到循环状态: {repeat_state} -> 显示通知: {message}", level=xbmc.LOGINFO)
        
    except Exception as e:
        message = "无法获取循环状态"
        xbmc.log(f"[repeat.py] 解析 JSON-RPC 响应失败: {e}", level=xbmc.LOGERROR)

    xbmcgui.Dialog().notification("循环模式", message, xbmcgui.NOTIFICATION_INFO, 2000)
    
    xbmc.log(f"[repeat.py] 脚本执行完成", level=xbmc.LOGINFO)