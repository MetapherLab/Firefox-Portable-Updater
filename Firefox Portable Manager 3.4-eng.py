"""
--------------------------------------------------------------------------------
SCRIPT INFO
--------------------------------------------------------------------------------
Name:           Firefox Portable Manager
Description:    Management of portable Firefox versions.
                Fixes V3.4:
                - FIX: "Gray" status issue resolved (Fallback to application.ini)
                - FIX: Enforced absolute paths for os.path.exists
                - FIX: UI turns green even if version unreadable, as long as file exists
Author:         AI Assistant
Date:           2024-12-01
Version:        3.4 (Stable UI Fix / English Release)
--------------------------------------------------------------------------------
"""

import os
import sys
import shutil
import subprocess
import threading
import configparser
import logging
import requests
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import win32com.client
import pythoncom
from win32api import GetFileVersionInfo, LOWORD, HIWORD

# ----------------- DEFAULT CONFIGURATION -----------------
# Switched lang=de to lang=en-US for international use
DEFAULT_URLS = {
    "Stable": "https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US",
    "Beta":   "https://download.mozilla.org/?product=firefox-beta-latest-ssl&os=win64&lang=en-US",
    "Nightly":"https://download.mozilla.org/?product=firefox-nightly-latest-ssl&os=win64&lang=en-US"
}

DEFAULT_HELP_TEXT = """
Firefox Portable Manager Help

1. FUNCTION
This tool manages multiple Firefox versions (Stable, Beta, Nightly) completely independently.
Each version is assigned:
- A dedicated subfolder (Core)
- A separate user profile (Profile)
- A shortcut in the base directory

2. PREREQUISITES
- An active internet connection for downloads.
- 7-Zip installed (or access to 7z.exe), as Mozilla installers need to be extracted.
  The path to 7z.exe can be configured in the Settings.

3. USAGE
- 'Status': Checks which versions are currently installed locally.
- 'Install/Update': Downloads the latest version, extracts it, and updates the core files. Your user profile remains untouched.
- 'Start': Launches Firefox with the isolated profile (-profile "..." -no-remote).

4. SETTINGS
You can adjust paths in the Settings menu.
Configuration is saved in the local .ini file.
"""

# ----------------- HELPER FUNCTIONS -----------------

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    return os.path.join(get_base_dir(), "firefox_manager_config.ini")

def get_log_path():
    return os.path.join(get_base_dir(), "FirefoxManager_Log.txt")

def parse_version_to_tuple(version_str):
    if not version_str or "Unknown" in version_str:
        return (0, 0, 0)
    
    clean_str = re.sub(r'[^0-9\.]', '', version_str)
    parts = clean_str.split('.')
    try:
        return tuple(map(int, parts))
    except ValueError:
        return (0, 0, 0)

# ----------------- LOGGING CLASS -----------------
class Logger:
    def __init__(self, log_file, ui_callback=None):
        self.log_file = log_file
        self.ui_callback = ui_callback
        self.log_buffer = []  # Buffer for early logs
        logging.basicConfig(filename=self.log_file, level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s', force=True)

    def log(self, message, level="info"):
        if level == "info": logging.info(message)
        elif level == "error": logging.error(message)
        elif level == "warning": logging.warning(message)
        
        print(f"[{level.upper()}] {message}")
        
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}\n"
        
        # Save to buffer
        self.log_buffer.append(formatted_msg)
        
        if self.ui_callback:
            self.ui_callback(formatted_msg)

# ----------------- GUI CLASS -----------------
class FirefoxManagerApp:
    def __init__(self, root):
        self.root = root
        self.base_dir = get_base_dir()
        self.config = configparser.ConfigParser()
        self.load_config()
        
        self.console_window = None
        self.console_text_widget = None

        self.logger = Logger(get_log_path(), self.log_to_console)

        self.root.title("Firefox Portable Manager 3.4")
        self.apply_window_geometry()
        
        # --- STYLES ---
        self.style = ttk.Style()
        self.style.configure("TButton", padding=5)
        self.style.configure("Header.TLabel", font=('Segoe UI', 10, 'bold'))
        
        self.style.configure("Installed.TLabel", font=('Segoe UI', 9), foreground="#008000") # Green
        self.style.configure("Update.TLabel", font=('Segoe UI', 9, 'bold'), foreground="#CC0000") # Red
        self.style.configure("Missing.TLabel", font=('Segoe UI', 9), foreground="#808080") # Gray
        self.style.configure("Checking.TLabel", font=('Segoe UI', 9), foreground="#0066CC") # Blue

        self.create_menu()

        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Info
        info_frame = ttk.LabelFrame(main_frame, text="Info & Status", padding="5")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = ttk.Label(info_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(fill=tk.X)
        self.progress = ttk.Progressbar(info_frame, mode='indeterminate')
        
        # Versions
        versions_frame = ttk.LabelFrame(main_frame, text="Firefox Versions", padding="5")
        versions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(versions_frame, text="Version", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(versions_frame, text="Status (Local)", style="Header.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(versions_frame, text="Actions", style="Header.TLabel").grid(row=0, column=2, sticky="w")

        self.version_widgets = {}
        row = 1
        for v_name, v_url in DEFAULT_URLS.items():
            self.create_version_row(versions_frame, v_name, row)
            row += 1

        # Footer
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Button(footer_frame, text="Settings", command=self.open_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer_frame, text="Help", command=self.show_help).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer_frame, text="Log / Console", command=self.show_console).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer_frame, text="Exit", command=self.on_close).pack(side=tk.RIGHT, padx=5)

        self.check_cli_args()
        
        self.logger.log(f"Base Directory: {self.config.get('GENERAL', 'BaseDir')}")
        self.refresh_versions_ui()
        self.root.after(2000, self.startup_update_check)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Settings", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Show Console", command=self.show_console)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Show Help", command=self.show_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def load_config(self):
        cfg_path = get_config_path()
        if not os.path.exists(cfg_path):
            self.config['GENERAL'] = {
                'BaseDir': self.base_dir,
                '7ZipPath': self.find_7zip(),
                'WindowGeo': '750x500'
            }
            self.config['HELP'] = {'Text': DEFAULT_HELP_TEXT}
            self.save_config()
        else:
            self.config.read(cfg_path, encoding='utf-8')

    def save_config(self):
        with open(get_config_path(), 'w', encoding='utf-8') as f:
            self.config.write(f)

    def find_7zip(self):
        candidates = [r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe", "7z.exe"]
        for c in candidates:
            if os.path.exists(c) or shutil.which("7z"): return c
        return ""

    def apply_window_geometry(self):
        geo = self.config.get('GENERAL', 'WindowGeo', fallback='750x500')
        self.root.geometry(geo)

    def create_version_row(self, parent, name, row):
        lbl_name = ttk.Label(parent, text=name, font=('Segoe UI', 10))
        lbl_name.grid(row=row, column=0, sticky="w", pady=10, padx=5)

        # Default text is Checking...
        lbl_ver = ttk.Label(parent, text="Checking...", foreground="gray")
        lbl_ver.grid(row=row, column=1, sticky="w", pady=10, padx=5)

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=2, sticky="w", pady=10, padx=5)

        btn_start = ttk.Button(btn_frame, text="Start", command=lambda n=name: self.launch_firefox(n))
        btn_update = ttk.Button(btn_frame, text="Update / Install", command=lambda n=name: self.start_check_process(n))
        btn_del = ttk.Button(btn_frame, text="Delete", command=lambda n=name: self.delete_version(n))
        
        btn_start.pack(side=tk.LEFT, padx=2)
        btn_update.pack(side=tk.LEFT, padx=2)
        btn_del.pack(side=tk.LEFT, padx=2)

        self.version_widgets[name] = {
            'lbl_ver': lbl_ver,
            'btn_start': btn_start,
            'btn_update': btn_update,
            'btn_delete': btn_del
        }

    # ----------------- CONSOLE -----------------

    def show_console(self):
        if self.console_window is None or not tk.Toplevel.winfo_exists(self.console_window):
            self.console_window = tk.Toplevel(self.root)
            self.console_window.title("Log / Console")
            self.console_window.geometry("600x400")
            
            self.console_text_widget = scrolledtext.ScrolledText(self.console_window, state='disabled', font=("Consolas", 9))
            self.console_text_widget.pack(fill=tk.BOTH, expand=True)
            
            btn_clear = ttk.Button(self.console_window, text="Clear", command=self.clear_console)
            btn_clear.pack(side=tk.BOTTOM, fill=tk.X)
            
            # Show buffered logs
            if self.logger.log_buffer:
                self.console_text_widget.config(state='normal')
                for msg in self.logger.log_buffer:
                    self.console_text_widget.insert(tk.END, msg)
                self.console_text_widget.see(tk.END)
                self.console_text_widget.config(state='disabled')
        else:
            self.console_window.lift()

    def clear_console(self):
        if self.console_text_widget:
            self.console_text_widget.config(state='normal')
            self.console_text_widget.delete(1.0, tk.END)
            self.console_text_widget.config(state='disabled')

    def log_to_console(self, msg):
        self.root.after(0, lambda: self._append_log_text(msg))

    def _append_log_text(self, msg):
        if self.console_window and tk.Toplevel.winfo_exists(self.console_window) and self.console_text_widget:
            self.console_text_widget.config(state='normal')
            self.console_text_widget.insert(tk.END, msg)
            self.console_text_widget.see(tk.END)
            self.console_text_widget.config(state='disabled')

    # ----------------- STATUS & PATHS -----------------

    def get_version_dir(self, name):
        base = self.config.get('GENERAL', 'BaseDir', fallback=self.base_dir)
        # Fix: Enforce absolute paths
        return os.path.abspath(os.path.join(base, name))

    def get_exe_path(self, name):
        return os.path.join(self.get_version_dir(name), "core", "firefox.exe")

    def get_profile_path(self, name):
        return os.path.join(self.get_version_dir(name), "profile")

    def check_cli_args(self):
        if len(sys.argv) > 1: self.cli_files = sys.argv[1:]
        else: self.cli_files = []

    def refresh_versions_ui(self):
        """ 
        Updates the UI based on local status.
        Runs immediately at startup.
        """
        for name in DEFAULT_URLS.keys():
            exe = self.get_exe_path(name)
            widgets = self.version_widgets[name]
            
            if os.path.exists(exe):
                ver = self.get_file_version(exe)
                if ver == "Unknown":
                    ver_text = "Installed (Ver.?)"
                else:
                    ver_text = f"{ver} (Checking...)"
                
                # Set to "Checking" status (blue) until Auto-Check completes
                widgets['lbl_ver'].config(text=ver_text, style="Checking.TLabel")
                widgets['btn_start'].state(['!disabled'])
                widgets['btn_delete'].state(['!disabled'])
            else:
                widgets['lbl_ver'].config(text="Not installed", style="Missing.TLabel")
                widgets['btn_start'].state(['disabled'])
                widgets['btn_delete'].state(['disabled'])

    def get_file_version(self, path):
        """ 
        Attempts to read version.
        Method 1: application.ini (reliable for Firefox)
        Method 2: Win32 API (Fallback)
        """
        # Method 1: read application.ini
        try:
            exe_dir = os.path.dirname(path)
            ini_path = os.path.join(exe_dir, "application.ini")
            if os.path.exists(ini_path):
                with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Look for [App] ... Version=X.X.X
                    match = re.search(r'Version=([0-9\.]+[a-z0-9]*)', content)
                    if match:
                        return match.group(1)
        except Exception:
            pass # Move to Method 2

        # Method 2: Win32 API
        try:
            info = GetFileVersionInfo(path, "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            return f"{HIWORD(ms)}.{LOWORD(ms)}.{HIWORD(ls)}.{LOWORD(ls)}"
        except Exception:
            pass
            
        return "Unknown"

    # ----------------- AUTO-CHECK -----------------

    def startup_update_check(self):
        t = threading.Thread(target=self.run_startup_check)
        t.daemon = True
        t.start()

    def run_startup_check(self):
        self.logger.log("Starting auto-update check...", "info")
        updates_found = 0
        
        for name, url in DEFAULT_URLS.items():
            exe_path = self.get_exe_path(name)
            
            if not os.path.exists(exe_path):
                self.logger.log(f"[CHECK] {name}: Not installed", "info")
                continue

            local_str = self.get_file_version(exe_path)
            self.logger.log(f"[CHECK] {name}: Local Version = {local_str}", "info")
            
            # FIX: If version unknown but file exists -> mark GREEN anyway
            if local_str == "Unknown":
                 self.logger.log(f"[WARN] Version of {name} unreadable, but installed.", "warning")
                 self.root.after(0, lambda n=name: self.mark_uptodate(n, "Installed (Ver.?)"))
                 continue

            remote_str = self.get_remote_version_info(url)
            self.logger.log(f"[CHECK] {name}: Remote Version = {remote_str}", "info")
            
            if not remote_str:
                self.logger.log(f"[CHECK] {name}: No internet, marking as current", "info")
                self.root.after(0, lambda n=name, l=local_str: self.mark_uptodate(n, l))
                continue

            if self.check_is_newer(local_str, remote_str):
                updates_found += 1
                self.logger.log(f"[CHECK] {name}: Update available!", "info")
                self.root.after(0, lambda n=name, l=local_str: self.mark_update_available(n, l))
            else:
                self.logger.log(f"[CHECK] {name}: Is up to date", "info")
                self.root.after(0, lambda n=name, l=local_str: self.mark_uptodate(n, l))

        if updates_found > 0:
            self.root.after(0, lambda: self.status_var.set(f"{updates_found} Update(s) found."))
        else:
            self.root.after(0, lambda: self.status_var.set("All installations up to date."))

    def mark_update_available(self, name, local_ver):
        lbl = self.version_widgets[name]['lbl_ver']
        # Remove "(Checking...)" if present
        clean_ver = local_ver.replace(" (Checking...)", "")
        
        # Enforce Red Color directly
        lbl.config(
            text=f"{clean_ver} (Update!)", 
            style="Update.TLabel",
            foreground="#CC0000"
        )
        lbl.update_idletasks()
        
        self.logger.log(f"[UI] {name} marked as update available: {clean_ver}", "info")

    def mark_uptodate(self, name, local_ver):
        lbl = self.version_widgets[name]['lbl_ver']
        # Remove "(Checking...)" if present
        clean_ver = local_ver.replace(" (Checking...)", "")
        
        # Enforce Green Color directly
        lbl.config(
            text=f"{clean_ver}", 
            style="Installed.TLabel",
            foreground="#008000"
        )
        lbl.update_idletasks()
        
        self.logger.log(f"[UI] {name} marked as up to date: {clean_ver}", "info")

    def check_is_newer(self, local_ver, remote_ver):
        if "Unknown" in local_ver or not remote_ver: return False
        
        loc_tup = parse_version_to_tuple(local_ver)
        rem_tup = parse_version_to_tuple(remote_ver)
        
        check_len = len(rem_tup)
        loc_trimmed = loc_tup[:check_len]
        
        return rem_tup > loc_trimmed

    # ----------------- UPDATE PROCESS -----------------

    def get_remote_version_info(self, url):
        try:
            r = requests.head(url, allow_redirects=True, timeout=5)
            match = re.search(r'/releases/([0-9]+\.[0-9]+([a-z0-9\.]+)?)', r.url)
            if match: return match.group(1)
            return None
        except Exception:
            return None

    def start_check_process(self, name):
        self.set_busy(True)
        t = threading.Thread(target=self.run_manual_check, args=(name,))
        t.start()

    def run_manual_check(self, name):
        url = DEFAULT_URLS[name]
        exe_path = self.get_exe_path(name)
        
        local_ver = None
        is_installed = os.path.exists(exe_path)

        if is_installed:
            local_ver = self.get_file_version(exe_path)
            
        self.update_status(f"Checking online version for {name}...")
        remote_ver = self.get_remote_version_info(url)
        self.set_busy(False)

        should_install = False
        
        if not is_installed:
            msg = f"{name} is not installed.\nPath: {exe_path}\n"
            if remote_ver: msg += f"Available: {remote_ver}\n"
            msg += "\nInstall now?"
            if messagebox.askyesno("Installation", msg):
                should_install = True
        else:
            # Update Logic
            disp_local = local_ver if local_ver else "Unknown"
            
            if remote_ver:
                if self.check_is_newer(disp_local, remote_ver):
                    msg = f"Update available!\nLocal: {disp_local}\nOnline: {remote_ver}\n\nUpdate?"
                    if messagebox.askyesno("Update", msg): should_install = True
                else:
                    msg = f"Version is up to date.\nLocal: {disp_local}\nOnline: {remote_ver}\n\nReinstall / Repair?"
                    if messagebox.askyesno("Up to date", msg): should_install = True
            else:
                if messagebox.askyesno("Connection Issue", f"No online info.\nLocal: {disp_local}\nDownload anyway?"):
                    should_install = True

        if should_install:
            self.root.after(0, self.show_console)
            self.set_busy(True)
            t = threading.Thread(target=self.run_download_install_process, args=(name, url))
            t.start()
        else:
            self.update_status("Cancelled.")

    def run_download_install_process(self, name, url):
        try:
            self.logger.log(f"--- Starting Installation: {name} ---")
            
            seven_zip = self.config.get('GENERAL', '7ZipPath')
            if not seven_zip or (not os.path.exists(seven_zip) and not shutil.which("7z")):
                raise Exception("7-Zip path invalid!")

            self.update_status(f"Downloading {name}...")
            temp_dir = os.path.join(self.base_dir, "temp_install")
            os.makedirs(temp_dir, exist_ok=True)
            installer_path = os.path.join(temp_dir, f"firefox_{name}.exe")
            
            r = requests.get(url, stream=True)
            r.raise_for_status()
            with open(installer_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            self.logger.log("Download complete.")

            self.update_status(f"Extracting {name}...")
            version_dir = self.get_version_dir(name)
            core_dir = os.path.join(version_dir, "core")
            
            if os.path.exists(core_dir):
                try:
                    shutil.move(core_dir, core_dir + "_bak")
                except Exception as e:
                    self.logger.log(f"Backup failed (Firefox open?): {e}", "error")
                    raise
            
            os.makedirs(core_dir, exist_ok=True)
            extract_temp = os.path.join(temp_dir, "extracted")
            if os.path.exists(extract_temp): shutil.rmtree(extract_temp)

            cmd = [seven_zip, "x", installer_path, f"-o{extract_temp}", "-y"]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            found_exe = False
            for root, dirs, files in os.walk(extract_temp):
                if "firefox.exe" in files:
                    source_dir = root
                    self.logger.log(f"Firefox found in: {source_dir}")
                    
                    for item in os.listdir(source_dir):
                        s = os.path.join(source_dir, item)
                        d = os.path.join(core_dir, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)
                    found_exe = True
                    break
            
            if not found_exe:
                raise Exception("firefox.exe could not be found in installer!")

            shutil.rmtree(temp_dir, ignore_errors=True)
            if os.path.exists(core_dir + "_bak"): shutil.rmtree(core_dir + "_bak", ignore_errors=True)

            profile_dir = self.get_profile_path(name)
            os.makedirs(profile_dir, exist_ok=True)
            self.create_shortcut(name)

            self.logger.log(f"--- {name} successfully installed ---")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"{name} installed."))
            
        except Exception as e:
            self.logger.log(f"ERROR: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        finally:
            self.root.after(0, self.set_busy, False)
            self.root.after(0, self.refresh_versions_ui)

    # ----------------- DELETE & START -----------------

    def delete_version(self, name):
        exe_path = self.get_exe_path(name)
        if not os.path.exists(exe_path): return

        msg = f"Really delete Firefox {name}?"
        if not messagebox.askyesno("Delete", msg, icon='warning'): return

        try:
            self.logger.log(f"Deleting {name}...")
            ver_dir = self.get_version_dir(name)
            if os.path.exists(ver_dir): shutil.rmtree(ver_dir)
            
            lnk = os.path.join(self.config.get('GENERAL', 'BaseDir'), f"Firefox Portable {name}.lnk")
            if os.path.exists(lnk): os.remove(lnk)

            self.refresh_versions_ui()
            messagebox.showinfo("Info", f"{name} deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def create_shortcut(self, name):
        try:
            pythoncom.CoInitialize() 
            base = self.config.get('GENERAL', 'BaseDir')
            lnk = os.path.join(base, f"Firefox Portable {name}.lnk")
            exe = self.get_exe_path(name)
            prof = self.get_profile_path(name)

            shell = win32com.client.Dispatch("WScript.Shell")
            s = shell.CreateShortCut(lnk)
            s.Targetpath = exe
            s.Arguments = f'-profile "{prof}" -no-remote'
            s.WorkingDirectory = os.path.dirname(exe)
            s.IconLocation = exe
            s.Description = f"Firefox {name} Portable"
            s.save()
        except Exception as e:
            self.logger.log(f"Shortcut Error: {e}", "warning")

    def launch_firefox(self, name):
        exe = self.get_exe_path(name)
        prof = self.get_profile_path(name)
        cmd = [exe, '-profile', prof, '-no-remote']
        if self.cli_files:
            cmd.extend(self.cli_files)
            self.cli_files = []
        
        try:
            subprocess.Popen(cmd)
            self.status_var.set(f"{name} started.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ----------------- UI HELPER -----------------

    def set_busy(self, busy=True):
        if busy:
            self.progress.pack(fill=tk.X, padx=5, pady=2)
            self.progress.start(10)
            self.status_var.set("Working...")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.status_var.set("Ready.")

    def update_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def open_settings(self):
        SettingsDialog(self.root, self.config, self.save_config)

    def show_help(self):
        HelpDialog(self.root, self.config.get('HELP', 'Text'))

    def on_close(self):
        self.config['GENERAL']['WindowGeo'] = self.root.geometry()
        self.save_config()
        self.root.destroy()
        sys.exit(0)

# ----------------- DIALOGS -----------------

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config, save_cb):
        super().__init__(parent)
        self.title("Settings")
        self.config = config
        self.save_cb = save_cb
        self.geometry("500x250")
        self.transient(parent)
        self.grab_set()
        
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50
        self.geometry(f"+{x}+{y}")

        ttk.Label(self, text="Base Directory:").pack(anchor="w", padx=10, pady=(10,0))
        self.entry_base = ttk.Entry(self)
        self.entry_base.pack(fill=tk.X, padx=10, pady=2)
        self.entry_base.insert(0, config.get('GENERAL', 'BaseDir'))
        ttk.Button(self, text="Browse", command=self.browse_base).pack(anchor="e", padx=10)

        ttk.Label(self, text="7-Zip Path (7z.exe):").pack(anchor="w", padx=10, pady=(10,0))
        self.entry_7z = ttk.Entry(self)
        self.entry_7z.pack(fill=tk.X, padx=10, pady=2)
        self.entry_7z.insert(0, config.get('GENERAL', '7ZipPath'))
        ttk.Button(self, text="Browse", command=self.browse_7z).pack(anchor="e", padx=10)

        f = ttk.Frame(self)
        f.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        ttk.Button(f, text="Save", command=self.save).pack(side=tk.RIGHT, padx=10)
        ttk.Button(f, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

    def browse_base(self):
        d = filedialog.askdirectory(initialdir=self.entry_base.get())
        if d: self.entry_base.delete(0, tk.END); self.entry_base.insert(0, d)

    def browse_7z(self):
        f = filedialog.askopenfilename(filetypes=[("EXE", "*.exe")])
        if f: self.entry_7z.delete(0, tk.END); self.entry_7z.insert(0, f)

    def save(self):
        self.config['GENERAL']['BaseDir'] = self.entry_base.get()
        self.config['GENERAL']['7ZipPath'] = self.entry_7z.get()
        self.save_cb()
        self.destroy()

class HelpDialog(tk.Toplevel):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.title("Help")
        self.geometry("600x400")
        t = tk.Text(self, wrap=tk.WORD, padx=10, pady=10, font=("Consolas", 10))
        t.pack(fill=tk.BOTH, expand=True)
        t.insert(tk.END, text)
        t.config(state=tk.DISABLED) 

if __name__ == "__main__":
    root = tk.Tk()
    app = FirefoxManagerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()