# Spokecut

Schneide Videos, in denen jemand spricht, indem du das Transkript bearbeitest. Lösche ein Wort, und es verschwindet aus dem Video. Läuft auf deinem eigenen Rechner und kostet nichts.

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[Live-Demo](https://arthur031221.github.io/Spokecut/) | [Installation](docs/install.md) | [Verwendung](docs/usage.md) | [Konfiguration](docs/config.md) | [Architektur](docs/architecture.md) | [Benchmarks](docs/benchmarks.md)

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | Deutsch | [Português (Brasil)](README.pt-BR.md)

![Spokecut: Pausen und Füllwörter schneiden, einen Satz löschen, den Schnitt mit übersprungenen Cuts abspielen, den Untertitelstil wechseln](assets/demo.gif)

Ein 5 Minuten langes Sprechvideo wird auf einer RTX 5090 in 15,0 s transkribiert, aufgeräumt und mit eingebrannten Untertiteln gerendert, das ist das 20,0-Fache der Echtzeit. Das ist der ganze Ablauf aus einem Kaltstart (`python bench/bench.py pipeline talk.mp4`, Mittel aus 4 Läufen, 14,7 bis 15,1 s, `large-v3-turbo` und NVENC). Auf einem Ryzen 5 7500F mit 3 Threads, `small` und x264 braucht dasselbe Video 61,1 s.

Dein Video verlässt deinen Rechner nie. Ich sage dir lieber, dass Whisper die meisten deiner Ähms versteckt, als so zu tun, als fände der Füllwort-Knopf alle.

## Vorher und nachher

Die Zahlen stammen vom 80 Sekunden langen Demo-Clip, der auch die Live-Demo ist, sofern eine Zeile nichts anderes sagt.

| Was du willst | Von Hand in einem Timeline-Editor | Spokecut |
| --- | --- | --- |
| 10 Pausen über 0,7 s schneiden | Jede nach Gehör suchen, teilen, mit Lückenschluss löschen, zehnmal | Ein Klick oder `--pauses 0.7 --no-fillers --no-repeats --model large-v3`. Aus 80,3 s werden 73,4 s |
| Ein "äh" und ein wiederholtes Wort entfernen | Hin und her scrubben, bis man es hört | Wort anklicken und Entf drücken oder die Knöpfe für Füllwörter und Wiederholungen nutzen |
| Einen ganzen Satz schneiden | Anfang und Ende auf der Wellenform suchen | Wörter markieren und Entf drücken. Schnitte rasten auf dem leisesten Punkt zwischen zwei Wörtern ein |
| Ein Klicken an der Schnittstelle vermeiden | An jedem Schnitt eine Überblendung einfügen | Jede Naht hat eine 15-ms-Blende. Im 300-Sekunden-Benchmark-Clip lagen 3 von 37 Nähten ohne Blende über dem Zehnfachen des üblichen Sprungs zwischen Samples, mit Blende keine |
| Untertitel bekommen | Woanders transkribieren, eine SRT importieren, nach jedem Schnitt neu timen | Die Untertitel folgen dem Schnitt. Fünf Stile eingebrannt oder SRT, VTT und ASS |
| Den Schnitt in einen anderen Editor mitnehmen | Von Hand nachbauen | EDL, FCPXML und OTIO der behaltenen Bereiche |
| Ergebnis auf dem Demo-Clip |  | Von 80,3 s auf 72,1 s, 8,2 s entfernt, mit einem Befehl: `spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## Installation

Es ist noch nicht auf PyPI, also installiere es von GitHub. Du brauchst außerdem Python 3.10 oder neuer und ffmpeg.

<details>
<summary>Linux (NVIDIA-GPU oder CPU)</summary>

```sh
sudo apt install ffmpeg
pip install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

Lass `[cuda]` weg für eine reine CPU-Installation. Das Rendern nutzt NVENC, wenn ffmpeg es öffnen kann, sonst x264.

</details>

<details>
<summary>macOS (Apple Silicon oder Intel)</summary>

```sh
brew install ffmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

Die Transkription läuft auf der CPU und das Rendern nutzt x264. Ich habe Spokecut nicht auf einem Mac ausgeführt.

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

Ich habe Spokecut nicht unter Windows ausgeführt. Der CI-Job deckt nur Linux ab.

</details>

Die erste Transkription lädt das Whisper-Modell herunter, etwa 1,6 GB für `large-v3-turbo` und 464 MB für `small`. Danach braucht nichts mehr das Netzwerk.

## Verwendung

```sh
spokecut talk.mp4
```

Das öffnet den Editor im Browser. Klicke ein Wort an und drücke Entf, um es zu schneiden, ziehe über mehrere Wörter, um eine Passage zu schneiden, klicke einen grauen Chip, um eine Pause zu schneiden, und drücke Enter auf einem Wort, um einen Untertitel zu korrigieren. Mit Strg+F suchst du ein Wort oder eine Wendung und schneidest alle Treffer auf einmal. Die Wiedergabe überspringt, was du geschnitten hast. Der Schnitt wird neben dem Video als `talk.mp4.spokecut.json` gespeichert, und das Video selbst wird nie verändert.

Für den häufigen Fall brauchst du keinen Browser:

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut export talk.mp4 --format fcpxml
```

Tastenkürzel und alle Formate stehen unter [Verwendung](docs/usage.md), die Optionen unter [Konfiguration](docs/config.md).

## Füllwörter, ehrlich gesagt

Das Standard-Whisper lässt die meisten Ähms und Ähs aus seinem Transkript weg, deshalb findet der Füllwort-Knopf nur wenig. Im Demo-Clip behielt `large-v3` 2 Füllwörter. `--verbatim` wechselt zu CrisperWhisper, das sie behält, und fand im selben Clip 4. Die Lizenz ist CC BY-NC 4.0, also nur für nichtkommerzielle Nutzung. Pausen und unmittelbare Wiederholungen funktionieren mit jedem Modell.

## Was es nicht kann

- Ein Sprecher pro Datei. Stimmen werden nicht getrennt.
- Es schneidet und untertitelt. Es gibt keine Mehrspur-Timeline, keine Bildschirmaufnahme und kein Stimmenklonen.
- Ich habe die EDL-, FCPXML- und OTIO-Dateien in den Tests über die OpenTimelineIO-Adapter zurückgelesen. In Resolve oder Premiere habe ich sie nicht importiert, und das OTIO hat nur eine Videospur.
- Die Live-Demo kann dein eigenes Video weder transkribieren noch als MP4 rendern. Dafür braucht es die Python-Seite.
- Die Untertitelschriften kommen von deinem System. Eingebranntes Chinesisch habe ich mit installiertem Noto CJK geprüft. Ohne Schrift für deine Sprache wird der Text nicht richtig gezeichnet.

## So funktioniert es

Spokecut dekodiert das Audio, lässt faster-whisper Zeitstempel pro Wort bestimmen und sucht zwischen jedem Wortpaar den leisesten Punkt, damit ein Schnitt in der Stille landet. Dein Schnitt ist ein kleines Zustandsobjekt aus gelöschten Wörtern, geschnittenen Pausen und Untertiteleinstellungen. Jede Ausgabe wird aus den Wörtern und diesem Zustand berechnet, und das Rendern wird zu einem einzigen ffmpeg-Filtergraphen mit bildgenauen Trims. Der Editor besteht aus einfachen ES-Modulen ohne Build-Schritt, in neun Sprachen. Die Seite [Architektur](docs/architecture.md) hat die Details und die Seite [Benchmarks](docs/benchmarks.md) die Methode hinter jeder Zahl.

## Mitmachen

Am meisten hilft ein Fehlerbericht mit einem kurzen Video, das das Problem zeigt. Siehe [CONTRIBUTING](CONTRIBUTING.md).

## Lizenz

MIT, siehe [LICENSE](LICENSE). Der Demo-Clip ist ein Ausschnitt aus "Ward Cunningham, Inventor of the Wiki" von Vgrigas, CC BY-SA 3.0, siehe [web/demo/NOTICE](web/demo/NOTICE).

Assisted by Claude/Codex.
