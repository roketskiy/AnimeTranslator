# AnimeTranslator 交互模式 TUI 化设计

日期: 2026-04-21
作者: OpenCode
范围: `main.py` 交互模式（命令行参数模式 `core_cli.py` 不受影响）

---

## 1. 目标

将 `main.py` 的文本数字输入交互改造为方向键选择 + 回车确认的 TUI 体验，并在启动时展示 ASCII block 像素风格的项目名称大字。

---

## 2. 非目标

- 不改 `core_cli.py` 的命令行参数模式。
- 不改 `core/` 翻译逻辑、`config.py`、字幕解析逻辑。
- 不引入 GUI 框架（Tkinter 仍仅用于文件浏览弹窗）。
- 不将自由文本输入（文件路径、输出路径）改为选择。

---

## 3. 依赖

新增唯一依赖：

```text
questionary>=2.0
```

基于 `prompt-toolkit`，Windows / macOS / Linux 原生兼容，在非 TTY 环境自动降级为文本输入。

同时更新 `requirements.txt`。

---

## 4. Banner 大字设计

替换 `print_banner()`，使用 ASCII block 字符拼成加宽字距的像素大字，并实现错位叠加的立体阴影效果：

- **实心层**：`ANIME` + `TRANS`，使用 `#d44020`（橙红，ANSI `38;2;212;64;32m`）+ `reset`
- **空心阴影层**：同字母，用 `░`（light shade）字符拼出，向右下方错位 1 个字符
- **叠加方式**：`print_banner()` 通过 `_merge_banner_line()` 逐字符合并两层——实心层字符优先覆盖阴影层，未被覆盖的阴影字符露出右下边缘，形成 3D 错位感
- **第三行**：普通等宽小字 `视频字幕翻译工具  v1.0`
- **Windows 兼容**：程序启动时通过 `ctypes` 启用 `ENABLE_VIRTUAL_TERMINAL_PROCESSING`，确保 Windows 终端正确解析 ANSI 颜色码

示例效果（概念，在实际支持 ANSI 的终端中显示为橙红实心 + 浅灰阴影）：

```
  ███░    █░  █░   █████░   █░  █░   █████░
 █░  █░   ██░ █░     █░     ██░██░   █░
 █████░   █░█░█░     █░     █░█░█░   ████░
 █░  █░   █░ ██░     █░     █░  █░   █░
 █░  █░   █░  █░   █████░   █░  █░   █████░

  █████░   ████░     ███░    █░  █░    ████░
    █░     █░  █░   █░  █░   ██░ █░   █░
    █░     ████░    █████░   █░█░█░    ███░
    █░     █░ █░    █░  █░   █░ ██░      █░
    █░     █░  █░   █░  █░   █░  █░   ████░

        视频字幕翻译工具  v1.0
```

---

## 5. 交互控件改造清单

| 交互点 | 原方式 | 新方式 |
|---|---|---|
| **主菜单** | 数字输入 `1/2/3/0` | `questionary.select()` 上下箭头 + 回车，选中项 `#d44020` |
| **字幕轨道选择** | 数字输入索引 | `questionary.select()` 上下箭头 + 回车，选中项 `#d44020` |
| **源语言** | 自由输入 `ja` | `questionary.select()`：English / 日本語，选中项 `#d44020` |
| **目标语言** | 自由输入 `zh` | **固定提示"目标语言：中文"，不可更改** |
| **是否保留原轨** | 输入 `y/n` | `questionary.confirm()` 回车确认（默认"是"），选中项 `#d44020` |
| **文件路径** | 输入 / GUI 浏览 | **保持不变** |
| **输出路径** | 自由输入 | **保持不变** |

**颜色配置**：通过 `questionary.Style([("selected", "fg:#d44020")])` 统一设置，`pointer` 保持默认不变，未选中项保持默认白色/灰色。

---

## 6. 内部映射

UI 显示 → 内部语言代码：

- `English` → `en`
- `日本語` → `ja`
- 目标语言固定为 `zh`

---

## 7. 交互流程（以 mode_file 为例）

```
[Banner 大字]
    ↓
questionary.select: 请选择模式
    - 翻译字幕文件 (.srt/.ass)
    - 翻译视频软字幕
    - 翻译视频硬字幕 (OCR)
    - 退出
    ↓
prompt_file: 选择字幕文件（输入路径或 Enter 浏览）
    ↓
questionary.select: 源语言
    - English
    - 日本語
    ↓
（提示：目标语言：中文）
    ↓
questionary.confirm: 输出原轨字幕?
    - 是 (默认高亮)
    - 否
    ↓
prompt_input: 输出文件路径 [默认路径]
    ↓
翻译进度条 (tqdm)
    ↓
完成提示
```

---

## 8. 边界与降级

- **TTY 降级**：`questionary` 在非交互环境（管道、重定向）自动降级为纯文本输入，程序不会崩溃。
- **异常处理**：保留现有的 `try/except KeyboardInterrupt` 和通用异常捕获。
- **取消行为**：用户在 `questionary` 中按 Ctrl+C 会抛出 `KeyboardInterrupt`，由外层捕获并返回上级菜单或退出。

---

## 9. 文件影响范围

- **`main.py`**：重写 `print_banner()`，改造 `interactive_loop()`、`mode_file()`、`mode_soft()`、`mode_hard()` 中的 prompt 逻辑，移除/替换 `prompt_choice()`、`prompt_yes_no()` 的实现（或保留为 wrapper 调用 `questionary`）。
- **`requirements.txt`**：新增 `questionary>=2.0`。
- **`core_cli.py`**：**无修改**。
- **`config.py`** / **`core/`**：**无修改**。

---

## 10. 验收标准

- [ ] 运行 `python main.py` 时，首屏展示 ASCII block 像素大字 Banner。
- [ ] 主菜单可用上下箭头选择，回车确认。
- [ ] 源语言为 English / 日本語 二选一。
- [ ] 目标语言固定显示为中文，无需选择。
- [ ] yes/no 确认可用方向键左右切换 + 回车，默认"是"。
- [ ] 命令行参数模式 `python main.py -- ...` 仍正常工作（`core_cli.py` 不受影响）。
- [ ] 在非 TTY 环境下，程序仍能运行（降级为文本输入）。
