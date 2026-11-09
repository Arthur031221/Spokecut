# Usage

## The editor

```sh
spokecut talk.mp4        # same as: spokecut edit talk.mp4
spokecut                 # open the editor and drop a video on it
```

This starts a server on `127.0.0.1:8765`, opens a browser tab and transcribes the video. The first run for a
video writes `talk.mp4.spokecut.json` next to it. That file holds the words, the timings and your edit, so the next
open is instant and you can copy it with the video.

In the editor:

- Click a word and press Delete to cut it. Drag across words to cut a phrase. Press Delete again to bring them back.
- The Cut button above the transcript does the same as Delete, so you can edit on a phone or tablet. There, tap the
  first word of a phrase, tap Select range, tap the last word, then tap Cut.
- Press Enter on a word to fix a misspelling. This changes the caption text and leaves the audio alone.
- The gray chip between two words is a pause. Click it to cut it down to the length you set in the cleanup box.
- Playback skips what you cut, so you hear the edit and not the original. Turn off Follow to stop the transcript
  scrolling with the playhead.
- Under the transcript the waveform shows the cut parts shaded. Click it to seek.
- Press Ctrl or Cmd + F, or /, to find a word or phrase. Matches are highlighted, Enter steps to the next one and
  Shift + Enter to the previous one. The Cut button cuts every match at once, and a second press brings them back.
  Case and punctuation don't matter, and a match is always whole words.
- The cleanup box marks fillers, repeats and pauses in one click. Each button has arrows to step through the hits.
- Under Transcription options on the first screen you can set the spoken language, the Whisper model and whether to
  keep ums and uhs (`--verbatim`) before you open a video. Wrong language, or too many mistakes? Open Transcribe
  again under the transcript, pick other options and run it again. The words change, so the edit you had is kept
  next to the video as `talk.mp4.spokecut.json.bak`, and if the new run fails the old transcript stays open. The
  first run of a model downloads it, and the progress page says so while it loads.
- Undo and redo cover every change. Changes are saved a moment after you make them.

### Keyboard

| Key | Action |
| --- | --- |
| Space | play from the selected word, or pause |
| Left, Right | move one word |
| Up, Down | move one line |
| Shift + arrows | extend the selection |
| Delete, Backspace | cut or restore the selection |
| Enter | edit the word |
| Home, End | first and last word |
| Escape | clear the selection, or clear the find box |
| Ctrl or Cmd + F, / | go to the find box |
| Enter, Shift + Enter (in the find box) | next match, previous match |
| Ctrl or Cmd + Z, Shift + Z | undo and redo (Ctrl or Cmd + Y also redoes) |

### Captions

Pick a style (highlight, karaoke, pop, lower third, plain), a position, a size and the colours. The preview on the
video is the same layout the render draws, for portrait and phone video too: the frame follows the rotation flag. Burn in is on by default for MP4 and has no effect on the other formats.

### Export

| Format | What you get |
| --- | --- |
| MP4 | the edit rendered with captions burned in. NVENC when available |
| SRT, VTT, ASS | captions on the edited timeline |
| EDL | CMX 3600 cut list for Resolve, Premiere and Avid |
| FCPXML | Final Cut Pro X 1.9 project |
| OTIO | OpenTimelineIO, video track only |
| JSON | the cut list: kept ranges and removed ranges in source time |

I read the EDL, FCPXML and OTIO files back through the OpenTimelineIO adapters in the test suite to check the cut
points. I have not imported them into Resolve or Premiere, so test the import on a short file before you rely on it.

## Without a browser

```sh
spokecut transcribe talk.mp4
spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3
spokecut export talk.mp4 --format srt
```

`clean` takes several files, as in `spokecut clean *.mp4 --pauses 0.7`. It loads the model once, keeps going when
one file fails, and exits with 1 if any did. `clean` marks fillers and repeats, shortens pauses of at least `--pauses` seconds down to `--keep` seconds
(0.25 by default), and writes the result. It reuses `talk.mp4.spokecut.json` when it exists, so edits you made in
the editor carry over. Pass `--retranscribe` to ignore it. `--model`, `--language` and `--device` only matter when there is no saved
project yet, so use `--retranscribe` with them on a video you already opened. A new transcription keeps the old
edit next to it as `talk.mp4.spokecut.json.bak`, because word numbers change and the old edit can't carry over.

On the demo clip it prints:

```
80.3 s -> 72.1 s (8.2 s removed), wrote talk.spokecut.mp4
```

## Fillers

Stock Whisper leaves most ums and uhs out of its transcript, so there is little for the filler button to find. On
the demo clip `large-v3` found 2 fillers. Add `--verbatim` to use CrisperWhisper, which keeps them. It found 4 on the
same clip. CrisperWhisper is licensed CC BY-NC 4.0, so it is for non-commercial use only. Pauses and immediate
repeats work with every model.
