"""临时配置：用 SQLite 跑通全流程自检（方便在没有 MySQL 凭据时验证代码逻辑）。

用法：
    DJANGO_SETTINGS_MODULE=config.settings_sqlite .venv\\Scripts\\python manage.py migrate
"""

from config.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "_selftest.sqlite3"),  # noqa: F405
    }
}
