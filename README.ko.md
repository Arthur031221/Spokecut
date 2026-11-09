# Spokecut

대본을 편집해서 말하는 영상을 편집합니다. 단어를 지우면 영상에서도 그 단어가 사라집니다. 내 컴퓨터에서 돌아가고 무료입니다.

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[라이브 데모](https://arthur031221.github.io/Spokecut/) | [설치](docs/install.md) | [사용법](docs/usage.md) | [설정](docs/config.md) | [아키텍처](docs/architecture.md) | [벤치마크](docs/benchmarks.md)

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | 한국어 | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

![Spokecut: 쉼과 군더더기 말을 자르고, 문장 하나를 지우고, 잘린 부분을 건너뛰며 재생하고, 자막 스타일을 바꿉니다](assets/demo.gif)

5분짜리 말하는 영상을 받아쓰기, 정리, 자막 입히기까지 RTX 5090에서 15.0초에 끝냅니다. 실시간의 20.0배입니다. 콜드 스타트부터 전체 작업을 잰 값입니다(`python bench/bench.py pipeline talk.mp4`, 4회 평균, 14.7~15.1초, `large-v3-turbo`와 NVENC). 스레드 3개의 Ryzen 5 7500F에서 `small`과 x264를 쓰면 같은 영상에 61.1초가 걸립니다.

영상은 내 컴퓨터 밖으로 나가지 않습니다. 군더더기 버튼이 전부 찾아낸다고 우기기보다, Whisper가 "음"과 "어"의 대부분을 없애 버린다고 솔직히 말씀드리겠습니다.

## 전과 후

숫자는 80초짜리 데모 클립에서 나온 것이고, 라이브 데모와 같은 클립입니다. 행에 따로 적은 경우는 예외입니다.

| 하고 싶은 일 | 타임라인 편집기에서 직접 하기 | Spokecut |
| --- | --- | --- |
| 0.7초보다 긴 쉼 10곳 자르기 | 귀로 찾고, 나누고, 리플 삭제를 열 번 반복 | 한 번 클릭하거나 `--pauses 0.7 --no-fillers --no-repeats --model large-v3`. 80.3초가 73.4초가 됩니다 |
| "uh"와 반복된 단어 없애기 | 들릴 때까지 앞뒤로 돌려 보기 | 단어를 클릭하고 Delete를 누르거나 군더더기와 반복 버튼을 사용 |
| 문장 하나 통째로 자르기 | 파형에서 시작과 끝을 찾기 | 단어를 선택하고 Delete. 자르는 위치는 단어 사이에서 가장 조용한 지점에 맞춰집니다 |
| 이음매의 딸깍 소리 피하기 | 컷마다 크로스페이드 넣기 | 모든 이음매에 15 ms 페이드가 있습니다. 300초 벤치마크 클립에서 페이드가 없으면 37곳 중 3곳의 샘플 변화가 보통의 10배를 넘었고, 페이드가 있으면 0곳이었습니다 |
| 자막 만들기 | 다른 곳에서 받아쓰고, SRT를 가져오고, 컷할 때마다 타이밍을 다시 맞추기 | 자막이 편집을 따라갑니다. 다섯 가지 스타일을 입힐 수 있고 SRT, VTT, ASS로도 내보낼 수 있습니다 |
| 편집 내용을 다른 편집기로 가져가기 | 손으로 다시 만들기 | 남긴 구간의 EDL, FCPXML, OTIO |
| 데모 클립의 결과 |  | 80.3초에서 72.1초로, 8.2초를 제거. 명령은 한 줄입니다: `spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## 설치

아직 PyPI에는 없으니 GitHub에서 설치하세요. Python 3.10 이상과 ffmpeg도 필요합니다.

<details>
<summary>Linux (NVIDIA GPU 또는 CPU)</summary>

```sh
sudo apt install ffmpeg
pip install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

CPU만 쓴다면 `[cuda]`를 빼세요. ffmpeg가 NVENC를 열 수 있으면 렌더링에 NVENC를 쓰고, 못 열면 x264를 씁니다.

</details>

<details>
<summary>macOS (Apple Silicon 또는 Intel)</summary>

```sh
brew install ffmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

받아쓰기는 CPU에서 돌고 렌더링은 x264를 씁니다. Mac에서는 Spokecut을 실행해 보지 않았습니다.

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

Windows에서는 Spokecut을 실행해 보지 않았습니다. CI는 Linux만 다룹니다.

</details>

처음 받아쓰기를 하면 Whisper 모델을 내려받습니다. `large-v3-turbo`는 약 1.6 GB, `small`은 464 MB입니다. 그 뒤로는 네트워크가 필요 없습니다.

## 사용법

```sh
spokecut talk.mp4
```

브라우저에서 편집기가 열립니다. 단어를 클릭하고 Delete를 누르면 잘리고, 드래그하면 구절이 잘리고, 회색 칩을 클릭하면 쉼이 잘리고, 단어에서 Enter를 누르면 자막을 고칠 수 있습니다. Ctrl+F로 단어나 문구를 찾아 일치하는 곳을 한 번에 자를 수 있습니다. 재생할 때는 자른 부분을 건너뜁니다. 편집 내용은 영상 옆에 `talk.mp4.spokecut.json`으로 저장되고, 영상 자체는 바뀌지 않습니다.

흔한 경우에는 브라우저가 필요 없습니다:

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut export talk.mp4 --format fcpxml
```

키보드 단축키와 모든 형식은 [사용법](docs/usage.md), 옵션은 [설정](docs/config.md)을 보세요.

## 군더더기 말, 솔직하게

기본 Whisper는 "음"과 "어"의 대부분을 받아쓰기에서 빼 버리기 때문에 군더더기 버튼이 찾을 것이 많지 않습니다. 데모 클립에서 `large-v3`가 남긴 군더더기는 2개였습니다. `--verbatim`은 CrisperWhisper로 바꾸는데, 이 모델은 군더더기를 남겨 두어 같은 클립에서 4개를 찾았습니다. 라이선스는 CC BY-NC 4.0이라 비상업적 용도로만 쓸 수 있습니다. 쉼과 바로 이어지는 반복은 어떤 모델에서도 동작합니다.

## 하지 못하는 것

- 파일당 화자는 한 명입니다. 목소리를 분리하지 않습니다.
- 자르기와 자막만 합니다. 멀티트랙 타임라인, 화면 녹화, 음성 복제는 없습니다.
- EDL, FCPXML, OTIO는 테스트에서 OpenTimelineIO 어댑터로 다시 읽어 확인했습니다. Resolve나 Premiere로 가져와 보지는 않았고, OTIO에는 비디오 트랙만 있습니다.
- 라이브 데모에서는 내 영상을 받아쓰거나 MP4로 렌더링할 수 없습니다. Python 쪽이 필요합니다.
- 자막 글꼴은 시스템의 것을 씁니다. 입혀진 중국어는 Noto CJK가 설치된 환경에서 확인했습니다. 해당 언어의 글꼴이 없으면 글자가 제대로 그려지지 않습니다.

## 동작 방식

Spokecut은 오디오를 디코딩하고 faster-whisper로 단어별 타임스탬프를 얻은 다음, 단어 쌍마다 가장 조용한 지점을 찾아 컷이 무음에 떨어지게 합니다. 편집 내용은 삭제한 단어, 자른 쉼, 자막 설정을 담은 작은 상태 객체입니다. 모든 출력은 단어와 이 상태에서 계산되고, 렌더링은 프레임 단위로 정확한 트림이 들어간 ffmpeg 필터 그래프 하나가 됩니다. 편집기는 빌드 단계가 없는 순수 ES 모듈이며 9개 언어를 지원합니다. 자세한 내용은 [아키텍처](docs/architecture.md), 각 숫자를 잰 방법은 [벤치마크](docs/benchmarks.md)에 있습니다.

## 기여

문제를 재현하는 짧은 영상이 있는 버그 리포트가 가장 도움이 됩니다. [CONTRIBUTING](CONTRIBUTING.md)을 보세요.

## 라이선스

MIT입니다. [LICENSE](LICENSE)를 보세요. 데모 클립은 Vgrigas의 "Ward Cunningham, Inventor of the Wiki"에서 발췌한 것으로 CC BY-SA 3.0입니다. [web/demo/NOTICE](web/demo/NOTICE)를 보세요.

Assisted by Claude/Codex.
