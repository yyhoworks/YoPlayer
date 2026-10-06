import requests
import json
import os
import re
import time
import xbmc
import xbmcvfs
import sys

def getWbiKeys():
    """从 plugin.video.bili 的 account.json 中读取 Cookie 并获取 WBI 密钥"""
    cookie_str = ""
    try:
        # 修改为更具通用性的路径
        addon_data_path = xbmcvfs.translatePath('special://userdata/addon_data/plugin.video.bili/.storage/account.json')
        
        if xbmcvfs.exists(addon_data_path):
            with open(addon_data_path, 'r', encoding='utf-8') as f:
                account_data = json.load(f)
                # account.json 中通常直接包含 'cookie' 字段
                if 'cookie' in account_data and account_data['cookie']:
                    cookie_str = account_data['cookie']
                    xbmc.log("[btrailer] 成功从 account.json 读取到Cookie", xbmc.LOGINFO)
                else:
                    xbmc.log("[btrailer] account.json 中未找到有效的 cookie 字段", xbmc.LOGWARNING)
        else:
            xbmc.log(f"[btrailer] 未找到 account.json 文件: {addon_data_path}", xbmc.LOGWARNING)
            # 文件不存在，切换到demo模式
            xbmc.log("[btrailer] 切换到Demo模式", xbmc.LOGINFO)
            xbmc.executebuiltin('RunScript(special://skin/scripts/bili.py,demo)')
            return None, None
            
    except Exception as e:
        xbmc.log(f"[btrailer] 读取 account.json 时出错: {e}", xbmc.LOGERROR)

    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    
    if cookie_str:
        headers['Cookie'] = cookie_str
        
    # 请求 nav 接口获取 WBI 密钥
    url = 'https://api.bilibili.com/x/web-interface/nav'
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('code') == 0:
            wbi_img = data.get('data', {}).get('wbi_img', {})
            img_url = wbi_img.get('img_url', '')
            sub_url = wbi_img.get('sub_url', '')
            if img_url and sub_url:
                img_key = img_url.split('/')[-1].split('.')[0]
                sub_key = sub_url.split('/')[-1].split('.')[0]
                xbmc.log("[btrailer] 成功获取WBI密钥", xbmc.LOGINFO)
                return img_key, sub_key
            else:
                xbmc.log("[btrailer] WBI图片URL为空", xbmc.LOGERROR)
        else:
            xbmc.log(f"[btrailer] WBI API返回错误: Code {data.get('code')}, Message: {data.get('message')}", xbmc.LOGERROR)
            if data.get('code') == -101:
                xbmc.log("[btrailer] 提示: Cookie可能已失效，请在 plugin.video.bili 插件内重新登录。", xbmc.LOGINFO)
                # Cookie失效，切换到demo模式
                xbmc.log("[btrailer] 切换到Demo模式", xbmc.LOGINFO)
                xbmc.executebuiltin('RunScript(special://skin/scripts/bili.py,demo)')
            return None, None
    except Exception as e:
        xbmc.log(f"[btrailer] 请求WBI API异常: {e}", xbmc.LOGERROR)
    
    return None, None

def encWbi(params, img_key, sub_key):
    """生成 WBI 签名"""
    # B站WBI签名的固定混淆映射表
    mixin_key_enc = '46479831250103528496637145822395016136440275938862175734651624'
    time_stamp = int(time.time())
    params.update({'wts': time_stamp})
    
    # 对键名进行排序并拼接
    params = dict(sorted(params.items()))
    query = []
    for key, value in params.items():
        # 过滤掉特殊字符
        value_str = str(value)
        for char in "!'()*":
            value_str = value_str.replace(char, '')
        query.append(f"{key}={value_str}")
    query = '&'.join(query)
    
    # 截取混淆后的密钥前32位
    wbi_sign = mixin_key_enc[:32]
    
    # 生成签名
    import hashlib
    w_rid = hashlib.md5((query + wbi_sign).encode('utf-8')).hexdigest()
    return w_rid

def search_bili(keyword):
    """搜索B站视频"""
    img_key, sub_key = getWbiKeys()
    if not img_key or not sub_key:
        xbmc.log("[btrailer] 无法获取WBI密钥，搜索失败。", xbmc.LOGERROR)
        return None

    # 搜索API参数
    params = {
        'search_type': 'video',
        'keyword': keyword,
        'page': 1,
        'pagesize': 1
    }
    
    # 生成签名
    w_rid = encWbi(params, img_key, sub_key)
    params['w_rid'] = w_rid
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://search.bilibili.com/'
    }
    
    url = 'https://api.bilibili.com/x/web-interface/wbi/search/type'
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('code') == 0:
            results = data.get('data', {}).get('result', [])
            if results:
                # 获取第一个结果的BV号和标题
                bvid = results[0].get('bvid')
                title = results[0].get('title')
                # 构造插件播放URL
                plugin_url = f"plugin://plugin.video.bili/video/{bvid}/0/false/false/False/{title}/"
                xbmc.log(f"[btrailer] 找到预告片URL: {plugin_url}", xbmc.LOGINFO)
                return plugin_url
            else:
                xbmc.log("[btrailer] 未搜索到相关视频", xbmc.LOGINFO)
        else:
            xbmc.log(f"[btrailer] 搜索API返回错误: Code {data.get('code')}, Message: {data.get('message')}", xbmc.LOGERROR)
    except Exception as e:
        xbmc.log(f"[btrailer] 搜索请求异常: {e}", xbmc.LOGERROR)
    
    return None

def clean_url(url):
    """清理URL中的HTML标签和数字串"""
    # 移除 <em class=_keyword_> 和 <_em> 标签
    cleaned = re.sub(r'<[^>]+>', '', url)
    # 将URL路径中的纯数字串（视频CID）替换为 0
    # 匹配 /video/BV号/纯数字/ 中的纯数字部分
    cleaned = re.sub(r'(/video/BV\w+/)\d+(/)', r'\g<1>0\g<2>', cleaned)
    return cleaned

def play_and_monitor(plugin_url, demo_mode=False):
    """播放并监测播放器状态"""
    # 1. 清理URL
    final_url = clean_url(plugin_url)
    xbmc.log(f"[btrailer] 净化后的播放地址: {final_url}", xbmc.LOGINFO)
    
    # 2. 执行播放
    xbmc.executebuiltin(f'PlayMedia({final_url}, False, 1)')
    
    # 如果是 demo 模式，播放后直接返回，不进行后续监控
    if demo_mode:
        xbmc.log("[btrailer] Demo模式：已触发播放，跳过状态监控和循环检测。", xbmc.LOGINFO)
        return

    # 3. 等待片刻，检测是否正常开始播放 (以下代码仅在非demo模式下执行)
    time.sleep(3)
    if not xbmc.getCondVisibility('Player.HasVideo'):
        xbmc.log("[btrailer] 预告片未能正常播放，关闭脚本。", xbmc.LOGINFO)
        return
    
    # 4. 播放正常，设置 notrailer 为 0
    xbmc.executebuiltin('Skin.SetString(notrailer,0)')
    xbmc.log("[btrailer] 预告片正常播放，已设置 Skin.SetString(notrailer,0)", xbmc.LOGINFO)
    
    # 5. 检测是否开启了循环播放 (trailerloop)
    is_loop = xbmc.getCondVisibility('Skin.HasSetting(trailerloop)')
    
    # --- 进入循环监测逻辑 ---
    while True:
        # 循环监测 Player.HasVideo
        if not xbmc.getCondVisibility('Player.HasVideo'):
            # 视频播放结束或停止，延时1秒
            time.sleep(1)
            
            # 检测 MovieInformation 窗口是否可见
            if xbmc.getCondVisibility('Window.IsVisible(MovieInformation)'):
                if is_loop:
                    # 如果开启了循环且还在电影信息页，重新播放
                    xbmc.log("[btrailer] 检测到循环播放设置，重新播放预告片...", xbmc.LOGINFO)
                    xbmc.executebuiltin(f'PlayMedia({final_url}, False, 1)')
                    time.sleep(3) # 等待重新播放启动
                    continue
                else:
                    # 没开循环，但还在信息页，直接退出
                    xbmc.log("[btrailer] 未开启循环播放，脚本结束。", xbmc.LOGINFO)
                    break
            else:
                # 不在电影信息页了，说明用户已经离开，设置 notrailer=1 并退出
                xbmc.executebuiltin('Skin.SetString(notrailer,1)')
                xbmc.log("[btrailer] 用户已离开信息页，已设置 Skin.SetString(notrailer,1)，脚本结束。", xbmc.LOGINFO)
                break
        
        time.sleep(1) # 每次循环间隔1秒

# --- 脚本主入口 ---
if __name__ == '__main__':
    try:
        # 1. 检查是否传入了 'demo' 参数
        # sys.argv 通常包含脚本路径和后续参数，我们检查是否有 'demo' 字符串
        is_demo = 'demo' in sys.argv
        
        if is_demo:
            xbmc.log("[btrailer] 检测到 Demo 参数，将以演示模式运行。", xbmc.LOGINFO)

        # 2. 获取当前项目类型 (保持原有逻辑不变)
        dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
        if dbtype == "episode":
            # 情况1：如果是剧集，则使用电视剧标题
            movie_title = xbmc.getInfoLabel('$INFO[ListItem.TVShowTitle]')
            xbmc.log(f"[btrailer] 检测到剧集项目，使用电视剧标题: {movie_title}", xbmc.LOGINFO)
        else:
            # 情况2：如果不是剧集，则按原逻辑使用列表项标题
            movie_title = xbmc.getInfoLabel('ListItem.Title')
            xbmc.log(f"[btrailer] 检测到非剧集项目，使用列表项标题: {movie_title}", xbmc.LOGINFO)

        if movie_title:
            xbmc.log(f"[btrailer] 获取到标题: {movie_title}", xbmc.LOGINFO)
            search_keyword = f"{movie_title} 预告"
            xbmc.log(f"[btrailer] 搜索关键词: {search_keyword}", xbmc.LOGINFO)
            xbmc.log(f"[btrailer] 开始搜索: {search_keyword}", xbmc.LOGINFO)
            
            video_url = search_bili(search_keyword)
            
            if video_url:
                # 3. 调用播放函数时，传入 is_demo 标志
                play_and_monitor(video_url, demo_mode=is_demo)
            else:
                # 如果无法获取预告片URL，设置trailerfail标志并退出
                xbmc.executebuiltin('Skin.SetString(trailerfail,1)')
                xbmc.log("[btrailer] 无法获取预告片URL，已设置 Skin.SetString(trailerfail,1)，脚本结束。", xbmc.LOGINFO)
        else:
            xbmc.executebuiltin('Skin.SetString(trailerfail,1)')
            xbmc.log("[btrailer] 未能获取到项目标题，请确保在正确的界面运行脚本。已设置 Skin.SetString(trailerfail,1)，脚本结束。", xbmc.LOGERROR)
            
    except Exception as e:
        # 在任何异常情况下都设置trailerfail标志并退出
        xbmc.executebuiltin('Skin.SetString(trailerfail,1)')
        xbmc.log(f"[btrailer] 脚本执行过程中发生异常: {str(e)}，已设置 Skin.SetString(trailerfail,1)，脚本结束。", xbmc.LOGERROR)