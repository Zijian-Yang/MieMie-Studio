"""
场景 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json

from app.models.scene import Scene, SceneImage
from app.services.storage import storage_service
from app.services.dashscope.llm import LLMService
from app.services.dashscope.text_to_image import TextToImageService
from app.services.dashscope.image_to_image import ImageToImageService
from typing import List as TypingList

router = APIRouter()


def build_scene_prompt(common_prompt: str, scene_prompt: str, style=None) -> tuple[str, TypingList[str]]:
    """
    构建场景生图提示词
    返回 (final_prompt, image_urls)
    - 生图提示词 = 通用提示词 + 场景提示词 + 风格提示词
    """
    prompt_parts = [common_prompt, scene_prompt]
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


class SceneExtractRequest(BaseModel):
    """场景提取请求"""
    project_id: str


class SceneGenerateRequest(BaseModel):
    """场景图片生成请求"""
    group_index: int = 0
    common_prompt: Optional[str] = None
    scene_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    # 风格参考
    use_style: bool = False
    style_id: Optional[str] = None


class SceneGenerateAllRequest(BaseModel):
    """场景所有组图片生成请求"""
    common_prompt: Optional[str] = None
    scene_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: int = 3
    # 风格参考
    use_style: bool = False
    style_id: Optional[str] = None


class SceneUpdateRequest(BaseModel):
    """场景更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    common_prompt: Optional[str] = None
    scene_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    selected_group_index: Optional[int] = None


# 场景提取提示词
SCENE_EXTRACT_PROMPT = """请从以下剧本中提取所有出现的场景，并为每个场景生成详细信息。

要求：
1. 识别剧本中所有不同的场景/地点
2. 为每个场景生成以下信息（JSON格式）：
   - name: 场景名称（简洁明确）
   - description: 场景简介（用于说明，不用于生图）
   - scene_prompt: 用于生成场景图片的提示词（中文，只描述场景环境特征）

【重要】scene_prompt 是生图提示词，必须使用中文，只描述场景环境本身：
- 场所类型（室内/室外、建筑类型等）
- 空间布局和结构
- 环境元素（植被、建筑、装饰等）
- 光线和氛围
- 色调和风格
- 材质和纹理细节

【禁止】scene_prompt 中绝对不能包含：
- 任何角色、人物、动物等生物
- 任何动作或故事情节
- 时间、天气、氛围等抽象概念（除非可视化表现）

这是空镜头场景，用于保持视频各镜头的场景一致性。

请直接输出JSON数组格式，不要包含其他文字说明。

剧本内容：
"""


@router.post("/extract")
async def extract_scenes(request: SceneExtractRequest):
    """从剧本提取场景"""
    project = storage_service.get_project(request.project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    content = project.script.processed_content or project.script.original_content
    if not content:
        raise HTTPException(status_code=400, detail="剧本内容为空")
    
    llm_service = LLMService()
    
    try:
        result = await llm_service.chat(
            prompt=SCENE_EXTRACT_PROMPT + content,
            model="qwen3-max"
        )
        
        scenes_data = json.loads(result)
        
        scenes = []
        for scene_data in scenes_data:
            scene = Scene(
                project_id=request.project_id,
                name=scene_data.get("name", "未命名场景"),
                description=scene_data.get("description", ""),
                scene_prompt=scene_data.get("scene_prompt", "")
            )
            storage_service.save_scene(scene)
            scenes.append(scene)
            project.scene_ids.append(scene.id)
        
        storage_service.save_project(project)
        
        return {"scenes": scenes}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="场景提取失败，返回格式不正确")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"场景提取失败: {str(e)}")


@router.get("")
async def list_scenes(project_id: str):
    """获取项目所有场景"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    scenes = []
    for scene_id in project.scene_ids:
        scene = storage_service.get_scene(scene_id)
        if scene:
            scenes.append(scene)
    
    return {"scenes": scenes}


@router.get("/{scene_id}")
async def get_scene(scene_id: str):
    """获取场景详情"""
    scene = storage_service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scene


@router.put("/{scene_id}")
async def update_scene(scene_id: str, request: SceneUpdateRequest):
    """更新场景信息"""
    scene = storage_service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(scene, key, value)
    
    storage_service.save_scene(scene)
    return scene


@router.post("/{scene_id}/generate")
async def generate_scene_images(scene_id: str, request: SceneGenerateRequest):
    """生成场景图片（单组）
    
    生图提示词构成：通用提示词 + 场景提示词 + 风格（图片或JSON）
    注意：描述(description)不参与生图
    """
    scene = storage_service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    common_prompt = request.common_prompt or scene.common_prompt
    scene_prompt = request.scene_prompt or scene.scene_prompt
    negative_prompt = request.negative_prompt or scene.negative_prompt
    
    # 检查是否使用风格参考
    style = None
    if request.use_style and request.style_id:
        style = storage_service.get_style(request.style_id)
    
    final_prompt, image_urls = build_scene_prompt(common_prompt, scene_prompt, style)
    
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
        
        image = SceneImage(
            group_index=request.group_index,
            url=url,
            prompt_used=final_prompt
        )
        
        while len(scene.image_groups) <= request.group_index:
            scene.image_groups.append(SceneImage(group_index=len(scene.image_groups)))
        
        scene.image_groups[request.group_index] = image
        
        if request.common_prompt:
            scene.common_prompt = request.common_prompt
        if request.scene_prompt:
            scene.scene_prompt = request.scene_prompt
        if request.negative_prompt is not None:
            scene.negative_prompt = request.negative_prompt
        
        storage_service.save_scene(scene)
        
        return {"image": image}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.post("/{scene_id}/generate-all")
async def generate_all_scene_images(scene_id: str, request: SceneGenerateAllRequest):
    """并发生成场景所有组图片"""
    import asyncio
    
    scene = storage_service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    common_prompt = request.common_prompt or scene.common_prompt
    scene_prompt = request.scene_prompt or scene.scene_prompt
    negative_prompt = request.negative_prompt or scene.negative_prompt
    
    # 检查是否使用风格参考
    style = None
    if request.use_style and request.style_id:
        style = storage_service.get_style(request.style_id)
    
    final_prompt, image_urls = build_scene_prompt(common_prompt, scene_prompt, style)
    
    async def generate_group(group_index: int) -> SceneImage:
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
        return SceneImage(
            group_index=group_index,
            url=url,
            prompt_used=final_prompt
        )
    
    try:
        tasks = [generate_group(i) for i in range(request.group_count)]
        image_groups = await asyncio.gather(*tasks)
        
        scene.image_groups = list(image_groups)
        
        if request.common_prompt:
            scene.common_prompt = request.common_prompt
        if request.scene_prompt:
            scene.scene_prompt = request.scene_prompt
        if request.negative_prompt is not None:
            scene.negative_prompt = request.negative_prompt
        
        storage_service.save_scene(scene)
        
        return {"image_groups": image_groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.delete("/{scene_id}")
async def delete_scene(scene_id: str):
    """删除场景"""
    scene = storage_service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    project = storage_service.get_project(scene.project_id)
    if project and scene_id in project.scene_ids:
        project.scene_ids.remove(scene_id)
        storage_service.save_project(project)
    
    storage_service.delete_scene(scene_id)
    return {"message": "场景已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_scenes(project_id: str):
    """删除项目的所有场景"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    deleted_count = 0
    for scene_id in project.scene_ids[:]:
        storage_service.delete_scene(scene_id)
        deleted_count += 1
    
    project.scene_ids = []
    storage_service.save_project(project)
    
    return {"message": f"已删除 {deleted_count} 个场景"}
