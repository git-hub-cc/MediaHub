import json
import os
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# --- Configuration ---
# IMPORTANT: Replace "YOUR_TMDB_API_KEY" with your actual TMDb API key
TMDB_API_KEY = "在此处粘贴你的API密钥"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original" # Use 'original' for highest quality
DOWNLOAD_BASE_DIR = "download" # Base directory where downloaded posters will be saved

# Number of concurrent threads for downloading/API calls
MAX_WORKERS = 8

# Use a lock for printing to prevent interleaved output from multiple threads
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    """Prints messages in a thread-safe manner."""
    with print_lock:
        print(*args, **kwargs)

# --- Helper Functions ---

def get_tmdb_info(query, media_type):
    """
    Searches TMDb for a movie or TV show.
    media_type can be 'movie', 'tv', or 'multi'.
    """
    url = f"https://api.themoviedb.org/3/search/{media_type}"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "zh-CN" # Prioritize Chinese results
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results")
        if results:
            # Prioritize exact title match, then the first result
            for result in results:
                if result.get('title') == query or result.get('name') == query:
                    return result
            return results[0]
        return None
    except requests.exceptions.RequestException as e:
        safe_print(f"Error querying TMDb for '{query}' ({media_type}): {e}")
        return None

def download_image(image_url, save_path):
    """Downloads an image from a URL and saves it to a specified path."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    try:
        response = requests.get(image_url, stream=True, timeout=30)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        safe_print(f"Downloaded: {os.path.relpath(save_path)}")
        return True
    except requests.exceptions.RequestException as e:
        safe_print(f"Error downloading image from {image_url} to {save_path}: {e}")
        return False

def get_search_title(original_path, is_tv_show_entry):
    """
    Derives the search query title for TMDb based on the path.
    This function NO LONGER determines the display folder name.
    """
    path_parts = original_path.split('\\')
    search_title = path_parts[-1] # Default search title is the last part of the path

    # Special handling for well-known series where the search should be on the series name,
    # not the season name.
    if "孤独的美食家" in original_path:
        search_title = "孤独的美食家"
    elif "帝国的崛起：奥斯曼" in original_path and is_tv_show_entry:
        search_title = "帝国的崛起：奥斯曼"
    elif "古罗马_一个帝国的兴起和衰亡" in original_path:
        search_title = "古罗马 一个帝国的兴起和衰亡" # Add space for better TMDb search
    # Add other special search cases here if needed

    return search_title

def process_single_media_item(item, media_type_str):
    """Processes a single media item to find and download its poster, using strict pathing."""
    original_path = item['path']
    files_info = item['files'][0]

    if 'poster_image' in files_info:
        # Poster already exists in the index, skip this item entirely.
        return

    safe_print(f"\n--- Processing missing poster for: {original_path} (Type: {media_type_str}) ---")

    # --- NEW PATH LOGIC ---
    # Normalize the path from the JSON (which uses '\') to the OS's native separator.
    normalized_path = original_path.replace('\\', os.sep)
    # The target directory is now the base download dir + the full normalized original path.
    target_dir = os.path.join(DOWNLOAD_BASE_DIR, normalized_path)
    poster_save_path = os.path.join(target_dir, "poster.jpg")

    if os.path.exists(poster_save_path):
        safe_print(f"Poster already exists at {os.path.relpath(poster_save_path)}. Skipping download.")
        return

    # Get the best title to search for on TMDb.
    search_title = get_search_title(original_path, media_type_str == 'tv')

    safe_print(f"Searching TMDb for '{search_title}' as a {media_type_str}...")
    tmdb_result = get_tmdb_info(search_title, media_type_str)

    if tmdb_result and tmdb_result.get('poster_path'):
        poster_url = TMDB_IMAGE_BASE_URL + tmdb_result['poster_path']
        safe_print(f"Found poster URL: {poster_url}")
        download_image(poster_url, poster_save_path)
    else:
        safe_print(f"No poster found on TMDb for '{search_title}' as a {media_type_str}. Trying other media type...")
        alt_media_type = 'movie' if media_type_str == 'tv' else 'tv'

        tmdb_result_alt = get_tmdb_info(search_title, alt_media_type)
        if tmdb_result_alt and tmdb_result_alt.get('poster_path'):
            poster_url = TMDB_IMAGE_BASE_URL + tmdb_result_alt['poster_path']
            safe_print(f"Found poster URL as {alt_media_type}: {poster_url}")
            download_image(poster_url, poster_save_path)
        else:
            safe_print(f"No poster found on TMDb for '{search_title}' even as a {alt_media_type}.")

# --- Main Execution ---
if __name__ == "__main__":
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        safe_print("ERROR: Please replace 'YOUR_TMDB_API_KEY' in the script with your actual TMDb API key.")
        safe_print("You can get one from https://www.themoviedb.org/documentation/api")
        exit()

    try:
        with open('media_index.json', 'r', encoding='utf-8') as f:
            media_data = json.load(f)
    except FileNotFoundError:
        safe_print("Error: media_index.json not found in the current directory.")
        exit()
    except json.JSONDecodeError:
        safe_print("Error: Could not decode media_index.json. Check JSON format for errors.")
        exit()

    futures = []
    items_to_process = []

    # Collect all items that need processing
    for item in media_data.get('movies', []):
        if 'poster_image' not in item['files'][0]:
            items_to_process.append((item, 'movie'))

    for item in media_data.get('tv_shows', []):
        if 'poster_image' not in item['files'][0]:
            items_to_process.append((item, 'tv'))

    total_tasks = len(items_to_process)
    if total_tasks == 0:
        safe_print("No missing posters to process. All entries seem to have a 'poster_image' key.")
        exit()

    safe_print(f"Found {total_tasks} items with missing posters. Submitting to thread pool...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks to the executor
        for item, media_type in items_to_process:
            futures.append(executor.submit(process_single_media_item, item, media_type))

        # Wait for all submitted tasks to complete and show progress
        completed_tasks = 0
        safe_print(f"\n--- Waiting for {total_tasks} tasks to complete ---")
        for future in as_completed(futures):
            completed_tasks += 1
            try:
                future.result()
            except Exception as exc:
                safe_print(f'A task generated an exception: {exc}')
            # No need to print progress for every single completion, can be too noisy.
            # You can uncomment the line below if you want detailed progress.
            # safe_print(f"Progress: {completed_tasks}/{total_tasks} tasks completed.")

    safe_print("\n--- Processing complete ---")
    safe_print(f"All tasks finished. Check the '{DOWNLOAD_BASE_DIR}' directory for downloaded posters.")