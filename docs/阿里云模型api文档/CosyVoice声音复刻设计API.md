CosyVoice声音复刻/设计API
更新时间：2026-03-03 13:31:53
复制为 MD 格式
产品详情
我的收藏
CosyVoice声音复刻服务基于生成式语音大模型，使用10~20秒音频样本即可生成高度相似且自然的定制声音，无需传统训练过程。声音设计通过文本描述生成定制化音色，支持多语言和多维度音色特征定义，适用于广告配音、角色塑造、有声内容创作等多种应用。声音复刻/设计与语音合成是前后关联的两个步骤。本文档聚焦于介绍声音复刻/设计的参数和接口细节，语音合成请参见实时语音合成-CosyVoice/Sambert。

用户指南：关于模型介绍和选型建议请参见实时语音合成-CosyVoice/Sambert。

重要
本文档专用于CosyVoice声音复刻/设计接口；若您使用的是千问模型，请参见声音复刻（Qwen）和声音设计（Qwen）。

支持的模型
声音复刻：

cosyvoice-v3.5-plus、cosyvoice-v3.5-flash

cosyvoice-v3-plus、cosyvoice-v3-flash

cosyvoice-v1、cosyvoice-v2

声音设计：

cosyvoice-v3.5-plus、cosyvoice-v3.5-flash

cosyvoice-v3-plus、cosyvoice-v3-flash

重要
cosyvoice-v3.5-plus和cosyvoice-v3.5-flash仅在中国内地部署模式（北京地域）下可用。

在国际部署模式（新加坡地域）下，cosyvoice-v3-plus和cosyvoice-v3-flash不支持声音复刻和声音设计功能，请选择其他模型。

支持的语言
声音复刻：因驱动音色的语音合成模型（通过target_model/targetModel参数指定）而异：

cosyvoice-v1、cosyvoice-v2：中文（普通话）、英文

cosyvoice-v3.5-plus、cosyvoice-v3.5-flash、cosyvoice-v3-flash：中文（普通话、广东话、东北话、甘肃话、贵州话、河南话、湖北话、江西话、闽南话、宁夏话、山西话、陕西话、山东话、上海话、四川话、天津话、云南话）、英文、法语、德语、日语、韩语、俄语、葡萄牙语、泰语、印尼语、越南语

cosyvoice-v3-plus：中文（普通话）、英文、法语、德语、日语、韩语、俄语

当前声音复刻仅支持上述列出的语言（中文普通话及表中列出的方言、英文、法语、德语、日语、韩语、俄语），暂不支持西班牙语、意大利语等其他语种的声音复刻。

声音设计：中文、英文。

快速开始：从声音复刻到语音合成
image
声音复刻与语音合成是紧密关联的两个独立步骤，遵循“先创建，后使用”的流程：

准备录音文件

将符合声音复刻：输入音频格式的音频文件上传至公网可访问的位置，如阿里云对象存储OSS，并确保URL可公开访问。

创建音色

调用创建音色接口。此步骤必须指定target_model/targetModel，声明创建的音色将由哪个语音合成模型驱动。

若已有创建好的音色（调用查询音色列表接口查看），可跳过这一步直接进行下一步。

使用音色进行语音合成

使用创建音色接口创建音色成功后，系统会返回一个voice_id/voiceID：

该 voice_id/voiceID 可直接作为语音合成接口或各语言 SDK 中的 voice 参数使用，用于后续的文本转语音。

支持多种调用形态，包括非流式、单向流式以及双向流式合成。

合成时指定的语音合成模型必须与创建音色时的 target_model/targetModel 保持一致，否则合成会失败。

示例代码：

 
import os
import time
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer

# 1. 环境准备
# 推荐通过环境变量配置API Key
# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "sk-xxx"
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
if not dashscope.api_key:
    raise ValueError("DASHSCOPE_API_KEY environment variable not set.")

# 以下为北京地域WebSocket url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'
# 以下为北京地域HTTP url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'


# 2. 定义复刻参数
TARGET_MODEL = "cosyvoice-v3.5-plus" 
# 为音色起一个有意义的前缀
VOICE_PREFIX = "myvoice" # 仅允许数字和小写字母，小于十个字符
# 公网可访问音频URL
AUDIO_URL = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/cosyvoice/cosyvoice-zeroshot-sample.wav" # 示例URL，请替换为自己的

# 3. 创建音色 (异步任务)
print("--- Step 1: Creating voice enrollment ---")
service = VoiceEnrollmentService()
try:
    voice_id = service.create_voice(
        target_model=TARGET_MODEL,
        prefix=VOICE_PREFIX,
        url=AUDIO_URL
    )
    print(f"Voice enrollment submitted successfully. Request ID: {service.get_last_request_id()}")
    print(f"Generated Voice ID: {voice_id}")
except Exception as e:
    print(f"Error during voice creation: {e}")
    raise e
# 4. 轮询查询音色状态
print("\n--- Step 2: Polling for voice status ---")
max_attempts = 30
poll_interval = 10 # 秒
for attempt in range(max_attempts):
    try:
        voice_info = service.query_voice(voice_id=voice_id)
        status = voice_info.get("status")
        print(f"Attempt {attempt + 1}/{max_attempts}: Voice status is '{status}'")
        
        if status == "OK":
            print("Voice is ready for synthesis.")
            break
        elif status == "UNDEPLOYED":
            print(f"Voice processing failed with status: {status}. Please check audio quality or contact support.")
            raise RuntimeError(f"Voice processing failed with status: {status}")
        # 对于 "DEPLOYING" 等中间状态，继续等待
        time.sleep(poll_interval)
    except Exception as e:
        print(f"Error during status polling: {e}")
        time.sleep(poll_interval)
else:
    print("Polling timed out. The voice is not ready after several attempts.")
    raise RuntimeError("Polling timed out. The voice is not ready after several attempts.")

# 5. 使用复刻音色进行语音合成
print("\n--- Step 3: Synthesizing speech with the new voice ---")
try:
    synthesizer = SpeechSynthesizer(model=TARGET_MODEL, voice=voice_id)
    text_to_synthesize = "恭喜，已成功复刻并合成了属于自己的声音！"
    
    # call()方法返回二进制音频数据
    audio_data = synthesizer.call(text_to_synthesize)
    print(f"Speech synthesis successful. Request ID: {synthesizer.get_last_request_id()}")

    # 6. 保存音频文件
    output_file = "my_custom_voice_output.mp3"
    with open(output_file, "wb") as f:
        f.write(audio_data)
    print(f"Audio saved to {output_file}")

except Exception as e:
    print(f"Error during speech synthesis: {e}")
快速开始：从声音设计到语音合成
image
声音设计与语音合成是紧密关联的两个独立步骤，遵循“先创建，后使用”的流程：

准备声音设计所需的声音描述与试听文本。

声音描述（voice_prompt）：定义目标音色的特征（关于如何编写请参见“声音设计：如何编写高质量的声音描述？”）。

试听文本（preview_text）：目标音色生成的预览音频朗读的内容（如“大家好，欢迎收听”）。

调用创建音色接口，创建一个专属音色，获取音色名和预览音频。

此步骤必须指定target_model，声明创建的音色将由哪个语音合成模型驱动

试听获取预览音频来判断是否符合预期；若符合要求，继续下一步，否则，重新设计。

若已有创建好的音色（调用查询音色列表接口查看），可跳过这一步直接进行下一步。

使用音色进行语音合成

使用创建音色接口创建音色成功后，系统会返回一个voice_id/voiceID：

该 voice_id/voiceID 可直接作为语音合成接口或各语言 SDK 中的 voice 参数使用，用于后续的文本转语音。

支持多种调用形态，包括非流式、单向流式以及双向流式合成。

合成时指定的语音合成模型必须与创建音色时的 target_model/targetModel 保持一致，否则合成会失败。

示例代码：

生成专属音色并试听效果，若对效果满意，进行下一步；否则重新生成。

PythonJava
 
import requests
import base64
import os

def create_voice_and_play():
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("错误: 未找到DASHSCOPE_API_KEY环境变量，请先设置API Key")
        return None, None, None
    
    # 准备请求数据
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "voice-enrollment",
        "input": {
            "action": "create_voice",
            "target_model": "cosyvoice-v3.5-plus",
            "voice_prompt": "沉稳的中年男性播音员，音色低沉浑厚，富有磁性，语速平稳，吐字清晰，适合用于新闻播报或纪录片解说。",
            "preview_text": "各位听众朋友，大家好，欢迎收听晚间新闻。",
            "prefix": "announcer"
        },
        "parameters": {
            "sample_rate": 24000,
            "response_format": "wav"
        }
    }
    
    # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
    url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
    
    try:
        # 发送请求
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=60  # 添加超时设置
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # 获取音色ID
            voice_id = result["output"]["voice_id"]
            print(f"音色ID: {voice_id}")
            
            # 获取预览音频数据
            base64_audio = result["output"]["preview_audio"]["data"]
            
            # 解码Base64音频数据
            audio_bytes = base64.b64decode(base64_audio)
            
            # 保存音频文件到本地
            filename = f"{voice_id}_preview.wav"
            
            # 将音频数据写入本地文件
            with open(filename, 'wb') as f:
                f.write(audio_bytes)
            
            print(f"音频已保存到本地文件: {filename}")
            print(f"文件路径: {os.path.abspath(filename)}")
            
            return voice_id, audio_bytes, filename
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None, None, None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求发生错误: {e}")
        return None, None, None
    except KeyError as e:
        print(f"响应数据格式错误，缺少必要的字段: {e}")
        print(f"响应内容: {response.text if 'response' in locals() else 'No response'}")
        return None, None, None
    except Exception as e:
        print(f"发生未知错误: {e}")
        return None, None, None

if __name__ == "__main__":
    print("开始创建语音...")
    voice_id, audio_data, saved_filename = create_voice_and_play()
    
    if voice_id:
        print(f"\n成功创建音色 '{voice_id}'")
        print(f"音频文件已保存: '{saved_filename}'")
        print(f"文件大小: {os.path.getsize(saved_filename)} 字节")
    else:
        print("\n音色创建失败")
使用上一步生成的专属音色进行语音合成。

这里参考了非流式调用示例代码，将voice参数替换为声音设计生成的专属音色进行语音合成。

关键原则：声音设计时使用的模型 (target_model) 必须与后续进行语音合成时使用的模型 (model) 保持一致，否则会导致合成失败。

PythonJava
 
# coding=utf-8

import dashscope
from dashscope.audio.tts_v2 import *
import os

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "sk-xxx"
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY')

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 声音设计、语音合成要使用相同的模型
model = "cosyvoice-v3.5-plus"
# 将voice参数替换为声音设计生成的专属音色
voice = "your_voice"

# 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数
synthesizer = SpeechSynthesizer(model=model, voice=voice)
# 发送待合成文本，获取二进制音频
audio = synthesizer.call("今天天气怎么样？")
# 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format(
    synthesizer.get_last_request_id(),
    synthesizer.get_first_package_delay()))

# 将音频保存至本地
with open('output.mp3', 'wb') as f:
    f.write(audio)
API参考
使用不同 API 时，请确保使用同一账号进行操作。

重要
Java和Python DashScope SDK不支持声音设计。使用声音设计功能时请参见RESTful API。

创建音色
RESTful APIPython SDKJava SDK
URL

中国内地：

 
POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization
国际：

 
POST https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
请求头

参数

类型

是否必须

说明

Authorization

string

支持

鉴权令牌，格式为Bearer <your_api_key>，使用时，将“<your_api_key>”替换为实际的API Key。

Content-Type

string

支持

请求体中传输的数据的媒体类型。固定为application/json。

消息体

包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略。

重要
注意区分如下参数：

model：声音复刻/设计模型，固定为voice-enrollment

target_model：驱动音色的语音合成模型，须和后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败

声音复刻声音设计
 
{
    "model": "voice-enrollment",
    "input": {
        "action": "create_voice",
        "target_model": "cosyvoice-v3.5-plus",
        "prefix": "myvoice",
        "url": "https://yourAudioFileUrl",
        "language_hints": ["zh"]
    }
}
请求参数

参数

类型

默认值

是否必须

说明

model

string

-

支持

声音复刻/设计模型，固定为voice-enrollment。

action

string

-

支持

操作类型，固定为create_voice。

target_model

string

-

支持

驱动音色的语音合成模型（参见支持的模型）。

必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。

url

string

-

支持

重要
仅在声音复刻时必须使用该参数

用于复刻音色的音频文件URL，要求公网可访问。

音频格式说明请参见。

如何录音请参见录音操作指南。

voice_prompt

string

-

支持

重要
仅在声音设计时必须使用该参数

声音描述。最大长度 500 字符。

只支持中文和英文。

关于如何编写声音描述，请参见“”。

preview_text

string

-

支持

重要
仅在声音设计时必须使用该参数

预览音频对应的文本。最大长度 200 字符。

支持中文（zh）、英文（en）。

prefix

string

-

支持

为音色指定一个便于识别的名称（仅允许数字和英文字母，不超过10个字符）。建议选用与角色、场景相关的标识。

该关键字会在设计的音色名中出现，例如关键字为“announcer”，最终音色名为：
声音复刻：cosyvoice-v3.5-plus-announcer-8aae0c0397fa408ca60c29cf******
声音设计：cosyvoice-v3.5-plus-vd-announcer-8aae0c0397fa408ca60c29cf******
language_hints

array[string]

["zh"]

不支持

指定用于提取目标音色特征的样本音频语种，仅适用于 cosyvoice-v3.5-plus、cosyvoice-v3.5-flash、cosyvoice-v3-flash 和 cosyvoice-v3-plus 模型。

注意：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。

功能说明：

声音复刻声音设计
该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。若设置的语言提示与实际音频语言不符（例如为中文音频设置 en），系统将忽略此提示，并依据音频内容自动检测语言。

取值范围（因模型而异）：

cosyvoice-v3-plus：

zh：中文（默认值）

en：英文

fr：法语

de：德语

ja：日语

ko：韩语

ru：俄语

cosyvoice-v3.5-plus、cosyvoice-v3.5-flash、cosyvoice-v3-flash：

zh：中文（默认值）

en：英文

fr：法语

de：德语

ja：日语

ko：韩语

ru：俄语

pt：葡萄牙语

th：泰语

id：印尼语

vi：越南语

对于中文方言（例如东北话、粤语等），建议仍将 language_hints 设置为 zh，方言风格应在后续语音合成调用中通过文本内容或 instruct 等参数进行控制。

max_prompt_audio_length

float

10.0

否

重要
仅在声音复刻场景下可以使用该参数

音频预处理后用于声音复刻的参考音频最大时长，单位为秒。仅适用于 cosyvoice-v3.5-plus、cosyvoice-v3.5-flash和cosyvoice-v3-flash 模型。

sample_rate

int

24000

不支持

重要
仅在声音设计场景下可以使用该参数

声音设计生成的预览音频采样率（单位：Hz）。

取值范围：

16000

24000

48000

response_format

string

wav

不支持

重要
仅在声音设计场景下可以使用该参数

声音设计生成的预览音频格式。

取值范围：

pcm

wav

mp3

响应参数

点击查看响应示例

需关注的参数如下：

参数

类型

说明

voice_id

string

音色ID，可直接用于语音合成接口的voice参数。

data

string

声音设计生成的预览音频数据，以 Base64 编码字符串形式返回。

sample_rate

int

声音设计生成的预览音频采样率（单位：Hz），与音色创建时的采样率一致，未指定则默认为 24000 Hz。

response_format

string

声音设计生成的预览音频格式，与音色创建时的音频格式一致，未指定则默认为wav。

target_model

string

驱动音色的语音合成模型（参见支持的模型）。

必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。

request_id

string

Request ID。

count

integer

本次请求实际“创建音色”次数。

创建音色时，count恒为1。

示例代码

重要
注意区分如下参数：

model：声音复刻/设计模型，固定为voice-enrollment

target_model：驱动音色的语音合成模型，须和后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败

声音复刻声音设计
若未将API Key配置到环境变量，需将示例中的$DASHSCOPE_API_KEY替换为实际的API Key。

 
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "create_voice",
        "target_model": "cosyvoice-v3.5-plus",
        "prefix": "myvoice",
        "url": "https://yourAudioFileUrl"
    }
}'
查询音色列表
分页查询已创建的音色列表。

RESTful APIPython SDKJava SDK
URL和请求头与创建音色接口相同

消息体

包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略。

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

 
{
    "model": "voice-enrollment",
    "input": {
        "action": "list_voice",
        "prefix": "announcer"
        "page_size": 10,
        "page_index": 0
    }
}
请求参数

参数

类型

默认值

是否必须

说明

model

string

-

支持

声音复刻/设计模型，固定为voice-enrollment。

action

string

-

支持

操作类型，固定为list_voice。

prefix

string

-

不支持

和创建音色时使用的prefix相同。仅允许数字和英文字母，不超过10个字符。

page_index

integer

0

不支持

页码索引，需大于或等于0。

page_size

integer

10

不支持

每页包含数据条数。取值范围：[0, 1000]。

响应参数

点击查看响应示例

需关注的参数如下：

参数

类型

说明

voice_id

string

音色ID，可直接用于语音合成接口的voice参数。

target_model

string

驱动音色的语音合成模型（参见支持的模型）。

必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。

gmt_create

string

创建音色的时间。

gmt_modified

string

修改音色的时间。

voice_prompt

string

声音描述。

preview_text

string

试听文本。

request_id

string

Request ID。

status

string

音色状态：

DEPLOYING： 审核中

OK：审核通过，可调用

UNDEPLOYED：审核不通过，不可调用

示例代码

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

若未将API Key配置到环境变量，需将示例中的$DASHSCOPE_API_KEY替换为实际的API Key。

 
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "list_voice",
        "prefix": "announcer",
        "page_size": 10,
        "page_index": 0
    }
}'
查询特定音色
通过音色名称获取特定音色的详细信息。

RESTful APIPython SDKJava SDK
URL和请求头与创建音色接口相同

消息体

包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略。

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

 
{
    "model": "voice-enrollment",
    "input": {
        "action": "query_voice",
        "voice_id": "yourVoiceID"
    }
}
请求参数

参数

类型

默认值

是否必须

说明

model

string

-

支持

声音复刻/设计模型，固定为voice-enrollment。

action

string

-

支持

操作类型，固定为query_voice。

voice_id

string

-

支持

待查询的音色ID。

响应参数

点击查看响应示例

声音复刻声音设计
 
{
    "output": {
        "gmt_create": "2024-12-11 13:38:02",
        "resource_link": "https://yourAudioFileUrl",
        "target_model": "cosyvoice-v3.5-plus",
        "gmt_modified": "2024-12-11 13:38:02",
        "status": "OK"
    },
    "usage": {
        "count": 1
    },
    "request_id": "2450f969-d9ea-9483-bafc-************"
}
参数说明请参见查询音色列表接口。

示例代码

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

若未将API Key配置到环境变量，需将示例中的$DASHSCOPE_API_KEY替换为实际的API Key。

 
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "query_voice",
        "voice_id": "yourVoiceID"
    }
}'
更新音色（仅限声音复刻）
使用新的音频文件更新一个已存在的音色。

重要
声音设计不支持该功能。

RESTful APIPython SDKJava SDK
URL和请求头与创建音色接口相同

消息体

包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略：

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

 
{
    "model": "voice-enrollment",
    "input": {
        "action": "update_voice",
        "voice_id": "yourVoiceId",
        "url": "https://yourAudioFileUrl"
    }
}
请求参数

参数

类型

默认值

是否必须

说明

model

string

-

支持

声音复刻/设计模型，固定为voice-enrollment。

action

string

-

支持

操作类型，固定为update_voice。

voice_id

string

-

支持

待更新的音色。

url

string

-

支持

用于更新音色的音频文件URL。该URL要求公网可访问。

响应参数

点击查看响应示例

 
{
    "output": {},
    "usage": {
        "count": 1
    },
    "request_id": "yourRequestId"
}
示例代码

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

若未将API Key配置到环境变量，需将示例中的$DASHSCOPE_API_KEY替换为实际的API Key。

 
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "update_voice",
        "voice_id": "yourVoiceId",
        "url": "https://yourAudioFileUrl"
    }
}'
删除音色
删除一个不再需要的音色以释放配额。此操作不可逆。

RESTful APIPython SDKJava SDK
URL和请求头与创建音色接口相同

消息体

包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略：

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

 
{
    "model": "voice-enrollment",
    "input": {
        "action": "delete_voice",
        "voice_id": "yourVoiceID"
    }
}
请求参数

参数

类型

默认值

是否必须

说明

model

string

-

支持

声音复刻/设计模型，固定为voice-enrollment。

action

string

-

支持

操作类型，固定为delete_voice。

voice_id

string

-

支持

待删除的音色。

响应参数
点击查看响应示例

 
{
    "output": {},
    "usage": {
        "count": 1
    },
    "request_id": "yourRequestId"
}
示例代码

重要
model：声音复刻/设计模型，固定为voice-enrollment，请勿修改。

若未将API Key配置到环境变量，需将示例中的$DASHSCOPE_API_KEY替换为实际的API Key。

 
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "delete_voice",
        "voice_id": "yourVoiceID"
    }
}'
音色配额与自动清理规则
总数限制：1000个音色

当前接口不提供音色数量查询功能，可通过调用接口自行统计音色数目
自动清理：若单个音色在过去一年内未被用于任何语音合成请求，系统将自动将其删除

计费说明
声音复刻/设计：创建、查询、更新、删除音色免费

使用声音复刻/设计生成的专属音色进行语音合成：按量（文本字符数）计费，参见实时语音合成-CosyVoice/Sambert

版权与合法性
您需对所提供声音的所有权及合法使用权负责，请注意阅读服务协议。

错误码
如遇报错问题，请参见错误信息进行排查。

常见问题
功能特性
Q：如何调节自定义音色的语速、音量？
与使用预置音色完全相同。在调用语音合成API时，传入相应的参数即可，例如 speech_rate (Python) / speechRate (Java) 用于调节语速，volume 用于调节音量。详情请参见语音合成API文档（Java SDK/Python SDK/WebSocket API）

Q：除了Java和Python，其他语言（如Go, C#, Node.js）如何调用？
对于音色管理，请直接使用文档中提供的RESTful API。对于语音合成，请使用WebSocket API，并将复刻得到的 voice_id 作为 voice 参数传入。

故障排查
如遇代码报错问题，请根据错误码中的信息进行排查。

Q：使用复刻音色合成时音频中出现额外内容如何处理？
若使用复刻音色合成音频时，发现输出的音频中包含输入文本以外的额外字符或杂音，请按以下步骤排查：

检查源音频质量

复刻音频质量直接影响合成效果。确保源音频满足以下要求：

无背景噪音和杂音

音质清晰（建议采样率≥16kHz）

音频格式：WAV格式优于MP3（避免有损压缩）

单声道（立体声可能引入干扰）

无静音段或过长停顿

语速适中（过快的语速影响特征提取）

检查输入文本

确认输入文本中不包含特殊符号或标记：

避免使用 **、""、'' 等特殊符号

若非用于LaTeX公式包裹，建议预处理过滤特殊符号

验证音色复刻参数

确保时，语言参数（language_hints/languageHints）设置正确

尝试重新复刻

使用质量更高的源音频重新进行复刻，并测试合成效果。

对比系统音色

使用系统预置音色测试相同文本，确认是否为复刻音色特定问题。

Q：使用复刻音色生成的音频无声音如何排查？
确认音色状态

调用查询特定音色接口，查看音色status是否为OK。

检查模型版本一致性

确保复刻音色时使用的target_model参数与语音合成时的model参数完全一致。例如：

复刻时使用cosyvoice-v3-plus

合成时也必须使用cosyvoice-v3-plus

验证源音频质量

检查复刻音色时使用的源音频是否符合声音复刻输入音频格式：

音频时长：10-20秒

音质清晰

无背景噪音

检查请求参数

确认语音合成时请求参数voice设置为复刻音色的ID。

Q：声音复刻后合成效果不稳定或语音不完整如何处理？
如果复刻音色后合成的语音出现以下问题：

语音播放不完整，只读出部分文字

合成效果不稳定，时好时坏

语音中包含异常停顿或静音段

可能原因：源音频质量不符合要求

解决方案：检查源音频是否符合如下要求，建议按照录音操作指南重新录制

检查音频连续性：确保源音频中语音内容连续，避免长时间停顿或静音段（超过2秒）。如果音频中存在明显的空白段，会导致模型将静音或噪声作为音色特征的一部分，影响生成效果

检查语音活动比例：确保有效语音占音频总时长的60%以上。如果背景噪声、非语音段过多，会干扰音色特征提取

验证音频质量细节：

音频时长：10-20秒（推荐15秒左右）

发音清晰，语速平稳

无背景噪音、回音、杂音

语音能量集中，无长时间静音段

Q：为什么找不到 VoiceEnrollmentService 类？
SDK版本过低。请安装最新版SDK。

Q：声音复刻效果不佳，有杂音或不清晰怎么办？
这通常是由于输入音频质量不高导致的。请严格遵循录音操作指南重新录制并上传音频。

Q：为什么使用复刻音色合成很短的文本（例如单个词语）时，前面会出现较长的静音或音频整体时长异常？
声音复刻模型会学习样本音频中的停顿与节奏，如果原始录音中包含较长的起始静音或停顿，合成结果也可能保留类似模式。对于单字或极短文本，这种静音比例会被放大，看起来像“音频很长但几乎都是静音”。建议在录制样本音频时避免长时间静音，合成时尽量使用完整句子或较长文本；如必须对单个词语进行合成，可在前后补充少量上下文或使用同音替换词以规避极端情况。

权限与认证
Q：使用子业务空间的API Key是否可以进行声音复刻？
需要为API Key对应的子业务空间进行模型授权后方才支持，详情请参见子业务空间的模型调用。