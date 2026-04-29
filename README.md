# AnimeTranslator

使用 LLM 将动漫字幕翻译为中文。支持字幕文件、视频软字幕、视频硬字幕(OCR)三种模式。

## 功能

- **字幕文件翻译** — 直接翻译 `.srt` / `.ass` 字幕文件
- **视频软字幕翻译** — 提取视频内嵌字幕轨道并翻译
- **视频硬字幕翻译** — OCR 识别烧录在画面中的字幕并翻译（基于 PaddleOCR）
- **并发翻译** — 多批次并发请求，加速翻译（可配置并发数）
- **上下文感知** — 翻译时携带前后文字幕作为上下文，提升连贯性
- **双语输出** — 可选择输出原文 + 译文双语字幕
- **TUI / CLI 双入口** — 交互式终端界面 + 命令行模式

## 安装

```bash
# 克隆项目
git clone https://github.com/roketskiy/AnimeTranslator.git
cd AnimeTranslator

# 安装依赖
pip install -r requirements.txt

# 安装 PaddleOCR（硬字幕模式需要）
# pip install paddleocr paddlepaddle
```

## 配置

在项目根目录创建 `.env` 文件并设置 API Key：

```env
OPENROUTER_API_KEY=your_openrouter_api_key
```

`config.py` 中的可调参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TRANSLATE_BATCH_SIZE` | 30 | 每批翻译字幕条数 |
| `TRANSLATE_MAX_CONCURRENT` | 5 | 最大并发请求数 |
| `TRANSLATE_CONTEXT_SIZE` | 2 | 上下文窗口大小 |
| `TRANSLATE_RETRY_TIMES` | 3 | API 调用失败重试次数 |
| `API_MODEL` | openai/gpt-oss-120b:free | 使用的 LLM 模型 |

## 使用方式

### 交互式 TUI

```bash
python main.py
```

方向键选择模式，支持三种翻译模式。

### 命令行 CLI

```bash
# 翻译字幕文件
python core_cli.py file -i input.srt --src ja --dst zh

# 翻译视频软字幕
python core_cli.py soft -i video.mkv --src ja --dst zh

# 翻译视频硬字幕 (OCR)
python core_cli.py hard -i video.mp4 --src ja --dst zh
```

## 项目结构

```
AnimeTranslator/
├── config.py              # 全局配置
├── main.py                # 交互式 TUI 入口
├── core_cli.py            # CLI 命令行入口
├── core/                  # 核心逻辑
│   ├── translator.py      # 翻译引擎（并发 API 调用）
│   ├── subtitle_parser.py # 字幕解析 (SRT/ASS)
│   ├── srt_generator.py   # SRT 文件生成
│   ├── soft_subtitle.py   # 软字幕提取 (ffmpeg)
│   └── hard_subtitle.py   # 硬字幕 OCR 提取 (PaddleOCR)
├── utils/                 # 工具模块
│   ├── progress.py        # 自定义进度条
│   ├── preprocess.py      # 图像预处理
│   └── video.py           # 视频帧采样
└── docs/                  # 文档
    └── superpowers/specs/ # 设计文档
```

## 依赖

- `requests` — HTTP API 调用
- `click` — CLI 框架
- `pysrt` / `pysubs2` — 字幕解析
- `tqdm` — 进度条
- `questionary` — 交互式终端 UI
- `paddleocr` / `paddlepaddle` — 硬字幕 OCR（可选）
- `opencv-python` — 图像处理（可选）

## License

MIT
