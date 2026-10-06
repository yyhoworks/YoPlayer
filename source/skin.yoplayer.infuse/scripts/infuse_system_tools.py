"""Native TV tool sheet with capability-gated actions and parent focus return."""
import json
import threading
import time
import runpy
import types
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

GROUPS=('显示与播放','网络','日志与诊断','高级维护')


def rpc(method,params):
    response=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})))
    if 'error' in response:raise RuntimeError('原生设置接口不可用')
    return response['result']


def open_native(target, command=None):
    """Called on script thread after our sheet closes, never a Kodi UI callback."""
    monitor=xbmc.Monitor()
    origin=(xbmcgui.getCurrentWindowId(),xbmcgui.getCurrentWindowDialogId())
    xbmc.executebuiltin(command or 'ActivateWindow('+target+')',wait=True)
    current=lambda:(xbmcgui.getCurrentWindowId(),xbmcgui.getCurrentWindowDialogId())
    until=time.monotonic()+5
    while current()==origin:
        if time.monotonic()>until or monitor.waitForAbort(.05):return
    # Follow child pages and modal pickers too; only returning to the actual
    # origin reopens our sheet. Python addon window IDs are allocated at runtime.
    while current()!=origin:
        if monitor.waitForAbort(.1):return


def refresh_mode():
    try:
        value=rpc('Settings.GetSettingValue',{'setting':'videoplayer.adjustrefreshrate'})['value']
        if type(value) is not int or value not in range(4):raise RuntimeError('unknown')
        return value
    except (RuntimeError,KeyError,ValueError):return None


def entries(group):
    from infuse_device import capabilities
    caps=capabilities()
    if group==0:
        mode=refresh_mode()
        rows=[('刷新率匹配','当前：'+(('关闭','始终','起播和停止','起播时')[mode] if mode is not None else '设备未提供'),'refresh-rate','tv-minimal'),
              ('杜比视界一键配置' if caps['coreelec'] else '显示设置','自动检测 / DV-std / DV-LL / HDR-444 / HDR-422' if caps['coreelec'] else '进入设备原生设置','dv' if caps['coreelec'] else 'display','tv-minimal')]
        if caps['coreelec']:rows.append(('显示高级设置','分辨率、色彩及设备原生显示选项','display','tv-minimal'))
        if caps['coreelec']:rows.append(('CoreELEC 设置','网络、蓝牙与设备功能','ce','cog'))
        return rows
    if group==1:
        rows=[('检测网络状态','分别查看局域网、已配置 Emby 与外网','detect','network'),
                        ('媒体读取测速','NAS / 挂载网盘 · 最多 64 MiB / 8 秒','speed','hard-drive'),
                        ('网络设置','当前平台的原生网络与服务设置','ce' if caps['coreelec'] else 'network','network')]
        if caps['coreelec']:rows += [('手动 IP 配置','进入 CoreELEC 网络连接 → IPv4 → 手动','ce','network'),
                                    ('刷新网卡速率信息','等待网络就绪最多 5 分钟；之后检测链路速率','link-info','refresh-cw')]
        return rows
    if group==2:return [('查看运行日志','有界日志尾部 · 筛选、刷新与异常上下文','logs','info'),
                        ('导出诊断包','脱敏日志、版本与必要插件状态','export','folder-plus'),
                        ('分享日志','预览脱敏内容并确认公开目的服务','share','network'),
                        ('Kodi 事件记录','启动、扫描等事件通知（次级入口）','events','info')]
    rows=[('重新载入皮肤','重新加载当前界面 · 执行前确认','reload','refresh-cw'),
          ('从 ZIP 安装插件','打开 Kodi 原生安装入口','zip','puzzle')]
    if caps.get('clean'):rows.append(('释放系统缓存','按需维护，不是常规加速 · 执行前确认','clean','hard-drive'))
    if caps.get('kernel'):rows.append(('内核切换 / 升级','CoreELEC 原有流程 · 执行前确认','kernel','cog'))
    if caps['coreelec']:rows.append(('复位累计运行时间','原有维护流程 · 需确认并重启设备','reset-uptime','info'))
    rows.append(('关于 YoPlayer','版本与更新说明','about','info'))
    return rows


def legacy_dv(script='dvoption.py',argument='set'):
    """Run the unchanged preset chain on this script thread, before returning
    to Tools. Keep each script's argv local and its native dialog semantics.
    """
    allowed={'dvoption.py':'set','dvautoset.py':'option','dvtype.py':'detect'}
    if allowed.get(script)!=argument:raise RuntimeError('Unknown DV action')
    if xbmc.Player().isPlaying():raise RuntimeError('Playback appeared')
    class Native:
        def __getattr__(self,name):return getattr(xbmc,name)
        def executeJSONRPC(self,query):
            if json.loads(query).get('method')=='Settings.SetSettingValue' and xbmc.Player().isPlaying():
                raise RuntimeError('Playback appeared before display change')
            return xbmc.executeJSONRPC(query)
        def executebuiltin(self,command,*args,**kwargs):
            # Only the existing three preset scripts are awaited here. No
            # shared xbmc/sys module is changed and no alternate preset exists.
            for name,arg in allowed.items():
                if command=='RunScript(special://skin/scripts/'+name+','+arg+')':
                    return legacy_dv(name,arg)
            return xbmc.executebuiltin(command,*args,**kwargs)
    path=xbmcvfs.translatePath('special://skin/scripts/'+script)
    namespace=runpy.run_path(path,run_name='yoplayer_dv_legacy')
    def exit_script():raise SystemExit
    namespace['sys']=types.SimpleNamespace(argv=[path,argument],exit=exit_script)
    namespace['xbmc']=Native()
    # run_path returns a copy; the function globals belong to the loaded script.
    namespace['main'].__globals__.update(sys=namespace['sys'],xbmc=namespace['xbmc'])
    try:namespace['main']()
    except SystemExit:pass


def perform(action):
    dialog=xbmcgui.Dialog()
    if action in {'logs','export','share'}:
        from infuse_diagnostics import view_logs,export,share
        {'logs':view_logs,'export':export,'share':share}[action]()
    elif action in {'detect','speed'}:
        from infuse_network_tools import detect,speed
        {'detect':detect,'speed':speed}[action]()
    elif action=='refresh-rate':
        from infuse import import_actions
        import_actions()
        from home_dialog import Dialog
        before=refresh_mode()
        if before is None:dialog.ok('刷新率匹配','设备未提供此设置，未写入猜测值。');return
        choice=Dialog().select('刷新率匹配',['关闭','始终','起播和停止','起播时'],preselect=before)
        if choice<0:return
        if refresh_mode()!=before:dialog.ok('设置已变化','当前策略已改变，请重新打开后再选择。');return
        try:
            if rpc('Settings.SetSettingValue',{'setting':'videoplayer.adjustrefreshrate','value':choice})!=True or refresh_mode()!=choice:raise RuntimeError('write')
        except (RuntimeError,ValueError):dialog.ok('设置未能确认','原生设置接口未确认选择，请查看当前策略。')
    elif action in {'link-info','reset-uptime'}:
        from infuse_device import capabilities
        if not capabilities()['coreelec']:dialog.ok('设备状态变化','此操作仅用于 CoreELEC。');return
        if xbmc.Player().isPlaying():dialog.ok('维护不可用','请结束播放后再执行。');return
        script='ethtool.py' if action=='link-info' else 'resettime.py'
        namespace=runpy.run_path(xbmcvfs.translatePath('special://skin/scripts/'+script),run_name='yoplayer_legacy_tool')
        def guarded(function):
            def call(*args,**kwargs):
                if xbmc.Player().isPlaying():raise RuntimeError('Playback appeared')
                return function(*args,**kwargs)
            return call
        if action=='reset-uptime':
            context=namespace['main'].__globals__
            for name in ('modify_guisettings','setup_autostart'):context[name]=guarded(context[name])
            class Native:
                def __getattr__(self,name):return getattr(xbmc,name)
                def executebuiltin(self,*args,**kwargs):return guarded(xbmc.executebuiltin)(*args,**kwargs)
            context['xbmc']=Native()
        if xbmc.Player().isPlaying():raise RuntimeError('Playback appeared')
        namespace['main']('refresh') if action=='link-info' else namespace['main']()
    elif action in {'clean','kernel'}:
        if xbmc.Player().isPlaying():dialog.ok('维护不可用','请结束播放后执行维护。');return
        from infuse_device import dispatch
        dispatch(action,guard=lambda:not xbmc.Player().isPlaying())
    elif action=='reload':
        if xbmc.Player().isPlaying():dialog.ok('重新载入皮肤','请结束播放后再重新载入。');return
        if dialog.yesno('重新载入皮肤','重新加载当前界面？',nolabel='取消',yeslabel='重新加载',defaultbutton=xbmcgui.DLG_YESNO_NO_BTN):return ('reload',)
    elif action=='about':
        from infuse_system import run
        run('native-versions')
        try:
            with open(xbmcvfs.translatePath('special://skin/changelog.txt'),encoding='utf-8',errors='replace') as f:text=f.read(48*1024)
        except OSError:text='当前版本没有可读取的更新说明。'
        dialog.textviewer('YoPlayer 更新说明',text)
    elif action=='ce':
        from infuse_device import capabilities
        if not capabilities()['coreelec']:dialog.ok('设备状态变化','CoreELEC 设置当前不可用。');return
        return ('ce',)
    elif action=='dv':
        from infuse_device import capabilities
        if capabilities()['coreelec']:
            if xbmc.Player().isPlaying():dialog.ok('杜比视界一键配置','请结束播放后再调整显示配置。');return
            legacy_dv()
        else:dialog.ok('设备状态变化','CoreELEC 杜比视界设置当前不可用。')
    elif action in {'display','network','events','zip'}:
        return ('native',{'display':'SystemSettings','network':'ServiceSettings','events':'EventLog','zip':'AddonBrowser'}[action], 'InstallFromZip' if action=='zip' else None)


class Tools(xbmcgui.WindowXMLDialog):
    def configure(self,group=0,position=0,return_to_list=False):
        self.group=group;self.position=position;self.result=None;self.pending_focus=True
        self.return_to_list=return_to_list
        self.groups=[entries(i) for i in range(4)]

    def onInit(self):
        self.render()
        self.getControl(8610).selectItem(self.position)
        ident=xbmcgui.getCurrentWindowDialogId()
        def focus():
            monitor=xbmc.Monitor()
            for _ in range(8):
                if monitor.waitForAbort(.05) or not self.pending_focus or xbmcgui.getCurrentWindowDialogId()!=ident:return
                try:
                    if self.getFocusId() not in (0,8699,8601):return
                    self.setFocusId(8610 if self.return_to_list else 8601+self.group);self.pending_focus=False;return
                except RuntimeError:continue
        threading.Thread(target=focus,daemon=True).start()

    def render(self):
        self.setProperty('YoPlayer.ToolGroup',str(self.group))
        for i,title in enumerate(GROUPS):
            self.getControl(8601+i).setLabel('[COLOR FF087C86]'+title+'[/COLOR]' if i==self.group else title)
        self.rows=self.groups[self.group]
        control=self.getControl(8610);control.reset()
        for title,detail,action,icon in self.rows:
            item=xbmcgui.ListItem(label=title,label2=detail)
            item.setArt({'icon':'special://skin/media/infuse/settings_final/'+icon+'.png'})
            control.addItem(item)
        control.controlLeft(self.getControl(8601+self.group))
        self.getControl(8600).setLabel(GROUPS[self.group])

    def onFocus(self,control_id):
        if 8601<=control_id<=8604 and self.group!=control_id-8601:
            self.group=control_id-8601;self.position=0;self.render()

    def onClick(self,control_id):
        self.pending_focus=False
        if control_id==8699:self.close()
        elif 8601<=control_id<=8604:self.setFocusId(8610)
        elif control_id==8610:
            position=self.getControl(8610).getSelectedPosition()
            if 0<=position<len(self.rows):
                # Native RPC, I/O and modal work belongs on the script thread.
                self.position=position;self.result=self.rows[position][2];self.close()

    def onAction(self,action):
        if action.getId() in (1,2,3,4,7,10,92,100,101):self.pending_focus=False
        if action.getId() in (10,92):self.close()


def show():
    group=0;position=0;return_to_list=False;monitor=xbmc.Monitor()
    while not monitor.abortRequested():
        sheet=Tools('custom_1186_SystemTools.xml',xbmcvfs.translatePath('special://skin'),'default','1080p')
        sheet.configure(group,position,return_to_list);sheet.doModal()
        group,position,action=sheet.group,sheet.position,sheet.result
        del sheet
        if not action:return
        return_to_list=True
        try:result=perform(action)
        except (RuntimeError,OSError,ValueError):
            xbmcgui.Dialog().ok('操作未完成','当前接口或设备不可用，请稍后重试。');continue
        if result and result[0]=='reload':
            xbmc.executebuiltin('ReloadSkin()',wait=True);return 'close'
        if result and result[0]=='native':open_native(result[1],result[2])
        if result and result[0]=='ce':
            open_native('coreelec','RunAddon(service.coreelec.settings)')
