# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import time
import os
import gc
import traceback
import subprocess
import threading

# 全局常量配置【✨修复：新增传输稳定期阈值】
TEST_DURATION = 30          # 最大测速时长：30秒
MAX_READ_SIZE = 600 * 1024 * 1024  # 最大读取数据量：600MB (字节)
BUFFER_SIZE = 1024 * 1024   # 分块读取大小 1MB，兼顾精度和内存
MIN_FILE_SIZE = 1024 * 1024 * 1024  # 最低测试文件要求：1GB (字节)
MIN_VALID_TIME = 1          # 防除零阈值
STABILIZATION_DURATION = 2  # ✨修复：传输稳定期（前2秒不统计最低/最高速度）
LOG_TAG = "[网盘测速工具-全协议版] - "
# 支持的网络协议白名单【重点】，覆盖所有常用局域网/网盘协议
SUPPORT_PROTOCOLS = [
    "smb://", "nfs://", "webdav://", "dav://",  # 核心局域网/网盘协议
    "http://", "https://", "ftp://", "ftps://", # 流媒体/远程文件协议
    "" # 空值代表本地路径 (C:/xxx / /storage/xxx)
]

# ===================== 标准分级日志【不变】 =====================
def log_debug(msg):
    xbmc.log(f"{LOG_TAG}DEBUG: {str(msg)}", level=xbmc.LOGDEBUG)
def log_info(msg):
    xbmc.log(f"{LOG_TAG}INFO: {str(msg)}", level=xbmc.LOGINFO)
def log_warning(msg):
    xbmc.log(f"{LOG_TAG}WARNING: {str(msg)}", level=xbmc.LOGWARNING)
def log_error(msg):
    xbmc.log(f"{LOG_TAG}ERROR: {str(msg)}", level=xbmc.LOGERROR)

# 核心保留：协议类型自动识别函数【精准判断】
def get_file_protocol(file_path):
    """传入文件路径，返回对应的协议类型名称，无协议则返回本地路径"""
    if not file_path:
        return "未知协议"
    file_path_lower = file_path.lower()
    if file_path_lower.startswith("smb://"):
        return "SMB 局域网共享"
    elif file_path_lower.startswith("nfs://"):
        return "NFS 局域网高速共享"
    elif file_path_lower.startswith(("webdav://", "dav://")):
        return "WEBDAV 远程/网盘挂载"
    elif file_path_lower.startswith(("http://", "https://")):
        return "HTTP/HTTPS 流媒体"
    elif file_path_lower.startswith(("ftp://", "ftps://")):
        return "FTP 远程文件"
    else:
        return "网盘挂载路径"

# 核心保留：协议合规性校验函数
def is_supported_protocol(file_path):
    """校验文件路径是否属于支持的协议白名单，返回布尔值"""
    if not file_path:
        return False
    file_path_lower = file_path.lower()
    for proto in SUPPORT_PROTOCOLS:
        if file_path_lower.startswith(proto):
            return True
    return False

# ========== 深度内存清理函数【精简优化，无缓存变量清理】 ==========
def clear_memory(var_list=None):
    log_info("开始执行【深度内存清理】流程")
    if var_list and isinstance(var_list, list):
        log_info(f"待清理变量列表：{len(var_list)}个，开始逐个删除")
        for idx, var in enumerate(var_list):
            try:
                del var
                log_debug(f"成功删除第{idx+1}个临时变量")
            except Exception as e:
                log_warning(f"删除变量失败：{str(e)}，跳过该变量")
    gc.collect()
    log_info("已执行Python强制垃圾回收 gc.collect()")
    xbmc.executebuiltin("ClearCache")
    log_info("已执行KODI内置缓存清理 ClearCache")
    xbmcgui.Window(10000).clearProperty("SpeedTestTempData")
    log_info("已清除KODI窗口临时属性 SpeedTestTempData")
    log_info("【深度内存清理】流程执行完毕，无内存残留")

# 新增：检测系统类型函数
def detect_system_type():
    """检测当前运行系统类型"""
    try:
        # 获取Kodi系统信息
        system_name = xbmc.getInfoLabel('System.Name')
        system_platform = xbmc.getInfoLabel('System.Platform')
        
        if system_name:
            system_name_lower = system_name.lower()
            if 'coreelec' in system_name_lower or 'libreelec' in system_name_lower or 'osmc' in system_name_lower:
                return 'COREELEC'
        
        if system_platform:
            system_platform_lower = system_platform.lower()
            if 'linux' in system_platform_lower:
                # 尝试检测是否为COREELEC
                if os.path.exists('/flash/') or os.path.exists('/usr/bin/coreelec'):
                    return 'COREELEC'
        
        # 尝试从系统路径检测
        if os.path.exists('/flash/'):
            return 'COREELEC'
        
        # 默认认为不是COREELEC系统
        return 'OTHER'
    except Exception as e:
        log_warning(f"检测系统类型时出错: {str(e)}, 默认返回OTHER")
        return 'OTHER'

# 新增：服务器连通性测试函数
def test_server_connectivity():
    """测试服务器连通性，带倒计时和超时处理"""
    log_info("开始执行服务器连通性测试")
    
    # 检测系统类型
    system_type = detect_system_type()
    log_info(f"检测到系统类型: {system_type}")
    
    if system_type != 'COREELEC':
        # 如果不是COREELEC系统，直接弹出提示
        log_info("非COREELEC系统，不支持连通性验证")
        dialog = xbmcgui.Dialog()
        dialog.ok("连通性验证", "[COLOR yellow]您的系统不支持图片服务器连通性验证！[/COLOR]")
        return
    
    # 显示倒计时进度条
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("服务器连通性测试", "正在测试服务器连通性。。。")
    
    # 存储结果的变量
    result_success = [False]
    result_output = [""]
    
    def run_connectivity_test():
        """在子线程中执行连通性测试命令"""
        try:
            # COREELEC系统使用curl命令
            log_info("执行curl -I https://www.google.com 命令")
            process = subprocess.run(
                ["curl", "-I", "https://www.google.com"],
                capture_output=True,
                text=True,
                timeout=20  # 设置20秒超时
            )
            result_output[0] = process.stdout
            # 只要命令成功执行就认为成功，不需要特定关键词
            result_success[0] = process.returncode == 0
            log_info(f"curl命令执行完成，返回码: {process.returncode}, 成功: {result_success[0]}")
        except subprocess.TimeoutExpired:
            log_warning("连通性测试命令执行超时")
            result_success[0] = False
        except Exception as e:
            log_error(f"连通性测试命令执行异常: {str(e)}")
            result_success[0] = False
    
    # 启动子线程执行测试
    test_thread = threading.Thread(target=run_connectivity_test)
    test_thread.daemon = True
    test_thread.start()
    
    # 开始倒计时
    countdown = 20
    while countdown > 0 and test_thread.is_alive():
        progress_percent = int((20 - countdown) * 5)  # 20秒对应100%
        progress_dialog.update(progress_percent, f"正在测试服务器连通性。。。剩余 {countdown} 秒")
        
        # 检查用户是否取消
        if progress_dialog.iscanceled():
            log_info("用户取消了服务器连通性测试")
            progress_dialog.close()
            return
        
        time.sleep(1)
        countdown -= 1
    
    # 关闭进度条
    progress_dialog.close()
    
    # 检查测试结果
    if result_success[0]:
        log_info("服务器连通性测试成功")
        dialog = xbmcgui.Dialog()
        dialog.ok("连通性测试结果", "[COLOR green]您的系统与图片服务器连接正常！[/COLOR]")
    else:
        log_info("服务器连通性测试失败")
        dialog = xbmcgui.Dialog()
        dialog.ok("连通性测试结果", "[COLOR red]您的系统与图片服务器未正常连接，请排查原因！[/COLOR]")

def main():
    log_info("="*50)
    log_info("网盘测速工具【全协议版-纯读取】程序正式启动 | 支持 SMB/NFS/WEBDAV/本地 | 随读随弃 0内存缓存")
    log_info("="*50)
    log_debug(f"核心配置：测速{TEST_DURATION}秒 | 最大读取{MAX_READ_SIZE/1024/1024:.1f}MB | 分块{BUFFER_SIZE/1024/1024:.1f}MB | 最小文件{MIN_FILE_SIZE/1024/1024/1024:.1f}GB | 稳定期{STABILIZATION_DURATION}秒") # ✨修复：日志新增稳定期
    log_debug(f"支持协议：{SUPPORT_PROTOCOLS}")
    dialog = xbmcgui.Dialog()

    # ===================== 第一步：弹出测速类型三选一选择窗 =====================
    speed_type_title = "请选择测速类型"
    speed_type_list = [
        "已挂载网盘测速",
        "局域网NAS/SMB/NFS/webdav测速",
        "木第连通性验证"  # 修改选项名称
    ]
    log_info("弹出测速类型选择弹窗，等待用户选择测速模式")
    select_type = dialog.select(speed_type_title, speed_type_list)
    
    # 用户取消选择，直接退出
    if select_type == -1:
        log_info("用户点击【取消】选择测速类型，退出测速程序")
        clear_memory()
        return
    
    # 如果选择的是"木第连通性验证"选项
    if select_type == 2:
        log_info("用户选择了：木第连通性验证")
        test_server_connectivity()
        clear_memory()
        return
    
    # ===================== 第二步：根据选择的类型，执行对应逻辑+统一确认弹窗 =====================
    confirm_title = "测速确认提示"
    confirm_msg = "点击确认后请选择视频文件继续测速（≥1GB最佳）！"
    log_info(f"用户选择了：{speed_type_list[select_type]}")
    
    # 弹出统一的确认窗口
    if not dialog.ok(confirm_title, confirm_msg):
        log_info("用户点击【取消】确认弹窗，退出测速程序")
        clear_memory()
        return

    # ===================== 第三步：根据选择的类型，加载对应文件选择窗参数 =====================
    select_file = ""
    if select_type == 0:
        # 选项1：已挂载网盘测速 → 限定video分类的文件选择窗
        file_title = "请选择【已挂载网盘】的视频文件 ≥1GB"
        select_file = dialog.browseSingle(1, file_title, "video", "", False, False, "")
    elif select_type == 1:
        # 选项2：局域网NAS测速 → 无分类限制的文件选择窗（原参数）
        file_title = "请选择【局域网】视频文件【SMB/NFS/WEBDAV】≥1GB"
        select_file = dialog.browseSingle(1, file_title, "", "", False, False, "")

    # ===================== 第四步：循环文件选择+【全协议增强校验】核心环节 =====================
    while True:
        # 1. 无文件选择，直接退出
        if not select_file or select_file == "":
            log_info("用户未选择任何文件，取消测速")
            dialog.notification("测速取消", "未选择任何视频文件", xbmcgui.NOTIFICATION_INFO, 3000)
            clear_memory()
            return
        
        # 协议合规性校验
        if not is_supported_protocol(select_file):
            file_proto = get_file_protocol(select_file)
            log_warning(f"选中文件协议不支持：{file_proto} | 路径：{select_file}")
            dialog.ok("协议不支持", f"当前文件为【{file_proto}】\n该协议暂不支持测速，请选择：\n✅ SMB局域网 / ✅ NFS / ✅ WEBDAV / ✅ 本地文件")
            # 重新选择文件，沿用当前测速类型的文件选择窗参数
            if select_type == 0:
                select_file = dialog.browseSingle(1, file_title, "video", "", False, False, "")
            else:
                select_file = dialog.browseSingle(1, file_title, "", "", False, False, "")
            continue
        
        # 增强校验：网络文件+本地文件 通用存在性校验
        if not xbmcvfs.exists(select_file):
            file_proto = get_file_protocol(select_file)
            log_warning(f"{file_proto} 文件不存在：{select_file}")
            dialog.ok("文件错误", f"【{file_proto}】\n选择的文件不存在，请重新选择！")
            # 重新选择文件，沿用当前测速类型的文件选择窗参数
            if select_type == 0:
                select_file = dialog.browseSingle(1, file_title, "video", "", False, False, "")
            else:
                select_file = dialog.browseSingle(1, file_title, "", "", False, False, "")
            continue
        
        # 原有校验：文件大小≥1GB强制校验
        file_size = xbmcvfs.File(select_file).size()
        file_proto = get_file_protocol(select_file)
        file_size_gb = round(file_size / (1024 * 1024 * 1024), 2)
        log_debug(f"选中文件：【{file_proto}】 | 路径：{select_file} | 大小：{file_size_gb}GB")
        
        if file_size < MIN_FILE_SIZE:
            log_warning(f"{file_proto} 文件过小：{file_size_gb}GB < 1GB")
            dialog.ok("文件过小提醒", f"【{file_proto}】\n文件大小：{file_size_gb}GB，小于1GB可能测速不准，请选择更大的文件！")
            # 重新选择文件，沿用当前测速类型的文件选择窗参数
            if select_type == 0:
                select_file = dialog.browseSingle(1, file_title, "video", "", False, False, "")
            else:
                select_file = dialog.browseSingle(1, file_title, "", "", False, False, "")
            continue
        
        # 所有校验通过，跳出循环
        log_info(f"✅ 所有校验通过 | 【{file_proto}】 | {file_size_gb}GB | {select_file}")
        break

    # ===================== 初始化核心参数 =====================
    total_bytes_read = 0  # 仅统计读取的总字节数，无缓存
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("全协议网速测速中", f"【{get_file_protocol(select_file)}】\n等待文件响应中，请稍候...")
    is_running = True
    is_test_started = False
    start_time = 0.0         
    avg_speed_mb = 0.0
    avg_speed_mbps = 0.0
    total_mb = 0.0
    file_proto = get_file_protocol(select_file)
    
    # 初始化最高/最低网速（关键：最低网速初始设为极大值，最高初始为0）
    max_speed_mb = 0.0       # 最高网速（MB/s）
    min_speed_mb = float('inf')  # 最低网速（MB/s），初始为无穷大
    stability_rate = 0.0     # 网络稳定度（百分比）
    
    log_info(f"初始化参数完成，当前测速协议：{file_proto} | 纯读取模式 无内存缓存 | 稳定期{STABILIZATION_DURATION}秒")

    # ===================== 第五步：纯读取测速+双终止+防除零【✨修复：稳定期后再统计速度】 =====================
    try:
        log_info(f"使用KODI官方xbmcvfs打开【{file_proto}】文件：{select_file}")
        f_src = xbmcvfs.File(select_file, 'r')
        log_info("文件打开成功，进入【纯读取】分块测速循环 - 读取后立即丢弃，不缓存")
        
        while is_running:
            if progress_dialog.iscanceled():
                log_info("用户点击取消，终止测速")
                is_running = False
                break

            # xbmcvfs 二进制分块读取，完美兼容所有协议
            buffer = f_src.readBytes(BUFFER_SIZE)
            if not buffer:
                log_info(f"{file_proto} 文件读取完毕，终止测速")
                break

            # 精准计时：读到真实数据才开始计时，排除网络响应时间
            if not is_test_started:
                start_time = time.time()
                is_test_started = True
                log_info(f"✅ 首次读取到有效数据，启动精准计时（前{STABILIZATION_DURATION}秒为稳定期，不统计速度）")
                progress_dialog.update(0, f"【{file_proto}】测速正式开始\n计时30秒/读取600MB，先到为准...\n📌 前{STABILIZATION_DURATION}秒为连接稳定期，不统计速度") # ✨修复：进度条提示稳定期
            
            if is_test_started and start_time > 0:
                # 核心修改 关键行：仅累加读取字节数，不保存buffer，读完直接丢弃，无内存占用
                total_bytes_read += len(buffer)

                # 时间计算+防除零过滤
                current_time = time.time()
                elapsed_time = round(current_time - start_time, 1)
                elapsed_time = MIN_VALID_TIME if elapsed_time < MIN_VALID_TIME else elapsed_time
                remaining_time = max(0, round(TEST_DURATION - elapsed_time, 1))

                # 双终止条件（谁先到谁生效）：30秒 或 读取满600MB
                total_mb_read = round(total_bytes_read / (1024 * 1024), 1)
                if elapsed_time >= TEST_DURATION or total_bytes_read >= MAX_READ_SIZE:
                    if elapsed_time >= TEST_DURATION:
                        log_info(f"触发终止条件1：测速时长达标 {elapsed_time}秒")
                    else:
                        log_info(f"触发终止条件2：累计读取达标 {total_mb_read}MB")
                    is_running = False
                    break

                # 实时速度计算（公式不变，数据来源为纯读取字节数）
                real_speed_mb = round(total_mb_read / elapsed_time, 1) if elapsed_time > 0 else 0.0
                real_speed_mbps = round(real_speed_mb * 8, 1)
                
                # ✨修复：仅当超过稳定期后，才更新最高/最低网速（排除初始连接的低速度）
                if real_speed_mb > 0 and elapsed_time > STABILIZATION_DURATION:
                    if real_speed_mb > max_speed_mb:
                        max_speed_mb = real_speed_mb  # 更新最高网速
                    if real_speed_mb < min_speed_mb:
                        min_speed_mb = real_speed_mb  # 更新最低网速
                # 稳定期内提示日志
                elif elapsed_time <= STABILIZATION_DURATION and real_speed_mb > 0:
                    log_debug(f"稳定期内（{elapsed_time}秒），暂不统计速度：{real_speed_mb}MB/s")
                
                log_debug(f"实时数据 | {elapsed_time}s/{remaining_time}s | {total_mb_read}MB | {real_speed_mb}MB/s({real_speed_mbps}Mbps) | 最高：{max_speed_mb}MB/s | 最低：{min_speed_mb}MB/s")

                # 更新进度条（文字改为累计读取）
                progress_percent = int((max(elapsed_time/TEST_DURATION, total_bytes_read/MAX_READ_SIZE)) * 100)
                # ✨修复：进度条区分稳定期状态
                if elapsed_time <= STABILIZATION_DURATION:
                    progress_text = f"【{file_proto}】\n已测速：{elapsed_time}秒 | 剩余：{remaining_time}秒\n" \
                                    f"当前速度：{real_speed_mb} MB/s ({real_speed_mbps} Mbps)\n" \
                                    f"累计读取：{total_mb_read} MB / 600 MB\n" \
                                    f"📌 处于{STABILIZATION_DURATION}秒稳定期，暂不统计最高/最低"
                else:
                    progress_text = f"【{file_proto}】\n已测速：{elapsed_time}秒 | 剩余：{remaining_time}秒\n" \
                                    f"当前速度：{real_speed_mb} MB/s ({real_speed_mbps} Mbps)\n" \
                                    f"累计读取：{total_mb_read} MB / 600 MB\n" \
                                    f"最高/最低：{max_speed_mb} / {min_speed_mb} MB/s"
                progress_dialog.update(progress_percent, progress_text)

            time.sleep(0.01)

    except ZeroDivisionError:
        err_msg = "测速中断，未获取到有效测速数据！"
        log_error(f"{err_msg} | {traceback.format_exc()}")
        progress_dialog.close()
        dialog.ok("测速提示", err_msg)
        clear_memory([total_bytes_read])
        return
    except Exception as e:
        # 协议专属异常提示：针对不同协议给出不同解决方案
        err_proto_tips = ""
        if file_proto == "SMB 局域网共享":
            err_proto_tips = "请检查SMB共享权限/局域网连接/账号密码！"
        elif file_proto == "NFS 局域网高速共享":
            err_proto_tips = "请检查NFS挂载配置/局域网连通性！"
        elif file_proto == "WEBDAV 远程/网盘挂载":
            err_proto_tips = "请检查WEBDAV地址/账号密码/网盘挂载状态！"
        err_msg = f"【{file_proto}】测速异常：{str(e)}\n{err_proto_tips}"
        log_error(f"{err_msg} | {traceback.format_exc()}")
        progress_dialog.close()
        dialog.ok("测速出错", err_msg)
        clear_memory([total_bytes_read])
        return
    finally:
        # 手动关闭文件句柄，释放网络连接，防止内存泄漏
        if 'f_src' in locals() and f_src:
            f_src.close()
            log_info(f"已关闭【{file_proto}】文件句柄，释放网络连接")
        progress_dialog.close()
        log_info("测速循环结束，关闭进度条弹窗")

    # ===================== 第六步：精准统计平均速度+稳定度【✨修复：处理稳定期后无数据的情况】 =====================
    log_info("进入测速结果统计阶段，计算平均读取速度+网络稳定度")
    if is_test_started and start_time > 0 and total_bytes_read > 0:
        end_time = time.time()
        actual_elapsed = round(end_time - start_time, 1)
        actual_elapsed = TEST_DURATION if actual_elapsed >= TEST_DURATION else actual_elapsed
        actual_elapsed = MIN_VALID_TIME if actual_elapsed < MIN_VALID_TIME else actual_elapsed
        
        total_mb = round(total_bytes_read / (1024 * 1024), 1)
        avg_speed_mb = round(total_mb / actual_elapsed, 1) if actual_elapsed > 0 else 0.0
        avg_speed_mbps = round(avg_speed_mb * 8, 1)
        
        # 计算网络稳定度（防除零+处理稳定期后无数据的情况）
        if max_speed_mb > 0 and min_speed_mb != float('inf'):
            stability_rate = round((min_speed_mb / max_speed_mb) * 100, 1)
        elif elapsed_time <= STABILIZATION_DURATION:
            # 测速全程都在稳定期内，无有效统计数据
            stability_rate = 0.0
            log_warning(f"测速时长{elapsed_time}秒≤稳定期{STABILIZATION_DURATION}秒，无法计算稳定度")
        else:
            stability_rate = 0.0  # 无有效数据时稳定度为0
        
        log_info("="*30 + "测速结果统计" + "="*30)
        log_info(f"文件协议：{file_proto}")
        log_info(f"实际测速耗时：{actual_elapsed} 秒")
        log_info(f"累计读取数据：{total_mb} MB")
        log_info(f"平均读取速度：{avg_speed_mb} MB/s | {avg_speed_mbps} Mbps")
        log_info(f"最高读取速度：{max_speed_mb} MB/s（稳定期后）")  # ✨修复：标注稳定期后
        log_info(f"最低读取速度：{min_speed_mb} MB/s（稳定期后）")  # ✨修复：标注稳定期后
        log_info(f"网络稳定度：{stability_rate}%（仅统计稳定期后数据）")      # ✨修复：标注统计范围
        log_info("="*66)
    else:
        log_warning("未获取到有效测速数据，无法计算平均速度和稳定度")

    # ===================== 第七步：测速结果弹窗【优化稳定度提示】 =====================
    result_title = "✅ 全协议网速测速结果【纯读取+稳定性分析】"
    # 先判断稳定度，再决定提示内容
    if stability_rate < 70 and stability_rate > 0:
        # 稳定度<70%：强制提示卡顿风险，忽略平均网速
        result_msg = f"【文件协议：{file_proto}】\n⚠️ 网络稳定度偏低！稳定度：{stability_rate}% < 70% \n平均速度：{avg_speed_mb} MB/s ({avg_speed_mbps} Mbps)\n最高速度：{max_speed_mb} MB/s | 最低速度：{min_speed_mb} MB/s\n网速的稳定性不好，波动较大，请优化网络稳定性！"
    elif stability_rate == 0 and elapsed_time <= STABILIZATION_DURATION:
        # 稳定期内无有效数据
        result_msg = f"【文件协议：{file_proto}】\n❌ 测速时长{elapsed_time}秒≤稳定期{STABILIZATION_DURATION}秒\n无法统计有效稳定度，请重新测速（确保测速时长超过{STABILIZATION_DURATION}秒）！\n平均速度：{avg_speed_mb} MB/s ({avg_speed_mbps} Mbps)"
    elif stability_rate == 0:
        # 无有效稳定度数据
        result_msg = f"【文件协议：{file_proto}】\n❌ 未获取到有效测速数据\n无法计算网络稳定度，请重新选择文件测速！"
    else:
        # 稳定度≥70%：沿用原有分级提示
        if avg_speed_mb < 12.5:
            result_msg = f"【文件协议：{file_proto}】\n您的网络读取速度小于100mbps\n平均速度：{avg_speed_mb} MB/s ({avg_speed_mbps} Mbps)\n最高速度：{max_speed_mb} MB/s | 最低速度：{min_speed_mb} MB/s  稳定度：{stability_rate}% \n观看蓝光原盘将会卡顿，请排查网络问题！"
        elif 12.5 <= avg_speed_mb < 25:
            result_msg = f"【文件协议：{file_proto}】\n您的网络读取速度在100mbps～200mbps之间\n平均速度：{avg_speed_mb} MB/s ({avg_speed_mbps} Mbps)\n最高速度：{max_speed_mb} MB/s | 最低速度：{min_speed_mb} MB/s  稳定度：{stability_rate}%\n基本符合蓝光原盘播放，极限状态可能卡顿, 请继续优化！"
        elif 25 <= avg_speed_mb < 37.5:
            result_msg = f"【文件协议：{file_proto}】\n您的网络读取速度超过200mbps\n平均速度：{avg_speed_mb} MB/s ({avg_speed_mbps} Mbps)\n最高速度：{max_speed_mb} MB/s | 最低速度：{min_speed_mb} MB/s  稳定度：{stability_rate}%\n🎉 完全满足蓝光原盘全速播放需求，请继续保持！"
        else:
            result_msg = f"【文件协议：{file_proto}】\n您的网络读取速度超过300mbps\n平均速度：{avg_speed_mb} MB/s ({avg_speed_mbps} Mbps)\n最高速度：{max_speed_mb} MB/s | 最低速度：{min_speed_mb} MB/s  稳定度：{stability_rate}%\n🎉 完全满足蓝光原盘全速播放需求，完全不用担心网速问题！"

    log_info("弹出测速结果弹窗，等待用户确认")
    dialog.ok(result_title, result_msg)

    # ===================== 第八步：深度清理内存+退出 =====================
    log_info("用户已确认结果，执行最终内存清理")
    # 清理所有变量，包括新增的稳定期相关变量
    clear_memory([total_bytes_read, avg_speed_mb, avg_speed_mbps, total_mb, select_file, max_speed_mb, min_speed_mb, stability_rate])
    log_info("全协议版测速工具【纯读取】执行完毕，正常退出")
    log_info("="*50)
    return

if __name__ == "__main__":
    main()