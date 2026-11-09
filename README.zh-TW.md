# Spokecut

透過編輯逐字稿來剪輯講話影片。刪掉一個字，影片裡就沒有那個字。在你自己的電腦上執行，不用花錢。

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[線上展示](https://arthur031221.github.io/Spokecut/) | [安裝](docs/install.md) | [使用方式](docs/usage.md) | [設定](docs/config.md) | [架構](docs/architecture.md) | [效能測試](docs/benchmarks.md)

[English](README.md) | 繁體中文 | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

![Spokecut：剪掉停頓與贅詞、刪除一句話、跳過剪掉的部分播放成品、更換字幕樣式](assets/demo.gif)

一支 5 分鐘的講話影片，在 RTX 5090 上只要 15.0 秒就能轉成逐字稿、清理完畢並燒入字幕，是即時速度的 20.0 倍。這是從冷啟動開始的完整流程（`python bench/bench.py pipeline talk.mp4`，4 次平均，14.7 到 15.1 秒，`large-v3-turbo` 加 NVENC）。在 3 條執行緒的 Ryzen 5 7500F 上改用 `small` 和 x264，同一支影片需要 61.1 秒。

你的影片不會離開你的電腦。我寧可老實告訴你 Whisper 會把大部分的「嗯」「呃」藏起來，也不想假裝贅詞按鈕什麼都找得到。

## 前後對照

數字來自 80 秒的示範影片，也就是線上展示用的那一支，除非該列另有說明。

| 你想做的事 | 在時間軸剪輯軟體裡手動做 | Spokecut |
| --- | --- | --- |
| 剪掉 10 段超過 0.7 秒的停頓 | 用耳朵一段一段找，切開、波紋刪除，重複十次 | 按一下，或用 `--pauses 0.7 --no-fillers --no-repeats --model large-v3`。80.3 秒變成 73.4 秒 |
| 去掉一個「uh」和一個重複的字 | 來回拖動直到聽見 | 點那個字按 Delete，或用「贅詞」與「重複」按鈕 |
| 剪掉整句話 | 在波形上找它的起點和終點 | 選取文字按 Delete。切點會對齊字與字之間最安靜的位置 |
| 避免接點出現喀聲 | 每個切點加一個交叉淡化 | 每個接點都有 15 毫秒的淡化。在 300 秒的測試影片上，37 個接點裡有 3 個在沒有淡化時的取樣跳變超過一般值的 10 倍，加上淡化後一個都沒有 |
| 取得字幕 | 先在別處轉錄，匯入 SRT，每次剪輯後再重新對時間 | 字幕會跟著剪輯走。五種樣式可燒入畫面，也可匯出 SRT、VTT 和 ASS |
| 把剪輯帶到別的軟體 | 手動重做一遍 | 輸出保留片段的 EDL、FCPXML 和 OTIO |
| 示範影片的結果 |  | 80.3 秒變成 72.1 秒，剪掉 8.2 秒，只要一行指令：`spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## 安裝

目前還沒上 PyPI，請從 GitHub 安裝。你還需要 Python 3.10 以上和 ffmpeg。

<details>
<summary>Linux（NVIDIA GPU 或 CPU）</summary>

```sh
sudo apt install ffmpeg pipx
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

只用 CPU 的話請拿掉 `[cuda]`。ffmpeg 能開啟 NVENC 時渲染用 NVENC，否則用 x264。

</details>

<details>
<summary>macOS（Apple Silicon 或 Intel）</summary>

```sh
brew install ffmpeg pipx
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

轉錄在 CPU 上執行，渲染用 x264。我沒有在 Mac 上跑過 Spokecut。

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

我沒有在 Windows 上跑過 Spokecut。CI 只涵蓋 Linux。

</details>

第一次轉錄會下載 Whisper 模型，`large-v3-turbo` 約 1.6 GB，`small` 464 MB。之後就不需要網路。

## 使用方式

```sh
spokecut talk.mp4
```

這會在瀏覽器裡開啟編輯器。點一個字按 Delete 就剪掉它，拖曳可剪掉一段話，點灰色小標籤可剪掉停頓，在字上按 Enter 可修改字幕。按 Ctrl+F 可尋找字詞或片語，一次剪掉所有符合的地方。播放時會跳過你剪掉的部分。剪輯結果存在影片旁邊的 `talk.mp4.spokecut.json`，影片本身不會被改動。說話語言、模型和保留嗯呃的選項在「轉錄選項」裡，語言偵測錯了可以按「重新轉錄」。

常見的情況不需要瀏覽器：

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut clean *.mp4 --pauses 0.7
spokecut export talk.mp4 --format fcpxml
```

鍵盤快速鍵與所有格式請見[使用方式](docs/usage.md)，旗標請見[設定](docs/config.md)。

## 關於贅詞，說實話

一般的 Whisper 會把大部分「嗯」「呃」從逐字稿裡拿掉，所以贅詞按鈕能找到的不多。在示範影片上 `large-v3` 留下 2 個贅詞。`--verbatim` 會改用 CrisperWhisper，它會保留這些詞，同一支影片找到 4 個。它的授權是 CC BY-NC 4.0，僅限非商業使用。停頓和緊接著的重複字，每個模型都能處理。

## 它做不到的事

- 每個檔案一位說話者，不會分辨不同的聲音。
- 它只負責剪輯和字幕。沒有多軌時間軸、沒有螢幕錄影，也沒有聲音複製。
- 我在測試裡用 OpenTimelineIO 轉接器把 EDL、FCPXML 和 OTIO 讀回來檢查。我沒有把它們匯入 Resolve 或 Premiere 試過，而且 OTIO 只有視訊軌。
- 線上展示無法轉錄你自己的影片，也不能渲染 MP4，這些需要 Python 端。
- 字幕字型來自你的系統。我只在裝有 Noto CJK 的環境檢查過燒入的中文。沒有對應語言的字型，文字就無法正確顯示。

## 運作方式

Spokecut 先解碼音訊，用 faster-whisper 取得每個字的時間戳，再找出每對字之間最安靜的位置，讓切點落在靜音裡。你的剪輯只是一個小小的狀態物件，記錄刪除的字、剪掉的停頓和字幕設定。所有輸出都由文字和這個狀態算出來，渲染則變成一個 ffmpeg 濾鏡圖，剪裁精確到影格。編輯器是沒有建置步驟的純 ES 模組，支援九種語言。細節請見[架構](docs/architecture.md)，每個數字背後的方法請見[效能測試](docs/benchmarks.md)。

## 參與貢獻

附上能重現問題的短影片，是最有幫助的回報。請見 [CONTRIBUTING](CONTRIBUTING.md)。

## 授權

MIT，見 [LICENSE](LICENSE)。示範影片節錄自 Vgrigas 的 "Ward Cunningham, Inventor of the Wiki"，採 CC BY-SA 3.0，見 [web/demo/NOTICE](web/demo/NOTICE)。

Assisted by Claude/Codex.
