# Contributing

Bug reports with a short video that reproduces the problem are the most useful thing you can send.

## Set up

```sh
git clone https://github.com/Arthur031221/Spokecut
cd Spokecut
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

You need ffmpeg on your PATH. For the browser tests, also run `playwright install chrome`.

## Checks

Run these before opening a pull request. CI runs the same ones.

```sh
ruff check . && ruff format --check .
pytest -m "not slow and not e2e"        # fast, no model weights
node --test tests/js/*.test.mjs
SPOKECUT_BROWSER_CHANNEL=chrome pytest -m e2e
pytest -m slow                          # real tiny.en weights, downloads about 75 MB
```

## Guidelines

- Keep the browser side free of a build step. Plain ES modules, no framework.
- The timeline and caption logic exists in Python and JavaScript. If you change one, change the other and run
  `python scripts/make_golden.py` so both test suites check the same fixtures.
- A new UI string goes into every file in `web/locales/`. `tests/js/i18n.test.mjs` fails if the keys or placeholders
  differ. A machine translation is fine for a first pass. Say so in the pull request and a native speaker can fix it.
- A change to the render should come with a number from `bench/bench.py`.
- Add a test with the fix.
- Keep pull requests small and say what you ran.

## Adding a language

Copy `web/locales/en.json`, translate the values, and add the code to the list in `web/js/i18n.js`. If you want a translated README, add it as `README.<code>.md` at the top of the repository. It must end with the same last line as the English README.
