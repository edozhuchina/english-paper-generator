# 小学英语出卷系统

从题库管理到组卷出卷，再到导出可排版 Word 试卷的一体化本地工具。
浏览器打开 `http://127.0.0.1:8000` 使用，数据存放在本机 MySQL。

## 技术栈

| 组件 | 选型 |
|---|---|
| 后端 | Python 3.12 + Django 5.2（LTS） |
| 数据库 | MySQL 8.0（`utf8mb4`） |
| Excel | openpyxl（模板生成、批量导入） |
| Word | python-docx（双向：解析导入 + 排版导出） |
| 图片 | Pillow（尺寸与 dpi 换算） |
| 前端 | Django Templates + 原生 CSS/JS，零 CDN 依赖，可完全离线 |

> **为什么不用 Node/React**：本地单机工具，改完刷新即可生效，没有构建环节也就没有构建故障。

## 快速开始

### 1. 环境准备

```powershell
D:\Python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> ⚠️ 本机同时装有 Python 3.14 与 3.12，**所有命令必须用 `.venv\Scripts\python`**，不要裸敲 `pip`。

### 2. 配置数据库连接

复制 `.env.example` 为 `.env`，填写真实值：

```ini
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=english_exam
```

如未建库，用 MySQL Workbench 执行 `sql/001_create_db.sql`。

### 3. 建表与初始数据

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py loaddata fixtures/question_types.json fixtures/tags.json
.\.venv\Scripts\python.exe manage.py load_sample_bank
.\.venv\Scripts\python.exe manage.py createsuperuser
```

三行命令分别做：建表、灌入 15 个题型 + 40 个标签、生成约 113 道三~六年级样例题、创建后台超管。

### 4. 启动

双击 `scripts\run.ps1`，或：

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

## 功能地图

| 模块 | 路径 | 说明 |
|---|---|---|
| 登录 | `/login/` | 全站登录保护；未登录访问任何业务页都会跳到这里 |
| 题库列表 | `/bank/` | 按题型/年级/难度/标签/关键词筛选，支持全文检索题干与答案 |
| 手动录题 | `/bank/create/` | 选择题型后自动出现对应结构化表单（选项/答案/评分要点） |
| 批量导入 | `/import/` | 下载 Excel 模板 → 上传校验 → 确认入库，含行级错误与重复跳过 |
| 试卷列表 | `/papers/` | 新建、组卷、导出、删除 |
| 组卷工作台 | `/papers/<id>/` | 左栏挑题右栏组卷，勾选/拖拽排序/实时分值统计 |
| Word 导出 | `/papers/<id>/export/docx/` | 可编辑 `.docx`，含卷头分数栏、答案页、答题卡、听力清单 |
| 打印预览 | `/print/paper/<id>/` | A4 排版，`?mode=answer` 显示答案，浏览器 Ctrl+P 存 PDF |
| 后台管理 | `/admin/` | Django 原生后台，账号权限、字典维护、批量操作 |

## 目录结构

```
config/            Django 项目配置（settings 从 .env 读取）
apps/
  core/            抽象基类（时间戳、软删除）与全局枚举
  catalog/         题型字典 QuestionType、标签 Tag
  bank/            题库核心：Question / Passage / MediaAsset
  importer/        Excel/CSV/Word/AI 四种录入，共用草稿表与校对流程
  paper/           试卷 Paper / 大题 PaperSection / 关联 PaperQuestion
  exporter/        RenderPlan 中间层 + python-docx  writer + 题型渲染器
  prints/          A4 打印视图（与 Word 导出共用同一份 RenderPlan）
scripts/           run.ps1 启动；backup_db.ps1 数据库备份；selfcheck_*.py 自检脚本
fixtures/          题型与标签初始数据
sql/               建库脚本
samples/           导入模板输出位置
```

## 核心设计

**一套 schema 容纳 15 种题型。** 公共检索字段（题型/年级/难度/审核态）落在列上，让组卷能用索引 SQL 抽题；题型特有结构（选项、填空位、评分要点）放在 `content` / `answer` 两个 JSON 字段里。**新增题型只需往 QuestionType 插一行数据，不需要改模型、不需要迁移。**

**一行 = 一道可判分的题。** 阅读理解/完形填空这类「一材多题」的题，材料单独存 `Passage`，每道小题是独立的 `Question` 行，通过 `passage` 外键关联 —— 小题可以单独检索、单独赋分、单独渲染。

**排版只写一遍。** 题库经 `RenderPlan` 中间层转换后，同时喂给 Word writer 和打印 HTML 两个消费者，保证导出的 Word 和网页上看到的完全一致。

**四种录入方式共用一套提交逻辑。** Excel/CSV、Word 解析、AI 图片识别、手动录入都先落成 `ImportDraft` 草稿，再走同一个 `commit_drafts()` 入库，去重与标签挂载行为完全一致。

## 已知限制

- **python-docx 无法把 mp3 嵌入 Word**，听力音频以「网页 `<audio>` 播放 + 卷末音频清单」方式交付
- Word 解析导入不识别公式（`OMML`）、艺术字、复杂文本框，这类内容请在页面提示下改用图片识别或手工补录
- 图片 AI 识别需要在 `.env` 配置 `AI_VISION_*`（兼容 OpenAI 接口），未配置时该按钮自动禁用，其余功能不受影响

## 登录与备份

**登录保护。** 全站由 `LoginRequiredMiddleware` 接管：除登录页与后台登录页外，任何页面（含所有 AJAX 接口）都要求先登录，未登录一律 302 到 `/login/`。账号就是后台账号，退出入口在右上角。

**数据库备份。** `scripts\backup_db.ps1` 读取 `.env` 里的连接信息，用 `mysqldump` 导出一份带时间戳的 `.sql` 到 `backups\`，默认只保留最近 14 份。密码通过临时 defaults 文件传给 mysqldump，不出现在命令行、导出后立即删除。图片与音频在 `media\`，需要的话单独复制该目录。

## 常用命令

```powershell
# 单元 / 回归测试（用临时 SQLite，不碰 MySQL）
.\.venv\Scripts\python.exe manage.py test apps --settings=config.settings_sqlite

# 数据库备份（默认保留最近 14 份）
.\scripts\backup_db.ps1

# 自检：页面冒烟测试
$env:DJANGO_SETTINGS_MODULE="config.settings_sqlite"
.\.venv\Scripts\python.exe scripts\selfcheck_pages.py

# 自检：组卷 + Word 导出
.\.venv\Scripts\python.exe scripts\selfcheck_flow.py

# 自检：Excel 导入链路（含去重验证）
.\.venv\Scripts\python.exe scripts\selfcheck_import.py
```

自检脚本使用临时的 SQLite 配置（`config/settings_sqlite.py`），不会碰你的 MySQL 数据。
