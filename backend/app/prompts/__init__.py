"""
预置提示词模板
"""

# 分镜脚本生成提示词
SCRIPT_GENERATION_PROMPT = """你是一位专业的影视编剧和分镜师。请根据以下剧本内容，生成详细的分镜脚本。

要求：
1. 将剧本拆分为多个连续的镜头
2. 每个镜头需要包含以下字段（使用JSON格式输出）：
   - shot_number: 镜头序号（从1开始）
   - shot_design: 镜头设计描述
   - scene_type: 景别（远景/全景/中景/近景/特写）
   - voice_subject: 配音主体（角色名或"无配音"）
   - dialogue: 视频台词（如果有）
   - characters: 出镜角色列表
   - character_appearance: 角色造型描述
   - character_action: 角色动作描述
   - scene_setting: 场景设置
   - lighting: 光线设计
   - mood: 情绪基调
   - composition: 构图方式
   - props: 道具列表
   - sound_effects: 音效描述
   - duration: 建议视频时长（秒）

请直接输出JSON数组格式的分镜脚本，不要包含其他文字说明。

剧本内容：
"""

# 角色提取提示词
CHARACTER_EXTRACT_PROMPT = """请从以下剧本中提取所有出现的角色，并为每个角色生成详细信息。

要求：
1. 识别剧本中所有出现的角色
2. 为每个角色生成以下信息（JSON格式）：
   - name: 角色名称
   - description: 角色简介
   - appearance: 外观描述（详细的外貌、服装等，用于生成图片）
   - personality: 性格特点
   - character_prompt: 用于生成角色图片的提示词（英文，详细描述外貌特征）

请直接输出JSON数组格式，不要包含其他文字说明。

剧本内容：
"""

# 场景提取提示词
SCENE_EXTRACT_PROMPT = """请从以下剧本中提取所有出现的场景，并为每个场景生成详细信息。

要求：
1. 识别剧本中所有不同的场景/地点
2. 为每个场景生成以下信息（JSON格式）：
   - name: 场景名称
   - description: 场景描述
   - location: 具体地点
   - time_of_day: 时间（白天/黄昏/夜晚等）
   - weather: 天气状况
   - atmosphere: 氛围描述
   - scene_prompt: 用于生成场景图片的提示词（英文，详细描述场景特征）

请直接输出JSON数组格式，不要包含其他文字说明。

剧本内容：
"""

# 道具提取提示词
PROP_EXTRACT_PROMPT = """请从以下剧本中提取所有重要的道具，并为每个道具生成详细信息。

要求：
1. 识别剧本中多次出现或对剧情重要的道具/物品
2. 为每个道具生成以下信息（JSON格式）：
   - name: 道具名称
   - description: 道具描述
   - material: 材质
   - color: 颜色
   - size: 尺寸描述
   - prop_prompt: 用于生成道具图片的提示词（英文，详细描述道具特征）

请直接输出JSON数组格式，不要包含其他文字说明。

剧本内容：
"""

# 角色三视图通用提示词
CHARACTER_VIEW_PROMPT = "半身人物肖像，白色纯净背景，高清细节，一致的光线，专业摄影风格"

# 场景通用提示词
SCENE_COMMON_PROMPT = "空镜头，无人物，高清画质，电影感，专业摄影"

# 道具通用提示词
PROP_COMMON_PROMPT = "物品特写，白色纯净背景，高清细节，产品摄影风格"
