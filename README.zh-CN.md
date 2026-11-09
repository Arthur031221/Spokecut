# Spokecut

通过编辑逐字稿来剪辑讲话视频。删掉一个字，视频里就没有那个字。在你自己的电脑上运行，不用花钱。

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[在线演示](https://arthur031221.github.io/Spokecut/) | [安装](docs/install.md) | [使用方法](docs/usage.md) | [配置](docs/config.md) | [架构](docs/architecture.md) | [性能测试](docs/benchmarks.md)

[English](README.md) | [繁體中文](README.zh-TW.md) | 简体中文 | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

![Spokecut：剪掉停顿和赘词、删除一句话、跳过剪掉的部分播放成品、更换字幕样式](assets/demo.gif)

一段 5 分钟的讲话视频，在 RTX 5090 上只需 15.0 秒就能转成逐字稿、清理完毕并烧录字幕，是实时速度的 20.0 倍。这是从冷启动开始的完整流程（`python bench/bench.py pipeline talk.mp4`，4 次平均，14.7 到 15.1 秒，`large-v3-turbo` 加 NVENC）。在 3 个线程的 Ryzen 5 7500F 上改用 `small` 和 x264，同一段视频需要 61.1 秒。

你的视频不会离开你的电脑。我宁可老实告诉你 Whisper 会把大部分的"嗯""呃"藏起来，也不想假装赘词按钮什么都找得到。

## 前后对比

数字来自 80 秒的演示视频，也就是在线演示用的那一段，除非该行另有说明。

| 你想做的事 | 在时间线剪辑软件里手动做 | Spokecut |
| --- | --- | --- |
| 剪掉 10 段超过 0.7 秒的停顿 | 用耳朵一段一段找，切开、波纹删除，重复十次 | 点一下，或用 `--pauses 0.7 --no-fillers --no-repeats --model large-v3`。80.3 秒变成 73.4 秒 |
| 去掉一个"uh"和一个重复的字 | 来回拖动直到听见 | 点那个字按 Delete，或用"赘词"和"重复"按钮 |
| 剪掉整句话 | 在波形上找它的起点和终点 | 选中文字按 Delete。切点会对齐字与字之间最安静的位置 |
| 避免接点出现咔声 | 每个切点加一个交叉淡化 | 每个接点都有 15 毫秒的淡化。在 300 秒的测试视频上，37 个接点里有 3 个在没有淡化时的采样跳变超过一般值的 10 倍，加上淡化后一个都没有 |
| 获得字幕 | 先在别处转录，导入 SRT，每次剪辑后再重新对时间 | 字幕会跟着剪辑走。五种样式可烧录进画面，也可导出 SRT、VTT 和 ASS |
| 把剪辑带到别的软件 | 手动重做一遍 | 输出保留片段的 EDL、FCPXML 和 OTIO |
| 演示视频的结果 |  | 80.3 秒变成 72.1 秒，剪掉 8.2 秒，只要一行命令：`spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## 安装

目前还没上 PyPI，请从 GitHub 安装。你还需要 Python 3.10 以上和 ffmpeg。

<details>
<summary>Linux（NVIDIA GPU 或 CPU）</summary>

```sh
sudo apt install ffmpeg pipx
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

只用 CPU 的话请去掉 `[cuda]`。ffmpeg 能打开 NVENC 时渲染用 NVENC，否则用 x264。

</details>

<details>
<summary>macOS（Apple Silicon 或 Intel）</summary>

```sh
brew install ffmpeg pipx
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

转录在 CPU 上运行，渲染用 x264。我自己没有在 Mac 上用过 Spokecut。CI 会在 macOS 上运行测试，包括渲染。烧录字幕需要带 libass 的 ffmpeg，没有的话 Spokecut 会提示。

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

我自己没有在 Windows 上用过 Spokecut。CI 会在 Windows 上运行测试，包括渲染。

</details>

第一次转录会下载 Whisper 模型，`large-v3-turbo` 约 1.6 GB，`small` 464 MB。之后就不需要网络。

## 使用方法

```sh
spokecut talk.mp4
```

这会在浏览器里打开编辑器。点一个字按 Delete 就剪掉它，拖动可剪掉一段话，点灰色小标签可剪掉停顿，在字上按 Enter 可修改字幕。按 Ctrl+F 可查找字词或短语，一次剪掉所有匹配的地方。播放时会跳过你剪掉的部分。剪辑结果保存在视频旁边的 `talk.mp4.spokecut.json`，视频本身不会被改动。说话语言、模型和保留嗯呃的选项在「转录选项」里，语言检测错了可以点「重新转录」。

常见的情况不需要浏览器：

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut clean *.mp4 --pauses 0.7
spokecut export talk.mp4 --format fcpxml
```

键盘快捷键和所有格式请见[使用方法](docs/usage.md)，参数请见[配置](docs/config.md)。

## 关于赘词，说实话

普通的 Whisper 会把大部分"嗯""呃"从逐字稿里去掉，所以赘词按钮能找到的不多。在演示视频上 `large-v3` 留下 2 个赘词。`--verbatim` 会改用 CrisperWhisper，它会保留这些词，同一段视频找到 4 个。它的许可证是 CC BY-NC 4.0，仅限非商业使用。停顿和紧接着的重复字，每个模型都能处理。

## 它做不到的事

- 每个文件一位说话者，不会区分不同的声音。
- 它只负责剪辑和字幕。没有多轨时间线、没有屏幕录制，也没有声音克隆。
- 我在测试里用 OpenTimelineIO 适配器把 EDL、FCPXML 和 OTIO 读回来检查。我没有把它们导入 Resolve 或 Premiere 试过，而且 OTIO 只有视频轨。
- 在线演示无法转录你自己的视频，也不能渲染 MP4，这些需要 Python 端。
- 字幕字体来自你的系统。我只在装有 Noto CJK 的环境检查过烧录的中文。没有对应语言的字体，文字就无法正确显示。

## 工作方式

Spokecut 先解码音频，用 faster-whisper 得到每个字的时间戳，再找出每对字之间最安静的位置，让切点落在静音里。你的剪辑只是一个小小的状态对象，记录删除的字、剪掉的停顿和字幕设置。所有输出都由文字和这个状态算出来，渲染则变成一个 ffmpeg 滤镜图，剪切精确到帧。编辑器是没有构建步骤的纯 ES 模块，支持九种语言。细节请见[架构](docs/architecture.md)，每个数字背后的方法请见[性能测试](docs/benchmarks.md)。

## 参与贡献

附上能复现问题的短视频，是最有帮助的反馈。请见 [CONTRIBUTING](CONTRIBUTING.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。演示视频节选自 Vgrigas 的 "Ward Cunningham, Inventor of the Wiki"，采用 CC BY-SA 3.0，见 [web/demo/NOTICE](web/demo/NOTICE)。

Assisted by Claude/Codex.
