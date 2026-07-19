# chengfeng-videocut-skills

> 给 Codex / Claude Code 使用的视频剪辑与纪录片创作 Skills 包。

这个仓库保留 chengfeng 原始视频剪辑工作流，并在当前分支增加酸梅纪录片系统的原创 `纪录片分镜` Skill。

## 来源与扩展

视频剪辑基础 Skills 由 **chengfeng / AI产品自由** 原创并维护。

原始仓库：

```text
https://github.com/Agentchengfeng/chengfeng-videocut-skills
```

当前仓库新增：

```text
chengfeng-videocut-skills:纪录片分镜
```

该 Skill 由 **isuanmei / 酸梅纪录片系统** 整理和维护，用于纪录片旁白、口述史、人物回忆和纪实故事的 AI 分镜生产。

使用、转载、翻译、二次发布或改造本项目时，请保留原作者、原始仓库链接、`LICENSE` 和 `NOTICE.md`。

## 安装当前扩展版

安装到 Codex 和 Claude Code：

```bash
npx chengfeng-videocut-skills install \
  --repo https://github.com/isuanmei/chengfeng-videocut-skills.git
```

只安装到 Codex：

```bash
npx chengfeng-videocut-skills install \
  --target codex \
  --repo https://github.com/isuanmei/chengfeng-videocut-skills.git
```

只安装到 Claude Code：

```bash
npx chengfeng-videocut-skills install \
  --target claude \
  --repo https://github.com/isuanmei/chengfeng-videocut-skills.git
```

默认安装目录：

```text
~/.claude/skills/chengfeng-videocut-skills
~/.codex/skills/chengfeng-videocut-skills
```

克隆仓库后也可以直接运行安装器：

```bash
git clone https://github.com/isuanmei/chengfeng-videocut-skills.git
cd chengfeng-videocut-skills
node bin/cli.js install --target codex
```

## 最短使用方式

### 纪录片分镜

```text
用 chengfeng-videocut-skills:纪录片分镜，把下面这段旁白做成约 60 个镜头的分镜表。
画面用于即梦和可灵生成，保持酸梅纪录片风格。

故事正文：
……
```

详细说明：

```text
纪录片分镜/README.md
```

### 准备口播素材

```text
用 chengfeng-videocut-skills:剪口播，把这条录屏处理成后面口播成片要用的基础素材包。
```

### 制作口播成片

```text
用 chengfeng-videocut-skills:口播成片，把这个文件夹里的视频和字幕做成 1080x1440 竖屏 MP4。
先生成分镜页面给我确认，不要直接导出。
```

## Skill 清单

| Skill | 作用 | 常见输入 | 常见输出 |
| --- | --- | --- | --- |
| `chengfeng-videocut-skills:安装` | 准备 Node.js、FFmpeg、API Key 等环境 | 无 | 环境检查结果 |
| `chengfeng-videocut-skills:剪口播` | 口播粗剪、重转写和字幕校对 | 原始录屏、口播视频 | 剪后视频、字幕、审核页 |
| `chengfeng-videocut-skills:口播成片` | 生成分镜页面、时间线预览和最终竖屏 MP4 | 剪后视频、字幕、素材 | 分镜页、预览页、MP4 |
| `chengfeng-videocut-skills:纪录片分镜` | 把纪录片旁白拆成约 60 镜，并生成即梦、可灵提示词 | 旁白、口述史、人物故事 | 8 列 Markdown 分镜表 |
| `chengfeng-videocut-skills:自进化` | 把使用偏好沉淀回规则 | 用户反馈 | 更新后的规则 |

## 纪录片分镜工作流

```text
故事正文
  |
  v
梳理时间线、人物关系和情绪转折
  |
  v
拆成约 60 个镜头
  |
  v
生成静态画面提示词和动态提示词
  |
  v
检查人物连续性、旁白完整性和声音设计
  |
  v
即梦、可灵生成分镜图和视频
  |
  v
按镜头编号进入剪辑
```

核心特点：

- 真实、克制、观察式的纪录片重现
- 按叙事重量分配时长，不平均切分
- 静态提示词可以独立生成画面
- 动态提示词只使用简单的推、拉、摇、移
- 同一人物跨镜头保持年龄、外形、服装和道具连续
- 同期声、呼吸声、动作声和环境声优先
- 适配即梦和可灵的 5 至 15 秒镜头生产

## 口播视频工作流

```text
原始口播视频
  |
  v
剪口播
转录、识别口误、重复和静音，确认后剪出新视频
  |
  v
口播成片
按字幕拆分镜，判断每段画面来源，生成分镜页面
  |
  v
时间线预览
检查视频、截图、HTML 画面和动画的时间关系
  |
  v
最终导出
确认后合成 1080x1440 竖版 MP4
```

## 推荐口播项目结构

```text
project/
├── source_cut.mp4
├── subtitles.srt
└── assets/
    ├── 产品截图.png
    ├── 评论截图.png
    └── 结果页.png
```

## 环境配置

视频剪辑 Skills 的基础依赖：

| 依赖 | 用途 |
| --- | --- |
| Node.js 18+ | 运行安装器和脚本 |
| FFmpeg | 音视频处理 |
| curl | API 请求 |
| 火山引擎语音识别 API Key | 口播转录 |

纪录片分镜 Skill 只生成文本分镜表，不依赖 FFmpeg 和语音识别 API。

口播工具需要复制环境变量模板：

```bash
cd ~/.codex/skills/chengfeng-videocut-skills
cp .env.example .env
```

在 `.env` 中填写：

```text
VOLCENGINE_API_KEY=your_volcengine_api_key_here
```

## 仓库结构

```text
chengfeng-videocut-skills/
├── README.md
├── package.json
├── bin/
│   └── cli.js
├── 剪口播/
│   ├── SKILL.md
│   ├── scripts/
│   └── 用户习惯/
├── 口播成片/
│   ├── SKILL.md
│   ├── templates/
│   ├── references/
│   └── scripts/
├── 纪录片分镜/
│   ├── SKILL.md
│   ├── README.md
│   ├── examples/
│   │   └── 最短调用示例.md
│   └── references/
│       ├── 输出规范.md
│       └── 质量检查清单.md
└── 自进化/
    ├── SKILL.md
    └── README.md
```

## 本地运行产物

以下内容不应上传到 GitHub：

```text
.env
log/
memory/
output/
口播成片/agents/
*.mp4
*.mov
*.m4a
*.wav
*.zip
```

## npm 和 GitHub

npm 包提供安装命令，GitHub 保存 Skills 源码和文档。

当前扩展 Skill 尚未单独发布新的 npm 包，因此安装时要使用 `--repo` 指向当前仓库。更新 Skill 内容通常只需要推送 GitHub。

## 协议

本项目使用 Apache License 2.0。

重新分发或发布派生版本时，请保留 `LICENSE`、`NOTICE.md`、原作者和原始仓库信息。
