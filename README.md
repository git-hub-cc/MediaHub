# Static Media Library Browser

This is a purely front-end, serverless media library browser designed to provide a beautiful, efficient, Netflix/Jellyfin-like interface for your local media resources, especially those organized by tools like "XiaoYa AList".

It operates by using pre-generated static JSON data files to display your movie and TV show library. It can be easily deployed on any static web hosting service (like GitHub Pages, Vercel) or run from a simple local server.

## ✨ Features

*   **100% Static**: No complex backend services required. Simple to deploy and blazingly fast.
*   **High-Performance Browsing**: Utilizes infinite scrolling to smoothly handle tens of thousands of media items.
*   **In-Browser Caching**: Leverages IndexedDB to cache metadata after the first load, making subsequent visits and searches instantaneous.
*   **Rich Metadata Display**: Supports posters, fanart, plot summaries, cast and crew, collections, studios, and detailed audio/video stream information.
*   **Powerful Search & Filtering**: Full-text search across titles, plots, directors, and actors. Filter your library by collection or person.
*   **Flexible Playback Options**:
    *   One-click invocation of local media players (e.g., PotPlayer, VLC, IINA, MPV).
    *   Supports configuring multiple **round-robin playback URLs**, allowing you to easily switch between local network, external network, or backup addresses.
*   **Responsive Design**: Looks great on both desktop and mobile devices.
*   **Data Generation Scripts**: Comes with a complete set of Python scripts to scan your media library and automatically generate the necessary data files.

## 🚀 How It Works

The core idea of this project is a "front-end/back-end separation," but with the "backend" work pre-processed into static assets.

1.  **Data Generation (One-time process)**: Use the provided Python scripts to scan your media library directories (e.g., the `all` and `config` directories from "XiaoYa"). The scripts parse `.nfo` files, locate images, and generate four core `.json` data files.
2.  **Front-end Loading**: When a user visits the webpage, the browser downloads these static `.json` files, which serve as its data source.
3.  **Indexing & Interaction**:
    *   The front-end application renders the data into a beautiful media wall.
    *   The user can choose to **Build Index** in the settings panel. This action further parses all NFO data and stores it in the browser's IndexedDB, powering advanced search and filtering.
    *   All interactions—searching, filtering, viewing details—are handled client-side for a swift and responsive experience.

## ⚙️ Installation and Setup Guide

Follow these steps to deploy and use your own media library browser.

### 1. Prerequisites

*   **Python 3** installed.
*   A structured media library (like **XiaoYa AList resources**), which contains `all` and `config` directories. These directories should include files like `.nfo`, `.strm`, `poster.jpg`, `fanart.jpg`, etc.

### 2. Prepare Project Files

First, download or clone all project files (HTML, CSS, JS) to your computer. Then, place or link your media library directories into the project root, creating the following structure:

```
/your-project-folder/
├── all/              <-- Your main media library directory (e.g., 'all' from XiaoYa)
├── config/           <-- Your media metadata directory (e.g., 'config' from XiaoYa)
├── data/             <-- Create this empty directory for the generated JSON files
├── js/
│   ├── main.js
│   ├── virtual-scroll.js
│   └── ...
├── style.css
├── index.html
├── generate_movies.py      <-- Script to be created in the next step
├── generate_people.py      <-- Script to be created in the next step
├── generate_collections.py <-- Script to be created in the next step
├── generate_studios.py     <-- Script to be created in the next step
└── README.md
```

**Tip**: If your media library is large, consider using symbolic links to point `all` and `config` to your project folder to avoid duplicating large amounts of data.
*   **Windows (as Administrator)**: `mklink /D "all" "D:\path\to\your\all"`
*   **Linux / macOS**: `ln -s /path/to/your/all all`

### 3. Run the Scripts to Generate Data

Now, open your terminal (or command prompt), `cd` into your project's root directory, and run the four scripts in sequence. This process might take a few minutes, depending on the size of your media library.

```bash
python generate_movies.py
python generate_people.py
python generate_collections.py
python generate_studios.py
```

Once completed, check the `data/` directory. You should see four new files: `movie_summary.json`, `people_summary.json`, `collections_summary.json`, and `studios_summary.json`.

### 4. Launch and Access

Due to browser security policies, you cannot open `index.html` directly via the `file://` protocol. You need a local web server to run it.

1.  In your terminal, while in the project's root directory, run the following command:
    ```bash
    # If you have Python 3
    python -m http.server
    
    # You can also specify a port, e.g., 8000
    python -m http.server 8000
    ```
2.  Open your web browser and navigate to `http://localhost:8000`.
3.  You should now see your media library!

## 🧑‍💻 Usage Instructions

### Building the Metadata Index

For the best search and filtering experience, it is highly recommended that you build the metadata index on your first visit.

1.  Click the **Settings button (⚙️)** in the bottom-right corner of the page.
2.  In the side panel that appears, find the "Metadata Index" section.
3.  Click the **Build/Rebuild Index** button.
4.  Wait for the process to complete. This will cache the detailed information from all NFO files in your browser, so you won't need to do it again (unless your media library is significantly updated).

### Configuring Playback Paths

The playback URL in `.strm` files defaults to `http://xiaoya.host:5678`. If your access URL is different (e.g., a local IP like `http://192.168.1.10:5678` or a public domain like `http://my-nas.com`), you can add your own addresses in the settings.

1.  Click the **Settings button (⚙️)**.
2.  In the "Resource Playback Paths" section, you will see a list.
3.  Click **+ Add New Path** to add one or more of your access URLs.
4.  The settings are saved automatically.

**How it works**: When you click to play a video, the application selects one of the URLs from your configured list in a **round-robin fashion** to replace the default prefix in the `.strm` file, enabling easy switching between different networks or backup lines.