import os
import re
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def natural_key(text):
    """
    自然排序：
    例如 1.pdf, 2.pdf, 10.pdf 会按 1、2、10 排，而不是 1、10、2。
    """
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(text))]


def is_pdf_file(path):
    p = Path(path)
    return p.is_file() and p.suffix.lower() == ".pdf"


def collect_pdf_files(paths, recursive=False):
    """从文件或文件夹中收集 PDF 文件。"""
    collected = []
    seen = set()

    for raw in paths:
        if not raw:
            continue

        path = Path(raw)

        if path.is_file() and is_pdf_file(path):
            resolved = str(path.resolve())
            if resolved not in seen:
                collected.append(resolved)
                seen.add(resolved)

        elif path.is_dir():
            iterator = path.rglob("*.pdf") if recursive else path.glob("*.pdf")
            for item in iterator:
                if is_pdf_file(item):
                    resolved = str(item.resolve())
                    if resolved not in seen:
                        collected.append(resolved)
                        seen.add(resolved)

    return collected


def get_pdf_page_count(path):
    if fitz is None:
        return "未知"
    try:
        doc = fitz.open(path)
        pages = len(doc)
        doc.close()
        return pages
    except Exception:
        return "读取失败"


def format_size(size_bytes):
    try:
        size_bytes = float(size_bytes)
    except Exception:
        return ""

    units = ["B", "KB", "MB", "GB"]
    value = size_bytes
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def merge_pdfs(pdf_files, output_path, progress_callback=None):
    """
    按列表顺序合并 PDF。
    使用 PyMuPDF，不额外依赖 pypdf。
    """
    if fitz is None:
        raise RuntimeError("缺少 PyMuPDF，请先安装：pip install PyMuPDF")

    if not pdf_files:
        raise RuntimeError("没有可合并的 PDF 文件。")

    if not output_path:
        raise RuntimeError("请先选择输出 PDF 文件。")

    output_path = os.path.abspath(output_path)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 防止把输出文件也作为输入文件，导致合并异常
    output_abs = os.path.abspath(output_path)
    input_abs_list = [os.path.abspath(p) for p in pdf_files]
    if output_abs in input_abs_list:
        raise RuntimeError("输出 PDF 不能和待合并的 PDF 文件相同，请换一个输出文件名。")

    merged = fitz.open()

    try:
        total = len(pdf_files)

        for index, pdf_path in enumerate(pdf_files, start=1):
            src = None
            item = {
                "input": pdf_path,
                "status": "成功",
            }

            try:
                src = fitz.open(pdf_path)
                merged.insert_pdf(src)
            except Exception as e:
                item["status"] = f"失败：{e}"
            finally:
                if src is not None:
                    src.close()

            if progress_callback:
                progress_callback(index, total, item)

        if len(merged) == 0:
            raise RuntimeError("合并失败：没有成功插入任何页面。")

        merged.save(output_path)
        return output_path

    finally:
        merged.close()


class PDFMergeFrame(ttk.Frame):
    """多个 PDF 合并页面。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.pdf_files = []
        self.output_path = tk.StringVar(value="")
        self.recursive_var = tk.BooleanVar(value=False)
        self.sort_key_var = tk.StringVar(value="文件名")
        self.sort_order_var = tk.StringVar(value="升序")
        self._create_widgets()

    def _create_widgets(self):
        setting = ttk.LabelFrame(self, text="合并设置", padding=10)
        setting.pack(fill=tk.X)

        ttk.Label(setting, text="输出文件：").grid(row=0, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(setting, textvariable=self.output_path)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(setting, text="选择", command=self.choose_output_file).grid(row=0, column=2, padx=5)

        ttk.Label(setting, text="排序方式：").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        sort_combo = ttk.Combobox(
            setting,
            textvariable=self.sort_key_var,
            values=["文件名", "完整路径", "修改时间", "创建时间", "文件大小", "页数"],
            width=14,
            state="readonly"
        )
        sort_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(8, 0))

        order_combo = ttk.Combobox(
            setting,
            textvariable=self.sort_order_var,
            values=["升序", "降序"],
            width=8,
            state="readonly"
        )
        order_combo.grid(row=1, column=1, sticky=tk.W, padx=(150, 5), pady=(8, 0))

        ttk.Button(setting, text="按当前方式排序", command=self.sort_files).grid(row=1, column=2, padx=5, pady=(8, 0))
        ttk.Checkbutton(setting, text="添加文件夹时包含子文件夹", variable=self.recursive_var).grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=(8, 0)
        )

        setting.grid_columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self, padding=(0, 10))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="添加 PDF 文件", command=self.add_files).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="添加文件夹", command=self.add_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="删除选中", command=self.remove_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=4)

        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(btn_frame, text="置顶", command=self.move_top).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="上移", command=self.move_up).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="下移", command=self.move_down).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="置底", command=self.move_bottom).pack(side=tk.LEFT, padx=4)

        self.merge_btn = ttk.Button(btn_frame, text="开始合并", command=self.start_merge)
        self.merge_btn.pack(side=tk.RIGHT, padx=4)

        tip = ttk.Label(
            self,
            text="说明：最终合并顺序以当前列表从上到下为准。可以先自动排序，再手动上移/下移微调。",
            foreground="gray"
        )
        tip.pack(fill=tk.X, pady=(0, 8))

        drop_frame = ttk.LabelFrame(self, text="拖拽区域", padding=10)
        drop_frame.pack(fill=tk.X, pady=5)

        self.drop_label = ttk.Label(
            drop_frame,
            text="可以拖入多个 PDF 文件，或拖入包含 PDF 的文件夹。",
            foreground="gray"
        )
        self.drop_label.pack()

        if DND_FILES is not None:
            try:
                drop_frame.drop_target_register(DND_FILES)
                drop_frame.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                self.drop_label.config(text="拖拽注册失败，请使用按钮添加。")
        else:
            self.drop_label.config(text="未安装 tkinterdnd2，拖拽功能不可用，请使用按钮添加。")

        list_frame = ttk.LabelFrame(self, text="待合并 PDF 列表", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("order", "file", "pages", "size", "mtime", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=14, selectmode="extended")
        headings = {
            "order": "顺序",
            "file": "PDF 文件",
            "pages": "页数",
            "size": "大小",
            "mtime": "修改时间",
            "status": "状态",
        }
        widths = {
            "order": 60,
            "file": 420,
            "pages": 70,
            "size": 90,
            "mtime": 160,
            "status": 180,
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=tk.CENTER if col != "file" else tk.W)

        v_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.config(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, pady=(6, 0))

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.status_label = ttk.Label(bottom, text="未开始")
        self.status_label.pack(side=tk.RIGHT)

    def choose_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="选择合并后的 PDF 文件",
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")]
        )
        if file_path:
            self.output_path.set(file_path)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
        )
        self._add_paths(files)

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含 PDF 文件的文件夹")
        if folder:
            self._add_paths([folder])

    def on_drop(self, event):
        self._add_paths(self._parse_drop_files(event.data))

    def _parse_drop_files(self, data):
        files = []
        parts = []
        current = ""

        for ch in data:
            if ch == "{":
                if current.strip():
                    parts.append(current.strip())
                current = ""
            elif ch == "}":
                if current.strip():
                    parts.append(current.strip())
                current = ""
            else:
                current += ch

        if current.strip():
            parts.append(current.strip())

        if not parts:
            parts = data.split()

        for p in parts:
            p = p.strip()
            if p:
                files.append(p)

        return files

    def _add_paths(self, paths):
        files = collect_pdf_files(paths, recursive=self.recursive_var.get())

        if not files:
            messagebox.showwarning("未找到文件", "没有找到 PDF 文件。")
            return

        existing = set(self.pdf_files)
        added = 0

        for file_path in files:
            if file_path not in existing:
                self.pdf_files.append(file_path)
                existing.add(file_path)
                added += 1

        self.refresh_tree()
        self.status_label.config(text=f"已添加 {added} 个文件，共 {len(self.pdf_files)} 个")

    def refresh_tree(self, keep_selection_paths=None):
        keep_selection_paths = set(keep_selection_paths or [])

        for item in self.tree.get_children():
            self.tree.delete(item)

        selected_items = []

        for index, file_path in enumerate(self.pdf_files, start=1):
            p = Path(file_path)
            try:
                stat = p.stat()
                size = format_size(stat.st_size)
                mtime = __import__("datetime").datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                size = ""
                mtime = ""

            pages = get_pdf_page_count(file_path)

            item_id = self.tree.insert(
                "",
                tk.END,
                values=(index, file_path, pages, size, mtime, "等待合并")
            )

            if file_path in keep_selection_paths:
                selected_items.append(item_id)

        if selected_items:
            self.tree.selection_set(selected_items)
            self.tree.see(selected_items[0])

    def get_selected_indices(self):
        selected = self.tree.selection()
        indices = []

        for item in selected:
            values = self.tree.item(item, "values")
            if values:
                try:
                    indices.append(int(values[0]) - 1)
                except Exception:
                    pass

        return sorted(indices)

    def remove_selected(self):
        indices = self.get_selected_indices()
        if not indices:
            return

        for index in reversed(indices):
            if 0 <= index < len(self.pdf_files):
                self.pdf_files.pop(index)

        self.refresh_tree()
        self.status_label.config(text=f"已删除选中文件，剩余 {len(self.pdf_files)} 个")

    def clear_files(self):
        self.pdf_files.clear()
        self.refresh_tree()
        self.progress["value"] = 0
        self.status_label.config(text="已清空")

    def sort_files(self):
        key_name = self.sort_key_var.get()
        reverse = self.sort_order_var.get() == "降序"

        def sort_key(path):
            p = Path(path)
            try:
                stat = p.stat()
            except Exception:
                stat = None

            if key_name == "文件名":
                return natural_key(p.name)
            if key_name == "完整路径":
                return natural_key(str(p))
            if key_name == "修改时间":
                return stat.st_mtime if stat else 0
            if key_name == "创建时间":
                return stat.st_ctime if stat else 0
            if key_name == "文件大小":
                return stat.st_size if stat else 0
            if key_name == "页数":
                pages = get_pdf_page_count(path)
                return pages if isinstance(pages, int) else 0

            return natural_key(p.name)

        self.pdf_files.sort(key=sort_key, reverse=reverse)
        self.refresh_tree()
        self.status_label.config(text=f"已按{key_name}{self.sort_order_var.get()}排序")

    def move_up(self):
        indices = self.get_selected_indices()
        if not indices:
            return

        selected_paths = [self.pdf_files[i] for i in indices if 0 <= i < len(self.pdf_files)]

        for i in indices:
            if i > 0:
                self.pdf_files[i - 1], self.pdf_files[i] = self.pdf_files[i], self.pdf_files[i - 1]

        self.refresh_tree(selected_paths)

    def move_down(self):
        indices = self.get_selected_indices()
        if not indices:
            return

        selected_paths = [self.pdf_files[i] for i in indices if 0 <= i < len(self.pdf_files)]

        for i in reversed(indices):
            if i < len(self.pdf_files) - 1:
                self.pdf_files[i + 1], self.pdf_files[i] = self.pdf_files[i], self.pdf_files[i + 1]

        self.refresh_tree(selected_paths)

    def move_top(self):
        indices = self.get_selected_indices()
        if not indices:
            return

        selected_paths = [self.pdf_files[i] for i in indices if 0 <= i < len(self.pdf_files)]
        remaining = [p for i, p in enumerate(self.pdf_files) if i not in indices]
        self.pdf_files = selected_paths + remaining
        self.refresh_tree(selected_paths)

    def move_bottom(self):
        indices = self.get_selected_indices()
        if not indices:
            return

        selected_paths = [self.pdf_files[i] for i in indices if 0 <= i < len(self.pdf_files)]
        remaining = [p for i, p in enumerate(self.pdf_files) if i not in indices]
        self.pdf_files = remaining + selected_paths
        self.refresh_tree(selected_paths)

    def start_merge(self):
        if not self.pdf_files:
            messagebox.showwarning("提示", "请先添加 PDF 文件。")
            return

        output_path = self.output_path.get().strip()
        if not output_path:
            messagebox.showwarning("提示", "请先选择输出 PDF 文件。")
            return

        self.progress["maximum"] = len(self.pdf_files)
        self.progress["value"] = 0
        self.merge_btn.config(state=tk.DISABLED)
        self.status_label.config(text="合并中...")

        # 把列表里的状态重置为等待合并
        for item in self.tree.get_children():
            values = list(self.tree.item(item, "values"))
            if values:
                values[-1] = "等待合并"
                self.tree.item(item, values=values)

        def progress_callback(index, total, item):
            self.after(0, lambda idx=index, total=total, data=item: self._update_one_result(idx, total, data))

        def worker():
            try:
                out = merge_pdfs(list(self.pdf_files), output_path, progress_callback=progress_callback)
                self.after(0, lambda path=out: self._finish_merge(f"合并完成：{path}"))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._finish_merge(f"合并失败：{msg}", error=True))

        threading.Thread(target=worker, daemon=True).start()

    def _update_one_result(self, index, total, item):
        children = self.tree.get_children()
        if 0 <= index - 1 < len(children):
            values = list(self.tree.item(children[index - 1], "values"))
            if values:
                values[-1] = item.get("status", "")
                self.tree.item(children[index - 1], values=values)
                self.tree.see(children[index - 1])

        self.progress["value"] = index
        self.status_label.config(text=f"{index}/{total}")

    def _finish_merge(self, msg, error=False):
        self.merge_btn.config(state=tk.NORMAL)
        self.status_label.config(text=msg)

        if error:
            messagebox.showerror("合并失败", msg)
        else:
            messagebox.showinfo("完成", msg)
