# Spokecut

Edita vídeo de gente hablando editando su transcripción. Borra una palabra y desaparece del vídeo. Funciona en tu propio equipo y es gratis.

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[Demo en vivo](https://arthur031221.github.io/Spokecut/) | [Instalación](docs/install.md) | [Uso](docs/usage.md) | [Configuración](docs/config.md) | [Arquitectura](docs/architecture.md) | [Benchmarks](docs/benchmarks.md)

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | Español | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

![Spokecut: corta pausas y muletillas, borra una frase, reproduce la edición saltando los cortes y cambia el estilo de los subtítulos](assets/demo.gif)

Un vídeo de 5 minutos de una persona hablando se transcribe, se limpia y se renderiza con subtítulos grabados en 15,0 s en una RTX 5090, 20,0 veces más rápido que el tiempo real. Es el trabajo completo desde un arranque en frío (`python bench/bench.py pipeline talk.mp4`, media de 4 ejecuciones, de 14,7 a 15,1 s, `large-v3-turbo` y NVENC). En un Ryzen 5 7500F con 3 hilos, `small` y x264, el mismo vídeo tarda 61,1 s.

Tu vídeo no sale de tu equipo. Prefiero decirte que Whisper esconde la mayoría de tus «eh» y «mm» antes que fingir que el botón de muletillas las encuentra todas.

## Antes y después

Los números salen del clip de demostración de 80 segundos, el mismo de la demo en vivo, salvo que una fila diga otra cosa.

| Lo que quieres | A mano en un editor de línea de tiempo | Spokecut |
| --- | --- | --- |
| Cortar 10 pausas de más de 0,7 s | Buscar cada una de oído, dividir, borrar con ondulación, diez veces | Un clic, o `--pauses 0.7 --no-fillers --no-repeats --model large-v3`. 80,3 s pasan a 73,4 s |
| Quitar un «uh» y una palabra repetida | Mover el cursor hasta oírlo | Haz clic en la palabra y pulsa Supr, o usa los botones de muletillas y repeticiones |
| Cortar una frase entera | Buscar su inicio y su final en la forma de onda | Selecciona las palabras y pulsa Supr. Los cortes se ajustan al punto más silencioso entre palabras |
| Evitar un chasquido donde se unen dos trozos | Añadir un fundido cruzado en cada corte | Cada unión lleva un fundido de 15 ms. En el clip de 300 segundos, 3 de 37 uniones superaron 10 veces el salto normal entre muestras sin el fundido y ninguna lo hizo con él |
| Conseguir subtítulos | Transcribir en otra herramienta, importar un SRT y reajustar los tiempos tras cada corte | Los subtítulos siguen a la edición. Cinco estilos grabados en el vídeo, o SRT, VTT y ASS |
| Llevar la edición a otro editor | Rehacerla a mano | EDL, FCPXML y OTIO de los tramos conservados |
| Resultado en el clip de demostración |  | De 80,3 s a 72,1 s, 8,2 s eliminados, con un solo comando: `spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## Instalación

Todavía no está en PyPI, así que se instala desde GitHub. También necesitas Python 3.10 o superior y ffmpeg.

<details>
<summary>Linux (GPU NVIDIA o CPU)</summary>

```sh
sudo apt install ffmpeg pipx
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

Quita `[cuda]` para una instalación solo con CPU. El renderizado usa NVENC cuando ffmpeg puede abrirlo y x264 cuando no.

</details>

<details>
<summary>macOS (Apple Silicon o Intel)</summary>

```sh
brew install ffmpeg pipx
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

La transcripción se ejecuta en la CPU y el renderizado usa x264. No he ejecutado Spokecut en un Mac.

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

No he ejecutado Spokecut en Windows. El trabajo de CI solo cubre Linux.

</details>

La primera transcripción descarga el modelo de Whisper: unos 1,6 GB para `large-v3-turbo` y 464 MB para `small`. Después no hace falta red.

## Uso

```sh
spokecut talk.mp4
```

Esto abre el editor en el navegador. Haz clic en una palabra y pulsa Supr para cortarla, arrastra para cortar una frase, haz clic en una etiqueta gris para cortar una pausa y pulsa Intro sobre una palabra para corregir un subtítulo. Pulsa Ctrl+F para buscar una palabra o frase y cortar todas las coincidencias de una vez. La reproducción salta lo que cortaste. La edición se guarda junto al vídeo como `talk.mp4.spokecut.json` y el vídeo en sí nunca cambia.

Para el caso habitual no hace falta el navegador:

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut export talk.mp4 --format fcpxml
```

Consulta [uso](docs/usage.md) para los atajos de teclado y todos los formatos, y [configuración](docs/config.md) para las opciones.

## Las muletillas, con franqueza

El Whisper estándar elimina casi todos los «eh» y «mm» de su transcripción, así que el botón de muletillas tiene poco que encontrar. En el clip de demostración `large-v3` conservó 2 muletillas. `--verbatim` cambia a CrisperWhisper, que las conserva, y encontró 4 en el mismo clip. Su licencia es CC BY-NC 4.0, así que solo sirve para uso no comercial. Las pausas y las repeticiones inmediatas funcionan con todos los modelos.

## Lo que no hace

- Una sola persona hablando por archivo. No separa voces.
- Corta y subtitula. No hay línea de tiempo multipista, ni grabación de pantalla, ni clonación de voz.
- Leí los archivos EDL, FCPXML y OTIO con los adaptadores de OpenTimelineIO en las pruebas. No los he importado en Resolve ni en Premiere, y el OTIO solo tiene pista de vídeo.
- La demo en vivo no puede transcribir tu propio vídeo ni renderizar un MP4. Eso necesita la parte de Python.
- Las fuentes de los subtítulos vienen de tu sistema. Comprobé el chino grabado en el vídeo con Noto CJK instalado. Sin una fuente para tu idioma, el texto no se dibujará bien.

## Cómo funciona

Spokecut decodifica el audio, ejecuta faster-whisper para obtener marcas de tiempo por palabra y busca el punto más silencioso entre cada par de palabras para que el corte caiga en silencio. Tu edición es un pequeño objeto de estado con las palabras borradas, las pausas cortadas y los ajustes de subtítulos. Cada salida se calcula a partir de las palabras y de ese estado, y el renderizado se convierte en un solo grafo de filtros de ffmpeg con recortes exactos al fotograma. El editor son módulos ES sin paso de compilación, en nueve idiomas. La página de [arquitectura](docs/architecture.md) tiene los detalles y la de [benchmarks](docs/benchmarks.md) el método detrás de cada número.

## Contribuir

Lo que más ayuda es un informe de error con un vídeo corto que reproduzca el problema. Mira [CONTRIBUTING](CONTRIBUTING.md).

## Licencia

MIT, mira [LICENSE](LICENSE). El clip de demostración es un fragmento de "Ward Cunningham, Inventor of the Wiki" de Vgrigas, CC BY-SA 3.0, mira [web/demo/NOTICE](web/demo/NOTICE).

Assisted by Claude/Codex.
