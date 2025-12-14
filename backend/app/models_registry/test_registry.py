"""
模型注册系统测试脚本

运行方式:
    cd backend
    python -m app.models_registry.test_registry
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models_registry import registry, ModelType


def test_registry():
    """测试模型注册"""
    print("=" * 60)
    print("模型注册系统测试")
    print("=" * 60)
    
    # 1. 测试获取所有模型
    print("\n📋 所有已注册模型:")
    all_models = registry.list_models()
    for model in all_models:
        print(f"  - {model.id}: {model.name} ({model.type.value})")
    
    print(f"\n总计: {len(all_models)} 个模型")
    
    # 2. 按类型列出模型
    print("\n📂 按类型分组:")
    models_by_type = registry.list_models_by_type()
    for model_type, models in models_by_type.items():
        print(f"\n  {model_type.value}:")
        for m in models:
            print(f"    - {m.id}: {m.name}")
    
    # 3. 测试单个模型详情
    print("\n🔍 模型详情示例 (wan2.5-i2v-preview):")
    model = registry.get_model_info("wan2.5-i2v-preview")
    if model:
        print(f"  名称: {model.name}")
        print(f"  类型: {model.type.value}")
        print(f"  描述: {model.description}")
        print(f"  能力:")
        print(f"    - 异步: {model.capabilities.supports_async}")
        print(f"    - 音频: {model.capabilities.supports_audio}")
        print(f"    - 种子: {model.capabilities.supports_seed}")
        print(f"  参数数量: {len(model.parameters)}")
        print(f"  参数列表:")
        for p in model.parameters:
            default = f" (默认: {p.default})" if p.default is not None else ""
            required = " *必填" if p.required else ""
            print(f"    - {p.name}: {p.type.value}{required}{default}")
    
    # 4. 测试参数验证
    print("\n✅ 参数验证测试:")
    test_params = {
        "img_url": "https://example.com/image.jpg",
        "prompt": "测试提示词",
        "resolution": "720P",
        "duration": 10,
    }
    valid, errors = model.validate_params(test_params)
    print(f"  验证结果: {'通过' if valid else '失败'}")
    if errors:
        for err in errors:
            print(f"    - {err}")
    
    # 5. 测试 LLM 模型
    print("\n🤖 LLM 模型示例 (qwen3-max):")
    llm = registry.get_model_info("qwen3-max")
    if llm:
        print(f"  名称: {llm.name}")
        print(f"  能力:")
        print(f"    - 流式: {llm.capabilities.supports_streaming}")
        print(f"    - 思考: {llm.capabilities.supports_thinking}")
        print(f"    - 搜索: {llm.capabilities.supports_search}")
        print(f"    - JSON: {llm.capabilities.supports_json_mode}")
    
    # 6. 测试获取前端配置
    print("\n📱 前端配置 (部分):")
    frontend_config = registry.get_all_model_info_for_frontend()
    for model_id, config in list(frontend_config.items())[:2]:
        print(f"\n  {model_id}:")
        print(f"    name: {config['name']}")
        print(f"    type: {config['type']}")
        print(f"    parameters: {len(config['parameters'])} 个")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    test_registry()

