# TgCrypto installation fix

- Removed TgCrypto from mandatory `requirements.txt`: it is an optional Pyrogram speed-up, not a runtime requirement.
- `deploy.sh` now installs the pinned `TgCrypto==1.2.5` separately, trying a compatible wheel and then a source build.
- A TgCrypto build failure is a warning, not a fatal deployment error; Pyrogram can continue with its pure-Python crypto implementation.
- Docker installs build tools and attempts the same pinned optional package.

For a manual retry inside the project virtual environment:

```bash
./venv/bin/python -m pip install --upgrade pip setuptools wheel
./venv/bin/python -m pip install --no-cache-dir --prefer-binary TgCrypto==1.2.5
```

If source compilation is required on Debian/Ubuntu, install `build-essential python3-dev`, then retry.
