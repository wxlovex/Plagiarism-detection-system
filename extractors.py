# filename: extractors.py
import fitz  # PyMuPDF
import docx
import re

def extract_text(file_storage):
    """支持 txt / pdf / docx，返回全文"""
    filename = file_storage.filename.lower()
    content = file_storage.read()

    if filename.endswith('.txt'):
        return content.decode('utf-8')
    elif filename.endswith('.pdf'):
        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    elif filename.endswith('.docx'):
        doc = docx.Document(file_storage)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        raise ValueError("仅支持 .txt / .pdf / .docx")

def extract_acknowledgements(text):
    """自动提取致谢段落（中文/英文关键词）"""
    keywords = ['致谢', '感谢', 'Acknowledgements', '致 谢', 'Acknowledgment']
    pattern = re.compile(r'(?i)(' + '|'.join(keywords) + r')[\s：:]*', re.MULTILINE)
    match = pattern.search(text)
    if match:
        start = match.end()
        # 取后面 1500 字符，或到下一个大标题
        end = text.find('\n\n\n', start)
        if end == -1:
            end = start + 1500
        return text[start:end].strip()
    return text  # 没找到就返回全文（兼容旧用法）