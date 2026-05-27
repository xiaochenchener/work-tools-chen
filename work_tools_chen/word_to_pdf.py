import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None


WORD_EXTENSIONS = {".doc", ".docx"}


def is_word_file(path: str) -> bool:
    p = Path(path)
    return p.is_file() and p.suffix.lower() in WORD_EXTENSIONS and not p.name.startswith("~$")


def collect_word_files(paths, recursive=False):
    """从文件或文件夹中收集 .doc / .docx。"""
    collected = []
    seen = set()

    for raw in paths:
        if not raw:
            continue

        path = Path(raw)

        if path.is_file() and is_word_file(str(path)):
            resolved = str(path.resolve())
            if resolved not in seen:
                collected.append(resolved)
                seen.add(resolved)

        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            for item in iterator:
                if is_word_file(str(item)):
                    resolved = str(item.resolve())
                    if resolved not in seen:
                        collected.append(resolved)
                        seen.add(resolved)

    return collected


def find_libreoffice_executable():
    """查找 LibreOffice / soffice 可执行文件。"""
    candidates = [
        "soffice",
        "libreoffice",
    ]

    if platform.system().lower() == "windows":
        candidates.extend([
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ])
    elif platform.system().lower() == "darwin":
        candidates.extend([
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ])

    for candidate in candidates:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found

    return None


def output_pdf_path(input_file, output_dir=None):
    input_path = Path(input_file)
    if output_dir:
        return str(Path(output_dir) / (input_path.stem + ".pdf"))
    return str(input_path.with_suffix(".pdf"))


def convert_with_word_com(files, output_dir=None, overwrite=False, progress_callback=None):
    """
    使用 Microsoft Word COM 转 PDF。
    适用：Windows + 已安装 Microsoft Word。
    支持：.doc / .docx。
    """
    if platform.system().lower() != "windows":
        raise RuntimeError("Microsoft Word COM 转换只支持 Windows。")

    try:
        import pythoncom
        import win32com.client
    except ImportError as e:
        raise RuntimeError("缺少 pywin32，请先运行 pip install pywin32。") from e

    pythoncom.CoInitialize()
    word = None
    results = []

    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        wd_format_pdf = 17

        for index, file_path in enumerate(files, start=1):
            pdf_path = output_pdf_path(file_path, output_dir)
            status = "成功"

            try:
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

                if os.path.exists(pdf_path) and not overwrite:
                    status = "跳过：PDF 已存在"
                else:
                    if os.path.exists(pdf_path) and overwrite:
                        os.remove(pdf_path)

                    doc = word.Documents.Open(
                        os.path.abspath(file_path),
                        ReadOnly=True,
                        AddToRecentFiles=False
                    )
                    doc.SaveAs(os.path.abspath(pdf_path), FileFormat=wd_format_pdf)
                    doc.Close(False)

            except Exception as e:
                status = f"失败：{e}"

            item = {
                "input": file_path,
                "output": pdf_path,
                "status": status,
            }
            results.append(item)

            if progress_callback:
                progress_callback(index, len(files), item)

    finally:
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()

    return results


def convert_with_libreoffice(files, output_dir=None, overwrite=False, progress_callback=None):
    """
    使用 LibreOffice headless 转 PDF。
    适用：Windows / macOS / Linux，前提是已安装 LibreOffice。
    支持：通常支持 .doc / .docx。
    """
    soffice = find_libreoffice_executable()
    if not soffice:
        raise RuntimeError("未找到 LibreOffice / soffice，请先安装 LibreOffice，或使用 Microsoft Word 方式。")

    results = []

    for index, file_path in enumerate(files, start=1):
        pdf_path = output_pdf_path(file_path, output_dir)
        out_dir = output_dir or os.path.dirname(file_path)
        status = "成功"

        try:
            os.makedirs(out_dir, exist_ok=True)

            if os.path.exists(pdf_path) and not overwrite:
                status = "跳过：PDF 已存在"
            else:
                if os.path.exists(pdf_path) and overwrite:
                    os.remove(pdf_path)

                cmd = [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    out_dir,
                    file_path,
                ]

                completed = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120
                )

                if completed.returncode != 0:
                    status = f"失败：{completed.stderr.strip() or completed.stdout.strip()}"
                elif not os.path.exists(pdf_path):
                    status = "失败：转换命令执行完成，但未找到输出 PDF"

        except Exception as e:
            status = f"失败：{e}"

        item = {
            "input": file_path,
            "output": pdf_path,
            "status": status,
        }
        results.append(item)

        if progress_callback:
            progress_callback(index, len(files), item)

    return results


def convert_with_docx2pdf(files, output_dir=None, overwrite=False, progress_callback=None):
    """
    使用 docx2pdf 转 PDF。
    适用：Windows / macOS + 已安装 Microsoft Word。
    限制：一般只适合 .docx，不建议用于 .doc。
    """
    try:
        from docx2pdf import convert
    except ImportError as e:
        raise RuntimeError("缺少 docx2pdf，请先运行 pip install docx2pdf。") from e

    results = []

    for index, file_path in enumerate(files, start=1):
        pdf_path = output_pdf_path(file_path, output_dir)
        status = "成功"

        try:
            if Path(file_path).suffix.lower() != ".docx":
                status = "跳过：docx2pdf 方式仅支持 .docx"
            else:
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

                if os.path.exists(pdf_path) and not overwrite:
                    status = "跳过：PDF 已存在"
                else:
                    if os.path.exists(pdf_path) and overwrite:
                        os.remove(pdf_path)
                    convert(file_path, pdf_path)

        except Exception as e:
            status = f"失败：{e}"

        item = {
            "input": file_path,
            "output": pdf_path,
            "status": status,
        }
        results.append(item)

        if progress_callback:
            progress_callback(index, len(files), item)

    return results


def convert_word_files(files, output_dir=None, overwrite=False, backend="auto", progress_callback=None):
    """
    统一转换入口。
    backend:
        auto
        word
        libreoffice
        docx2pdf

    说明：
    - Windows: auto 优先 Microsoft Word COM，失败后尝试 LibreOffice。
    - macOS: auto 优先 docx2pdf 处理 .docx；如果包含 .doc 或 docx2pdf 失败，再尝试 LibreOffice。
    - Linux: auto 使用 LibreOffice。
    """
    backend = backend.lower().strip()
    system = platform.system().lower()

    if backend == "auto":
        if system == "windows":
            try:
                return convert_with_word_com(files, output_dir, overwrite, progress_callback)
            except Exception as word_error:
                try:
                    return convert_with_libreoffice(files, output_dir, overwrite, progress_callback)
                except Exception as libre_error:
                    raise RuntimeError(
                        f"自动转换失败。Word 错误：{word_error}；LibreOffice 错误：{libre_error}"
                    )

        if system == "darwin":
            has_doc = any(Path(f).suffix.lower() == ".doc" for f in files)
            if not has_doc:
                try:
                    return convert_with_docx2pdf(files, output_dir, overwrite, progress_callback)
                except Exception as docx2pdf_error:
                    try:
                        return convert_with_libreoffice(files, output_dir, overwrite, progress_callback)
                    except Exception as libre_error:
                        raise RuntimeError(
                            f"自动转换失败。docx2pdf 错误：{docx2pdf_error}；LibreOffice 错误：{libre_error}"
                        )
            return convert_with_libreoffice(files, output_dir, overwrite, progress_callback)

        return convert_with_libreoffice(files, output_dir, overwrite, progress_callback)

    if backend == "word":
        return convert_with_word_com(files, output_dir, overwrite, progress_callback)

    if backend == "libreoffice":
        return convert_with_libreoffice(files, output_dir, overwrite, progress_callback)

    if backend == "docx2pdf":
        return convert_with_docx2pdf(files, output_dir, overwrite, progress_callback)

    raise RuntimeError(f"未知转换方式：{backend}")


class WordToPdfFrame(ttk.Frame):
    """批量 Word 转 PDF 页面。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.word_files = []
        self.output_dir = tk.StringVar(value="")
        self.recursive_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.backend_var = tk.StringVar(value="auto")
        self._create_widgets()

    def _create_widgets(self):
        top = ttk.LabelFrame(self, text="转换设置", padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="输出目录：").grid(row=0, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(top, textvariable=self.output_dir)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(top, text="选择", command=self.choose_output_dir).grid(row=0, column=2, padx=5)

        ttk.Label(top, text="转换方式：").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        backend_combo = ttk.Combobox(
            top,
            textvariable=self.backend_var,
            values=["auto", "word", "libreoffice", "docx2pdf"],
            width=16,
            state="readonly"
        )
        backend_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(8, 0))

        ttk.Checkbutton(top, text="添加文件夹时包含子文件夹", variable=self.recursive_var).grid(
            row=1, column=1, sticky=tk.E, padx=5, pady=(8, 0)
        )
        ttk.Checkbutton(top, text="覆盖已存在 PDF", variable=self.overwrite_var).grid(
            row=1, column=2, sticky=tk.W, padx=5, pady=(8, 0)
        )

        top.grid_columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self, padding=(0, 10))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="添加 Word 文件", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="添加文件夹", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(btn_frame, text="开始转换", command=self.start_convert)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=5)

        tip = ttk.Label(
            self,
            text="说明：auto 在 Windows 上优先调用 Microsoft Word；否则尝试 LibreOffice。输出目录留空时，PDF 会保存到原 Word 文件同目录。",
            foreground="gray"
        )
        tip.pack(fill=tk.X, pady=(0, 8))

        drop_frame = ttk.LabelFrame(self, text="拖拽区域", padding=10)
        drop_frame.pack(fill=tk.X, pady=5)

        self.drop_label = ttk.Label(
            drop_frame,
            text="可以拖入 .doc / .docx 文件，或拖入包含 Word 文件的文件夹。",
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

        list_frame = ttk.LabelFrame(self, text="待转换文件", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("input", "output", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        self.tree.heading("input", text="Word 文件")
        self.tree.heading("output", text="输出 PDF")
        self.tree.heading("status", text="状态")
        self.tree.column("input", width=340, anchor=tk.W)
        self.tree.column("output", width=340, anchor=tk.W)
        self.tree.column("status", width=180, anchor=tk.W)

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

    def choose_output_dir(self):
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="选择 Word 文件",
            filetypes=[("Word 文件", "*.doc *.docx"), ("所有文件", "*.*")]
        )
        self._add_paths(files)

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含 Word 文件的文件夹")
        if folder:
            self._add_paths([folder])

    def on_drop(self, event):
        paths = self._parse_drop_files(event.data)
        self._add_paths(paths)

    def _add_paths(self, paths):
        files = collect_word_files(paths, recursive=self.recursive_var.get())

        if not files:
            messagebox.showwarning("未找到文件", "没有找到 .doc 或 .docx 文件。")
            return

        existing = set(self.word_files)
        added = 0

        for file_path in files:
            if file_path not in existing:
                self.word_files.append(file_path)
                existing.add(file_path)
                self.tree.insert("", tk.END, values=(file_path, output_pdf_path(file_path, self.output_dir.get() or None), "等待转换"))
                added += 1

        self.status_label.config(text=f"已添加 {added} 个文件，共 {len(self.word_files)} 个")

    def _parse_drop_files(self, data):
        files = []
        parts = []
        current = ""
        in_brace = False

        for ch in data:
            if ch == "{":
                in_brace = True
                if current.strip():
                    parts.append(current.strip())
                current = ""
            elif ch == "}":
                in_brace = False
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

    def clear_files(self):
        self.word_files.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.progress["value"] = 0
        self.status_label.config(text="已清空")

    def start_convert(self):
        if not self.word_files:
            messagebox.showwarning("提示", "请先添加 Word 文件或文件夹。")
            return

        output_dir = self.output_dir.get().strip() or None
        backend = self.backend_var.get()
        overwrite = self.overwrite_var.get()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for file_path in self.word_files:
            self.tree.insert("", tk.END, values=(file_path, output_pdf_path(file_path, output_dir), "等待转换"))

        self.progress["maximum"] = len(self.word_files)
        self.progress["value"] = 0
        self.start_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"转换中... 使用方式：{backend}")

        def progress_callback(index, total, item):
            self.after(0, lambda: self._update_one_result(index, total, item))

        def worker():
            try:
                convert_word_files(
                    list(self.word_files),
                    output_dir=output_dir,
                    overwrite=overwrite,
                    backend=backend,
                    progress_callback=progress_callback,
                )
                self.after(0, lambda: self._finish_convert("转换完成"))
            except Exception as e:
                # 注意：Python 会在 except 结束后清理异常变量 e。
                # 必须先转成字符串，否则 lambda 回到主线程执行时会取不到 e，界面就会一直停在“转换中...”。
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._finish_convert(f"转换失败：{msg}", error=True))

        threading.Thread(target=worker, daemon=True).start()

    def _update_one_result(self, index, total, item):
        children = self.tree.get_children()
        if 0 <= index - 1 < len(children):
            self.tree.item(children[index - 1], values=(item["input"], item["output"], item["status"]))
            self.tree.see(children[index - 1])

        self.progress["value"] = index
        self.status_label.config(text=f"{index}/{total}")

    def _finish_convert(self, msg, error=False):
        self.start_btn.config(state=tk.NORMAL)
        self.status_label.config(text=msg)

        if error:
            messagebox.showerror("转换失败", msg)
        else:
            messagebox.showinfo("完成", msg)
