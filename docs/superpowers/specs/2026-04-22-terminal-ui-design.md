# AnimeTranslator Terminal UI 设计文档

**日期**: 2026-04-22  
**状态**: 已确认，待实现  
**作者**: AI Assistant

---

## 1. 目标

将现有的 `questionary` TUI 替换为 **Claude Code 风格**的终端界面：顶部标题栏 + 中间滚动内容区 + 底部动态菜单。使用 **Textual** 框架实现。

### 非目标
- 不改动现有的 `click` CLI（`core_cli.py`），保留供脚本和自动化使用
- 不改动核心翻译逻辑（`core/translator.py`、`core/subtitle_parser.py` 等）
- 不增加自然语言对话功能

---

## 2. 视觉风格

### 布局结构
三栏垂直分割：

```
+------------------------------------------+
| Header:  "> AnimeTranslator"   [当前状态] |
+------------------------------------------+
|                                          |
|  Content 区域                             |
|  - 显示交互历史（选择记录、进度、结果）     |
|  - 可滚动，带时间戳                       |
|  - 翻译时显示实时进度条                   |
|                                          |
+------------------------------------------+
|  [1] 翻译字幕文件  [2] 翻译软字幕 ...     |
|  > _                                     |
+------------------------------------------+
```

### 配色方案

| 元素 | 色值 | 用途 |
|------|------|------|
| 背景 | `#1e1e1e` | 全局背景 |
| 主强调 | `#d44020` | 选中项、进度条、品牌色 |
| 次要文字 | `#a0a0a0` | 辅助信息、时间戳 |
| 成功 | `#4caf50` | 翻译完成、成功提示 |
| 错误 | `#f44336` | 错误提示 |
| 边框 | `#333333` | 面板边框、分隔线 |

---

## 3. 状态机设计

### 状态定义

| 状态 | 说明 |
|------|------|
| `STATE_TOP` | 顶层菜单（选择三种翻译模式） |
| `STATE_FILE_SELECT` | 文件翻译：选择字幕文件（`.srt` / `.ass`） |
| `STATE_SOFT_SELECT` | 软字幕：选择视频文件 |
| `STATE_HARD_SELECT` | 硬字幕：选择视频文件 |
| `STATE_SRC_LANG` | 选择源语言（所有模式共用） |
| `STATE_TRACK_SELECT` | 软字幕：选择字幕轨道 |
| `STATE_OPTIONS` | 确认输出选项（保留原轨、输出路径等） |
| `STATE_TRANSLATING` | 翻译中（显示进度，锁定菜单） |
| `STATE_RESULT` | 翻译完成，显示结果和文件路径 |
| `STATE_ERROR` | 错误提示，可返回重试 |

### 状态转换示例（文件翻译模式）

```
STATE_TOP --[选择"翻译字幕文件"]--> STATE_FILE_SELECT
STATE_FILE_SELECT --[确认文件路径]--> STATE_SRC_LANG
STATE_SRC_LANG --[选择英语/日语]--> STATE_OPTIONS
STATE_OPTIONS --[开始翻译]--> STATE_TRANSLATING
STATE_TRANSLATING --[完成]--> STATE_RESULT
STATE_RESULT --[再来一次]--> STATE_FILE_SELECT
STATE_RESULT --[返回上级]--> STATE_TOP
```

### 通用转换规则

- 任意状态（除 `STATE_TOP`）按 `Esc` 可返回上一步
- `STATE_TRANSLATING` 按 `Esc` 发送取消信号
- `STATE_ERROR` 按 `Esc` 返回首页（`STATE_TOP`）

---

## 4. 组件架构

### 目录结构

```
ui/
├── terminal_app.py        # Textual App 主入口，状态机管理
├── screens/
│   └── main_screen.py     # 主界面布局（Header + Content + Menu + Input）
├── widgets/
│   ├── header.py          # 顶部标题栏（应用名 + 当前步骤）
│   ├── log_view.py        # 内容/历史显示区（滚动日志）
│   ├── menu_bar.py        # 底部动态菜单（按钮列表）
│   ├── file_browser.py    # 内置文件浏览器（DirectoryTree 封装）
│   └── progress_panel.py  # 翻译进度面板（进度条 + 统计）
└── styles.tcss            # Textual CSS 样式定义

core/
├── workflow.py            # 三种翻译模式的业务逻辑（TUI + CLI 共用）
├── subtitle_parser.py     # （现有，不变）
├── translator.py          # （现有，不变）
├── srt_generator.py       # （现有，不变）
├── soft_subtitle.py       # （现有，不变）
├── hard_subtitle.py       # （现有，不变）
└── __init__.py

main.py                    # 入口：有参数→CLI，无参数→TUI
core_cli.py                # click CLI（完全保留）
config.py                  # （现有，不变）
```

### 组件职责

| 组件 | 职责 | 依赖 |
|------|------|------|
| `AnimeTranslatorApp` | 应用入口、状态机驱动、全局事件路由 | Textual `App` |
| `MainScreen` | 三栏布局组合 | `Header`, `LogView`, `MenuBar`, `Input` |
| `Header` | 显示 `> AnimeTranslator` + 当前状态名 | 无 |
| `LogView` | 追加/滚动显示交互历史，支持时间戳 | `RichLog` |
| `MenuBar` | 根据状态动态渲染按钮，处理快捷键 | `Horizontal` + `Button` |
| `FileBrowser` | 目录树导航，过滤文件类型 | `DirectoryTree` |
| `ProgressPanel` | 实时进度条、批次统计、预计时间 | `ProgressBar` |

---

## 5. 文件选择机制

### 内置文件浏览器（默认）
- 使用 Textual `DirectoryTree` 或自建文件列表
- `↑/↓` 导航文件，`Enter` 进入文件夹或选中文件，`Backspace` 返回上级
- 只显示对应类型的文件（`.srt/.ass` 或 `.mp4/.mkv` 等）
- 底部菜单：`[Enter] 选择  [Tab] 输入路径  [Esc] 返回`

### 输入路径模式（按 `Tab` 切换）
- 显示 `Input` 输入框，支持直接输入绝对/相对路径
- 输入为空时按 `Enter` 唤起 `tkinter.filedialog`（保留现有逻辑，对不熟悉终端操作的用户友好）

### 文件选中后
- `LogView` 追加文件信息（路径、大小、格式）
- 自动进入下一步（`STATE_SRC_LANG`）

---

## 6. 翻译进度显示

### STATE_TRANSLATING 界面示例

```
+------------------------------------------+
| > AnimeTranslator    [翻译中...]          |
+------------------------------------------+
|                                          |
|  正在翻译: episode_01.srt                |
|  源语言: 日语 → 中文                     |
|                                          |
|  进度: 180 / 342 条字幕                  |
|  [████████████████░░░░░░░░░░░░] 52.6%    |
|  当前批次: 第 6 / 12 批                  |
|                                          |
|  预计剩余: 约 45 秒                      |
|                                          |
+------------------------------------------+
|  [Esc] 取消翻译                          |
+------------------------------------------+
```

### 进度更新机制
- 使用 Textual `Worker` 在后台线程执行翻译，避免阻塞 UI
- 通过 `post_message` 将进度事件传回主线程更新界面
- 批次完成时更新进度条和统计数字

### 取消翻译
- 按 `Esc` 发送取消信号（`Worker.cancel()` 或共享标志位）
- Worker 检查取消标志，在当前批次完成后优雅退出
- 已翻译的结果不保存，提示用户"翻译已取消"

---

## 7. 错误处理与恢复

### 错误分类

| 类型 | 示例 | 处理方式 |
|------|------|---------|
| 输入错误 | 文件不存在、格式不支持 | `LogView` 红色提示，停留在当前状态，可重试 |
| 配置错误 | API Key 未设置 | 进入 `STATE_ERROR`，显示修复指令，提供 `[1] 我已设置，重试` |
| 网络/翻译错误 | API 超时、速率限制 | 自动重试（复用 `config.TRANSLATE_RETRY_TIMES`），失败后提供 `[1] 重试 [2] 跳过本条 [3] 取消` |
| 未知异常 | 代码 Bug | 显示简略错误信息，`[1] 返回首页 [q] 退出`，同时写日志文件 |

### STATE_ERROR 界面示例

```
+------------------------------------------+
| > AnimeTranslator    [错误]               |
+------------------------------------------+
|                                          |
|  [错误] 未设置 TRANSLATE_API_KEY         |
|                                          |
|  请先设置环境变量后再试:                  |
|  set TRANSLATE_API_KEY=your_key          |
|                                          |
+------------------------------------------+
|  [1] 我已设置，重试    [Esc] 返回首页    |
+------------------------------------------+
```

---

## 8. 键盘交互

| 按键 | 全局行为 |
|------|---------|
| `↑/↓` 或 `Tab/Shift+Tab` | 在菜单按钮间切换焦点 |
| `Enter` | 确认当前选中项 |
| `Esc` | 返回上一步 / 取消 |
| `1-9` | 快速选择对应菜单项 |
| `q` | 退出应用（仅在 `STATE_TOP` 时） |
| `Tab` | 在文件浏览器和输入框间切换 |

---

## 9. 与现有 CLI 的集成

`main.py` 入口逻辑保持不变，内部调度调整：

```python
def main():
    if len(sys.argv) > 1:
        from core_cli import cli
        cli()
    else:
        from ui.terminal_app import AnimeTranslatorApp
        app = AnimeTranslatorApp()
        app.run()
```

### main.py 的改动
- 移除 `print_banner()`、`interactive_loop()`、所有 `prompt_*` 函数、`_LETTERS` 等 Banner 相关代码
- 移除 `mode_file()`、`mode_soft()`、`mode_hard()`、`do_translate()` 的业务逻辑
- 这些逻辑迁移到 `core/workflow.py`，供 TUI 和 CLI 共同调用

### core_cli.py 的处理
- 完全保留，不改动任何接口
- 底层翻译逻辑统一调用 `core/workflow.py` 中的函数，避免 TUI 和 CLI 各自维护两套翻译流程

---

## 10. 技术选型

| 技术 | 用途 | 版本要求 |
|------|------|---------|
| `textual` | TUI 框架 | `>=0.50.0` |
| `rich` | Textual 的底层依赖，用于样式和渲染 | 随 Textual 安装 |
| `click` | CLI 框架（现有） | 不变 |
| `questionary` | 旧 TUI（将被移除） | 移除 |

---

## 11. 测试策略

| 测试层级 | 内容 |
|---------|------|
| 单元测试 | `core/workflow.py` 的每个函数独立测试（使用 mock API 和临时文件） |
| 组件测试 | 每个 Textual widget 的独立测试（Textual 提供 `Pilot` 测试工具） |
| 集成测试 | 完整的翻译流程端到端测试（文件选择 → 参数设置 → 翻译 → 结果验证） |
| 手动测试 | 跨平台终端兼容性（Windows Terminal、iTerm2、GNOME Terminal） |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Textual 在 Windows 终端兼容性问题 | 高 | 早期在目标环境测试，保留 `tkinter.filedialog` 作为备用 |
| Worker 线程与 UI 状态同步复杂 | 中 | 统一使用 `post_message` 事件机制，避免直接操作 UI |
| 状态机逻辑膨胀 | 中 | 每个状态独立处理函数，避免嵌套条件；状态转换表集中维护 |
| 文件浏览器性能（大目录） | 低 | 使用 `DirectoryTree` 懒加载，或限制初始显示深度 |

---

## 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-22 | v1.0 | 初始设计确认 |
