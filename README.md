# Firefox Portable Manager 🦊📦

A lightweight, Python-based GUI tool designed to manage multiple portable instances of Mozilla Firefox (Stable, Beta, and Nightly) on Windows.

It allows you to download, install, and update Firefox versions independently without affecting your main system installation. Each version runs with its own isolated profile.

## ✨ Features

- **Multi-Channel Support:** Manage Stable, Beta, and Nightly versions side-by-side.
- **True Portability:** Keeps the browser core and user profile strictly separated in local folders.
- **Auto-Update Check:** Checks against official Mozilla servers for new versions on startup.
- **Smart Detection (v3.4):** Uses both `win32api` and `application.ini` parsing to correctly detect installed versions (fixes "gray status" issues).
- **GUI & CLI:**
  - User-friendly Interface (Tkinter).
  - dragging files onto the generated shortcuts opens them in the specific portable version.
- **7-Zip Integration:** Uses 7-Zip for fast extraction of official installers.

## 🛠 Prerequisites

1. **Windows OS** (Tested on Windows 10/11).
2. **Python 3.x** installed.
3. **7-Zip** installed (The script needs `7z.exe` to extract the installers) or **7-Zip console executable**.


## 📦 Building a Standalone EXE

If you want to run this tool on a computer without Python installed, you can convert the script into a single executable file using **auto-py-to-exe**.

1. **Install auto-py-to-exe:**
   Open your terminal/command prompt and run:
   ```bash
   pip install auto-py-to-exe
   ```

2. **Start the GUI Builder:**
   Run the following command:
   ```bash
   auto-py-to-exe
   ```

3. **Configuration Steps:**
   A window will open. Configure it as follows:
   *   **Script Location:** Browse and select your python script (e.g., `firefox_manager.py`).
   *   **Onefile:** Select **Onefile** (this creates a single, portable `.exe`).
   *   **Console Window:** Select **Window Based (hide the console)**.
       *   *Note: If you want to see debug outputs during testing, leave this on "Console Based".*
   *   **Icon (Optional):** Under "Icon", you can browse for an `.ico` file to give your app a professional look.

4. **Build:**
   Click the big blue **Convert .py to .exe** button.

5. **Finish:**
   Once completed, click **Open Output Folder**. You will find your standalone `.exe` there. You can now move this file to any location (e.g., a USB drive) and run it.
