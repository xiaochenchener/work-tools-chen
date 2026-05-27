import tkinter as tk
from tkinter import ttk

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None

from .pdf_checker import PDFCheckerFrame
from .word_to_pdf import WordToPdfFrame
from .pdf_merge import PDFMergeFrame
from .image_convert import ImageConvertFrame
from .image_resize import ImageResizeFrame


class WorkToolsChenApp:
    """work-tools-chen 主程序：开始菜单 + 工具页面切换。"""

    def __init__(self, root):
        self.root = root
        self.root.title("work-tools-chen")
        self.root.geometry("1080x720")
        self.root.minsize(980, 620)

        self.container = ttk.Frame(self.root, padding=16)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.show_home()

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def set_title(self, title: str):
        self.root.title(f"work-tools-chen - {title}")

    def show_home(self):
        self.clear_container()
        self.set_title("开始菜单")

        outer = ttk.Frame(self.container)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text="work-tools-chen",
            font=("Microsoft YaHei UI", 24, "bold")
        )
        title.pack(pady=(18, 8))

        subtitle = ttk.Label(
            outer,
            text="请选择要使用的工具",
            font=("Microsoft YaHei UI", 12)
        )
        subtitle.pack(pady=(0, 20))

        cards = ttk.Frame(outer)
        cards.pack(fill=tk.BOTH, expand=True)

        tools = [
            {
                "title": "PDF 正文字数与超链接检查",
                "description": "统计 PDF 全文字数、扣除原表初始字数、判断是否超限，并检测真实链接和文本 URL。",
                "button_text": "进入 PDF 检查",
                "command": self.show_pdf_checker,
            },
            {
                "title": "批量 Word 转 PDF",
                "description": "批量转换 .doc / .docx 文件为 PDF，可选择输出目录，支持 Microsoft Word 或 LibreOffice。",
                "button_text": "进入 Word 转 PDF",
                "command": self.show_word_to_pdf,
            },
            {
                "title": "多个 PDF 合并",
                "description": "把多个 PDF 按当前列表顺序合并，可按名称、路径、时间、大小、页数排序，并支持手动调整顺序。",
                "button_text": "进入 PDF 合并",
                "command": self.show_pdf_merge,
            },
            {
                "title": "JPG / PNG 格式互转",
                "description": "批量将 JPG、JPEG、PNG 图片互相转换，支持输出目录、覆盖设置和 JPG 质量设置。",
                "button_text": "进入格式转换",
                "command": self.show_image_convert,
            },
            {
                "title": "图片尺寸调整",
                "description": "批量放大或缩小图片，支持按百分比、按宽度、按高度、指定宽高调整。",
                "button_text": "进入尺寸调整",
                "command": self.show_image_resize,
            },
        ]

        for i, tool in enumerate(tools):
            row = i // 2
            col = i % 2
            self._tool_card(
                cards,
                title=tool["title"],
                description=tool["description"],
                button_text=tool["button_text"],
                command=tool["command"],
                row=row,
                column=col,
            )

        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)

        footer = ttk.Label(
            outer,
            text="建议后续所有小工具都按这种结构继续加入：一个菜单入口 + 一个功能页面。",
            foreground="gray"
        )
        footer.pack(side=tk.BOTTOM, pady=8)

    def _tool_card(self, parent, title, description, button_text, command, row, column):
        card = ttk.LabelFrame(parent, text=title, padding=16)
        card.grid(row=row, column=column, padx=12, pady=8, sticky="nsew")
        card.configure(height=150)
        card.grid_propagate(False)

        desc = ttk.Label(card, text=description, wraplength=420, justify=tk.LEFT)
        desc.pack(fill=tk.X, pady=(4, 14))

        btn = ttk.Button(card, text=button_text, command=command)
        btn.pack(side=tk.BOTTOM, pady=4)

    def _add_back_button(self):
        top = ttk.Frame(self.container)
        top.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(top, text="← 返回开始菜单", command=self.show_home).pack(side=tk.LEFT)

    def show_pdf_checker(self):
        self.clear_container()
        self.set_title("PDF 检查")
        self._add_back_button()
        PDFCheckerFrame(self.container).pack(fill=tk.BOTH, expand=True)

    def show_word_to_pdf(self):
        self.clear_container()
        self.set_title("Word 转 PDF")
        self._add_back_button()
        WordToPdfFrame(self.container).pack(fill=tk.BOTH, expand=True)

    def show_pdf_merge(self):
        self.clear_container()
        self.set_title("PDF 合并")
        self._add_back_button()
        PDFMergeFrame(self.container).pack(fill=tk.BOTH, expand=True)

    def show_image_convert(self):
        self.clear_container()
        self.set_title("图片格式转换")
        self._add_back_button()
        ImageConvertFrame(self.container).pack(fill=tk.BOTH, expand=True)

    def show_image_resize(self):
        self.clear_container()
        self.set_title("图片尺寸调整")
        self._add_back_button()
        ImageResizeFrame(self.container).pack(fill=tk.BOTH, expand=True)


def run_app():
    """启动程序。优先使用 TkinterDnD.Tk，这样拖拽功能可用。"""
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    WorkToolsChenApp(root)
    root.mainloop()
