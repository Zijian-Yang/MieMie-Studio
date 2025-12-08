"""
角色 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json

from app.models.character import Character, CharacterImage, VoiceConfig
from app.services.storage import storage_service
from app.services.dashscope.llm import LLMService
from app.services.dashscope.text_to_image import TextToImageService
from app.services.dashscope.image_to_image import ImageToImageService
from typing import List as TypingList

router = APIRouter()


class CharacterExtractRequest(BaseModel):
    """角色提取请求"""
    project_id: str


class CharacterGenerateRequest(BaseModel):
    """角色图片生成请求"""
    group_index: int = 0  # 要生成的组索引
    common_prompt: Optional[str] = None  # 自定义通用提示词
    character_prompt: Optional[str] = None  # 自定义角色提示词
    negative_prompt: Optional[str] = None  # 负向提示词
    # 风格参考
    use_style: bool = False  # 是否使用风格参考
    style_id: Optional[str] = None  # 风格ID


class CharacterGenerateAllRequest(BaseModel):
    """角色图片批量生成请求"""
    common_prompt: Optional[str] = None
    character_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: int = 3  # 生成组数
    # 风格参考
    use_style: bool = False  # 是否使用风格参考
    style_id: Optional[str] = None  # 风格ID


class CharacterUpdateRequest(BaseModel):
    """角色更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    common_prompt: Optional[str] = None
    character_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None  # 负向提示词
    selected_group_index: Optional[int] = None
    voice: Optional[VoiceConfig] = None


# 角色提取提示词
CHARACTER_EXTRACT_PROMPT = """请从以下剧本中提取所有出现的角色，并为每个角色生成详细信息。

要求：
1. 识别剧本中所有出现的角色
2. 为每个角色生成以下信息（JSON格式）：
   - name: 角色名称
   - description: 角色简介
   - appearance: 外观描述（详细的外貌、服装等）
   - personality: 性格特点
   - character_prompt: 用于生成角色图片的提示词（中文，只描述角色本身的样貌特征）

重要：character_prompt 必须使用中文，只描述角色的基本样貌信息，包括：
- 性别、年龄段
- 发型、发色
- 五官特征
- 肤色
- 体型
- 基础服装风格

不要在 character_prompt 中包含：背景、场景、动作、表情、道具、复杂服饰细节等。

请直接输出JSON数组格式，不要包含其他文字说明。

剧本内容：
"""

# 三视图生成提示词模板
VIEW_PROMPTS = {
    "front": "正面视角，面向镜头",
    "side": "侧面视角，面向右侧",
    "back": "背面视角，背对镜头"
}


@router.post("/extract")
async def extract_characters(request: CharacterExtractRequest):
    """从剧本提取角色"""
    project = storage_service.get_project(request.project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    content = project.script.processed_content or project.script.original_content
    if not content:
        raise HTTPException(status_code=400, detail="剧本内容为空")
    
    llm_service = LLMService()
    
    try:
        result = await llm_service.chat(
            prompt=CHARACTER_EXTRACT_PROMPT + content,
            model="qwen3-max"
        )
        
        # 解析 JSON
        characters_data = json.loads(result)
        
        # 创建角色
        characters = []
        for char_data in characters_data:
            character = Character(
                project_id=request.project_id,
                name=char_data.get("name", "未命名角色"),
                description=char_data.get("description", ""),
                appearance=char_data.get("appearance", ""),
                personality=char_data.get("personality", ""),
                character_prompt=char_data.get("character_prompt", "")
            )
            storage_service.save_character(character)
            characters.append(character)
            project.character_ids.append(character.id)
        
        storage_service.save_project(project)
        
        return {"characters": characters}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="角色提取失败，返回格式不正确")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"角色提取失败: {str(e)}")


@router.get("")
async def list_characters(project_id: str):
    """获取项目所有角色"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    characters = []
    for char_id in project.character_ids:
        character = storage_service.get_character(char_id)
        if character:
            characters.append(character)
    
    return {"characters": characters}


@router.get("/{character_id}")
async def get_character(character_id: str):
    """获取角色详情"""
    character = storage_service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


@router.put("/{character_id}")
async def update_character(character_id: str, request: CharacterUpdateRequest):
    """更新角色信息"""
    character = storage_service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(character, key, value)
    
    storage_service.save_character(character)
    return character


def build_character_prompt(common_prompt: str, char_prompt: str, negative_prompt: str, view_prompt: str, style=None) -> tuple[str, TypingList[str]]:
    """
    构建角色生图提示词
    返回 (final_prompt, image_urls)
    - 生图提示词 = 通用提示词 + 角色提示词 + 视角提示词 + 风格提示词
    - 外观描述和性格特点不参与生图
    """
    prompt_parts = [common_prompt, char_prompt, view_prompt]
    image_urls = []
    
    if style:
        if style.style_type == "image" and style.image_groups:
            # 图片风格：提示词说明参考风格图
            if style.selected_group_index < len(style.image_groups):
                style_url = style.image_groups[style.selected_group_index].url
                if style_url:
                    image_urls.append(style_url)
                    prompt_parts.insert(0, "参考输入图片的艺术风格和视觉特征，")
        elif style.style_type == "text" and style.text_style_content:
            # 文本风格：将风格JSON嵌入提示词
            prompt_parts.append(f"使用以下风格进行生成: {style.text_style_content}")
    
    final_prompt = ", ".join([p for p in prompt_parts if p])
    return final_prompt, image_urls


@router.post("/{character_id}/generate")
async def generate_character_images(character_id: str, request: CharacterGenerateRequest):
    """生成角色三视图（单组）
    
    生图提示词构成：通用提示词 + 角色提示词（样貌） + 视角提示词 + 风格（图片或JSON）
    注意：外观描述(appearance)和性格特点(personality)不参与生图
    """
    character = storage_service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 使用提供的提示词或角色已有的提示词
    common_prompt = request.common_prompt or character.common_prompt
    char_prompt = request.character_prompt or character.character_prompt
    negative_prompt = request.negative_prompt or character.negative_prompt
    
    # 检查是否使用风格参考
    style = None
    if request.use_style and request.style_id:
        style = storage_service.get_style(request.style_id)
    
    # 生成三个视角的图片
    image_group = CharacterImage(group_index=request.group_index)
    
    try:
        for view_name, view_prompt in VIEW_PROMPTS.items():
            final_prompt, image_urls = build_character_prompt(
                common_prompt, char_prompt, negative_prompt, view_prompt, style
            )
            
            if image_urls:
                # 使用图生图服务（带风格图片）
                i2i_service = ImageToImageService()
                url = await i2i_service.generate_with_multi_images(
                    prompt=final_prompt,
                    image_urls=image_urls,
                    negative_prompt=negative_prompt
                )
            else:
                # 使用文生图服务
                t2i_service = TextToImageService()
                url = await t2i_service.generate(final_prompt, negative_prompt=negative_prompt)
            
            if view_name == "front":
                image_group.front_url = url
            elif view_name == "side":
                image_group.side_url = url
            else:
                image_group.back_url = url
        
        image_group.prompt_used = f"{common_prompt}, {char_prompt}"
        
        # 更新角色
        while len(character.image_groups) <= request.group_index:
            character.image_groups.append(CharacterImage(group_index=len(character.image_groups)))
        
        character.image_groups[request.group_index] = image_group
        
        # 保存更新的提示词
        if request.common_prompt:
            character.common_prompt = request.common_prompt
        if request.character_prompt:
            character.character_prompt = request.character_prompt
        if request.negative_prompt is not None:
            character.negative_prompt = request.negative_prompt
        
        storage_service.save_character(character)
        
        return {"image_group": image_group}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.post("/{character_id}/generate-all")
async def generate_all_character_images(character_id: str, request: CharacterGenerateAllRequest):
    """并发生成角色三组三视图"""
    import asyncio
    
    character = storage_service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 使用提供的提示词或角色已有的提示词
    common_prompt = request.common_prompt or character.common_prompt
    char_prompt = request.character_prompt or character.character_prompt
    negative_prompt = request.negative_prompt or character.negative_prompt
    
    # 检查是否使用风格参考
    style = None
    if request.use_style and request.style_id:
        style = storage_service.get_style(request.style_id)
    
    async def generate_group(group_index: int) -> CharacterImage:
        """生成单组三视图"""
        image_group = CharacterImage(group_index=group_index)
        
        for view_name, view_prompt in VIEW_PROMPTS.items():
            final_prompt, image_urls = build_character_prompt(
                common_prompt, char_prompt, negative_prompt, view_prompt, style
            )
            
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
            
            if view_name == "front":
                image_group.front_url = url
            elif view_name == "side":
                image_group.side_url = url
            else:
                image_group.back_url = url
        
        image_group.prompt_used = f"{common_prompt}, {char_prompt}"
        return image_group
    
    try:
        # 并发生成指定组数
        tasks = [generate_group(i) for i in range(request.group_count)]
        image_groups = await asyncio.gather(*tasks)
        
        # 更新角色
        character.image_groups = list(image_groups)
        
        # 保存更新的提示词
        if request.common_prompt:
            character.common_prompt = request.common_prompt
        if request.character_prompt:
            character.character_prompt = request.character_prompt
        if request.negative_prompt is not None:
            character.negative_prompt = request.negative_prompt
        
        storage_service.save_character(character)
        
        return {"image_groups": image_groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.delete("/{character_id}")
async def delete_character(character_id: str):
    """删除角色"""
    character = storage_service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 从项目中移除
    project = storage_service.get_project(character.project_id)
    if project and character_id in project.character_ids:
        project.character_ids.remove(character_id)
        storage_service.save_project(project)
    
    storage_service.delete_character(character_id)
    return {"message": "角色已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_characters(project_id: str):
    """删除项目的所有角色"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    deleted_count = 0
    for character_id in project.character_ids[:]:
        storage_service.delete_character(character_id)
        deleted_count += 1
    
    project.character_ids = []
    storage_service.save_project(project)
    
    return {"message": f"已删除 {deleted_count} 个角色"}
