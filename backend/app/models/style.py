"""
风格数据模型
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class StyleImage(BaseModel):
    """风格图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引
    url: Optional[str] = None  # 图片 URL
    prompt_used: Optional[str] = None  # 生成时使用的提示词
    created_at: datetime = Field(default_factory=datetime.now)


class TextStyleVersion(BaseModel):
    """纯文本风格版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""  # 版本名称
    content: str = ""  # JSON 格式的风格描述
    created_at: datetime = Field(default_factory=datetime.now)
    modified_info: str = ""  # 修改说明


class Style(BaseModel):
    """风格"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    name: str  # 风格名称
    description: str = ""  # 风格描述
    
    # 风格类型: "image" 或 "text"
    style_type: str = "image"
    
    # 图片风格相关字段
    style_prompt: str = ""  # 风格提示词（用于生成参考图）
    negative_prompt: str = ""  # 负向提示词
    preset_name: Optional[str] = None  # 预设名称（如果使用了预设）
    image_groups: List[StyleImage] = []  # 风格图片组
    selected_group_index: int = 0  # 选中的组索引
    
    # 纯文本风格相关字段
    text_style_content: str = ""  # 当前文本风格内容（JSON 格式）
    text_style_versions: List[TextStyleVersion] = []  # 文本风格版本历史
    text_preset_name: Optional[str] = None  # 文本预设名称
    
    # 是否为当前选中的风格
    is_selected: bool = False
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def thumbnail_url(self) -> Optional[str]:
        """获取缩略图URL（仅图片风格有效）"""
        if self.style_type == "image" and self.image_groups and self.selected_group_index < len(self.image_groups):
            return self.image_groups[self.selected_group_index].url
        return None


# 图片风格预设
IMAGE_STYLE_PRESETS = {
    "anime": {
        "name": "日本动漫风格",
        "prompt": "anime style, Japanese animation, vibrant colors, detailed character design, studio ghibli inspired, fantasy scene with characters and props, dramatic lighting, cinematic composition",
        "negative_prompt": "realistic, photo, 3d render, blurry, low quality"
    },
    "pixar": {
        "name": "皮克斯3D风格",
        "prompt": "pixar 3d animation style, cute cartoon characters in detailed scene, warm lighting, colorful environment with props, high quality render, expressive faces, disney pixar movie screenshot",
        "negative_prompt": "realistic, 2d, anime, sketch, low quality"
    },
    "watercolor": {
        "name": "水彩画风格",
        "prompt": "watercolor painting style, soft edges, artistic brushstrokes, characters and scenery in watercolor, pastel colors, traditional art, dreamy atmosphere, handpainted look",
        "negative_prompt": "digital art, sharp edges, realistic, photo, 3d"
    },
    "oil_painting": {
        "name": "油画风格",
        "prompt": "oil painting style, classical art technique, rich textures, dramatic lighting, characters and scene in oil paint, museum quality, renaissance inspired, thick brushstrokes",
        "negative_prompt": "digital art, anime, cartoon, photo, flat colors"
    },
    "cyberpunk": {
        "name": "赛博朋克风格",
        "prompt": "cyberpunk style, neon lights, futuristic city, high tech low life, characters with cybernetic enhancements, rainy night scene, holographic displays, blade runner inspired",
        "negative_prompt": "natural, daylight, medieval, fantasy, cartoon"
    },
    "chinese_ink": {
        "name": "中国水墨风格",
        "prompt": "traditional chinese ink painting style, brush strokes, black ink with subtle color washes, mountains and figures, calligraphy aesthetic, zen atmosphere, white space",
        "negative_prompt": "colorful, western art, digital, 3d, anime"
    },
    "comic_book": {
        "name": "美式漫画风格",
        "prompt": "american comic book style, bold outlines, dynamic action poses, halftone dots, speech bubbles, superhero aesthetic, vivid colors, marvel dc inspired",
        "negative_prompt": "realistic, anime, watercolor, soft edges, 3d"
    },
    "studio_ghibli": {
        "name": "吉卜力工作室风格",
        "prompt": "studio ghibli style, miyazaki inspired, whimsical fantasy, lush nature, detailed backgrounds, warm colors, magical atmosphere, hand-drawn animation look",
        "negative_prompt": "3d, realistic, dark, horror, modern"
    },
    "low_poly": {
        "name": "低多边形风格",
        "prompt": "low poly 3d art style, geometric shapes, minimalist, flat shading, colorful facets, isometric view, characters and scene in low poly, modern design",
        "negative_prompt": "realistic, detailed, smooth, organic, photo"
    },
    "vintage_poster": {
        "name": "复古海报风格",
        "prompt": "vintage poster art style, retro illustration, limited color palette, art deco influence, bold typography space, characters in classic poster composition, 1950s aesthetic",
        "negative_prompt": "modern, photorealistic, 3d, digital effects"
    }
}

# 纯文本风格预设（JSON 格式描述）
TEXT_STYLE_PRESETS = {
    "cute_pet": {
        "name": "可爱宠物风格",
        "content": """{
  "style_definition": {
    "art_style": "digital illustration",
    "rendering": "soft shading, clean lines",
    "color_palette": ["warm tones", "pastel colors", "high saturation"],
    "lighting": "soft studio lighting, no harsh shadows"
  },
  "subject_treatment": {
    "character_style": "cute, adorable, expressive eyes",
    "pose_preference": "natural, relaxed poses",
    "expression": "friendly, approachable"
  },
  "composition": {
    "background": "solid white or soft gradient",
    "framing": "centered subject, adequate negative space",
    "style": "high-key photography aesthetic"
  },
  "tags": ["cute", "adorable", "studio shot", "isolated subject"]
}"""
    },
    "fantasy_character": {
        "name": "奇幻角色风格",
        "content": """{
  "style_definition": {
    "art_style": "fantasy illustration, concept art",
    "rendering": "detailed painterly style, rich textures",
    "color_palette": ["jewel tones", "dramatic contrasts", "magical glow effects"],
    "lighting": "dramatic rim lighting, atmospheric fog"
  },
  "subject_treatment": {
    "character_style": "heroic proportions, detailed armor/clothing",
    "pose_preference": "dynamic, powerful stances",
    "expression": "determined, confident"
  },
  "composition": {
    "background": "epic fantasy environment hints",
    "framing": "dynamic angles, cinematic composition",
    "style": "movie poster aesthetic"
  },
  "tags": ["fantasy", "epic", "heroic", "magical", "cinematic"]
}"""
    },
    "anime_style": {
        "name": "日式动漫风格",
        "content": """{
  "style_definition": {
    "art_style": "anime, japanese animation",
    "rendering": "cel shading, clean outlines, flat colors with gradients",
    "color_palette": ["vibrant colors", "high saturation", "characteristic anime color schemes"],
    "lighting": "dramatic anime lighting, rim lights, ambient occlusion"
  },
  "subject_treatment": {
    "character_style": "anime proportions, large expressive eyes, stylized features",
    "pose_preference": "dynamic action poses or cute idle poses",
    "expression": "exaggerated, expressive anime emotions"
  },
  "composition": {
    "background": "detailed anime backgrounds or simple gradient",
    "framing": "manga-inspired composition",
    "style": "anime key visual aesthetic"
  },
  "tags": ["anime", "manga", "japanese", "stylized", "expressive"]
}"""
    },
    "realistic_portrait": {
        "name": "写实肖像风格",
        "content": """{
  "style_definition": {
    "art_style": "photorealistic, hyperrealistic",
    "rendering": "detailed skin textures, subsurface scattering, fine details",
    "color_palette": ["natural skin tones", "realistic lighting colors"],
    "lighting": "professional portrait lighting, three-point setup"
  },
  "subject_treatment": {
    "character_style": "realistic human proportions, natural features",
    "pose_preference": "natural, professional portrait poses",
    "expression": "subtle, natural emotions"
  },
  "composition": {
    "background": "studio backdrop or environmental portrait",
    "framing": "portrait framing, rule of thirds",
    "style": "professional photography aesthetic"
  },
  "tags": ["realistic", "portrait", "photography", "professional", "detailed"]
}"""
    },
    "pixel_art": {
        "name": "像素艺术风格",
        "content": """{
  "style_definition": {
    "art_style": "pixel art, retro game art",
    "rendering": "limited color palette, visible pixels, dithering",
    "color_palette": ["16-bit color palette", "limited but vibrant colors"],
    "lighting": "simplified lighting, cel-shaded pixels"
  },
  "subject_treatment": {
    "character_style": "chibi or retro game character proportions",
    "pose_preference": "iconic, readable silhouettes",
    "expression": "simple, clear expressions"
  },
  "composition": {
    "background": "pixel art environment or solid color",
    "framing": "game sprite composition",
    "style": "retro video game aesthetic"
  },
  "tags": ["pixel", "retro", "8-bit", "16-bit", "game art", "nostalgic"]
}"""
    },
    "minimalist": {
        "name": "极简主义风格",
        "content": """{
  "style_definition": {
    "art_style": "minimalist, flat design",
    "rendering": "flat colors, clean shapes, no gradients",
    "color_palette": ["limited palette", "2-3 main colors", "high contrast"],
    "lighting": "no lighting effects, flat appearance"
  },
  "subject_treatment": {
    "character_style": "simplified shapes, geometric forms",
    "pose_preference": "simple, iconic poses",
    "expression": "minimal or no facial details"
  },
  "composition": {
    "background": "solid color or simple gradient",
    "framing": "lots of negative space",
    "style": "modern design aesthetic, logo-like"
  },
  "tags": ["minimal", "clean", "simple", "modern", "flat design"]
}"""
    }
}

# 兼容旧的 STYLE_PRESETS 名称
STYLE_PRESETS = IMAGE_STYLE_PRESETS
