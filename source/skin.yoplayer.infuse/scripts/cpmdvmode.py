import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
import os
import sys

def get_setting_value(root, setting_id):
    """
    从XML根节点中查找指定ID的setting值
    :param root: XML根节点（Element对象）
    :param setting_id: 要查找的setting的id属性值
    :return: setting的文本值（去除前后空格），未找到返回None
    """
    for setting in root.findall('setting'):
        if setting.get('id') == setting_id:
            return setting.text.strip() if setting.text else None
    return None

def update_skin_settings():
    """
    执行原始逻辑，根据guisettings.xml更新皮肤字符串。
    """
    # 1. 定义路径并检测优先顺序
    coreelec_path = '/storage/.kodi/userdata/guisettings.xml'
    # 使用 xbmcvfs.translatePath 替代 xbmc.translatePath
    kodi_path = xbmcvfs.translatePath('special://userdata/guisettings.xml')
    final_path = None

    if os.path.isfile(coreelec_path):
        final_path = coreelec_path
        xbmc.log(f"[DV Mode Script] 检测到CoreELEC系统，使用路径：{final_path}", level=xbmc.LOGINFO)
    elif os.path.isfile(kodi_path):
        final_path = kodi_path
        xbmc.log(f"[DV Mode Script] 检测到Kodi系统，使用路径：{final_path}", level=xbmc.LOGINFO)
    else:
        xbmc.log(f"[DV Mode Script] 错误：未找到guisettings.xml文件（CoreELEC路径：{coreelec_path}，Kodi路径：{kodi_path}）", level=xbmc.LOGERROR)
        return

    # 2. 解析XML文件
    try:
        tree = ET.parse(final_path)
        root = tree.getroot()
    except ET.ParseError as e:
        xbmc.log(f"[DV Mode Script] 错误：解析guisettings.xml失败（格式错误）：{str(e)}", level=xbmc.LOGERROR)
        return
    except Exception as e:
        xbmc.log(f"[DV Mode Script] 错误：读取guisettings.xml失败：{str(e)}", level=xbmc.LOGERROR)
        return

    # --- 新增逻辑开始 ---
    # 检查视频刷新率自动调整设置
    refresh_rate_value = get_setting_value(root, 'videoplayer.adjustrefreshrate')
    xbmc.log(f"[DV Mode Script] 找到videoplayer.adjustrefreshrate的值：{refresh_rate_value}", level=xbmc.LOGINFO)

    if refresh_rate_value == '0':
        xbmc.executebuiltin('Skin.SetString(refreshrate,关闭)')
        xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(refreshrate,关闭)", level=xbmc.LOGINFO)
    elif refresh_rate_value == '1':
        xbmc.executebuiltin('Skin.SetString(refreshrate,始终)')
        xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(refreshrate,始终)", level=xbmc.LOGINFO)
    elif refresh_rate_value == '2':
        xbmc.executebuiltin('Skin.SetString(refreshrate,自适应)')
        xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(refreshrate,起播和停止)", level=xbmc.LOGINFO)
    elif refresh_rate_value == '3':
        xbmc.executebuiltin('Skin.SetString(refreshrate,起播时)')
        xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(refreshrate,起播)", level=xbmc.LOGINFO)
    else:
        xbmc.log(f"[DV Mode Script] 警告：未知的videoplayer.adjustrefreshrate值：{refresh_rate_value}", level=xbmc.LOGWARNING)
    # --- 新增逻辑结束 ---

    # 3. 处理第一个设置：coreelec.amlogic.dolbyvision.mode
    mode_value = get_setting_value(root, 'coreelec.amlogic.dolbyvision.mode')
    xbmc.log(f"[DV Mode Script] 找到coreelec.amlogic.dolbyvision.mode的值：{mode_value}", level=xbmc.LOGINFO)

    if mode_value == '2':
        # 模式为2 → 设置cpmdvmode为"关闭"，并将cpmvsvdb设为空字符串
        xbmc.executebuiltin('Skin.SetString(cpmdvmode,关闭)')
        xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmdvmode,关闭)", level=xbmc.LOGINFO)
        
        xbmc.executebuiltin('Skin.SetString(cpmvsvdb,"")')
        xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmvsvdb,"")", level=xbmc.LOGINFO)
    else:
        # 模式不为2 → 处理第二个设置：coreelec.amlogic.dolbyvision.type
        type_value = get_setting_value(root, 'coreelec.amlogic.dolbyvision.type')
        xbmc.log(f"[DV Mode Script] 找到coreelec.amlogic.dolbyvision.type的值：{type_value}", level=xbmc.LOGINFO)

        if type_value == '0':
            xbmc.executebuiltin('Skin.SetString(cpmdvmode,DV-std)')
            xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmdvmode,DV-Std)", level=xbmc.LOGINFO)
        elif type_value == '1':
            xbmc.executebuiltin('Skin.SetString(cpmdvmode,DV-LL)')
            xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmdvmode,DV-LL)", level=xbmc.LOGINFO)
        elif type_value == '2':
            xbmc.executebuiltin("Skin.SetString(cpmdvmode,PL-HDR)")
            xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmdvmode,'播放器主导HDR')", level=xbmc.LOGINFO)
        elif type_value == '3':
            xbmc.executebuiltin("Skin.SetString(cpmdvmode,VS10 Only)")
            xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmdvmode,'VS10 Only')", level=xbmc.LOGINFO)
        else:
            xbmc.log(f"[DV Mode Script] 警告：未知的coreelec.amlogic.dolbyvision.type值：{type_value}", level=xbmc.LOGWARNING)

        # 处理第三个设置：coreelec.amlogic.dolbyvision.vsvdb.inject
        vsvdb_value = get_setting_value(root, 'coreelec.amlogic.dolbyvision.vsvdb.inject')
        xbmc.log(f"[DV Mode Script] 找到coreelec.amlogic.dolbyvision.vsvdb.inject的值：{vsvdb_value}", level=xbmc.LOGINFO)

        if vsvdb_value and vsvdb_value.lower() == 'true':
            xbmc.executebuiltin('Skin.SetString(cpmvsvdb,ON)')
            xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmvsvdb,ON)", level=xbmc.LOGINFO)
        else:
            xbmc.executebuiltin('Skin.SetString(cpmvsvdb,OFF)')
            xbmc.log(f"[DV Mode Script] 执行命令：Skin.SetString(cpmvsvdb,OFF)", level=xbmc.LOGINFO)

def main():
    """
    主函数，负责解析命令行参数并分支执行逻辑。
    """
    # --- 新增：处理命令行参数 ---
    if len(sys.argv) > 1 and sys.argv[1] == 'dvset':
        xbmc.log(f"[DV Mode Script] 检测到参数 'dvset'，进入设置模式。", level=xbmc.LOGINFO)
        
        supported_hdr_types = xbmc.getInfoLabel('System.SupportedHDRTypes')
        xbmc.log(f"[DV Mode Script] 检测到支持的HDR类型: '{supported_hdr_types}'", level=xbmc.LOGINFO)

        # 预先解析当前设置（使用同样的路径检测逻辑）
        current_mode = None
        current_type = None
        current_vsvdb = None
        coreelec_path = '/storage/.kodi/userdata/guisettings.xml'
        # 使用 xbmcvfs.translatePath 替代 xbmc.translatePath
        kodi_path = xbmcvfs.translatePath('special://userdata/guisettings.xml')
        final_path = coreelec_path if os.path.isfile(coreelec_path) else kodi_path

        if os.path.isfile(final_path):
            try:
                tree = ET.parse(final_path)
                root = tree.getroot()
                current_mode = get_setting_value(root, 'coreelec.amlogic.dolbyvision.mode')
                current_type = get_setting_value(root, 'coreelec.amlogic.dolbyvision.type')
                current_vsvdb = get_setting_value(root, 'coreelec.amlogic.dolbyvision.vsvdb.inject')
            except Exception as e:
                xbmc.log(f"[DV Mode Script] 警告：解析设置文件失败。错误: {e}", level=xbmc.LOGWARNING)

        if not supported_hdr_types:
            xbmc.log(f"[DV Mode Script] 显示设备不支持HDR或杜比视界。", level=xbmc.LOGINFO)
            dialog = xbmcgui.Dialog()
            dialog.ok("杜比视界设置", "自动检测到您的显示设备不支持HDR和杜比视界，请手动操作杜比视界设置项核实！")
            xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
        
        elif "Dolby Vision" in supported_hdr_types:
            xbmc.log(f"[DV Mode Script] 显示设备支持杜比视界。", level=xbmc.LOGINFO)
            
            options = []
            opt1 = "电视主导(DV-std)"
            opt2 = "关闭杜比视界"
            if current_mode == '2':
                opt2 += " - 当前选项"
            else:
                if current_type == '0':
                    opt1 += " - 当前选项"
            options.append(opt1)
            options.append(opt2)
            options.append("手动设置杜比视界")

            dialog = xbmcgui.Dialog()
            choice = dialog.select("选择杜比视界模式", options)

            if choice == 0: # 用户选择了 "电视主导(DV-std)"
                xbmc.log(f"[DV Mode Script] 用户选择切换到 '电视主导(DV-std)'。", level=xbmc.LOGINFO)

                # 第一步：获取当前mode值，分两种情况处理
                if current_mode == '2':
                    xbmc.log(f"[DV Mode Script] 情况1：当前mode为'2'（关闭），执行启用并切换逻辑。", level=xbmc.LOGINFO)
                    # 1. 导航到杜比视界主开关页面（保持500ms延时）
                    xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
                    xbmc.sleep(500)
                    # 2. 执行一次select启用杜比视界（从关闭→自动）（同一页面内改为250ms）
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    
                    # 3. 根据当前type值执行切换到DV-std的逻辑
                    if current_type == '0':
                        xbmc.log(f"[DV Mode Script] 当前type已为'0'（DV-std），无需切换模式。", level=xbmc.LOGINFO)
                    elif current_type == '1': # 当前为DV-LL（type=1）
                        xbmc.log(f"[DV Mode Script] 当前type为'1'（DV-LL），切换到DV-std。", level=xbmc.LOGINFO)
                        # 导航到type选项（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(down)')
                        xbmc.sleep(250)
                        # 执行一次select切换（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                    elif current_type == '2': # 当前为PL-HDR（type=2）
                        xbmc.log(f"[DV Mode Script] 当前type为'2'（PL-HDR），切换到DV-std。", level=xbmc.LOGINFO)
                        # 导航到type选项（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(down)')
                        xbmc.sleep(250)
                        # 执行两次select切换（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                    elif current_type == '3': # 当前为VS10 Only（type=3）
                        xbmc.log(f"[DV Mode Script] 当前type为'3'（VS10 Only），切换到DV-std。", level=xbmc.LOGINFO)
                        # 导航到type选项（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(down)')
                        xbmc.sleep(250)
                        # 执行三次select切换（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                    
                    # 4. 检查VSVDB注入状态并处理
                    if current_vsvdb and current_vsvdb.lower() == 'true':
                        xbmc.log(f"[DV Mode Script] VSVDB注入为开启，执行关闭操作。", level=xbmc.LOGINFO)
                        # 向下导航到VSVDB选项（同一页面内改为250ms）
                        down_presses = 1 if current_type != '0' else 2
                        for _ in range(down_presses):
                            xbmc.executebuiltin('Action(down)')
                            xbmc.sleep(250)
                        # 执行select关闭VSVDB（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(select)')
                        xbmc.sleep(250)
                    else:
                        xbmc.log(f"[DV Mode Script] VSVDB注入已为关闭，无需操作。", level=xbmc.LOGINFO)
                    
                    # 5. 返回主页（保持500ms延时）
                    xbmc.log(f"[DV Mode Script] 操作完成，返回主页...", level=xbmc.LOGINFO)
                    for _ in range(3):
                        xbmc.executebuiltin('Action(back)')
                        xbmc.sleep(500)

                else: # current_mode不为'2'（已启用，可能为0或1）
                    xbmc.log(f"[DV Mode Script] 情况2：当前mode不为'2'（已启用），直接切换逻辑。", level=xbmc.LOGINFO)
                    
                    # 1. 根据当前type值分情况处理
                    if current_type == '0':
                        xbmc.log(f"[DV Mode Script] 当前已为电视主导（type=0），检查VSVDB注入状态。", level=xbmc.LOGINFO)
                        # 检查VSVDB注入值
                        if current_vsvdb and current_vsvdb.lower() == 'true':
                            xbmc.log(f"[DV Mode Script] VSVDB注入为开启，导航至VSVDB设置页面关闭。", level=xbmc.LOGINFO)
                            # 直接导航到VSVDB选项（保持500ms延时）
                            xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -171, 2)')
                            xbmc.sleep(500)
                            # 执行select关闭VSVDB（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            # 返回主页（保持500ms延时）
                            for _ in range(3):
                                xbmc.executebuiltin('Action(back)')
                                xbmc.sleep(500)
                        else:
                            xbmc.log(f"[DV Mode Script] 当前已为电视主导且VSVDB注入关闭，无需操作。", level=xbmc.LOGINFO)
                    
                    else: # current_type不为'0'，需要切换到type=0
                        xbmc.log(f"[DV Mode Script] 当前type不为'0'，导航至type设置页面切换。", level=xbmc.LOGINFO)
                        # 1. 导航到type选项页面（保持500ms延时）
                        xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -172, 2)')
                        xbmc.sleep(500)
                        
                        # 2. 根据当前type值切换到电视主导（type=0）
                        if current_type == '1': # 当前为DV-LL（type=1）
                            xbmc.log(f"[DV Mode Script] 当前type为'1'（DV-LL），切换到DV-std。", level=xbmc.LOGINFO)
                            # 执行一次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        elif current_type == '2': # 当前为PL-HDR（type=2）
                            xbmc.log(f"[DV Mode Script] 当前type为'2'（PL-HDR），切换到DV-std。", level=xbmc.LOGINFO)
                            # 执行两次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        elif current_type == '3': # 当前为VS10 Only（type=3）
                            xbmc.log(f"[DV Mode Script] 当前type为'3'（VS10 Only），切换到DV-std。", level=xbmc.LOGINFO)
                            # 执行三次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        
                        # 3. 检查VSVDB注入状态并处理
                        if current_vsvdb and current_vsvdb.lower() == 'true':
                            xbmc.log(f"[DV Mode Script] VSVDB注入为开启，执行关闭操作。", level=xbmc.LOGINFO)
                            # 向下导航到VSVDB选项（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(down)')
                            xbmc.sleep(250)
                            # 执行select关闭VSVDB（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        else:
                            xbmc.log(f"[DV Mode Script] VSVDB注入已为关闭，无需操作。", level=xbmc.LOGINFO)
                        
                        # 4. 返回主页（保持500ms延时）
                        xbmc.log(f"[DV Mode Script] 操作完成，返回主页...", level=xbmc.LOGINFO)
                        for _ in range(3):
                            xbmc.executebuiltin('Action(back)')
                            xbmc.sleep(500)

            elif choice == 1: # 用户选择了 "关闭杜比视界"
                xbmc.log(f"[DV Mode Script] 用户选择 '关闭杜比视界'。", level=xbmc.LOGINFO)

                # --- 关闭杜比视界的逻辑 ---
                if current_mode == '0':
                    xbmc.log(f"[DV Mode Script] 当前模式为'自动'，导航至设置页面关闭...", level=xbmc.LOGINFO)
                    # 导航到设置页面（保持500ms延时）
                    xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
                    xbmc.sleep(500)
                    # 执行select（同一页面内改为250ms）
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    # 返回主页（保持500ms延时）
                    for _ in range(3):
                        xbmc.executebuiltin('Action(back)')
                        xbmc.sleep(500)
                elif current_mode == '1':
                    xbmc.log(f"[DV Mode Script] 当前模式为'开启'，导航至设置页面关闭...", level=xbmc.LOGINFO)
                    # 导航到设置页面（保持500ms延时）
                    xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
                    xbmc.sleep(500)
                    # 执行两次select（同一页面内改为250ms）
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    # 返回主页（保持500ms延时）
                    for _ in range(3):
                        xbmc.executebuiltin('Action(back)')
                        xbmc.sleep(500)
                elif current_mode == '2':
                    xbmc.log(f"[DV Mode Script] 当前已为'关闭'模式，无需操作。", level=xbmc.LOGINFO)
                else:
                    xbmc.log(f"[DV Mode Script] 警告：未知的mode值 '{current_mode}'，无法执行关闭操作。", level=xbmc.LOGWARNING)
            
            elif choice == 2: # 用户选择了 "手动设置杜比视界"
                xbmc.log(f"[DV Mode Script] 用户选择 '手动设置杜比视界'。", level=xbmc.LOGINFO)
                xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')

        else: # 支持HDR，但不支持杜比视界
            xbmc.log(f"[DV Mode Script] 显示设备支持HDR，但不支持杜比视界。", level=xbmc.LOGINFO)
            
            options = []
            opt1 = "播放器主导(HDR)"
            opt2 = "关闭杜比视界"
            if current_mode == '2':
                opt2 += " - 当前选项"
            else:
                if current_type == '2':
                    opt1 += " - 当前选项"
            options.append(opt1)
            options.append(opt2)
            options.append("手动设置杜比视界")

            dialog = xbmcgui.Dialog()
            choice = dialog.select("选择HDR模式", options)

            if choice == 0: # 用户选择了 "播放器主导(HDR)"
                xbmc.log(f"[DV Mode Script] 用户选择切换到 '播放器主导(HDR)'。", level=xbmc.LOGINFO)

                # 第一步：获取当前mode值，分两种情况处理
                if current_mode == '2':
                    xbmc.log(f"[DV Mode Script] 情况1：当前mode为'2'（关闭），执行启用并切换逻辑。", level=xbmc.LOGINFO)
                    # 1. 导航到杜比视界主开关页面（保持500ms延时）
                    xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
                    xbmc.sleep(500)
                    # 2. 执行一次select启用杜比视界（同一页面内改为250ms）
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    
                    # 3. 根据当前type值执行后续操作
                    if current_type == '2':
                        xbmc.log(f"[DV Mode Script] 当前type为'2'（已为播放器主导），检查VSVDB注入状态。", level=xbmc.LOGINFO)
                        # 检查VSVDB注入值
                        if current_vsvdb and current_vsvdb.lower() == 'false':
                            xbmc.log(f"[DV Mode Script] VSVDB注入为关闭，执行开启操作。", level=xbmc.LOGINFO)
                            # 两次down导航到VSVDB选项（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(down)')
                            xbmc.sleep(250)
                            xbmc.executebuiltin('Action(down)')
                            xbmc.sleep(250)
                            # 开启VSVDB注入（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        else:
                            xbmc.log(f"[DV Mode Script] VSVDB注入已为开启，返回主页。", level=xbmc.LOGINFO)
                        # 无论VSVDB是否操作，都返回主页（保持500ms延时）
                        for _ in range(3):
                            xbmc.executebuiltin('Action(back)')
                            xbmc.sleep(500)
                    
                    else: # current_type不为'2'
                        xbmc.log(f"[DV Mode Script] 当前type不为'2'，执行切换到播放器主导逻辑。", level=xbmc.LOGINFO)
                        # 1. down导航到type选项（同一页面内改为250ms）
                        xbmc.executebuiltin('Action(down)')
                        xbmc.sleep(250)
                        
                        # 2. 根据type具体值切换到播放器主导（type=2）
                        if current_type == '1': # 当前为DV-LL（type=1）
                            xbmc.log(f"[DV Mode Script] 当前type为'1'（DV-LL），切换到播放器主导。", level=xbmc.LOGINFO)
                            # 执行两次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        elif current_type == '3': # 当前为VS10 Only（type=3）
                            xbmc.log(f"[DV Mode Script] 当前type为'3'（VS10 Only），切换到播放器主导。", level=xbmc.LOGINFO)
                            # 执行一次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        
                        # 3. 检查VSVDB注入状态并处理
                        if current_vsvdb and current_vsvdb.lower() == 'false':
                            xbmc.log(f"[DV Mode Script] VSVDB注入为关闭，执行开启操作。", level=xbmc.LOGINFO)
                            # 向下导航到VSVDB选项（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(down)')
                            xbmc.sleep(250)
                            # 执行select开启VSVDB（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        else:
                            xbmc.log(f"[DV Mode Script] VSVDB注入已为开启，返回主页。", level=xbmc.LOGINFO)
                        
                        # 4. 返回主页（保持500ms延时）
                        for _ in range(3):
                            xbmc.executebuiltin('Action(back)')
                            xbmc.sleep(500)
                
                else: # current_mode不为'2'（已启用，可能为0或1）
                    xbmc.log(f"[DV Mode Script] 情况2：当前mode不为'2'（已启用），直接切换逻辑。", level=xbmc.LOGINFO)
                    
                    # 1. 根据当前type值分情况处理
                    if current_type == '2':
                        xbmc.log(f"[DV Mode Script] 当前已为播放器主导（type=2），检查VSVDB注入状态。", level=xbmc.LOGINFO)
                        # 检查VSVDB注入值
                        if current_vsvdb and current_vsvdb.lower() == 'false':
                            xbmc.log(f"[DV Mode Script] VSVDB注入为关闭，导航至VSVDB设置页面开启。", level=xbmc.LOGINFO)
                            # 直接导航到VSVDB选项（保持500ms延时）
                            xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -171, 2)')
                            xbmc.sleep(500)
                            # 执行select开启VSVDB（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            # 返回主页（保持500ms延时）
                            for _ in range(3):
                                xbmc.executebuiltin('Action(back)')
                                xbmc.sleep(500)
                        else:
                            xbmc.log(f"[DV Mode Script] 当前已为播放器主导且VSVDB注入开启，无需操作。", level=xbmc.LOGINFO)
                    
                    else: # current_type不为'2'，需要切换到type=2
                        xbmc.log(f"[DV Mode Script] 当前type不为'2'，导航至type设置页面切换。", level=xbmc.LOGINFO)
                        # 1. 导航到type选项页面（保持500ms延时）
                        xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -172, 2)')
                        xbmc.sleep(500)
                        
                        # 2. 根据当前type值切换到播放器主导（type=2）
                        if current_type == '1': # 当前为DV-LL（type=1）
                            xbmc.log(f"[DV Mode Script] 当前type为'1'（DV-LL），切换到播放器主导。", level=xbmc.LOGINFO)
                            # 执行两次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        elif current_type == '3': # 当前为VS10 Only（type=3）
                            xbmc.log(f"[DV Mode Script] 当前type为'3'（VS10 Only），切换到播放器主导。", level=xbmc.LOGINFO)
                            # 执行一次select切换（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        
                        # 3. 检查VSVDB注入状态并处理
                        if current_vsvdb and current_vsvdb.lower() == 'false':
                            xbmc.log(f"[DV Mode Script] VSVDB注入为关闭，执行开启操作。", level=xbmc.LOGINFO)
                            # 向下导航到VSVDB选项（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(down)')
                            xbmc.sleep(250)
                            # 执行select开启VSVDB（同一页面内改为250ms）
                            xbmc.executebuiltin('Action(select)')
                            xbmc.sleep(250)
                        else:
                            xbmc.log(f"[DV Mode Script] VSVDB注入已为开启，返回主页。", level=xbmc.LOGINFO)
                        
                        # 4. 返回主页（保持500ms延时）
                        for _ in range(3):
                            xbmc.executebuiltin('Action(back)')
                            xbmc.sleep(500)

            elif choice == 1: # 用户选择了 "关闭杜比视界"
                xbmc.log(f"[DV Mode Script] 用户选择 '关闭杜比视界'。", level=xbmc.LOGINFO)

                # --- 关闭杜比视界的逻辑 ---
                if current_mode == '0':
                    xbmc.log(f"[DV Mode Script] 当前模式为'自动'，导航至设置页面关闭...", level=xbmc.LOGINFO)
                    # 导航到设置页面（保持500ms延时）
                    xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
                    xbmc.sleep(500)
                    # 执行select（同一页面内改为250ms）
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    # 返回主页（保持500ms延时）
                    for _ in range(3):
                        xbmc.executebuiltin('Action(back)')
                        xbmc.sleep(500)
                elif current_mode == '1':
                    xbmc.log(f"[DV Mode Script] 当前模式为'开启'，导航至设置页面关闭...", level=xbmc.LOGINFO)
                    # 导航到设置页面（保持500ms延时）
                    xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')
                    xbmc.sleep(500)
                    # 执行两次select（同一页面内改为250ms）
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(250)
                    # 返回主页（保持500ms延时）
                    for _ in range(3):
                        xbmc.executebuiltin('Action(back)')
                        xbmc.sleep(500)
                elif current_mode == '2':
                    xbmc.log(f"[DV Mode Script] 当前已为'关闭'模式，无需操作。", level=xbmc.LOGINFO)
                else:
                    xbmc.log(f"[DV Mode Script] 警告：未知的mode值 '{current_mode}'，无法执行关闭操作。", level=xbmc.LOGWARNING)
            
            elif choice == 2: # 用户选择了 "手动设置杜比视界"
                xbmc.log(f"[DV Mode Script] 用户选择 '手动设置杜比视界'。", level=xbmc.LOGINFO)
                xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings, -193, 0, -174, 2)')

        # 在用户完成所有设置操作后，更新皮肤显示
        xbmc.log(f"[DV Mode Script] 设置已更改，正在更新皮肤显示...", level=xbmc.LOGINFO)
        update_skin_settings()

    else:
        # --- 原有逻辑：不带参数或参数不是'dvset'时执行 ---
        xbmc.log(f"[DV Mode Script] 未检测到参数 'dvset'，执行常规更新逻辑。", level=xbmc.LOGINFO)
        update_skin_settings()

if __name__ == '__main__':
    main()