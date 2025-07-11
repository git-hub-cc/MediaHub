# -*- coding: utf-8 -*-
import os
import json

def scan_studio_directory(directory_path, base_working_dir):
    """
    扫描单个制片厂目录，返回找到的Logo信息的字典。
    这是一个辅助函数，被主逻辑调用。
    """
    studios_map = {}
    if not os.path.isdir(directory_path):
        # 如果目录不存在，直接返回空字典，不打印错误，因为这是预期行为
        return studios_map

    print(f"🔎 正在扫描: {directory_path}")

    for studio_name in os.listdir(directory_path):
        studio_path = os.path.join(directory_path, studio_name)
        if os.path.isdir(studio_path):
            # 查找可能的logo文件
            for logo_file in ['landscape.jpg', 'logo.png', 'folder.jpg', 'folder.png']:
                logo_path = os.path.join(studio_path, logo_file)
                if os.path.exists(logo_path):
                    # 从项目根目录计算相对路径
                    relative_path = os.path.relpath(logo_path, base_working_dir).replace(os.path.sep, '/')
                    studios_map[studio_name] = relative_path
                    print(f"  🏢 找到制片厂Logo: {studio_name}")
                    break # 找到一个即可，继续下一个制片厂文件夹

    return studios_map

def summarize_all_studios(output_file='studios_summary.json'):
    """
    扫描所有可能的Emby制片厂目录，并将结果合并生成一个JSON文件。
    """
    print("🚀 开始扫描制片厂信息...")
    current_working_dir = os.getcwd()

    # 定义所有可能的制片厂父目录
    # 根据图片，它们都在 'config/metadata' 下
    metadata_base_dir = os.path.join(current_working_dir, 'config', 'metadata')
    possible_folders = ['studios'] # 检查 'studios' 和 'Studio'

    all_studios_map = {}

    # 遍历所有可能的目录名
    for folder_name in possible_folders:
        studios_directory = os.path.join(metadata_base_dir, folder_name)
        # 调用辅助函数扫描并返回结果
        found_studios = scan_studio_directory(studios_directory, current_working_dir)
        # 将找到的结果合并到主字典中
        all_studios_map.update(found_studios)

    # 在所有目录扫描完毕后，统一处理并保存文件
    if all_studios_map:
        sorted_map = dict(sorted(all_studios_map.items()))
        output_path = os.path.join(current_working_dir, output_file)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_map, f, ensure_ascii=False, indent=4)
            print(f"\n✅ 制片厂信息已成功合并并保存到: {output_path}")
        except IOError as e:
            print(f"\n❌ 保存文件时出错: {e}")
    else:
        print("\n🤷‍♂️ 在所有指定目录中均未找到任何制片厂信息。")


if __name__ == "__main__":
    # 直接调用主函数即可
    summarize_all_studios()