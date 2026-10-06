import xbmc
import json
import urllib.request
import urllib.parse

# 配置项 无修改
TMDB_CREDITS_URL = "https://api.themoviedb.org/3/tv/{tmdb_id}/credits?api_key={api_key}"
TMDB_TV_DETAILS_URL = "https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={api_key}&append_to_response=credits"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/tv?api_key={api_key}&query={query}&language=en-US&page=1"
SKIN_STRING_DIRECTOR = "eptvshowid"
SKIN_STRING_TMDB_ID = "eptvshowidactor"
API_KEY_SKIN_STRING = "tmdbapikey"
LOG_PREFIX = "[剧集导演ID脚本]"

# 扩展API密钥列表，按优先级排序
API_KEYS_LIST = [
    "af3a53eb387d57fc935e9128468b1899",
    "f090bb54758cabf231fb605d3e3e0468",
    "a07324c669cac4d96789197134ce272b"
]

def get_tmdb_id_by_title_and_year(api_key, title, target_year_str):
    """通过剧集名+年份查TMDB ID，字符串切片解析年份，零报错"""
    if not title:
        return ""
    
    target_year = None
    if target_year_str and target_year_str.isdigit():
        target_year = int(target_year_str)

    encoded_title = urllib.parse.quote(title.strip())
    url = TMDB_SEARCH_URL.format(api_key=api_key, query=encoded_title)
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if not results:
                return ""
            
            if len(results) == 1:
                return str(results[0].get("id", ""))
            
            valid_results = []
            for result in results:
                first_air_date = result.get("first_air_date", "")
                res_id = result.get("id", "")
                show_year = None
                year_diff = float("inf")

                # 字符串切片解析年份 核心修复
                if first_air_date and len(first_air_date) >= 4:
                    show_year_str = first_air_date[0:4]
                    if show_year_str.isdigit():
                        show_year = int(show_year_str)

                if target_year and show_year:
                    year_diff = abs(show_year - target_year)

                valid_results.append({
                    "tmdb_id": str(res_id),
                    "year_diff": year_diff
                })

            if not valid_results:
                return ""
            
            valid_results.sort(key=lambda x: x["year_diff"])
            return valid_results[0]["tmdb_id"]
    
    except Exception as e:
        # 报错时输出【详细日志】
        xbmc.log(f"{LOG_PREFIX} 【错误】查询剧集ID失败：{str(e)} | 标题={title} | 年份={target_year_str}", xbmc.LOGERROR)
        return ""

def get_director_id_from_credits(api_key, tmdb_id):
    """主逻辑-获取导演ID"""
    try:
        url = TMDB_CREDITS_URL.format(tmdb_id=tmdb_id, api_key=api_key)
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for crew in data.get("crew", []):
                if crew.get("job") == "Director":
                    return str(crew.get("id", ""))
        return ""
    except Exception as e:
        # 报错时输出【详细日志】
        xbmc.log(f"{LOG_PREFIX} 【错误】Credits接口获取导演ID失败：{str(e)} | TMDB_ID={tmdb_id}", xbmc.LOGERROR)
        return ""

def get_director_id_from_details(api_key, tmdb_id):
    """备用逻辑-获取导演/创作者ID"""
    try:
        url = TMDB_TV_DETAILS_URL.format(tmdb_id=tmdb_id, api_key=api_key)
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            created_by = data.get("created_by", [])
            if created_by:
                return str(created_by[0].get("id", ""))
            
            credits = data.get("credits", {})
            directing = credits.get("directing", [])
            if directing:
                return str(directing[0].get("id", ""))

            director_str = data.get("director_str", "").strip()
            if director_str and director_str != "N/A":
                first_director_name = director_str.split(",")[0].strip()
                if first_director_name:
                    return search_person_id_by_name(api_key, first_director_name)
            return ""
    except Exception as e:
        # 报错时输出【详细日志】
        xbmc.log(f"{LOG_PREFIX} 【错误】详情接口获取导演ID失败：{str(e)} | TMDB_ID={tmdb_id}", xbmc.LOGERROR)
        return ""

def search_person_id_by_name(api_key, person_name):
    """人名搜索人物ID"""
    TMDB_PERSON_SEARCH_URL = "https://api.themoviedb.org/3/search/person?api_key={api_key}&query={query}&language=en-US&page=1"
    try:
        encoded_name = urllib.parse.quote(person_name.strip())
        url = TMDB_PERSON_SEARCH_URL.format(api_key=api_key, query=encoded_name)
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                return str(results[0].get("id", ""))
        return ""
    except Exception as e:
        # 报错时输出【详细日志】
        xbmc.log(f"{LOG_PREFIX} 【错误】人物搜索失败：{str(e)} | 人名={person_name}", xbmc.LOGERROR)
        return ""

def try_api_keys_for_function(func, *args):
    """尝试多个API密钥直到成功或全部失败"""
    # 首先尝试皮肤配置的密钥
    skin_api_key = xbmc.getInfoLabel(f"Skin.String({API_KEY_SKIN_STRING})").strip()
    if skin_api_key:
        xbmc.log(f"{LOG_PREFIX} 【信息】尝试使用皮肤配置的API密钥", xbmc.LOGINFO)
        result = func(skin_api_key, *args[1:])
        if result:
            return result
        else:
            xbmc.log(f"{LOG_PREFIX} 【警告】皮肤配置的API密钥无效或请求失败，尝试默认密钥", xbmc.LOGWARNING)
    
    # 依次尝试默认API密钥
    for i, api_key in enumerate(API_KEYS_LIST):
        xbmc.log(f"{LOG_PREFIX} 【信息】尝试默认API密钥 #{i+1}: {api_key[:6]}...", xbmc.LOGINFO)
        result = func(api_key, *args[1:])
        if result:
            xbmc.log(f"{LOG_PREFIX} 【信息】成功使用默认API密钥 #{i+1}", xbmc.LOGINFO)
            return result
        else:
            xbmc.log(f"{LOG_PREFIX} 【警告】默认API密钥 #{i+1} 失效或请求失败", xbmc.LOGWARNING)
    
    # 所有密钥都失败
    xbmc.log(f"{LOG_PREFIX} 【错误】所有API密钥均无效或请求失败", xbmc.LOGERROR)
    return ""

def main():
    # 1. 获取剧集TMDB ID
    tmdb_id = xbmc.getInfoLabel("Container(99950).ListItem.Property(TMDb_id)").strip()
    if not (tmdb_id and tmdb_id.isdigit()):
        tvshow_title = xbmc.getInfoLabel("ListItem.TVShowTitle").strip()
        premiered_date = xbmc.getInfoLabel("ListItem.Premiered").strip()
        target_year_str = premiered_date.split("-")[0] if premiered_date else ""
        
        # 使用多个API密钥尝试获取剧集ID
        tmdb_id = try_api_keys_for_function(get_tmdb_id_by_title_and_year, "", tvshow_title, target_year_str)

    # 2. 验证ID有效性
    if not (tmdb_id and tmdb_id.isdigit()):
        xbmc.log(f"{LOG_PREFIX} 【错误】未获取到有效剧集TMDB ID", xbmc.LOGERROR)
        return

    # 3. 写入剧集ID到皮肤字符串
    try:
        xbmc.executebuiltin(f'Skin.SetString({SKIN_STRING_TMDB_ID},"{tmdb_id}")')
    except Exception as e:
        xbmc.log(f"{LOG_PREFIX} 【错误】写入剧集ID失败：{str(e)} | KEY={SKIN_STRING_TMDB_ID}", xbmc.LOGERROR)

    # 4. 获取导演ID - 使用多个API密钥
    # 先尝试从credits获取
    director_id = try_api_keys_for_function(get_director_id_from_credits, "", tmdb_id)
    
    # 如果从credits获取失败，尝试从details获取
    if not director_id:
        xbmc.log(f"{LOG_PREFIX} 【信息】从credits获取导演ID失败，尝试从details获取", xbmc.LOGINFO)
        director_id = try_api_keys_for_function(get_director_id_from_details, "", tmdb_id)

    # 5. 写入导演ID到皮肤字符串
    if director_id:
        try:
            xbmc.executebuiltin(f'Skin.SetString({SKIN_STRING_DIRECTOR},"{director_id}")')
        except Exception as e:
            xbmc.log(f"{LOG_PREFIX} 【错误】写入导演ID失败：{str(e)} | KEY={SKIN_STRING_DIRECTOR}", xbmc.LOGERROR)
    else:
        xbmc.log(f"{LOG_PREFIX} 【警告】未获取到有效导演ID | TMDB_ID={tmdb_id}", xbmc.LOGWARNING)

if __name__ == "__main__":
    main()