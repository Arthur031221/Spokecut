# Spokecut

Montez une vidéo où l'on parle en modifiant sa transcription. Supprimez un mot et il disparaît de la vidéo. Ça tourne sur votre machine et c'est gratuit.

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[Démo en ligne](https://arthur031221.github.io/Spokecut/) | [Installation](docs/install.md) | [Utilisation](docs/usage.md) | [Configuration](docs/config.md) | [Architecture](docs/architecture.md) | [Benchmarks](docs/benchmarks.md)

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | Français | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

![Spokecut : couper les pauses et les tics de langage, supprimer une phrase, écouter le montage en sautant les coupes, changer le style des sous-titres](assets/demo.gif)

Une vidéo parlée de 5 minutes est transcrite, nettoyée et rendue avec des sous-titres incrustés en 15,0 s sur une RTX 5090, soit 20,0 fois le temps réel. C'est le travail complet depuis un démarrage à froid (`python bench/bench.py pipeline talk.mp4`, moyenne de 4 exécutions, de 14,7 à 15,1 s, `large-v3-turbo` et NVENC). Sur un Ryzen 5 7500F avec 3 threads, `small` et x264, la même vidéo prend 61,1 s.

Votre vidéo ne quitte jamais votre machine. Je préfère vous dire que Whisper cache la plupart de vos « euh » plutôt que de prétendre que le bouton des tics de langage les trouve tous.

## Avant et après

Les chiffres viennent du clip de démonstration de 80 secondes, le même que la démo en ligne, sauf mention contraire sur une ligne.

| Ce que vous voulez | À la main dans un éditeur à timeline | Spokecut |
| --- | --- | --- |
| Couper 10 pauses de plus de 0,7 s | Les chercher à l'oreille une par une, découper, supprimer avec décalage, dix fois | Un clic, ou `--pauses 0.7 --no-fillers --no-repeats --model large-v3`. 80,3 s deviennent 73,4 s |
| Retirer un « uh » et un mot répété | Naviguer jusqu'à l'entendre | Cliquez sur le mot et appuyez sur Suppr, ou utilisez les boutons des tics de langage et des répétitions |
| Couper une phrase entière | Chercher son début et sa fin sur la forme d'onde | Sélectionnez les mots et appuyez sur Suppr. Les coupes se calent sur le point le plus silencieux entre deux mots |
| Éviter un clic à la jonction de deux morceaux | Ajouter un fondu enchaîné à chaque coupe | Chaque jonction a un fondu de 15 ms. Sur le clip de 300 secondes, 3 jonctions sur 37 dépassaient 10 fois le saut habituel entre échantillons sans le fondu, et aucune avec |
| Obtenir des sous-titres | Transcrire ailleurs, importer un SRT, recaler le timing après chaque coupe | Les sous-titres suivent le montage. Cinq styles incrustés, ou SRT, VTT et ASS |
| Emporter le montage dans un autre éditeur | Le refaire à la main | EDL, FCPXML et OTIO des plages conservées |
| Résultat sur le clip de démonstration |  | De 80,3 s à 72,1 s, 8,2 s retirées, avec une seule commande : `spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## Installation

Ce n'est pas encore sur PyPI, donc installez depuis GitHub. Il vous faut aussi Python 3.10 ou plus récent et ffmpeg.

<details>
<summary>Linux (GPU NVIDIA ou CPU)</summary>

```sh
sudo apt install ffmpeg pipx
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

Retirez `[cuda]` pour une installation CPU seulement. Le rendu utilise NVENC quand ffmpeg peut l'ouvrir et x264 sinon.

</details>

<details>
<summary>macOS (Apple Silicon ou Intel)</summary>

```sh
brew install ffmpeg pipx
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

La transcription tourne sur le CPU et le rendu utilise x264. Je n'ai pas utilisé Spokecut moi-même sur un Mac. La CI lance les tests, rendus compris, sous macOS. Les sous-titres incrustés demandent un ffmpeg compilé avec libass, et Spokecut le signale si le vôtre n'en a pas.

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

Je n'ai pas utilisé Spokecut moi-même sur Windows. La CI lance les tests, rendus compris, sous Windows.

</details>

La première transcription télécharge le modèle Whisper : environ 1,6 Go pour `large-v3-turbo` et 464 Mo pour `small`. Ensuite, plus besoin de réseau.

## Utilisation

```sh
spokecut talk.mp4
```

Cela ouvre l'éditeur dans votre navigateur. Cliquez sur un mot et appuyez sur Suppr pour le couper, faites glisser pour couper une phrase, cliquez sur une pastille grise pour couper une pause, et appuyez sur Entrée sur un mot pour corriger un sous-titre. Appuyez sur Ctrl+F pour chercher un mot ou une phrase et couper toutes les occurrences d'un coup. La lecture saute ce que vous avez coupé. Le montage est enregistré à côté de la vidéo sous `talk.mp4.spokecut.json`, et la vidéo elle-même n'est jamais modifiée. La langue, le modèle et l'option qui garde les euh sont dans Options de transcription, et Transcrire à nouveau refait une vidéo dont la langue a été mal détectée.

Pas besoin de navigateur dans le cas courant :

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut clean *.mp4 --pauses 0.7
spokecut export talk.mp4 --format fcpxml
```

Voir [utilisation](docs/usage.md) pour les raccourcis clavier et tous les formats, et [configuration](docs/config.md) pour les options.

## Les tics de langage, franchement

Le Whisper standard retire la plupart des « euh » de sa transcription, donc le bouton des tics de langage a peu à trouver. Sur le clip de démonstration, `large-v3` en a gardé 2. `--verbatim` passe à CrisperWhisper, qui les conserve, et il en a trouvé 4 sur le même clip. Sa licence est CC BY-NC 4.0, donc usage non commercial uniquement. Les pauses et les répétitions immédiates marchent avec tous les modèles.

## Ce qu'il ne fait pas

- Une seule personne qui parle par fichier. Il ne sépare pas les voix.
- Il coupe et il sous-titre. Pas de timeline multipiste, pas d'enregistrement d'écran, pas de clonage de voix.
- J'ai relu les fichiers EDL, FCPXML et OTIO avec les adaptateurs OpenTimelineIO dans les tests. Je ne les ai pas importés dans Resolve ni dans Premiere, et l'OTIO n'a qu'une piste vidéo.
- La démo en ligne ne peut ni transcrire votre propre vidéo ni rendre un MP4. Cela demande la partie Python.
- Les polices des sous-titres viennent de votre système. J'ai vérifié le chinois incrusté avec Noto CJK installé. Sans police pour votre langue, le texte ne s'affichera pas correctement.

## Comment ça marche

Spokecut décode l'audio, lance faster-whisper pour obtenir des horodatages par mot, et cherche le point le plus silencieux entre chaque paire de mots pour que la coupe tombe dans le silence. Votre montage est un petit objet d'état avec les mots supprimés, les pauses coupées et les réglages des sous-titres. Chaque sortie est calculée à partir des mots et de cet état, et le rendu devient un seul graphe de filtres ffmpeg avec des coupes exactes à l'image. L'éditeur est fait de modules ES simples, sans étape de build, en neuf langues. La page [architecture](docs/architecture.md) donne les détails et la page [benchmarks](docs/benchmarks.md) la méthode derrière chaque chiffre.

## Contribuer

Un rapport de bogue avec une courte vidéo qui reproduit le problème est ce qui aide le plus. Voir [CONTRIBUTING](CONTRIBUTING.md).

## Licence

MIT, voir [LICENSE](LICENSE). Le clip de démonstration est un extrait de « Ward Cunningham, Inventor of the Wiki » par Vgrigas, CC BY-SA 3.0, voir [web/demo/NOTICE](web/demo/NOTICE).

Assisted by Claude/Codex.
