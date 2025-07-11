# -*- coding: utf-8 -*-
import os
from PIL import Image, UnidentifiedImageError
import concurrent.futures
import time

# --- 配置 ---
# 要搜索的根目录
TARGET_DIR = 'studios'
# 要查找的文件基础名 (不区分大小写, 不含扩展名)
TARGET_BASENAME = 'landscape'
# 支持的文件扩展名列表 (小写)
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png']
# 调整后的新高度（单位：像素），宽度将自适应
NEW_HEIGHT = 50
# 使用的线程数 (None 表示让Python自动选择)
MAX_WORKERS = None

# 定义真实格式到首选扩展名的映射
FORMAT_TO_EXT = {
    'JPEG': '.jpg',
    'PNG': '.png'
}

def process_single_image(file_path):
    """
    处理单个图片文件。
    1. 检查文件真实格式，如果扩展名不匹配，则准备重命名。
    2. 如果图片高度不等于 NEW_HEIGHT，则进行缩放。
    3. 以其真实格式保存，并使用正确的扩展名，如果需要则删除旧文件。
    返回一个状态元组: (状态字符串, 消息)。
    状态字符串为: 'processed', 'renamed', 'skipped', 'failed'。
    """
    try:
        # --- 核心强化：检测并纠正扩展名 ---
        with Image.open(file_path) as img:
            # 1. 获取文件的真实格式和当前路径信息
            actual_format = img.format  # e.g., 'JPEG', 'PNG'
            if actual_format not in FORMAT_TO_EXT:
                return "failed", f"不支持的格式: {actual_format} in {file_path}"

            root, filename = os.path.split(file_path)
            basename, current_ext = os.path.splitext(filename)

            # 2. 确定正确的文件扩展名和最终输出路径
            correct_ext = FORMAT_TO_EXT[actual_format]
            output_path = os.path.join(root, basename + correct_ext)

            # 检查是否需要重命名 (扩展名与真实格式不符)
            needs_rename = (file_path.lower() != output_path.lower())

            # 3. 检查尺寸是否需要调整
            needs_resize = (img.height != NEW_HEIGHT)

            # 如果尺寸符合且无需重命名，则完全跳过
            if not needs_resize and not needs_rename:
                return "skipped", f"尺寸符合且文件名正确: {file_path}"

            # --- 执行处理 ---
            # 只有在需要时才进行缩放，节省性能
            if needs_resize:
                aspect_ratio = img.width / img.height
                new_width = int(NEW_HEIGHT * aspect_ratio)
                resized_img = img.resize((new_width, NEW_HEIGHT), Image.LANCZOS)
            else:
                # 如果只是重命名，不需要缩放，直接使用原图
                resized_img = img

            # 4. 根据真实格式保存
            if actual_format == 'JPEG':
                if resized_img.mode not in ('RGB', 'L'):
                    resized_img = resized_img.convert('RGB')
                resized_img.save(output_path, format='JPEG', quality=95)
            elif actual_format == 'PNG':
                resized_img.save(output_path, format='PNG', optimize=True)

            # 5. 如果重命名了，删除旧文件
            if needs_rename:
                os.remove(file_path)
                return "renamed", f"处理并修正文件名: {file_path} -> {output_path}"
            else:
                return "processed", f"成功处理: {file_path}"

    except UnidentifiedImageError:
        return "failed", f"无法识别的图片文件: {file_path}"
    except Exception as e:
        return "failed", f"处理失败: {file_path} - 错误: {e}"

def run_resize_task():
    """
    主函数：查找所有目标图片并使用多线程进行处理。
    """
    if not os.path.isdir(TARGET_DIR):
        print(f"错误：目录 '{TARGET_DIR}' 不存在。")
        return

    image_paths_to_process = []
    print(f"正在 '{TARGET_DIR}' 目录中搜索基础名为 '{TARGET_BASENAME}' 的图片...")
    for root, _, files in os.walk(TARGET_DIR):
        for filename in files:
            basename, ext = os.path.splitext(filename)
            if basename.lower() == TARGET_BASENAME.lower() and ext.lower() in SUPPORTED_EXTENSIONS:
                image_paths_to_process.append(os.path.join(root, filename))

    if not image_paths_to_process:
        print(f"在 '{TARGET_DIR}' 目录中未找到任何目标图片。")
        return

    print(f"找到 {len(image_paths_to_process)} 张目标图片，开始多线程处理...")
    start_time = time.time()

    processed_count = 0
    renamed_count = 0
    skipped_count = 0
    failed_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {executor.submit(process_single_image, path): path for path in image_paths_to_process}

        for future in concurrent.futures.as_completed(future_to_path):
            try:
                status, message = future.result()
                if status == 'processed':
                    processed_count += 1
                elif status == 'renamed':
                    renamed_count += 1
                    print(f"✅ {message}") # 对重命名的操作进行显式打印
                elif status == 'skipped':
                    skipped_count += 1
                elif status == 'failed':
                    failed_count += 1
                    print(f"❌ {message}") # 打印失败详情
            except Exception as exc:
                path = future_to_path[future]
                failed_count += 1
                print(f"❌ 处理 {path} 时发生严重错误: {exc}")

    end_time = time.time()

    print("\n--- 处理完成 ---")
    print(f"总耗时: {end_time - start_time:.2f} 秒")
    print(f"✅ 成功修改 (未重命名): {processed_count} 张图片")
    print(f"🔄️ 成功修改 (并修正文件名): {renamed_count} 张图片")
    print(f"⏭️  跳过 (尺寸/文件名均正确): {skipped_count} 张图片")
    if failed_count > 0:
        print(f"❌ 处理失败: {failed_count} 张图片，请查看上面的错误日志。")
    else:
        print("🎉 所有图片均处理成功！")


if __name__ == "__main__":
    run_resize_task()