# 豆包语音合成 - 单向流式API文档

## 1 接口功能

单向流式API为用户提供文本转语音的能力，支持多语种、多方言，同时支持http协议流式输出。

### 1.1 最佳实践

* 客户端读取服务端流式返回的json数据，从中取出对应的音频数据；
* 音频数据返回的是base64格式，需要解析后拼接到字节数组即可组装音频进行播放；
* 可以使用对应编程语言的连接复用组件，避免重复建立tcp连接（火山服务端keep-alive时间为1分钟），例如python的session组件：

```python
session = requests.Session()
response = session.post(url, headers=headers, json=payload, stream=True)
```

## 2 接口说明

### 2.1 请求Request

#### 请求路径

* 服务对应的请求路径：`https://openspeech.bytedance.com/api/v3/tts/unidirectional`

#### Request Headers

| Key | 说明 | 是否必须 | Value示例 |
|---|---|---|---|
| X-Api-App-Id | 使用火山引擎控制台获取的APP ID | 是 | 123456789 |
| X-Api-Access-Key | 使用火山引擎控制台获取的Access Token | 是 | your-access-key |
| X-Api-Resource-Id | 表示调用服务的资源信息 ID<br>• 豆包语音合成模型1.0：<br>  - seed-tts-1.0 或者 volc.service_type.10029（字符版）<br>  - seed-tts-1.0-concurr 或者 volc.service_type.10048（并发版）<br>• 豆包语音合成模型2.0:<br>  - seed-tts-2.0 (字符版)<br>• 声音复刻：<br>  - seed-icl-1.0（声音复刻1.0字符版）<br>  - seed-icl-1.0-concurr（声音复刻1.0并发版）<br>  - seed-icl-2.0 (声音复刻2.0字符版) | 是 | seed-tts-2.0 |
| X-Api-Request-Id | 标识客户端请求ID，uuid随机字符串 | 否 | 67ee89ba-7050-4c04-a3d7-ac61a63499b3 |
| X-Control-Require-Usage-Tokens-Return | 请求消耗的用量返回控制标记 | 否 | * 或 text_words |

#### Response Headers

| Key | 说明 | Value示例 |
|---|---|---|
| X-Tt-Logid | 服务端返回的 logid，建议用户获取和打印方便定位问题 | 2025041513355271DF5CF1A0AE0508E78C |

### 2.2 请求Body

#### 核心参数

| 字段 | 描述 | 是否必须 | 类型 | 默认值 |
|---|---|---|---|---|
| user.uid | 用户uid | 否 | string | - |
| namespace | 请求方法 | 否 | string | BidirectionalTTS |
| req_params.text | 输入文本 | 是 | string | - |
| req_params.speaker | 发音人，具体见发音人列表 | 是 | string | - |
| req_params.model | 模型版本，传`seed-tts-1.1`较默认版本音质有提升 | 否 | string | - |
| req_params.ssml | SSML格式文本（TTS 2.0暂不支持） | 否 | string | - |

#### 音频参数 (req_params.audio_params)

| 字段 | 描述 | 类型 | 默认值 |
|---|---|---|---|
| format | 音频编码格式：mp3/ogg_opus/pcm | string | mp3 |
| sample_rate | 音频采样率：[8000,16000,22050,24000,32000,44100,48000] | number | 24000 |
| bit_rate | 音频比特率，默认范围64k～160k | number | - |
| emotion | 设置音色的情感（仅部分音色支持） | string | - |
| emotion_scale | 情绪值，范围1~5 | number | 4 |
| speech_rate | 语速，取值范围[-50,100] | number | 0 |
| loudness_rate | 音量，取值范围[-50,100] | number | 0 |
| enable_timestamp | 返回句级别字的时间戳（仅TTS1.0支持） | bool | false |

#### 高级参数 (req_params.additions)

| 字段 | 描述 | 类型 | 默认值 |
|---|---|---|---|
| silence_duration | 句尾增加静音时长，范围0~30000ms | number | 0 |
| enable_language_detector | 自动识别语种 | bool | false |
| disable_markdown_filter | 是否开启markdown解析过滤 | bool | false |
| disable_emoji_filter | emoji表情在文本中不过滤显示 | bool | false |
| enable_latex_tn | 是否可以播报latex公式 | bool | false |
| explicit_language | 明确语种：zh-cn/en/ja/es-mx/id/pt-br等 | string | - |
| context_language | 参考语种 | string | - |
| unsupported_char_ratio_thresh | 不支持文本比例阈值 | float | 0.3 |
| aigc_watermark | 是否在合成结尾增加音频节奏标识 | bool | false |
| post_process.pitch | 音调取值范围[-12,12] | int | 0 |
| context_texts | 语音合成的辅助信息（仅TTS2.0支持） | string list | null |

#### 缓存参数 (req_params.additions.cache_config)

| 字段 | 描述 | 类型 |
|---|---|---|
| text_type | 开启缓存时传1 | int |
| use_cache | 开启缓存时传true | bool |

#### Mix混音参数 (req_params.mix_speaker)

| 字段 | 描述 |
|---|---|
| speakers | 混音音色名以及影响因子列表（最多3个音色） |
| speakers[i].source_speaker | 混音源音色名 |
| speakers[i].mix_factor | 混音源音色名影响因子（总和=1） |

### 2.3 响应Response

#### 音频响应数据

```json
{
    "code": 0,
    "message": "",
    "data": "{{BASE64_AUDIO_DATA}}"
}
```

#### 文本响应数据（包含时间戳）

```json
{
    "code": 0,
    "message": "",
    "data": null,
    "sentence": {
        "text": "其他人。",
        "words": [
            {
                "confidence": 0.8531248,
                "endTime": 0.315,
                "startTime": 0.205,
                "word": "其"
            }
        ]
    }
}
```

#### 合成结束响应

```json
{
    "code": 20000000,
    "message": "ok",
    "data": null,
    "usage": {"text_words": 10}
}
```

## 3 错误码

| Code | Message | 说明 |
|---|---|---|
| 20000000 | ok | 音频合成结束的成功状态码 |
| 40402003 | TTSExceededTextLimit:exceed max limit | 提交文本长度超过限制 |
| 45000000 | speaker permission denied / quota exceeded | 音色鉴权失败或并发限流 |
| 55000000 | 服务端一些error | 服务端通用错误 |

## 4 请求示例

### 单音色请求

```json
{
    "user": {
        "uid": "12345"
    },
    "req_params": {
        "text": "明朝开国皇帝朱元璋也称这本书为,万物之根",
        "speaker": "zh_female_shuangkuaisisi_moon_bigtts",
        "audio_params": {
            "format": "mp3",
            "sample_rate": 24000
        }
    }
}
```

### Mix混音请求

```json
{
    "user": {
        "uid": "12345"
    },
    "req_params": {
        "text": "明朝开国皇帝朱元璋也称这本书为万物之根",
        "speaker": "custom_mix_bigtts",
        "audio_params": {
            "format": "mp3",
            "sample_rate": 24000
        },
        "mix_speaker": {
            "speakers": [
                {
                    "source_speaker": "zh_male_bvlazysheep",
                    "mix_factor": 0.3
                },
                {
                    "source_speaker": "BV120_streaming",
                    "mix_factor": 0.3
                },
                {
                    "source_speaker": "zh_male_ahu_conversation_wvae_bigtts",
                    "mix_factor": 0.4
                }
            ]
        }
    }
}
```

## 5 稳定性最佳实践

### 5.1 确保语音稳定的关键参数

为了在多次使用中获得稳定的语音效果，建议配置以下参数：

1. **固定音频参数**
   ```json
   "audio_params": {
       "format": "mp3",
       "sample_rate": 24000,
       "speech_rate": 0,
       "loudness_rate": 0
   }
   ```

2. **使用缓存（相同文本）**
   ```json
   "additions": {
       "cache_config": {
           "text_type": 1,
           "use_cache": true
       }
   }
   ```

3. **固定用户ID**
   ```json
   "user": {
       "uid": "auto_podcast"
   }
   ```

4. **明确语种（TTS 2.0）**
   ```json
   "additions": {
       "explicit_language": "zh-cn"
   }
   ```

5. **使用Session连接复用**
   ```python
   session = requests.Session()
   response = session.post(url, headers=headers, json=payload, stream=True)
   ```

### 5.2 TTS 2.0 特殊参数

对于TTS 2.0音色，可以使用`context_texts`来控制语音风格：

```json
"additions": {
    "context_texts": ["请用平稳自然的语气说话"]
}
```

常见用法：
- 语速调整：`["你可以说慢一点吗？"]`
- 情绪调整：`["请用平稳的语气说话"]`
- 音量调整：`["你嗓门再小点。"]`

### 5.3 避免的问题

1. **不要频繁更改采样率和格式**
2. **避免使用过高的emotion_scale值**（建议3-4）
3. **不要在生产环境使用随机的uid**
4. **建议使用固定的X-Api-Request-Id格式**（如UUID v4）
