import json
import xml.etree.ElementTree as ET
import os
from collections import deque

# --- Configuration ---
MEDIA_INDEX_FILE = 'media_index.json'
STUDIOS_SUMMARY_FILE = 'studios_summary.json'
REPORT_FILE_NAME = 'report_studios.txt'
# Set to True to include warnings about missing/malformed NFOs in the report file
# Set to False to only report missing studios and high-level errors
VERBOSE_WARNINGS = False
# Assuming the script is run from the root directory where "动漫", "People", etc. reside
# Adjust this base_path if your script is in a different location relative to your media files
BASE_MEDIA_PATH = '.'
# --- End Configuration ---

def get_all_nfo_paths(media_data_entry, current_base_path, f_report=None):
    """
    Recursively collects all NFO file paths for a given media entry.
    Handles nested structures found in tv_shows.
    """
    nfo_paths = []

    # Construct the full base path for the current media item
    full_item_path = os.path.join(current_base_path, media_data_entry['path'])

    files_info = media_data_entry.get('files', [])
    if not files_info:
        return nfo_paths

    for file_entry in files_info:
        potential_nfo_keys = ['tvshow_nfo', 'season_nfo', 'nfo']

        for key in potential_nfo_keys:
            if key in file_entry:
                nfo_data = file_entry[key]
                if isinstance(nfo_data, str):
                    full_nfo_path = os.path.join(full_item_path, nfo_data)
                    # Only add if the file exists, and log warning if not, based on VERBOSE_WARNINGS
                    if os.path.exists(full_nfo_path):
                        nfo_paths.append(full_nfo_path)
                    elif VERBOSE_WARNINGS and f_report:
                        print(f"Warning: NFO file not found: {full_nfo_path}", file=f_report)
                elif isinstance(nfo_data, list):
                    for item_or_dict in nfo_data:
                        if isinstance(item_or_dict, dict):
                            for season_folder_name, episode_nfo_list in item_or_dict.items():
                                for episode_nfo_rel_path in episode_nfo_list:
                                    full_nfo_path = os.path.join(full_item_path, episode_nfo_rel_path)
                                    if os.path.exists(full_nfo_path):
                                        nfo_paths.append(full_nfo_path)
                                    elif VERBOSE_WARNINGS and f_report:
                                        print(f"Warning: NFO file not found: {full_nfo_path}", file=f_report)
                        elif isinstance(item_or_dict, str):
                            full_nfo_path = os.path.join(full_item_path, item_or_dict)
                            if os.path.exists(full_nfo_path):
                                nfo_paths.append(full_nfo_path)
                            elif VERBOSE_WARNINGS and f_report:
                                print(f"Warning: NFO file not found: {full_nfo_path}", file=f_report)

    return nfo_paths

def parse_nfo_for_studios(nfo_file_path, f_report=None):
    """
    Parses an NFO XML file and extracts all studio names.
    Logs errors to f_report if VERBOSE_WARNINGS is True.
    """
    studios = set()

    try:
        with open(nfo_file_path, 'rb') as f:
            raw_xml = f.read()
            try:
                tree = ET.fromstring(raw_xml.decode('utf-8'))
            except UnicodeDecodeError:
                tree = ET.fromstring(raw_xml.decode('latin-1')) # Try common fallback
            except ET.ParseError as e:
                if VERBOSE_WARNINGS and f_report:
                    print(f"Warning: XML parsing failed for {nfo_file_path}. Trying with 'ignore'. Error: {e}", file=f_report)
                tree = ET.fromstring(raw_xml.decode('utf-8', errors='ignore')) # Ignore problematic chars

        for studio_elem in tree.findall('studio'):
            if studio_elem is not None and studio_elem.text:
                studio_name = studio_elem.text.strip()
                if studio_name: # Ensure the name isn't just whitespace
                    studios.add(studio_name)
    except ET.ParseError as e:
        if VERBOSE_WARNINGS and f_report:
            print(f"Error parsing XML for {nfo_file_path}: {e}", file=f_report)
    except Exception as e:
        if VERBOSE_WARNINGS and f_report:
            print(f"An unexpected error occurred reading/parsing {nfo_file_path}: {e}", file=f_report)
    return studios

def main():
    # Open the report file at the beginning
    with open(REPORT_FILE_NAME, 'w', encoding='utf-8') as f_report:
        # 1. Load data - Errors here are critical, print to console
        try:
            with open(MEDIA_INDEX_FILE, 'r', encoding='utf-8') as f:
                media_index_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {MEDIA_INDEX_FILE} not found. Please ensure it's in the correct directory.")
            print(f"Error: {MEDIA_INDEX_FILE} not found.", file=f_report)
            return
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {MEDIA_INDEX_FILE}: {e}")
            print(f"Error decoding JSON from {MEDIA_INDEX_FILE}: {e}", file=f_report)
            return

        try:
            with open(STUDIOS_SUMMARY_FILE, 'r', encoding='utf-8') as f:
                studios_summary_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {STUDIOS_SUMMARY_FILE} not found. Please ensure it's in the correct directory.")
            print(f"Error: {STUDIOS_SUMMARY_FILE} not found.", file=f_report)
            return
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {STUDIOS_SUMMARY_FILE}: {e}")
            print(f"Error decoding JSON from {STUDIOS_SUMMARY_FILE}: {e}", file=f_report)
            return

        # 2. Get existing studios from studios_summary
        existing_studios_in_summary = set(studios_summary_data.keys())

        # 3. Collect all NFO paths from media_index
        all_nfo_paths_to_process = set() # Use a set to avoid processing the same NFO multiple times

        for media_type in ['movies', 'tv_shows']:
            for entry in media_index_data.get(media_type, []):
                # Pass f_report to the helper function for logging inside it
                paths = get_all_nfo_paths(entry, BASE_MEDIA_PATH, f_report)
                all_nfo_paths_to_process.update(paths)

        # 4. Parse all collected NFOs and extract studio names
        all_studios_from_nfo = set()

        # Print progress to console and initial message to report file
        print(f"Scanning {len(all_nfo_paths_to_process)} NFO files for studios...")
        print(f"Scanning {len(all_nfo_paths_to_process)} NFO files for studios...", file=f_report)

        for i, nfo_path in enumerate(all_nfo_paths_to_process):
            # Print progress to console (using \r for in-place update)
            if (i + 1) % 50 == 0 or (i + 1) == len(all_nfo_paths_to_process): # Update progress less frequently
                 print(f"Processed {i+1}/{len(all_nfo_paths_to_process)} NFOs.", end='\r')

            # Pass f_report to the helper function for logging inside it
            studios_in_nfo = parse_nfo_for_studios(nfo_path, f_report)
            all_studios_from_nfo.update(studios_in_nfo)

        # Clear the progress line on console
        print("\nNFO scanning complete.")
        print("NFO scanning complete.", file=f_report) # Also log to file

        # 5. Find missing studios
        missing_studios = sorted(list(all_studios_from_nfo - existing_studios_in_summary))

        # 6. Report results to the file and console
        if missing_studios:
            print("\n--- Missing Studios Report ---", file=f_report)
            print("The following studios were found in NFO files but are NOT in studios_summary.json:", file=f_report)
            for studio in missing_studios:
                print(f"- {studio}", file=f_report)
            print(f"\nTotal missing studios: {len(missing_studios)}", file=f_report)

            # Also print a summary to the console
            print(f"\nFound {len(missing_studios)} missing studios. See '{REPORT_FILE_NAME}' for details.")
        else:
            print("\nGood news! All studios mentioned in NFO files are present in studios_summary.json.", file=f_report)
            print("\nGood news! All studios mentioned in NFO files are present in studios_summary.json.")


if __name__ == "__main__":
    main()