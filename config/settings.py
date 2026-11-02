"""小学英语出卷系统 — Django 项目配置。"""

from pathlib import Path

from config import env

env.load_env()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env.get("DJANGO_SECRET_KEY", "django-insecure-local-exam-gen-2026")
DEBUG = env.get_bool("DEBUG", True)
# 只允许本机访问：去掉 "*" 之后，Host 头不可伪造，恶意网页没法用 DNS rebinding 打本机服务。
# 需要用局域网 IP 访问时，在 .env 里写 DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.10
ALLOWED_HOSTS = [
    host.strip()
    for host in env.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.bank",
    "apps.importer",
    "apps.paper",
    "apps.exporter",
    "apps.prints",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # 全站登录保护：除 login_not_required 标注的视图（登录页、后台登录）外，一律先登录
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.debug",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env.get("MYSQL_DATABASE", "english_exam"),
        "USER": env.get("MYSQL_USER", "root"),
        "PASSWORD": env.get("MYSQL_PASSWORD", ""),
        "HOST": env.get("MYSQL_HOST", "127.0.0.1"),
        "PORT": env.get("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_HEALTH_CHECKS": True,
        "CONN_MAX_AGE": 0,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
# 单机本地工具，关闭时区支持以避免 Windows MySQL 未加载时区表带来的坑
USE_TZ = False

# ---------------------------------------------------------------- 登录
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/papers/"
LOGOUT_REDIRECT_URL = "/login/"

# 自助注册开关：置 0 后 /register/ 会提示“已关闭”并退回登录页
ALLOW_SELF_REGISTRATION = env.get_bool("ALLOW_SELF_REGISTRATION", True)

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

# ---------------------------------------------------------------- 业务配置

GRADE_CHOICES = [(3, "三年级"), (4, "四年级"), (5, "五年级"), (6, "六年级")]

AI_VISION_ENABLED = env.get_bool("AI_VISION_ENABLED", False)
AI_VISION_BASE_URL = env.get("AI_VISION_BASE_URL", "")
AI_VISION_API_KEY = env.get("AI_VISION_API_KEY", "")
AI_VISION_MODEL = env.get("AI_VISION_MODEL", "")
AI_VISION_TIMEOUT = 45
