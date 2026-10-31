# TGBoxOffice - production-oriented container for Render Web Services.
# Python 3.12 is a stable compatibility target for this legacy Pyrogram stack.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000

# Runtime libraries and build tools required by media/Python dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       ffmpeg \
       git \
       gcc \
       g++ \
       build-essential \
       libglib2.0-0 \
       libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies separately so Docker can cache this layer.
COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir setuptools==80.9.0 wheel \
    && python -m pip install --prefer-binary -r requirements.txt

COPY . .

# Fail early on malformed Python source during image build.
RUN python - <<'PY'
import ast
from pathlib import Path
files = list(Path('/app').rglob('*.py'))
errors = []
for path in files:
    try:
        ast.parse(path.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'{path}: {exc}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Validated syntax for {len(files)} Python files.')

# Validate the legacy sticker plugin API and its urllib3 1.x dependency at image-build time.
import pkg_resources
import urllib3
assert urllib3.__version__.startswith('1.'), f'python-telegram-bot 13.15 requires urllib3 1.x; found {urllib3.__version__}'
import urllib3.contrib.appengine
import telegram
from telegram import ParseMode, TelegramError, Update, Bot
from telegram.ext import CommandHandler, run_async, Updater, Handler, InlineQueryHandler
assert telegram.__version__.startswith('13.'), telegram.__version__
print(f'Validated python-telegram-bot {telegram.__version__} legacy API.')

# ytthumb 2.0.0 uses warnings.deprecated (Python 3.13+); verify the
# Python 3.12 compatibility shim used by the plugin before deployment.
import warnings
if not hasattr(warnings, 'deprecated'):
    def _compat_deprecated(message=None, *, category=DeprecationWarning, stacklevel=1):
        def decorate(obj):
            return obj
        return decorate
    warnings.deprecated = _compat_deprecated
import ytthumb
print('Validated ytthumb import on this Python runtime.')
PY

EXPOSE 10000
CMD ["python", "-u", "bot.py"]
