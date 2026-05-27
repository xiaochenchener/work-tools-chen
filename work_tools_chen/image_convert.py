import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

try:
    from PIL import Image
except ImportError:
    Image = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def is_supported_image(path):
    p = Path(path)
    return p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS


def collect_image_files(paths, recursive=False):
    collected = []
    seen = set()

    for raw in paths:
        if not raw:
            continue

        path = Path(raw)

        if path.is_file() and is_supported_image(path):
            resolved = str(path.resolve())
            if resolved not in seen:
                collected.append(resolved)
                seen.add(resolved)

        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            for item in iterator:
                if is_supported_image(item):
                    resolved = str(item.resolve())
                    if resolved not in seen:
                        collected.append(resolved)
                        seen.add(resolved)

    return collected


def build_output_path(input_file, output_dir=None, target_format="png", overwrite=False):
    p = Path(input_file)
    target_format = target_format.lower().strip()
    suffix = ".jpg" if target_format in {"jpg", "jpeg"} else ".png"
    out_dir = Path(output_dir) if output_dir else p.parent
    output_path = out_dir / (p.stem + suffix)

    # 如果原文件也是目标格式且不覆盖，就自动加后缀，避免覆盖原图
    if output_path.resolve() == p.resolve() and not overwrite:
        output_path = out_dir / (p.stem + "_converted" + suffix)

    return str(output_path)


def convert_one_image(input_file, output_path, target_format="png", jpeg_quality=95):
    if Image is None:
        raise RuntimeError("缺少 Pillow，请先安装：pip install Pillow")

    target_format = target_format.lower().strip()

    with Image.open(input_file) as img:
        if target_format in {"jpg", "jpeg"}:
            # JPG 不支持透明通道，需要白底合成
            if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")

            img.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)

        elif target_format == "png":
            img.save(output_path, "PNG", optimize=True)

        else:
            raise RuntimeError(f"不支持的目标格式：{target_format}")


def convert_images(files, output_dir=None, target_format="png", overwrite=False, jpeg_quality=95, progress_callback=None):
    results = []

    for index, file_path in enumerate(files, start=1):
        output_path = build_output_path(file_path, output_dir, target_format, overwrite)
        status = "成功"

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if os.path.exists(output_path) and not overwrite:
                status = "跳过：文件已存在"
            else:
                convert_one_image(file_path, output_path, target_format, jpeg_quality)

        except Exception as e:
            status = f"失败：{e}"

        item = {
            "input": file_path,
            "output": output_path,
            "status": status,
        }
        results.append(item)

        if progress_callback:
            progress_callback(index, len(files), item)

    return results


class ImageConvertFrame(ttk.Frame):
    """JPG / PNG 图片格式互转页面。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.image_files = []
        self.output_dir = tk.StringVar(value="")
        self.recursive_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.target_format_var = tk.StringVar(value="png")
        self.jpeg_quality_var = tk.IntVar(value=95)
        self._create_widgets()

    def _create_widgets(self):
        setting = ttk.LabelFrame(self, text="转换设置", padding=10)
        setting.pack(fill=tk.X)

        ttk.Label(setting, text="输出目录：").grid(row=0, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(setting, textvariable=self.output_dir)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(setting, text="选择", command=self.choose_output_dir).grid(row=0, column=2, padx=5)

        ttk.Label(setting, text="目标格式：").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        fmt_combo = ttk.Combobox(
            setting,
            textvariable=self.target_format_var,
            values=["png", "jpg"],
            width=10,
            state="readonly"
        )
        fmt_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(8, 0))

        ttk.Label(setting, text="JPG质量：").grid(row=1, column=1, sticky=tk.W, padx=(110, 0), pady=(8, 0))
        quality_spin = ttk.Spinbox(setting, from_=1, to=100, textvariable=self.jpeg_quality_var, width=6)
        quality_spin.grid(row=1, column=1, sticky=tk.W, padx=(175, 0), pady=(8, 0))

        ttk.Checkbutton(setting, text="添加文件夹时包含子文件夹", variable=self.recursive_var).grid(
            row=1, column=1, sticky=tk.E, padx=5, pady=(8, 0)
        )
        ttk.Checkbutton(setting, text="覆盖已存在文件", variable=self.overwrite_var).grid(
            row=1, column=2, sticky=tk.W, padx=5, pady=(8, 0)
        )

        setting.grid_columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self, padding=(0, 10))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="添加图片文件", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="添加文件夹", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(btn_frame, text="开始转换", command=self.start_convert)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=5)

        tip = ttk.Label(
            self,
            text="说明：PNG 转 JPG 时，透明背景会自动合成为白色背景。输出目录留空时，会保存到原图同目录。",
            foreground="gray"
        )
        tip.pack(fill=tk.X, pady=(0, 8))

        drop_frame = ttk.LabelFrame(self, text="拖拽区域", padding=10)
        drop_frame.pack(fill=tk.X, pady=5)

        self.drop_label = ttk.Label(
            drop_frame,
            text="可以拖入 .jpg / .jpeg / .png 文件，或拖入包含图片的文件夹。",
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

        list_frame = ttk.LabelFrame(self, text="待转换图片", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("input", "output", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        self.tree.heading("input", text="原图片")
        self.tree.heading("output", text="输出图片")
        self.tree.heading("status", text="状态")
        self.tree.column("input", width=360, anchor=tk.W)
        self.tree.column("output", width=360, anchor=tk.W)
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
            self.refresh_tree()

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="选择图片文件",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png"), ("所有文件", "*.*")]
        )
        self._add_paths(files)

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
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

        return [p.strip() for p in parts if p.strip()]

    def _add_paths(self, paths):
        files = collect_image_files(paths, recursive=self.recursive_var.get())

        if not files:
            messagebox.showwarning("未找到文件", "没有找到 jpg、jpeg 或 png 图片。")
            return

        existing = set(self.image_files)
        added = 0

        for file_path in files:
            if file_path not in existing:
                self.image_files.append(file_path)
                existing.add(file_path)
                added += 1

        self.refresh_tree()
        self.status_label.config(text=f"已添加 {added} 个文件，共 {len(self.image_files)} 个")

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        out_dir = self.output_dir.get().strip() or None
        fmt = self.target_format_var.get()
        overwrite = self.overwrite_var.get()

        for file_path in self.image_files:
            self.tree.insert(
                "",
                tk.END,
                values=(file_path, build_output_path(file_path, out_dir, fmt, overwrite), "等待转换")
            )

    def clear_files(self):
        self.image_files.clear()
        self.refresh_tree()
        self.progress["value"] = 0
        self.status_label.config(text="已清空")

    def start_convert(self):
        if not self.image_files:
            messagebox.showwarning("提示", "请先添加图片文件。")
            return

        out_dir = self.output_dir.get().strip() or None
        fmt = self.target_format_var.get()
        overwrite = self.overwrite_var.get()

        try:
            quality = int(self.jpeg_quality_var.get())
            quality = max(1, min(100, quality))
        except Exception:
            messagebox.showerror("输入错误", "JPG质量必须是 1 到 100 之间的整数。")
            return

        self.refresh_tree()
        self.progress["maximum"] = len(self.image_files)
        self.progress["value"] = 0
        self.start_btn.config(state=tk.DISABLED)
        self.status_label.config(text="转换中...")

        def progress_callback(index, total, item):
            self.after(0, lambda idx=index, total=total, data=item: self._update_one_result(idx, total, data))

        def worker():
            try:
                convert_images(
                    list(self.image_files),
                    output_dir=out_dir,
                    target_format=fmt,
                    overwrite=overwrite,
                    jpeg_quality=quality,
                    progress_callback=progress_callback,
                )
                self.after(0, lambda: self._finish_convert("转换完成"))
            except Exception as e:
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
