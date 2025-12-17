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
    # 文生图模型参数
    model: Optional[str] = None  # 文生图模型 (wan2.6-t2i / wan2.5-t2i-preview)
    width: Optional[int] = None  # 图片宽度
    height: Optional[int] = None  # 图片高度
    prompt_extend: Optional[bool] = None  # 智能改写
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子


class CharacterGenerateAllRequest(BaseModel):
    """角色图片批量生成请求"""
    common_prompt: Optional[str] = None
    character_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: int = 3  # 生成组数
    # 风格参考
    use_style: bool = False  # 是否使用风格参考
    style_id: Optional[str] = None  # 风格ID
    # 文生图模型参数
    model: Optional[str] = None  # 文生图模型 (wan2.6-t2i / wan2.5-t2i-preview)
    width: Optional[int] = None  # 图片宽度
    height: Optional[int] = None  # 图片高度
    prompt_extend: Optional[bool] = None  # 智能改写
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子


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


class CharacterCreateRequest(BaseModel):
    """手动创建角色请求"""
    project_id: str
    name: str
    description: Optional[str] = ""
    appearance: Optional[str] = ""
    personality: Optional[str] = ""
    common_prompt: Optional[str] = ""
    character_prompt: Optional[str] = ""
    negative_prompt: Optional[str] = ""


class CharacterSelectImageRequest(BaseModel):
    """从图库选择图片作为角色图请求"""
    image_urls: List[str]  # 可以是 1-3 张图片
    group_index: int = 0  # 要设置的组索引


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

# 三视图合成图提示词模板
THREE_VIEW_PROMPT = "角色三视图，同一画面内从左到右依次展示：正面视角（面向镜头）、侧面视角（面向右侧）、背面视角（背对镜头），三个视角的角色服装和外观完全一致，白色纯净背景，专业角色设计参考图"


@router.post("/create")
async def create_character(request: CharacterCreateRequest):
    """手动创建角色"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 创建角色
    character = Character(
        project_id=request.project_id,
        name=request.name,
        description=request.description or "",
        appearance=request.appearance or "",
        personality=request.personality or "",
        common_prompt=request.common_prompt or "半身人物肖像，白色纯净背景，高清细节，一致的光线，专业摄影风格",
        character_prompt=request.character_prompt or "",
        negative_prompt=request.negative_prompt or "",
    )
    
    storage_service.save_character(character)
    
    # 更新项目的角色列表
    if character.id not in project.character_ids:
        project.character_ids.append(character.id)
        storage_service.save_project(project)
    
    return {"character": character}


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


@router.post("/{character_id}/select-images")
async def select_character_images(character_id: str, request: CharacterSelectImageRequest):
    """从图库选择图片作为角色图（支持1-3张：正面、侧面、背面）"""
    from datetime import datetime
    
    character = storage_service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    if not request.image_urls or len(request.image_urls) == 0:
        raise HTTPException(status_code=400, detail="请提供至少一张图片")
    
    if len(request.image_urls) > 3:
        raise HTTPException(status_code=400, detail="最多选择3张图片（正面、侧面、背面）")
    
    # 创建图片组
    image_group = CharacterImage(
        group_index=request.group_index,
        front_url=request.image_urls[0] if len(request.image_urls) > 0 else None,
        side_url=request.image_urls[1] if len(request.image_urls) > 1 else None,
        back_url=request.image_urls[2] if len(request.image_urls) > 2 else None,
        prompt_used="从图库选择",
        created_at=datetime.now().isoformat()
    )
    
    # 检查组索引是否已存在
    existing_index = None
    for i, group in enumerate(character.image_groups):
        if group.group_index == request.group_index:
            existing_index = i
            break
    
    if existing_index is not None:
        character.image_groups[existing_index] = image_group
    else:
        character.image_groups.append(image_group)
        character.image_groups.sort(key=lambda x: x.group_index)
    
    # 自动选中该组
    character.selected_group_index = request.group_index
    
    storage_service.save_character(character)
    
    return {"character": character}


def build_character_prompt(common_prompt: str, char_prompt: str, negative_prompt: str, style=None) -> tuple[str, TypingList[str]]:
    """
    构建角色三视图合成图生图提示词
    返回 (final_prompt, image_urls)
    - 生图提示词 = 三视图提示词 + 通用提示词 + 角色提示词 + 风格提示词
    - 外观描述和性格特点不参与生图
    """
    prompt_parts = [THREE_VIEW_PROMPT, common_prompt, char_prompt]
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
    """生成角色三视图合成图（单组）
    
    生成一张包含正面、侧面、背面三个视角的合成图
    生图提示词构成：三视图提示词 + 通用提示词 + 角色提示词 + 风格（图片或JSON）
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
    
    # 生成一张三视图合成图
    image_group = CharacterImage(group_index=request.group_index)
    
    try:
        final_prompt, image_urls = build_character_prompt(
            common_prompt, char_prompt, negative_prompt, style
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
            url = await t2i_service.generate(
                final_prompt, 
                negative_prompt=negative_prompt,
                model=request.model,
                width=request.width,
                height=request.height,
                prompt_extend=request.prompt_extend,
                watermark=request.watermark,
                seed=request.seed,
                project_id=character.project_id
            )
        
        # 将三视图合成图存储在 front_url 字段中
        image_group.front_url = url
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
    """并发生成角色多组三视图合成图"""
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
        """生成单组三视图合成图"""
        image_group = CharacterImage(group_index=group_index)
        
        final_prompt, image_urls = build_character_prompt(
            common_prompt, char_prompt, negative_prompt, style
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
            url = await t2i_service.generate(
                final_prompt, 
                negative_prompt=negative_prompt,
                model=request.model,
                width=request.width,
                height=request.height,
                prompt_extend=request.prompt_extend,
                watermark=request.watermark,
                seed=request.seed,
                project_id=character.project_id
            )
        
        # 将三视图合成图存储在 front_url 字段中
        image_group.front_url = url
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
