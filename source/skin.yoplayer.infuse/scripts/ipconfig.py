import xbmc
import xbmcgui
import time

class BlockingDialog(xbmcgui.WindowXMLDialog):
    def onAction(self, action):
        # 吃掉所有按键事件
        pass

    def onControl(self, control):
        pass

    def onClick(self, controlId):
        pass

# 显示阻塞对话框
dialog = BlockingDialog('DialogConfirm.xml', '')
dialog.show()

try:
    # 1. 打开 CoreELEC 设置
    xbmc.executebuiltin('RunAddon(service.coreelec.settings)')
    time.sleep(0.8)

    # 2. 向下三次
    for _ in range(3):
        xbmc.executebuiltin('Action(Down)')
        time.sleep(0.3)

    # 3. 向右一次
    xbmc.executebuiltin('Action(Right)')
    time.sleep(0.3)

    # 4. 点击确认
    xbmc.executebuiltin('Action(Select)')
    time.sleep(0.8)

    # 5. 向下一次
    xbmc.executebuiltin('Action(Down)')
    time.sleep(0.3)

    # 6. 点击确认
    xbmc.executebuiltin('Action(Select)')
    time.sleep(0.8)

    # 7. 向下一次
    xbmc.executebuiltin('Action(Down)')
    time.sleep(0.3)

    # 8. 向右一次
    xbmc.executebuiltin('Action(Right)')
    time.sleep(0.3)

    # 9. 点击确认
    xbmc.executebuiltin('Action(Select)')
    time.sleep(0.8)

    # 10. 向下一次
    xbmc.executebuiltin('Action(Down)')
    time.sleep(0.3)

    # 11. 点击确认（进入手动配置 IP）
    xbmc.executebuiltin('Action(Select)')

finally:
    # 关闭阻塞对话框，恢复遥控器响应
    dialog.close()