"""
风格 API 路由
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.models.style import Style, StyleImage, TextStyleVersion, IMAGE_STYLE_PRESETS, TEXT_STYLE_PRESETS
from app.services.storage import storage_service
from app.services.dashscope.text_to_image import TextToImageService

router = APIRouter()


class StyleCreateRequest(BaseModel):
    """风格创建请求"""
    project_id: str
    name: str
    style_type: str = "image"  # "image" 或 "text"
    # 图片风格字段
    style_prompt: str = ""
    negative_prompt: str = ""
    preset_name: Optional[str] = None
    # 文本风格字段
    text_style_content: str = ""
    text_preset_name: Optional[str] = None


class StyleGenerateRequest(BaseModel):
    """风格图片生成请求"""
    group_index: int = 0
    style_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None


class StyleGenerateAllRequest(BaseModel):
    """风格所有组图片生成请求"""
    style_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: int = 3


class StyleUpdateRequest(BaseModel):
    """风格更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    style_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    selected_group_index: Optional[int] = None
    is_selected: Optional[bool] = None
    # 文本风格字段
    text_style_content: Optional[str] = None


class TextStyleVersionRequest(BaseModel):
    """文本风格版本保存请求"""
    version_name: str
    content: str
    modified_info: str = ""


@router.get("/presets")
async def get_style_presets():
    """获取预设风格列表"""
    return {
        "image_presets": IMAGE_STYLE_PRESETS,
        "text_presets": TEXT_STYLE_PRESETS
    }


@router.post("/create")
async def create_style(request: StyleCreateRequest):
    """创建新风格"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    style = Style(
        project_id=request.project_id,
        name=request.name,
        style_type=request.style_type
    )
    
    if request.style_type == "image":
        # 图片风格
        style_prompt = request.style_prompt
        negative_prompt = request.negative_prompt
        preset_name = request.preset_name
        
        if preset_name and preset_name in IMAGE_STYLE_PRESETS:
            preset = IMAGE_STYLE_PRESETS[preset_name]
            if not style_prompt:
                style_prompt = preset["prompt"]
            if not negative_prompt:
                negative_prompt = preset["negative_prompt"]
        
        style.style_prompt = style_prompt
        style.negative_prompt = negative_prompt
        style.preset_name = preset_name
    else:
        # 文本风格
        text_content = request.text_style_content
        text_preset_name = request.text_preset_name
        
        if text_preset_name and text_preset_name in TEXT_STYLE_PRESETS:
            preset = TEXT_STYLE_PRESETS[text_preset_name]
            if not text_content:
                text_content = preset["content"]
        
        style.text_style_content = text_content
        style.text_preset_name = text_preset_name
    
    storage_service.save_style(style)
    
    # 添加到项目
    if not hasattr(project, 'style_ids'):
        project.style_ids = []
    project.style_ids.append(style.id)
    storage_service.save_project(project)
    
    return style


@router.get("")
async def list_styles(project_id: str):
    """获取项目所有风格"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    styles = []
    style_ids = getattr(project, 'style_ids', [])
    for style_id in style_ids:
        style = storage_service.get_style(style_id)
        if style:
            styles.append(style)
    
    return {"styles": styles}


@router.get("/{style_id}")
async def get_style(style_id: str):
    """获取风格详情"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    return style


@router.put("/{style_id}")
async def update_style(style_id: str, request: StyleUpdateRequest):
    """更新风格信息"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    
    # 如果设置为选中，取消其他风格的选中状态
    if request.is_selected:
        project = storage_service.get_project(style.project_id)
        if project:
            for sid in getattr(project, 'style_ids', []):
                if sid != style_id:
                    other_style = storage_service.get_style(sid)
                    if other_style and other_style.is_selected:
                        other_style.is_selected = False
                        storage_service.save_style(other_style)
    
    for key, value in update_data.items():
        if value is not None:
            setattr(style, key, value)
    
    storage_service.save_style(style)
    return style


@router.post("/{style_id}/save-text-version")
async def save_text_style_version(style_id: str, request: TextStyleVersionRequest):
    """保存文本风格版本"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    if style.style_type != "text":
        raise HTTPException(status_code=400, detail="仅文本风格支持版本管理")
    
    version = TextStyleVersion(
        name=request.version_name,
        content=request.content,
        modified_info=request.modified_info
    )
    
    style.text_style_versions.insert(0, version)
    style.text_style_content = request.content
    storage_service.save_style(style)
    
    return {"version": version, "message": "版本已保存"}


@router.post("/{style_id}/load-text-version/{version_id}")
async def load_text_style_version(style_id: str, version_id: str):
    """加载文本风格版本"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    version = next((v for v in style.text_style_versions if v.id == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    style.text_style_content = version.content
    storage_service.save_style(style)
    
    return {"message": "版本已加载", "content": version.content}


@router.post("/{style_id}/generate")
async def generate_style_images(style_id: str, request: StyleGenerateRequest):
    """生成风格图片（单组）- 仅图片风格"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    if style.style_type != "image":
        raise HTTPException(status_code=400, detail="仅图片风格支持图片生成")
    
    t2i_service = TextToImageService()
    
    style_prompt = request.style_prompt or style.style_prompt
    negative_prompt = request.negative_prompt or style.negative_prompt
    
    try:
        # 服务层会自动处理 OSS 上传
        url = await t2i_service.generate(style_prompt, negative_prompt=negative_prompt, project_id=style.project_id)
        
        image = StyleImage(
            group_index=request.group_index,
            url=url,
            prompt_used=style_prompt
        )
        
        while len(style.image_groups) <= request.group_index:
            style.image_groups.append(StyleImage(group_index=len(style.image_groups)))
        
        style.image_groups[request.group_index] = image
        
        if request.style_prompt:
            style.style_prompt = request.style_prompt
        if request.negative_prompt is not None:
            style.negative_prompt = request.negative_prompt
        
        storage_service.save_style(style)
        
        return {"image": image}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.post("/{style_id}/generate-all")
async def generate_all_style_images(style_id: str, request: StyleGenerateAllRequest):
    """并发生成风格所有组图片 - 仅图片风格"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    if style.style_type != "image":
        raise HTTPException(status_code=400, detail="仅图片风格支持图片生成")
    
    t2i_service = TextToImageService()
    
    style_prompt = request.style_prompt or style.style_prompt
    negative_prompt = request.negative_prompt or style.negative_prompt
    
    async def generate_group(group_index: int) -> StyleImage:
        # 服务层会自动处理 OSS 上传
        url = await t2i_service.generate(style_prompt, negative_prompt=negative_prompt, project_id=style.project_id)
        return StyleImage(
            group_index=group_index,
            url=url,
            prompt_used=style_prompt
        )
    
    try:
        tasks = [generate_group(i) for i in range(request.group_count)]
        image_groups = await asyncio.gather(*tasks)
        
        style.image_groups = list(image_groups)
        
        if request.style_prompt:
            style.style_prompt = request.style_prompt
        if request.negative_prompt is not None:
            style.negative_prompt = request.negative_prompt
        
        storage_service.save_style(style)
        
        return {"image_groups": image_groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.post("/{style_id}/select")
async def select_style(style_id: str, group_index: int = 0):
    """选择风格及其图片组"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    # 取消其他风格的选中状态
    project = storage_service.get_project(style.project_id)
    if project:
        for sid in getattr(project, 'style_ids', []):
            other_style = storage_service.get_style(sid)
            if other_style:
                other_style.is_selected = (sid == style_id)
                if sid == style_id:
                    other_style.selected_group_index = group_index
                storage_service.save_style(other_style)
    
    return storage_service.get_style(style_id)


@router.delete("/{style_id}")
async def delete_style(style_id: str):
    """删除风格"""
    style = storage_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="风格不存在")
    
    project = storage_service.get_project(style.project_id)
    if project and hasattr(project, 'style_ids') and style_id in project.style_ids:
        project.style_ids.remove(style_id)
        storage_service.save_project(project)
    
    storage_service.delete_style(style_id)
    return {"message": "风格已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_styles(project_id: str):
    """删除项目的所有风格"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    deleted_count = 0
    style_ids = getattr(project, 'style_ids', [])
    for style_id in style_ids[:]:
        storage_service.delete_style(style_id)
        deleted_count += 1
    
    project.style_ids = []
    storage_service.save_project(project)
    
    return {"message": f"已删除 {deleted_count} 个风格"}
