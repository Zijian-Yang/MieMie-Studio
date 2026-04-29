"""
视频工作室能力 schema 服务

统一聚合：
1. 现有 Wan / VACE / 数字人能力
2. Kling 多能力视频模型
3. Vidu 系列视频模型

该模块返回前端可直接消费的能力定义，作为视频工作室的新配置源。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from app.config import (
    KEYFRAME_TO_VIDEO_MODELS,
    REF_VIDEO_MODELS,
    TEXT_TO_VIDEO_MODELS,
    VIDEO_EDIT_MODELS,
    VIDEO_MODELS,
    VIDEO_REPAINTING_MODELS,
)
from app.services.model_rate_limits import rate_limit_capabilities


TASK_KIND_DEFS: List[Dict[str, Any]] = [
    {
        "id": "text_to_video",
        "label": "文生视频",
        "description": "基于文本提示词生成视频",
        "legacy_task_types": ["text_to_video"],
    },
    {
        "id": "image_to_video",
        "label": "首帧生视频",
        "description": "基于单张首帧图片生成视频",
        "legacy_task_types": ["image_to_video"],
    },
    {
        "id": "keyframe_to_video",
        "label": "首尾帧生视频",
        "description": "基于首帧和尾帧图片生成平滑过渡视频",
        "legacy_task_types": ["keyframe_to_video"],
    },
    {
        "id": "video_extension",
        "label": "视频续写",
        "description": "基于首段视频续写生成后续内容",
        "legacy_task_types": ["video_extension"],
    },
    {
        "id": "reference_to_video",
        "label": "参考生视频",
        "description": "基于参考图片或参考视频生成新视频",
        "legacy_task_types": ["reference_to_video"],
    },
    {
        "id": "video_edit_global",
        "label": "视频编辑",
        "description": "基于整段视频进行重构和编辑",
        "legacy_task_types": ["video_edit_global"],
    },
    {
        "id": "video_edit_local",
        "label": "局部编辑",
        "description": "基于首帧 Mask 对视频局部区域进行编辑",
        "legacy_task_types": ["video_edit"],
    },
    {
        "id": "video_repainting",
        "label": "视频重绘",
        "description": "提取源视频特征并重绘生成新视频",
        "legacy_task_types": ["video_repainting"],
    },
]

VIDEO_STUDIO_DEFAULT_MODELS = {
    "text_to_video": "wan2.7-t2v",
    "reference_to_video": "wan2.7-r2v",
}


LEGACY_TASK_KIND_MAP = {
    "image_to_video": "image_to_video",
    "reference_to_video": "reference_to_video",
    "text_to_video": "text_to_video",
    "keyframe_to_video": "keyframe_to_video",
    "video_extension": "video_extension",
    "video_repainting": "video_repainting",
    "video_edit": "video_edit_local",
    "video_edit_global": "video_edit_global",
}


def _select_option(value: Any, label: str, description: str = "") -> Dict[str, Any]:
    return {"value": value, "label": label, "description": description}


def _help(
    *,
    summary: str | None = None,
    meaning: str | None = None,
    limits: List[str] | None = None,
    how_to_choose: List[str] | None = None,
    examples: List[str] | None = None,
    notes: List[str] | None = None,
) -> Dict[str, Any]:
    payload = {
        "summary": summary,
        "meaning": meaning,
        "limits": limits or None,
        "how_to_choose": how_to_choose or None,
        "examples": examples or None,
        "notes": notes or None,
    }
    return {key: value for key, value in payload.items() if value}


def _param(
    name: str,
    label: str,
    param_type: str,
    *,
    description: str = "",
    help: Dict[str, Any] | None = None,
    required: bool = False,
    default: Any = None,
    group: str = "advanced",
    order: int = 0,
    advanced: bool = False,
    min_value: Any = None,
    max_value: Any = None,
    max_length: int | None = None,
    options: List[Dict[str, Any]] | None = None,
    depends_on: str | None = None,
    depends_value: Any = None,
) -> Dict[str, Any]:
    constraint: Dict[str, Any] = {}
    if min_value is not None:
        constraint["min_value"] = min_value
    if max_value is not None:
        constraint["max_value"] = max_value
    if max_length is not None:
        constraint["max_length"] = max_length
    if options is not None:
        constraint["options"] = options
    if depends_on is not None:
        constraint["depends_on"] = depends_on
        constraint["depends_value"] = depends_value

    return {
        "name": name,
        "label": label,
        "type": param_type,
        "description": description,
        "help": help,
        "required": required,
        "default": default,
        "constraint": constraint or None,
        "group": group,
        "advanced": advanced,
        "order": order,
    }


def _bool_param(
    name: str,
    label: str,
    default: bool,
    description: str,
    order: int,
    *,
    help: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return _param(name, label, "boolean", default=default, description=description, order=order, help=help)


def _tags_param(
    name: str,
    label: str,
    *,
    description: str,
    help: Dict[str, Any] | None = None,
    group: str = "advanced",
    order: int = 0,
    advanced: bool = True,
) -> Dict[str, Any]:
    return _param(
        name,
        label,
        "tags",
        description=description,
        help=help,
        group=group,
        order=order,
        advanced=advanced,
    )


def _seed_help() -> Dict[str, Any]:
    return _help(
        summary="随机数种子用于提升结果的可复现性。",
        meaning="固定相同 seed 后，模型会尽量沿着相近的随机路径生成内容；不填写时由系统自动随机。",
        limits=["取值范围为 0 到 2147483647"],
        how_to_choose=["希望多次试验结果更稳定时固定 seed", "想要更多随机变化时留空"],
        examples=["例如：12345"],
        notes=["即使 seed 相同，生成式模型也不能保证每次输出完全一致。"],
    )


def _watermark_help(text: str) -> Dict[str, Any]:
    return _help(
        summary="控制是否保留模型侧默认水印。",
        meaning="打开后会在视频右下角保留厂商规定的 AI 生成标识。",
        how_to_choose=["内测预览或对外演示时通常建议关闭", "需要保留模型官方标识时开启"],
        notes=[text],
    )


def _audio_help(summary: str, notes: List[str] | None = None) -> Dict[str, Any]:
    return _help(
        summary=summary,
        meaning="开启后模型会尝试为视频自动生成背景音乐或音效；关闭则输出无声视频。",
        how_to_choose=["需要快速预览画面时可先关闭", "需要完整交付或听感预览时再开启"],
        notes=notes or [],
    )


def _prompt_extend_help(recommended_off: bool = False) -> Dict[str, Any]:
    notes = ["短 prompt 常能从智能改写里获益。"]
    if recommended_off:
        notes.insert(0, "当输入素材和目标描述差异较大时，建议关闭智能改写，直接手写更具体的 prompt。")
    return _help(
        summary="是否让模型先自动润色 prompt 再生成。",
        meaning="开启后会用大模型补充描述细节，提升短提示词效果，但会增加耗时，也可能让控制更发散。",
        how_to_choose=["需要更强可控性时关闭", "提示词较短、想让模型补充细节时开启"],
        notes=notes,
    )


def _duration_help(summary: str, limits: List[str], notes: List[str] | None = None) -> Dict[str, Any]:
    return _help(
        summary=summary,
        meaning="时长直接决定生成长度，也通常直接影响计费。",
        limits=limits,
        how_to_choose=["先用较短时长验证画面和动作", "确认效果后再逐步拉长"],
        notes=notes or [],
    )


def _asset_help(
    summary: str,
    *,
    limits: List[str] | None = None,
    how_to_choose: List[str] | None = None,
    examples: List[str] | None = None,
    notes: List[str] | None = None,
) -> Dict[str, Any]:
    return _help(
        summary=summary,
        limits=limits,
        how_to_choose=how_to_choose,
        examples=examples,
        notes=notes,
    )


def _default_verification_profiles(provider: str, task_kind: str, profile: Dict[str, Any]) -> Dict[str, List[str]]:
    if provider == "kling" and task_kind == "text_to_video":
        modes = profile.get("supported_narrative_modes", ["single"])
        full_variants = ["single"]
        if "multi_shot_intelligence" in modes:
            full_variants.append("multi_shot_intelligence")
        if "multi_shot_customize" in modes:
            full_variants.append("multi_shot_customize")
        return {"smoke": ["single"], "full": full_variants}

    if task_kind == "reference_to_video":
        input_roles = set(profile.get("input_roles", []))
        variants = ["image_only"]
        if "reference_video" in input_roles:
            variants.append("video_plus_image")
        return {"smoke": ["image_only"], "full": variants}

    if task_kind == "video_edit_global":
        return {"smoke": ["base_only"], "full": ["base_only", "base_plus_reference"]}

    return {"smoke": ["default"], "full": ["default"]}


def _build_model(
    *,
    model_id: str,
    name: str,
    provider: str,
    description: str,
    recommended: bool = False,
    doc_url: str = "",
    supported_task_kinds: List[str],
    task_profiles: Dict[str, Dict[str, Any]],
    ui_hints: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized_profiles: Dict[str, Dict[str, Any]] = {}
    for task_kind, profile in task_profiles.items():
        normalized_profiles[task_kind] = {
            "task_kind": task_kind,
            "label": profile.get("label", task_kind),
            "description": profile.get("description", ""),
            "input_roles": profile.get("input_roles", []),
            "parameters": profile.get("parameters", []),
            "ui_hints": profile.get("ui_hints", {}),
            "supported_narrative_modes": profile.get("supported_narrative_modes", ["single"]),
            "verification_profiles": profile.get(
                "verification_profiles",
                _default_verification_profiles(provider, task_kind, profile),
            ),
            "default_values": {
                param["name"]: param["default"]
                for param in profile.get("parameters", [])
                if param.get("default") is not None
            },
        }

    return {
        "id": model_id,
        "name": name,
        "provider": provider,
        "type": supported_task_kinds[0] if supported_task_kinds else "video",
        "description": description,
        "doc_url": doc_url,
        "capabilities": rate_limit_capabilities(model_id),
        "supported_task_kinds": supported_task_kinds,
        "task_profiles": normalized_profiles,
        "ui_hints": ui_hints or {},
    }


def _wan_text_to_video_models() -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}
    for model_id, info in TEXT_TO_VIDEO_MODELS.items():
        size_options: List[Dict[str, Any]] = []
        size_options.extend(info.get("resolutions_1080p", []))
        size_options.extend(info.get("resolutions_720p", []))
        size_options.extend(info.get("resolutions_480p", []))

        duration_options = [_select_option(value, f"{value}秒") for value in info.get("durations", [])]
        duration_param = _param(
            "duration",
            "时长",
            "integer" if info.get("duration_range") else "select",
            description="视频时长（秒）",
            help=_duration_help(
                "控制最终生成视频的长度。",
                limits=[
                    f"当前模型支持的时长范围：{(info.get('duration_range') or [info.get('durations', [5])[0], info.get('durations', [5])[-1]])[0]} 到 {(info.get('duration_range') or [info.get('durations', [5])[0], info.get('durations', [5])[-1]])[1]} 秒"
                ] if info.get("duration_range") or info.get("durations") else ["默认 5 秒"],
            ),
            default=info.get("default_duration", 5),
            group="generation",
            order=2,
            min_value=(info.get("duration_range") or [None, None])[0],
            max_value=(info.get("duration_range") or [None, None])[1],
            options=duration_options or None,
        )

        parameters = [
            _param(
                "size",
                "分辨率",
                "select",
                description="输出分辨率",
                help=_help(
                    summary="控制输出视频的宽高和清晰度档位。",
                    meaning="不同 size 会同时影响画面比例、清晰度和计费。",
                    how_to_choose=["先按目标发布平台选择横屏、竖屏或方屏", "先用较低成本分辨率验证内容，再切到最终档位"],
                ),
                default=info.get("default_size"),
                group="generation",
                order=1,
                options=[_select_option(item["value"], item["label"]) for item in size_options],
            ),
            duration_param,
            _bool_param("prompt_extend", "智能改写", info.get("supports_prompt_extend", True), "自动优化提示词", 3, help=_prompt_extend_help()),
            _bool_param("watermark", "添加水印", False, "是否添加 AI 生成水印", 5, help=_watermark_help("万相水印文案为“AI生成”。")),
        ]
        if info.get("supports_shot_type"):
            parameters.append(
                _param(
                    "shot_type",
                    "镜头类型",
                    "select",
                    description="单镜头或多镜头",
                    help=_help(
                        summary="控制视频叙事是单镜头还是多镜头。",
                        limits=["仅在开启智能改写时生效"],
                        how_to_choose=["产品展示、单段动作优先用单镜头", "故事表达或多个动作节奏可尝试多镜头"],
                        notes=["关闭智能改写后该参数会自动禁用并清空。", "该参数生效时会优先覆盖 prompt 中的镜头描述。"],
                    ),
                    default=info.get("default_shot_type", "single"),
                    group="generation",
                    order=4,
                    depends_on="prompt_extend",
                    depends_value=True,
                    options=[
                        _select_option("single", "单镜头"),
                        _select_option("multi", "多镜头"),
                    ],
                )
            )
        if info.get("supports_audio_toggle"):
            parameters.append(_bool_param("audio", "自动配音", True, "自动生成声音", 6, help=_audio_help("控制是否让模型自动生成声音。", ["如果同时提供自定义音频，模型会优先使用音频素材。"])))
        if info.get("supports_seed"):
            parameters.append(
                _param(
                    "seed",
                    "随机种子",
                    "integer",
                    description="0 到 2147483647，留空为随机",
                    help=_seed_help(),
                    group="advanced",
                    advanced=True,
                    order=7,
                    min_value=0,
                    max_value=2147483647,
                )
            )

        models[model_id] = _build_model(
            model_id=model_id,
            name=info["name"],
            provider="wan",
            description=info.get("description", ""),
            recommended=model_id == "wan2.6-t2v",
            doc_url="https://help.aliyun.com/zh/model-studio/text-to-video-api",
            supported_task_kinds=["text_to_video"],
            task_profiles={
                "text_to_video": {
                    "label": "文生视频",
                    "description": info.get("description", ""),
                    "input_roles": ["audio"] if info.get("supports_audio") else [],
                    "parameters": parameters,
                    "supported_narrative_modes": ["single", "multi_shot_intelligence"],
                    "ui_hints": {
                        "prompt_max_length": info.get("prompt_max_length", 1500),
                        "negative_prompt_max_length": info.get("negative_prompt_max_length", 500),
                        "asset_help": {
                            "audio": _asset_help(
                                "可选自定义音频会优先覆盖自动音频生成。",
                                limits=["仅 Wan 2.5 / 2.6 文生视频支持", "请优先使用音频库中可长期访问的音频 URL"],
                                how_to_choose=["需要明确旁白、配音或现成音轨时使用", "只想让模型自动生成环境音时可留空"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 用于描述画面主体、动作、场景、镜头语言和风格。",
                            limits=[f"提示词最大长度：{info.get('prompt_max_length', 1500)} 字符"],
                            how_to_choose=["先写主体和动作，再补场景、镜头、风格", "想更稳定时用明确、具体的描述"],
                            examples=["例如：工业机械臂在仓库中平稳打开柜门，镜头缓慢推进，冷色工业风。"],
                            notes=["Wan 2.6 的镜头类型参数仅在开启智能改写时生效。"],
                        ),
                    },
                }
            },
        )
    return models


def _wan_image_to_video_models() -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}
    for model_id, info in VIDEO_MODELS.items():
        parameters = [
            _param(
                "resolution",
                "分辨率",
                "select",
                description="输出分辨率档位",
                help=_help(
                    summary="控制输出分辨率档位。",
                    meaning="不同档位会影响清晰度、生成速度和成本。",
                    how_to_choose=["先用低档位验证动作与构图", "确认内容后再切高档位出最终结果"],
                ),
                default=info.get("default_resolution"),
                group="generation",
                order=1,
                options=[_select_option(item["value"], item["label"]) for item in info.get("resolutions", [])],
            ),
            _param(
                "duration",
                "时长",
                "integer" if info.get("duration_range") else "select",
                description="视频时长（秒）",
                help=_duration_help(
                    "控制最终生成视频的长度。",
                    limits=[
                        f"当前模型支持的时长范围：{(info.get('duration_range') or [info.get('durations', [5])[0], info.get('durations', [5])[-1]])[0]} 到 {(info.get('duration_range') or [info.get('durations', [5])[0], info.get('durations', [5])[-1]])[1]} 秒"
                    ] if info.get("duration_range") or info.get("durations") else ["默认 5 秒"],
                ),
                default=info.get("default_duration", 5),
                group="generation",
                order=2,
                min_value=(info.get("duration_range") or [None, None])[0],
                max_value=(info.get("duration_range") or [None, None])[1],
                options=[_select_option(value, f"{value}秒") for value in info.get("durations", [])] or None,
            ),
            _bool_param("prompt_extend", "智能改写", info.get("supports_prompt_extend", False), "自动优化提示词", 3, help=_prompt_extend_help()),
            _bool_param("watermark", "添加水印", False, "是否添加 AI 生成水印", 5, help=_watermark_help("万相水印文案为“AI生成”。")),
        ]
        if info.get("supports_shot_type"):
            parameters.append(
                _param(
                    "shot_type",
                    "镜头类型",
                    "select",
                    description="单镜头或多镜头",
                    help=_help(
                        summary="控制视频叙事是单镜头还是多镜头。",
                        limits=["仅在开启智能改写时生效"],
                        how_to_choose=["人物/物体单段动作优先用单镜头", "想让模型拆分多个镜头节奏时再尝试多镜头"],
                        notes=["关闭智能改写后该参数会自动禁用并清空。", "该参数生效时会优先覆盖 prompt 中的镜头描述。"],
                    ),
                    default=info.get("default_shot_type", "single"),
                    group="generation",
                    order=4,
                    depends_on="prompt_extend",
                    depends_value=True,
                    options=[
                        _select_option("single", "单镜头"),
                        _select_option("multi", "多镜头"),
                    ],
                )
            )
        if info.get("supports_audio_toggle"):
            parameters.append(_bool_param("audio", "自动配音", True, "自动生成声音", 6, help=_audio_help("控制是否让模型自动生成背景音或音效。", ["如果同时提供自定义音频，模型会优先使用音频素材。"])))
        if info.get("supports_seed"):
            parameters.append(
                _param(
                    "seed",
                    "随机种子",
                    "integer",
                    description="0 到 2147483647，留空为随机",
                    help=_seed_help(),
                    group="advanced",
                    advanced=True,
                    order=7,
                    min_value=0,
                    max_value=2147483647,
                )
            )

        models[model_id] = _build_model(
            model_id=model_id,
            name=info["name"],
            provider="wan",
            description=info.get("description", ""),
            recommended=model_id == "wan2.6-i2v-flash",
            doc_url="https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference",
            supported_task_kinds=["image_to_video"],
            task_profiles={
                "image_to_video": {
                    "label": "首帧生视频",
                    "description": info.get("description", ""),
                    "input_roles": ["first_frame"] + (["audio"] if (info.get("requires_audio") or model_id.startswith("wan2.5") or model_id.startswith("wan2.6")) else []),
                    "parameters": parameters,
                    "supported_narrative_modes": ["single", "multi_shot_intelligence"] if info.get("supports_shot_type") else ["single"],
                    "ui_hints": {
                        "requires_audio": info.get("requires_audio", False),
                        "supports_prompt": info.get("supports_prompt", True),
                        "asset_help": {
                            "audio": _asset_help(
                                "自定义音频会作为首帧生视频的音轨输入。",
                                limits=["Wan 2.5 / 2.6 首帧生视频支持自定义音频", "wan2.6-i2v-flash 中若同时开启自动音频并提供自定义音频，模型会优先使用音频素材"],
                                how_to_choose=["需要明确旁白、对白或现成声音时使用", "只想让模型自动补声音时可留空"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 用于描述首帧之后的视频运动、镜头和风格。",
                            how_to_choose=["先描述‘怎么动’，再描述镜头和氛围", "若模型更依赖首帧，prompt 可更聚焦动作和镜头变化"],
                            notes=["Wan 首帧生视频不需要手动选择 size，输出尺寸会跟随输入图比例并按模型要求做 16 倍数微调。", "Wan 2.6 的镜头类型参数仅在开启智能改写时生效。"],
                        ),
                    },
                }
            },
        )
    return models


def _wan_reference_to_video_models() -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}
    for model_id, info in REF_VIDEO_MODELS.items():
        size_options: List[Dict[str, Any]] = []
        size_options.extend(info.get("resolutions_1080p", []))
        size_options.extend(info.get("resolutions_720p", []))
        parameters = [
            _param(
                "size",
                "分辨率",
                "select",
                description="输出分辨率",
                help=_help(
                    summary="控制输出视频尺寸和宽高比。",
                    how_to_choose=["参考视频较多时，优先选与主要参考素材接近的比例", "要发短视频平台时优先竖屏尺寸"],
                ),
                default=info.get("default_size"),
                group="generation",
                order=1,
                options=[_select_option(item["value"], item["label"]) for item in size_options],
            ),
            _param(
                "duration",
                "时长",
                "integer",
                description="视频时长（秒）",
                help=_duration_help(
                    "控制生成视频总时长。",
                    limits=[f"当前模型支持 {info.get('min_duration', 2)} 到 {info.get('max_duration', 10)} 秒"],
                ),
                default=info.get("default_duration", 5),
                group="generation",
                order=2,
                min_value=info.get("min_duration", 2),
                max_value=info.get("max_duration", 10),
            ),
            _bool_param("watermark", "添加水印", False, "是否添加 AI 生成水印", 4, help=_watermark_help("万相水印文案为“AI生成”。")),
        ]
        if info.get("supports_shot_type"):
            parameters.append(
                _param(
                    "shot_type",
                    "镜头类型",
                    "select",
                    description="单镜头或多镜头",
                    help=_help(
                        summary="控制参考生视频是单镜头还是多镜头叙事。",
                        how_to_choose=["参考素材较少、动作简单时优先单镜头", "想让模型根据提示做多段镜头演绎时可尝试多镜头"],
                    ),
                    default=info.get("default_shot_type", "single"),
                    group="generation",
                    order=3,
                    options=[
                        _select_option("single", "单镜头"),
                        _select_option("multi", "多镜头"),
                    ],
                )
            )
        if info.get("supports_audio_toggle"):
            parameters.append(_bool_param("audio", "有声视频", True, "是否保留声音", 5, help=_audio_help("控制输出是否保留声音。")))
        if info.get("supports_seed"):
            parameters.append(
                _param(
                    "seed",
                    "随机种子",
                    "integer",
                    description="0 到 2147483647，留空为随机",
                    help=_seed_help(),
                    group="advanced",
                    advanced=True,
                    order=6,
                    min_value=0,
                    max_value=2147483647,
                )
            )

        models[model_id] = _build_model(
            model_id=model_id,
            name=info["name"],
            provider="wan",
            description=info.get("description", ""),
            recommended=model_id == "wan2.6-r2v-flash",
            doc_url="https://help.aliyun.com/zh/model-studio/wan-video-to-video-api-reference",
            supported_task_kinds=["reference_to_video"],
            task_profiles={
                "reference_to_video": {
                    "label": "参考生视频",
                    "description": info.get("description", ""),
                    "input_roles": ["reference_image", "reference_video"],
                    "parameters": parameters,
                    "supported_narrative_modes": ["single", "multi_shot_intelligence"] if info.get("supports_shot_type") else ["single"],
                    "ui_hints": {
                        "max_reference_images": info.get("max_reference_images", 5),
                        "max_reference_videos": info.get("max_reference_videos", 3),
                        "max_reference_total": info.get("max_reference_total", 5),
                        "prompt_help": _help(
                            summary="Prompt 用于说明参考素材要如何被组合、演绎或转化成新视频。",
                            how_to_choose=["写清楚主体关系、动作、镜头和氛围", "若参考素材很多，prompt 更要明确主次关系"],
                            notes=["前端会分别收集参考图和参考视频，但提交时会按照官方 reference_urls 语义组合成混合参考列表。", "如果你在 prompt 中写 character1、character2 等引用，请确保它们与素材添加顺序一致。"],
                        ),
                    },
                }
            },
        )
    return models


def _wan_keyframe_models() -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}
    for model_id, info in KEYFRAME_TO_VIDEO_MODELS.items():
        parameters = [
            _param(
                "resolution",
                "分辨率",
                "select",
                description="输出分辨率档位",
                help=_help(
                    summary="控制首尾帧生视频的输出分辨率。",
                    how_to_choose=["首尾帧图质量较高时可用高分辨率", "如果只是先看过渡效果，低一档更省成本"],
                ),
                default=info.get("default_resolution"),
                group="generation",
                order=1,
                options=[_select_option(value, value) for value in info.get("resolutions", [])],
            ),
            _bool_param("prompt_extend", "智能改写", info.get("supports_prompt_extend", True), "自动优化提示词", 2, help=_prompt_extend_help()),
            _bool_param("watermark", "添加水印", False, "是否添加 AI 生成水印", 3, help=_watermark_help("万相水印文案为“AI生成”。")),
        ]
        if info.get("supports_seed"):
            parameters.append(
                _param(
                    "seed",
                    "随机种子",
                    "integer",
                    description="0 到 2147483647，留空为随机",
                    help=_seed_help(),
                    group="advanced",
                    advanced=True,
                    order=4,
                    min_value=0,
                    max_value=2147483647,
                )
            )

        models[model_id] = _build_model(
            model_id=model_id,
            name=info["name"],
            provider="wan",
            description=info.get("description", ""),
            recommended=True,
            doc_url="https://help.aliyun.com/zh/model-studio/image-to-video-by-first-and-last-frame-api-reference",
            supported_task_kinds=["keyframe_to_video"],
            task_profiles={
                "keyframe_to_video": {
                    "label": "首尾帧生视频",
                    "description": info.get("description", ""),
                    "input_roles": ["first_frame", "last_frame"],
                    "parameters": parameters,
                    "ui_hints": {
                        "duration": info.get("duration", 5),
                        "prompt_max_length": info.get("prompt_max_length", 800),
                        "prompt_help": _help(
                            summary="Prompt 用于描述首帧到尾帧之间应该发生的变化过程。",
                            limits=[f"提示词最大长度：{info.get('prompt_max_length', 800)} 字符"],
                            how_to_choose=["重点描述‘如何从首帧过渡到尾帧’", "不要重复描述首尾帧里已经很明显的静态内容"],
                        ),
                    },
                }
            },
        )
    return models


def _wan27_video_models() -> Dict[str, Dict[str, Any]]:
    resolution_options = [
        _select_option("720P", "720P", "更适合预览与快速试验"),
        _select_option("1080P", "1080P", "画面更清晰，耗时通常更高"),
    ]
    ratio_options = [
        _select_option("16:9", "16:9 横屏", "适合桌面播放与横屏内容"),
        _select_option("9:16", "9:16 竖屏", "适合短视频与手机观看"),
        _select_option("1:1", "1:1 方形", "适合封面与社媒方形内容"),
        _select_option("4:3", "4:3 横版", "适合较传统的画面构图"),
        _select_option("3:4", "3:4 竖版", "适合人像与竖版展示"),
    ]
    audio_setting_options = [
        _select_option("auto", "auto（自动生成/判断）", "让模型自动决定声音生成方式"),
        _select_option("origin", "origin（保留原声）", "尽量保留输入视频原有声音"),
    ]

    i2v_common_params = [
        _param(
            "resolution",
            "分辨率档位",
            "select",
            default="1080P",
            description="wan2.7 图生视频仅支持 720P / 1080P。",
            help=_help(
                summary="控制 wan2.7 输出视频清晰度。",
                limits=["仅支持 720P 和 1080P"],
                how_to_choose=["快速试验时先用 720P", "准备交付或看细节时用 1080P"],
            ),
            group="generation",
            order=1,
            options=resolution_options,
        ),
        _param(
            "duration",
            "时长",
            "integer",
            default=5,
            min_value=2,
            max_value=15,
            description="输出时长，支持 2 到 15 秒。",
            help=_duration_help(
                "控制 wan2.7 输出视频时长。",
                limits=["支持 2 到 15 秒整数时长"],
            ),
            group="generation",
            order=2,
        ),
        _bool_param(
            "prompt_extend",
            "智能改写",
            True,
            "开启后由模型先扩写提示词再生成。",
            3,
            help=_prompt_extend_help(),
        ),
        _bool_param("watermark", "添加水印", False, "是否保留 AI 生成水印。", 4, help=_watermark_help("开启后保留万相侧 AI 生成水印。")),
        _param(
            "seed",
            "随机种子",
            "integer",
            description="0 到 2147483647，留空为随机",
            help=_seed_help(),
            group="advanced",
            advanced=True,
            order=5,
            min_value=0,
            max_value=2147483647,
        ),
    ]

    image_prompt_help = _help(
        summary="Prompt 用于描述视频主体、动作、镜头变化和氛围。",
        limits=["最大长度约 5000 字符", "负面提示词最大长度约 500 字符"],
        how_to_choose=["首帧已确定静态构图时，重点写主体如何运动、镜头如何变化", "需要抑制的内容写在负面提示词里"],
        notes=["不传驱动音频时，wan2.7-i2v 会自动补充匹配音频。"],
    )

    t2v_params = [
        _param(
            "resolution",
            "分辨率档位",
            "select",
            default="1080P",
            description="wan2.7 文生视频仅支持 720P / 1080P。",
            help=_help(
                summary="控制文生视频输出清晰度。",
                limits=["仅支持 720P 和 1080P"],
                how_to_choose=["快速试验时先用 720P", "准备交付或看细节时用 1080P"],
            ),
            group="generation",
            order=1,
            options=resolution_options,
        ),
        _param(
            "ratio",
            "画面比例",
            "select",
            default="16:9",
            description="控制输出画面的宽高比。",
            help=_help(
                summary="控制输出画面比例。",
                limits=["仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4"],
                how_to_choose=["横屏内容优先 16:9", "短视频或手机观看优先 9:16", "封面和社媒方形内容可用 1:1"],
                notes=["wan2.7 文生视频的多镜头叙事通过 prompt 自然语言控制，不再提供 shot_type 参数。"],
            ),
            group="generation",
            order=2,
            options=ratio_options,
        ),
        _param(
            "duration",
            "时长",
            "integer",
            default=5,
            min_value=2,
            max_value=15,
            description="输出时长，支持 2 到 15 秒。",
            help=_duration_help(
                "控制 wan2.7 文生视频输出时长。",
                limits=["支持 2 到 15 秒整数时长"],
            ),
            group="generation",
            order=3,
        ),
        _bool_param(
            "prompt_extend",
            "智能改写",
            True,
            "开启后由模型先扩写提示词再生成。",
            4,
            help=_prompt_extend_help(),
        ),
        _bool_param("watermark", "添加水印", False, "是否保留 AI 生成水印。", 5, help=_watermark_help("开启后保留万相侧 AI 生成水印。")),
        _param(
            "seed",
            "随机种子",
            "integer",
            description="0 到 2147483647，留空为随机",
            help=_seed_help(),
            group="advanced",
            advanced=True,
            order=6,
            min_value=0,
            max_value=2147483647,
        ),
    ]

    r2v_params = [
        _param(
            "resolution",
            "分辨率档位",
            "select",
            default="1080P",
            description="wan2.7 参考生视频仅支持 720P / 1080P。",
            help=_help(
                summary="控制参考生视频输出清晰度。",
                limits=["仅支持 720P 和 1080P"],
                how_to_choose=["快速试验时先用 720P", "准备交付或看细节时用 1080P"],
            ),
            group="generation",
            order=1,
            options=resolution_options,
        ),
        _param(
            "ratio",
            "画面比例",
            "select",
            default="16:9",
            description="控制输出画面比例；提供首帧图时会自动跟随首帧比例。",
            help=_help(
                summary="控制输出画面比例。",
                limits=["仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4"],
                how_to_choose=["未提供首帧图时可直接指定横屏、竖屏或方屏", "提供首帧图时可忽略该参数，让模型跟随首帧图比例"],
                notes=["传入首帧图后，provider payload 会自动忽略 ratio 参数。"],
            ),
            group="generation",
            order=2,
            options=ratio_options,
        ),
        _param(
            "duration",
            "时长",
            "integer",
            default=5,
            min_value=2,
            max_value=10,
            description="输出时长，支持 2 到 10 秒。",
            help=_duration_help(
                "控制 wan2.7 参考生视频输出时长。",
                limits=["支持 2 到 10 秒整数时长"],
            ),
            group="generation",
            order=3,
        ),
        _bool_param(
            "prompt_extend",
            "智能改写",
            True,
            "开启后由模型先扩写提示词再生成。",
            4,
            help=_prompt_extend_help(),
        ),
        _bool_param("watermark", "添加水印", False, "是否保留 AI 生成水印。", 5, help=_watermark_help("开启后保留万相侧 AI 生成水印。")),
        _param(
            "seed",
            "随机种子",
            "integer",
            description="0 到 2147483647，留空为随机",
            help=_seed_help(),
            group="advanced",
            advanced=True,
            order=6,
            min_value=0,
            max_value=2147483647,
        ),
    ]

    models = {
        "wan2.7-t2v": _build_model(
            model_id="wan2.7-t2v",
            name="万相 2.7 文生视频",
            provider="wan",
            description="支持分辨率档位、画面比例、自定义音频和自然语言多镜头叙事的万相 2.7 文生视频模型",
            recommended=True,
            doc_url="https://help.aliyun.com/zh/model-studio/text-to-video-guide",
            supported_task_kinds=["text_to_video"],
            task_profiles={
                "text_to_video": {
                    "label": "文生视频",
                    "description": "仅用文本提示词生成视频，可选自定义音频。",
                    "input_roles": ["audio"],
                    "parameters": t2v_params,
                    "supported_narrative_modes": ["single", "multi_shot_intelligence"],
                    "ui_hints": {
                        "prompt_max_length": 5000,
                        "negative_prompt_max_length": 500,
                        "asset_help": {
                            "audio": _asset_help(
                                "自定义音频会直接作为文生视频的音轨输入。",
                                limits=["仅支持 WAV/MP3", "时长需在 2 到 30 秒之间", "文件大小不超过 15MB"],
                                how_to_choose=["需要明确旁白、对白或现成声音时使用", "只想让模型自动生成背景音或音效时可留空"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 用于描述主体、动作、场景、镜头和风格。",
                            limits=["最大长度约 5000 字符", "负面提示词最大长度约 500 字符"],
                            how_to_choose=["先写主体和动作，再补镜头、氛围和风格", "想做多镜头时可直接在 prompt 里写“生成多镜头视频”或按时间段描述分镜"],
                            notes=["wan2.7 文生视频不再提供 shot_type，镜头结构完全由 prompt 控制。", "不传自定义音频时，模型会自动补充匹配的背景音乐或音效。"],
                        ),
                    },
                }
            },
        ),
        "wan2.7-r2v": _build_model(
            model_id="wan2.7-r2v",
            name="万相 2.7 参考生视频",
            provider="wan",
            description="支持首帧图、多张参考图/参考视频和逐素材参考音色绑定的万相 2.7 参考生视频模型",
            recommended=True,
            doc_url="https://help.aliyun.com/zh/model-studio/video-to-video-guide",
            supported_task_kinds=["reference_to_video"],
            task_profiles={
                "reference_to_video": {
                    "label": "参考生视频",
                    "description": "基于参考图像、参考视频和可选首帧图生成新视频。",
                    "input_roles": ["first_frame", "reference_image", "reference_video"],
                    "parameters": r2v_params,
                    "supported_narrative_modes": ["single", "multi_shot_intelligence"],
                    "ui_hints": {
                        "prompt_max_length": 5000,
                        "negative_prompt_max_length": 500,
                        "max_reference_images": 5,
                        "max_reference_videos": 5,
                        "max_reference_total": 5,
                        "supports_reference_voice": True,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图可选，用于约束生成视频的初始构图和输出比例。",
                                limits=["最多 1 张首帧图", "支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                                how_to_choose=["需要明确视频起始画面时再提供", "不提供时由 ratio 控制输出比例"],
                            ),
                            "reference_image": _asset_help(
                                "参考图用于提供人物、动物、物体或场景线索。",
                                limits=["图片和视频总数最多 5 个", "支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                                how_to_choose=["尽量单主体、主体清晰", "需要给纯图片角色绑定音色时，可为该素材额外选择参考音频"],
                            ),
                            "reference_video": _asset_help(
                                "参考视频用于提供主体形象、动作氛围和可选音色参考。",
                                limits=["图片和视频总数最多 5 个", "支持 MP4/MOV", "时长需在 1 到 30 秒之间", "宽高需在 240 到 4096 像素之间", "宽高比需在 1:8 到 8:1 之间", "文件大小不超过 100MB"],
                                how_to_choose=["优先选择单镜头、主体明确的视频", "未显式绑定 reference_voice 时，模型会默认使用参考视频原声做音色参考"],
                            ),
                            "audio": _asset_help(
                                "可从音频库为单个参考素材单独绑定 reference_voice。",
                                limits=["仅支持 WAV/MP3", "时长需在 1 到 10 秒之间", "文件大小不超过 15MB"],
                                how_to_choose=["纯图片角色需要声音时可单独绑定", "想覆盖参考视频原声时也可显式绑定参考音频"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 用于描述参考素材之间的关系、动作和镜头安排。",
                            limits=["最大长度约 5000 字符", "负面提示词最大长度约 500 字符"],
                            how_to_choose=["先写清主体关系和动作，再补镜头、场景和氛围", "引用角色时，按当前列表中同类型素材的顺序使用“图片1 / 图片2 / 视频1 / 视频2”"],
                            notes=["参考素材卡片顺序会直接反映到开发者模式里的 media 顺序。", "首帧图只控制构图与比例，不参与“图片1 / 视频1”的编号。", "未显式绑定 reference_voice 的参考视频会沿用文档默认行为，优先使用视频原声做音色参考。"],
                        ),
                    },
                }
            },
        ),
        "wan2.7-i2v": _build_model(
            model_id="wan2.7-i2v",
            name="万相 2.7 图生视频",
            provider="wan",
            description="支持首帧图、首尾帧、驱动音频和视频续写的万相 2.7 图生视频模型",
            recommended=False,
            doc_url="https://help.aliyun.com/zh/model-studio/wanx-image-to-video-2-7-api-reference",
            supported_task_kinds=["image_to_video", "keyframe_to_video", "video_extension"],
            task_profiles={
                "image_to_video": {
                    "label": "图生视频",
                    "description": "使用首帧图生成视频，可选驱动音频。",
                    "input_roles": ["first_frame", "audio"],
                    "parameters": deepcopy(i2v_common_params),
                    "ui_hints": {
                        "prompt_max_length": 5000,
                        "negative_prompt_max_length": 500,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图决定视频初始构图、主体位置和基础风格。",
                                limits=["支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                                how_to_choose=["主体尽量完整清晰", "避免裁切到关键肢体或主体边缘"],
                            ),
                            "audio": _asset_help(
                                "驱动音频可为视频动作和节奏提供声音参考。",
                                limits=["仅支持 WAV/MP3", "时长需在 2 到 30 秒之间", "文件大小不超过 15MB"],
                                how_to_choose=["需要严格跟随声音节奏时再传入", "不传时模型会自动生成匹配音频"],
                            ),
                        },
                        "prompt_help": image_prompt_help,
                    },
                },
                "keyframe_to_video": {
                    "label": "首尾帧生视频",
                    "description": "使用首帧和尾帧生成平滑过渡视频，可选驱动音频。",
                    "input_roles": ["first_frame", "last_frame", "audio"],
                    "parameters": deepcopy(i2v_common_params),
                    "ui_hints": {
                        "prompt_max_length": 5000,
                        "negative_prompt_max_length": 500,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图定义视频起始状态。",
                                limits=["支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                            ),
                            "last_frame": _asset_help(
                                "尾帧图定义视频结束状态。",
                                limits=["支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                                how_to_choose=["首尾帧主体应保持同一对象或明确可过渡", "适合开合、转身、位移等过渡镜头"],
                            ),
                            "audio": _asset_help(
                                "驱动音频可为视频动作和节奏提供声音参考。",
                                limits=["仅支持 WAV/MP3", "时长需在 2 到 30 秒之间", "文件大小不超过 15MB"],
                                how_to_choose=["需要严格跟随声音节奏时再传入", "不传时模型会自动生成匹配音频"],
                            ),
                        },
                        "prompt_help": image_prompt_help,
                    },
                },
                "video_extension": {
                    "label": "视频续写",
                    "description": "使用首段视频续写后续内容，可选尾帧图辅助收束终点。",
                    "input_roles": ["first_clip", "last_frame"],
                    "parameters": deepcopy(i2v_common_params),
                    "ui_hints": {
                        "prompt_max_length": 5000,
                        "negative_prompt_max_length": 500,
                        "asset_help": {
                            "first_clip": _asset_help(
                                "首段视频用于提供续写前的动作、镜头和节奏起点。",
                                limits=["支持 MP4/MOV", "时长需在 2 到 10 秒之间", "宽高需在 240 到 4096 像素之间", "宽高比需在 1:8 到 8:1 之间", "文件大小不超过 100MB"],
                                how_to_choose=["优先选择单镜头、主体清晰的视频片段", "动作和镜头越明确，续写越稳定"],
                            ),
                            "last_frame": _asset_help(
                                "尾帧图可用于约束续写终点构图；不传时由模型自由结束。",
                                limits=["支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                                how_to_choose=["希望续写在某个明确画面结束时再提供尾帧图"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 描述首段视频之后要继续发生什么，以及镜头或氛围如何延续。",
                            limits=["最大长度约 5000 字符", "负面提示词最大长度约 500 字符"],
                            how_to_choose=["先写续写后的新动作或镜头变化", "如果提供尾帧图，可在提示词里强调如何自然过渡到终点"],
                            notes=["输出比例跟随首段视频，宽高会被模型微调为 16 的倍数。", "视频续写不支持驱动音频。"],
                        ),
                    },
                },
            },
        ),
        "wan2.7-videoedit": _build_model(
            model_id="wan2.7-videoedit",
            name="万相 2.7 视频编辑",
            provider="wan",
            description="支持整段视频编辑和多张参考图引导的万相 2.7 视频编辑模型",
            recommended=False,
            doc_url="https://help.aliyun.com/zh/model-studio/wanx-videoedit-2-7-api-reference",
            supported_task_kinds=["video_edit_global"],
            task_profiles={
                "video_edit_global": {
                    "label": "视频编辑",
                    "description": "对整段视频做风格修改或参考编辑。",
                    "input_roles": ["base_video", "reference_image"],
                    "parameters": [
                        _param(
                            "resolution",
                            "分辨率档位",
                            "select",
                            default="1080P",
                            description="wan2.7 视频编辑仅支持 720P / 1080P。",
                            help=_help(
                                summary="控制视频编辑输出清晰度。",
                                limits=["仅支持 720P 和 1080P"],
                                how_to_choose=["快速试验时先用 720P", "准备交付或看细节时用 1080P"],
                            ),
                            group="generation",
                            order=1,
                            options=resolution_options,
                        ),
                        _param(
                            "ratio",
                            "画面比例",
                            "select",
                            description="可选；不填时沿用输入视频的近似比例。",
                            help=_help(
                                summary="控制输出画面比例。",
                                limits=["仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4"],
                                how_to_choose=["想保持原视频比例时可留空", "需要明确改成横屏、竖屏或方屏时再手动指定"],
                            ),
                            group="generation",
                            order=2,
                            options=ratio_options,
                        ),
                        _param(
                            "duration",
                            "时长",
                            "integer",
                            default=0,
                            min_value=0,
                            max_value=10,
                            description="支持 0 或 2 到 10 秒；0 表示保持输入视频完整时长。",
                            help=_help(
                                summary="控制视频编辑输出时长。",
                                limits=["仅支持 0 或 2 到 10 秒整数", "0 表示保持输入视频完整时长"],
                                how_to_choose=["想完整保留原视频长度时填 0", "想缩短或明确时长时再填 2 到 10 秒"],
                            ),
                            group="generation",
                            order=3,
                        ),
                        _param(
                            "audio_setting",
                            "声音设置",
                            "select",
                            default="auto",
                            description="控制视频声音的保留方式。",
                            help=_help(
                                summary="控制输出视频声音策略。",
                                limits=["仅支持 auto / origin"],
                                how_to_choose=["不确定时先用 auto", "希望尽量保留输入视频原声时用 origin"],
                            ),
                            group="generation",
                            order=4,
                            options=audio_setting_options,
                        ),
                        _bool_param(
                            "prompt_extend",
                            "智能改写",
                            True,
                            "开启后由模型先扩写提示词再生成。",
                            5,
                            help=_prompt_extend_help(),
                        ),
                        _bool_param("watermark", "添加水印", False, "是否保留 AI 生成水印。", 6, help=_watermark_help("开启后保留万相侧 AI 生成水印。")),
                        _param(
                            "seed",
                            "随机种子",
                            "integer",
                            description="0 到 2147483647，留空为随机",
                            help=_seed_help(),
                            group="advanced",
                            advanced=True,
                            order=7,
                            min_value=0,
                            max_value=2147483647,
                        ),
                    ],
                    "ui_hints": {
                        "prompt_max_length": 5000,
                        "negative_prompt_max_length": 500,
                        "max_reference_images": 3,
                        "max_reference_videos": 0,
                        "asset_help": {
                            "base_video": _asset_help(
                                "待编辑视频是被修改的原始视频。",
                                limits=["支持 MP4/MOV", "时长需在 2 到 10 秒之间", "宽高需在 240 到 4096 像素之间", "宽高比需在 1:8 到 8:1 之间", "文件大小不超过 100MB"],
                                how_to_choose=["优先使用单镜头、主体清晰的视频", "复杂剪辑视频会降低编辑稳定性"],
                            ),
                            "reference_image": _asset_help(
                                "参考图用于引导编辑后的视频主体外观、风格或局部视觉特征。",
                                limits=["最多 3 张参考图", "支持 JPEG/JPG/PNG/BMP/WEBP", "宽高需在 240 到 8000 像素之间", "宽高比需在 1:8 到 8:1 之间", "不支持透明 PNG", "文件大小不超过 20MB"],
                                how_to_choose=["不传参考图时更适合做风格修改或普通视频编辑", "传参考图时更适合做参考主体或风格编辑"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 用于描述整段视频要被改造成什么效果。",
                            limits=["最大长度约 5000 字符", "负面提示词最大长度约 500 字符"],
                            how_to_choose=["只做风格修改时，重点写风格、材质和镜头氛围", "做参考编辑时，写清参考图中的主体或外观特征要如何作用到视频中"],
                            notes=["不传参考图 = 风格修改/视频编辑；传参考图 = 参考编辑。", "duration=0 表示保持输入视频完整时长。", "ratio 留空时通常沿用输入视频近似比例。"],
                        ),
                    },
                },
            },
        ),
    }
    snapshot_model = deepcopy(models["wan2.7-i2v"])
    snapshot_model["id"] = "wan2.7-i2v-2026-04-25"
    snapshot_model["name"] = "万相 2.7 图生视频 2026-04-25 快照"
    snapshot_model["description"] = "用于临时测试 2026-04-25 快照效果的万相 2.7 图生视频模型；长期主用模型仍为 wan2.7-i2v"
    snapshot_model["doc_url"] = "docs/阿里云模型api文档/万相-图生视频2.7.md"
    snapshot_model["capabilities"] = rate_limit_capabilities("wan2.7-i2v-2026-04-25")
    snapshot_model["ui_hints"] = {
        **snapshot_model.get("ui_hints", {}),
        "temporary_snapshot": True,
        "removal_note": "该快照模型仅用于阶段性效果测试，后续可从能力 schema 中移除。",
    }
    models["wan2.7-i2v-2026-04-25"] = snapshot_model
    return models


def _wan_vace_models() -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}

    for model_id, info in VIDEO_REPAINTING_MODELS.items():
        models[model_id] = _build_model(
            model_id=model_id,
            name=info["name"],
            provider="wan",
            description=info.get("description", ""),
            recommended=True,
            doc_url="https://help.aliyun.com/zh/model-studio/use-video-edit",
            supported_task_kinds=["video_repainting"],
            task_profiles={
                "video_repainting": {
                    "label": "视频重绘",
                    "description": info.get("description", ""),
                    "input_roles": ["source_video", "reference_image"],
                    "parameters": [
                        _param(
                            "control_condition",
                            "控制条件",
                            "select",
                            required=True,
                            default=info.get("default_control_condition"),
                            description="告诉模型从原视频里提取哪类结构信息。机械/通用场景一般更适合 depth；人体动作可尝试 posebody 或 posebodyface。",
                            help=_help(
                                summary="控制模型从源视频里优先保留哪类结构或运动信息。",
                                meaning="它不是风格参数，而是“要从原视频里抽取什么约束”的开关，会直接影响重绘后的视频还能保留多少原动作和构图。",
                                how_to_choose=[
                                    "机械臂、产品、通用物体和空间结构优先选 depth",
                                    "人物全身动作优先试 posebody",
                                    "人物脸部表情和动作都重要时试 posebodyface",
                                    "希望保留线稿或轮廓趋势时再试 scribble",
                                ],
                                examples=["例如：机械臂换造型通常先用 depth；舞蹈动作重绘更适合 posebody。"],
                            ),
                            group="generation",
                            order=1,
                            options=[
                                _select_option("depth", "depth", "保留空间层次和构图，通用场景优先"),
                                _select_option("posebodyface", "posebodyface", "适合包含人物脸部和动作的场景"),
                                _select_option("posebody", "posebody", "适合以人体动作姿态为主的场景"),
                                _select_option("scribble", "scribble", "更强调线稿/轮廓控制"),
                            ],
                        ),
                        _param(
                            "strength",
                            "重绘强度",
                            "float",
                            default=info.get("default_strength", 1.0),
                            description="0 到 1。值越大，越偏向重绘结果；值越小，越保留原视频特征。",
                            help=_help(
                                summary="控制重绘结果对原视频的改动强度。",
                                meaning="值越高，模型越愿意偏离原视频去生成新内容；值越低，越倾向保留原视频动作、构图和细节。",
                                limits=["取值范围为 0 到 1"],
                                how_to_choose=[
                                    "想明显换风格、换主体时提高到 0.7 以上",
                                    "只想轻微改造原视频时先试 0.3 到 0.6",
                                ],
                                examples=["例如：完全换成另一种机械外观可先试 0.8。"],
                            ),
                            group="generation",
                            order=2,
                            min_value=(info.get("strength_range") or [0.0, 1.0])[0],
                            max_value=(info.get("strength_range") or [0.0, 1.0])[1],
                        ),
                        _bool_param("prompt_extend", "智能改写", info.get("supports_prompt_extend", True), "自动优化提示词", 3, help=_prompt_extend_help(recommended_off=True)),
                        _bool_param("watermark", "添加水印", False, "是否添加 AI 生成水印", 4, help=_watermark_help("万相水印文案为“AI生成”。")),
                        _param(
                            "seed",
                            "随机种子",
                            "integer",
                            description="0 到 2147483647，留空为随机",
                            help=_seed_help(),
                            group="advanced",
                            advanced=True,
                            order=5,
                            min_value=0,
                            max_value=2147483647,
                        ),
                    ],
                    "ui_hints": {
                        "asset_help": {
                            "source_video": _asset_help(
                                "源视频用于提供动作、结构和镜头基础，重绘会围绕它重新生成。",
                                limits=["格式必须为 MP4", "帧率至少 16 FPS", "文件大小不超过 50MB", "超过 5 秒时模型实际只使用前 5 秒"],
                                how_to_choose=["优先使用单镜头、动作清晰、主体明确的视频", "尽量避免快切、多镜头混剪和过强压缩"],
                                examples=["例如：5 秒内的机械臂操作视频、人物走路单镜头。"],
                            ),
                            "reference_image": _asset_help(
                                "参考图用于引导重绘后的主体外观或风格方向。",
                                limits=["最多 1 张参考图", "格式需满足模型与平台图片要求"],
                                how_to_choose=["主体参考图尽量单主体、背景干净", "需要风格借鉴时选择风格一致的图"],
                                examples=["例如：目标机械臂的正面参考图、希望靠拢的风格图。"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 说明重绘后的主体、风格、镜头和保留策略。",
                            how_to_choose=["先写‘要重绘成什么’，再写‘哪些动作和场景保持不变’", "与源视频差异较大时尽量关闭智能改写并写具体描述"],
                            examples=["例如：将原机械臂重绘为白色工业机械臂，保留原视频开柜门动作、镜头推进和背景布局。"],
                        ),
                    },
                }
            },
        )

    for model_id, info in VIDEO_EDIT_MODELS.items():
        task_profiles = deepcopy(models.get(model_id, {}).get("task_profiles", {}))
        task_profiles["video_edit_local"] = {
            "label": "局部编辑",
            "description": info.get("description", ""),
            "input_roles": ["source_video", "reference_image", "mask_image"],
            "parameters": [
                _param(
                    "control_condition",
                    "控制条件",
                    "select",
                    default=None,
                    description="可选的视频结构提取方式。机械或物体替换通常优先 depth；人物类局部替换可尝试 posebodyface。",
                    help=_help(
                        summary="可选的原视频结构约束方式。",
                        meaning="局部编辑默认已经会参考源视频与蒙版范围，控制条件用于额外强调空间结构或人物动作特征。",
                        how_to_choose=[
                            "机械臂、产品、通用物体替换优先试 depth",
                            "人物面部和姿态都重要时再试 posebodyface",
                            "不确定时可以先留空做首轮测试",
                        ],
                    ),
                    group="generation",
                    order=1,
                    options=[
                        _select_option("depth", "depth", "保留空间层次和结构，通用场景优先"),
                        _select_option("posebodyface", "posebodyface", "适合包含人物脸部和动作的局部编辑"),
                    ],
                ),
                _param(
                    "mask_type",
                    "蒙版模式",
                    "select",
                    default=info.get("default_mask_type", "tracking"),
                    description="tracking 会自动跟踪首帧蒙版区域，适合运动目标；fixed 固定使用首帧蒙版区域，适合静止目标。",
                    help=_help(
                        summary="控制首帧蒙版在后续帧中是自动跟踪还是固定不动。",
                        meaning="这是局部编辑最关键的稳定性参数之一，会决定模型如何把首帧蒙版传播到整段视频。",
                        how_to_choose=[
                            "运动目标、位移明显的主体优先用 tracking",
                            "静止目标或几乎不动的局部修改优先用 fixed",
                        ],
                        examples=["例如：机械臂开柜门通常选 tracking；墙上贴纸替换更适合 fixed。"],
                    ),
                    group="generation",
                    order=2,
                    options=[
                        _select_option("tracking", "tracking", "自动跟踪蒙版区域，适合运动主体"),
                        _select_option("fixed", "fixed", "固定首帧区域，适合静止主体"),
                    ],
                ),
                _param(
                    "expand_ratio",
                    "扩展比例",
                    "float",
                    default=info.get("default_expand_ratio", 0.05),
                    description="仅在 tracking 模式下生效。目标运动较大或边缘容易被裁掉时可适当增大。",
                    help=_help(
                        summary="控制跟踪区域相对首帧蒙版向外扩张多少。",
                        meaning="tracking 模式下，如果主体后续帧移动、转动或边缘容易被切掉，可以通过扩展比例给跟踪留更大余量。",
                        limits=["仅在 tracking 模式下生效", "取值范围为 0 到 1"],
                        how_to_choose=[
                            "先从默认值 0.05 开始",
                            "主体运动大、边缘被裁掉时增加到 0.08 到 0.15",
                            "背景被带入太多时适当减小",
                        ],
                    ),
                    group="generation",
                    order=3,
                    min_value=(info.get("expand_ratio_range") or [0.0, 1.0])[0],
                    max_value=(info.get("expand_ratio_range") or [0.0, 1.0])[1],
                    depends_on="mask_type",
                    depends_value="tracking",
                ),
                _param(
                    "expand_mode",
                    "包裹模式",
                    "select",
                    default=info.get("default_expand_mode", "hull"),
                    description="仅在 tracking 模式下生效。hull 更贴合主体轮廓，bbox 是外接矩形，original 尽量保持原始蒙版形状。",
                    help=_help(
                        summary="控制 tracking 模式下后续帧如何包裹被跟踪目标。",
                        meaning="不同包裹模式会影响蒙版覆盖范围，进而影响编辑区域是否过紧或带入过多背景。",
                        limits=["仅在 tracking 模式下生效"],
                        how_to_choose=[
                            "机械臂、人物肢体等不规则目标优先用 hull",
                            "担心跟踪过紧漏掉主体时试 bbox",
                            "想尽量贴近原始蒙版形状时试 original",
                        ],
                        examples=["例如：机械臂换装通常优先 hull。"],
                    ),
                    group="generation",
                    order=4,
                    options=[
                        _select_option("hull", "hull", "更贴合主体轮廓，机械臂等不规则目标优先"),
                        _select_option("bbox", "bbox", "使用外接矩形，覆盖更宽但容易带入背景"),
                        _select_option("original", "original", "尽量保持原始蒙版形状"),
                    ],
                    depends_on="mask_type",
                    depends_value="tracking",
                ),
                _param(
                    "size",
                    "输出尺寸",
                    "select",
                    default=info.get("default_size"),
                    description="VACE 仅支持固定输出尺寸集合。",
                    help=_help(
                        summary="控制局部编辑结果的视频尺寸。",
                        limits=["仅支持模型公开的固定尺寸集合"],
                        how_to_choose=["优先选择与源视频方向一致的尺寸", "如果只是验证替换效果，先选成本较低的相近尺寸"],
                    ),
                    group="generation",
                    order=5,
                    options=[_select_option(item["value"], item["label"]) for item in info.get("sizes", [])],
                ),
                _bool_param("prompt_extend", "智能改写", info.get("supports_prompt_extend", True), "自动优化提示词", 6, help=_prompt_extend_help(recommended_off=True)),
                _bool_param("watermark", "添加水印", False, "是否添加 AI 生成水印", 7, help=_watermark_help("万相水印文案为“AI生成”。")),
                _param(
                    "seed",
                    "随机种子",
                    "integer",
                    description="0 到 2147483647，留空为随机",
                    help=_seed_help(),
                    group="advanced",
                    advanced=True,
                    order=8,
                    min_value=0,
                    max_value=2147483647,
                ),
            ],
            "ui_hints": {
                "asset_help": {
                    "source_video": _asset_help(
                        "源视频用于提供局部编辑前的原始动作、镜头和空间结构。",
                        limits=["格式必须为 MP4", "帧率至少 16 FPS", "文件大小不超过 50MB", "超过 5 秒时模型只会取前 5 秒"],
                        how_to_choose=["尽量使用单镜头、主体清晰的视频", "局部替换任务里源视频越稳定，编辑越容易保持原动作"],
                    ),
                    "reference_image": _asset_help(
                        "参考图用于引导被替换区域应生成成什么主体或风格。",
                        limits=["最多 1 张参考图"],
                        how_to_choose=["需要换具体物体时优先选单主体、背景干净的参考图", "参考图更像是引导生成，不是像素级贴图"],
                        examples=["例如：另一种机械臂的正面图。"],
                        notes=["当前官方 video_edit 文档没有把 obj_or_bg 列为公开参数，因此平台本轮不暴露该开关。"],
                    ),
                    "mask_image": _asset_help(
                        "Mask 白色区域会被编辑，黑色区域保持不变。",
                        limits=["Mask 分辨率必须与源视频首帧完全一致", "建议导出纯黑白二值图"],
                        how_to_choose=["替换主体时尽量覆盖完整主体轮廓", "与背景接触的边缘可适当多包一点，避免切边"],
                        examples=["例如：替换机械臂时应覆盖机械臂主体和关键接触部位。"],
                    ),
                },
                "prompt_help": _help(
                    summary="Prompt 描述被蒙版区域要改成什么，同时强调哪些内容需要保持不变。",
                    how_to_choose=[
                        "先写要替换成什么主体，再写保留哪些动作、镜头和背景",
                        "不要只写“换成参考图”，而要描述造型、材质或结构特征",
                    ],
                    examples=["例如：将白色蒙版区域中的原机械臂替换为参考图中的白色工业机械臂，保留原视频开柜门动作、背景和镜头推进。"],
                ),
            },
        }
        models[model_id] = _build_model(
            model_id=model_id,
            name=info["name"],
            provider="wan",
            description=info.get("description", ""),
            recommended=True,
            doc_url="https://help.aliyun.com/zh/model-studio/use-video-edit",
            supported_task_kinds=list({*models.get(model_id, {}).get("supported_task_kinds", []), "video_edit_local", "video_repainting"}),
            task_profiles=task_profiles,
        )
    return models


def _kling_models() -> Dict[str, Dict[str, Any]]:
    mode_options = [
        _select_option("pro", "专业模式 (1080P)", "画质更高，成本更高"),
        _select_option("std", "标准模式 (720P)", "速度更快，适合多数预览和批量生成"),
    ]
    ratio_options = [
        _select_option("16:9", "16:9 横屏", "适合桌面播放、横屏镜头"),
        _select_option("9:16", "9:16 竖屏", "适合短视频和手机观看"),
        _select_option("1:1", "1:1 方形", "适合社媒封面或方形内容"),
    ]
    narration_options = [
        _select_option("single", "单镜头", "一个整体镜头连续生成"),
        _select_option("multi_shot_intelligence", "多镜头 - 智能分镜", "由模型自动规划镜头切换"),
        _select_option("multi_shot_customize", "多镜头 - 自定义分镜", "手工填写每段分镜提示词和时长"),
    ]

    common_video_params = [
        _param(
            "mode",
            "画质模式",
            "select",
            default="pro",
            description="pro 为 1080P，std 为 720P。",
            help=_help(
                summary="控制可灵输出画质档位。",
                meaning="pro 更偏最终交付，std 更适合预览和批量试验。",
                how_to_choose=["需要更高画质时选 pro", "追求速度和成本平衡时先用 std"],
            ),
            group="generation",
            order=1,
            options=mode_options,
        ),
        _param(
            "duration",
            "时长",
            "integer",
            default=5,
            min_value=3,
            max_value=15,
            description="无视频输入时支持 3 到 15 秒；带参考视频或待编辑视频时上限会收窄到 10 秒。",
            help=_duration_help(
                "控制可灵输出视频时长。",
                limits=["普通文生/图生最长 15 秒", "带参考视频或 base video 时最长 10 秒"],
                notes=["如果输入视频超出范围，平台会在提交前拦截。"],
            ),
            group="generation",
            order=2,
        ),
        _bool_param("audio", "生成音频", True, "开启后模型会自动生成背景音乐或音效。", 4, help=_audio_help("控制是否让可灵为视频自动补声音。")),
        _bool_param("watermark", "添加水印", False, "是否保留“可灵AI”水印。", 5, help=_watermark_help("开启后保留可灵侧的 AI 生成水印。")),
    ]
    element_ids_param = _tags_param(
        "element_ids",
        "主体ID",
        description="可输入一个或多个主体ID，按回车确认。首帧/首尾帧最多 3 个；参考生视频和视频编辑需要与参考图数量合并计算上限。",
        help=_help(
            summary="主体 ID 用于引用可灵侧已识别或已绑定的主体元素。",
            meaning="它主要用于更强地约束角色、物体或元素的一致性，通常属于高级用法。",
            how_to_choose=[
                "没有主体 ID 时可以留空，只用普通 prompt 和参考素材",
                "已有稳定主体资产且希望跨镜头保持一致时再填写",
            ],
            examples=["例如：输入 101、205，并在 prompt 中使用 <<<element_1>>>。"],
            notes=["不同任务的主体 ID 数量上限不同，会与参考图数量一起计算。"],
        ),
        order=10,
    )

    return {
        "kling/kling-v3-video-generation": _build_model(
            model_id="kling/kling-v3-video-generation",
            name="可灵 V3 视频生成",
            provider="kling",
            description="可灵基础视频模型，支持文生、图生、首尾帧和多镜头文生视频",
            recommended=False,
            doc_url="https://help.aliyun.com/zh/model-studio/use-video-generation",
            supported_task_kinds=["text_to_video", "image_to_video", "keyframe_to_video"],
            task_profiles={
                "text_to_video": {
                    "label": "文生视频",
                    "description": "支持普通文生与多镜头文生视频",
                    "input_roles": [],
                    "supported_narrative_modes": ["single", "multi_shot_intelligence", "multi_shot_customize"],
                    "parameters": [
                        common_video_params[0],
                        _param(
                            "aspect_ratio",
                            "画面比例",
                            "select",
                            default="16:9",
                            required=True,
                            description="文生视频必须指定画面比例。",
                            help=_help(
                                summary="控制文生视频的画面比例。",
                                limits=["文生视频必须指定画面比例"],
                                how_to_choose=["桌面播放或横屏内容用 16:9", "短视频平台优先 9:16", "封面感或通用裁切可选 1:1"],
                            ),
                            group="generation",
                            order=2,
                            options=ratio_options,
                        ),
                        common_video_params[1],
                        _param(
                            "narrative_mode",
                            "叙事模式",
                            "select",
                            default="single",
                            description="单镜头适合普通生成；多镜头可做智能分镜或手工分镜。",
                            help=_help(
                                summary="控制生成单镜头还是多镜头分镜视频。",
                                how_to_choose=[
                                    "普通动作展示先用单镜头",
                                    "希望模型自动拆镜头时选多镜头 - 智能分镜",
                                    "你已经明确每段镜头内容时选多镜头 - 自定义分镜",
                                ],
                            ),
                            group="generation",
                            order=3,
                            options=narration_options,
                        ),
                        common_video_params[2],
                        common_video_params[3],
                    ],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "supports_multi_shot": True,
                        "multi_prompt_max_count": 6,
                        "prompt_help": _help(
                            summary="Prompt 描述视频主体、动作、场景、镜头和风格。",
                            limits=["最大长度约 2500 字符"],
                            how_to_choose=["先写主体和动作，再补镜头语言和风格", "自定义多镜头时，总提示词负责总方向，分镜内容写在分镜段落里"],
                            examples=["例如：白色工业机械臂在仓库中平稳打开柜门，镜头缓慢推进，工业冷色调。"],
                        ),
                    },
                },
                "image_to_video": {
                    "label": "首帧生视频",
                    "description": "基于首帧生成视频",
                    "input_roles": ["first_frame"],
                    "parameters": [*common_video_params, element_ids_param],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图定义视频的初始构图、主体位置和基础风格。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道"],
                                how_to_choose=["主体尽量完整、清晰", "避免裁切到关键肢体或主体边缘"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 重点描述首帧之后的视频动作、镜头变化和氛围。",
                            how_to_choose=["首帧已经给出静态内容时，prompt 更应强调‘怎么动’", "不要重复过多首帧里已经很明显的内容"],
                        ),
                    },
                },
                "keyframe_to_video": {
                    "label": "首尾帧生视频",
                    "description": "基于首帧和尾帧生成视频",
                    "input_roles": ["first_frame", "last_frame"],
                    "parameters": [*common_video_params, element_ids_param],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图定义视频的起始状态。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道"],
                            ),
                            "last_frame": _asset_help(
                                "尾帧图定义视频的结束状态。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道"],
                                how_to_choose=["首尾帧最好主体一致、变化明确", "适合姿态变化、镜头移动、开合动作等任务"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 描述首帧到尾帧之间的变化过程。",
                            how_to_choose=["重点写过渡方式、镜头节奏和中间动作", "避免只重复首尾帧静态内容"],
                        ),
                    },
                },
            },
            ui_hints={"supports_prompt_tokens": False},
        ),
        "kling/kling-v3-omni-video-generation": _build_model(
            model_id="kling/kling-v3-omni-video-generation",
            name="可灵 V3 Omni 视频生成",
            provider="kling",
            description="可灵全能视频模型，支持文生、图生、首尾帧、参考生视频和视频编辑",
            recommended=True,
            doc_url="https://help.aliyun.com/zh/model-studio/use-video-generation",
            supported_task_kinds=["text_to_video", "image_to_video", "keyframe_to_video", "reference_to_video", "video_edit_global"],
            task_profiles={
                "text_to_video": {
                    "label": "文生视频",
                    "description": "支持普通文生与多镜头文生视频",
                    "input_roles": [],
                    "supported_narrative_modes": ["single", "multi_shot_intelligence", "multi_shot_customize"],
                    "parameters": [
                        common_video_params[0],
                        _param(
                            "aspect_ratio",
                            "画面比例",
                            "select",
                            default="16:9",
                            required=True,
                            description="文生视频必须指定画面比例。",
                            help=_help(
                                summary="控制文生视频的画面比例。",
                                limits=["文生视频必须指定画面比例"],
                                how_to_choose=["桌面播放或横屏内容用 16:9", "短视频平台优先 9:16", "封面感或通用裁切可选 1:1"],
                            ),
                            group="generation",
                            order=2,
                            options=ratio_options,
                        ),
                        common_video_params[1],
                        _param(
                            "narrative_mode",
                            "叙事模式",
                            "select",
                            default="single",
                            description="单镜头适合普通生成；多镜头可做智能分镜或手工分镜。",
                            help=_help(
                                summary="控制生成单镜头还是多镜头分镜视频。",
                                how_to_choose=[
                                    "普通动作展示先用单镜头",
                                    "希望模型自动拆镜头时选多镜头 - 智能分镜",
                                    "你已经明确每段镜头内容时选多镜头 - 自定义分镜",
                                ],
                            ),
                            group="generation",
                            order=3,
                            options=narration_options,
                        ),
                        common_video_params[2],
                        common_video_params[3],
                    ],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "supports_multi_shot": True,
                        "multi_prompt_max_count": 6,
                        "prompt_help": _help(
                            summary="Prompt 描述视频主体、动作、场景、镜头和风格。",
                            limits=["最大长度约 2500 字符"],
                            how_to_choose=["先写主体和动作，再补镜头语言和风格", "自定义多镜头时，总提示词负责总方向，分镜内容写在分镜段落里"],
                        ),
                    },
                },
                "image_to_video": {
                    "label": "首帧生视频",
                    "description": "基于首帧生成视频",
                    "input_roles": ["first_frame"],
                    "parameters": [*common_video_params, element_ids_param],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图定义视频的初始构图、主体位置和基础风格。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道"],
                                how_to_choose=["主体尽量完整、清晰", "避免裁切到关键肢体或主体边缘"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 重点描述首帧之后的视频动作、镜头变化和氛围。",
                            how_to_choose=["首帧已经给出静态内容时，prompt 更应强调‘怎么动’", "不要重复过多首帧里已经很明显的内容"],
                        ),
                    },
                },
                "keyframe_to_video": {
                    "label": "首尾帧生视频",
                    "description": "基于首帧和尾帧生成视频",
                    "input_roles": ["first_frame", "last_frame"],
                    "parameters": [*common_video_params, element_ids_param],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "asset_help": {
                            "first_frame": _asset_help(
                                "首帧图定义视频的起始状态。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道"],
                            ),
                            "last_frame": _asset_help(
                                "尾帧图定义视频的结束状态。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道"],
                                how_to_choose=["首尾帧最好主体一致、变化明确", "适合姿态变化、镜头移动、开合动作等任务"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 描述首帧到尾帧之间的变化过程。",
                            how_to_choose=["重点写过渡方式、镜头节奏和中间动作", "避免只重复首尾帧静态内容"],
                        ),
                    },
                },
                "reference_to_video": {
                    "label": "参考生视频",
                    "description": "支持参考图、参考视频和主体引用的组合生成",
                    "input_roles": ["reference_image", "reference_video", "first_frame"],
                    "parameters": [
                        common_video_params[0],
                        _param(
                            "aspect_ratio",
                            "画面比例",
                            "select",
                            default="16:9",
                            description="仅参考图、仅参考视频、参考图+参考视频模式下都建议明确指定；若使用 feature + first_frame，可由首帧比例决定。",
                            help=_help(
                                summary="控制参考生视频的目标画面比例。",
                                meaning="部分素材组合下可以由首帧图决定构图比例，但显式指定通常更稳定。",
                                how_to_choose=["只有参考图或参考视频时建议手动指定", "使用 feature + first_frame 时可让首帧图主导比例"],
                            ),
                            group="generation",
                            order=2,
                            options=ratio_options,
                        ),
                        _param(
                            "duration",
                            "时长",
                            "integer",
                            default=5,
                            min_value=3,
                            max_value=10,
                            description="参考生视频带视频输入时最长 10 秒。",
                            help=_duration_help(
                                "控制参考生视频输出时长。",
                                limits=["有视频输入时最长 10 秒"],
                            ),
                            group="generation",
                            order=3,
                        ),
                        common_video_params[2],
                        _bool_param(
                            "keep_original_sound",
                            "保留原声",
                            False,
                            "仅在传入参考视频时生效。",
                            5,
                            help=_help(
                                summary="控制输出视频是否保留参考视频的原始声音。",
                                how_to_choose=["只想参考动作和镜头、不需要原声音轨时关闭", "希望原视频声音继续保留时开启"],
                            ),
                        ),
                        common_video_params[3],
                        element_ids_param,
                    ],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "supports_prompt_tokens": True,
                        "max_reference_images": 7,
                        "max_reference_videos": 1,
                        "asset_help": {
                            "reference_image": _asset_help(
                                "参考图用于引导主体造型、服饰、物体外观或风格。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道", "仅参考图模式下：参考图数量与主体 ID 数量之和最多 7"],
                                how_to_choose=["主体参考图尽量单主体、背景干净", "多个参考图时要注意主次关系"],
                            ),
                            "reference_video": _asset_help(
                                "参考视频用于提供动作、镜头节奏或整体动态趋势。",
                                limits=["格式支持 MP4/MOV", "时长需在 3 到 10 秒之间", "帧率需在 24 到 60 FPS 之间", "宽高需在 720 到 2160 像素之间"],
                                how_to_choose=["优先选择单镜头、动作明确的片段", "复杂混剪视频更不稳定"],
                            ),
                            "first_frame": _asset_help(
                                "仅在 feature + first_frame 模式下使用，由首帧图决定输出构图比例。",
                                how_to_choose=["当你既想借参考视频动作，又想用特定首帧构图时使用"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="可在提示词中用占位符引用素材与主体。",
                            how_to_choose=["引用参考图时用 <<<image_1>>>", "引用参考视频时用 <<<video_1>>>", "引用主体 ID 时用 <<<element_1>>>"],
                            examples=["例如：让 <<<video_1>>> 的镜头运动配合 <<<image_1>>> 中机械臂的外观。"],
                            notes=["编号按媒体添加顺序计算。"],
                        ),
                    },
                },
                "video_edit_global": {
                    "label": "视频编辑",
                    "description": "对整段视频进行编辑，可选单张参考图",
                    "input_roles": ["base_video", "reference_image"],
                    "parameters": [
                        common_video_params[0],
                        _param(
                            "duration",
                            "时长",
                            "integer",
                            default=5,
                            min_value=3,
                            max_value=10,
                            description="视频编辑带 base 输入时最长 10 秒。",
                            help=_duration_help(
                                "控制视频编辑输出时长。",
                                limits=["带 base video 输入时最长 10 秒"],
                            ),
                            group="generation",
                            order=2,
                        ),
                        common_video_params[2],
                        _bool_param(
                            "keep_original_sound",
                            "保留原声",
                            False,
                            "保留输入视频声音。",
                            4,
                            help=_help(
                                summary="控制输出视频是否保留待编辑视频的原始声音。",
                                how_to_choose=["只做画面编辑又想保留现场声时开启", "只关心画面或后续要重新配音时关闭"],
                            ),
                        ),
                        common_video_params[3],
                        element_ids_param,
                    ],
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "max_reference_images": 4,
                        "asset_help": {
                            "base_video": _asset_help(
                                "base video 是被编辑的原视频。",
                                limits=["格式支持 MP4/MOV", "时长需在 3 到 10 秒之间", "帧率需在 24 到 60 FPS 之间", "宽高需在 720 到 2160 像素之间"],
                                how_to_choose=["优先使用单镜头、主体清晰的视频", "复杂剪辑会显著降低编辑稳定性"],
                            ),
                            "reference_image": _asset_help(
                                "参考图用于引导编辑后的视频主体外观或风格。",
                                limits=["格式支持 JPG/JPEG/PNG", "宽高需在 300 到 8000 像素之间", "不支持透明通道", "参考图数量与主体 ID 数量之和最多 4"],
                                how_to_choose=["参考图更适合作为风格或主体引导，不是像素级贴图", "主体参考图尽量单主体、背景干净"],
                            ),
                        },
                        "prompt_help": _help(
                            summary="Prompt 用于描述整段视频要被改造成什么效果。",
                            how_to_choose=["先说明要替换或增强的方向，再说明哪些内容保持不变", "使用主体 ID 时可在 prompt 中引用 <<<element_1>>>"],
                        ),
                    },
                },
            },
            ui_hints={"supports_prompt_tokens": True},
        ),
    }


def _vidu_size_options() -> Dict[str, List[Dict[str, str]]]:
    return {
        "540P": [
            {"value": "960*528", "label": "960×528 横向 16:9"},
            {"value": "528*960", "label": "528×960 竖向 9:16"},
            {"value": "720*720", "label": "720×720 方形 1:1"},
            {"value": "816*608", "label": "816×608 横向 4:3"},
            {"value": "608*816", "label": "608×816 竖向 3:4"},
        ],
        "720P": [
            {"value": "1280*720", "label": "1280×720 横向 16:9"},
            {"value": "720*1280", "label": "720×1280 竖向 9:16"},
            {"value": "960*960", "label": "960×960 方形 1:1"},
            {"value": "1104*816", "label": "1104×816 横向 4:3"},
            {"value": "816*1104", "label": "816×1104 竖向 3:4"},
        ],
        "1080P": [
            {"value": "1920*1080", "label": "1920×1080 横向 16:9"},
            {"value": "1080*1920", "label": "1080×1920 竖向 9:16"},
            {"value": "1440*1440", "label": "1440×1440 方形 1:1"},
            {"value": "1674*1238", "label": "1674×1238 横向 4:3"},
            {"value": "1238*1674", "label": "1238×1674 竖向 3:4"},
        ],
    }


def _vidu_reference_size_options() -> Dict[str, List[Dict[str, str]]]:
    return {
        "540P": [
            {"value": "960*540", "label": "960×540 横向 16:9"},
            {"value": "720*540", "label": "720×540 横向 4:3"},
            {"value": "540*540", "label": "540×540 方形 1:1"},
            {"value": "540*720", "label": "540×720 竖向 3:4"},
            {"value": "540*960", "label": "540×960 竖向 9:16"},
        ],
        "720P": [
            {"value": "1280*720", "label": "1280×720 横向 16:9"},
            {"value": "960*720", "label": "960×720 横向 4:3"},
            {"value": "720*720", "label": "720×720 方形 1:1"},
            {"value": "720*960", "label": "720×960 竖向 3:4"},
            {"value": "720*1280", "label": "720×1280 竖向 9:16"},
        ],
        "1080P": [
            {"value": "1920*1080", "label": "1920×1080 横向 16:9"},
            {"value": "1440*1080", "label": "1440×1080 横向 4:3"},
            {"value": "1080*1080", "label": "1080×1080 方形 1:1"},
            {"value": "1080*1440", "label": "1080×1440 竖向 3:4"},
            {"value": "1080*1920", "label": "1080×1920 竖向 9:16"},
        ],
    }


def _vidu_model(
    *,
    model_id: str,
    name: str,
    description: str,
    task_kind: str,
    input_roles: List[str],
    duration_range: List[int],
    supports_audio: bool,
    size_options_by_resolution: Dict[str, List[Dict[str, str]]] | None = None,
    resolution_values: List[str] | None = None,
    recommended: bool = False,
    ui_hints: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    effective_resolution_values = resolution_values or ["540P", "720P", "1080P"]
    parameters: List[Dict[str, Any]] = [
        _param(
            "resolution",
            "分辨率档位",
            "select",
            default="720P",
            description="建议与输出尺寸一起设置；若只传分辨率，平台会按该档位默认 16:9 输出。",
            help=_help(
                summary="控制 Vidu 输出的清晰度档位。",
                meaning="resolution 与 size 建议成对设置，二者不匹配时平台会拦截或由模型回退默认值。",
                how_to_choose=["先选分辨率档位，再选该档位支持的尺寸", "预览时可先用较低档位降低成本"],
            ),
            group="generation",
            order=1,
            options=[_select_option(value, value) for value in effective_resolution_values],
        ),
        _param(
            "duration",
            "时长",
            "integer",
            default=5,
            min_value=duration_range[0],
            max_value=duration_range[1],
            description="按秒计费。不同型号的时长范围不同，参考生视频的 Pro 型号额外支持 0 表示自动规划时长。",
            help=_duration_help(
                "控制 Vidu 输出时长。",
                limits=[f"当前模型支持 {duration_range[0]} 到 {duration_range[1]} 秒"] + (["参考生视频的 Pro 型号支持 0，表示自动规划时长"] if duration_range[0] == 0 else []),
            ),
            group="generation",
            order=2,
        ),
        _bool_param("watermark", "添加水印", False, "是否添加“内容由AI生成”水印。", 4, help=_watermark_help("开启后保留 Vidu 的 AI 生成水印。")),
    ]
    if size_options_by_resolution:
        parameters.insert(
            1,
            _param(
                "size",
                "输出尺寸",
                "select",
                default=size_options_by_resolution["720P"][0]["value"],
                description="推荐与分辨率档位同时设置；若只传 size，Vidu 会忽略该值并回退到默认 720P 16:9。",
                help=_help(
                    summary="控制 Vidu 输出的具体宽高尺寸。",
                    meaning="size 与 resolution 存在严格联动，不同分辨率档位支持的尺寸集合不同。",
                    how_to_choose=["先决定横屏、竖屏、方屏", "再在当前分辨率档位下选择合法尺寸"],
                    notes=["只改 size 不改 resolution 时，模型可能回退到默认尺寸。"],
                ),
                group="generation",
                order=2,
                options=[
                    _select_option(option["value"], f"{option['label']} ({resolution})")
                    for resolution, options in size_options_by_resolution.items()
                    for option in options
                ],
            ),
        )
    if supports_audio:
        parameters.insert(3, _bool_param("audio", "生成音频", True, "开启后模型会自动生成背景音乐或音效。", 3, help=_audio_help("控制是否让 Vidu 自动生成声音。")))
    parameters.append(
        _param(
            "seed",
            "随机种子",
            "integer",
            description="0 到 2147483647，留空为随机",
            help=_seed_help(),
            group="advanced",
            advanced=True,
            order=6,
            min_value=0,
            max_value=2147483647,
        )
    )

    return _build_model(
        model_id=model_id,
        name=name,
        provider="vidu",
        description=description,
        recommended=recommended,
        doc_url="https://help.aliyun.com/zh/model-studio/use-video-generation",
        supported_task_kinds=[task_kind],
        task_profiles={
            task_kind: {
                "label": next(item["label"] for item in TASK_KIND_DEFS if item["id"] == task_kind),
                "description": description,
                "input_roles": input_roles,
                "parameters": parameters,
                "ui_hints": {
                    "size_options_by_resolution": size_options_by_resolution or {},
                    "prompt_help": _help(
                        summary="Prompt 用于描述视频主体、动作、场景、镜头和风格。",
                        limits=["Vidu 对 prompt 的细节描述比较敏感，建议写清主体和动作"],
                        how_to_choose=["先写主体和动作，再补镜头和风格", "参考生视频时要写清参考素材如何被使用"],
                    ),
                    **(ui_hints or {}),
                },
            }
        },
    )


def _happyhorse_models() -> Dict[str, Dict[str, Any]]:
    resolution_options = [
        _select_option("1080P", "1080P", "画面更细腻，适合最终交付"),
        _select_option("720P", "720P", "更适合快速试验与低成本 smoke"),
    ]
    ratio_options = [
        _select_option("16:9", "16:9 横屏", "适合桌面视频与横屏叙事"),
        _select_option("9:16", "9:16 竖屏", "适合短视频与手机观看"),
        _select_option("1:1", "1:1 方形", "适合封面与社媒方形内容"),
        _select_option("4:3", "4:3 横版", "适合传统构图与演示内容"),
        _select_option("3:4", "3:4 竖版", "适合人像与竖版展示"),
    ]
    audio_setting_options = [
        _select_option("auto", "自动", "由模型自动决定声音策略"),
        _select_option("origin", "保留原声", "尽量保留输入视频原始声音"),
    ]
    watermark_help = _watermark_help("HappyHorse 文档默认 watermark=true；平台会显式下发 false，避免回落到厂商默认值。")
    common_notes = ["该模型需要提前加白。首次加白通过后，还需至少登录一次百炼控制台激活后再调用。"]

    t2v_params = [
        _param(
            "resolution",
            "分辨率档位",
            "select",
            default="1080P",
            description="HappyHorse 文生视频仅支持 720P / 1080P。",
            help=_help(summary="控制输出视频清晰度。", limits=["仅支持 720P 和 1080P"], how_to_choose=["快速 smoke 时先用 720P", "需要看细节或准备交付时用 1080P"], notes=common_notes),
            group="generation",
            order=1,
            options=resolution_options,
        ),
        _param(
            "ratio",
            "画面比例",
            "select",
            default="16:9",
            description="控制输出画面的宽高比。",
            help=_help(summary="控制输出画面的横竖构图。", limits=["仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4"], how_to_choose=["横屏内容优先 16:9", "短视频或手机观看优先 9:16", "封面或社媒卡面可选 1:1"]),
            group="generation",
            order=2,
            options=ratio_options,
        ),
        _param("duration", "时长", "integer", default=5, min_value=3, max_value=15, description="输出时长，支持 3 到 15 秒。", help=_duration_help("控制 HappyHorse 文生视频输出时长。", limits=["支持 3 到 15 秒整数时长"]), group="generation", order=3),
        _bool_param("watermark", "添加水印", False, "是否保留厂商默认 AI 水印。", 4, help=watermark_help),
        _param("seed", "随机种子", "integer", description="0 到 2147483647，留空为随机。", help=_seed_help(), group="advanced", advanced=True, order=5, min_value=0, max_value=2147483647),
    ]

    i2v_params = [
        _param(
            "resolution",
            "分辨率档位",
            "select",
            default="1080P",
            description="HappyHorse 图生视频仅支持 720P / 1080P。",
            help=_help(summary="控制输出视频清晰度。", limits=["仅支持 720P 和 1080P"], how_to_choose=["快速 smoke 时先用 720P", "需要看细节或准备交付时用 1080P"], notes=common_notes),
            group="generation",
            order=1,
            options=resolution_options,
        ),
        _param("duration", "时长", "integer", default=5, min_value=3, max_value=15, description="输出时长，支持 3 到 15 秒。", help=_duration_help("控制 HappyHorse 图生视频输出时长。", limits=["支持 3 到 15 秒整数时长"]), group="generation", order=2),
        _bool_param("watermark", "添加水印", False, "是否保留厂商默认 AI 水印。", 3, help=watermark_help),
        _param("seed", "随机种子", "integer", description="0 到 2147483647，留空为随机。", help=_seed_help(), group="advanced", advanced=True, order=4, min_value=0, max_value=2147483647),
    ]

    r2v_params = [
        _param("resolution", "分辨率档位", "select", default="1080P", description="HappyHorse 参考生视频仅支持 720P / 1080P。", help=_help(summary="控制参考生视频输出清晰度。", limits=["仅支持 720P 和 1080P"], how_to_choose=["快速验证角色引用时先用 720P", "需要看参考图融合细节时用 1080P"], notes=common_notes), group="generation", order=1, options=resolution_options),
        _param("ratio", "画面比例", "select", default="16:9", description="控制输出视频的宽高比。", help=_help(summary="控制参考生视频横竖构图。", limits=["仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4"], how_to_choose=["横屏叙事优先 16:9", "短视频优先 9:16", "角色展示可选 3:4"]), group="generation", order=2, options=ratio_options),
        _param("duration", "时长", "integer", default=5, min_value=3, max_value=15, description="输出时长，支持 3 到 15 秒。", help=_duration_help("控制 HappyHorse 参考生视频输出时长。", limits=["支持 3 到 15 秒整数时长"]), group="generation", order=3),
        _bool_param("watermark", "添加水印", False, "是否保留厂商默认 AI 水印。", 4, help=watermark_help),
        _param("seed", "随机种子", "integer", description="0 到 2147483647，留空为随机。", help=_seed_help(), group="advanced", advanced=True, order=5, min_value=0, max_value=2147483647),
    ]

    video_edit_params = [
        _param("resolution", "分辨率档位", "select", default="1080P", description="HappyHorse 视频编辑仅支持 720P / 1080P。", help=_help(summary="控制视频编辑输出清晰度。", limits=["仅支持 720P 和 1080P"], how_to_choose=["快速验证编辑意图时先用 720P", "需要看服饰、材质等细节时用 1080P"], notes=common_notes), group="generation", order=1, options=resolution_options),
        _bool_param("watermark", "添加水印", False, "是否保留厂商默认 AI 水印。", 2, help=watermark_help),
        _param("audio_setting", "声音设置", "select", default="auto", description="控制输出视频声音策略。", help=_help(summary="控制 HappyHorse 视频编辑的声音处理。", limits=["仅支持 auto / origin"], how_to_choose=["不确定时用 auto", "希望尽量保留输入视频原声时用 origin"]), group="generation", order=3, options=audio_setting_options),
        _param("seed", "随机种子", "integer", description="0 到 2147483647，留空为随机。", help=_seed_help(), group="advanced", advanced=True, order=4, min_value=0, max_value=2147483647),
    ]

    return {
        "happyhorse-1.0-t2v": _build_model(
            model_id="happyhorse-1.0-t2v",
            name="HappyHorse 1.0 文生视频",
            provider="happyhorse",
            description="HappyHorse 文生视频模型，支持分辨率档位、画面比例、时长、种子和水印控制。",
            recommended=False,
            doc_url="docs/阿里云模型api文档/HappyHorse-文生视频API参考.md",
            supported_task_kinds=["text_to_video"],
            task_profiles={
                "text_to_video": {
                    "label": "文生视频",
                    "description": "仅用文本提示词生成视频，不支持负面提示词、智能改写、自定义音频或 shot_type。",
                    "input_roles": [],
                    "parameters": t2v_params,
                    "verification_profiles": {"smoke": ["basic_prompt"], "full": ["basic_prompt", "portrait_ratio", "seeded_generation"]},
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "prompt_help": _help(summary="Prompt 用于描述主体、动作、场景、镜头和风格。", limits=["最大长度约 2500 字符", "不能为空或纯空格"], how_to_choose=["先写主体和动作，再补镜头、氛围和风格", "需要更强可控性时直接写清运镜、速度和场景变化"], notes=common_notes),
                    },
                }
            },
        ),
        "happyhorse-1.0-i2v": _build_model(
            model_id="happyhorse-1.0-i2v",
            name="HappyHorse 1.0 图生视频",
            provider="happyhorse",
            description="HappyHorse 图生视频模型，使用单张首帧图生成视频，可选补充 prompt。",
            recommended=False,
            doc_url="docs/阿里云模型api文档/HappyHorse-图生视频-基于首帧API参考.md",
            supported_task_kinds=["image_to_video"],
            task_profiles={
                "image_to_video": {
                    "label": "图生视频",
                    "description": "使用 1 张首帧图生成视频，不支持首尾帧、视频续写、驱动音频或 ratio。",
                    "input_roles": ["first_frame"],
                    "parameters": i2v_params,
                    "verification_profiles": {"smoke": ["single_first_frame"], "full": ["single_first_frame", "optional_prompt", "seeded_generation"]},
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "asset_help": {
                            "first_frame": _asset_help("首帧图决定视频初始构图、主体位置和基础风格。", limits=["必须且仅支持 1 张首帧图", "支持 JPEG/JPG/PNG/WEBP", "宽高不能小于 300 像素", "宽高比需在 1:2.5 到 2.5:1 之间", "文件大小不超过 10MB"], how_to_choose=["主体尽量完整清晰", "避免裁切到关键主体边缘", "图像比例尽量接近目标出图比例"], notes=common_notes),
                        },
                        "prompt_help": _help(summary="Prompt 为可选项，用于补充动作、镜头和节奏信息。", limits=["最大长度约 2500 字符", "留空时仅依据首帧图生成"], how_to_choose=["首帧已能表达主体时，用 prompt 补动作和镜头变化", "想保持更多首帧原貌时可先留空做 smoke"], notes=common_notes),
                    },
                }
            },
        ),
        "happyhorse-1.0-r2v": _build_model(
            model_id="happyhorse-1.0-r2v",
            name="HappyHorse 1.0 参考生视频",
            provider="happyhorse",
            description="HappyHorse 参考生视频模型，使用 1 到 9 张参考图和提示词融合生成视频。",
            recommended=False,
            doc_url="docs/阿里云模型api文档/HappyHorse-参考生视频API参考.md",
            supported_task_kinds=["reference_to_video"],
            task_profiles={
                "reference_to_video": {
                    "label": "参考生视频",
                    "description": "使用多张参考图生成视频，prompt 可通过 character1、character2 指代对应顺序的参考图。",
                    "input_roles": ["reference_image"],
                    "parameters": r2v_params,
                    "verification_profiles": {"smoke": ["single_reference_image"], "full": ["single_reference_image", "multi_reference_images"]},
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "max_reference_images": 9,
                        "max_reference_videos": 0,
                        "max_reference_total": 9,
                        "asset_help": {
                            "reference_image": _asset_help("参考图用于指定视频中的角色、物体或视觉主体。", limits=["必须提供 1 到 9 张参考图", "支持 JPEG/JPG/PNG/WEBP", "短边不能小于 400 像素", "文件大小不超过 10MB"], how_to_choose=["按照 prompt 中 character1、character2 的引用顺序添加参考图", "主体尽量清晰完整，避免强压缩和模糊"], notes=common_notes),
                        },
                        "prompt_help": _help(summary="Prompt 描述场景、动作、镜头和参考图的融合方式。", limits=["最大长度约 2500 字符", "不能为空或纯空格"], how_to_choose=["使用 character1、character2 等词指代对应顺序的参考图", "先写主体关系，再补场景、动作和镜头"], notes=["character1 对应第 1 张参考图，character2 对应第 2 张参考图，以此类推。", *common_notes]),
                    },
                }
            },
        ),
        "happyhorse-1.0-video-edit": _build_model(
            model_id="happyhorse-1.0-video-edit",
            name="HappyHorse 1.0 视频编辑",
            provider="happyhorse",
            description="HappyHorse 视频编辑模型，基于输入视频和可选参考图完成风格变换、局部替换等编辑。",
            recommended=False,
            doc_url="docs/阿里云模型api文档/HappyHorse-视频编辑API参考.md",
            supported_task_kinds=["video_edit_global"],
            task_profiles={
                "video_edit_global": {
                    "label": "视频编辑",
                    "description": "对整段视频做指令编辑，可选参考图引导服饰、物体或风格。",
                    "input_roles": ["base_video", "reference_image"],
                    "parameters": video_edit_params,
                    "verification_profiles": {"smoke": ["base_only"], "full": ["base_only", "base_plus_reference_images"]},
                    "ui_hints": {
                        "prompt_max_length": 2500,
                        "max_reference_images": 5,
                        "max_reference_videos": 0,
                        "max_reference_total": 5,
                        "asset_help": {
                            "base_video": _asset_help("待编辑视频是被修改的原始视频。", limits=["必须且仅支持 1 个视频", "支持 MP4/MOV，建议 H.264", "时长需在 3 到 60 秒之间", "长边不超过 2160 像素，短边不小于 320 像素", "宽高比需在 1:2.5 到 2.5:1 之间", "文件大小不超过 100MB", "帧率必须大于 8 FPS"], how_to_choose=["优先选择单镜头、主体清晰的视频", "输入视频超过 15 秒时，厂商会从头截取前 15 秒作为有效输出片段"], notes=common_notes),
                            "reference_image": _asset_help("参考图用于引导编辑后的外观、服饰、物体或风格。", limits=["最多 5 张参考图", "支持 JPEG/JPG/PNG/WEBP", "宽高不能小于 300 像素", "宽高比需在 1:2.5 到 2.5:1 之间", "文件大小不超过 10MB"], how_to_choose=["不传参考图时适合普通风格修改", "传参考图时适合服饰替换、物体参考和局部视觉引导"], notes=common_notes),
                        },
                        "prompt_help": _help(summary="Prompt 描述视频编辑意图。", limits=["最大长度约 2500 字符", "不能为空或纯空格"], how_to_choose=["明确写出要改变什么，以及参考图应如何被使用", "例如服饰替换、风格变换、局部物体替换"], notes=common_notes),
                    },
                }
            },
        ),
    }


def _vidu_models() -> Dict[str, Dict[str, Any]]:
    size_options = _vidu_size_options()
    ref_size_options = _vidu_reference_size_options()
    return {
        "vidu/viduq3-pro_text2video": _vidu_model(
            model_id="vidu/viduq3-pro_text2video",
            name="Vidu Q3 Pro 文生视频",
            description="Vidu Q3 Pro 文生视频，支持 1-16 秒和音频",
            task_kind="text_to_video",
            input_roles=[],
            duration_range=[1, 16],
            supports_audio=True,
            size_options_by_resolution=size_options,
        ),
        "vidu/viduq3-turbo_text2video": _vidu_model(
            model_id="vidu/viduq3-turbo_text2video",
            name="Vidu Q3 Turbo 文生视频",
            description="Vidu Q3 Turbo 文生视频，支持 1-16 秒和音频",
            task_kind="text_to_video",
            input_roles=[],
            duration_range=[1, 16],
            supports_audio=True,
            size_options_by_resolution=size_options,
            recommended=True,
        ),
        "vidu/viduq2_text2video": _vidu_model(
            model_id="vidu/viduq2_text2video",
            name="Vidu Q2 文生视频",
            description="Vidu Q2 文生视频，支持 1-10 秒，无音频",
            task_kind="text_to_video",
            input_roles=[],
            duration_range=[1, 10],
            supports_audio=False,
            size_options_by_resolution=size_options,
        ),
        "vidu/viduq3-pro_img2video": _vidu_model(
            model_id="vidu/viduq3-pro_img2video",
            name="Vidu Q3 Pro 首帧生视频",
            description="Vidu Q3 Pro 图生视频，支持 1-16 秒和音频",
            task_kind="image_to_video",
            input_roles=["first_frame"],
            duration_range=[1, 16],
            supports_audio=True,
            recommended=False,
            ui_hints={"size_options_by_resolution": {}},
        ),
        "vidu/viduq3-turbo_img2video": _vidu_model(
            model_id="vidu/viduq3-turbo_img2video",
            name="Vidu Q3 Turbo 首帧生视频",
            description="Vidu Q3 Turbo 图生视频，支持 1-16 秒和音频",
            task_kind="image_to_video",
            input_roles=["first_frame"],
            duration_range=[1, 16],
            supports_audio=True,
            recommended=True,
            ui_hints={"size_options_by_resolution": {}},
        ),
        "vidu/viduq2-pro_img2video": _vidu_model(
            model_id="vidu/viduq2-pro_img2video",
            name="Vidu Q2 Pro 首帧生视频",
            description="Vidu Q2 Pro 图生视频，支持 1-10 秒，无音频",
            task_kind="image_to_video",
            input_roles=["first_frame"],
            duration_range=[1, 10],
            supports_audio=False,
            resolution_values=["720P", "1080P"],
            ui_hints={"size_options_by_resolution": {}},
        ),
        "vidu/viduq2-turbo_img2video": _vidu_model(
            model_id="vidu/viduq2-turbo_img2video",
            name="Vidu Q2 Turbo 首帧生视频",
            description="Vidu Q2 Turbo 图生视频，支持 1-10 秒，无音频",
            task_kind="image_to_video",
            input_roles=["first_frame"],
            duration_range=[1, 10],
            supports_audio=False,
            resolution_values=["720P", "1080P"],
            ui_hints={"size_options_by_resolution": {}},
        ),
        "vidu/viduq3-pro_start-end2video": _vidu_model(
            model_id="vidu/viduq3-pro_start-end2video",
            name="Vidu Q3 Pro 首尾帧生视频",
            description="Vidu Q3 Pro 首尾帧生视频，支持 1-16 秒和音频",
            task_kind="keyframe_to_video",
            input_roles=["first_frame", "last_frame"],
            duration_range=[1, 16],
            supports_audio=True,
        ),
        "vidu/viduq3-turbo_start-end2video": _vidu_model(
            model_id="vidu/viduq3-turbo_start-end2video",
            name="Vidu Q3 Turbo 首尾帧生视频",
            description="Vidu Q3 Turbo 首尾帧生视频，支持 1-16 秒和音频",
            task_kind="keyframe_to_video",
            input_roles=["first_frame", "last_frame"],
            duration_range=[1, 16],
            supports_audio=True,
            recommended=True,
        ),
        "vidu/viduq2-pro_start-end2video": _vidu_model(
            model_id="vidu/viduq2-pro_start-end2video",
            name="Vidu Q2 Pro 首尾帧生视频",
            description="Vidu Q2 Pro 首尾帧生视频，支持 1-10 秒，无音频",
            task_kind="keyframe_to_video",
            input_roles=["first_frame", "last_frame"],
            duration_range=[1, 10],
            supports_audio=False,
        ),
        "vidu/viduq2-turbo_start-end2video": _vidu_model(
            model_id="vidu/viduq2-turbo_start-end2video",
            name="Vidu Q2 Turbo 首尾帧生视频",
            description="Vidu Q2 Turbo 首尾帧生视频，支持 1-10 秒，无音频",
            task_kind="keyframe_to_video",
            input_roles=["first_frame", "last_frame"],
            duration_range=[1, 10],
            supports_audio=False,
        ),
        "vidu/viduq2_reference2video": _vidu_model(
            model_id="vidu/viduq2_reference2video",
            name="Vidu Q2 参考生视频",
            description="Vidu Q2 参考生视频，支持 1-7 张参考图",
            task_kind="reference_to_video",
            input_roles=["reference_image"],
            duration_range=[1, 10],
            supports_audio=False,
            size_options_by_resolution=ref_size_options,
            ui_hints={"max_reference_images": 7, "max_reference_videos": 0, "max_reference_total": 7},
        ),
        "vidu/viduq2-pro_reference2video": _vidu_model(
            model_id="vidu/viduq2-pro_reference2video",
            name="Vidu Q2 Pro 参考生视频",
            description="Vidu Q2 Pro 参考生视频，支持图像和参考视频组合",
            task_kind="reference_to_video",
            input_roles=["reference_image", "reference_video"],
            duration_range=[0, 10],
            supports_audio=False,
            size_options_by_resolution=ref_size_options,
            recommended=True,
            ui_hints={"max_reference_images": 4, "max_reference_videos": 2, "max_reference_total": 5},
        ),
    }


def get_video_capabilities() -> Dict[str, Any]:
    models: Dict[str, Dict[str, Any]] = {}
    models.update(_wan_text_to_video_models())
    models.update(_wan_image_to_video_models())
    models.update(_wan_reference_to_video_models())
    models.update(_wan_keyframe_models())
    models.update(_wan27_video_models())
    models.update(_wan_vace_models())
    models.update(_happyhorse_models())
    models.update(_kling_models())
    models.update(_vidu_models())

    task_kinds: List[Dict[str, Any]] = []
    for task_def in TASK_KIND_DEFS:
        supported_models = [
            model_id
            for model_id, model in models.items()
            if task_def["id"] in model.get("supported_task_kinds", [])
        ]
        default_model_id = VIDEO_STUDIO_DEFAULT_MODELS.get(task_def["id"])
        if default_model_id not in supported_models:
            default_model_id = supported_models[0] if supported_models else None
        task_kinds.append(
            {
                **task_def,
                "model_ids": supported_models,
                "default_model_id": default_model_id,
            }
        )

    return {
        "task_kinds": task_kinds,
        "models": models,
        "legacy_task_kind_map": deepcopy(LEGACY_TASK_KIND_MAP),
    }
