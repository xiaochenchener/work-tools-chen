import os
import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from io import BytesIO
from PIL import Image
import threading

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from rapidocr import RapidOCR
    RAPIDOCR_AVAILABLE = True
except ImportError:
    RAPIDOCR_AVAILABLE = False
    RapidOCR = None


def resource_base_dir():
    """兼容 PyInstaller 打包后的资源目录。"""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_model_paths():
    """
    按优先级查找本地 ONNX 模型路径：
    1. PyInstaller 打包后的临时目录
    2. 项目根目录下的 models/ 文件夹
    """
    base_dir = resource_base_dir()
    models_dir = os.path.join(base_dir, "models")

    det_path = os.path.join(models_dir, "ch_PP-OCRv4_det_infer.onnx")
    rec_path = os.path.join(models_dir, "ch_PP-OCRv4_rec_infer.onnx")
    cls_path = os.path.join(models_dir, "ch_ppocr_mobile_v2.0_cls_infer.onnx")

    missing = []
    for p in [det_path, rec_path, cls_path]:
        if not os.path.exists(p):
            missing.append(os.path.basename(p))

    if missing:
        return None, f"缺少模型文件：{', '.join(missing)}，请将 models/ 文件夹放在程序同级目录"

    return {"det": det_path, "rec": rec_path, "cls": cls_path}, None


def init_ocr_engine():
    """初始化 RapidOCR。失败时返回 None 和提示信息，不影响普通 PDF 检查。"""
    if not RAPIDOCR_AVAILABLE:
        return None, "未安装 rapidocr，OCR 功能不可用。"

    model_paths, err_msg = get_model_paths()
    if not model_paths:
        return None, err_msg

    try:
        params = {
            "Det.model_path": model_paths["det"],
            "Rec.model_path": model_paths["rec"],
            "Cls.model_path": model_paths["cls"],
        }
        engine = RapidOCR(params=params)
        return engine, "RapidOCR 引擎初始化成功。"
    except Exception as e:
        return None, f"RapidOCR 初始化失败：{e}"


def extract_ocr_text(doc, engine):
    """
    智能 OCR：只对扫描页和嵌入图片进行识别，正常文字页跳过。
    返回：(识别到的全部文本字符串, OCR处理的页数)
    """
    if engine is None:
        return "", 0

    ocr_text = ""
    ocr_page_count = 0

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_text = page.get_text()
        has_embedded_images = len(page.get_images(full=True)) > 0

        if len(page_text.strip()) < 30:
            try:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                output = engine(img)
                if output and output.txts:
                    page_ocr = "\n".join(output.txts)
                    if page_ocr.strip():
                        ocr_text += page_ocr + "\n"
                        ocr_page_count += 1
            except Exception:
                pass

        elif has_embedded_images:
            image_list = page.get_images(full=True)
            img_ocr_texts = []
            for img_info in image_list:
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_data = pix.tobytes("png")
                    pil_img = Image.open(BytesIO(img_data))
                    output = engine(pil_img)
                    if output and output.txts:
                        img_text = "\n".join(output.txts)
                        if img_text.strip():
                            img_ocr_texts.append(img_text)
                    pix = None
                except Exception:
                    continue

            if img_ocr_texts:
                ocr_text += "\n".join(img_ocr_texts) + "\n"
                ocr_page_count += 1

    return ocr_text, ocr_page_count


def count_total_chars(text):
    """
    字数 = 中文字符 + 英文单词 + 数字串
    不计入：标点符号、空格、换行符。
    """
    chinese_chars = re.findall(
        r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3007]",
        text
    )

    english_words = re.findall(
        r"[a-zA-Z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff]+"
        r"(?:[-'][a-zA-Z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff]+)*",
        text
    )

    number_words = re.findall(r"\d+", text)

    breakdown = {
        "chinese": len(chinese_chars),
        "english_words": len(english_words),
        "number_words": len(number_words),
    }

    total = len(chinese_chars) + len(english_words) + len(number_words)
    return total, breakdown


def detect_pdf_real_links(doc):
    """使用 page.get_links() 检测 PDF 中的真实超链接。"""
    real_links = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        links = page.get_links()
        for link in links:
            if "uri" in link:
                real_links.append({
                    "page": page_num + 1,
                    "uri": link["uri"]
                })
    return real_links


def detect_text_urls(text):
    """检测文本中的 URL。"""
    url_pattern = r"(https?://[^\s，。；、）)\]]+|www\.[^\s，。；、）)\]]+|doi\.org/[^\s，。；、）)\]]+)"
    return re.findall(url_pattern, text)


def analyze_pdf(pdf_path, initial_word_count, word_limit, engine=None):
    """综合分析单个 PDF 文件。"""
    result = {
        "file_name": os.path.basename(pdf_path),
        "file_path": pdf_path,
        "total_pages": 0,
        "full_char_count": 0,
        "initial_word_count": initial_word_count,
        "body_char_count": 0,
        "word_limit": word_limit,
        "over_limit": False,
        "has_any_links": False,
        "real_pdf_link_count": 0,
        "text_url_count": 0,
        "real_pdf_links": [],
        "text_urls": [],
        "ocr_used": False,
        "ocr_char_count": 0,
        "ocr_page_count": 0,
        "status": "检测完成"
    }

    if fitz is None:
        result["status"] = "错误：未安装 PyMuPDF，请先运行 pip install PyMuPDF"
        return result

    if not os.path.exists(pdf_path):
        result["status"] = "错误：文件不存在"
        return result

    if not pdf_path.lower().endswith(".pdf"):
        result["status"] = "错误：不是 PDF 文件"
        return result

    try:
        doc = fitz.open(pdf_path)
        result["total_pages"] = len(doc)

        full_text = ""
        for page in doc:
            full_text += page.get_text()

        if RAPIDOCR_AVAILABLE and engine is not None:
            ocr_text, ocr_page_count = extract_ocr_text(doc, engine)
            if ocr_text.strip():
                full_text += "\n" + ocr_text
            result["ocr_used"] = True
            ocr_count, _ = count_total_chars(ocr_text)
            result["ocr_char_count"] = ocr_count
            result["ocr_page_count"] = ocr_page_count

        if not full_text.strip():
            result["status"] = "警告：PDF 无文本，可能是扫描版"
            doc.close()
            return result

        pdf_word_count, _ = count_total_chars(full_text)
        result["full_char_count"] = pdf_word_count

        body_count = pdf_word_count - initial_word_count
        if body_count < 0:
            body_count = 0
        result["body_char_count"] = body_count
        result["over_limit"] = result["body_char_count"] > word_limit

        real_links = detect_pdf_real_links(doc)
        result["real_pdf_links"] = real_links
        result["real_pdf_link_count"] = len(real_links)
        doc.close()

        text_urls = detect_text_urls(full_text)
        result["text_urls"] = text_urls
        result["text_url_count"] = len(text_urls)
        result["has_any_links"] = (len(real_links) > 0) or (len(text_urls) > 0)
        result["status"] = "检测完成"

    except fitz.FileDataError:
        result["status"] = "错误：PDF 文件损坏或无法解析"
    except fitz.PasswordError:
        result["status"] = "错误：PDF 已加密，无法读取"
    except ValueError as ve:
        result["status"] = f"错误：{str(ve)}"
    except Exception as e:
        result["status"] = f"错误：{str(e)}"

    return result


class PDFCheckerFrame(ttk.Frame):
    """PDF 检查器页面。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.pdf_files = []
        self.ocr_engine = None
        self.ocr_status = "OCR 尚未初始化。"
        self._create_widgets()
        self._init_ocr_async()

    def _create_widgets(self):
        input_frame = ttk.LabelFrame(self, text="检测参数", padding=10)
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="原表初始字数：").grid(row=0, column=0, sticky=tk.W)
        self.initial_entry = ttk.Entry(input_frame, width=10)
        self.initial_entry.insert(0, "0")
        self.initial_entry.grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="正文字数上限：").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        self.limit_entry = ttk.Entry(input_frame, width=10)
        self.limit_entry.insert(0, "7000")
        self.limit_entry.grid(row=0, column=3, padx=5)

        self.ocr_label = ttk.Label(input_frame, text="OCR 初始化中...", foreground="gray")
        self.ocr_label.grid(row=0, column=4, padx=(20, 0), sticky=tk.W)

        btn_frame = ttk.Frame(self, padding=(0, 10))
        btn_frame.pack(fill=tk.X)

        self.add_btn = ttk.Button(btn_frame, text="添加 PDF 文件", command=self.on_add_files)
        self.add_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(btn_frame, text="开始检测", command=self.on_start_check)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(btn_frame, text="清空列表", command=self.on_clear_list)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        drop_frame = ttk.LabelFrame(self, text="PDF 拖拽区域", padding=10)
        drop_frame.pack(fill=tk.X, pady=5)

        self.drop_label = ttk.Label(
            drop_frame,
            text="可以点击“添加 PDF 文件”，也可以将一个或多个 PDF 文件拖入此处。",
            foreground="gray"
        )
        self.drop_label.pack()

        if DND_FILES is not None:
            try:
                drop_frame.drop_target_register(DND_FILES)
                drop_frame.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                self.drop_label.config(text="拖拽注册失败，请使用“添加 PDF 文件”。")
        else:
            self.drop_label.config(text="未安装 tkinterdnd2，拖拽功能不可用，请使用“添加 PDF 文件”。")

        list_frame = ttk.LabelFrame(self, text="已导入的 PDF 文件", padding=10)
        list_frame.pack(fill=tk.X, pady=5)

        self.file_listbox = tk.Listbox(list_frame, height=5)
        self.file_listbox.pack(fill=tk.X)

        result_frame = ttk.LabelFrame(self, text="检测结果", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = (
            "file_name", "total_pages", "full_char_count", "initial_word_count",
            "body_char_count", "word_limit", "over_limit", "has_any_links",
            "real_pdf_link_count", "text_url_count",
            "ocr_used", "ocr_char_count", "ocr_page_count", "status"
        )
        column_names = {
            "file_name": "文件名",
            "total_pages": "总页数",
            "full_char_count": "PDF全文字数",
            "initial_word_count": "原表初始字数",
            "body_char_count": "正文字数",
            "word_limit": "字数上限",
            "over_limit": "是否超限",
            "has_any_links": "是否存在链接",
            "real_pdf_link_count": "PDF真实链接数",
            "text_url_count": "文本URL数",
            "ocr_used": "是否启用OCR",
            "ocr_char_count": "OCR字数",
            "ocr_page_count": "OCR页数",
            "status": "状态说明"
        }

        self.result_tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=10)
        for col in columns:
            self.result_tree.heading(col, text=column_names[col])
            self.result_tree.column(col, width=100, anchor=tk.CENTER)
        self.result_tree.column("file_name", width=180, anchor=tk.W)
        self.result_tree.column("status", width=260, anchor=tk.W)

        v_scroll = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        h_scroll = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        self.result_tree.config(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.result_tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

    def _init_ocr_async(self):
        def worker():
            engine, status = init_ocr_engine()
            self.after(0, lambda: self._set_ocr_status(engine, status))

        threading.Thread(target=worker, daemon=True).start()

    def _set_ocr_status(self, engine, status):
        self.ocr_engine = engine
        self.ocr_status = status
        if engine is not None:
            self.ocr_label.config(text="OCR 可用", foreground="green")
        else:
            self.ocr_label.config(text=f"OCR 不可用：{status}", foreground="gray")

    def on_add_files(self):
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
        )
        self._add_pdf_files(files)

    def on_drop(self, event):
        files = self._parse_drop_files(event.data)
        self._add_pdf_files(files)

    def _add_pdf_files(self, files):
        for f in files:
            if f.lower().endswith(".pdf"):
                if f not in self.pdf_files:
                    self.pdf_files.append(f)
                    self.file_listbox.insert(tk.END, f)
            else:
                messagebox.showwarning("文件类型错误", f"不是 PDF 文件，已跳过：\n{f}")

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

    def on_start_check(self):
        if not self.pdf_files:
            messagebox.showwarning("提示", "请先添加或拖入 PDF 文件")
            return

        try:
            initial_word_count = int(self.initial_entry.get().strip())
            word_limit = int(self.limit_entry.get().strip())
        except ValueError:
            messagebox.showerror("输入错误", "原表初始字数、字数上限都必须是整数")
            return

        if initial_word_count < 0 or word_limit < 0:
            messagebox.showerror("输入错误", "输入的数字不能为负数")
            return

        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        self.start_btn.config(state=tk.DISABLED)
        self.add_btn.config(state=tk.DISABLED)

        def worker():
            for pdf_path in list(self.pdf_files):
                result = analyze_pdf(pdf_path, initial_word_count, word_limit, self.ocr_engine)
                self.after(0, lambda r=result: self._insert_result(r))
            self.after(0, self._finish_check)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_check(self):
        self.start_btn.config(state=tk.NORMAL)
        self.add_btn.config(state=tk.NORMAL)
        messagebox.showinfo("完成", "检测完成！")

    def _insert_result(self, result):
        values = (
            result["file_name"],
            result["total_pages"],
            result["full_char_count"],
            result["initial_word_count"],
            result["body_char_count"],
            result["word_limit"],
            "是" if result["over_limit"] else "否",
            "是" if result["has_any_links"] else "否",
            result["real_pdf_link_count"],
            result["text_url_count"],
            "是" if result["ocr_used"] else "否",
            result["ocr_char_count"],
            result["ocr_page_count"],
            result["status"]
        )
        self.result_tree.insert("", tk.END, values=values)

    def on_clear_list(self):
        self.pdf_files.clear()
        self.file_listbox.delete(0, tk.END)
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
