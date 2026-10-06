import xbmc
import xbmcgui
import time

# 打开视频插件窗口
xbmc.executebuiltin('ActivateWindow(Videos,Addons,return)')
time.sleep(0.3)

# 确保列表获得焦点
xbmc.executebuiltin('SendClick(0,0,0)')
time.sleep(0.2)

# 遍历列表查找TMDb Helper
found = False
for i in range(10):  # 假设最多10个项目
    label = xbmc.getInfoLabel('Container.ListItem.Label')
    
    if label and 'tmdb helper' in label.lower():
        found = True
        break
    
    xbmc.executebuiltin('Action(Up)')  # 向下移动
    time.sleep(0.2)

if not found:
    # 未找到插件时输出报错日志
    xbmc.log("未找到TMDb Helper插件", level=xbmc.LOGERROR)
    xbmcgui.Dialog().ok("提示", "未找到TMDb Helper插件")
else:
    # 呼出菜单
    xbmc.executebuiltin('Action(Contextmenu)')
    time.sleep(0.2)
    
    # 选择菜单第一项（信息）
    xbmc.executebuiltin('Action(Select)')
    time.sleep(0.5)  # 等待信息窗口加载完成
    
    # 将焦点聚焦到ID=7的按钮
    xbmc.executebuiltin(f'Control.SetFocus(7)')
    time.sleep(0.2)  # 等待焦点切换完成
    
    # 模拟确认按键
    xbmc.executebuiltin('Action(Select)')
    
    # 检测0.5秒内焦点是否变为ID=11的按钮
    focus_on_11 = False
    
    # 0.5秒内检测（每0.1秒一次，共5次）
    for j in range(5):
        focused_id = xbmc.getInfoLabel('System.CurrentControlId')
        
        if focused_id == '11':
            focus_on_11 = True
            break
        time.sleep(0.1)
    
    if focus_on_11:
        time.sleep(1)  # 延时1秒
    else:
        # 未检测到目标焦点时输出日志
        xbmc.log("未检测到焦点切换到ID=11的按钮", level=xbmc.LOGWARNING)
        xbmc.executebuiltin('Action(Back)')
        time.sleep(0.2)
        xbmc.executebuiltin('ActivateWindow(10035)')
        time.sleep(0.3)