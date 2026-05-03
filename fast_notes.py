"""
Fast Notes - A quick-access note-taking app for Windows
With built-in Web Server for Samsung/Mobile access via WLAN
Requirements: pip install customtkinter keyboard pystray Pillow flask
"""

import customtkinter as ctk
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
import keyboard
import pystray
from PIL import Image, ImageDraw
import sys
import socket

# Flask for mobile web server
from flask import Flask, request, jsonify, render_template_string

# ─────────────────────────────────────────────
#  STORAGE LAYER
# ─────────────────────────────────────────────

NOTES_FILE = Path(os.getenv("APPDATA", ".")) / "FastNotes" / "notes.json"
WEB_PORT   = 5000


def ensure_storage():
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("[]", encoding="utf-8")


def load_notes() -> list:
    ensure_storage()
    try:
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_note(content: str, note_id=None, title=None) -> dict:
    ensure_storage()
    notes = load_notes()
    now   = datetime.now().isoformat(timespec="seconds")

    if note_id:
        for note in notes:
            if note["id"] == note_id:
                note["content"]    = content
                note["updated_at"] = now
                if title is not None:
                    note["title"] = title
                break
        saved = next((n for n in notes if n["id"] == note_id), None)
    else:
        saved = {
            "id":         datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
            "title":      None,
            "content":    content,
            "created_at": now,
            "updated_at": now,
        }
        notes.insert(0, saved)

    NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return saved


def update_note_title(note_id: str, title: str):
    notes = load_notes()
    for note in notes:
        if note["id"] == note_id:
            note["title"] = title or None
            break
    NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_note(note_id: str):
    notes = [n for n in load_notes() if n["id"] != note_id]
    NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")


def format_display_title(note: dict) -> str:
    if note.get("title"):
        return note["title"]
    try:
        dt = datetime.fromisoformat(note["created_at"])
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return note["id"]


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ─────────────────────────────────────────────
#  WEB SERVER (Flask)
# ─────────────────────────────────────────────

MOBILE_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Fast Notes</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #1e1e2e;
    color: #cdd6f4;
    min-height: 100vh;
  }
  header {
    background: #181825;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 1px solid #313244;
  }
  header h1 { font-size: 18px; font-weight: 700; color: #89b4fa; }
  header span { font-size: 12px; color: #6c7086; }

  .tabs {
    display: flex;
    background: #181825;
    border-bottom: 1px solid #313244;
  }
  .tab {
    flex: 1;
    padding: 12px;
    text-align: center;
    font-size: 13px;
    color: #6c7086;
    cursor: pointer;
    border: none;
    background: transparent;
    color: #6c7086;
    transition: all 0.2s;
  }
  .tab.active {
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
  }

  .panel { display: none; padding: 16px; }
  .panel.active { display: block; }

  /* New Note Panel */
  #new-panel textarea {
    width: 100%;
    min-height: 220px;
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 12px;
    color: #cdd6f4;
    font-size: 15px;
    padding: 14px;
    resize: vertical;
    outline: none;
    font-family: inherit;
    line-height: 1.5;
  }
  #new-panel textarea:focus { border-color: #89b4fa; }

  #new-panel input[type=text] {
    width: 100%;
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 10px;
    color: #cdd6f4;
    font-size: 14px;
    padding: 10px 14px;
    outline: none;
    margin-top: 10px;
    font-family: inherit;
  }
  #new-panel input:focus { border-color: #89b4fa; }

  .btn {
    display: block;
    width: 100%;
    margin-top: 12px;
    padding: 14px;
    border-radius: 12px;
    border: none;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  .btn:active { opacity: 0.8; }
  .btn-primary { background: #89b4fa; color: #1e1e2e; }
  .btn-danger  { background: #f38ba8; color: #1e1e2e; }

  /* Notes List */
  .note-card {
    background: #313244;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: border-color 0.2s;
  }
  .note-card:active { border-color: #89b4fa; }
  .note-title { font-size: 14px; font-weight: 600; color: #cdd6f4; margin-bottom: 4px; }
  .note-preview { font-size: 12px; color: #6c7086; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .note-date { font-size: 11px; color: #45475a; margin-top: 6px; }

  /* Edit view */
  #edit-view {
    display: none;
    position: fixed;
    inset: 0;
    background: #1e1e2e;
    z-index: 200;
    flex-direction: column;
  }
  #edit-view.open { display: flex; }
  #edit-header {
    background: #181825;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #313244;
  }
  #edit-header button {
    background: #313244;
    border: none;
    color: #cdd6f4;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
  }
  #edit-title-input {
    flex: 1;
    background: transparent;
    border: none;
    color: #89b4fa;
    font-size: 14px;
    font-weight: 600;
    outline: none;
  }
  #edit-textarea {
    flex: 1;
    background: transparent;
    border: none;
    color: #cdd6f4;
    font-size: 15px;
    padding: 16px;
    resize: none;
    outline: none;
    font-family: inherit;
    line-height: 1.6;
  }
  #edit-footer {
    padding: 12px 16px;
    background: #181825;
    border-top: 1px solid #313244;
    display: flex;
    gap: 10px;
  }
  #edit-footer button {
    flex: 1;
    padding: 12px;
    border-radius: 10px;
    border: none;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
  }
  .save-btn   { background: #89b4fa; color: #1e1e2e; }
  .delete-btn { background: #313244; color: #f38ba8; }

  .empty { text-align: center; padding: 40px 20px; color: #6c7086; font-size: 14px; }

  .toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: #a6e3a1;
    color: #1e1e2e;
    padding: 10px 24px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 14px;
    z-index: 999;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>

<header>
  <h1>📝 Fast Notes</h1>
  <span>WLAN Sync</span>
</header>

<div class="tabs">
  <button class="tab active" onclick="switchTab('new')">✏️ Neue Notiz</button>
  <button class="tab" onclick="switchTab('list')">📋 Alle Notizen</button>
</div>

<!-- NEW NOTE -->
<div id="new-panel" class="panel active">
  <textarea id="new-content" placeholder="Notiz hier eingeben..."></textarea>
  <input type="text" id="new-title" placeholder="Titel (optional)">
  <button class="btn btn-primary" onclick="saveNew()">💾 Speichern</button>
</div>

<!-- NOTES LIST -->
<div id="list-panel" class="panel">
  <div id="notes-list"></div>
</div>

<!-- EDIT VIEW -->
<div id="edit-view">
  <div id="edit-header">
    <button onclick="closeEdit()">← Zurück</button>
    <input type="text" id="edit-title-input" placeholder="Titel...">
  </div>
  <textarea id="edit-textarea"></textarea>
  <div id="edit-footer">
    <button class="save-btn" onclick="saveEdit()">💾 Speichern</button>
    <button class="delete-btn" onclick="deleteNote()">🗑️ Löschen</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentNoteId = null;

function switchTab(tab) {
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', (tab==='new'&&i===0)||(tab==='list'&&i===1)));
  document.getElementById('new-panel').classList.toggle('active', tab==='new');
  document.getElementById('list-panel').classList.toggle('active', tab==='list');
  if (tab === 'list') loadNotes();
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

async function saveNew() {
  const content = document.getElementById('new-content').value.trim();
  const title   = document.getElementById('new-title').value.trim();
  if (!content) return;
  await fetch('/api/notes', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({content, title: title || null})
  });
  document.getElementById('new-content').value = '';
  document.getElementById('new-title').value   = '';
  showToast('✓ Gespeichert!');
}

async function loadNotes() {
  const res   = await fetch('/api/notes');
  const notes = await res.json();
  const el    = document.getElementById('notes-list');
  if (!notes.length) {
    el.innerHTML = '<div class="empty">Noch keine Notizen vorhanden.</div>';
    return;
  }
  el.innerHTML = notes.map(n => `
    <div class="note-card" onclick="openEdit('${n.id}')">
      <div class="note-title">${n.title || formatDate(n.created_at)}</div>
      <div class="note-preview">${n.content.replace(/</g,'&lt;')}</div>
      <div class="note-date">${formatDate(n.updated_at)}</div>
    </div>
  `).join('');
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('de-CH') + ' ' + d.toLocaleTimeString('de-CH', {hour:'2-digit',minute:'2-digit'});
}

async function openEdit(id) {
  const res  = await fetch('/api/notes');
  const all  = await res.json();
  const note = all.find(n => n.id === id);
  if (!note) return;
  currentNoteId = id;
  document.getElementById('edit-textarea').value    = note.content;
  document.getElementById('edit-title-input').value = note.title || '';
  document.getElementById('edit-view').classList.add('open');
}

function closeEdit() {
  document.getElementById('edit-view').classList.remove('open');
  currentNoteId = null;
  loadNotes();
}

async function saveEdit() {
  const content = document.getElementById('edit-textarea').value.trim();
  const title   = document.getElementById('edit-title-input').value.trim();
  if (!content || !currentNoteId) return;
  await fetch(`/api/notes/${currentNoteId}`, {
    method: 'PUT',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({content, title: title || null})
  });
  showToast('✓ Gespeichert!');
  closeEdit();
}

async function deleteNote() {
  if (!currentNoteId) return;
  if (!confirm('Notiz wirklich löschen?')) return;
  await fetch(`/api/notes/${currentNoteId}`, {method: 'DELETE'});
  closeEdit();
}
</script>
</body>
</html>
"""

flask_app = Flask(__name__)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # suppress Flask console spam


@flask_app.route("/")
def index():
    return render_template_string(MOBILE_HTML)


@flask_app.route("/api/notes", methods=["GET"])
def api_get_notes():
    return jsonify(load_notes())


@flask_app.route("/api/notes", methods=["POST"])
def api_create_note():
    data    = request.get_json()
    content = data.get("content", "").strip()
    title   = data.get("title")
    if not content:
        return jsonify({"error": "empty"}), 400
    saved = save_note(content, title=title)
    return jsonify(saved), 201


@flask_app.route("/api/notes/<note_id>", methods=["PUT"])
def api_update_note(note_id):
    data    = request.get_json()
    content = data.get("content", "").strip()
    title   = data.get("title")
    if not content:
        return jsonify({"error": "empty"}), 400
    saved = save_note(content, note_id=note_id, title=title)
    return jsonify(saved)


@flask_app.route("/api/notes/<note_id>", methods=["DELETE"])
def api_delete_note(note_id):
    delete_note(note_id)
    return jsonify({"ok": True})


def start_web_server():
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)


# ─────────────────────────────────────────────
#  TRAY ICON HELPER
# ─────────────────────────────────────────────

def create_tray_image(size=64) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=12, fill="#1e1e2e")
    draw.rectangle([22, 14, 34, 44], fill="#f9e2af")
    draw.polygon([(22, 44), (34, 44), (28, 54)], fill="#f38ba8")
    draw.rectangle([22, 14, 34, 22], fill="#89b4fa")
    return img


# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────

class FastNotesApp:
    SIDEBAR_WIDTH = 220
    WINDOW_W      = 400
    WINDOW_H      = 600

    def __init__(self):
        self._visible          = False
        self._sidebar_open     = False
        self._current_note_id  = None
        self._tray             = None
        self._local_ip         = get_local_ip()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Fast Notes")
        self.root.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}")
        self.root.resizable(True, True)
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            from ctypes import windll, c_int, byref, sizeof
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            windll.dwmapi.DwmSetWindowAttribute(
                windll.user32.GetParent(self.root.winfo_id()),
                DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(c_int(2)), sizeof(c_int),
            )
        except Exception:
            pass

        self._build_ui()
        self._start_web_server()
        self._start_tray()
        self._register_shortcut()

    # ── UI BUILD ──────────────────────────────

    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(
            self.root, width=self.SIDEBAR_WIDTH, corner_radius=0, fg_color="#181825"
        )
        self.sidebar_label = ctk.CTkLabel(
            self.sidebar_frame, text="Notizen-Verlauf",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#cdd6f4"
        )
        self.sidebar_label.pack(pady=(14, 6), padx=12, anchor="w")
        self.sidebar_scroll = ctk.CTkScrollableFrame(
            self.sidebar_frame, fg_color="#181825", scrollbar_button_color="#313244"
        )
        self.sidebar_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        # Main panel
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#1e1e2e")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Top bar
        topbar = ctk.CTkFrame(self.main_frame, height=46, fg_color="#181825", corner_radius=0)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            topbar, text="☰  Historie", width=110, height=30,
            fg_color="#313244", hover_color="#45475a", corner_radius=8,
            font=ctk.CTkFont(size=12), command=self._toggle_sidebar,
        ).grid(row=0, column=0, padx=10, pady=8)

        self.note_title_label = ctk.CTkLabel(
            topbar, text="Neue Notiz", font=ctk.CTkFont(size=12), text_color="#6c7086"
        )
        self.note_title_label.grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            topbar, text="＋ Neu", width=80, height=30,
            fg_color="#313244", hover_color="#45475a", corner_radius=8,
            font=ctk.CTkFont(size=12), command=self._new_note,
        ).grid(row=0, column=2, padx=10, pady=8)

        ctk.CTkLabel(
            topbar, text=f"📱 {self._local_ip}:{WEB_PORT}",
            font=ctk.CTkFont(size=9), text_color="#a6e3a1"
        ).grid(row=0, column=3, padx=(0,10))


        # Text area
        self.textbox = ctk.CTkTextbox(
            self.main_frame,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="#1e1e2e", text_color="#cdd6f4",
            border_color="#313244", border_width=1,
            corner_radius=10, wrap="word",
        )
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 6))
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Bottom bar
        bottombar = ctk.CTkFrame(self.main_frame, height=40, fg_color="#181825", corner_radius=0)
        bottombar.grid(row=2, column=0, sticky="ew")
        bottombar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            bottombar, text="Alt+Leertaste zum Ein-/Ausblenden",
            font=ctk.CTkFont(size=10), text_color="#6c7086"
        )
        self.status_label.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        ctk.CTkButton(
            bottombar, text="💾 Speichern", width=100, height=26,
            fg_color="#89b4fa", hover_color="#74c7ec", text_color="#1e1e2e",
            corner_radius=8, font=ctk.CTkFont(size=11, weight="bold"),
            command=self._save_current,
        ).grid(row=0, column=1, padx=12, pady=6)

    # ── WEB SERVER ────────────────────────────

    def _start_web_server(self):
        t = threading.Thread(target=start_web_server, daemon=True)
        t.start()

    # ── SIDEBAR ──────────────────────────────

    def _toggle_sidebar(self):
        if self._sidebar_open:
            self.sidebar_frame.grid_remove()
            self._sidebar_open = False
            self.root.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}")
        else:
            self._refresh_sidebar()
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self._sidebar_open = True
            self.root.geometry(f"{self.WINDOW_W + self.SIDEBAR_WIDTH}x{self.WINDOW_H}")

    def _refresh_sidebar(self):
        for w in self.sidebar_scroll.winfo_children():
            w.destroy()
        for note in load_notes():
            btn = ctk.CTkButton(
                self.sidebar_scroll,
                text=format_display_title(note),
                anchor="w", fg_color="transparent", hover_color="#313244",
                text_color="#cdd6f4", corner_radius=6,
                font=ctk.CTkFont(size=12), height=30,
                command=lambda n=note: self._open_note(n),
            )
            btn.pack(fill="x", padx=4, pady=2)
            btn.bind("<Button-3>", lambda e, n=note: self._sidebar_context_menu(e, n))

    def _sidebar_context_menu(self, event, note: dict):
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.geometry(f"160x90+{event.x_root}+{event.y_root}")
        menu.configure(fg_color="#313244")
        menu.lift()
        menu.focus_force()

        def close_menu(): menu.destroy()

        def rename():
            close_menu()
            self._rename_dialog(note)

        def remove():
            close_menu()
            delete_note(note["id"])
            if self._current_note_id == note["id"]:
                self._new_note()
            self._refresh_sidebar()

        ctk.CTkButton(
            menu, text="✏️  Titel vergeben", anchor="w", fg_color="transparent",
            hover_color="#45475a", text_color="#cdd6f4", corner_radius=0,
            command=rename, height=36
        ).pack(fill="x", padx=2, pady=(4, 0))
        ctk.CTkButton(
            menu, text="🗑️  Löschen", anchor="w", fg_color="transparent",
            hover_color="#f38ba8", text_color="#f38ba8", corner_radius=0,
            command=remove, height=32
        ).pack(fill="x", padx=2)
        menu.bind("<FocusOut>", lambda e: close_menu())

    def _rename_dialog(self, note: dict):
        dialog    = ctk.CTkInputDialog(text="Neuer Titel (leer = Datum):", title="Titel vergeben")
        new_title = dialog.get_input()
        if new_title is not None:
            update_note_title(note["id"], new_title.strip())
            if self._sidebar_open:
                self._refresh_sidebar()

    # ── NOTE OPERATIONS ───────────────────────

    def _new_note(self):
        self._current_note_id = None
        self.textbox.delete("1.0", "end")
        self.note_title_label.configure(text="Neue Notiz")
        self.textbox.focus_set()

    def _open_note(self, note: dict):
        self._current_note_id = note["id"]
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", note.get("content", ""))
        self.note_title_label.configure(text=format_display_title(note))
        self.textbox.focus_set()

    def _save_current(self):
        content = self.textbox.get("1.0", "end-1c").strip()
        if not content:
            return None
        saved = save_note(content, note_id=self._current_note_id)
        self._current_note_id = saved["id"]
        self.note_title_label.configure(text=format_display_title(saved))
        self._set_status("Gespeichert ✓")
        if self._sidebar_open:
            self._refresh_sidebar()
        return saved["id"]

    def _set_status(self, text: str, duration_ms: int = 2000):
        self.status_label.configure(text=text)
        self.root.after(duration_ms, lambda: self.status_label.configure(
            text="Alt+Leertaste zum Ein-/Ausblenden"
        ))

    # ── VISIBILITY TOGGLE ─────────────────────

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))
        self.root.after(50, lambda: self.textbox.focus_set())
        self._visible = True
        self._new_note()

    def _hide_window(self):
        self._save_current()
        self.root.withdraw()
        self._visible = False

    def toggle_window(self):
        if self._visible:
            self.root.after(0, self._hide_window)
        else:
            self.root.after(0, self._show_window)

    # ── KEYBOARD SHORTCUT ─────────────────────

    def _register_shortcut(self):
        def listener():
            try:
                keyboard.add_hotkey("alt+space", self.toggle_window, suppress=True)
                keyboard.wait()
            except Exception as exc:
                print(f"Shortcut-Fehler: {exc}")
        threading.Thread(target=listener, daemon=True).start()

    # ── SYSTEM TRAY ───────────────────────────

    def _start_tray(self):
        icon_img = create_tray_image()

        def on_show(icon, item):
            self.root.after(0, self._show_window)

        def on_quit(icon, item):
            self._save_current()
            icon.stop()
            self.root.after(0, self.root.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("Fast Notes öffnen", on_show, default=True),
            pystray.MenuItem(f"📱 http://{self._local_ip}:{WEB_PORT}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", on_quit),
        )
        self._tray = pystray.Icon("FastNotes", icon_img, "Fast Notes", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    # ── WINDOW CLOSE ─────────────────────────

    def _on_close(self):
        self._save_current()
        self.root.withdraw()
        self._visible = False

    # ── MAIN LOOP ────────────────────────────

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "FastNotesMutex_v2")
        if ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.user32.MessageBoxW(0, "Fast Notes läuft bereits!", "Fast Notes", 0x40)
            sys.exit(0)
    except Exception:
        pass

    app = FastNotesApp()
    app.run()
