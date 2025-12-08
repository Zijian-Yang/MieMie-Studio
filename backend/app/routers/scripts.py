"""
分镜脚本 API 路由
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json

from app.models.project import Script, Shot
from app.services.storage import storage_service
from app.services.dashscope.llm import LLMService
from app.services.file_parser import parse_file

router = APIRouter()


class ScriptGenerateRequest(BaseModel):
    """剧本生成请求"""
    project_id: str
    content: str  # 原始剧本内容
    model: str = "qwen3-max"  # 使用的模型
    prompt: Optional[str] = None  # 自定义提示词


class ScriptSaveRequest(BaseModel):
    """剧本保存请求"""
    project_id: str
    content: str  # 剧本内容
    model_used: Optional[str] = None
    prompt_used: Optional[str] = None


class ShotUpdateRequest(BaseModel):
    """分镜列表更新请求"""
    shots: List[Shot]


class SingleShotUpdateRequest(BaseModel):
    """单个分镜更新请求"""
    shot_number: Optional[int] = None
    shot_design: Optional[str] = None
    scene_type: Optional[str] = None
    voice_subject: Optional[str] = None
    dialogue: Optional[str] = None
    characters: Optional[List[str]] = None
    character_appearance: Optional[str] = None
    character_action: Optional[str] = None
    scene_setting: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    composition: Optional[str] = None
    props: Optional[List[str]] = None
    sound_effects: Optional[str] = None
    duration: Optional[float] = None


class ShotReorderRequest(BaseModel):
    """分镜排序请求"""
    shot_ids: List[str]  # 按新顺序排列的分镜ID列表


class ShotCreateRequest(BaseModel):
    """新增分镜请求"""
    shot_design: str = ""
    scene_type: str = ""
    voice_subject: str = ""
    dialogue: str = ""
    characters: List[str] = []
    character_appearance: str = ""
    character_action: str = ""
    scene_setting: str = ""
    lighting: str = ""
    mood: str = ""
    composition: str = ""
    props: List[str] = []
    sound_effects: str = ""
    duration: float = 5.0
    insert_after_shot_id: Optional[str] = None  # 在哪个镜头后插入，None 表示末尾


# 默认分镜脚本生成提示词
DEFAULT_SCRIPT_PROMPT = """你是一位资深的影视编剧、分镜师和AI视频制作专家。请根据以下剧本/故事内容，生成专业详细的分镜脚本。

【重要约束】
1. 每个镜头的duration（时长）必须在 1-10 秒之间，建议 3-8 秒为主
2. 输出必须是严格有效的JSON数组格式，不要包含任何其他文字、解释或markdown代码块标记
3. 所有字符串值必须正确转义，确保JSON可被解析

【输出格式要求】
直接输出JSON数组，每个元素是一个镜头对象，包含以下字段：

{
  "shot_number": 1,                    // 镜头序号，从1开始递增
  "shot_design": "...",                // 详细的镜头设计：运镜方式、镜头运动、画面重点等
  "scene_type": "远景/全景/中景/近景/特写",  // 景别选择
  "voice_subject": "角色名/旁白/无配音",     // 配音主体
  "dialogue": "...",                   // 该镜头的台词或旁白文本
  "characters": ["角色1", "角色2"],    // 出镜角色名称列表
  "character_appearance": "...",       // 角色在该镜头的造型描述
  "character_action": "...",           // 角色的具体动作和表情
  "scene_setting": "...",              // 场景环境的详细描述
  "lighting": "...",                   // 光线设计：光源、色温、明暗等
  "mood": "...",                       // 情绪基调和氛围
  "composition": "...",                // 构图方式：三分法、对称、引导线等
  "props": ["道具1", "道具2"],         // 该镜头涉及的道具列表
  "sound_effects": "...",              // 音效描述
  "duration": 5                        // 建议时长（秒），1-10之间的数字
}

【分镜设计原则】
1. 镜头之间要有逻辑连贯性，注意转场衔接
2. 景别变化要有节奏感，避免单调
3. 场景设置要具体可视化，便于AI生成首帧图
4. 角色动作要具体明确，有画面感
5. 每个镜头只承载一个核心动作或信息点

【注意事项】
- 道具列表只填写需要跨多个镜头保持一致的重要道具
- 角色名称要前后一致，便于后续识别匹配
- 场景名称要规范化，相同场景使用相同名称

请直接输出JSON数组：

剧本内容：
"""


@router.post("/upload")
async def upload_script(
    project_id: str = Form(...),
    file: UploadFile = File(...)
):
    """上传剧本文件"""
    try:
        content = await parse_file(file)
        
        # 获取或创建项目
        project = storage_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 更新项目的原始剧本
        if project.script is None:
            project.script = Script(original_content=content)
        else:
            project.script.original_content = content
        
        storage_service.save_project(project)
        
        return {
            "message": "文件上传成功",
            "content": content,
            "filename": file.filename
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")


@router.post("/generate")
async def generate_script(request: ScriptGenerateRequest):
    """生成/优化分镜脚本（SSE 流式输出）"""
    
    async def generate():
        llm_service = LLMService()
        
        # 构建提示词
        prompt = request.prompt or DEFAULT_SCRIPT_PROMPT
        full_prompt = prompt + request.content
        
        try:
            async for chunk in llm_service.stream_chat(
                prompt=full_prompt,
                model=request.model
            ):
                # SSE 格式
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/save")
async def save_script(request: ScriptSaveRequest):
    """保存剧本"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if project.script is None:
        project.script = Script()
    
    project.script.processed_content = request.content
    project.script.model_used = request.model_used
    project.script.prompt_used = request.prompt_used
    
    storage_service.save_project(project)
    
    return {"message": "剧本已保存", "script_id": project.script.id}


@router.get("/{project_id}")
async def get_script(project_id: str):
    """获取项目剧本"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return project.script


@router.post("/{project_id}/parse-shots")
async def parse_shots(project_id: str):
    """解析剧本内容为分镜列表"""
    project = storage_service.get_project(project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    content = project.script.processed_content or project.script.original_content
    if not content:
        raise HTTPException(status_code=400, detail="剧本内容为空")
    
    llm_service = LLMService()
    
    try:
        # 使用 LLM 解析分镜
        result = await llm_service.chat(
            prompt=DEFAULT_SCRIPT_PROMPT + content,
            model="qwen3-max"
        )
        
        # 尝试解析 JSON
        shots_data = json.loads(result)
        shots = [Shot(**shot) for shot in shots_data]
        
        # 更新项目
        project.script.shots = shots
        storage_service.save_project(project)
        
        return {"shots": shots}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="分镜解析失败，返回格式不正确")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分镜解析失败: {str(e)}")


@router.put("/{project_id}/shots")
async def update_shots(project_id: str, request: ShotUpdateRequest):
    """更新分镜列表"""
    project = storage_service.get_project(project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    project.script.shots = request.shots
    storage_service.save_project(project)
    
    return {"message": "分镜已更新"}


@router.get("/prompts/default")
async def get_default_prompt():
    """获取默认提示词"""
    return {"prompt": DEFAULT_SCRIPT_PROMPT}


@router.put("/{project_id}/shots/{shot_id}")
async def update_single_shot(project_id: str, shot_id: str, request: SingleShotUpdateRequest):
    """更新单个分镜"""
    project = storage_service.get_project(project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    # 查找分镜
    shot_index = None
    for i, shot in enumerate(project.script.shots):
        if shot.id == shot_id:
            shot_index = i
            break
    
    if shot_index is None:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    # 更新分镜字段
    shot = project.script.shots[shot_index]
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(shot, key, value)
    
    storage_service.save_project(project)
    
    return {"shot": shot}


@router.put("/{project_id}/shots-reorder")
async def reorder_shots(project_id: str, request: ShotReorderRequest):
    """调整分镜顺序"""
    project = storage_service.get_project(project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    # 创建 ID 到 Shot 的映射
    shots_map = {shot.id: shot for shot in project.script.shots}
    
    # 检查所有 ID 是否有效
    for shot_id in request.shot_ids:
        if shot_id not in shots_map:
            raise HTTPException(status_code=400, detail=f"分镜ID不存在: {shot_id}")
    
    # 按新顺序重建列表并更新 shot_number
    new_shots = []
    for i, shot_id in enumerate(request.shot_ids):
        shot = shots_map[shot_id]
        shot.shot_number = i + 1  # 更新镜头序号
        new_shots.append(shot)
    
    project.script.shots = new_shots
    storage_service.save_project(project)
    
    return {"shots": new_shots}


@router.post("/{project_id}/shots")
async def create_shot(project_id: str, request: ShotCreateRequest):
    """新增分镜"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if not project.script:
        project.script = Script()
    
    # 创建新分镜
    new_shot = Shot(
        shot_design=request.shot_design,
        scene_type=request.scene_type,
        voice_subject=request.voice_subject,
        dialogue=request.dialogue,
        characters=request.characters,
        character_appearance=request.character_appearance,
        character_action=request.character_action,
        scene_setting=request.scene_setting,
        lighting=request.lighting,
        mood=request.mood,
        composition=request.composition,
        props=request.props,
        sound_effects=request.sound_effects,
        duration=min(request.duration, 10.0)  # 确保不超过10秒
    )
    
    # 确定插入位置
    if request.insert_after_shot_id:
        insert_index = -1
        for i, shot in enumerate(project.script.shots):
            if shot.id == request.insert_after_shot_id:
                insert_index = i + 1
                break
        if insert_index == -1:
            project.script.shots.append(new_shot)
        else:
            project.script.shots.insert(insert_index, new_shot)
    else:
        project.script.shots.append(new_shot)
    
    # 重新编号
    for i, shot in enumerate(project.script.shots):
        shot.shot_number = i + 1
    
    storage_service.save_project(project)
    
    return {"shot": new_shot, "shots": project.script.shots}


@router.delete("/{project_id}/shots/{shot_id}")
async def delete_shot(project_id: str, shot_id: str):
    """删除分镜"""
    project = storage_service.get_project(project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    # 查找并删除分镜
    shot_index = None
    for i, shot in enumerate(project.script.shots):
        if shot.id == shot_id:
            shot_index = i
            break
    
    if shot_index is None:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    # 同时删除相关的首帧和视频
    from app.services.storage import storage_service as ss
    frame = ss.get_frame_by_shot(project_id, shot_id)
    if frame:
        ss.delete_frame(frame.id)
    
    video = ss.get_video_by_shot(project_id, shot_id)
    if video:
        ss.delete_video(video.id)
    
    # 删除分镜
    project.script.shots.pop(shot_index)
    
    # 重新编号
    for i, shot in enumerate(project.script.shots):
        shot.shot_number = i + 1
    
    storage_service.save_project(project)
    
    return {"message": "分镜已删除", "shots": project.script.shots}
