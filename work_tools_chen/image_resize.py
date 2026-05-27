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


def get_image_size(path):
    if Image is None:
        return ""
    try:
        with Image.open(path) as img:
            return f"{img.width}×{img.height}"
    except Exception:
        return "读取失败"


def build_output_path(input_file, output_dir=None, suffix_text="_resized", output_format="same", overwrite=False):
    p = Path(input_file)
    out_dir = Path(output_dir) if output_dir else p.parent

    if output_format == "same":
        suffix = p.suffix
    elif output_format == "jpg":
        suffix = ".jpg"
    elif output_format == "png":
        suffix = ".png"
    else:
        suffix = p.suffix

    if overwrite and output_dir is None and output_format == "same":
        return str(p)

    return str(out_dir / (p.stem + suffix_text + suffix))


def calculate_new_size(width, height, mode, percent=100, target_width=None, target_height=None, keep_ratio=True):
    if mode == "按百分比":
        scale = percent / 100
        new_w = max(1, int(round(width * scale)))
        new_h = max(1, int(round(height * scale)))
        return new_w, new_h

    if mode == "按宽度":
        if not target_width:
            raise RuntimeError("请输入目标宽度。")
        new_w = int(target_width)
        if keep_ratio:
            new_h = max(1, int(round(height * new_w / width)))
        else:
            if not target_height:
                raise RuntimeError("未勾选保持比例时，需要同时输入目标高度。")
            new_h = int(target_height)
        return max(1, new_w), max(1, new_h)

    if mode == "按高度":
        if not target_height:
            raise RuntimeError("请输入目标高度。")
        new_h = int(target_height)
        if keep_ratio:
            new_w = max(1, int(round(width * new_h / height)))
        else:
            if not target_width:
                raise RuntimeError("未勾选保持比例时，需要同时输入目标宽度。")
            new_w = int(target_width)
        return max(1, new_w), max(1, new_h)

    if mode == "指定宽高":
        if not target_width or not target_height:
            raise RuntimeError("请输入目标宽度和目标高度。")
        return max(1, int(target_width)), max(1, int(target_height))

    raise RuntimeError(f"未知调整方式：{mode}")


def save_image(img, output_path, output_format="same", jpeg_quality=95):
    p = Path(output_path)

    if output_format == "same":
        fmt = p.suffix.lower().lstrip(".")
    else:
        fmt = output_format.lower()

    if fmt in {"jpg", "jpeg"}:
        if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert("RGB")
        img.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)
    elif fmt == "png":
        img.save(output_path, "PNG", optimize=True)
    else:
        img.save(output_path)


def resize_one_image(
    input_file,
    output_path,
    mode,
    percent=100,
    target_width=None,
    target_height=None,
    keep_ratio=True,
    output_format="same",
    jpeg_quality=95,
):
    if Image is None:
        raise RuntimeError("缺少 Pillow，请先安装：pip install Pillow")

    with Image.open(input_file) as img:
        new_size = calculate_new_size(
            img.width,
            img.height,
            mode,
            percent=percent,
            target_width=target_width,
            target_height=target_height,
            keep_ratio=keep_ratio,
        )

        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        save_image(resized, output_path, output_format=output_format, jpeg_quality=jpeg_quality)

        return new_size


def resize_images(
    files,
    output_dir=None,
    mode="按百分比",
    percent=50,
    target_width=None,
    target_height=None,
    keep_ratio=True,
    output_format="same",
    suffix_text="_resized",
    overwrite=False,
    jpeg_quality=95,
    progress_callback=None,
):
    results = []

    for index, file_path in enumerate(files, start=1):
        output_path = build_output_path(file_path, output_dir, suffix_text, output_format, overwrite)
        status = "成功"

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if os.path.exists(output_path) and not overwrite:
                status = "跳过：文件已存在"
            else:
                resize_one_image(
                    file_path,
                    output_path,
                    mode,
                    percent=percent,
                    target_width=target_width,
                    target_height=target_height,
                    keep_ratio=keep_ratio,
                    output_format=output_format,
                    jpeg_quality=jpeg_quality,
                )

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


class ImageResizeFrame(ttk.Frame):
    """图片尺寸调整页面。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.image_files = []
        self.output_dir = tk.StringVar(value="")
        self.recursive_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.keep_ratio_var = tk.BooleanVar(value=True)
        self.mode_var = tk.StringVar(value="按百分比")
        self.percent_var = tk.IntVar(value=50)
        self.width_var = tk.StringVar(value="")
        self.height_var = tk.StringVar(value="")
        self.output_format_var = tk.StringVar(value="same")
        self.suffix_var = tk.StringVar(value="_resized")
        self.jpeg_quality_var = tk.IntVar(value=95)
        self._create_widgets()

    def _create_widgets(self):
        setting = ttk.LabelFrame(self, text="尺寸调整设置", padding=10)
        setting.pack(fill=tk.X)

        ttk.Label(setting, text="输出目录：").grid(row=0, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(setting, textvariable=self.output_dir)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(setting, text="选择", command=self.choose_output_dir).grid(row=0, column=2, padx=5)

        ttk.Label(setting, text="调整方式：").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        mode_combo = ttk.Combobox(
            setting,
            textvariable=self.mode_var,
            values=["按百分比", "按宽度", "按高度", "指定宽高"],
            width=12,
            state="readonly"
        )
        mode_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(8, 0))

        ttk.Label(setting, text="百分比：").grid(row=1, column=1, sticky=tk.W, padx=(120, 0), pady=(8, 0))
        ttk.Spinbox(setting, from_=1, to=500, textvariable=self.percent_var, width=6).grid(
            row=1, column=1, sticky=tk.W, padx=(180, 0), pady=(8, 0)
        )

        ttk.Label(setting, text="宽：").grid(row=1, column=1, sticky=tk.W, padx=(250, 0), pady=(8, 0))
        ttk.Entry(setting, textvariable=self.width_var, width=8).grid(
            row=1, column=1, sticky=tk.W, padx=(285, 0), pady=(8, 0)
        )

        ttk.Label(setting, text="高：").grid(row=1, column=1, sticky=tk.W, padx=(360, 0), pady=(8, 0))
        ttk.Entry(setting, textvariable=self.height_var, width=8).grid(
            row=1, column=1, sticky=tk.W, padx=(395, 0), pady=(8, 0)
        )

        ttk.Checkbutton(setting, text="保持比例", variable=self.keep_ratio_var).grid(
            row=1, column=2, sticky=tk.W, padx=5, pady=(8, 0)
        )

        ttk.Label(setting, text="输出格式：").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        fmt_combo = ttk.Combobox(
            setting,
            textvariable=self.output_format_var,
            values=["same", "jpg", "png"],
            width=10,
            state="readonly"
        )
        fmt_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=(8, 0))

        ttk.Label(setting, text="文件名后缀：").grid(row=2, column=1, sticky=tk.W, padx=(120, 0), pady=(8, 0))
        ttk.Entry(setting, textvariable=self.suffix_var, width=14).grid(
            row=2, column=1, sticky=tk.W, padx=(200, 0), pady=(8, 0)
        )

        ttk.Label(setting, text="JPG质量：").grid(row=2, column=1, sticky=tk.W, padx=(330, 0), pady=(8, 0))
        ttk.Spinbox(setting, from_=1, to=100, textvariable=self.jpeg_quality_var, width=6).grid(
            row=2, column=1, sticky=tk.W, padx=(400, 0), pady=(8, 0)
        )

        ttk.Checkbutton(setting, text="添加文件夹时包含子文件夹", variable=self.recursive_var).grid(
            row=2, column=2, sticky=tk.W, padx=5, pady=(8, 0)
        )

        ttk.Checkbutton(setting, text="覆盖已存在文件", variable=self.overwrite_var).grid(
            row=3, column=1, sticky=tk.W, padx=5, pady=(8, 0)
        )

        setting.grid_columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self, padding=(0, 10))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="添加图片文件", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="添加文件夹", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(btn_frame, text="开始调整", command=self.start_resize)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=5)

        tip = ttk.Label(
            self,
            text="说明：输出格式 same 表示保持原格式。默认在文件名后加 _resized，避免覆盖原图。",
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

        list_frame = ttk.LabelFrame(self, text="待调整图片", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("input", "size", "output", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        self.tree.heading("input", text="原图片")
        self.tree.heading("size", text="原尺寸")
        self.tree.heading("output", text="输出图片")
        self.tree.heading("status", text="状态")
        self.tree.column("input", width=320, anchor=tk.W)
        self.tree.column("size", width=100, anchor=tk.CENTER)
        self.tree.column("output", width=320, anchor=tk.W)
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
        suffix_text = self.suffix_var.get() or "_resized"
        output_format = self.output_format_var.get()
        overwrite = self.overwrite_var.get()

        for file_path in self.image_files:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    file_path,
                    get_image_size(file_path),
                    build_output_path(file_path, out_dir, suffix_text, output_format, overwrite),
                    "等待调整"
                )
            )

    def clear_files(self):
        self.image_files.clear()
        self.refresh_tree()
        self.progress["value"] = 0
        self.status_label.config(text="已清空")

    def start_resize(self):
        if not self.image_files:
            messagebox.showwarning("提示", "请先添加图片文件。")
            return

        mode = self.mode_var.get()
        out_dir = self.output_dir.get().strip() or None
        suffix_text = self.suffix_var.get() or "_resized"
        output_format = self.output_format_var.get()
        overwrite = self.overwrite_var.get()
        keep_ratio = self.keep_ratio_var.get()

        try:
            percent = int(self.percent_var.get())
            if percent <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("输入错误", "百分比必须是大于 0 的整数。")
            return

        width = self.width_var.get().strip()
        height = self.height_var.get().strip()

        try:
            target_width = int(width) if width else None
            target_height = int(height) if height else None
            if target_width is not None and target_width <= 0:
                raise ValueError
            if target_height is not None and target_height <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("输入错误", "宽度和高度必须是大于 0 的整数。")
            return

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
        self.status_label.config(text="调整中...")

        def progress_callback(index, total, item):
            self.after(0, lambda idx=index, total=total, data=item: self._update_one_result(idx, total, data))

        def worker():
            try:
                resize_images(
                    list(self.image_files),
                    output_dir=out_dir,
                    mode=mode,
                    percent=percent,
                    target_width=target_width,
                    target_height=target_height,
                    keep_ratio=keep_ratio,
                    output_format=output_format,
                    suffix_text=suffix_text,
                    overwrite=overwrite,
                    jpeg_quality=quality,
                    progress_callback=progress_callback,
                )
                self.after(0, lambda: self._finish_resize("调整完成"))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._finish_resize(f"调整失败：{msg}", error=True))

        threading.Thread(target=worker, daemon=True).start()

    def _update_one_result(self, index, total, item):
        children = self.tree.get_children()
        if 0 <= index - 1 < len(children):
            old_values = list(self.tree.item(children[index - 1], "values"))
            old_size = old_values[1] if len(old_values) > 1 else ""
            self.tree.item(children[index - 1], values=(item["input"], old_size, item["output"], item["status"]))
            self.tree.see(children[index - 1])

        self.progress["value"] = index
        self.status_label.config(text=f"{index}/{total}")

    def _finish_resize(self, msg, error=False):
        self.start_btn.config(state=tk.NORMAL)
        self.status_label.config(text=msg)

        if error:
            messagebox.showerror("调整失败", msg)
        else:
            messagebox.showinfo("完成", msg)
