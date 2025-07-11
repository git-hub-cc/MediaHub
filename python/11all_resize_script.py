# -*- coding: utf-8 -*-
import os
from PIL import Image
import concurrent.futures
import time

# --- 配置 ---
# 要搜索的根目录 (当前目录下的 'studios')
TARGET_DIR = 'all'
# 要查找并调整大小的文件名 (不区分大小写)
TARGET_FILENAME = 'poster.jpg'
# 调整后的新宽度（单位：像素）
NEW_WIDTH = 200
# 使用的线程数 (None 表示让Python自动选择合适的数量)
MAX_WORKERS = None

def process_single_image(file_path):
    """
    处理单个图片文件。
    如果图片宽度不等于 NEW_WIDTH，则进行缩放并覆盖保存。
    返回一个状态字符串: 'processed', 'skipped', 或 'failed'。
    """
    try:
        with Image.open(file_path) as img:
            # 如果宽度已经是目标宽度，则跳过
            if img.width == NEW_WIDTH:
                return "skipped"

            # 计算新的高度以保持宽高比
            aspect_ratio = img.height / img.width
            new_height = int(NEW_WIDTH * aspect_ratio)

            # 使用高质量的 LANCZOS 算法进行缩放
            resized_img = img.resize((NEW_WIDTH, new_height), Image.LANCZOS)

            # --- 关键修复 ---
            # 检查图像模式，如果是有Alpha通道的RGBA，则转换为RGB
            # JPEG格式不支持透明度（Alpha通道），这是导致错误的核心原因。
            # .convert('RGB') 会移除Alpha通道，从而可以被正确保存为JPEG。
            if resized_img.mode == 'RGBA':
                resized_img = resized_img.convert('RGB')
            # --- 修复结束 ---

            # 覆盖保存原文件
            resized_img.save(file_path, 'JPEG', quality=95)
            return "processed"

    except Exception as e:
        # 即使不为每张图片输出成功日志，也应该报告错误，以便排查问题
        print(f"处理失败: {file_path} - 错误: {e}")
        return "failed"

def run_resize_task():
    """
    主函数：查找所有目标图片并使用多线程进行处理。
    """
    # 检查目标目录是否存在
    if not os.path.isdir(TARGET_DIR):
        print(f"错误：目录 '{TARGET_DIR}' 不存在。")
        print("请确保此脚本与 'studios' 目录在同一个文件夹下。")
        return

    # 1. 首先，收集所有需要处理的图片路径
    image_paths_to_process = []
    for root, _, files in os.walk(TARGET_DIR):
        for filename in files:
            if filename.lower() == TARGET_FILENAME:
                image_paths_to_process.append(os.path.join(root, filename))

    if not image_paths_to_process:
        print(f"在 '{TARGET_DIR}' 目录中未找到任何名为 '{TARGET_FILENAME}' 的图片。")
        return

    print(f"找到 {len(image_paths_to_process)} 张目标图片，开始多线程处理...")
    start_time = time.time()

    processed_count = 0
    failed_count = 0 # 增加一个失败计数器，以便更好地总结

    # 2. 使用线程池并发处理所有图片
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # executor.map 会将列表中的每个元素传递给处理函数，并返回一个结果迭代器
        future_to_path = {executor.submit(process_single_image, path): path for path in image_paths_to_process}

        for future in concurrent.futures.as_completed(future_to_path):
            result = future.result()
            if result == 'processed':
                processed_count += 1
            elif result == 'failed':
                failed_count += 1


    end_time = time.time()

    # 3. 任务结束，输出最终总结
    print("\n--- 处理完成 ---")
    print(f"总耗时: {end_time - start_time:.2f} 秒")
    print(f"成功修改了 {processed_count} 张图片。")
    if failed_count > 0:
        print(f"有 {failed_count} 张图片处理失败，请查看上面的错误日志。")


if __name__ == "__main__":
    run_resize_task()