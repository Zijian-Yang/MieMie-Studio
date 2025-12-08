"""
预置提示词模板
"""

# 分镜脚本生成提示词
SCRIPT_GENERATION_PROMPT = """你是一位专业的影视编剧和分镜师。请根据用户提供的剧本内容，生成详细的分镜脚本。

要求：
1. 将剧本拆分成多个独立的分镜场景
2. 每个分镜需要包含以下完整信息：
   - 镜头设计：描述镜头的运动和切换方式
   - 景别：远景/全景/中景/近景/特写
   - 配音主体：需要配音的角色，无则填"无配音"
   - 视频台词：角色在该镜头中的台词，无则填"无台词"
   - 出镜角色：该镜头中出现的所有角色
   - 角色造型：角色的服装、发型等外观描述
   - 角色动作：角色在该镜头中的具体动作
   - 场景设置：场景的环境描述
   - 光线设计：光线的来源、强度、色调
   - 情绪基调：该镜头想要传达的情绪
   - 构图：构图方式（如三分法、对称、框架等）
   - 道具：镜头中出现的重要道具
   - 音效：需要的背景音效
   - 视频时长：建议的镜头时长（秒）

3. 输出格式：每个分镜用"---"分隔，字段用"字段名：内容"格式

用户剧本内容：
{content}

请生成详细的分镜脚本："""

# 角色提取提示词
CHARACTER_EXTRACTION_PROMPT = """你是一位专业的影视角色分析师。请从以下剧本内容中提取所有角色信息。

要求：
1. 识别剧本中所有出现的角色（包括主角、配角）
2. 为每个角色生成：
   - name: 角色名字
   - description: 角色在故事中的定位和性格
   - appearance: 详细的外貌特征描述（包括年龄、性别、体型、发型、标志性特征等）
   - prompt: 用于AI生图的详细提示词（英文，描述角色外貌，适合生成人物肖像）

3. 输出格式：JSON数组
[
  {{
    "name": "角色名",
    "description": "角色描述",
    "appearance": "外貌特征",
    "prompt": "英文生图提示词"
  }}
]

剧本内容：
{content}

请提取角色信息（只输出JSON，不要其他内容）："""

# 场景提取提示词
SCENE_EXTRACTION_PROMPT = """你是一位专业的影视场景设计师。请从以下剧本内容中提取所有独特的场景。

要求：
1. 识别剧本中所有不同的场景/地点
2. 为每个场景生成：
   - name: 场景名称
   - description: 场景的详细描述（环境、氛围、时间等）
   - prompt: 用于AI生图的详细提示词（英文，描述空镜头场景，无人物）

3. 输出格式：JSON数组
[
  {{
    "name": "场景名",
    "description": "场景描述",
    "prompt": "英文生图提示词"
  }}
]

剧本内容：
{content}

请提取场景信息（只输出JSON，不要其他内容）："""

# 道具提取提示词
PROP_EXTRACTION_PROMPT = """你是一位专业的影视道具师。请从以下剧本内容中提取所有重要的道具。

要求：
1. 识别剧本中多次出现或对剧情重要的道具物品
2. 为每个道具生成：
   - name: 道具名称
   - description: 道具的详细描述（材质、颜色、大小、特征等）
   - prompt: 用于AI生图的详细提示词（英文，描述道具特写，白色背景）

3. 输出格式：JSON数组
[
  {{
    "name": "道具名",
    "description": "道具描述",
    "prompt": "英文生图提示词"
  }}
]

剧本内容：
{content}

请提取道具信息（只输出JSON，不要其他内容）："""

# 角色三视图通用提示词
CHARACTER_IMAGE_COMMON_PROMPT = """half-body portrait, white pure background, high detail, consistent lighting, professional photography style, studio lighting, 8k quality"""

# 角色三视图视角提示词
CHARACTER_VIEW_PROMPTS = {
    "front": "front view, facing camera, looking at viewer",
    "side": "side view, profile, looking to the side",
    "back": "back view, from behind, showing back of head"
}

# 场景图片通用提示词
SCENE_IMAGE_COMMON_PROMPT = """cinematic scene, empty room without people, atmospheric lighting, high detail, 8k quality, film photography style"""

# 道具图片通用提示词
PROP_IMAGE_COMMON_PROMPT = """product photography, white background, centered composition, high detail, studio lighting, 8k quality"""

# 分镜首帧生成提示词模板
FIRST_FRAME_PROMPT_TEMPLATE = """cinematic still frame, {scene_setting}, {characters} {action}, {lighting}, {mood} atmosphere, {composition} composition, film photography, 8k quality"""

