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
3. **7-Zip** installed (The script needs `7z.exe` to extract the installers).

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/firefox-portable-manager.git
   cd firefox-portable-manager
