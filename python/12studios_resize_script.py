# -*- coding: utf-8 -*-
import os
from PIL import Image
import concurrent.futures
import time

# --- 配置 ---
# 要搜索的根目录
TARGET_DIR = 'studios'
# 要查找并调整大小的文件名 (不区分大小写)
TARGET_FILENAME = 'landscape.jpg'
# 调整后的新高度（单位：像素），宽度将自适应
NEW_HEIGHT = 50
# 使用的线程数 (None 表示让Python自动选择，对于IO密集型任务，可以设置稍高一些，如 16 或 32)
MAX_WORKERS = None

def process_single_image(file_path):
    """
    处理单个图片文件。
    如果图片高度不等于 NEW_HEIGHT，则进行缩放并覆盖保存。
    返回一个状态元组: (状态字符串, 文件路径)。
    状态字符串为: 'processed', 'skipped', 'failed'。
    """
    try:
        with Image.open(file_path) as img:
            # 如果高度已经是目标高度，则跳过
            if img.height == NEW_HEIGHT:
                return "skipped", file_path

            # 计算新的宽度以保持宽高比
            # (新宽度 / 新高度) = (原宽度 / 原高度)
            # 新宽度 = 新高度 * (原宽度 / 原高度)
            aspect_ratio = img.width / img.height
            new_width = int(NEW_HEIGHT * aspect_ratio)

            # 使用高质量的 LANCZOS 算法进行缩放，参数为 (宽度, 高度)
            resized_img = img.resize((new_width, NEW_HEIGHT), Image.LANCZOS)

            # --- 核心修复 ---
            # JPEG格式不支持透明度(如 RGBA, LA)或调色板模式(P)。
            # 在保存为JPEG前，最稳妥的方法是统一将图像转换为'RGB'模式。
            # 这会移除Alpha通道，并将调色板或灰度模式转换为标准的RGB。
            if resized_img.mode != 'RGB':
                resized_img = resized_img.convert('RGB')
            # --- 修复结束 ---

            # 覆盖保存原文件，指定高质量
            # 'quality=95' 是一个很好的平衡点
            # 'subsampling=0' 可以保留更多颜色细节，但会增加文件大小，可根据需要开启
            resized_img.save(file_path, 'JPEG', quality=95)
            return "processed", file_path

    except Exception as e:
        # 返回失败状态和错误信息，以便主线程可以打印
        return "failed", f"处理失败: {file_path} - 错误: {e}"

def run_resize_task():
    """
    主函数：查找所有目标图片并使用多线程进行处理。
    """
    # 检查目标目录是否存在
    if not os.path.isdir(TARGET_DIR):
        print(f"错误：目录 '{TARGET_DIR}' 不存在。")
        print(f"请确保此脚本与 '{TARGET_DIR}' 目录在同一个文件夹下。")
        return

    # 1. 首先，收集所有需要处理的图片路径
    image_paths_to_process = []
    print(f"正在 '{TARGET_DIR}' 目录中搜索 '{TARGET_FILENAME}'...")
    for root, _, files in os.walk(TARGET_DIR):
        for filename in files:
            if filename.lower() == TARGET_FILENAME.lower():
                image_paths_to_process.append(os.path.join(root, filename))

    if not image_paths_to_process:
        print(f"在 '{TARGET_DIR}' 目录中未找到任何名为 '{TARGET_FILENAME}' 的图片。")
        return

    print(f"找到 {len(image_paths_to_process)} 张目标图片，开始多线程处理...")
    start_time = time.time()

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    # 2. 使用线程池并发处理所有图片
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 创建一个 future 到路径的映射，以便处理结果
        future_to_path = {executor.submit(process_single_image, path): path for path in image_paths_to_process}

        # as_completed 会在任务完成时立即返回结果，而不是等待所有任务结束
        for future in concurrent.futures.as_completed(future_to_path):
            try:
                status, result_info = future.result()
                if status == 'processed':
                    processed_count += 1
                elif status == 'skipped':
                    skipped_count += 1
                elif status == 'failed':
                    failed_count += 1
                    # 打印详细的错误信息
                    print(result_info)
            except Exception as exc:
                # 捕获在任务执行期间可能发生的意外异常
                path = future_to_path[future]
                failed_count += 1
                print(f"处理 {path} 时发生严重错误: {exc}")


    end_time = time.time()

    # 3. 任务结束，输出最终总结
    print("\n--- 处理完成 ---")
    print(f"总耗时: {end_time - start_time:.2f} 秒")
    print(f"✅ 成功修改: {processed_count} 张图片")
    print(f"⏭️  跳过 (尺寸已符合): {skipped_count} 张图片")
    if failed_count > 0:
        print(f"❌ 处理失败: {failed_count} 张图片，请查看上面的错误日志。")
    else:
        print("🎉 所有图片均处理成功！")


if __name__ == "__main__":
    run_resize_task()