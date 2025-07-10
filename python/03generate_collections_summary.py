# -*- coding: utf-8 -*-
import os
import json

def summarize_collections(collections_dir, output_file='collections_summary.json'):
    """
    扫描Emby的collections目录，生成合集信息的JSON。
    """
    print(f"🚀 开始扫描合集目录: {collections_dir}")
    if not os.path.isdir(collections_dir):
        print(f"❌ 目录不存在: {collections_dir}")
        return

    collections_map = {}
    current_working_dir = os.getcwd()

    for collection_name in os.listdir(collections_dir):
        collection_path = os.path.join(collections_dir, collection_name)
        if os.path.isdir(collection_path):
            collection_data = {}
            # 查找海报和背景图
            for art_type in ['poster.jpg', 'fanart.jpg']:
                art_path = os.path.join(collection_path, art_type)
                if os.path.exists(art_path):
                    # 从当前工作目录计算相对路径
                    relative_path = os.path.relpath(art_path, current_working_dir).replace(os.path.sep, '/')
                    # 使用 'poster' 和 'fanart' 作为键
                    collection_data[art_type.split('.')[0]] = relative_path

            if collection_data:
                print(f"  🖼️  找到合集: {collection_name}")
                collections_map[collection_name] = collection_data

    if collections_map:
        sorted_map = dict(sorted(collections_map.items()))
        output_path = os.path.join(current_working_dir, output_file)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_map, f, ensure_ascii=False, indent=4)
            print(f"\n✅ 合集信息已成功保存到: {output_path}")
        except IOError as e:
            print(f"\n❌ 保存文件时出错: {e}")
    else:
        print("\n🤷‍♂️ 未找到任何合集信息。")

if __name__ == "__main__":
    # 假设脚本在 videoWall 目录下运行
    # 根据图片中的目录结构，collections 文件夹位于 config/metadata/collections
    # --- 修改的就是下面这一行 ---
    collections_directory = os.path.join(os.getcwd(), 'config', 'metadata', 'collections')
    summarize_collections(collections_directory)