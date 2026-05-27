# work-tools-chen

此项目为大连理工大学一个在校学生因为工作过于繁忙而开发的一个用 Python + Tkinter 写的桌面端工具集合。

当前包含：

1. PDF 正文字数与超链接检查
2. 批量 Word 转 PDF
3. 多个 PDF 合并
4. JPG / PNG 图片格式互转
5. 图片尺寸调整

## 运行方式

```bash
pip install -r requirements.txt
python main.py
```

## 项目结构

```text
work-tools-chen/
├─ main.py
├─ requirements.txt
├─ README.md
├─ models/
│  ├─ ch_PP-OCRv4_det_infer.onnx
│  ├─ ch_PP-OCRv4_rec_infer.onnx
│  └─ ch_ppocr_mobile_v2.0_cls_infer.onnx
└─ work_tools_chen/
   ├─ __init__.py
   ├─ app.py
   ├─ pdf_checker.py
   ├─ word_to_pdf.py
   ├─ pdf_merge.py
   ├─ image_convert.py
   └─ image_resize.py
```

## 功能说明

### 1. PDF 正文字数与超链接检查

用于统计 PDF 全文字数、扣除原表初始字数、判断是否超限，并检测 PDF 真实链接和文本 URL。

如果需要 OCR，请在项目根目录放置 `models/` 文件夹，包含：

```text
ch_PP-OCRv4_det_infer.onnx
ch_PP-OCRv4_rec_infer.onnx
ch_ppocr_mobile_v2.0_cls_infer.onnx
```

没有模型也能运行，只是 OCR 功能不可用；普通可复制文字的 PDF 仍然可以统计。

### 2. 批量 Word 转 PDF

Windows 推荐安装 Microsoft Word 后使用 `word` 或 `auto`。

macOS 如果是 `.docx`，推荐安装 Microsoft Word 后选择 `docx2pdf` 或 `auto`。

如果没有 Microsoft Word，可以安装 LibreOffice，然后选择 `libreoffice`。

### 3. 多个 PDF 合并

支持：

- 添加多个 PDF 文件
- 添加包含 PDF 的文件夹
- 按文件名、完整路径、修改时间、创建时间、文件大小、页数排序
- 支持升序 / 降序
- 支持置顶、上移、下移、置底
- 支持删除选中和清空列表
- 按当前列表顺序合并输出

### 4. JPG / PNG 图片格式互转

支持：

- `.jpg`
- `.jpeg`
- `.png`

PNG 转 JPG 时，如果原图有透明通道，会自动合成为白色背景。

### 5. 图片尺寸调整

支持：

- 按百分比缩放
- 按宽度缩放
- 按高度缩放
- 指定宽高
- 保持比例
- 输出格式保持原格式、JPG、PNG
- 批量处理

### 6. 鼓励与支持

如果觉得不错欢迎大家给小琛琛儿投喂一个麦麦的薯条三重奏🍟🍟🍟

如有问题欢迎联系小琛琛儿的微信：wsndliangzechen
