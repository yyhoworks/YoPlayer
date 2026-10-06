import xbmc
import xbmcgui
import time

def main():
    # 定义视图配置列表，包含显示名称和对应的皮肤变量名
    views_config = [
        {"name": "列表视图(基本模式)", "var": "list"},
        {"name": "超宽列表", "var": "widelist"},
        {"name": "三行八列海报墙", "var": "3h8lwall"},
        {"name": "两行六列海报墙", "var": "2h6lwall"},
        {"name": "地平线风格海报", "var": "dipingxian"},
        {"name": "3d效果海报", "var": "3d1poster"},
        {"name": "剧集列表(剧集专用)", "var": "episodeposter"}
    ]

    while True:
        options = []
        
        # 选项1: 全部海报视图设为可用
        options.append("全部海报视图设为可用")
        
        # 选项2-8: 读取当前皮肤变量值并动态生成各个视图的状态选项
        for view in views_config:
            var_name = view["var"]
            # 读取当前皮肤变量的值
            current_val = xbmc.getInfoLabel('Skin.String({})'.format(var_name))
            
            # 判断前缀颜色和文字 (使用Kodi标准颜色标签)
            if current_val == "0":
                prefix = "[COLOR red][禁用][/COLOR]"
            else:
                prefix = "[COLOR green][可用][/COLOR]"
            
            # 按照“前缀-海报视图名称”的格式拼接
            option_text = "{}-{}".format(prefix, view["name"])
            options.append(option_text)
            
        # 选项9: 退出设置窗口
        options.append("退出设置窗口")
        
        # 弹出单选窗口
        dialog = xbmcgui.Dialog()
        selected_index = dialog.select("海报视图设置", options)
        
        # 处理用户选择
        # 如果按返回键(-1) 或 选择最后一项“退出设置窗口”
        if selected_index == -1 or selected_index == len(options) - 1:
            # 探测所有皮肤变量是否都是“0”
            all_zero = True
            for view in views_config:
                val = xbmc.getInfoLabel('Skin.String({})'.format(view["var"]))
                if val != "0":
                    all_zero = False
                    break
            
            # 如果所有变量都是“0”，则将“列表视图(基本模式)”的变量设为“空”
            if all_zero:
                xbmc.executebuiltin('Skin.Reset(list)')
                
            # 执行跳转回主页并退出脚本
            xbmc.executebuiltin('ActivateWindow(Home)')
            break
            
        # 如果选择第一项“全部海报视图设为可用”
        elif selected_index == 0:
            for view in views_config:
                # 将所有视图对应的皮肤变量设为“空”
                xbmc.executebuiltin('Skin.Reset({})'.format(view["var"]))
                
        # 如果选择中间的具体视图选项 (索引 1 到 7)
        else:
            view_index = selected_index - 1
            target_view = views_config[view_index]
            var_name = target_view["var"]
            
            # 重新获取当前值以决定操作
            current_val = xbmc.getInfoLabel('Skin.String({})'.format(var_name))
            
            if current_val == "0":
                # 如果当前为"0"，则设为"空"
                xbmc.executebuiltin('Skin.Reset({})'.format(var_name))
            else:
                # 如果当前为"空"或其他值，则设为"0"
                xbmc.executebuiltin('Skin.SetString({},0)'.format(var_name))
        
        # 选择1-8项后，延时0.5秒，然后进入下一次循环重新探测变量并弹出窗口
        time.sleep(0.5)

if __name__ == '__main__':
    main()