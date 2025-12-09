"""
文本库 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.media import TextItem, TextItemVersion
from app.services.storage import storage_service

router = APIRouter()


class TextCreateRequest(BaseModel):
    """创建文本请求"""
    project_id: str
    name: str
    content: str
    category: str = ""
    description: str = ""


class TextUpdateRequest(BaseModel):
    """更新文本请求"""
    name: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    save_version: bool = False  # 是否保存为新版本
    version_description: str = ""  # 版本描述


class TextVersionRestoreRequest(BaseModel):
    """恢复版本请求"""
    version_id: str


@router.get("")
async def list_texts(project_id: str, category: Optional[str] = None):
    """获取项目所有文本"""
    texts = storage_service.get_text_items(project_id)
    if category:
        texts = [t for t in texts if t.category == category]
    return {"texts": texts}


@router.get("/{text_id}")
async def get_text(text_id: str):
    """获取单个文本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    return text


@router.post("")
async def create_text(request: TextCreateRequest):
    """创建文本"""
    text = TextItem(
        project_id=request.project_id,
        name=request.name,
        content=request.content,
        category=request.category
    )
    
    # 创建初始版本
    initial_version = TextItemVersion(
        content=request.content,
        description=request.description or "初始版本"
    )
    text.versions.append(initial_version)
    
    storage_service.save_text_item(text)
    return text


@router.put("/{text_id}")
async def update_text(text_id: str, request: TextUpdateRequest):
    """更新文本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    
    if request.name is not None:
        text.name = request.name
    if request.category is not None:
        text.category = request.category
    
    if request.content is not None:
        # 如果需要保存版本且内容有变化
        if request.save_version and text.content != request.content:
            version = TextItemVersion(
                content=request.content,
                description=request.version_description or f"更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            text.versions.append(version)
        text.content = request.content
    
    text.updated_at = datetime.now()
    storage_service.save_text_item(text)
    
    return text


@router.post("/{text_id}/versions")
async def save_version(text_id: str, description: str = ""):
    """保存当前内容为新版本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    
    version = TextItemVersion(
        content=text.content,
        description=description or f"版本 {len(text.versions) + 1}"
    )
    text.versions.append(version)
    text.updated_at = datetime.now()
    
    storage_service.save_text_item(text)
    
    return {"message": "版本已保存", "version": version}


@router.get("/{text_id}/versions")
async def list_versions(text_id: str):
    """获取文本的所有版本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    
    return {"versions": text.versions}


@router.post("/{text_id}/restore")
async def restore_version(text_id: str, request: TextVersionRestoreRequest):
    """恢复到指定版本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    
    # 查找版本
    version = None
    for v in text.versions:
        if v.id == request.version_id:
            version = v
            break
    
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    # 保存当前内容为新版本（恢复前备份）
    backup_version = TextItemVersion(
        content=text.content,
        description=f"恢复前备份 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    text.versions.append(backup_version)
    
    # 恢复内容
    text.content = version.content
    text.updated_at = datetime.now()
    
    storage_service.save_text_item(text)
    
    return {"message": "版本已恢复", "text": text}


@router.delete("/{text_id}/versions/{version_id}")
async def delete_version(text_id: str, version_id: str):
    """删除指定版本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    
    # 至少保留一个版本
    if len(text.versions) <= 1:
        raise HTTPException(status_code=400, detail="无法删除最后一个版本")
    
    text.versions = [v for v in text.versions if v.id != version_id]
    text.updated_at = datetime.now()
    
    storage_service.save_text_item(text)
    
    return {"message": "版本已删除"}


@router.delete("/{text_id}")
async def delete_text(text_id: str):
    """删除文本"""
    text = storage_service.get_text_item(text_id)
    if not text:
        raise HTTPException(status_code=404, detail="文本不存在")
    
    storage_service.delete_text_item(text_id)
    return {"message": "文本已删除"}


@router.delete("")
async def delete_all_texts(project_id: str, category: Optional[str] = None):
    """删除项目所有文本"""
    texts = storage_service.get_text_items(project_id)
    if category:
        texts = [t for t in texts if t.category == category]
    
    for text in texts:
        storage_service.delete_text_item(text.id)
    
    return {"message": f"已删除 {len(texts)} 个文本"}

