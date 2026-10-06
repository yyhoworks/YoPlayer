import os
import re
import sys
import json
import random
import math
import xml.etree.ElementTree as ET
import xbmc
import xbmcgui
import xbmcvfs
import urllib.request
import urllib.parse
from urllib.parse import unquote
import colorsys

# 尝试导入 PIL
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    xbmc.log("[favcover] Error: Pillow library is not installed.", xbmc.LOGERROR)

ADDON_ID = "script.skin.favcover"
LOG_PREFIX = f"[{ADDON_ID}] "

THUMBS_DIR = "special://userdata/Thumbnails/favthumb/"
TEMP_DIR = "special://temp/favcover_temp/"

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"{LOG_PREFIX}{msg}", level)

def ensure_dir(path):
    trans_path = xbmcvfs.translatePath(path)
    if not xbmcvfs.exists(trans_path):
        xbmcvfs.mkdirs(trans_path)
    return trans_path

def get_font(size):
    """
    获取字体，优先使用Kodi系统自带字体。
    """
    kodi_font_path = xbmcvfs.translatePath("special://xbmc/media/Fonts/arial.ttf")
    if os.path.exists(kodi_font_path):
        try:
            return ImageFont.truetype(kodi_font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def translate_to_english(text):
    """
    通过调用翻译API将文本翻译为英文。
    """
    if not text:
        return "Collection"
    
    if all(ord(c) < 128 for c in text):
        return text

    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.appworlds.cn/?text={encoded_text}&from=zh-CN&to=en"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Addon/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            result = response.read().decode('utf-8', errors='ignore').strip()
            
            try:
                json_data = json.loads(result)
                if isinstance(json_data, dict):
                    for key in ['data', 'translatedText', 'result', 'text', 'translation', 'dst']:
                        if key in json_data and isinstance(json_data[key], str):
                            return json_data[key].replace('\n', ' ').strip()
                    for val in json_data.values():
                        if isinstance(val, str):
                            return val.replace('\n', ' ').strip()
                elif isinstance(json_data, str):
                    return json_data.replace('\n', ' ').strip()
            except json.JSONDecodeError:
                pass
                
            clean_result = re.sub(r'<[^>]+>', '', result)
            return clean_result.replace('\n', ' ').strip()
                
    except Exception as e:
        log(f"Translation API error: {e}", xbmc.LOGWARNING)
        
    english_chars = [c for c in text if ord(c) < 128]
    fallback = "".join(english_chars).strip()
    return fallback if fallback else "Collection"

class JRPCHelper:
    @staticmethod
    def execute(method, params=None):
        if params is None:
            params = {}
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        
        response = xbmc.executeJSONRPC(json.dumps(request))
        try:
            result = json.loads(response)
            if "error" in result:
                log(f"JRPC Error for {method}: {result['error']}", xbmc.LOGWARNING)
                return None
            return result.get("result")
        except Exception as e:
            log(f"JRPC Parse Error: {e}", xbmc.LOGERROR)
            return None

    @staticmethod
    def parse_xsp_rules(xsp_path):
        """
        解析 .xsp 文件，提取媒体类型和过滤规则
        """
        try:
            tree = ET.parse(xsp_path)
            root = tree.getroot()
            
            media_type = root.get('type', 'movies')
            
            rules = []
            for rule_elem in root.findall('rule'):
                field = rule_elem.get('field')
                operator = rule_elem.get('operator')
                values = [val.text for val in rule_elem.findall('value') if val.text]
                
                if field and operator and values:
                    op_map = {
                        'is': 'is', 'isnot': 'isnot', 'startswith': 'startswith',
                        'endswith': 'endswith', 'contains': 'contains', 'doesnotcontain': 'doesnotcontain',
                        'lessthan': 'lessthan', 'greaterthan': 'greaterthan', 'after': 'after',
                        'before': 'before', 'inthelast': 'inthelast', 'notinthelast': 'notinthelast',
                        'true': 'true', 'false': 'false'
                    }
                    json_op = op_map.get(operator, 'contains')
                    
                    rules.append({
                        "field": field,
                        "operator": json_op,
                        "value": values[0] if len(values) == 1 else values
                    })
            
            return media_type, rules
        except Exception as e:
            log(f"Error parsing XSP: {e}", xbmc.LOGERROR)
            return None, None

    @staticmethod
    def get_posters_from_xsp(xsp_path, max_count=9):
        """
        通过解析 XSP 规则并查询数据库来获取海报
        """
        log(f"Parsing XSP file: {xsp_path}")
        media_type, rules = JRPCHelper.parse_xsp_rules(xsp_path)
        
        if not media_type:
            return []
            
        log(f"XSP Type: {media_type}, Rules Count: {len(rules) if rules else 0}")
        
        method_map = {
            'movies': 'VideoLibrary.GetMovies',
            'tvshows': 'VideoLibrary.GetTVShows',
            'episodes': 'VideoLibrary.GetEpisodes',
            'musicvideos': 'VideoLibrary.GetMusicVideos'
        }
        
        target_method = method_map.get(media_type)
        if not target_method:
            log(f"Unsupported XSP type: {media_type}")
            return []

        filter_params = None
        if rules:
            field_map = {
                'genre': 'genre', 'year': 'year', 'actor': 'cast', 'studio': 'studio',
                'director': 'director', 'tag': 'tag', 'mpaa': 'mpaarating', 'imdbnumber': 'imdbnumber',
                'title': 'title', 'plot': 'plot', 'set': 'set', 'country': 'country',
                'dateadded': 'dateadded', 'lastplayed': 'lastplayed', 'playcount': 'playcount',
                'videoresolution': 'videoresolution', 'videocodec': 'videocodec',
                'audiochannels': 'audiochannels', 'audiocodec': 'audiocodec',
                'file': 'file', 'path': 'path', 'season': 'season', 'episode': 'episode',
                'tvshowtitle': 'tvshowtitle', 'status': 'status', 'airdate': 'firstaired',
                'rating': 'rating', 'votes': 'votes', 'top250': 'top250',
                'album': 'album', 'artist': 'artist', 'duration': 'duration',
                'filename': 'filename',
            }
            
            filter_list = []
            for r in rules:
                json_field = field_map.get(r['field'], r['field'])
                
                if r['field'] == 'watched' and r['operator'] == 'true':
                    filter_list.append({"field": "playcount", "operator": "greaterthan", "value": "0"})
                    continue
                elif r['field'] == 'unwatched' and r['operator'] == 'true':
                    filter_list.append({"field": "playcount", "operator": "is", "value": "0"})
                    continue
                elif r['field'] == 'inprogress' and r['operator'] == 'true':
                     continue

                val = r['value']
                if isinstance(val, list):
                    processed_val = [str(v) for v in val]
                else:
                    processed_val = str(val)

                filter_list.append({
                    "field": json_field,
                    "operator": r['operator'],
                    "value": processed_val
                })
            
            if len(filter_list) == 1:
                filter_params = filter_list[0]
            elif len(filter_list) > 1:
                filter_params = {"and": filter_list}
        
        params = {
            "properties": ["art", "title"],
            "limits": {"end": max_count * 3}
        }
        
        if filter_params:
            params["filter"] = filter_params
            
        params["sort"] = {"method": "random"}

        log(f"Executing JRPC: {target_method} with filter: {json.dumps(filter_params) if filter_params else 'None'}")
        result = JRPCHelper.execute(target_method, params)
        
        posters = []
        items = []
        
        if result:
            if media_type == 'movies':
                items = result.get("movies", [])
            elif media_type == 'tvshows':
                items = result.get("tvshows", [])
            elif media_type == 'episodes':
                items = result.get("episodes", [])
            elif media_type == 'musicvideos':
                items = result.get("musicvideos", [])
                
        for item in items:
            if len(posters) >= max_count:
                break
            
            art = item.get("art", {})
            poster_url = None
            
            if "poster" in art and art["poster"]:
                poster_url = art["poster"]
            elif "thumb" in art and art["thumb"]:
                poster_url = art["thumb"]

            if poster_url:
                posters.append(poster_url)
                
        log(f"Found {len(posters)} posters from XSP query")
        return posters

    @staticmethod
    def get_posters_from_path(path, max_count=9):
        log(f"Fetching posters for path: {path}")
        
        if path.lower().endswith('.xsp'):
            local_path = xbmcvfs.translatePath(path) if path.startswith("special://") else path
            if os.path.exists(local_path):
                return JRPCHelper.get_posters_from_xsp(local_path, max_count)
            else:
                log(f"XSP file not found at: {local_path}")
                return []

        dir_content = JRPCHelper.execute("Files.GetDirectory", {
            "directory": path,
            "media": "video",
            "properties": ["title", "file", "art"]
        })
        
        posters = []
        if not dir_content or "files" not in dir_content:
            return posters
            
        items = dir_content["files"]
        random.shuffle(items)
        
        for item in items:
            if len(posters) >= max_count:
                break
            if "art" in item and "poster" in item["art"] and item["art"]["poster"]:
                posters.append(item["art"]["poster"])
                continue
            title = item.get("title")
            if title:
                movie_res = JRPCHelper.execute("VideoLibrary.GetMovies", {
                    "filter": {"field": "title", "operator": "contains", "value": title},
                    "properties": ["art"],
                    "limits": {"end": 1}
                })
                if movie_res and "movies" in movie_res and movie_res["movies"]:
                    art = movie_res["movies"][0].get("art", {})
                    if "poster" in art:
                        posters.append(art["poster"])
        log(f"Found {len(posters)} posters from directory")
        return posters

    @staticmethod
    def get_random_posters_from_library(count_needed, existing_urls=None):
        """
        从整个媒体库中随机获取海报以补齐数量
        """
        if count_needed <= 0:
            return []
            
        log(f"Fetching {count_needed} random posters from library to fill gaps...")
        all_posters = []
        seen_urls = set(existing_urls) if existing_urls else set()
        
        # 1. Get Random Movies
        movies_res = JRPCHelper.execute("VideoLibrary.GetMovies", {
            "properties": ["art"],
            "limits": {"end": count_needed * 2},
            "sort": {"method": "random"}
        })
        
        if movies_res and "movies" in movies_res:
            for m in movies_res["movies"]:
                if len(all_posters) >= count_needed:
                    break
                art = m.get("art", {})
                url = art.get("poster") or art.get("thumb")
                if url and url not in seen_urls:
                    all_posters.append(url)
                    seen_urls.add(url)

        # 2. Get Random TV Shows if still needed
        if len(all_posters) < count_needed:
            remaining = count_needed - len(all_posters)
            tv_res = JRPCHelper.execute("VideoLibrary.GetTVShows", {
                "properties": ["art"],
                "limits": {"end": remaining * 2},
                "sort": {"method": "random"}
            })
            
            if tv_res and "tvshows" in tv_res:
                for t in tv_res["tvshows"]:
                    if len(all_posters) >= count_needed:
                        break
                    art = t.get("art", {})
                    url = art.get("poster") or art.get("thumb")
                    if url and url not in seen_urls:
                        all_posters.append(url)
                        seen_urls.add(url)
                        
        log(f"Found {len(all_posters)} random library posters")
        return all_posters

    @staticmethod
    def download_image(url, save_path):
        try:
            if url.startswith(("special://", "image://")):
                real_url = xbmcvfs.translatePath(url)
            else:
                real_url = url
            success = xbmcvfs.copy(real_url, save_path)
            if success and xbmcvfs.exists(save_path):
                return True
            return False
        except Exception as e:
            log(f"Download error: {e}", xbmc.LOGERROR)
            return False

class CoverGenerator:
    def __init__(self):
        self.temp_translated = ensure_dir(TEMP_DIR)
        self.output_translated = ensure_dir(THUMBS_DIR)

    def create_rounded_rectangle_mask(self, size, radius):
        width, height = size
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
        draw.ellipse((width - radius * 2, 0, width, radius * 2), fill=255)
        draw.ellipse((0, height - radius * 2, radius * 2, height), fill=255)
        draw.ellipse((width - radius * 2, height - radius * 2, width, height), fill=255)
        draw.rectangle((radius, 0, width - radius, height), fill=255)
        draw.rectangle((0, radius, width, height - radius), fill=255)
        return mask

    def hsl_to_rgb(self, h, s, l):
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return (int(r * 255), int(g * 255), int(b * 255))

    def generate_random_vibrant_color(self):
        h = random.random()
        s = random.uniform(0.7, 1.0)
        l = random.uniform(0.4, 0.6)
        return self.hsl_to_rgb(h, s, l)

    def get_complementary_color(self, rgb):
        r, g, b = rgb
        h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        h_comp = (h + 0.5) % 1.0
        l_comp = min(1.0, l + 0.1) if l < 0.5 else max(0.0, l - 0.1)
        return self.hsl_to_rgb(h_comp, s, l_comp)

    def create_gradient_bg(self, width, height, base_color):
        r, g, b = base_color
        end_color = self.get_complementary_color(base_color)
        r2, g2, b2 = end_color
        
        left_img = Image.new("RGBA", (width, height), (r, g, b, 255))
        right_img = Image.new("RGBA", (width, height), (r2, g2, b2, 255))
        
        mask = Image.new("L", (width, height), 0)
        mask_data = []
        for y in range(height):
            for x in range(width):
                val = int(255.0 * (x + y) / (width + height))
                mask_data.append(val)
        mask.putdata(mask_data)
        
        return Image.composite(right_img, left_img, mask)

    def get_text_width(self, draw, text, font):
        """
        兼容 Pillow >= 10.0 的文本宽度获取方法
        """
        try:
            # Pillow >= 10.0 uses getbbox
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]
        except AttributeError:
            # Fallback for older Pillow versions
            w, h = draw.textsize(text, font=font)
            return w

    def wrap_text(self, draw, text, font, max_width):
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            w = self.get_text_width(draw, test_line, font)
            
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
            
        return lines if lines else [text]

    def generate(self, poster_paths, title, output_filename):
        if not poster_paths:
            return None

        W, H = 960, 540
        
        bg_color = self.generate_random_vibrant_color()
        log(f"Generated random background color: {bg_color}")
        
        bg = self.create_gradient_bg(W, H, bg_color)
        draw = ImageDraw.Draw(bg)
        
        cols = 3
        rows = 3
        margin = 15          
        cell_w = 175         
        cell_h = 240         
        corner_radius = 15   
        shadow_offset = 15   
        rotation_angle = -15 
        
        blur_radius = 10     
        blur_padding = blur_radius * 2 

        grid_total_w = cols * cell_w + (cols - 1) * margin
        grid_total_h = rows * cell_h + (rows - 1) * margin
        
        diag = math.sqrt(grid_total_w**2 + grid_total_h**2)
        pad = int(diag) 
        
        temp_size = pad + 100 
        temp_canvas = Image.new("RGBA", (temp_size, temp_size), (0,0,0,0))
        
        base_grid_start_x = (temp_size - grid_total_w) // 2
        base_grid_start_y = (temp_size - grid_total_h) // 2
        grid_offset_y = int(H * 0.05)
        
        grid_start_x = base_grid_start_x
        grid_start_y = base_grid_start_y + grid_offset_y

        # Ensure we have exactly 9 posters for the grid
        display_posters = (poster_paths * 3)[:9]
        
        for i, p_path in enumerate(display_posters):
            col = i % cols
            row = i // cols
            
            x = grid_start_x + col * (cell_w + margin)
            y = grid_start_y + row * (cell_h + margin)
            
            # 优化：在旋转前对特定竖排进行垂直偏移
            if col == 0:
                y += 55  # 第一竖排向下移动35个像素
            elif col == 2:
                y -= 55  # 第三竖排向上移动35个像素
            
            try:
                p_translated = xbmcvfs.translatePath(p_path)
                with Image.open(p_translated) as img:
                    img = img.resize((cell_w, cell_h), Image.LANCZOS)
                    
                    mask = self.create_rounded_rectangle_mask((cell_w, cell_h), corner_radius)
                    
                    rounded_poster = Image.new("RGBA", (cell_w, cell_h), (0,0,0,0))
                    rounded_poster.paste(img, (0,0), mask)
                    
                    shadow_w = cell_w + blur_padding
                    shadow_h = cell_h + blur_padding
                    shadow_layer = Image.new("RGBA", (shadow_w, shadow_h), (0,0,0,0))
                    
                    sx = blur_padding // 2
                    sy = blur_padding // 2
                    
                    shadow_fill = Image.new("RGBA", (cell_w, cell_h), (0,0,0,200))
                    shadow_fill_mask = self.create_rounded_rectangle_mask((cell_w, cell_h), corner_radius)
                    shadow_layer.paste(shadow_fill, (sx, sy), shadow_fill_mask)
                    
                    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                    
                    paste_shadow_x = x + shadow_offset - (blur_padding // 2)
                    paste_shadow_y = y + shadow_offset - (blur_padding // 2)
                    
                    temp_canvas.paste(shadow_layer, (paste_shadow_x, paste_shadow_y), shadow_layer)
                    temp_canvas.paste(rounded_poster, (x, y), rounded_poster)
                    
            except Exception as e:
                log(f"Error processing poster {i}: {e}", xbmc.LOGERROR)
                continue

        rotated_grid = temp_canvas.rotate(rotation_angle, Image.BICUBIC, expand=True)
        
        rot_w, rot_h = rotated_grid.size
        right_margin = 20
        base_paste_x = W - rot_w - right_margin
        extra_offset = int(W * 0.46)
        paste_x = base_paste_x + extra_offset
        paste_y = (H - rot_h) // 2
        
        bg.paste(rotated_grid, (paste_x, paste_y), rotated_grid)

        clean_title = re.sub(r'[(\[<{（【《].*?[)\]>}）】》]', '', title).strip()
        
        text_x = 50
        text_y = 180
        
        max_title_width = 360
        title_font_size = 100
        title_font = get_font(title_font_size)
        
        current_width = self.get_text_width(draw, clean_title, title_font)
        
        if current_width > max_title_width:
            scale_factor = max_title_width / current_width
            title_font_size = int(title_font_size * scale_factor)
            title_font_size = max(40, title_font_size)
            title_font = get_font(title_font_size)
            
        draw.text((text_x+4, text_y+4), clean_title, font=title_font, fill=(0,0,0,180))
        draw.text((text_x, text_y), clean_title, font=title_font, fill=(255,255,255,255))
        
        subtitle_en = translate_to_english(clean_title)
        sub_font_size = 30
        sub_font = get_font(sub_font_size)
        
        subtitle_x = text_x + 16
        subtitle_start_y = text_y + title_font_size + 20
        
        subtitle_lines = self.wrap_text(draw, subtitle_en, sub_font, max_title_width)
        
        line_height = sub_font_size + 5
        total_subtitle_height = len(subtitle_lines) * line_height
        
        brightness = (bg_color[0] * 299 + bg_color[1] * 587 + bg_color[2] * 114) / 1000
        if brightness < 128:
            accent_color = (255, 200, 0, 255)
        else:
            accent_color = (220, 20, 60, 255)
            
        current_y = subtitle_start_y
        for line in subtitle_lines:
            draw.text((subtitle_x+2, current_y+2), line, font=sub_font, fill=(0,0,0,120))
            draw.text((subtitle_x, current_y), line, font=sub_font, fill=(255, 255, 255, 255))
            current_y += line_height
            
        bar_x = subtitle_x - 25
        bar_y = subtitle_start_y + 5
        bar_width = 8
        bar_height = total_subtitle_height - 10 
        
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=accent_color)

        output_full_path = os.path.join(self.output_translated, output_filename)
        try:
            bg.save(output_full_path, "PNG")
            log(f"Cover saved to: {output_full_path}")
            return output_filename
        except Exception as e:
            log(f"Save error: {e}", xbmc.LOGERROR)
            return None

def main():
    log("=== Start Favourite Cover Generator ===")
    args = sys.argv[1:]
    
    if len(args) >= 2:
        clean_name = args[0]
        raw_path = args[1]
    elif len(args) == 1:
        raw_path = args[0]
        name_part = os.path.basename(raw_path.rstrip('/'))
        if not name_part:
            name_part = "Favourites"
        clean_name = os.path.splitext(name_part)[0]
    else:
        log("No arguments provided", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("错误", "未提供参数", xbmcgui.NOTIFICATION_ERROR)
        return
        
    log(f"Cover name: {clean_name}")
    log(f"Raw path argument: {raw_path}")
    path = unquote(raw_path)
    log(f"Decoded path: {path}")
    
    if path.startswith("special://"):
        process_path = xbmcvfs.translatePath(path)
    elif path.endswith(".xsp"):
        process_path = path 
    else:
        process_path = path

    jrpc = JRPCHelper()
    
    # 1. Get posters from specific path/XSP
    poster_urls = jrpc.get_posters_from_path(process_path)
    log(f"Initial posters found: {len(poster_urls)}")
    
    # 2. Fill up with random library posters if needed
    TARGET_COUNT = 9
    if len(poster_urls) < TARGET_COUNT:
        needed = TARGET_COUNT - len(poster_urls)
        log(f"Need {needed} more posters. Fetching from library...")
        random_posters = jrpc.get_random_posters_from_library(needed, poster_urls)
        poster_urls.extend(random_posters)
        
    if not poster_urls:
        log("No posters found at all", xbmc.LOGWARNING)
        xbmcgui.Dialog().notification("提示", "媒体库中未找到任何海报", xbmcgui.NOTIFICATION_INFO)
        return

    # 3. Download posters locally
    local_posters = []
    for i, url in enumerate(poster_urls):
        # Limit to 9 just in case we got more
        if len(local_posters) >= 9:
            break
            
        temp_file = os.path.join(TEMP_DIR, f"temp_poster_{i}.jpg")
        temp_file_translated = xbmcvfs.translatePath(temp_file)
        if jrpc.download_image(url, temp_file_translated):
            local_posters.append(temp_file_translated) 

    if not local_posters:
        log("Failed to download any posters", xbmc.LOGERROR)
        return

    generator = CoverGenerator()
    import time
    timestamp = int(time.time())
    filename = f"{clean_name}_{timestamp}.png"
    
    result_file = generator.generate(local_posters, clean_name, filename)
    
    # Cleanup temp files
    for f in local_posters:
        if xbmcvfs.exists(f):
            xbmcvfs.delete(f)
            
    if result_file:
        cmd = f'Skin.SetString(favcover,"{result_file}")'
        log(f"Executing: {cmd}")
        xbmc.executebuiltin(cmd)
    else:
        xbmcgui.Dialog().notification("失败", "封面生成失败", xbmcgui.NOTIFICATION_ERROR)

if __name__ == "__main__":
    main()