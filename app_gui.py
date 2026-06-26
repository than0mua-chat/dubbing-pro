import os
import sys
import time
import queue
import asyncio
import threading
import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import edge_tts

def load_dotenv(dotenv_path=".env"):
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        v_val = v.strip()
                        if len(v_val) >= 2 and ((v_val[0] == '"' and v_val[-1] == '"') or (v_val[0] == "'" and v_val[-1] == "'")):
                            v_val = v_val[1:-1]
                        os.environ[k.strip()] = v_val
        except Exception as e:
            print(f"Error loading .env file: {e}")

# Load environment variables
load_dotenv()

from text_processor import parse_srt, parse_txt, parse_dgt, format_srt_time, write_srt_file
from audio_processor import get_audio_duration, join_mp3_files

# Ensure app directory is in sys.path for imports
_app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)


class TTSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity Auto TTS & Subtitles v1.0")
        self.root.geometry("1100x700")
        self.root.minsize(950, 600)
        
        # Variables
        self.import_items = []  # List of dicts
        self.is_processing = False
        self.cancel_requested = False
        self.processing_thread = None
        self.executor = None
        self.elapsed_start_time = 0
        self.elapsed_time = 0
        self.done_count = 0
        self.err_count = 0
        self.active_async_tasks = []
        # Initialize Smart Proxy Manager
        from proxy_manager import ProxyManager
        self.proxy_manager = ProxyManager(change_callback=lambda: self.update_queue.put(("proxy_list_updated", None)))
        self.proxy_dashboard_open = False
        
        # ElevenLabs Key Pool variables
        self.elevenlabs_keys = []
        self.current_key_idx = 0
        self.key_lock = threading.Lock()
        
        # Load ElevenLabs keys
        self.load_elevenlabs_keys()
        
        # Target Output directory
        self.output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # UI Queue for thread-safe updates
        self.update_queue = queue.Queue()
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Colors & Fonts
        BG_DARK = "#1e1e24"
        BG_PANEL = "#282830"
        BG_INPUT = "#18181b"
        FG_LIGHT = "#f4f4f5"
        FG_MUTED = "#a1a1aa"
        ACCENT_INDIGO = "#6366f1"
        ACCENT_INDIGO_HOVER = "#4f46e5"
        ACCENT_EMERALD = "#10b981"
        ACCENT_EMERALD_HOVER = "#059669"
        ACCENT_CRIMSON = "#ef4444"
        ACCENT_CRIMSON_HOVER = "#dc2626"
        BORDER_COLOR = "#3f3f46"
        
        # Global Style
        self.style.configure(".",
            background=BG_DARK,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            darkcolor=BG_DARK,
            lightcolor=BG_DARK,
            troughcolor=BG_INPUT,
            font=("Segoe UI", 9)
        )
        
        # Frame
        self.style.configure("TFrame", background=BG_DARK)
        self.style.configure("Header.TFrame", background=BG_PANEL)
        
        # Label
        self.style.configure("TLabel", background=BG_DARK, foreground=FG_LIGHT)
        
        # Badges
        self.style.configure("Badge.TLabel",
            background=BG_INPUT,
            foreground=ACCENT_EMERALD,
            font=("Segoe UI", 8, "bold"),
            padding=(8, 3),
            bordercolor=BORDER_COLOR,
            relief=tk.SOLID
        )
        self.style.configure("BadgeBlue.TLabel",
            background=BG_INPUT,
            foreground="#60a5fa",
            font=("Segoe UI", 8, "bold"),
            padding=(8, 3),
            bordercolor=BORDER_COLOR,
            relief=tk.SOLID
        )
        
        # LabelFrame
        self.style.configure("TLabelframe", background=BG_DARK, bordercolor=BORDER_COLOR)
        self.style.configure("TLabelframe.Label", background=BG_DARK, foreground=FG_LIGHT, font=("Segoe UI", 9, "bold"))
        
        # Buttons
        self.style.configure("TButton",
            background=BG_PANEL,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            lightcolor=BG_PANEL,
            darkcolor=BG_PANEL,
            font=("Segoe UI", 9),
            anchor="center",
            padding=(10, 4)
        )
        self.style.map("TButton",
            background=[("active", ACCENT_INDIGO), ("pressed", ACCENT_INDIGO_HOVER), ("disabled", BG_DARK)],
            foreground=[("active", "#ffffff"), ("disabled", FG_MUTED)],
            bordercolor=[("active", ACCENT_INDIGO)]
        )
        
        # Start & Stop Button styles
        self.style.configure("Start.TButton",
            background=ACCENT_EMERALD,
            foreground="#ffffff",
            bordercolor=ACCENT_EMERALD,
            lightcolor=ACCENT_EMERALD,
            darkcolor=ACCENT_EMERALD,
            font=("Segoe UI", 9, "bold"),
            padding=(12, 6)
        )
        self.style.map("Start.TButton",
            background=[("active", ACCENT_EMERALD_HOVER), ("pressed", ACCENT_EMERALD_HOVER), ("disabled", BG_DARK)],
            foreground=[("active", "#ffffff"), ("disabled", FG_MUTED)],
            bordercolor=[("active", ACCENT_EMERALD_HOVER)]
        )
        
        self.style.configure("Stop.TButton",
            background=ACCENT_CRIMSON,
            foreground="#ffffff",
            bordercolor=ACCENT_CRIMSON,
            lightcolor=ACCENT_CRIMSON,
            darkcolor=ACCENT_CRIMSON,
            font=("Segoe UI", 9, "bold"),
            padding=(12, 6)
        )
        self.style.map("Stop.TButton",
            background=[("active", ACCENT_CRIMSON_HOVER), ("pressed", ACCENT_CRIMSON_HOVER), ("disabled", BG_DARK)],
            foreground=[("active", "#ffffff"), ("disabled", FG_MUTED)],
            bordercolor=[("active", ACCENT_CRIMSON_HOVER)]
        )
        
        # Entry
        self.style.configure("TEntry",
            fieldbackground=BG_INPUT,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            lightcolor=BG_INPUT,
            darkcolor=BG_INPUT,
            insertcolor=FG_LIGHT,
            padding=4
        )
        self.style.map("TEntry",
            bordercolor=[("focus", ACCENT_INDIGO)],
            lightcolor=[("focus", ACCENT_INDIGO)],
            darkcolor=[("focus", ACCENT_INDIGO)]
        )
        
        # Combobox
        self.style.configure("TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_PANEL,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            lightcolor=BG_INPUT,
            darkcolor=BG_INPUT,
            arrowcolor=FG_LIGHT,
            padding=4
        )
        self.style.map("TCombobox",
            bordercolor=[("focus", ACCENT_INDIGO)],
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG_LIGHT)]
        )
        
        # Spinbox
        self.style.configure("TSpinbox",
            fieldbackground=BG_INPUT,
            background=BG_PANEL,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            lightcolor=BG_INPUT,
            darkcolor=BG_INPUT,
            arrowcolor=FG_LIGHT,
            padding=4
        )
        self.style.map("TSpinbox",
            bordercolor=[("focus", ACCENT_INDIGO)]
        )
        
        # Checkbutton
        self.style.configure("TCheckbutton",
            background=BG_DARK,
            foreground=FG_LIGHT,
            indicatorbackground=BG_INPUT,
            indicatorforeground=ACCENT_INDIGO,
            font=("Segoe UI", 9)
        )
        self.style.map("TCheckbutton",
            background=[("active", BG_DARK)],
            indicatorbackground=[("active", BG_PANEL), ("selected", ACCENT_INDIGO)],
            foreground=[("active", FG_LIGHT)]
        )
        
        # Radiobutton
        self.style.configure("TRadiobutton",
            background=BG_DARK,
            foreground=FG_LIGHT,
            indicatorbackground=BG_INPUT,
            indicatorforeground=ACCENT_INDIGO,
            font=("Segoe UI", 9)
        )
        self.style.map("TRadiobutton",
            background=[("active", BG_DARK)],
            indicatorbackground=[("active", BG_PANEL), ("selected", ACCENT_INDIGO)],
            foreground=[("active", FG_LIGHT)]
        )
        
        # Treeview
        self.style.configure("Treeview",
            background=BG_INPUT,
            fieldbackground=BG_INPUT,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            rowheight=26,
            font=("Segoe UI", 9)
        )
        self.style.map("Treeview",
            background=[("selected", ACCENT_INDIGO)],
            foreground=[("selected", "#ffffff")]
        )
        self.style.configure("Treeview.Heading",
            background=BG_PANEL,
            foreground=FG_LIGHT,
            bordercolor=BORDER_COLOR,
            font=("Segoe UI", 9, "bold"),
            padding=6
        )
        self.style.map("Treeview.Heading",
            background=[("active", ACCENT_INDIGO)],
            foreground=[("active", "#ffffff")]
        )
        
        # Progressbar
        self.style.configure("Horizontal.TProgressbar",
            troughcolor=BG_PANEL,
            background=ACCENT_INDIGO,
            bordercolor=BORDER_COLOR,
            lightcolor=ACCENT_INDIGO,
            darkcolor=ACCENT_INDIGO
        )
        
        # Scrollbars
        self.style.configure("Vertical.TScrollbar",
            troughcolor=BG_INPUT,
            background=BG_PANEL,
            bordercolor=BORDER_COLOR,
            arrowcolor=FG_MUTED
        )
        self.style.map("Vertical.TScrollbar",
            background=[("active", BG_PANEL), ("pressed", ACCENT_INDIGO)]
        )
        self.style.configure("Horizontal.TScrollbar",
            troughcolor=BG_INPUT,
            background=BG_PANEL,
            bordercolor=BORDER_COLOR,
            arrowcolor=FG_MUTED
        )
        self.style.map("Horizontal.TScrollbar",
            background=[("active", BG_PANEL), ("pressed", ACCENT_INDIGO)]
        )
        
        # Option Database for Combobox Dropdown Listboxes
        self.root.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.root.option_add("*TCombobox*Listbox.foreground", FG_LIGHT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_INDIGO)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))
        self.root.option_add("*TCombobox*Listbox.relief", "flat")
        
        self.root.configure(bg=BG_DARK)
        
        # Build UI layout
        self.build_ui()
        
        # Load voices and models from local server after 500ms
        self.root.after(500, self.load_server_data)
        
        # Periodically check queue for UI updates
        self.root.after(100, self.process_queue)
        self.root.after(1000, self.update_timer)

    def apply_dark_theme(self, window):
        """Applies dark theme configurations to a Toplevel window and its children."""
        window.configure(bg="#1e1e24")
        
        def style_children(parent):
            for child in parent.winfo_children():
                win_class = child.winfo_class()
                if win_class == "Text":
                    child.configure(
                        bg="#18181b",
                        fg="#f4f4f5",
                        insertbackground="#6366f1",
                        selectbackground="#3f3f46",
                        selectforeground="#ffffff",
                        relief=tk.FLAT,
                        highlightthickness=1,
                        highlightbackground="#3f3f46",
                        highlightcolor="#6366f1"
                    )
                elif win_class == "Listbox":
                    child.configure(
                        bg="#18181b",
                        fg="#f4f4f5",
                        selectbackground="#6366f1",
                        selectforeground="#ffffff",
                        relief=tk.FLAT,
                        highlightthickness=1,
                        highlightbackground="#3f3f46",
                        highlightcolor="#6366f1"
                    )
                elif win_class == "Entry" and not isinstance(child, ttk.Entry):
                    child.configure(
                        bg="#18181b",
                        fg="#f4f4f5",
                        insertbackground="#6366f1",
                        selectbackground="#3f3f46",
                        selectforeground="#ffffff",
                        relief=tk.FLAT,
                        highlightthickness=1,
                        highlightbackground="#3f3f46",
                        highlightcolor="#6366f1"
                    )
                if child.winfo_children():
                    style_children(child)
                    
        style_children(window)

    def build_ui(self):
        # 0. Premium Header Banner
        header_frame = ttk.Frame(self.root, padding=(15, 10, 15, 10), style="Header.TFrame")
        header_frame.pack(fill=tk.X, side=tk.TOP)
        
        title_label = ttk.Label(header_frame, text="🎙️ DUBBING PRO", font=("Segoe UI", 16, "bold"), foreground="#6366f1", background="#282830")
        title_label.pack(side=tk.LEFT)
        
        subtitle_label = ttk.Label(header_frame, text=" •   AI Subtitles & Voice Synthesis Studio", font=("Segoe UI", 10), foreground="#a1a1aa", background="#282830")
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0), pady=(5, 0))
        
        license_badge = ttk.Label(header_frame, text="✓ ACTIVE LICENSE", style="Badge.TLabel")
        license_badge.pack(side=tk.RIGHT, padx=5)
        
        engine_badge = ttk.Label(header_frame, text="⚡ CORE V1.0", style="BadgeBlue.TLabel")
        engine_badge.pack(side=tk.RIGHT, padx=5)

        # 1. Main Top Frame (Control, Voice, Options)
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X, side=tk.TOP)
        
        # 1.1 Control Panel
        ctrl_lf = ttk.LabelFrame(top_frame, text="Control Panel", padding=10)
        ctrl_lf.pack(fill=tk.Y, side=tk.LEFT, padx=(0, 10))
        
        self.btn_start = ttk.Button(ctrl_lf, text="▶ Bắt đầu", style="Start.TButton", command=self.start_processing, width=12)
        self.btn_start.pack(pady=5)
        
        self.btn_stop = ttk.Button(ctrl_lf, text="⏹ Dừng", style="Stop.TButton", command=self.stop_processing, state=tk.DISABLED, width=12)
        self.btn_stop.pack(pady=5)
        
        # 1.2 Voice Settings Panel
        voice_lf = ttk.LabelFrame(top_frame, text="Voice Configuration", padding=10)
        voice_lf.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 10))
        
        # Voice grid layout
        voice_grid = ttk.Frame(voice_lf)
        voice_grid.pack(fill=tk.BOTH, expand=True)
        
        # Row 0: Search voice
        ttk.Label(voice_grid, text="Name Search:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.ent_search_name = ttk.Entry(voice_grid, width=15)
        self.ent_search_name.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        self.ent_search_name.insert(0, "vi-VN") # Default search term
        
        btn_search = ttk.Button(voice_grid, text="🔍 Tìm Kiếm", command=self.search_voices, width=12)
        btn_search.grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        
        # Buttons Add to library / Library VIP
        btn_add_lib = ttk.Button(voice_grid, text="➕ Thêm Thư Viện", command=self.add_to_library, width=16)
        btn_add_lib.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)
        
        btn_lib_vip = ttk.Button(voice_grid, text="🔊 Thư Viện Giọng", command=self.open_library, width=16)
        btn_lib_vip.grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        
        btn_keys_pool = ttk.Button(voice_grid, text="🔑 Quản Lý Keys", command=self.open_keys_pool, width=16)
        btn_keys_pool.grid(row=0, column=5, sticky=tk.W, padx=5, pady=2)
        
        # Row 1: Service, Voice
        ttk.Label(voice_grid, text="Service:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.cb_service = ttk.Combobox(voice_grid, values=["Edge-TTS", "ElevenLabs"], width=10, state="readonly")
        self.cb_service.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        self.cb_service.set("Edge-TTS")
        self.cb_service.bind("<<ComboboxSelected>>", self.on_service_changed)
        
        ttk.Label(voice_grid, text="Voice:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.cb_voice = ttk.Combobox(voice_grid, width=30, state="readonly")
        self.cb_voice.grid(row=1, column=3, columnspan=3, sticky=tk.EW, padx=5, pady=2)
        
        # Model is created but hidden
        self.lbl_model_dummy = ttk.Label(voice_grid, text="Model:")
        self.cb_model = ttk.Combobox(voice_grid, width=15, state="readonly")
        
        # Row 2: Speed and Change settings (Stability/Similarity are hidden)
        ttk.Label(voice_grid, text="Speed:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.spin_speed = ttk.Spinbox(voice_grid, from_=0.25, to=4.00, increment=0.05, width=6, state=tk.DISABLED)
        self.spin_speed.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        self.spin_speed.set("1.00")
        
        self.var_change_settings = tk.BooleanVar(value=False)
        self.chk_change_settings = ttk.Checkbutton(voice_grid, text="Change settings", variable=self.var_change_settings, command=self.toggle_voice_settings)
        self.chk_change_settings.grid(row=2, column=2, columnspan=4, sticky=tk.W, padx=10, pady=2)
        
        # Stability & Similarity are created but hidden
        self.lbl_stability_dummy = ttk.Label(voice_grid, text="Stability (%):")
        self.spin_stability = ttk.Spinbox(voice_grid, from_=0, to=100, increment=1, width=6, state=tk.DISABLED)
        self.spin_stability.set("50")
        
        self.lbl_similarity_dummy = ttk.Label(voice_grid, text="Similarity (%):")
        self.spin_similarity = ttk.Spinbox(voice_grid, from_=0, to=100, increment=1, width=6, state=tk.DISABLED)
        self.spin_similarity.set("75")
        
        # 1.3 Options Panel
        opts_lf = ttk.LabelFrame(top_frame, text="Options", padding=10)
        opts_lf.pack(fill=tk.Y, side=tk.RIGHT, padx=(10, 0))
        
        # Proxy row
        proxy_frame = ttk.Frame(opts_lf)
        proxy_frame.pack(fill=tk.X, pady=2)
        ttk.Label(proxy_frame, text="Proxy:").pack(side=tk.LEFT, padx=2)
        
        self.var_proxy_enabled = tk.BooleanVar(value=False)
        self.chk_proxy_enabled = ttk.Checkbutton(proxy_frame, text="Enable Pool", variable=self.var_proxy_enabled, command=self.on_proxy_toggle)
        self.chk_proxy_enabled.pack(side=tk.LEFT, padx=2)
        
        btn_manage_proxy = ttk.Button(proxy_frame, text="⚙️ Cấu Hình", width=11, command=self.open_proxy_manager_dashboard)
        btn_manage_proxy.pack(side=tk.RIGHT, padx=2)
        
        # Threads & Die/Err Status
        status_frame = ttk.Frame(opts_lf)
        status_frame.pack(fill=tk.X, pady=4)
        
        self.lbl_proxy_status = ttk.Label(status_frame, text="Live:0 / Err:0/4", font=("Segoe UI", 9, "bold"), foreground="#60a5fa")
        self.lbl_proxy_status.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(status_frame, text="Thread:").pack(side=tk.RIGHT, padx=2)
        self.spin_threads = ttk.Spinbox(status_frame, from_=1, to=50, increment=1, width=4)
        self.spin_threads.pack(side=tk.RIGHT, padx=2)
        self.spin_threads.set("10")
        
        # Join options sub-frame
        join_lf = ttk.LabelFrame(opts_lf, text="Cấu hình Ghép nối", padding=5)
        join_lf.pack(fill=tk.X, pady=(5, 0))
        
        self.var_align_timeline = tk.BooleanVar(value=True)
        self.chk_align_timeline = ttk.Checkbutton(join_lf, text="Khớp timeline video", variable=self.var_align_timeline, command=self.toggle_join_settings)
        self.chk_align_timeline.pack(anchor=tk.W, pady=2)
        
        # Max silence gap row
        max_sil_frame = ttk.Frame(join_lf)
        max_sil_frame.pack(fill=tk.X, pady=2)
        ttk.Label(max_sil_frame, text="Khoảng lặng max (s):").pack(side=tk.LEFT, padx=2)
        self.entry_max_silence = ttk.Entry(max_sil_frame, width=6)
        self.entry_max_silence.pack(side=tk.RIGHT, padx=2)
        self.entry_max_silence.insert(0, "0.30")
        
        # Default/Min pause row
        pause_frame = ttk.Frame(join_lf)
        pause_frame.pack(fill=tk.X, pady=2)
        ttk.Label(pause_frame, text="Nghỉ giữa câu (s):").pack(side=tk.LEFT, padx=2)
        self.entry_sentence_pause = ttk.Entry(pause_frame, width=6)
        self.entry_sentence_pause.pack(side=tk.RIGHT, padx=2)
        self.entry_sentence_pause.insert(0, "0.15")
        
        # Checkboxes Loop & Auto Split (Created but hidden from packaging)
        chk_frame = ttk.Frame(opts_lf)
        
        self.var_loop = tk.BooleanVar(value=False)
        self.chk_loop = ttk.Checkbutton(chk_frame, text="Loop", variable=self.var_loop)
        
        self.var_autosplit = tk.BooleanVar(value=False)
        self.chk_autosplit = ttk.Checkbutton(chk_frame, text="Auto Split (., ! ?)", variable=self.var_autosplit)
        
        self.var_normalize_acronyms = tk.BooleanVar(value=True)
        
        # 2. Subtitle Stats & Actions Frame
        action_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        action_frame.pack(fill=tk.X, side=tk.TOP)
        
        # Line 1: Statistics
        self.lbl_stats = ttk.Label(action_frame, text="Subtitles (Done: 0 Processing: 0 Total: 0) Elapsed: 0s", font=("Segoe UI", 9, "bold"))
        self.lbl_stats.pack(anchor=tk.W, pady=(0, 5))
        
        # Progress Bar
        self.progress_bar = ttk.Progressbar(action_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Line 2: Action Buttons
        btn_row = ttk.Frame(action_frame)
        btn_row.pack(fill=tk.X)
        
        ttk.Button(btn_row, text="📂 Nhập File", command=self.import_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="📁 Nhập Thư Mục", command=self.import_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="📺 Sub YouTube", command=self.open_youtube_downloader).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="📥 Mở Thư Mục Ra", command=self.open_output_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="📝 Định Dạng Câu", command=self.merge_sentences).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="🎵 Ghép Âm Thanh", command=self.join_audio_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="🎬 Ghép Vào Video", command=self.open_video_merger).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="🔄 Chạy Lại Lỗi", command=self.retry_failed_items).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="🔤 Xử Lý Viết Tắt", command=self.normalize_all_acronyms).pack(side=tk.LEFT, padx=5)
        
        self.btn_clear = ttk.Button(btn_row, text="🗑️ Xóa Danh Sách", command=self.clear_list)
        self.btn_clear.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 3. Main Data Treeview Table
        table_frame = ttk.Frame(self.root, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        columns = ("stt", "file", "text", "status", "duration", "path")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("stt", text="STT")
        self.tree.heading("file", text="Tên File Gốc")
        self.tree.heading("text", text="Nội Dung Văn Bản")
        self.tree.heading("status", text="Trạng Thái")
        self.tree.heading("duration", text="Độ Dài (s)")
        self.tree.heading("path", text="Đường Dẫn Kết Quả")
        
        self.tree.column("stt", width=50, minwidth=40, anchor=tk.CENTER)
        self.tree.column("file", width=150, minwidth=100)
        self.tree.column("text", width=450, minwidth=250)
        self.tree.column("status", width=100, minwidth=80, anchor=tk.CENTER)
        self.tree.column("duration", width=80, minwidth=60, anchor=tk.CENTER)
        self.tree.column("path", width=250, minwidth=150)
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 4. Footer Status Bar
        footer_frame = ttk.Frame(self.root, padding=5, relief=tk.SUNKEN)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.lbl_status_log = ttk.Label(footer_frame, text="Sẵn sàng...", font=("Segoe UI", 9))
        self.lbl_status_log.pack(side=tk.LEFT)
        
        lbl_credits = ttk.Label(footer_frame, text="Credits: Unlimited / User: Antigravity Agent / ExpiredDate: Lifetime", font=("Segoe UI", 9), foreground="#c084fc")
        lbl_credits.pack(side=tk.RIGHT)

    def toggle_voice_settings(self):
        state = tk.NORMAL if self.var_change_settings.get() else tk.DISABLED
        self.spin_speed.configure(state=state)
        self.spin_stability.configure(state=state)
        self.spin_similarity.configure(state=state)

    def toggle_join_settings(self):
        state = tk.NORMAL if self.var_align_timeline.get() else tk.DISABLED
        self.entry_max_silence.configure(state=state)

    def on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        # Open edit dialog if they double-clicked a row (specifically on the text column `#3`)
        if not item_id or column != "#3":
            return
            
        target_item = None
        for item in self.import_items:
            if str(item["id"]) == item_id:
                target_item = item
                break
                
        if not target_item:
            return
            
        self.open_edit_dialog(target_item, item_id)

    def open_edit_dialog(self, item, item_id):
        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Sửa nội dung câu {item['stt']}")
        edit_win.geometry("600x250")
        edit_win.transient(self.root)
        edit_win.grab_set()
        edit_win.resizable(True, True)
        
        # Center the edit window relative to the root window
        edit_win.update_idletasks()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        w = edit_win.winfo_width()
        h = edit_win.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        edit_win.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(edit_win, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Nội dung câu:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        text_box = tk.Text(main_frame, font=("Segoe UI", 10), wrap=tk.WORD, height=6)
        text_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_box.insert(tk.END, item["text"])
        text_box.focus_set()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        def save_changes():
            new_text = text_box.get("1.0", tk.END).strip()
            if not new_text:
                messagebox.showerror("Lỗi", "Nội dung câu không được để trống!", parent=edit_win)
                return
                
            if new_text != item["text"]:
                item["text"] = new_text
                item["status"] = "Ready"
                item["duration"] = 0.0
                item["output_path"] = ""
                
                # Update treeview
                self.tree.item(item_id, values=(
                    item["stt"],
                    item["file"],
                    item["text"],
                    item["status"],
                    "0.00",
                    ""
                ))
                self.update_stats_label()
                
            edit_win.destroy()
            
        def cancel_changes():
            edit_win.destroy()
            
        ttk.Button(btn_frame, text="💾 Lưu Thay Đổi", width=16, command=save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ Hủy Bỏ", width=10, command=cancel_changes).pack(side=tk.RIGHT)
        
        self.apply_dark_theme(edit_win)

    def normalize_all_acronyms(self):
        if not self.import_items:
            messagebox.showwarning("Xử lý viết tắt", "Danh sách câu trống!")
            return
            
        from acronym_processor import DICTIONARY, EXCEPTIONS, ACRONYM_MAP
        import collections
        import re
        
        # We will track replacement counts in a Counter
        stats = collections.Counter()
        
        # Sort keys by length descending to match longer terms first
        sorted_dict_keys = sorted(DICTIONARY.keys(), key=len, reverse=True)
        
        # Helper callbacks to count replacements
        def make_dict_replacer(key, has_s_allowed=False):
            def dict_replacer(match):
                has_s = False
                if has_s_allowed:
                    has_s = match.group(1) is not None
                
                stat_key = key + ("s" if has_s else "")
                stats[stat_key] += 1
                
                val = DICTIONARY[key]
                return " " + val + (" ét" if has_s else "") + " "
            return dict_replacer
            
        def replace_general_word(match):
            word = match.group(0)
            
            # Handle optional trailing 's'
            has_trailing_s = False
            lookup_word = word
            if word.endswith('s') and len(word) > 2 and word[:-1].isupper():
                has_trailing_s = True
                lookup_word = word[:-1]
                
            if lookup_word in EXCEPTIONS:
                return word
                
            stats[word] += 1
            
            phonetics = [ACRONYM_MAP.get(char, char) for char in lookup_word]
            result = " ".join(phonetics)
            if has_trailing_s:
                result += " ét"
            return " " + result + " "

        updated_count = 0
        for item in self.import_items:
            old_text = item["text"]
            text = old_text
            
            # 1. Dictionary replacements
            for key in sorted_dict_keys:
                escaped_key = re.escape(key)
                
                if key.isupper() and key.isalpha() and not key.endswith('S'):
                    # Allow optional 's' at the end: KPI -> KPI or KPIs
                    pattern_str = r'(?<![^\W\d_])' + escaped_key + r'(s)?(?![^\W\d_])'
                    text = re.sub(pattern_str, make_dict_replacer(key, has_s_allowed=True), text)
                else:
                    pattern_str = r'(?<![^\W\d_])' + escaped_key + r'(?![^\W\d_])'
                    text = re.sub(pattern_str, make_dict_replacer(key, has_s_allowed=False), text)
            
            # 2. General letter-by-letter replacements
            pattern = r'(?<![^\W\d_])[A-Z]{2,7}s?(?![^\W\d_])'
            text = re.sub(pattern, replace_general_word, text)
            
            # 3. Clean up spacing
            text = re.sub(r'\s+', ' ', text).strip()
            text = re.sub(r'\s+([.,!?:\;\)])', r'\1', text)
            text = re.sub(r'(\()\s+', r'\1', text)
            
            if text != old_text:
                item["text"] = text
                item["status"] = "Ready"
                item["duration"] = 0.0
                item["output_path"] = ""
                
                # Update treeview
                self.tree.item(str(item["id"]), values=(
                    item["stt"],
                    item["file"],
                    item["text"],
                    item["status"],
                    "0.00",
                    ""
                ))
                updated_count += 1
                
        # Refresh statistics log
        self.update_stats_label()
        
        # Show summary popup
        if stats:
            summary = f"Đã xử lý viết tắt thành công cho {updated_count} câu!\n\nChi tiết tần suất từ viết tắt:\n"
            for word, count in stats.most_common():
                summary += f"- {word}: {count} lần\n"
            messagebox.showinfo("Xử lý viết tắt", summary)
        else:
            messagebox.showinfo("Xử lý viết tắt", "Không tìm thấy cụm từ viết tắt nào mới cần xử lý.")

    def load_server_data(self):
        """Load available models and voices directly from Python module."""
        try:
            self.lbl_status_log.configure(text="Đang nạp cấu hình giọng đọc...")
            
            from tts_handler import get_models_formatted, get_voices_formatted, get_voices
            
            # Load models
            models_data = get_models_formatted()
            models = [m["id"] for m in models_data]
            
            # Load OpenAI voices
            voices_data = get_voices_formatted()
            voices = [v["id"] for v in voices_data]
            
            # Set values
            self.cb_model.configure(values=models)
            if models:
                self.cb_model.set(models[0])
                
            self.cb_voice.configure(values=voices)
            if voices:
                self.cb_voice.set(voices[0])
                
            # Load all Edge-TTS voices
            all_voices = get_voices(language='all')
            all_v_names = sorted([v["name"] for v in all_voices])
            self.all_voices_list = all_v_names
            
            # Merge lists
            combined_voices = voices + [v for v in all_v_names if v not in voices]
            self.cb_voice.configure(values=combined_voices)
            
            # Set default Vietnamese voice if available
            if "vi-VN-HoaiMyNeural" in combined_voices:
                self.cb_voice.set("vi-VN-HoaiMyNeural")
                
            self.lbl_status_log.configure(text="Đã nạp dữ liệu giọng đọc thành công!")
        except Exception as e:
            print(f"Error loading local TTS data: {e}")
            self.cb_model.configure(values=["tts-1", "tts-1-hd"])
            self.cb_model.set("tts-1")
            self.cb_voice.configure(values=["alloy", "echo", "fable", "onyx", "nova", "shimmer", "vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"])
            self.cb_voice.set("vi-VN-HoaiMyNeural")
            self.all_voices_list = ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
            self.lbl_status_log.configure(text="Lỗi nạp giọng đọc. Đã dùng dữ liệu mặc định.")

    def search_voices(self):
        query = self.ent_search_name.get().strip().lower()
        if not query:
            self.cb_voice.configure(values=self.all_voices_list)
            if self.all_voices_list:
                self.cb_voice.set(self.all_voices_list[0])
            return
            
        # Filter voices matching query
        filtered = [v for v in self.all_voices_list if query in v.lower()]
        if filtered:
            self.cb_voice.configure(values=filtered)
            self.cb_voice.set(filtered[0])
            self.lbl_status_log.configure(text=f"Tìm thấy {len(filtered)} giọng đọc khớp với '{query}'.")
        else:
            messagebox.showinfo("Tìm kiếm", f"Không tìm thấy giọng đọc nào chứa từ khóa '{query}'.")

    def add_to_library(self):
        messagebox.showinfo("Thư viện", "Đã thêm giọng đọc hiện tại vào thư viện yêu thích.")

    def open_library(self):
        lib_win = tk.Toplevel(self.root)
        lib_win.title("VIP Voice Library Browser")
        lib_win.geometry("850x550")
        lib_win.minsize(800, 480)
        lib_win.grab_set()
        
        # Top filters frame
        filter_frame = ttk.Frame(lib_win, padding=10)
        filter_frame.pack(fill=tk.X, side=tk.TOP)
        
        ttk.Label(filter_frame, text="Service:").pack(side=tk.LEFT, padx=5)
        cb_lib_service = ttk.Combobox(filter_frame, values=["All", "Edge-TTS", "ElevenLabs"], width=12, state="readonly")
        cb_lib_service.pack(side=tk.LEFT, padx=5)
        cb_lib_service.set("All")
        
        ttk.Label(filter_frame, text="Ngôn ngữ:").pack(side=tk.LEFT, padx=5)
        cb_lib_lang = ttk.Combobox(filter_frame, values=["All", "vi-VN", "en-US", "ja-JP", "ko-KR", "zh-CN"], width=10, state="readonly")
        cb_lib_lang.pack(side=tk.LEFT, padx=5)
        cb_lib_lang.set("All")
        
        ttk.Label(filter_frame, text="Tìm kiếm:").pack(side=tk.LEFT, padx=5)
        ent_lib_search = ttk.Entry(filter_frame, width=15)
        ent_lib_search.pack(side=tk.LEFT, padx=5)
        
        # Voice Treeview Table
        table_frame = ttk.Frame(lib_win, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        cols = ("service", "name", "gender", "locale", "voice_id")
        tree_lib = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        
        tree_lib.heading("service", text="Service")
        tree_lib.heading("name", text="Tên Giọng Đọc")
        tree_lib.heading("gender", text="Giới Tính")
        tree_lib.heading("locale", text="Mã Ngôn Ngữ")
        tree_lib.heading("voice_id", text="Voice ID / ShortName")
        
        tree_lib.column("service", width=80, anchor=tk.CENTER)
        tree_lib.column("name", width=150)
        tree_lib.column("gender", width=80, anchor=tk.CENTER)
        tree_lib.column("locale", width=100, anchor=tk.CENTER)
        tree_lib.column("voice_id", width=250)
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree_lib.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree_lib.xview)
        tree_lib.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        tree_lib.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        self.preview_mci_active = False
        
        # Bottom controls
        btn_frame = ttk.Frame(lib_win, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        lbl_info = ttk.Label(btn_frame, text="Chọn một giọng đọc và click để thao tác", foreground="gray")
        lbl_info.pack(side=tk.LEFT, padx=5)
        
        # Populate list
        voices_data = []
        
        # 1. Edge-TTS voices
        if hasattr(self, "all_voices_list") and self.all_voices_list:
            for v_name in self.all_voices_list:
                parts = v_name.split("-")
                locale = "-".join(parts[:2]) if len(parts) >= 2 else "unknown"
                short_name = parts[-1] if parts else v_name
                gender = "Male" if "nam" in short_name.lower() or "man" in short_name.lower() or "guy" in short_name.lower() else "Female"
                voices_data.append({
                    "service": "Edge-TTS",
                    "name": short_name,
                    "gender": gender,
                    "locale": locale,
                    "voice_id": v_name,
                    "preview_url": None
                })
        
        # 2. ElevenLabs voices
        api_key = self.get_active_api_key()
        el_raw_voices = []
        if api_key:
            try:
                res = requests.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": api_key}, timeout=5)
                if res.status_code == 200:
                    el_raw_voices = res.json().get("voices", [])
            except Exception:
                pass
                
        if el_raw_voices:
            for v in el_raw_voices:
                voices_data.append({
                    "service": "ElevenLabs",
                    "name": v["name"],
                    "gender": v.get("labels", {}).get("gender", "unknown").capitalize(),
                    "locale": v.get("labels", {}).get("accent", "en-US"),
                    "voice_id": v["voice_id"],
                    "preview_url": v.get("preview_url")
                })
        else:
            fallback_el = [
                ("Rachel", "Female", "US", "21m00Tcm4TlvDq8ikWAM", "https://api.elevenlabs.io/v1/voices/21m00Tcm4TlvDq8ikWAM/previews"),
                ("Drew", "Male", "US", "29vD33N1CtxCmqQRPOHJ", None),
                ("Clyde", "Male", "US", "EiwXtPIZ58qiFCDh9vv", None),
                ("Paul", "Male", "US", "5Q0t7uMcZetaP26tyZ7c", None),
                ("Nicole", "Female", "US", "piTKgcLEGmPEeZsZgnsD", None),
                ("Adam", "Male", "US", "pNInz6obpgfrhhF21wNZ", None),
                ("Antoni", "Male", "US", "ErXwobaYiN019PkySvjV", None),
                ("Bella", "Female", "US", "EXAVITQu4vr4xnSDxMaL", None)
            ]
            for name, gender, locale, v_id, p_url in fallback_el:
                voices_data.append({
                    "service": "ElevenLabs",
                    "name": name,
                    "gender": gender,
                    "locale": locale,
                    "voice_id": v_id,
                    "preview_url": p_url or f"https://api.elevenlabs.io/v1/voices/{v_id}/previews"
                })
                
        def update_lib_table():
            for row in tree_lib.get_children():
                tree_lib.delete(row)
                
            service_filter = cb_lib_service.get()
            lang_filter = cb_lib_lang.get()
            search_query = ent_lib_search.get().strip().lower()
            
            for v in voices_data:
                if service_filter != "All" and v["service"] != service_filter:
                    continue
                if lang_filter != "All" and lang_filter not in v["locale"]:
                    continue
                if search_query and search_query not in v["name"].lower() and search_query not in v["voice_id"].lower():
                    continue
                    
                tree_lib.insert("", "end", values=(
                    v["service"],
                    v["name"],
                    v["gender"],
                    v["locale"],
                    v["voice_id"]
                ))
                
        cb_lib_service.bind("<<ComboboxSelected>>", lambda e: update_lib_table())
        cb_lib_lang.bind("<<ComboboxSelected>>", lambda e: update_lib_table())
        ent_lib_search.bind("<KeyRelease>", lambda e: update_lib_table())
        
        update_lib_table()
        
        def stop_preview_audio():
            import ctypes
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW('stop preview_mp3', None, 0, 0)
            winmm.mciSendStringW('close preview_mp3', None, 0, 0)
            self.preview_mci_active = False
            lbl_info.configure(text="Đã dừng nghe thử.", foreground="#a1a1aa")
            
        def preview_voice():
            selected = tree_lib.focus()
            if not selected:
                messagebox.showwarning("Nghe thử", "Vui lòng chọn một giọng đọc trong bảng.")
                return
                
            vals = tree_lib.item(selected, "values")
            service_name, v_name, _, _, v_id = vals
            
            item = next((v for v in voices_data if v["voice_id"] == v_id), None)
            if not item:
                return
                
            if self.preview_mci_active:
                stop_preview_audio()
                
            if service_name == "Edge-TTS":
                lbl_info.configure(text="Đang sinh giọng nghe thử Edge-TTS...", foreground="#fbbf24")
                def edge_preview_thread():
                    try:
                        temp_path = os.path.join(tempfile.gettempdir(), f"preview_edge_{v_id}.mp3")
                        # Check proxy settings
                        proxy_str = None
                        if self.var_proxy_enabled.get():
                            proxy_str = self.proxy_manager.get_proxy(service_type="Edge-TTS")
                        
                        comm_kwargs = {
                            "text": f"Xin chào, đây là bản nghe thử giọng đọc {v_name} từ dịch vụ Edge TTS.",
                            "voice": v_id
                        }
                        connector = None
                        if proxy_str:
                            if proxy_str.startswith("socks"):
                                from aiohttp_socks import ProxyConnector
                                connector = ProxyConnector.from_url(proxy_str)
                                comm_kwargs["connector"] = connector
                            else:
                                comm_kwargs["proxy"] = proxy_str
                        
                        async def save_preview():
                            communicator = edge_tts.Communicate(**comm_kwargs)
                            await communicator.save(temp_path)
                            if connector:
                                await connector.close()
                                
                        asyncio.run(save_preview())
                        play_mci_sound(temp_path)
                        lbl_info.configure(text="Phát âm thanh nghe thử thành công.", foreground="#10b981")
                    except Exception as e:
                        print(f"Edge-TTS preview error: {e}")
                        self.update_queue.put(("log", f"Lỗi sinh audio preview: {e}"))
                        
                threading.Thread(target=edge_preview_thread, daemon=True).start()
            else:
                p_url = item["preview_url"]
                if not p_url:
                    lbl_info.configure(text="Giọng đọc này không hỗ trợ link nghe thử.", foreground="#ef4444")
                    return
                    
                lbl_info.configure(text="Đang tải tệp nghe thử ElevenLabs...", foreground="#fbbf24")
                
                def download_and_play():
                    try:
                        res = requests.get(p_url, timeout=15)
                        if res.status_code == 200:
                            temp_path = os.path.join(tempfile.gettempdir(), f"preview_el_{v_id}.mp3")
                            with open(temp_path, "wb") as f:
                                f.write(res.content)
                            play_mci_sound(temp_path)
                        else:
                            self.root.after(0, lambda: lbl_info.configure(text="Không tải được tệp nghe thử.", foreground="#ef4444"))
                    except Exception as e:
                        print(f"Error playing preview: {e}")
                        self.root.after(0, lambda: lbl_info.configure(text="Lỗi tải tệp nghe thử.", foreground="#ef4444"))
                        
                threading.Thread(target=download_and_play, daemon=True).start()
                
        def play_mci_sound(filepath):
            import ctypes
            winmm = ctypes.windll.winmm
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(filepath, buf, 260)
            short_path = buf.value
            
            winmm.mciSendStringW(f'open "{short_path}" type mpegvideo alias preview_mp3', None, 0, 0)
            winmm.mciSendStringW('play preview_mp3', None, 0, 0)
            
            self.preview_mci_active = True
            self.root.after(0, lambda: lbl_info.configure(text=f"Đang phát nghe thử giọng...", foreground="#10b981"))
            
        def select_voice():
            selected = tree_lib.focus()
            if not selected:
                messagebox.showwarning("Chọn giọng", "Vui lòng chọn một giọng đọc trong bảng.")
                return
                
            vals = tree_lib.item(selected, "values")
            service_name, _, _, _, v_id = vals
            
            self.cb_service.set(service_name)
            self.on_service_changed()
            
            voice_values = self.cb_voice["values"]
            matching = [v for v in voice_values if v_id in v or v == v_id]
            if matching:
                self.cb_voice.set(matching[0])
            else:
                new_vals = list(voice_values) + [v_id]
                self.cb_voice.configure(values=new_vals)
                self.cb_voice.set(v_id)
                
            if self.preview_mci_active:
                stop_preview_audio()
            lib_win.destroy()
            
        def on_close():
            if self.preview_mci_active:
                stop_preview_audio()
            lib_win.destroy()
            
        lib_win.protocol("WM_DELETE_WINDOW", on_close)
        
        ttk.Button(btn_frame, text="🔊 Nghe thử", command=preview_voice, width=14).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="⏹ Dừng nghe", command=stop_preview_audio, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="✅ Chọn giọng này", command=select_voice, width=18, style="Start.TButton").pack(side=tk.RIGHT, padx=5)
        
        self.apply_dark_theme(lib_win)

    def on_proxy_toggle(self):
        enabled = self.var_proxy_enabled.get()
        if enabled:
            self.lbl_status_log.configure(text="Đã bật sử dụng Proxy Pool.")
            # Set manager replenish protocol based on active service
            service = self.cb_service.get()
            pref_protocol = "SOCKS5" if service == "Edge-TTS" else "HTTP"
            self.proxy_manager.set_replenish(self.proxy_manager.replenish_enabled, pref_protocol)
        else:
            self.lbl_status_log.configure(text="Đã tắt sử dụng Proxy Pool.")

    # Import and display files in table
    def add_items_to_tree(self, parsed_items, filename):
        start_idx = len(self.import_items) + 1
        for item in parsed_items:
            item_data = {
                "id": len(self.import_items),
                "stt": start_idx,
                "file": filename,
                "text": item["text"],
                "type": item["type"],
                "start": item.get("start", ""),
                "end": item.get("end", ""),
                "status": "Ready",
                "duration": 0.0,
                "output_path": ""
            }
            self.import_items.append(item_data)
            
            # Add row to tree
            self.tree.insert("", "end", iid=str(item_data["id"]), values=(
                item_data["stt"],
                item_data["file"],
                item_data["text"],
                item_data["status"],
                "0.00",
                ""
            ))
            start_idx += 1
            
        self.update_stats_label()

    def import_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file phụ đề / văn bản",
            filetypes=[("Subtitle & Text Files", "*.srt;*.txt;*.dgt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
            
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        auto_split = self.var_autosplit.get()
        
        parsed = []
        if ext == ".srt":
            parsed = parse_srt(file_path)
        elif ext == ".txt":
            parsed = parse_txt(file_path, auto_split=auto_split)
        elif ext == ".dgt":
            parsed = parse_dgt(file_path, auto_split=auto_split)
            
        if parsed:
            self.add_items_to_tree(parsed, filename)
            self.lbl_status_log.configure(text=f"Đã nhập thành công {len(parsed)} dòng từ file {filename}.")
        else:
            messagebox.showwarning("Nhập file", "Không thể đọc hoặc file rỗng / sai cấu trúc.")

    def import_folder(self):
        folder_path = filedialog.askdirectory(title="Chọn thư mục nhập file")
        if not folder_path:
            return
            
        files = [f for f in os.listdir(folder_path) if os.path.splitext(f)[1].lower() in [".srt", ".txt", ".dgt"]]
        if not files:
            messagebox.showinfo("Nhập thư mục", "Không tìm thấy file .srt, .txt, hoặc .dgt nào trong thư mục này.")
            return
            
        total_parsed = 0
        auto_split = self.var_autosplit.get()
        
        for file in files:
            full_path = os.path.join(folder_path, file)
            ext = os.path.splitext(file)[1].lower()
            parsed = []
            if ext == ".srt":
                parsed = parse_srt(full_path)
            elif ext == ".txt":
                parsed = parse_txt(full_path, auto_split=auto_split)
            elif ext == ".dgt":
                parsed = parse_dgt(full_path, auto_split=auto_split)
                
            if parsed:
                self.add_items_to_tree(parsed, file)
                total_parsed += len(parsed)
                
        self.lbl_status_log.configure(text=f"Đã nhập tổng cộng {total_parsed} dòng từ {len(files)} file trong thư mục.")

    def open_output_dir(self):
        try:
            os.startfile(self.output_dir)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục đầu ra: {e}")

    def clear_list(self):
        self.import_items = []
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.done_count = 0
        self.err_count = 0
        self.lbl_proxy_status.configure(text=f"Live:{len(self.proxy_manager.live_proxies)} / Err:0/4")
        self.progress_bar["value"] = 0
        self.update_stats_label()
        self.lbl_status_log.configure(text="Đã xóa danh sách.")

    def update_stats_label(self):
        processing = 0
        if self.is_processing:
            processing = len([i for i in self.import_items if i["status"] == "Processing..."])
            
        self.lbl_stats.configure(text=f"Subtitles (Done: {self.done_count} Processing: {processing} Total: {len(self.import_items)}) Elapsed: {self.elapsed_time}s")

    # Background Generation Core
    def start_processing(self):
        if not self.import_items:
            messagebox.showwarning("Bắt đầu", "Danh sách xử lý trống. Vui lòng nhập file trước!")
            return
            
        if self.is_processing:
            return
            
        # Reset failed/Error items to Ready so they can be processed again
        for item in self.import_items:
            if item["status"] == "Error":
                item["status"] = "Ready"
                self.tree.set(str(item["id"]), column="status", value="Ready")
                
        # Recalculate counts dynamically to ensure 100% sync
        self.done_count = len([i for i in self.import_items if i["status"] == "Done"])
        self.err_count = len([i for i in self.import_items if i["status"] == "Error"])
        
        self.lbl_proxy_status.configure(text=f"Live:{len(self.proxy_manager.live_proxies)} / Err:{self.err_count}/4")

        self.is_processing = True
        self.cancel_requested = False
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        
        self.progress_bar["maximum"] = len(self.import_items)
        self.progress_bar["value"] = self.done_count + self.err_count
        
        self.elapsed_start_time = time.time() - self.elapsed_time
        self.lbl_status_log.configure(text="Bắt đầu chạy luồng sinh giọng nói...")
        
        # Spawn thread for loop
        self.processing_thread = threading.Thread(target=self.run_processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def stop_processing(self):
        if not self.is_processing:
            return
            
        self.lbl_status_log.configure(text="Đang dừng tiến trình xử lý...")
        self.cancel_requested = True
        
        # Instantly cancel active asyncio tasks for Edge-TTS
        if hasattr(self, "active_async_tasks") and self.active_async_tasks:
            for task in self.active_async_tasks:
                if not task.done():
                    task.cancel()
        
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
            
        self.is_processing = False
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)

    def retry_failed_items(self):
        if self.is_processing:
            messagebox.showwarning("Tạo lại", "Tiến trình đang chạy. Vui lòng dừng hoặc chờ hoàn thành!")
            return
            
        failed_items = [i for i in self.import_items if i["status"] == "Error"]
        if not failed_items:
            messagebox.showinfo("Tạo lại", "Không có câu nào bị lỗi để tạo lại.")
            return
            
        # Reset them to Ready
        for item in failed_items:
            item["status"] = "Ready"
            self.tree.set(str(item["id"]), column="status", value="Ready")
            
        # Recalculate counts dynamically to ensure 100% sync
        self.done_count = len([i for i in self.import_items if i["status"] == "Done"])
        self.err_count = len([i for i in self.import_items if i["status"] == "Error"])
        self.lbl_proxy_status.configure(text=f"Live:{len(self.proxy_manager.live_proxies)} / Err:{self.err_count}/4")
        self.progress_bar["value"] = self.done_count + self.err_count
        
        self.lbl_status_log.configure(text=f"Đã đặt lại {len(failed_items)} câu bị lỗi về trạng thái Chờ xử lý.")
        # Start processing automatically
        self.start_processing()

    def run_processing_loop(self):
        # Fetch current UI parameters
        voice = self.cb_voice.get()
        # Extract voice ID if it contains brackets e.g. "Rachel (21m00T...)"
        voice_id = voice
        if "(" in voice and voice.endswith(")"):
            voice_id = voice.split("(")[-1][:-1].strip()
            
        model = self.cb_model.get()
        speed = float(self.spin_speed.get()) if self.var_change_settings.get() else 1.0
        
        threads_count = int(self.spin_threads.get())
        
        # Check if service is Edge-TTS
        service = self.cb_service.get()
        is_edge_tts = (service == "Edge-TTS")
        
        # Filter items that are not Done
        items_to_process = [i for i in self.import_items if i["status"] != "Done"]
        if not items_to_process:
            self.update_queue.put(("log", "Tất cả các dòng đã hoàn thành."))
            self.update_queue.put(("finish", None))
            return
        
        if is_edge_tts:
            # If proxy pool is enabled, allow full threads_count concurrency.
            # Otherwise, cap at 5 to avoid Microsoft rate-limiting/blocking.
            if self.var_proxy_enabled.get():
                concurrency = threads_count
            else:
                concurrency = min(threads_count, 5)
            self.update_queue.put(("log", f"⚡ Edge-TTS Turbo Mode -> Async batch ({concurrency} đồng thời)..."))
            
            # Mark all items as Processing
            for item in items_to_process:
                self.update_queue.put(("status", (item["id"], "Processing...")))
            
            # Run async batch in this thread
            try:
                asyncio.run(self._process_edge_tts_batch(items_to_process, voice_id, speed, concurrency))
            except Exception as e:
                print(f"Async batch error: {e}")
                self.update_queue.put(("log", f"Lỗi async batch: {str(e)}"))
        else:
            # ===== ELEVENLABS: Thread pool (uses HTTP API) =====
            with self.proxy_manager.lock:
                has_proxies = len(self.proxy_manager.live_proxies) > 0
            if has_proxies:
                self.update_queue.put(("log", f"ElevenLabs + Proxy Pool -> Đa luồng ({threads_count} luồng)..."))
            else:
                self.update_queue.put(("log", f"Đang chạy đa luồng ElevenLabs ({threads_count} luồng)..."))
            
            self.executor = ThreadPoolExecutor(max_workers=threads_count)
            futures = {}
            for item in items_to_process:
                if self.cancel_requested:
                    break
                self.update_queue.put(("status", (item["id"], "Processing...")))
                future = self.executor.submit(self._process_elevenlabs_item, item, voice_id, model, speed)
                futures[future] = item["id"]
            
            # Use as_completed() for faster UI updates (process results as they finish)
            for future in as_completed(futures):
                if self.cancel_requested:
                    break
                item_id = futures[future]
                try:
                    result = future.result()
                    if self.cancel_requested:
                        break
                    if result:
                        self.update_queue.put(("success", (item_id, result["duration"], result["output_path"])))
                    else:
                        self.update_queue.put(("error", (item_id, "Error")))
                except Exception as e:
                    if self.cancel_requested:
                        break
                    print(f"Worker error for ID {item_id}: {e}")
                    self.update_queue.put(("error", (item_id, "Error")))
                
        self.update_queue.put(("finish", None))

    # ======================== EDGE-TTS ASYNC BATCH ========================
    async def _process_edge_tts_batch(self, items, voice_id, speed, concurrency):
        """Process all Edge-TTS items in a single asyncio event loop.
        Uses asyncio.Semaphore for rate limiting and asyncio.gather for concurrency.
        Bypasses HTTP server entirely - calls edge-tts directly."""
        from acronym_processor import normalize_acronyms_vi
        from tts_handler import speed_to_rate
        from handle_text import prepare_tts_input_with_context
        
        sem = asyncio.Semaphore(concurrency)
        speed_rate = speed_to_rate(speed)
        is_vietnamese = voice_id.lower().startswith('vi-') or 'vietnam' in voice_id.lower()
        
        self.active_async_tasks = []
        
        async def process_one(item):
            import random
            item_id = item["id"]
            text = item["text"]
            
            # Prepare output path
            out_filename = f"audio_{item['file']}_{item['stt']}.mp3"
            out_filename = "".join([c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in out_filename])
            output_file_path = os.path.join(self.output_dir, out_filename)
            
            # Text preprocessing (same as server pipeline)
            text = prepare_tts_input_with_context(text)
            if is_vietnamese and self.var_normalize_acronyms.get():
                text = normalize_acronyms_vi(text)
            
            max_retries = 4
            for attempt in range(1, max_retries + 1):
                if self.cancel_requested:
                    return
                
                # Query proxy from ProxyManager if enabled
                current_proxy_str = None
                if self.var_proxy_enabled.get():
                    current_proxy_str = self.proxy_manager.get_proxy(service_type="Edge-TTS")
                    
                try:
                    async with sem:
                        if self.cancel_requested:
                            return
                        # Small jitter to spread requests
                        await asyncio.sleep(random.uniform(0.05, 0.3))
                        if self.cancel_requested:
                            return
                        
                        start_time = time.time()
                        comm_kwargs = {
                            "text": text,
                            "voice": voice_id,
                            "rate": speed_rate
                        }
                        connector = None
                        if current_proxy_str:
                            if current_proxy_str.startswith("socks"):
                                from aiohttp_socks import ProxyConnector
                                connector = ProxyConnector.from_url(current_proxy_str)
                                comm_kwargs["connector"] = connector
                            else:
                                comm_kwargs["proxy"] = current_proxy_str
                                
                        communicator = edge_tts.Communicate(**comm_kwargs)
                        await communicator.save(output_file_path)
                        
                        if connector:
                            await connector.close()
                    
                    if self.cancel_requested:
                        return
                        
                    # Trim leading and trailing silence
                    self.trim_audio_silence(output_file_path)
                    # Get duration (mutagen, ~2ms)
                    duration = get_audio_duration(output_file_path)
                    self.update_queue.put(("success", (item_id, duration, output_file_path)))
                    
                    # Report proxy success
                    if current_proxy_str:
                        latency = time.time() - start_time
                        self.proxy_manager.report_success(current_proxy_str, latency)
                    return
                    
                except asyncio.CancelledError:
                    if connector:
                        try:
                            await connector.close()
                        except Exception:
                            pass
                    return
                except Exception as e:
                    if self.cancel_requested:
                        if connector:
                            try:
                                await connector.close()
                            except Exception:
                                pass
                        return
                        
                    print(f"Edge-TTS attempt {attempt}/{max_retries} row {item['stt']}: {e}")
                    
                    # Report proxy failure
                    if current_proxy_str:
                        self.proxy_manager.report_failure(current_proxy_str)
                        
                    # Exponential backoff
                    backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                    self.update_queue.put(("log", f"Retry {attempt}/{max_retries} câu {item['stt']} sau {backoff:.1f}s..."))
                    await asyncio.sleep(backoff)
            
            # All retries failed
            if not self.cancel_requested:
                self.update_queue.put(("error", (item_id, "Error")))
        
        # Launch all tasks and store in self.active_async_tasks for cancellation
        tasks = []
        for item in items:
            task = asyncio.create_task(process_one(item))
            tasks.append(task)
            self.active_async_tasks.append(task)
            
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self.active_async_tasks = []

    # ======================== ELEVENLABS THREAD POOL ========================
    def _process_elevenlabs_item(self, item, voice_id, model, speed):
        """Process a single ElevenLabs item in thread pool worker."""
        import random as _random
        
        text = item["text"]
        item_id = item["id"]
        
        out_filename = f"audio_{item['file']}_{item['stt']}.mp3"
        out_filename = "".join([c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in out_filename])
        output_file_path = os.path.join(self.output_dir, out_filename)
        
        max_retries = 4
        
        # Reduced jitter: 0.05-0.3s (was 0.1-1.5s)
        jitter = _random.uniform(0.05, 0.3)
        time.sleep(jitter)
        
        for attempt in range(1, max_retries + 1):
            if self.cancel_requested:
                return None
                
            # Query proxy from ProxyManager if enabled
            current_proxy_str = None
            current_proxy_dict = None
            if self.var_proxy_enabled.get():
                current_proxy_str = self.proxy_manager.get_proxy(service_type="ElevenLabs")
                if current_proxy_str:
                    current_proxy_dict = {
                        "http": current_proxy_str,
                        "https": current_proxy_str
                    }
                    
            try:
                api_key = self.get_active_api_key()
                if not api_key:
                    raise ValueError("Không tìm thấy ElevenLabs API Key.")
                    
                stability = float(self.spin_stability.get()) / 100.0
                similarity = float(self.spin_similarity.get()) / 100.0
                
                from tts_handler import generate_speech_elevenlabs
                start_time = time.time()
                res_path = generate_speech_elevenlabs(
                    text=text,
                    voice_id=voice_id,
                    model_id=model,
                    api_key=api_key,
                    stability=stability,
                    similarity=similarity,
                    speed=speed,
                    proxies=current_proxy_dict
                )
                
                import shutil
                os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                shutil.move(res_path, output_file_path)
                
                # Trim leading and trailing silence
                self.trim_audio_silence(output_file_path)
                duration = get_audio_duration(output_file_path)
                
                # Report proxy success
                if current_proxy_str:
                    latency = time.time() - start_time
                    self.proxy_manager.report_success(current_proxy_str, latency)
                    
                return {
                    "duration": duration,
                    "output_path": output_file_path
                }
            except Exception as e:
                print(f"Attempt {attempt}/{max_retries} failed for row {item['stt']}: {e}")
                
                # Report proxy failure
                if current_proxy_str:
                    self.proxy_manager.report_failure(current_proxy_str)
                    
                # Rotate API key on auth/quota error
                if "401" in str(e) or "429" in str(e) or "quota" in str(e).lower():
                    self.rotate_api_key()
                    active_key = self.get_active_api_key()
                    self.update_queue.put(("log", f"Đổi sang ElevenLabs Key tiếp theo: ...{active_key[-6:] if active_key else 'None'}"))
                    
                # Exponential backoff
                backoff_delay = (2 ** attempt) + _random.uniform(0.5, 2.0)
                self.update_queue.put(("log", f"Retry {attempt}/{max_retries} câu {item['stt']} sau {backoff_delay:.1f}s..."))
                time.sleep(backoff_delay)
                
        return None

    # Handle UI Updates in Main Thread
    def process_queue(self):
        while not self.update_queue.empty():
            try:
                msg_type, data = self.update_queue.get_nowait()
                if msg_type == "log":
                    self.lbl_status_log.configure(text=data)
                elif msg_type == "status":
                    item_id, status = data
                    self.import_items[item_id]["status"] = status
                    self.tree.set(str(item_id), column="status", value=status)
                elif msg_type == "success":
                    item_id, duration, path = data
                    item = self.import_items[item_id]
                    item["status"] = "Done"
                    item["duration"] = duration
                    item["output_path"] = path
                    
                    self.tree.set(str(item_id), column="status", value="Done")
                    self.tree.set(str(item_id), column="duration", value=f"{duration:.2f}")
                    self.tree.set(str(item_id), column="path", value=path)
                    
                    self.done_count += 1
                    self.progress_bar["value"] = self.done_count + self.err_count
                    self.update_stats_label()
                elif msg_type == "error":
                    item_id, status = data
                    self.import_items[item_id]["status"] = status
                    self.tree.set(str(item_id), column="status", value=status)
                    self.err_count += 1
                    self.lbl_proxy_status.configure(text=f"Live:{len(self.proxy_manager.live_proxies)} / Err:{self.err_count}/4")
                    self.progress_bar["value"] = self.done_count + self.err_count
                    self.update_stats_label()
                elif msg_type in ("proxy_count_update", "proxy_list_updated"):
                    self.lbl_proxy_status.configure(text=f"Live:{len(self.proxy_manager.live_proxies)} / Err:{self.err_count}/4")
                    self.refresh_proxy_dashboard_table()
                elif msg_type == "finish":
                    self.is_processing = False
                    self.btn_start.configure(state=tk.NORMAL)
                    self.btn_stop.configure(state=tk.DISABLED)
                    self.lbl_status_log.configure(text="Tiến trình hoàn thành!")
                    self.update_stats_label()
                    
                    # If Loop is enabled, auto restart
                    if self.var_loop.get() and not self.cancel_requested:
                        # Reset failed items to Ready and restart
                        reset_any = False
                        for item in self.import_items:
                            if item["status"] != "Done":
                                item["status"] = "Ready"
                                self.tree.set(str(item["id"]), column="status", value="Ready")
                                reset_any = True
                        if reset_any:
                            self.lbl_status_log.configure(text="Lặp lại tiến trình...")
                            self.root.after(1000, self.start_processing)
            except queue.Empty:
                break
                
        # Call again
        self.root.after(100, self.process_queue)

    def update_timer(self):
        if self.is_processing:
            self.elapsed_time = int(time.time() - self.elapsed_start_time)
            self.update_stats_label()
        self.root.after(1000, self.update_timer)

    # Creating SRT file
    def generate_srt_file(self):
        if not self.import_items:
            messagebox.showwarning("Tạo srt", "Danh sách phụ đề trống. Vui lòng nhập file trước!")
            return
            
        save_path = os.path.abspath(os.path.join(self.output_dir, f"{self.get_base_filename()}_tts.srt"))
            
        # Check if we have synthesized items
        done_items = [i for i in self.import_items if i["status"] == "Done"]
        
        srt_items = []
        
        if done_items:
            # We have synthesized items, we can use their new timings
            has_children = any("children" in item and item["children"] for item in done_items)
            
            if has_children:
                ans = messagebox.askyesnocancel("Tạo SRT", 
                    "Bạn muốn xuất phụ đề dưới dạng nào?\n\n"
                    "👉 Chọn YES: Giữ nguyên cấu trúc dòng gốc (Tự động phân bổ lại thời gian).\n"
                    "👉 Chọn NO: Lưu dưới dạng câu đã gộp hoàn chỉnh (Giao diện phụ đề mới ngắn gọn hơn).")
                
                if ans is None:  # Cancel
                    return
                elif ans is True:  # Yes - Redistribute
                    from text_processor import redistribute_subtitles_timing
                    srt_items = redistribute_subtitles_timing(done_items)
                else:  # No - Keep merged
                    current_time = 0.0
                    for item in done_items:
                        start_t = item.get("joined_start")
                        end_t = item.get("joined_end")
                        if start_t is None or end_t is None:
                            start_t = current_time
                            duration = item.get("duration", 0.0)
                            end_t = start_t + duration
                            current_time = end_t + 0.2
                            
                        srt_items.append({
                            "index": len(srt_items) + 1,
                            "start": format_srt_time(start_t),
                            "end": format_srt_time(end_t),
                            "text": item["text"]
                        })
            else:
                # Traditional calculation based on duration
                current_time = 0.0
                for item in done_items:
                    start_t = item.get("joined_start")
                    end_t = item.get("joined_end")
                    if start_t is None or end_t is None:
                        start_t = current_time
                        duration = item.get("duration", 0.0)
                        end_t = start_t + duration
                        current_time = end_t + 0.2
                        
                    srt_items.append({
                        "index": len(srt_items) + 1,
                        "start": format_srt_time(start_t),
                        "end": format_srt_time(end_t),
                        "text": item["text"]
                    })
        else:
            # No synthesized items, just export the current items using their original timestamps
            for i, item in enumerate(self.import_items):
                srt_items.append({
                    "index": i + 1,
                    "start": item["start"],
                    "end": item["end"],
                    "text": item["text"]
                })
                
        try:
            write_srt_file(srt_items, save_path)
            self.lbl_status_log.configure(text=f"Đã tạo file phụ đề tại: {save_path}")
            messagebox.showinfo("Thành công", f"Đã tạo file phụ đề SRT thành công tại:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể ghi file phụ đề: {e}")

    # Format sentences logic (formerly Merge sentences)
    def merge_sentences(self):
        if not self.import_items:
            messagebox.showwarning("Định dạng câu", "Danh sách rỗng. Vui lòng nhập file phụ đề trước!")
            return
            
        # Get GEMINI_API_KEY from environment
        env_gemini_key = os.getenv("GEMINI_API_KEY", "")
        
        # Show configuration dialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Định dạng & Phục hồi phụ đề")
        dlg.geometry("450x260")
        dlg.resizable(False, False)
        dlg.grab_set()
        
        # Center dialog
        dlg.update_idletasks()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        dlg.geometry(f"+{rx + (rw - w) // 2}+{ry + (rh - h) // 2}")
        
        self.apply_dark_theme(dlg)
        
        # Title
        ttk.Label(dlg, text="Chọn phương án xử lý phụ đề", font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        # Options Frame
        opts_frame = ttk.Frame(dlg, padding=10)
        opts_frame.pack(fill=tk.X, padx=15)
        
        var_mode = tk.StringVar(value="local")
        
        def on_mode_change():
            if var_mode.get() == "gemini":
                key_entry.configure(state="normal")
                chk_save.configure(state="normal")
            else:
                key_entry.configure(state="disabled")
                chk_save.configure(state="disabled")
                
        r_local = ttk.Radiobutton(opts_frame, text="Phương án A: Heuristic Cục bộ (Offline)", variable=var_mode, value="local", command=on_mode_change)
        r_local.pack(anchor=tk.W, pady=2)
        
        r_gemini = ttk.Radiobutton(opts_frame, text="Phương án B: Trí tuệ nhân tạo Gemini AI (Online)", variable=var_mode, value="gemini", command=on_mode_change)
        r_gemini.pack(anchor=tk.W, pady=2)
        
        # Key entry frame
        key_frame = ttk.Frame(dlg, padding=5)
        key_frame.pack(fill=tk.X, padx=20)
        
        ttk.Label(key_frame, text="Gemini API Key:").pack(side=tk.LEFT, padx=(0, 5))
        key_entry = ttk.Entry(key_frame, width=32, show="*")
        key_entry.insert(0, env_gemini_key)
        key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        key_entry.configure(state="disabled")
        
        # Save key checkbox
        chk_frame = ttk.Frame(dlg, padding=2)
        chk_frame.pack(fill=tk.X, padx=20)
        var_save_key = tk.BooleanVar(value=True)
        chk_save = ttk.Checkbutton(chk_frame, text="Lưu API Key vào file .env", variable=var_save_key)
        chk_save.pack(anchor=tk.W)
        chk_save.configure(state="disabled")
        
        # If there's an API Key in env, default to gemini AI option
        if env_gemini_key:
            var_mode.set("gemini")
            on_mode_change()
            
        def on_confirm():
            mode = var_mode.get()
            api_key = key_entry.get().strip()
            save_key = var_save_key.get()
            
            if mode == "gemini" and not api_key:
                messagebox.showerror("Lỗi", "Vui lòng nhập Gemini API Key để tiếp tục!", parent=dlg)
                return
                
            dlg.destroy()
            
            if mode == "gemini":
                # Save key to .env if requested
                if save_key:
                    self.save_gemini_key_to_env(api_key)
                # Run Gemini restructuring in background
                self.run_gemini_restoration(api_key)
            else:
                # Run local heuristics directly
                self.run_local_merging()
                
        btn_frame = ttk.Frame(dlg, padding=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Button(btn_frame, text="✅ Xác Nhận", width=12, style="Start.TButton", command=on_confirm).pack(side=tk.RIGHT, padx=(5, 15))
        ttk.Button(btn_frame, text="❌ Hủy", width=10, command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

    def save_gemini_key_to_env(self, api_key):
        try:
            dotenv_path = ".env"
            lines = []
            key_found = False
            
            if os.path.exists(dotenv_path):
                with open(dotenv_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("GEMINI_API_KEY="):
                            lines.append(f"GEMINI_API_KEY={api_key}\n")
                            key_found = True
                        else:
                            lines.append(line)
                            
            if not key_found:
                if lines and not lines[-1].endswith("\n"):
                    lines.append("\n")
                lines.append(f"GEMINI_API_KEY={api_key}\n")
                
            with open(dotenv_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            os.environ["GEMINI_API_KEY"] = api_key
            self.update_queue.put(("log", "Đã lưu Gemini API Key vào file .env thành công!"))
        except Exception as e:
            print(f"Error saving Gemini key to env: {e}")

    def run_local_merging(self):
        from text_processor import merge_subtitle_items
        self.lbl_status_log.configure(text="Đang định dạng câu bằng thuật toán Heuristic...")
        
        merged = merge_subtitle_items(self.import_items)
        if len(merged) == len(self.import_items):
            messagebox.showinfo("Định dạng câu", "Các câu trong danh sách đã hoàn chỉnh hoặc không thể định dạng thêm.")
            return
            
        msg = f"Đã định dạng {len(self.import_items)} dòng thành {len(merged)} câu hoàn chỉnh.\n\n" \
              f"Bảng danh sách sẽ được cập nhật thành các câu mới để chuẩn bị sinh giọng đọc tự nhiên hơn."
        if not messagebox.askokcancel("Định dạng câu", msg):
            return
            
        self.update_import_list_with_merged(merged)

    def update_import_list_with_merged(self, merged):
        for i, item in enumerate(merged):
            item["id"] = i
            item["stt"] = i + 1
            if "status" not in item:
                item["status"] = "Ready"
            if "duration" not in item:
                item["duration"] = 0.0
            if "output_path" not in item:
                item["output_path"] = ""
            
        self.import_items = merged
        
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        for item in self.import_items:
            self.tree.insert("", "end", iid=str(item["id"]), values=(
                item["stt"],
                item["file"],
                item["text"],
                item["status"],
                "0.00",
                ""
            ))
            
        self.done_count = 0
        self.err_count = 0
        self.lbl_proxy_status.configure(text="Die:0 / Err:0/4")
        self.update_stats_label()
        
        save_path = os.path.abspath(os.path.join(self.output_dir, f"{self.get_base_filename()}_tts.srt"))
        from text_processor import write_srt_file
        srt_items = []
        for i, item in enumerate(self.import_items):
            srt_items.append({
                "index": i + 1,
                "start": item["start"],
                "end": item["end"],
                "text": item["text"]
            })
        try:
            write_srt_file(srt_items, save_path)
            self.lbl_status_log.configure(text=f"Đã định dạng và xuất file phụ đề tại: {save_path}")
            messagebox.showinfo("Thành công", f"Đã định dạng thành công và xuất file phụ đề tại:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể ghi file phụ đề: {e}")

    def run_gemini_restoration(self, api_key):
        self.lbl_status_log.configure(text="Đang kết nối Gemini AI để khôi phục cấu trúc phụ đề...")
        
        def bg_thread():
            proxy_str = None
            try:
                from text_processor import merge_subtitle_items_gemini
                
                # Retrieve active proxy from ProxyManager
                proxy_str = self.proxy_manager.get_proxy(service_type="ElevenLabs")
                if proxy_str:
                    self.update_queue.put(("log", f"Sử dụng proxy cho Gemini: {proxy_str}"))
                else:
                    self.update_queue.put(("log", "Không có proxy, kết nối trực tiếp đến Gemini AI..."))
                
                def log_cb(msg):
                    self.update_queue.put(("log", msg))
                
                start_t = time.time()
                merged = merge_subtitle_items_gemini(self.import_items, api_key, proxy=proxy_str, logger_func=log_cb)
                latency = time.time() - start_t
                
                if proxy_str:
                    try:
                        self.proxy_manager.report_success(proxy_str, latency)
                    except Exception:
                        pass
                
                if not merged:
                    self.update_queue.put(("log", "Lỗi: Không nhận được dữ liệu hợp lệ từ Gemini AI."))
                    self.root.after(0, lambda: messagebox.showerror("Lỗi", "Không nhận được kết quả hợp lệ từ Gemini AI. Vui lòng kiểm tra lại API Key hoặc mạng.", parent=self.root))
                    return
                    
                def on_success():
                    msg = f"Đã khôi phục bằng Gemini AI: Gộp {len(self.import_items)} dòng thành {len(merged)} câu hoàn chỉnh.\n\n" \
                          f"Cập nhật danh sách mới?"
                    if messagebox.askokcancel("Định dạng câu AI", msg, parent=self.root):
                        self.update_import_list_with_merged(merged)
                        
                self.root.after(0, on_success)
                
            except Exception as e:
                print(f"Gemini restoration thread error: {e}")
                err_msg = str(e)
                if proxy_str:
                    try:
                        self.proxy_manager.report_failure(proxy_str)
                    except Exception:
                        pass
                
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    friendly_err = "Đã vượt quá giới hạn cuộc gọi (Rate Limit 429) của API Gemini miễn phí. Vui lòng chờ 1 phút hoặc đổi khóa khác."
                elif "400" in err_msg or "API_KEY_INVALID" in err_msg:
                    friendly_err = "Khóa API Gemini không chính xác hoặc không hợp lệ. Vui lòng kiểm tra lại."
                else:
                    friendly_err = f"Lỗi gọi API Gemini: {err_msg}"
                    
                self.update_queue.put(("log", f"Lỗi khôi phục phụ đề AI: {friendly_err}"))
                self.root.after(0, lambda: messagebox.showerror("Lỗi Gemini AI", friendly_err, parent=self.root))
                
        threading.Thread(target=bg_thread, daemon=True).start()

    # Automatically generate SRT silently when join is successful
    def generate_srt_file_silent(self):
        if not self.import_items:
            return None
            
        save_path = os.path.abspath(os.path.join(self.output_dir, f"{self.get_base_filename()}_tts.srt"))
        done_items = [i for i in self.import_items if i["status"] == "Done"]
        if not done_items:
            return None
            
        srt_items = []
        for item in done_items:
            start_t = item.get("joined_start")
            end_t = item.get("joined_end")
            
            if start_t is not None and end_t is not None:
                srt_items.append({
                    "index": len(srt_items) + 1,
                    "start": format_srt_time(start_t),
                    "end": format_srt_time(end_t),
                    "text": item["text"]
                })
                
        if not srt_items:
            # Fallback if no joined timings are calculated yet
            current_time = 0.0
            gap = 0.2
            for item in done_items:
                duration = item.get("duration", 0.0)
                start_str = format_srt_time(current_time)
                current_time += duration
                end_str = format_srt_time(current_time)
                current_time += gap
                srt_items.append({
                    "index": len(srt_items) + 1,
                    "start": start_str,
                    "end": end_str,
                    "text": item["text"]
                })
            
        try:
            write_srt_file(srt_items, save_path)
            return save_path
        except Exception as e:
            print(f"Error generating silent SRT: {e}")
            return None

    def trim_audio_silence(self, file_path):
        """Trim leading and trailing silence of an audio file using FFmpeg."""
        if not file_path or not os.path.exists(file_path):
            return
            
        temp_trimmed = file_path + ".trimmed.mp3"
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            creation_flags = 0x08000000 if sys.platform == "win32" else 0
            
            # Using the reverse-trim-reverse method to trim both ends reliably.
            # We use a threshold of -50dB which is very safe for high-quality TTS voices.
            cmd = [
                ffmpeg_path,
                "-y",
                "-i", file_path,
                "-af", "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-50dB,areverse",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                temp_trimmed
            ]
            
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            if res.returncode == 0 and os.path.exists(temp_trimmed) and os.path.getsize(temp_trimmed) > 0:
                os.remove(file_path)
                os.rename(temp_trimmed, file_path)
            else:
                if os.path.exists(temp_trimmed):
                    os.remove(temp_trimmed)
        except Exception as e:
            print(f"Error trimming audio silence: {e}")
            if os.path.exists(temp_trimmed):
                try:
                    os.remove(temp_trimmed)
                except Exception:
                    pass

    def get_audio_properties(self, file_path):
        """Get sample rate and channel count of an audio file using FFmpeg."""
        sample_rate = 24000
        channels = "mono"
        
        if not file_path or not os.path.exists(file_path):
            return sample_rate, channels
            
        try:
            import re
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [ffmpeg_path, '-i', file_path]
            creation_flags = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
            output = result.stderr
            
            # Search for Audio stream info: e.g., "Audio: mp3, 24000 Hz, mono, fltp"
            match = re.search(r"Audio:.*?, (\d+) Hz, ([^,]+)", output)
            if match:
                sample_rate = int(match.group(1))
                chan_str = match.group(2).strip().lower()
                if "stereo" in chan_str:
                    channels = "stereo"
                elif "mono" in chan_str:
                    channels = "mono"
        except Exception as e:
            print(f"Error getting audio properties: {e}")
            
        return sample_rate, channels

    # Joining audio files
    # Joining audio files
    def join_audio_files(self):
        done_items = [i for i in self.import_items if i["status"] == "Done" and i["output_path"]]
        if not done_items:
            messagebox.showwarning("Ghép MP3", "Không có file âm thanh nào hoàn thành để ghép nối!")
            return
            
        save_path = os.path.abspath(os.path.join(self.output_dir, f"{self.get_base_filename()}_joined.mp3"))
            
        self.lbl_status_log.configure(text="Đang thực hiện ghép nối các file MP3...")
        file_paths = [item["output_path"] for item in done_items]
        
        # Read joining configurations from GUI
        align_timeline = self.var_align_timeline.get()
        try:
            max_silence_gap = float(self.entry_max_silence.get())
        except ValueError:
            max_silence_gap = 0.30
        try:
            default_sentence_pause = float(self.entry_sentence_pause.get())
        except ValueError:
            default_sentence_pause = 0.15
            
        # Run in a background thread to prevent UI freezing
        def run_join():
            try:
                # We will prepare a list of files to join
                joined_file_paths = []
                temp_silences = []
                temp_sped_up_files = []
                
                # Check if we have valid start timestamps from SRT
                has_timestamps = any(item.get("start") for item in done_items)
                
                # Detect original audio parameters from the first segment
                sample_rate = 24000
                channels = "mono"
                for item in done_items:
                    f_path = item.get("output_path")
                    if f_path and os.path.exists(f_path):
                        sample_rate, channels = self.get_audio_properties(f_path)
                        break
                
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                creation_flags = 0x08000000 if sys.platform == "win32" else 0
                
                if has_timestamps:
                    self.update_queue.put(("log", "Đang tính toán khớp timeline và chèn khoảng lặng..."))
                    from text_processor import srt_time_to_seconds
                    
                    # First item start time
                    first_start = srt_time_to_seconds(done_items[0]["start"])
                    current_time = first_start
                    
                    # If first starts > 0, insert silence at beginning
                    if first_start > 0:
                        temp_silence = os.path.join(self.output_dir, f"temp_silence_start.mp3")
                        ac_count = "2" if channels == "stereo" else "1"
                        cmd = [
                            ffmpeg_path, "-y",
                            "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:channel_layout={channels}",
                            "-t", f"{first_start:.3f}",
                            "-c:a", "libmp3lame", "-ar", str(sample_rate), "-ac", ac_count, "-q:a", "2",
                            temp_silence
                        ]
                        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                        if os.path.exists(temp_silence):
                            joined_file_paths.append(temp_silence)
                            temp_silences.append(temp_silence)
                    
                    for idx, item in enumerate(done_items):
                        start_time = srt_time_to_seconds(item["start"])
                        end_time = srt_time_to_seconds(item["end"])
                        orig_dur = end_time - start_time
                        actual_dur = item.get("duration", 0.0)
                        
                        # Speed factor
                        speed_factor = 1.0
                        if orig_dur > 0:
                            ratio = actual_dur / orig_dur
                            if ratio > 1.02: # Allow 2% tolerance
                                speed_factor = min(ratio, 1.35)
                                
                        final_path = item["output_path"]
                        final_dur = actual_dur
                        
                        if speed_factor > 1.0:
                            temp_sped = os.path.join(self.output_dir, f"temp_speed_{item['id']}.mp3")
                            ac_count = "2" if channels == "stereo" else "1"
                            cmd = [
                                ffmpeg_path, "-y",
                                "-i", item["output_path"],
                                "-filter:a", f"atempo={speed_factor:.3f}",
                                "-c:a", "libmp3lame", "-ar", str(sample_rate), "-ac", ac_count, "-q:a", "2",
                                temp_sped
                            ]
                            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                            if os.path.exists(temp_sped):
                                final_path = temp_sped
                                temp_sped_up_files.append(temp_sped)
                                final_dur = actual_dur / speed_factor
                                
                        # Save the final duration in the item for the SRT generator
                        item["joined_duration"] = final_dur
                        
                        # Calculate gap to insert before this item (if not the first item)
                        if idx > 0:
                            prev_item = done_items[idx - 1]
                            prev_text = prev_item["text"].strip()
                            curr_text = item["text"].strip()
                            prev_orig_end = srt_time_to_seconds(prev_item["end"])
                            original_gap = start_time - prev_orig_end
                            if original_gap < 0:
                                original_gap = 0.0
                                
                            # Punctuation/Context aware checks
                            # Rule 1: Check if prev ends with sentence punctuation (. ! ? ...)
                            import re
                            
                            # Clean text for context checks (strip HTML tags and sound annotations)
                            def clean_sub_text(t):
                                if not t:
                                    return ""
                                t = re.sub(r'</?[^>]+(>|$)', '', t)
                                t = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', t)
                                return t.strip()
                                
                            clean_prev = clean_sub_text(prev_text)
                            clean_curr = clean_sub_text(curr_text)
                            
                            ends_with_sentence_ender = False
                            if clean_prev:
                                if re.search(r'[.!?](\"|\'|\)|\)|\]|\})*$', clean_prev) or clean_prev.endswith('...'):
                                    ends_with_sentence_ender = True
                                    
                            # Rule 2: Check if next starts with a lowercase letter
                            starts_with_lowercase = False
                            if clean_curr:
                                match = re.search(r'\w', clean_curr)
                                if match:
                                    if match.group(0).islower():
                                        starts_with_lowercase = True
                                        
                            # Rule 3: Check if prev ends with mild punctuation (, : ; -)
                            ends_with_mild_punctuation = False
                            if clean_prev and not ends_with_sentence_ender:
                                if clean_prev[-1] in [',', ':', ';', '-']:
                                    ends_with_mild_punctuation = True
                                    
                            is_continuation = False
                            if not ends_with_sentence_ender:
                                if starts_with_lowercase:
                                    is_continuation = True
                                elif original_gap <= 0.1:
                                    is_continuation = True
                                    
                            if is_continuation:
                                target_pause = 0.0
                            elif ends_with_mild_punctuation:
                                target_pause = 0.05
                            else:
                                target_pause = default_sentence_pause
                                
                            # Calculate silence gap duration
                            silence_dur = 0.0
                            if align_timeline:
                                diff = start_time - current_time
                                silence_dur = max(0.0, diff)
                            else:
                                # Continuous narration
                                if original_gap <= 0.1:
                                    silence_dur = target_pause
                                else:
                                    silence_dur = min(original_gap, max_silence_gap)
                                    
                            if silence_dur > 0:
                                temp_silence = os.path.join(self.output_dir, f"temp_silence_{item['id']}.mp3")
                                ac_count = "2" if channels == "stereo" else "1"
                                cmd = [
                                    ffmpeg_path, "-y",
                                    "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:channel_layout={channels}",
                                    "-t", f"{silence_dur:.3f}",
                                    "-c:a", "libmp3lame", "-ar", str(sample_rate), "-ac", ac_count, "-q:a", "2",
                                    temp_silence
                                ]
                                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                                if os.path.exists(temp_silence):
                                    joined_file_paths.append(temp_silence)
                                    temp_silences.append(temp_silence)
                                    current_time += silence_dur
                                    
                        # Save actual joined start/end for the SRT generator
                        item["joined_start"] = current_time
                        joined_file_paths.append(final_path)
                        current_time += final_dur
                        item["joined_end"] = current_time
                        
                    # Pad silence at the end if the last item(s) failed or video is longer
                    if align_timeline and self.import_items:
                        last_item = self.import_items[-1]
                        from text_processor import srt_time_to_seconds
                        last_end_time = srt_time_to_seconds(last_item["end"])
                        if current_time < last_end_time:
                            silence_dur = last_end_time - current_time
                            temp_silence = os.path.join(self.output_dir, f"temp_silence_end.mp3")
                            ac_count = "2" if channels == "stereo" else "1"
                            cmd = [
                                ffmpeg_path, "-y",
                                "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:channel_layout={channels}",
                                "-t", f"{silence_dur:.3f}",
                                "-c:a", "libmp3lame", "-ar", str(sample_rate), "-ac", ac_count, "-q:a", "2",
                                temp_silence
                            ]
                            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                            if os.path.exists(temp_silence):
                                joined_file_paths.append(temp_silence)
                                temp_silences.append(temp_silence)
                                current_time = last_end_time
                else:
                    # TXT mode (no timestamps)
                    current_time = 0.0
                    for idx, item in enumerate(done_items):
                        actual_dur = item.get("duration", 0.0)
                        item["joined_duration"] = actual_dur
                        
                        if idx > 0 and default_sentence_pause > 0:
                            # Context-aware pause check for TXT mode too
                            prev_item = done_items[idx - 1]
                            prev_text = prev_item["text"].strip()
                            curr_text = item["text"].strip()
                            
                            import re
                            
                            # Clean text for context checks (strip HTML tags and sound annotations)
                            def clean_sub_text(t):
                                if not t:
                                    return ""
                                t = re.sub(r'</?[^>]+(>|$)', '', t)
                                t = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', t)
                                return t.strip()
                                
                            clean_prev = clean_sub_text(prev_text)
                            clean_curr = clean_sub_text(curr_text)
                            
                            ends_with_sentence_ender = False
                            if clean_prev:
                                if re.search(r'[.!?](\"|\'|\)|\)|\]|\})*$', clean_prev) or clean_prev.endswith('...'):
                                    ends_with_sentence_ender = True
                            starts_with_lowercase = False
                            if clean_curr:
                                match = re.search(r'\w', clean_curr)
                                if match:
                                    if match.group(0).islower():
                                        starts_with_lowercase = True
                            ends_with_mild_punctuation = False
                            if clean_prev and not ends_with_sentence_ender:
                                if clean_prev[-1] in [',', ':', ';', '-']:
                                    ends_with_mild_punctuation = True
                                    
                            is_continuation = False
                            if not ends_with_sentence_ender:
                                if starts_with_lowercase:
                                    is_continuation = True
                                    
                            if is_continuation:
                                target_pause = 0.0
                            elif ends_with_mild_punctuation:
                                target_pause = 0.05
                            else:
                                target_pause = default_sentence_pause
                                
                            if target_pause > 0:
                                temp_silence = os.path.join(self.output_dir, f"temp_silence_{item['id']}.mp3")
                                ac_count = "2" if channels == "stereo" else "1"
                                cmd = [
                                    ffmpeg_path, "-y",
                                    "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:channel_layout={channels}",
                                    "-t", f"{target_pause:.3f}",
                                    "-c:a", "libmp3lame", "-ar", str(sample_rate), "-ac", ac_count, "-q:a", "2",
                                    temp_silence
                                ]
                                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                                if os.path.exists(temp_silence):
                                    joined_file_paths.append(temp_silence)
                                    temp_silences.append(temp_silence)
                                    current_time += target_pause
                                    
                        item["joined_start"] = current_time
                        joined_file_paths.append(item["output_path"])
                        current_time += actual_dur
                        item["joined_end"] = current_time
                        
                # Merge using the standard concat demuxer
                from audio_processor import join_mp3_files
                join_mp3_files(joined_file_paths, save_path)
                
                # Clean up temporary silence files
                for ts in temp_silences:
                    if os.path.exists(ts):
                        try:
                            os.remove(ts)
                        except Exception:
                            pass
                            
                # Clean up temporary speedup files
                for ts in temp_sped_up_files:
                    if os.path.exists(ts):
                        try:
                            os.remove(ts)
                        except Exception:
                            pass
                            
                # Auto-generate SRT file silently
                srt_path = self.generate_srt_file_silent()
                
                # Delete individual audio files if join was successful
                deleted_count = 0
                for item in done_items:
                    file_p = item.get("output_path")
                    if file_p and os.path.exists(file_p):
                        try:
                            os.remove(file_p)
                            deleted_count += 1
                        except Exception as delete_error:
                            print(f"Error deleting temporary file {file_p}: {delete_error}")
                
                msg_success = f"Ghép nối thành công các file MP3!\nLưu tại: {save_path}"
                if srt_path:
                    msg_success += f"\nĐã tạo phụ đề tại: {srt_path}"
                if deleted_count > 0:
                    msg_success += f"\nĐã xóa {deleted_count} file âm thanh rời."
                    
                self.update_queue.put(("log", f"Đã ghép nối thành công tại: {save_path}"))
                self.root.after(0, lambda: messagebox.showinfo("Thành công", msg_success))
            except Exception as e:
                self.update_queue.put(("log", f"Lỗi ghép nối: {e}"))
                self.root.after(0, lambda: messagebox.showerror("Lỗi ghép nối", f"Có lỗi xảy ra: {e}"))
                
        threading.Thread(target=run_join).start()

    # --- Triển khai các tính năng VIP & Proxy ---

    def load_elevenlabs_keys(self):
        keys_file = "elevenlabs_keys.txt"
        self.elevenlabs_keys = []
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            self.elevenlabs_keys.append(line)
            except Exception as e:
                print(f"Error reading {keys_file}: {e}")
        self.current_key_idx = 0

    def get_active_api_key(self):
        with self.key_lock:
            if not self.elevenlabs_keys:
                return None
            if self.current_key_idx >= len(self.elevenlabs_keys):
                self.current_key_idx = 0
            return self.elevenlabs_keys[self.current_key_idx]
            
    def rotate_api_key(self):
        with self.key_lock:
            if not self.elevenlabs_keys:
                return False
            self.current_key_idx += 1
            if self.current_key_idx >= len(self.elevenlabs_keys):
                self.current_key_idx = 0
                return False
            return True

    def open_keys_pool(self):
        pool_win = tk.Toplevel(self.root)
        pool_win.title("ElevenLabs API Keys Pool Manager")
        pool_win.geometry("500x400")
        pool_win.resizable(False, False)
        pool_win.grab_set()
        
        ttk.Label(pool_win, text="ElevenLabs API Keys Pool", font=("Segoe UI", 12, "bold")).pack(pady=10)
        ttk.Label(pool_win, text="Mỗi dòng nhập một API Key. Các dòng bắt đầu bằng '#' sẽ bị bỏ qua.", font=("Segoe UI", 9)).pack(pady=2)
        
        txt_keys = tk.Text(pool_win, width=55, height=12, font=("Courier New", 9))
        txt_keys.pack(pady=10, padx=15)
        
        keys_file = "elevenlabs_keys.txt"
        existing_content = ""
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            except Exception as e:
                existing_content = f"# Error reading file: {e}"
        else:
            existing_content = "# Dan ElevenLabs API Keys cua ban o day\n# Moi dong 1 key\n"
            
        txt_keys.insert(tk.END, existing_content)
        
        lbl_status = ttk.Label(pool_win, text=f"Đang có {len(self.elevenlabs_keys)} keys hoạt động trong Pool.", foreground="#60a5fa")
        lbl_status.pack(pady=5)
        
        def save_keys():
            content = txt_keys.get("1.0", tk.END).strip()
            try:
                with open(keys_file, "w", encoding="utf-8") as f:
                    f.write(content)
                self.load_elevenlabs_keys()
                lbl_status.configure(text=f"Đã lưu! Đang có {len(self.elevenlabs_keys)} keys hoạt động trong Pool.")
                messagebox.showinfo("Keys Pool", "Đã cập nhật danh sách ElevenLabs API Keys thành công!")
                pool_win.destroy()
            except Exception as e:
                messagebox.showerror("Keys Pool", f"Lỗi ghi file: {e}")
                
        btn_frame = ttk.Frame(pool_win)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="💾 Lưu Keys", command=save_keys, width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Hủy Bỏ", command=pool_win.destroy, width=12).pack(side=tk.LEFT, padx=5)
        
        self.apply_dark_theme(pool_win)

    def on_service_changed(self, event=None):
        service = self.cb_service.get()
        
        # Auto-configure preferred proxy protocol based on service
        pref_protocol = "SOCKS5" if service == "Edge-TTS" else "HTTP"
        self.proxy_manager.set_replenish(self.proxy_manager.replenish_enabled, pref_protocol)
        if self.proxy_dashboard_open and hasattr(self, "cb_fetch_protocol"):
            try:
                self.cb_fetch_protocol.set(pref_protocol)
            except Exception:
                pass
                
        if service == "Edge-TTS":
            self.cb_model.configure(values=["tts-1", "tts-1-hd", "gpt-4o-mini-tts"])
            self.cb_model.set("tts-1")
            if hasattr(self, "all_voices_list") and self.all_voices_list:
                self.cb_voice.configure(values=self.all_voices_list)
                if "vi-VN-HoaiMyNeural" in self.all_voices_list:
                    self.cb_voice.set("vi-VN-HoaiMyNeural")
                else:
                    self.cb_voice.set(self.all_voices_list[0])
        else:
            self.cb_model.configure(values=["eleven_multilingual_v2", "eleven_flash_v2", "eleven_monolingual_v1"])
            self.cb_model.set("eleven_multilingual_v2")
            
            el_voices = []
            api_key = self.get_active_api_key()
            if api_key:
                try:
                    url = "https://api.elevenlabs.io/v1/voices"
                    headers = {"xi-api-key": api_key}
                    res = requests.get(url, headers=headers, timeout=5)
                    if res.status_code == 200:
                        el_voices = [f"{v['name']} ({v['voice_id']})" for v in res.json().get("voices", [])]
                except Exception:
                    pass
            
            if not el_voices:
                el_voices = [
                    "Rachel (21m00Tcm4TlvDq8ikWAM)",
                    "Drew (29vD33N1CtxCmqQRPOHJ)",
                    "Clyde (2EiwXtPIZ58qiFCDh9vv)",
                    "Paul (5Q0t7uMcZetaP26tyZ7c)",
                    "Nicole (piTKgcLEGmPEeZsZgnsD)",
                    "Adam (pNInz6obpgfrhhF21wNZ)",
                    "Antoni (ErXwobaYiN019PkySvjV)",
                    "Bella (EXAVITQu4vr4xnSDxMaL)",
                    "Charlie (IKne3meq5aSn9XLyUdCD)",
                    "Dom (AZnzlk1XvdvUeBnXmlld)",
                    "Ellie (MF3mGyEYCl7XYWbV9VbO)",
                    "Josh (TxGEqn7nUa5To4PfPP3Y)"
                ]
            self.cb_voice.configure(values=el_voices)
            self.cb_voice.set(el_voices[0])

    def open_proxy_manager_dashboard(self):
        if self.proxy_dashboard_open:
            if hasattr(self, "proxy_dashboard_win") and self.proxy_dashboard_win.winfo_exists():
                self.proxy_dashboard_win.lift()
                return
        
        self.proxy_dashboard_open = True
        dashboard = tk.Toplevel(self.root)
        self.proxy_dashboard_win = dashboard
        dashboard.title("Smart Proxy Pool Manager")
        dashboard.geometry("820x520")
        dashboard.minsize(750, 400)
        
        def on_close_dashboard():
            self.proxy_dashboard_open = False
            dashboard.destroy()
            
        dashboard.protocol("WM_DELETE_WINDOW", on_close_dashboard)
        
        # Title
        title_frame = ttk.Frame(dashboard, padding=10)
        title_frame.pack(fill=tk.X)
        ttk.Label(title_frame, text="Quản Lý Pool Proxy Tự Động", font=("Segoe UI", 12, "bold"), foreground="#10b981").pack(side=tk.LEFT)
        
        # Control row
        ctrl_frame = ttk.LabelFrame(dashboard, text="Tải Proxy Miễn Phí", padding=10)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(ctrl_frame, text="Giao thức:").pack(side=tk.LEFT, padx=5)
        
        # Set default fetch protocol based on active service
        service = self.cb_service.get()
        default_proto = "SOCKS5" if service == "Edge-TTS" else "HTTP"
        
        self.cb_fetch_protocol = ttk.Combobox(ctrl_frame, values=["HTTP", "SOCKS4", "SOCKS5"], width=8, state="readonly")
        self.cb_fetch_protocol.pack(side=tk.LEFT, padx=5)
        self.cb_fetch_protocol.set(default_proto)
        
        self.var_auto_replenish = tk.BooleanVar(value=self.proxy_manager.replenish_enabled)
        
        def toggle_replenish():
            proto = self.cb_fetch_protocol.get()
            self.proxy_manager.set_replenish(self.var_auto_replenish.get(), proto)
            self.lbl_status_log.configure(text=f"Auto-Replenish: {'BẬT' if self.var_auto_replenish.get() else 'TẮT'} ({proto})")
            
        chk_replenish = ttk.Checkbutton(ctrl_frame, text="Tự động bù proxy ngầm (<15 live)", variable=self.var_auto_replenish, command=toggle_replenish)
        chk_replenish.pack(side=tk.LEFT, padx=15)
        
        def fetch_free_proxies():
            proto = self.cb_fetch_protocol.get()
            self.lbl_status_log.configure(text=f"Đang bắt đầu tải danh sách Free Proxy {proto}...")
            self.proxy_manager.load_free_proxies(proto)
            
        btn_fetch = ttk.Button(ctrl_frame, text="⚡ Tải Free Proxy", width=16, style="Start.TButton", command=fetch_free_proxies)
        btn_fetch.pack(side=tk.RIGHT, padx=5)
        
        # Table & Buttons Layout
        main_layout = ttk.Frame(dashboard, padding=10)
        main_layout.pack(fill=tk.BOTH, expand=True)
        
        # Left side: Table
        table_frame = ttk.Frame(main_layout)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.tree_proxies = ttk.Treeview(table_frame, columns=("no", "url", "proto", "latency", "ok", "fail", "status", "source"), show="headings", selectmode="browse")
        
        # Columns definitions
        self.tree_proxies.heading("no", text="No", anchor=tk.CENTER)
        self.tree_proxies.heading("url", text="Proxy Address")
        self.tree_proxies.heading("proto", text="Type", anchor=tk.CENTER)
        self.tree_proxies.heading("latency", text="Latency", anchor=tk.CENTER)
        self.tree_proxies.heading("ok", text="OK", anchor=tk.CENTER)
        self.tree_proxies.heading("fail", text="Fail", anchor=tk.CENTER)
        self.tree_proxies.heading("status", text="Status", anchor=tk.CENTER)
        self.tree_proxies.heading("source", text="Source")
        
        self.tree_proxies.column("no", width=35, minwidth=30, stretch=tk.NO, anchor=tk.CENTER)
        self.tree_proxies.column("url", width=220, minwidth=180)
        self.tree_proxies.column("proto", width=60, minwidth=50, stretch=tk.NO, anchor=tk.CENTER)
        self.tree_proxies.column("latency", width=85, minwidth=80, stretch=tk.NO, anchor=tk.CENTER)
        self.tree_proxies.column("ok", width=45, minwidth=40, stretch=tk.NO, anchor=tk.CENTER)
        self.tree_proxies.column("fail", width=45, minwidth=40, stretch=tk.NO, anchor=tk.CENTER)
        self.tree_proxies.column("status", width=95, minwidth=80, stretch=tk.NO, anchor=tk.CENTER)
        self.tree_proxies.column("source", width=110, minwidth=90)
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_proxies.yview)
        self.tree_proxies.configure(yscrollcommand=vsb.set)
        
        self.tree_proxies.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        # Right side: Control buttons
        side_btn_frame = ttk.Frame(main_layout, width=120)
        side_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        def run_test_all():
            self.lbl_status_log.configure(text="Bắt đầu đo latency tất cả proxy...")
            threading.Thread(target=self.proxy_manager.validate_all, daemon=True).start()
            
        def run_import_file():
            proto = self.cb_fetch_protocol.get()
            path = filedialog.askopenfilename(title="Chọn file proxy (.txt)", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
            if path:
                count = self.proxy_manager.import_from_file(path, protocol=proto)
                messagebox.showinfo("Import File", f"Đã nhập thành công {count} proxy từ file.")
                
        def run_export_live():
            path = filedialog.asksaveasfilename(title="Lưu live proxies", defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
            if path:
                count = self.proxy_manager.export_live(path)
                messagebox.showinfo("Export Live", f"Đã xuất thành công {count} live proxy ra file.")
                
        def run_clear_pool():
            if messagebox.askyesno("Clear Pool", "Bạn có chắc chắn muốn xóa sạch proxy hiện có?"):
                self.proxy_manager.clear()
                
        ttk.Button(side_btn_frame, text="⚡ Test Latency", width=14, command=run_test_all).pack(pady=5, fill=tk.X)
        ttk.Button(side_btn_frame, text="📋 Paste List", width=14, command=self.open_proxy_paste_dialog).pack(pady=5, fill=tk.X)
        ttk.Button(side_btn_frame, text="📂 Import File", width=14, command=run_import_file).pack(pady=5, fill=tk.X)
        ttk.Button(side_btn_frame, text="📤 Export Live", width=14, command=run_export_live).pack(pady=5, fill=tk.X)
        ttk.Button(side_btn_frame, text="🗑️ Clear Pool", width=14, command=run_clear_pool).pack(pady=5, fill=tk.X)
        ttk.Button(side_btn_frame, text="❌ Đóng", width=14, command=on_close_dashboard).pack(side=tk.BOTTOM, pady=5, fill=tk.X)
        
        # Load initial table data
        self.refresh_proxy_dashboard_table()
        
        self.apply_dark_theme(dashboard)
        
    def refresh_proxy_dashboard_table(self):
        if not self.proxy_dashboard_open or not hasattr(self, "tree_proxies"):
            return
            
        selected_item = self.tree_proxies.selection()
        selected_url = None
        if selected_item:
            selected_url = self.tree_proxies.item(selected_item[0], "values")[1]
            
        # Clear existing
        for item in self.tree_proxies.get_children():
            self.tree_proxies.delete(item)
            
        with self.proxy_manager.lock:
            proxies = [p.to_dict() for p in self.proxy_manager.all_proxies]
            
        # Sort by status (Active first) and then latency
        proxies.sort(key=lambda x: (0 if x["status"] == "Active" else 1 if x["status"] == "Testing" else 2, x["latency"]))
        
        restore_item_id = None
        for idx, p in enumerate(proxies):
            lat_str = f"{p['latency']*1000:.0f} ms" if p['latency'] < 999.0 else "Timeout ❌"
            status_symbol = p['status']
            if status_symbol == "Active":
                status_symbol = "Active (Live) "
            elif status_symbol == "Failed":
                status_symbol = "Failed ❌"
            elif status_symbol == "Testing":
                status_symbol = "Testing "
                
            item_id = self.tree_proxies.insert("", "end", values=(
                idx + 1,
                p["url"],
                p["protocol"].upper(),
                lat_str,
                p["success"],
                p["fail"],
                status_symbol,
                p["source"]
            ))
            
            if selected_url and p["url"] == selected_url:
                restore_item_id = item_id
                
        if restore_item_id:
            self.tree_proxies.selection_set(restore_item_id)
            self.tree_proxies.see(restore_item_id)

    def open_proxy_paste_dialog(self):
        paste_win = tk.Toplevel(self.root)
        paste_win.title("Dán danh sách Proxy")
        paste_win.geometry("450x330")
        paste_win.grab_set()
        
        ttk.Label(paste_win, text="Dán danh sách proxy vào đây (mỗi dòng một proxy):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 5))
        ttk.Label(paste_win, text="Định dạng: ip:port hoặc protocol://ip:port hoặc user:pass@ip:port", font=("Segoe UI", 8, "italic"), foreground="#a1a1aa").pack(anchor=tk.W, padx=15, pady=(0, 5))
        
        txt_frame = ttk.Frame(paste_win)
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        txt_area = tk.Text(txt_frame, width=50, height=10, font=("Consolas", 9))
        txt_area.grid(row=0, column=0, sticky="nsew")
        
        vsb = ttk.Scrollbar(txt_frame, orient="vertical", command=txt_area.yview)
        txt_area.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        
        txt_frame.grid_columnconfigure(0, weight=1)
        txt_frame.grid_rowconfigure(0, weight=1)
        
        proto_frame = ttk.Frame(paste_win)
        proto_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Label(proto_frame, text="Giao thức mặc định nếu thiếu:").pack(side=tk.LEFT, padx=5)
        
        service = self.cb_service.get()
        default_proto = "SOCKS5" if service == "Edge-TTS" else "HTTP"
        
        cb_import_proto = ttk.Combobox(proto_frame, values=["HTTP", "SOCKS4", "SOCKS5"], width=8, state="readonly")
        cb_import_proto.pack(side=tk.LEFT, padx=5)
        cb_import_proto.set(default_proto)
        
        def do_import():
            text = txt_area.get("1.0", tk.END).strip()
            if not text:
                messagebox.showwarning("Nhập proxy", "Vui lòng dán danh sách proxy trước!")
                return
            proto = cb_import_proto.get()
            count = self.proxy_manager.import_from_text(text, protocol=proto)
            messagebox.showinfo("Nhập proxy", f"Đã phát hiện và bắt đầu kiểm tra {count} proxy.")
            paste_win.destroy()
            
        btn_frame = ttk.Frame(paste_win)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="📥 Nhập Proxy", command=do_import, width=15, style="Start.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Hủy Bỏ", command=paste_win.destroy, width=10).pack(side=tk.LEFT, padx=5)
        
        self.apply_dark_theme(paste_win)

    def open_youtube_downloader(self):
        yt_win = tk.Toplevel(self.root)
        yt_win.title("Tải Phụ Đề Từ YouTube")
        yt_win.geometry("500x280")
        yt_win.resizable(False, False)
        yt_win.grab_set()
        
        # Center the window relative to the root
        yt_win.update_idletasks()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        w = yt_win.winfo_width()
        h = yt_win.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        yt_win.geometry(f"+{x}+{y}")
        
        ttk.Label(yt_win, text="Tải Phụ Đề Từ YouTube", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # Input Frame
        input_frame = ttk.Frame(yt_win, padding=10)
        input_frame.pack(fill=tk.X, padx=15)
        
        ttk.Label(input_frame, text="URL hoặc ID Video:").pack(anchor=tk.W, pady=2)
        ent_url = ttk.Entry(input_frame, width=55)
        ent_url.pack(fill=tk.X, pady=5)
        ent_url.focus_set()
        
        # Language Select Frame
        lang_frame = ttk.Frame(yt_win, padding=10)
        lang_frame.pack(fill=tk.X, padx=15)
        
        ttk.Label(lang_frame, text="Ngôn ngữ phụ đề:").pack(side=tk.LEFT, padx=(0, 10))
        cb_lang = ttk.Combobox(lang_frame, state="disabled", width=35)
        cb_lang.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Status Label
        lbl_status = ttk.Label(yt_win, text="Nhập URL/ID và nhấn Check để tải danh sách phụ đề.", foreground="#a1a1aa", font=("Segoe UI", 9, "italic"))
        lbl_status.pack(pady=5)
        
        # Store transcript list
        transcripts_data = {}  # desc -> t_obj or (t_obj, target_lang)
        download_state = {"last_path": None}
        
        def extract_youtube_video_id(url_or_id):
            import re
            url_or_id = url_or_id.strip()
            if len(url_or_id) == 11:
                return url_or_id
            patterns = [
                r'(?:v=|\/v\/|embed\/|shorts\/|youtu\.be\/|\/embed\/|\/v\/|watch\?v=|\?v=)([^#\&\?]{11})',
                r'youtu.be\/([^#\&\?]{11})'
            ]
            for pattern in patterns:
                match = re.search(pattern, url_or_id)
                if match:
                    return match.group(1)
            return None
            
        def fetch_languages():
            input_val = ent_url.get().strip()
            video_id = extract_youtube_video_id(input_val)
            if not video_id:
                messagebox.showerror("Lỗi", "Đường dẫn URL hoặc Video ID không hợp lệ!", parent=yt_win)
                return
                
            lbl_status.configure(text="Đang kết nối YouTube...", foreground="#fbbf24")
            yt_win.update()
            
            def run_fetch():
                from youtube_transcript_api import YouTubeTranscriptApi
                import requests
                import time
                
                max_retries = 3
                last_err = None
                
                for attempt in range(max_retries):
                    try:
                        session = requests.Session()
                        session.headers.update({"Connection": "close"})
                        
                        if self.var_proxy_enabled.get():
                            live_p = self.proxy_manager.get_live_proxy()
                            if live_p:
                                session.proxies.update({
                                    "http": live_p.url,
                                    "https": live_p.url
                                })
                                
                        api = YouTubeTranscriptApi(http_client=session)
                        transcript_list = api.list(video_id)
                        
                        transcripts_data.clear()
                        combo_vals = []
                        
                        for t in transcript_list:
                            desc = f"{t.language} ({t.language_code})"
                            if t.is_generated:
                                desc += " [Tự động]"
                            transcripts_data[desc] = t
                            combo_vals.append(desc)
                            
                            # Add Vietnamese translation option if not already Vietnamese
                            if t.is_translatable and t.language_code != 'vi':
                                desc_vi = f"{t.language} ({t.language_code}) -> Dịch sang Tiếng Việt (vi)"
                                transcripts_data[desc_vi] = (t, 'vi')
                                combo_vals.append(desc_vi)
                                
                        if not combo_vals:
                            self.root.after(0, lambda: messagebox.showerror("Lỗi", "Không tìm thấy phụ đề nào cho video này!", parent=yt_win))
                            self.root.after(0, lambda: lbl_status.configure(text="Không có phụ đề.", foreground="#ef4444"))
                            return
                            
                        def update_combo():
                            cb_lang.configure(values=combo_vals, state="readonly")
                            cb_lang.set(combo_vals[0])
                            lbl_status.configure(text="Đã tải xong danh sách phụ đề.", foreground="#10b981")
                            btn_download.configure(state="normal")
                            
                        self.root.after(0, update_combo)
                        return
                    except Exception as e:
                        print(f"Fetch attempt {attempt + 1} failed: {e}")
                        last_err = e
                        time.sleep(0.5)
                        
                # If all retries failed
                print(f"Error fetching YouTube transcripts after {max_retries} attempts: {last_err}")
                err_msg = str(last_err)
                if "Subtitles are disabled" in err_msg:
                    msg = "Video này đã bị tắt phụ đề!"
                elif "Could not retrieve" in err_msg:
                    msg = "Không thể lấy phụ đề (bị chặn quốc gia hoặc cần Proxy)."
                else:
                    msg = f"Lỗi kết nối: {err_msg[:60]}..."
                self.root.after(0, lambda: messagebox.showerror("Lỗi YouTube", msg, parent=yt_win))
                self.root.after(0, lambda: lbl_status.configure(text="Lấy danh sách thất bại.", foreground="#ef4444"))
                    
            threading.Thread(target=run_fetch, daemon=True).start()
            
        def download_transcript():
            selected_desc = cb_lang.get()
            if not selected_desc:
                return
                
            input_val = ent_url.get().strip()
            video_id = extract_youtube_video_id(input_val)
            
            # Determine language code
            obj = transcripts_data[selected_desc]
            if isinstance(obj, tuple):
                lang_code = obj[1]
            else:
                lang_code = obj.language_code
                
            # Open save dialog on the main thread
            initial_filename = f"youtube_{video_id}_{lang_code}.srt"
            save_path = filedialog.asksaveasfilename(
                parent=yt_win,
                title="Lưu phụ đề YouTube",
                initialdir=self.output_dir,
                initialfile=initial_filename,
                defaultextension=".srt",
                filetypes=[("SRT Subtitles", "*.srt"), ("All Files", "*.*")]
            )
            
            if not save_path:
                return # User cancelled
                
            lbl_status.configure(text="Đang tải phụ đề...", foreground="#fbbf24")
            yt_win.update()
            
            def run_download():
                import requests
                import time
                import urllib.parse
                
                max_retries = 3
                last_err = None
                
                for attempt in range(max_retries):
                    try:
                        session = requests.Session()
                        session.headers.update({"Connection": "close"})
                        
                        if self.var_proxy_enabled.get():
                            live_p = self.proxy_manager.get_live_proxy()
                            if live_p:
                                session.proxies.update({
                                    "http": live_p.url,
                                    "https": live_p.url
                                })
                                
                        obj_to_fetch = transcripts_data[selected_desc]
                        is_translation = isinstance(obj_to_fetch, tuple)
                        
                        if is_translation:
                            t_obj, target_lang = obj_to_fetch
                            t_obj._http_client = session
                            fetched_data = t_obj.fetch()
                            lang_code = target_lang
                        else:
                            obj_to_fetch._http_client = session
                            fetched_data = obj_to_fetch.fetch()
                            lang_code = obj_to_fetch.language_code
                            
                        # Define batch translation helpers using the session
                        def translate_single(text, t_lang):
                            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=" + t_lang + "&dt=t&q=" + urllib.parse.quote(text)
                            try:
                                res = session.get(url, timeout=5)
                                res.raise_for_status()
                                data = res.json()
                                translated_text = ""
                                for sentence in data[0]:
                                    if sentence[0]:
                                        translated_text += sentence[0]
                                return translated_text.strip()
                            except:
                                return text

                        def translate_chunk(chunk, t_lang):
                            text_block = "\n".join(chunk)
                            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=" + t_lang + "&dt=t&q=" + urllib.parse.quote(text_block)
                            try:
                                res = session.get(url, timeout=10)
                                res.raise_for_status()
                                data = res.json()
                                translated_block = ""
                                for sentence in data[0]:
                                    if sentence[0]:
                                        translated_block += sentence[0]
                                translated_lines = [line.strip() for line in translated_block.split("\n")]
                                
                                if len(translated_lines) != len(chunk):
                                    fallback_lines = []
                                    for t in chunk:
                                        fallback_lines.append(translate_single(t, t_lang))
                                        time.sleep(0.05)
                                    return fallback_lines
                                return translated_lines
                            except Exception as e:
                                print("Translate chunk error:", e)
                                fallback_lines = []
                                for t in chunk:
                                    fallback_lines.append(translate_single(t, t_lang))
                                return fallback_lines

                        def batch_translate(texts, t_lang='vi', chunk_size=3000):
                            translated_texts = []
                            current_chunk = []
                            current_length = 0
                            
                            for text in texts:
                                if current_length + len(text) + 1 > chunk_size and current_chunk:
                                    translated_texts.extend(translate_chunk(current_chunk, t_lang))
                                    current_chunk = []
                                    current_length = 0
                                    time.sleep(0.1)
                                current_chunk.append(text)
                                current_length += len(text) + 1
                                
                            if current_chunk:
                                translated_texts.extend(translate_chunk(current_chunk, t_lang))
                            return translated_texts
                            
                        # Build SRT structure
                        srt_items = []
                        
                        if is_translation:
                            # Translate all subtitle lines to the target language
                            original_texts = [line.text for line in fetched_data]
                            translated_texts = batch_translate(original_texts, target_lang)
                            
                            for idx, line in enumerate(fetched_data):
                                start_sec = line.start
                                dur_sec = line.duration
                                end_sec = start_sec + dur_sec
                                txt = translated_texts[idx] if idx < len(translated_texts) else line.text
                                
                                srt_items.append({
                                    "index": idx + 1,
                                    "start": format_srt_time(start_sec),
                                    "end": format_srt_time(end_sec),
                                    "text": txt
                                })
                        else:
                            for idx, line in enumerate(fetched_data):
                                start_sec = line.start
                                dur_sec = line.duration
                                end_sec = start_sec + dur_sec
                                
                                srt_items.append({
                                    "index": idx + 1,
                                    "start": format_srt_time(start_sec),
                                    "end": format_srt_time(end_sec),
                                    "text": line.text
                                })
                                
                        # Save to SRT file
                        write_srt_file(srt_items, save_path)
                        
                        # Store in state
                        download_state["last_path"] = save_path
                        
                        def success_ui():
                            lbl_status.configure(text="Tải thành công! Nhấp 'Nhập Vào Bảng' để import.", foreground="#10b981")
                            btn_import.configure(state="normal")
                            messagebox.showinfo("Thành công", f"Đã tải và lưu phụ đề thành công tại:\n{save_path}", parent=yt_win)
                            
                        self.root.after(0, success_ui)
                        return
                    except Exception as e:
                        print(f"Download attempt {attempt + 1} failed: {e}")
                        last_err = e
                        time.sleep(0.5)
                        
                # If all retries failed
                print(f"Error downloading transcript after {max_retries} attempts: {last_err}")
                self.root.after(0, lambda: messagebox.showerror("Lỗi tải phụ đề", f"Không tải được phụ đề: {last_err}", parent=yt_win))
                self.root.after(0, lambda: lbl_status.configure(text="Tải phụ đề thất bại.", foreground="#ef4444"))
                
            threading.Thread(target=run_download, daemon=True).start()

        def import_transcript():
            path = download_state["last_path"]
            if not path or not os.path.exists(path):
                messagebox.showerror("Lỗi", "Không tìm thấy file phụ đề vừa tải!", parent=yt_win)
                return
            parsed = parse_srt(path)
            if parsed:
                self.add_items_to_tree(parsed, os.path.basename(path))
                self.lbl_status_log.configure(text=f"Đã nhập thành công {len(parsed)} dòng từ {os.path.basename(path)}.")
                messagebox.showinfo("Thành công", f"Đã nhập thành công {len(parsed)} dòng phụ đề vào danh sách!", parent=yt_win)
                yt_win.destroy()
            else:
                messagebox.showerror("Lỗi", "Lỗi phân tích file phụ đề!", parent=yt_win)

        btn_fetch_langs = ttk.Button(lang_frame, text="🔍 Check", width=10, command=fetch_languages)
        btn_fetch_langs.pack(side=tk.RIGHT, padx=(10, 0))
        
        btn_frame = ttk.Frame(yt_win)
        btn_frame.pack(pady=15)
        
        btn_download = ttk.Button(btn_frame, text="📥 Tải Về File Sub", state="disabled", command=download_transcript, width=16, style="Start.TButton")
        btn_download.pack(side=tk.LEFT, padx=5)
        
        btn_import = ttk.Button(btn_frame, text="🔌 Nhập Vào Bảng", state="disabled", command=import_transcript, width=16, style="Start.TButton")
        btn_import.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="❌ Hủy Bỏ", command=yt_win.destroy, width=10).pack(side=tk.LEFT, padx=5)
        
        self.apply_dark_theme(yt_win)

    def open_video_merger(self):
        merge_win = tk.Toplevel(self.root)
        merge_win.title("Auto Video & Audio Merger (FFmpeg)")
        merge_win.geometry("550x380")
        merge_win.resizable(False, False)
        merge_win.grab_set()
        
        ttk.Label(merge_win, text="Ghép nối âm thanh & phụ đề vào Video gốc", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        grid = ttk.Frame(merge_win, padding=10)
        grid.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(grid, text="Video gốc:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        ent_video = ttk.Entry(grid, width=45)
        ent_video.grid(row=0, column=1, pady=5, padx=5)
        
        def browse_video():
            path = filedialog.askopenfilename(title="Chọn Video gốc", filetypes=[("Video Files", "*.mp4;*.mkv;*.avi;*.mov"), ("All Files", "*.*")])
            if path:
                ent_video.delete(0, tk.END)
                ent_video.insert(0, path)
        ttk.Button(grid, text="🔍 Chọn", command=browse_video, width=10).grid(row=0, column=2, pady=5, padx=5)
        
        ttk.Label(grid, text="Audio MP3:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        ent_audio = ttk.Entry(grid, width=45)
        ent_audio.grid(row=1, column=1, pady=5, padx=5)
        
        default_audio = ""
        base_name = self.get_base_filename()
        joined_path = os.path.abspath(os.path.join(self.output_dir, f"{base_name}_joined.mp3"))
        if os.path.exists(joined_path):
            default_audio = joined_path
        else:
            if os.path.exists(self.output_dir):
                for file in os.listdir(self.output_dir):
                    if file.endswith(".mp3"):
                        default_audio = os.path.join(self.output_dir, file)
                        break
        if default_audio:
            ent_audio.insert(0, default_audio)
            
        def browse_audio():
            path = filedialog.askopenfilename(title="Chọn Audio MP3 để ghép", filetypes=[("Audio Files", "*.mp3"), ("All Files", "*.*")])
            if path:
                ent_audio.delete(0, tk.END)
                ent_audio.insert(0, path)
        ttk.Button(grid, text="🔍 Chọn", command=browse_audio, width=10).grid(row=1, column=2, pady=5, padx=5)
        
        ttk.Label(grid, text="Phụ đề SRT:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        ent_srt = ttk.Entry(grid, width=45)
        ent_srt.grid(row=2, column=1, pady=5, padx=5)
        
        default_srt = ""
        srt_path = os.path.abspath(os.path.join(self.output_dir, f"{base_name}_tts.srt"))
        if os.path.exists(srt_path):
            default_srt = srt_path
        else:
            if os.path.exists(self.output_dir):
                for file in os.listdir(self.output_dir):
                    if file.endswith(".srt"):
                        default_srt = os.path.join(self.output_dir, file)
                        break
        if default_srt:
            ent_srt.insert(0, default_srt)
            
        def browse_srt():
            path = filedialog.askopenfilename(title="Chọn Phụ đề SRT", filetypes=[("SRT Files", "*.srt"), ("All Files", "*.*")])
            if path:
                ent_srt.delete(0, tk.END)
                ent_srt.insert(0, path)
        ttk.Button(grid, text="🔍 Chọn", command=browse_srt, width=10).grid(row=2, column=2, pady=5, padx=5)
        
        ttk.Label(grid, text="Xử lý Audio:").grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        var_audio_mode = tk.StringVar(value="replace")
        rad_replace = ttk.Radiobutton(grid, text="Ghi đè audio gốc", variable=var_audio_mode, value="replace")
        rad_replace.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        
        rad_mix = ttk.Radiobutton(grid, text="Trộn giảm nhỏ nhạc nền (Ducking 15%)", variable=var_audio_mode, value="mix")
        rad_mix.grid(row=4, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Label(grid, text="Xử lý Subtitle:").grid(row=5, column=0, sticky=tk.W, pady=5, padx=5)
        var_sub_mode = tk.StringVar(value="hard")
        rad_sub_none = ttk.Radiobutton(grid, text="Không chèn phụ đề", variable=var_sub_mode, value="none")
        rad_sub_none.grid(row=5, column=1, sticky=tk.W, pady=5, padx=5)
        
        rad_sub_hard = ttk.Radiobutton(grid, text="Chèn cứng phụ đề vào Video (Hardsub)", variable=var_sub_mode, value="hard")
        rad_sub_hard.grid(row=6, column=1, sticky=tk.W, pady=2, padx=5)
        
        def run_ffmpeg_merge():
            v_path = ent_video.get().strip()
            a_path = ent_audio.get().strip()
            s_path = ent_srt.get().strip()
            
            if not v_path or not os.path.exists(v_path):
                messagebox.showerror("Lỗi", "Vui lòng chọn Video gốc hợp lệ!")
                return
            if not a_path or not os.path.exists(a_path):
                messagebox.showerror("Lỗi", "Vui lòng chọn Audio MP3 hợp lệ!")
                return
                
            sub_mode = var_sub_mode.get()
            if sub_mode == "hard" and (not s_path or not os.path.exists(s_path)):
                messagebox.showerror("Lỗi", "Vui lòng chọn file phụ đề SRT để chèn cứng!")
                return
                
            video_basename = os.path.splitext(os.path.basename(v_path))[0]
            out_path = os.path.abspath(os.path.join(self.output_dir, f"{video_basename}_tts.mp4"))
                
            self.lbl_status_log.configure(text="Đang bắt đầu ghép video...")
            merge_win.destroy()
            
            def merge_thread():
                try:
                    import imageio_ffmpeg
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    
                    audio_mode = var_audio_mode.get()
                    
                    creation_flags = 0x08000000 if os.name == 'nt' else 0
                    res = subprocess.run([ffmpeg_exe, "-i", v_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                    stderr_str = res.stderr.decode('utf-8', 'ignore')
                    has_audio = "Audio:" in stderr_str
                    
                    filter_complex = []
                    if audio_mode == "mix" and has_audio:
                        filter_complex.append("[0:a]volume=0.15[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=first[a]")
                    
                    video_filters = []
                    if sub_mode == "hard":
                        escaped_srt = s_path.replace("\\", "/")
                        escaped_srt = escaped_srt.replace(":", "\\:")
                        video_filters.append(f"subtitles=filename='{escaped_srt}'")
                        
                    cmd_args = [ffmpeg_exe, "-y", "-i", v_path, "-i", a_path]
                    
                    if filter_complex:
                        cmd_args.extend(["-filter_complex", ";".join(filter_complex)])
                        
                    if video_filters:
                        cmd_args.extend(["-vf", ",".join(video_filters)])
                        
                    cmd_args.extend(["-map", "0:v"])
                    
                    if filter_complex:
                        cmd_args.extend(["-map", "[a]"])
                    else:
                        cmd_args.extend(["-map", "1:a"])
                        
                    if sub_mode == "hard":
                        cmd_args.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium"])
                    else:
                        cmd_args.extend(["-c:v", "copy"])
                        
                    cmd_args.extend(["-c:a", "aac", "-shortest", out_path])
                    
                    print("Running FFmpeg command:", " ".join(cmd_args))
                    self.update_queue.put(("log", "Đang xử lý ghép Video thành phẩm (vui lòng chờ)..."))
                    
                    process = subprocess.Popen(
                        cmd_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=creation_flags
                    )
                    
                    stdout_data, stderr_data = process.communicate()
                    
                    if process.returncode == 0:
                        self.update_queue.put(("log", f"Ghép video thành công! Đầu ra: {out_path}"))
                        self.root.after(0, lambda: messagebox.showinfo("Thành công", f"Đã xuất Video thành phẩm thành công tại:\n{out_path}"))
                    else:
                        err_msg = stderr_data.decode('utf-8', 'ignore')[-500:]
                        self.update_queue.put(("log", f"Lỗi FFmpeg: {process.returncode}"))
                        self.root.after(0, lambda: messagebox.showerror("Lỗi FFmpeg", f"Ghép video thất bại:\n{err_msg}"))
                        
                except Exception as e:
                    print(f"Error during video merging: {e}")
                    self.update_queue.put(("log", f"Lỗi ghép video: {str(e)}"))
                    self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {str(e)}"))
                    
            threading.Thread(target=merge_thread, daemon=True).start()
            
        btn_frame = ttk.Frame(merge_win)
        btn_frame.pack(pady=15)
        
        ttk.Button(btn_frame, text="🎬 Bắt đầu ghép", command=run_ffmpeg_merge, width=18, style="Start.TButton").pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="❌ Hủy bỏ", command=merge_win.destroy, width=12).pack(side=tk.LEFT, padx=10)
        
        self.apply_dark_theme(merge_win)

    def get_base_filename(self):
        if self.import_items:
            first_file = self.import_items[0]["file"]
            return os.path.splitext(first_file)[0]
        return "output"



if __name__ == "__main__":
    # Fix dpi scaling on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    root = tk.Tk()
    app = TTSApp(root)
    root.mainloop()
