# Spokecut

文字起こしを編集して、話している動画を編集します。単語を消せば、動画からもその単語が消えます。自分のマシンで動き、無料です。

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[ライブデモ](https://arthur031221.github.io/Spokecut/) | [インストール](docs/install.md) | [使い方](docs/usage.md) | [設定](docs/config.md) | [アーキテクチャ](docs/architecture.md) | [ベンチマーク](docs/benchmarks.md)

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | 日本語 | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

![Spokecut：間とフィラーを切り、1文を削除し、カット部分を飛ばして再生し、字幕のスタイルを変える](assets/demo.gif)

5分の話し動画を、文字起こし、整理、字幕の焼き込みまで含めて RTX 5090 で 15.0 秒で処理します。実時間の 20.0 倍です。コールドスタートからの全工程の値です（`python bench/bench.py pipeline talk.mp4`、4回の平均、14.7〜15.1 秒、`large-v3-turbo` と NVENC）。3スレッドの Ryzen 5 7500F で `small` と x264 を使うと、同じ動画に 61.1 秒かかります。

動画があなたのマシンの外に出ることはありません。フィラーボタンがすべて見つけると言い張るより、Whisper が「えー」や「あのー」の大半を消してしまうと正直にお伝えします。

## ビフォーアフター

数値は 80 秒のデモクリップのものです。ライブデモと同じクリップです。行に別の記載がある場合を除きます。

| やりたいこと | タイムラインエディタで手作業 | Spokecut |
| --- | --- | --- |
| 0.7 秒を超える間を 10 か所カットする | 耳で探して、分割して、リップル削除を 10 回繰り返す | ワンクリック、または `--pauses 0.7 --no-fillers --no-repeats --model large-v3`。80.3 秒が 73.4 秒になります |
| 「uh」と繰り返された単語を取り除く | 聞こえるまでスクラブする | 単語をクリックして Delete、または「フィラー」と「繰り返し」ボタンを使います |
| 1文まるごとカットする | 波形で始まりと終わりを探す | 単語を選んで Delete。カット位置は単語間でいちばん静かな点に合わせます |
| つなぎ目のクリック音を避ける | カットごとにクロスフェードを入れる | すべてのつなぎ目に 15 ms のフェードが入ります。300 秒のベンチマーククリップでは、フェードなしだと 37 か所中 3 か所でサンプルの変化が通常の 10 倍を超え、フェードありでは 0 か所でした |
| 字幕をつける | 別のツールで文字起こしして SRT を読み込み、カットのたびに時間を合わせ直す | 字幕は編集に追従します。5 種類のスタイルを焼き込めるほか、SRT、VTT、ASS も書き出せます |
| 編集を別のエディタに持っていく | 手作業で作り直す | 残した範囲の EDL、FCPXML、OTIO を書き出します |
| デモクリップでの結果 |  | 80.3 秒から 72.1 秒へ、8.2 秒を削除。コマンドは 1 つです：`spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## インストール

まだ PyPI にはないので、GitHub からインストールしてください。Python 3.10 以降と ffmpeg も必要です。

<details>
<summary>Linux（NVIDIA GPU または CPU）</summary>

```sh
sudo apt install ffmpeg pipx
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

CPU のみで使うなら `[cuda]` を外してください。ffmpeg が NVENC を開ける場合はレンダリングに NVENC を使い、開けない場合は x264 を使います。

</details>

<details>
<summary>macOS（Apple Silicon または Intel）</summary>

```sh
brew install ffmpeg pipx
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

文字起こしは CPU で動き、レンダリングは x264 です。Mac では Spokecut を実行していません。

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

Windows では Spokecut を実行していません。CI は Linux だけです。

</details>

最初の文字起こしで Whisper のモデルをダウンロードします。`large-v3-turbo` は約 1.6 GB、`small` は 464 MB です。その後はネットワークを必要としません。

## 使い方

```sh
spokecut talk.mp4
```

ブラウザでエディタが開きます。単語をクリックして Delete で削除し、ドラッグで一節を削除し、灰色のチップをクリックして間をカットし、単語で Enter を押して字幕を直します。Ctrl+F で単語やフレーズを検索し、一致した箇所をまとめてカットできます。再生ではカットした部分を飛ばします。編集内容は動画の隣に `talk.mp4.spokecut.json` として保存され、動画そのものは変更されません。話している言語、モデル、えーと等を残すかどうかは「文字起こしのオプション」にあり、言語の判定が違ったときは「もう一度文字起こし」で直せます。

よくある使い方ならブラウザは不要です：

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut clean *.mp4 --pauses 0.7
spokecut export talk.mp4 --format fcpxml
```

キーボードショートカットと全フォーマットは[使い方](docs/usage.md)、オプションは[設定](docs/config.md)を見てください。

## フィラーについて、正直に

標準の Whisper は「えー」や「あのー」の大半を文字起こしから落とすので、フィラーボタンが見つけられるものは多くありません。デモクリップでは `large-v3` が残したフィラーは 2 個でした。`--verbatim` は CrisperWhisper に切り替えます。これはフィラーを残し、同じクリップで 4 個見つけました。ライセンスは CC BY-NC 4.0 で、非商用に限られます。間と直前の繰り返しは、どのモデルでも使えます。

## できないこと

- 1 ファイルにつき話者は 1 人です。声の分離はしません。
- カットと字幕だけです。マルチトラックのタイムライン、画面録画、音声のクローンはありません。
- EDL、FCPXML、OTIO は、テストで OpenTimelineIO のアダプタを通して読み戻して確認しています。Resolve や Premiere には取り込んでいません。OTIO はビデオトラックのみです。
- ライブデモでは自分の動画の文字起こしも MP4 のレンダリングもできません。Python 側が必要です。
- 字幕のフォントはシステムのものを使います。焼き込んだ中国語は Noto CJK を入れた環境で確認しました。お使いの言語のフォントがないと、文字は正しく描画されません。

## 仕組み

Spokecut は音声をデコードし、faster-whisper で単語ごとのタイムスタンプを取り、単語の組ごとにいちばん静かな点を探して、カットが無音に落ちるようにします。編集は、削除した単語、カットした間、字幕設定をもつ小さな状態オブジェクトです。すべての出力は単語とこの状態から計算され、レンダリングはフレーム単位で正確なトリムを持つ 1 本の ffmpeg フィルタグラフになります。エディタはビルド手順のない素の ES モジュールで、9 言語に対応しています。詳細は[アーキテクチャ](docs/architecture.md)、各数値の測定方法は[ベンチマーク](docs/benchmarks.md)にあります。

## コントリビュート

問題を再現できる短い動画付きのバグ報告がいちばん助かります。[CONTRIBUTING](CONTRIBUTING.md) を見てください。

## ライセンス

MIT です。[LICENSE](LICENSE) を見てください。デモクリップは Vgrigas の "Ward Cunningham, Inventor of the Wiki" の抜粋で、CC BY-SA 3.0 です。[web/demo/NOTICE](web/demo/NOTICE) を見てください。

Assisted by Claude/Codex.
