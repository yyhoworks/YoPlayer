import xbmc
import random
import colorsys
import datetime

# 预设颜色列表 (参考用)
PRESET_COLORS = [
    "5528a8", 
    "f4511e", 
    "00b8d4", 
    "e91e63", 
    "0091ea", 
    "CCFF00", 
    "7C4DFF", 
    "FFD740", 
    "D500F9"
]

def hsl_to_hex(h, s, l):
    """
    将 HSL 颜色转换为 6位大写 HEX 字符串
    """
    h_norm = h / 360.0
    # colorsys 使用 HLS 顺序: Hue, Lightness, Saturation
    r, g, b = colorsys.hls_to_rgb(h_norm, l, s)
    
    r_int = int(round(r * 255))
    g_int = int(round(g * 255))
    b_int = int(round(b * 255))
    
    return "{:02X}{:02X}{:02X}".format(r_int, g_int, b_int)

def hex_to_rgb_float(hex_color):
    """
    将 HEX 字符串转换为 0.0-1.0 范围的 RGB 元组
    """
    if len(hex_color) != 6:
        return (0.0, 0.0, 0.0)
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return (0.0, 0.0, 0.0)

def get_luminance(rgb_tuple):
    """
    计算相对亮度 (Relative Luminance)
    输入: (r, g, b) 范围 0.0-1.0
    返回: 0.0 - 1.0
    """
    def linearize(c):
        if c <= 0.03928:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    r_lin = linearize(rgb_tuple[0])
    g_lin = linearize(rgb_tuple[1])
    b_lin = linearize(rgb_tuple[2])

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def get_contrast_ratio(hex_color_1, hex_color_2):
    """
    计算两个 HEX 颜色之间的对比度 (WCAG 2.0)
    返回对比度比值 (例如 4.5, 7.0 等)
    """
    rgb1 = hex_to_rgb_float(hex_color_1)
    rgb2 = hex_to_rgb_float(hex_color_2)
    
    l1 = get_luminance(rgb1)
    l2 = get_luminance(rgb2)
    
    # 确保 l1 是较亮的颜色
    lighter = max(l1, l2)
    darker = min(l1, l2)
    
    # 对比度公式: (L1 + 0.05) / (L2 + 0.05)
    return (lighter + 0.05) / (darker + 0.05)

def run():
    # 1. 初始化：清空 daycolor
    xbmc.executebuiltin('Skin.SetString(daycolor,"")')
    
    # 2. 判断是否为星期五
    is_friday = datetime.datetime.now().weekday() == 4
    
    if is_friday:
        # 星期五：清空 customcolor 并退出
        xbmc.executebuiltin('Skin.SetString(customcolor,"")')
        return
    else:
        # 非星期五：决定使用预设还是随机生成
        use_preset = random.random() < 0.5
        
        if use_preset:
            selected_hex = random.choice(PRESET_COLORS).upper()
        else:
            # 随机生成高饱和度颜色
            h = random.uniform(0, 360)
            s = random.uniform(0.85, 1.0)  # 高饱和度
            l = random.uniform(0.3, 0.7)   # 较宽的亮度范围
            selected_hex = hsl_to_hex(h, s, l)
            
        # 确保大写
        selected_hex = selected_hex.upper()
        
        # 验证 HEX 格式有效性
        if len(selected_hex) != 6:
            # 如果生成失败，回退到默认安全色
            selected_hex = "333333" 
            
        final_color_code = "FF" + selected_hex
        
        # 执行：设置 customcolor
        cmd_color = 'Skin.SetString(customcolor,"{}")'.format(final_color_code)
        xbmc.executebuiltin(cmd_color)
        
        # 3. 优化的对比度检查
        # 目标文字颜色：白色 (#FFFFFF)
        WHITE_HEX = "FFFFFF"
        
        # 计算背景色与白色的对比度
        contrast = get_contrast_ratio(selected_hex, WHITE_HEX)
        
        # WCAG AA 标准要求普通文本对比度至少为 4.5:1
        # 如果对比度小于 4.5，说明白色文字看不清，需要标记
        CONTRAST_THRESHOLD = 4.5
        
        if contrast < CONTRAST_THRESHOLD:
            # 对比度不足：设置 daycolor 为 1
            # 皮肤可根据此变量切换为黑色文字或添加文字阴影
            xbmc.executebuiltin('Skin.SetString(daycolor,1)')
        else:
            # 对比度充足：daycolor 保持为空
            pass
            
        return

if __name__ == '__main__':
    run()