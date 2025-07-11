import json
import os

# --- 配置 ---
MOVIE_SUMMARY_FILE = 'movie_summary.json'
PEOPLE_SUMMARY_FILE = 'people_summary.json'
OUTPUT_FILE = 'miss.md'

def check_files_exist():
    """检查所需文件是否存在"""
    if not os.path.exists(MOVIE_SUMMARY_FILE):
        print(f"错误: 找不到文件 '{MOVIE_SUMMARY_FILE}'。请确保它在当前目录中。")
        return False
    if not os.path.exists(PEOPLE_SUMMARY_FILE):
        print(f"错误: 找不到文件 '{PEOPLE_SUMMARY_FILE}'。请确保它在当前目录中。")
        return False
    return True

def load_json_data(filepath):
    """从文件加载 JSON 数据"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: 解析 JSON 文件 '{filepath}' 失败: {e}")
        return None
    except FileNotFoundError:
        return None

def get_unique_actors(movies_data):
    """从电影数据中提取所有唯一的演员信息。注意：即使多个演员重名，只要其中一个有thumb，我们这里也只保留一个版本。
       为了确保逻辑正确，我们保留完整的演员对象。"""
    unique_actors = {}
    if not isinstance(movies_data, list):
        print("警告: movie_summary.json 的顶层不是一个列表。")
        return {}

    for movie in movies_data:
        actors_list = movie.get('metadata', {}).get('actors', [])
        if not actors_list:
            continue

        for actor in actors_list:
            if isinstance(actor, dict) and 'name' in actor:
                actor_name = actor['name']
                if actor_name and actor_name not in unique_actors:
                    unique_actors[actor_name] = actor
    return unique_actors

def find_missing_actors(unique_actors, people_data):
    """
    根据 main.js 的完整逻辑查找缺失头像的演员。
    完整逻辑: actor.thumb || getPersonImage(actor.name)
    """
    missing_actors_list = []
    all_people_keys = people_data.keys()

    for actor_name, actor_obj in unique_actors.items():
        # --- 核心修正逻辑 START ---
        # 对应 JS: `actor.thumb || ...`
        # 步骤 1: 优先检查演员对象本身是否包含 'thumb' 属性。
        # .get('thumb') 会在 'thumb' 不存在时返回 None，这是一个 "falsy" 值。
        if actor_obj.get('thumb'):
            # 如果 thumb 存在且不为空字符串，说明该演员有直接指定的头像，不属于缺失。
            # 直接跳到下一个演员。
            continue
        # --- 核心修正逻辑 END ---

        # 只有在 actor_obj 中没有 'thumb' 的情况下，才执行 getPersonImage(actor.name) 的逻辑
        if not actor_name:
            continue

        # 步骤 2: 精确匹配 (对应 JS: `allPeople[personName]`)
        is_found = actor_name in people_data

        # 步骤 3: 前缀匹配 (对应 JS: `...find(k => k.startsWith(personName + '-tmdb-'))`)
        if not is_found:
            prefix_to_check = f"{actor_name}-tmdb-"
            is_found = any(key.startswith(prefix_to_check) for key in all_people_keys)

        # 如果所有检查都失败（没有 thumb，且两种名称匹配都失败），才判定为缺失。
        if not is_found:
            missing_actors_list.append(actor_obj)

    return missing_actors_list

def generate_output_xml(actor_obj):
    """根据演员对象生成指定格式的XML字符串"""
    name = actor_obj.get('name', 'N/A')
    role = actor_obj.get('role', '')

    name = name.replace('&', '&').replace('<', '<').replace('>', '>')
    role = str(role).replace('&', '&').replace('<', '<').replace('>', '>')

    return (
        f"  <actor>\n"
        f"    <name>{name}</name>\n"
        f"    <role>{role}</role>\n"
        f"    <type>Actor</type>\n"
        f"  </actor>"
    )


def main():
    """主执行函数"""
    print("开始检查缺失的演员头像...")

    if not check_files_exist():
        return

    print("正在加载 JSON 数据...")
    movies_data = load_json_data(MOVIE_SUMMARY_FILE)
    people_data = load_json_data(PEOPLE_SUMMARY_FILE)

    if movies_data is None or people_data is None:
        print("因数据加载失败，脚本已中止。")
        return

    print("步骤 1/3: 从电影数据中提取并去重演员...")
    unique_actors = get_unique_actors(movies_data)
    print(f"完成。共找到 {len(unique_actors)} 位独立演员。")

    print("步骤 2/3: 根据 'main.js' 完整逻辑匹配演员头像 (检查 thumb -> 精确匹配 -> 前缀匹配)...")
    missing = find_missing_actors(unique_actors, people_data)
    print(f"完成。找到 {len(missing)} 位演员真正缺少头像。")

    if not missing:
        print("\n恭喜！没有发现缺少头像的演员。")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("<!-- No missing actors found. -->\n")
        return

    print(f"步骤 3/3: 生成报告文件 '{OUTPUT_FILE}'...")
    missing_sorted = sorted(missing, key=lambda x: x.get('name', ''))

    output_content_list = [generate_output_xml(actor) for actor in missing_sorted]
    final_output = "\n".join(output_content_list)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_output)

    print(f"\n处理完毕！结果已写入 '{OUTPUT_FILE}'。")


if __name__ == "__main__":
    main()