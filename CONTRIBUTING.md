# Contributing

Thanks for helping improve the SportAPI Python client.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request (CI runs the same):

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Tests never touch the network: live-mode requests are mocked with
[respx](https://lundberg.github.io/respx/), and demo mode uses the bundled example responses.

## Guidelines

- Follow the [SportAPI documentation](https://sportapi.net/docs.html). Do not add endpoints,
  fields or parameters that are not documented there; open an issue instead.
- Keep the dependency footprint small (`httpx` only at runtime) and keep Python 3.9 support.
- Add tests for new behaviour and update `CHANGELOG.md`.
- **Never commit API keys**, base URLs of real accounts or `.env` files, and do not paste them
  into issues. Use placeholders such as `https://YOUR_API_DOMAIN`.

Questions about the API itself or access: [@sportapinet_bot](https://t.me/sportapinet_bot?start=github_sportapi_python).
