import xbmc
import sys

def main():
    # 获取传递的参数
    param = sys.argv[1] if len(sys.argv) > 1 else None
    
    if param and param == "2abc2":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击102
            xbmc.executebuiltin('SendClick(102)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(102) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击101
            xbmc.executebuiltin('SendClick(101)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(101) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "2abc":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，先执行SendClick(304)，延时50毫秒再执行SendClick(102)，延时50毫秒再执行SendClick(304)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(102)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            
            xbmc.log("'BasePY' found in label '" + label_text + "', custom sequence executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，按原脚本"2abc"逻辑执行
            xbmc.executebuiltin('Action(Shift,Keyboard)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(101)')
            xbmc.sleep(50)
            
            xbmc.log("Original '2abc' logic executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "11":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击101
            xbmc.executebuiltin('SendClick(101)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(101) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击100
            xbmc.executebuiltin('SendClick(100)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(100) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "1u":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，先执行SendClick(304)，延时50毫秒再执行SendClick(129)，延时50毫秒再执行SendClick(304)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(129)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            
            xbmc.log("'BasePY' found in label '" + label_text + "', custom sequence for '1u' executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，先执行SendClick(302)，延时50毫秒再执行SendClick(149)，延时50毫秒再执行SendClick(302)
            xbmc.executebuiltin('SendClick(302)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(149)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(302)')
            
            xbmc.log("'BasePY' not found in label '" + label_text + "', alternative sequence for '1u' executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "1l":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，先执行SendClick(304)，延时50毫秒再执行SendClick(146)，延时50毫秒再执行SendClick(304)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(146)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            
            xbmc.log("'BasePY' found in label '" + label_text + "', custom sequence for '1l' executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，先执行SendClick(302)，延时50毫秒再执行SendClick(169)
            xbmc.executebuiltin('SendClick(169)')
            
            xbmc.log("'BasePY' not found in label '" + label_text + "', alternative sequence for '1l' executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "1r":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，先执行SendClick(304)，延时50毫秒再执行SendClick(148)，延时50毫秒再执行SendClick(304)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(148)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            
            xbmc.log("'BasePY' found in label '" + label_text + "', custom sequence for '1r' executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，先执行SendClick(309)，延时50毫秒再执行SendClick(304)，延时50毫秒再执行SendClick(148)，延时50毫秒再执行SendClick(304)，延时50毫秒再执行SendClick(309)
            xbmc.executebuiltin('SendClick(309)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(148)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(309)')
            
            xbmc.log("'BasePY' not found in label '" + label_text + "', alternative sequence for '1r' executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "1d":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，先执行SendClick(304)，延时50毫秒再执行SendClick(105)，延时50毫秒再执行SendClick(304)
            xbmc.executebuiltin('SendClick(304)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(105)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(304)')
            
            xbmc.log("'BasePY' found in label '" + label_text + "', custom sequence for '1d' executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，先执行SendClick(302)，延时50毫秒再执行SendClick(104)
            xbmc.executebuiltin('SendClick(302)')
            xbmc.sleep(50)
            xbmc.executebuiltin('SendClick(104)')
            
            xbmc.log("'BasePY' not found in label '" + label_text + "', alternative sequence for '1d' executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "3abc3":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击103
            xbmc.executebuiltin('SendClick(103)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(103) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击102
            xbmc.executebuiltin('SendClick(102)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(102) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "4abc4":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击104
            xbmc.executebuiltin('SendClick(104)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(104) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击103
            xbmc.executebuiltin('SendClick(103)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(103) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "5abc5":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击105
            xbmc.executebuiltin('SendClick(105)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(105) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击104
            xbmc.executebuiltin('SendClick(104)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(104) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "6abc6":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击106
            xbmc.executebuiltin('SendClick(106)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(106) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击105
            xbmc.executebuiltin('SendClick(105)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(105) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "7abc7":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击107
            xbmc.executebuiltin('SendClick(107)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(107) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击106
            xbmc.executebuiltin('SendClick(106)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(106) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "8abc8":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击108
            xbmc.executebuiltin('SendClick(108)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(108) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击107
            xbmc.executebuiltin('SendClick(107)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(107) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "9abc9":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击109
            xbmc.executebuiltin('SendClick(109)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(109) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击108
            xbmc.executebuiltin('SendClick(108)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(108) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    elif param and param == "0abc0":
        # 关闭对话框
        xbmc.executebuiltin('Dialog.Close(1009)')
        xbmc.sleep(200)  # 延迟0.2秒
        
        # 获取控件309的标签文本
        label_text = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        # 不区分大小写检查是否包含"BasePY"
        if "basepy" in label_text.lower():
            # 如果包含"BasePY"，发送点击100
            xbmc.executebuiltin('SendClick(100)')
            xbmc.log("'BasePY' found in label '" + label_text + "', SendClick(100) executed", xbmc.LOGINFO)
        else:
            # 如果不包含"BasePY"，发送点击109
            xbmc.executebuiltin('SendClick(109)')
            xbmc.log("'BasePY' not found in label '" + label_text + "', SendClick(109) executed", xbmc.LOGINFO)
        
        # 执行完毕后退出脚本
        return
    else:
        xbmc.log("Script executed without '2abc', '2abc2', '11', '1u', '1l', '1r', '1d', '3abc3', '4abc4', '5abc5', '6abc6', '7abc7', '8abc8', '9abc9' or '0abc0' parameter" if param else "Script executed without parameters", xbmc.LOGINFO)

if __name__ == '__main__':
    main()