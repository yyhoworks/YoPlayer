import xbmc
import xbmcaddon
import sys

def main():
    # 获取命令行参数
    args = sys.argv
    
    if len(args) < 2:
        # 如果没有参数，则退出
        return
    
    action = args[1]
    
    if action == "play":
        # 设置皮肤字符串 musicbutton 为 0
        xbmc.executebuiltin('Skin.SetString(musicbutton,0)')
        # 设置焦点到控件ID 110
        xbmc.executebuiltin('SetFocus(110)')
        
    elif action == "lrc":
        # 设置皮肤字符串 musicbutton 为 1
        xbmc.executebuiltin('Skin.SetString(musicbutton,1)')
        # 设置焦点到控件ID 1100
        xbmc.executebuiltin('SetFocus(1100)')
    
    # 脚本执行完毕自动退出

if __name__ == "__main__":
    main()