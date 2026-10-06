import xbmc
import sys

def sendclick(click_id):
    """发送点击事件"""
    xbmc.executebuiltin('SendClick({})'.format(click_id))

def action_back():
    """执行返回操作"""
    xbmc.executebuiltin('Action(back)')

def close_dialog(dialog_id):
    """关闭对话框"""
    xbmc.executebuiltin('Dialog.Close({})'.format(dialog_id))

def main():
    # 定义字母与click_id的对应关系
    letter_to_click_id = {
        'a': 140,
        'b': 164,
        'c': 162,
        'd': 142,
        'e': 122,
        'f': 143,
        'g': 144,
        'h': 145,
        'i': 127,
        'j': 146,
        'k': 147,
        'l': 148,
        'm': 166,
        'n': 165,
        'o': 128,
        'p': 129,
        'q': 120,
        'r': 123,
        's': 141,
        't': 124,
        'u': 126,
        'v': 163,
        'w': 121,
        'x': 161,
        'y': 125,
        'z': 160
    }
    
    # 获取命令行参数
    args = sys.argv
    
    if len(args) < 2:
        # 没有参数时退出
        print("No arguments provided")
        return
    
    # 检查是否有字母参数
    letter_found = False
    for arg in args[1:]:
        # 直接检查是否是单个字母参数
        if len(arg) == 1 and arg.lower() in letter_to_click_id:
            letter = arg.lower()
            letter_found = True
            
            # 延迟0.1秒执行Action(back)
            print(f"Waiting 0.1 seconds before executing Action(back) for letter '{letter}'")
            xbmc.sleep(100)
            
            # 执行返回操作
            print(f"Executing Action(back) for letter '{letter}'")
            action_back()
            
            # 再延迟0.2秒
            print("Waiting 0.2 seconds before sending click...")
            xbmc.sleep(200)
            
            # 发送对应字母的点击事件
            click_id = letter_to_click_id[letter]
            print(f"Sending click {click_id} for letter '{letter}'")
            sendclick(click_id)
            
            # 添加额外的日志以便调试
            xbmc.log(f"KODI Input Script: Executed Action(back), then sent click {click_id} for letter {letter}", xbmc.LOGINFO)
            
            # 执行完毕后立即关闭对话框ID 1009
            print("Closing dialog 1009 and exiting script")
            close_dialog(1009)
    
    if not letter_found:
        print("No valid single letter argument found")
        for arg in args[1:]:
            print(f"Argument: {arg}")

if __name__ == '__main__':
    main()