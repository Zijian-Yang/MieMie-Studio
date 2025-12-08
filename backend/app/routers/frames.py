"""
分镜首帧 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.models.frame import Frame, FrameImage
from app.models.gallery import GalleryImage
from app.services.storage import storage_service
from app.services.dashscope.text_to_image import TextToImageService
from app.services.dashscope.image_to_image import ImageToImageService

router = APIRouter()


class FrameGenerateRequest(BaseModel):
    """首帧生成请求"""
    project_id: str
    shot_id: str
    shot_number: int = 0
    prompt: str  # 生成首帧的提示词
    negative_prompt: str = ""
    group_index: int = 0
    # 使用分镜关联的素材进行多图生图
    use_shot_references: bool = True  # 是否使用分镜关联的角色/场景/道具


class FrameBatchGenerateRequest(BaseModel):
    """批量首帧生成请求"""
    project_id: str


class FrameUpdateRequest(BaseModel):
    """首帧更新请求"""
    prompt: Optional[str] = None
    selected_group_index: Optional[int] = None


class SetFrameFromGalleryRequest(BaseModel):
    """从图库设置首帧请求"""
    project_id: str
    shot_id: str
    shot_number: int = 0
    gallery_image_id: str
    gallery_image_url: str
    group_index: int = 0


class SaveFrameToGalleryRequest(BaseModel):
    """保存首帧到图库请求"""
    name: str = ""
    description: str = ""


def get_shot_reference_urls(project_id: str, shot) -> List[str]:
    """获取分镜关联的素材图片URL列表"""
    urls = []
    
    # 1. 先添加角色图片（按 character_ids 顺序）
    for char_id in shot.character_ids:
        character = storage_service.get_character(char_id)
        if character and character.image_groups:
            idx = character.selected_group_index
            if idx < len(character.image_groups) and character.image_groups[idx].front_url:
                urls.append(character.image_groups[idx].front_url)
    
    # 2. 添加场景图片
    if shot.scene_id:
        scene = storage_service.get_scene(shot.scene_id)
        if scene and scene.image_groups:
            idx = scene.selected_group_index
            if idx < len(scene.image_groups) and scene.image_groups[idx].url:
                urls.append(scene.image_groups[idx].url)
    
    # 3. 添加道具图片（按 prop_ids 顺序）
    for prop_id in shot.prop_ids:
        prop = storage_service.get_prop(prop_id)
        if prop and prop.image_groups:
            idx = prop.selected_group_index
            if idx < len(prop.image_groups) and prop.image_groups[idx].url:
                urls.append(prop.image_groups[idx].url)
    
    return urls


def generate_shot_prompt(shot) -> str:
    """根据分镜信息生成首帧提示词"""
    prompt_parts = []
    
    # 场景设置
    if shot.scene_setting:
        prompt_parts.append(f"场景: {shot.scene_setting}")
    
    # 景别
    if shot.scene_type:
        prompt_parts.append(f"{shot.scene_type}镜头")
    
    # 构图
    if shot.composition:
        prompt_parts.append(f"构图: {shot.composition}")
    
    # 光线
    if shot.lighting:
        prompt_parts.append(f"光线: {shot.lighting}")
    
    # 情绪基调
    if shot.mood:
        prompt_parts.append(f"氛围: {shot.mood}")
    
    # 角色描述
    if shot.characters:
        char_desc = f"画面中有{', '.join(shot.characters)}"
        if shot.character_appearance:
            char_desc += f", {shot.character_appearance}"
        if shot.character_action:
            char_desc += f", 正在{shot.character_action}"
        prompt_parts.append(char_desc)
    
    # 道具
    if shot.props:
        prompt_parts.append(f"道具: {', '.join(shot.props)}")
    
    # 生成完整提示词
    if prompt_parts:
        prompt = "电影级画面, 高清细节, " + ", ".join(prompt_parts)
    else:
        prompt = "电影级画面, 高清细节, 精美构图"
    
    return prompt


@router.post("/generate")
async def generate_frame(request: FrameGenerateRequest):
    """生成单个分镜首帧"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取分镜信息
    shot = None
    if project.script and project.script.shots:
        for s in project.script.shots:
            if s.id == request.shot_id:
                shot = s
                break
    
    # 获取关联素材的图片URL
    ref_urls = []
    if request.use_shot_references and shot:
        ref_urls = get_shot_reference_urls(request.project_id, shot)
    
    try:
        if ref_urls:
            # 使用多图生图
            i2i_service = ImageToImageService()
            # 在提示词中说明使用参考图
            enhanced_prompt = f"参考输入的图片素材，{request.prompt}"
            url = await i2i_service.generate_with_multi_images(
                prompt=enhanced_prompt,
                image_urls=ref_urls,
                negative_prompt=request.negative_prompt
            )
        else:
            # 使用纯文生图
            t2i_service = TextToImageService()
            url = await t2i_service.generate(request.prompt, negative_prompt=request.negative_prompt)
        
        # 查找或创建 Frame
        frame = storage_service.get_frame_by_shot(request.project_id, request.shot_id)
        if not frame:
            frame = Frame(
                project_id=request.project_id,
                shot_id=request.shot_id,
                shot_number=request.shot_number,
                prompt=request.prompt
            )
        
        image = FrameImage(
            group_index=request.group_index,
            url=url,
            prompt_used=request.prompt
        )
        
        while len(frame.image_groups) <= request.group_index:
            frame.image_groups.append(FrameImage(group_index=len(frame.image_groups)))
        
        frame.image_groups[request.group_index] = image
        frame.prompt = request.prompt
        
        storage_service.save_frame(frame)
        
        # 更新分镜的首帧URL
        if shot and request.group_index == frame.selected_group_index:
            shot.first_frame_url = url
            storage_service.save_project(project)
        
        return {"frame": frame}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"首帧生成失败: {str(e)}")


@router.post("/generate-batch")
async def generate_frames_batch(request: FrameBatchGenerateRequest):
    """批量生成所有分镜首帧"""
    project = storage_service.get_project(request.project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    if not project.script.shots:
        raise HTTPException(status_code=400, detail="分镜列表为空")
    
    frames = []
    errors = []
    
    for shot in project.script.shots:
        try:
            # 自动生成提示词
            prompt = generate_shot_prompt(shot)
            
            # 获取关联素材的图片URL
            ref_urls = get_shot_reference_urls(request.project_id, shot)
            
            if ref_urls:
                # 使用多图生图
                i2i_service = ImageToImageService()
                enhanced_prompt = f"参考输入的图片素材，{prompt}"
                url = await i2i_service.generate_with_multi_images(
                    prompt=enhanced_prompt,
                    image_urls=ref_urls
                )
            else:
                # 使用纯文生图
                t2i_service = TextToImageService()
                url = await t2i_service.generate(prompt)
            
            frame = storage_service.get_frame_by_shot(request.project_id, shot.id)
            if not frame:
                frame = Frame(
                    project_id=request.project_id,
                    shot_id=shot.id,
                    shot_number=shot.shot_number,
                    prompt=prompt
                )
            
            image = FrameImage(
                group_index=0,
                url=url,
                prompt_used=prompt
            )
            
            if not frame.image_groups:
                frame.image_groups = [image]
            else:
                frame.image_groups[0] = image
            
            storage_service.save_frame(frame)
            frames.append(frame)
            
            # 更新分镜的首帧URL
            shot.first_frame_url = url
            
        except Exception as e:
            errors.append({
                "shot_id": shot.id,
                "shot_number": shot.shot_number,
                "error": str(e)
            })
    
    # 保存更新后的分镜
    storage_service.save_project(project)
    
    return {
        "frames": frames,
        "errors": errors,
        "success_count": len(frames),
        "error_count": len(errors)
    }


@router.get("")
async def list_frames(project_id: str):
    """获取项目所有首帧"""
    frames = storage_service.get_frames_by_project(project_id)
    return {"frames": frames}


@router.get("/{frame_id}")
async def get_frame(frame_id: str):
    """获取首帧详情"""
    frame = storage_service.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="首帧不存在")
    return frame


@router.put("/{frame_id}")
async def update_frame(frame_id: str, request: FrameUpdateRequest):
    """更新首帧信息"""
    frame = storage_service.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="首帧不存在")
    
    if request.prompt is not None:
        frame.prompt = request.prompt
    if request.selected_group_index is not None:
        frame.selected_group_index = request.selected_group_index
    
    storage_service.save_frame(frame)
    return frame


@router.delete("/{frame_id}")
async def delete_frame(frame_id: str):
    """删除首帧"""
    frame = storage_service.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="首帧不存在")
    
    storage_service.delete_frame(frame_id)
    return {"message": "首帧已删除"}


@router.post("/set-from-gallery")
async def set_frame_from_gallery(request: SetFrameFromGalleryRequest):
    """从图库设置首帧图片"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 验证图库图片存在
    gallery_image = storage_service.get_gallery_image(request.gallery_image_id)
    if not gallery_image:
        raise HTTPException(status_code=404, detail="图库图片不存在")
    
    # 查找或创建 Frame
    frame = storage_service.get_frame_by_shot(request.project_id, request.shot_id)
    if not frame:
        frame = Frame(
            project_id=request.project_id,
            shot_id=request.shot_id,
            shot_number=request.shot_number,
            prompt=f"从图库导入: {gallery_image.name}"
        )
    
    # 创建 FrameImage
    image = FrameImage(
        group_index=request.group_index,
        url=request.gallery_image_url,
        prompt_used=f"从图库导入: {gallery_image.name}"
    )
    
    # 确保 image_groups 列表足够长
    while len(frame.image_groups) <= request.group_index:
        frame.image_groups.append(FrameImage(group_index=len(frame.image_groups)))
    
    frame.image_groups[request.group_index] = image
    
    # 如果是设置第一组，同时设为选中
    if request.group_index == 0:
        frame.selected_group_index = 0
    
    storage_service.save_frame(frame)
    
    return {"frame": frame, "message": f"已从图库导入图片作为首帧"}


@router.post("/{frame_id}/save-to-gallery")
async def save_frame_to_gallery(frame_id: str, request: SaveFrameToGalleryRequest):
    """保存首帧到图库"""
    frame = storage_service.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="首帧不存在")
    
    # 获取选中的图片
    if frame.selected_group_index >= len(frame.image_groups):
        raise HTTPException(status_code=400, detail="没有可保存的图片")
    
    image = frame.image_groups[frame.selected_group_index]
    if not image.url:
        raise HTTPException(status_code=400, detail="选中的图片没有URL")
    
    # 创建图库图片
    gallery_image = GalleryImage(
        project_id=frame.project_id,
        name=request.name or f"首帧 - 镜头{frame.shot_number}",
        description=request.description or f"从分镜首帧保存",
        url=image.url,
        prompt_used=image.prompt_used,
        source="frame"
    )
    
    storage_service.save_gallery_image(gallery_image)
    
    return {"gallery_image": gallery_image, "message": "已保存到图库"}
