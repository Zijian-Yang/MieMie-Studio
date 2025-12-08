"""
文件解析服务
支持 md, txt, docx, pdf 等文件格式
"""

import io
from fastapi import UploadFile


async def parse_file(file: UploadFile) -> str:
    """
    解析上传的文件，返回文本内容
    
    Args:
        file: 上传的文件
        
    Returns:
        文件的文本内容
    """
    filename = file.filename or ""
    content = await file.read()
    
    # 根据文件扩展名选择解析方式
    if filename.endswith('.txt') or filename.endswith('.md'):
        return parse_text(content)
    elif filename.endswith('.docx'):
        return parse_docx(content)
    elif filename.endswith('.pdf'):
        return parse_pdf(content)
    else:
        # 尝试作为纯文本解析
        return parse_text(content)


def parse_text(content: bytes) -> str:
    """解析纯文本文件"""
    # 尝试不同的编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    # 如果都失败，使用 utf-8 并忽略错误
    return content.decode('utf-8', errors='ignore')


def parse_docx(content: bytes) -> str:
    """解析 Word 文档"""
    try:
        from docx import Document
        
        doc = Document(io.BytesIO(content))
        
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        
        return '\n\n'.join(paragraphs)
    except ImportError:
        raise ValueError("需要安装 python-docx 库来解析 Word 文档")
    except Exception as e:
        raise ValueError(f"Word 文档解析失败: {str(e)}")


def parse_pdf(content: bytes) -> str:
    """解析 PDF 文档"""
    try:
        import pypdf
        
        reader = pypdf.PdfReader(io.BytesIO(content))
        
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        return '\n\n'.join(text_parts)
    except ImportError:
        raise ValueError("需要安装 pypdf 库来解析 PDF 文档")
    except Exception as e:
        raise ValueError(f"PDF 文档解析失败: {str(e)}")
