"""
道具 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json

from app.models.prop import Prop, PropImage
from app.services.storage import storage_service
from app.services.dashscope.llm import LLMService
from app.services.dashscope.text_to_image import TextToImageService
from app.services.dashscope.image_to_image import ImageToImageService
from typing import List as TypingList

router = APIRouter()


def build_prop_prompt(common_prompt: str, prop_prompt: str, style=None) -> tuple[str, TypingList[str]]:
    """
    构建道具生图提示词
    返回 (final_prompt, image_urls)
    - 生图提示词 = 通用提示词 + 道具提示词 + 风格提示词
    """
    prompt_parts = [common_prompt, prop_prompt]
    image_urls = []
    
    if style:
        if style.style_type == "image" and style.image_groups:
            if style.selected_group_index < len(style.image_groups):
                style_url = style.image_groups[style.selected_group_index].url
                if style_url:
                    image_urls.append(style_url)
                    prompt_parts.insert(0, "参考输入图片的艺术风格和视觉特征，")
        elif style.style_type == "text" and style.text_style_content:
            prompt_parts.append(f"使用以下风格进行生成: {style.text_style_content}")
    
    final_prompt = ", ".join([p for p in prompt_parts if p])
    return final_prompt, image_urls


class PropExtractRequest(BaseModel):
    """道具提取请求"""
    project_id: str


class PropGenerateRequest(BaseModel):
    """道具图片生成请求"""
    group_index: int = 0
    common_prompt: Optional[str] = None
    prop_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    # 风格参考
    use_style: bool = False
    style_id: Optional[str] = None


class PropGenerateAllRequest(BaseModel):
    """道具所有组图片生成请求"""
    common_prompt: Optional[str] = None
    prop_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: int = 3
    # 风格参考
    use_style: bool = False
    style_id: Optional[str] = None


class PropUpdateRequest(BaseModel):
    """道具更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    common_prompt: Optional[str] = None
    prop_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    selected_group_index: Optional[int] = None


class PropCreateRequest(BaseModel):
    """手动创建道具请求"""
    project_id: str
    name: str
    description: Optional[str] = ""
    common_prompt: Optional[str] = ""
    prop_prompt: Optional[str] = ""
    negative_prompt: Optional[str] = ""


class PropSelectImageRequest(BaseModel):
    """从图库选择图片作为道具图请求"""
    image_url: str
    group_index: int = 0


# 道具提取提示词
PROP_EXTRACT_PROMPT = """请从以下剧本中提取需要保持一致性的道具，并为每个道具生成详细信息。

【重要】只提取在多个分镜/场景中重复出现的道具！
- 如果某个物品只在一个镜头中出现一次，不需要提取
- 只提取需要跨多个镜头保持一致性的重要道具
- 例如：主角的标志性物品、贯穿剧情的重要道具等

要求：
1. 识别剧本中在多个场景重复出现的道具/物品
2. 为每个道具生成以下信息（JSON格式）：
   - name: 道具名称（简洁明确）
   - description: 道具简介（用于说明，不用于生图）
   - prop_prompt: 用于生成道具图片的提示词（中文，只描述道具本身特征）

【重要】prop_prompt 是生图提示词，必须使用中文，只描述道具物品本身：
- 物品类型和名称
- 外形和结构
- 材质和质感
- 颜色和纹理
- 尺寸比例

【禁止】prop_prompt 中绝对不能包含：
- 任何角色、人物、手
- 任何场景背景
- 任何其他物品

这是纯道具特写，用于保持视频各镜头中该道具外观的一致性。

请直接输出JSON数组格式，不要包含其他文字说明。
如果没有需要跨镜头保持一致的道具，返回空数组 []。

剧本内容：
"""


@router.post("/create")
async def create_prop(request: PropCreateRequest):
    """手动创建道具"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 创建道具
    prop = Prop(
        project_id=request.project_id,
        name=request.name,
        description=request.description or "",
        common_prompt=request.common_prompt or "高清道具图，白色背景，产品摄影风格",
        prop_prompt=request.prop_prompt or "",
        negative_prompt=request.negative_prompt or "",
    )
    
    storage_service.save_prop(prop)
    
    # 更新项目的道具列表
    if prop.id not in project.prop_ids:
        project.prop_ids.append(prop.id)
        storage_service.save_project(project)
    
    return {"prop": prop}


@router.post("/extract")
async def extract_props(request: PropExtractRequest):
    """从剧本提取道具"""
    project = storage_service.get_project(request.project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    content = project.script.processed_content or project.script.original_content
    if not content:
        raise HTTPException(status_code=400, detail="剧本内容为空")
    
    llm_service = LLMService()
    
    try:
        result = await llm_service.chat(
            prompt=PROP_EXTRACT_PROMPT + content,
            model="qwen3-max"
        )
        
        props_data = json.loads(result)
        
        props = []
        for prop_data in props_data:
            prop = Prop(
                project_id=request.project_id,
                name=prop_data.get("name", "未命名道具"),
                description=prop_data.get("description", ""),
                prop_prompt=prop_data.get("prop_prompt", "")
            )
            storage_service.save_prop(prop)
            props.append(prop)
            project.prop_ids.append(prop.id)
        
        storage_service.save_project(project)
        
        return {"props": props}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="道具提取失败，返回格式不正确")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"道具提取失败: {str(e)}")


@router.get("")
async def list_props(project_id: str):
    """获取项目所有道具"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    props = []
    for prop_id in project.prop_ids:
        prop = storage_service.get_prop(prop_id)
        if prop:
            props.append(prop)
    
    return {"props": props}


@router.get("/{prop_id}")
async def get_prop(prop_id: str):
    """获取道具详情"""
    prop = storage_service.get_prop(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="道具不存在")
    return prop


@router.put("/{prop_id}")
async def update_prop(prop_id: str, request: PropUpdateRequest):
    """更新道具信息"""
    prop = storage_service.get_prop(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="道具不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(prop, key, value)
    
    storage_service.save_prop(prop)
    return prop


@router.post("/{prop_id}/select-image")
async def select_prop_image(prop_id: str, request: PropSelectImageRequest):
    """从图库选择图片作为道具图"""
    from datetime import datetime
    
    prop = storage_service.get_prop(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="道具不存在")
    
    if not request.image_url:
        raise HTTPException(status_code=400, detail="请提供图片URL")
    
    # 创建图片组
    image_group = PropImage(
        group_index=request.group_index,
        url=request.image_url,
        prompt_used="从图库选择",
        created_at=datetime.now().isoformat()
    )
    
    # 检查组索引是否已存在
    existing_index = None
    for i, group in enumerate(prop.image_groups):
        if group.group_index == request.group_index:
            existing_index = i
            break
    
    if existing_index is not None:
        prop.image_groups[existing_index] = image_group
    else:
        prop.image_groups.append(image_group)
        prop.image_groups.sort(key=lambda x: x.group_index)
    
    # 自动选中该组
    prop.selected_group_index = request.group_index
    
    storage_service.save_prop(prop)
    
    return {"prop": prop}


@router.post("/{prop_id}/generate")
async def generate_prop_images(prop_id: str, request: PropGenerateRequest):
    """生成道具图片（单组）
    
    生图提示词构成：通用提示词 + 道具提示词 + 风格（图片或JSON）
    注意：描述(description)不参与生图
    """
    prop = storage_service.get_prop(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="道具不存在")
    
    common_prompt = request.common_prompt or prop.common_prompt
    prop_prompt = request.prop_prompt or prop.prop_prompt
    negative_prompt = request.negative_prompt or prop.negative_prompt
    
    # 检查是否使用风格参考
    style = None
    if request.use_style and request.style_id:
        style = storage_service.get_style(request.style_id)
    
    final_prompt, image_urls = build_prop_prompt(common_prompt, prop_prompt, style)
    
    try:
        if image_urls:
            i2i_service = ImageToImageService()
            url = await i2i_service.generate_with_multi_images(
                prompt=final_prompt,
                image_urls=image_urls,
                negative_prompt=negative_prompt
            )
        else:
            t2i_service = TextToImageService()
            url = await t2i_service.generate(final_prompt, negative_prompt=negative_prompt)
        
        image = PropImage(
            group_index=request.group_index,
            url=url,
            prompt_used=final_prompt
        )
        
        while len(prop.image_groups) <= request.group_index:
            prop.image_groups.append(PropImage(group_index=len(prop.image_groups)))
        
        prop.image_groups[request.group_index] = image
        
        if request.common_prompt:
            prop.common_prompt = request.common_prompt
        if request.prop_prompt:
            prop.prop_prompt = request.prop_prompt
        if request.negative_prompt is not None:
            prop.negative_prompt = request.negative_prompt
        
        storage_service.save_prop(prop)
        
        return {"image": image}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.post("/{prop_id}/generate-all")
async def generate_all_prop_images(prop_id: str, request: PropGenerateAllRequest):
    """并发生成道具所有组图片"""
    import asyncio
    
    prop = storage_service.get_prop(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="道具不存在")
    
    common_prompt = request.common_prompt or prop.common_prompt
    prop_prompt = request.prop_prompt or prop.prop_prompt
    negative_prompt = request.negative_prompt or prop.negative_prompt
    
    # 检查是否使用风格参考
    style = None
    if request.use_style and request.style_id:
        style = storage_service.get_style(request.style_id)
    
    final_prompt, image_urls = build_prop_prompt(common_prompt, prop_prompt, style)
    
    async def generate_group(group_index: int) -> PropImage:
        if image_urls:
            i2i_service = ImageToImageService()
            url = await i2i_service.generate_with_multi_images(
                prompt=final_prompt,
                image_urls=image_urls,
                negative_prompt=negative_prompt
            )
        else:
            t2i_service = TextToImageService()
            url = await t2i_service.generate(final_prompt, negative_prompt=negative_prompt)
        return PropImage(
            group_index=group_index,
            url=url,
            prompt_used=final_prompt
        )
    
    try:
        tasks = [generate_group(i) for i in range(request.group_count)]
        image_groups = await asyncio.gather(*tasks)
        
        prop.image_groups = list(image_groups)
        
        if request.common_prompt:
            prop.common_prompt = request.common_prompt
        if request.prop_prompt:
            prop.prop_prompt = request.prop_prompt
        if request.negative_prompt is not None:
            prop.negative_prompt = request.negative_prompt
        
        storage_service.save_prop(prop)
        
        return {"image_groups": image_groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.delete("/{prop_id}")
async def delete_prop(prop_id: str):
    """删除道具"""
    prop = storage_service.get_prop(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="道具不存在")
    
    project = storage_service.get_project(prop.project_id)
    if project and prop_id in project.prop_ids:
        project.prop_ids.remove(prop_id)
        storage_service.save_project(project)
    
    storage_service.delete_prop(prop_id)
    return {"message": "道具已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_props(project_id: str):
    """删除项目的所有道具"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    deleted_count = 0
    for prop_id in project.prop_ids[:]:
        storage_service.delete_prop(prop_id)
        deleted_count += 1
    
    project.prop_ids = []
    storage_service.save_project(project)
    
    return {"message": f"已删除 {deleted_count} 个道具"}
