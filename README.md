# JIQT_2

## 项目简介

JIQT_2 / SCRmonitor 是一个本地实验数据管理与分析系统，用于样品管理、Raw Data 上传、解析器处理、前端可视化展示，以及本地 SQLite 与运行时文件存储管理。

系统当前处于早期阶段，核心目标是将样品、测试数据、工艺记录、原始测量文件、解析后的结构化记录、表征文件、性能数据集和 MES 风格流程信息集中到一个本地 Web 应用中管理。

## 技术栈

- Backend: Python standard-library HTTP server, SQLite。
- Frontend: React + TypeScript + Vite。
- Data processing: `SCRmonitor/parsers/` 下的 parser modules。
- Packaging: `SCRmonitor/packaging/` 下的 PowerShell / installer scripts。
- Package managers: Python 使用 `pip`，Frontend 使用 `npm`。

## 目录结构

- `SCRmonitor/server.py`: 后端主入口，负责 HTTP API、SQLite 访问、数据库迁移、文件上传、运行时输出访问和静态前端文件服务。
- `SCRmonitor/frontend/`: React + TypeScript + Vite 前端工程，包含页面、组件、API client、状态管理、类型定义和静态资源。
- `SCRmonitor/parsers/`: Raw Data 与测量文件解析、结构化记录生成、图表或可视化输出相关逻辑。
- `SCRmonitor/migrations/`: SQLite schema 和种子数据迁移文件，用于可复现地初始化或升级数据库结构。
- `SCRmonitor/templates/`: 应用需要提供给用户的安全模板文件。
- `SCRmonitor/tools/`: 本地辅助工具脚本。
- `SCRmonitor/packaging/`: 打包、安装、服务注册和 installer 配置相关脚本。
- `SCRmonitor/data/`: 默认本地运行数据目录。Git 中只保留 `.gitkeep` 占位文件，不提交真实运行数据。
- `docs/`: 项目级说明文档，包括代码结构、数据流和开发指南。

## 环境变量

`.env` 仅用于本地环境，禁止提交到 Git。`.env.example` 是安全模板，只能包含占位值和说明，不得包含真实 API key、token、password、credential 或 private config。

支持的环境变量：

- `JIQT_HOST`: 后端监听地址，未设置时使用默认值。
- `PORT`: 后端监听端口，未设置时默认使用 `8000`。
- `JIQT_DATA_DIR`: 运行时数据目录，用于 SQLite database、uploads、outputs、logs 和 backups。
- `OPENAI_API_KEY`: 仅在未来需要相关功能时作为占位变量使用，不得在 Git 中保存真实值。

## 本地开发启动

Backend setup:

```powershell
python -m venv .venv
pip install -r SCRmonitor/requirements.txt
```

Run backend:

```powershell
python SCRmonitor/server.py
```

如需显式指定运行目录：

```powershell
python SCRmonitor/server.py --host 0.0.0.0 --port 8000 --data-dir SCRmonitor/data
```

Frontend setup:

```powershell
cd SCRmonitor/frontend
npm install
npm run dev
```

Production frontend build:

```powershell
cd SCRmonitor/frontend
npm run build
```

`SCRmonitor/frontend/dist` 是生成目录，不应提交。

## 运行数据策略

运行数据必须保留在本地，不进入 Git。包括但不限于：

- SQLite databases: `*.db`, `*.sqlite`, `*.sqlite3`
- uploaded Raw Data
- parsed raw data
- generated outputs
- charts
- reports
- exports
- logs
- backups
- artifacts
- local runtime folders

`SCRmonitor/data/` 只提交 `.gitkeep` 占位文件，用于保留目录结构。真实数据库、上传文件、输出文件和日志必须由本地运行环境生成，并通过 `.gitignore` 排除。

## Git 上传原则

应提交：

- source code
- frontend/backend configuration
- dependency manifests and lock files
- documentation
- templates
- migrations
- packaging source scripts and installer configuration
- safe project rule files

禁止提交：

- `.env` 或任何 secrets
- API keys, tokens, credentials, passwords, private config
- `node_modules`
- virtual environments
- Python cache files
- `SCRmonitor/frontend/dist`
- `SCRmonitor/packaging/output`
- `SCRmonitor/packaging/staging`
- SQLite databases
- runtime uploads, outputs, exports, reports, charts, logs, backups
- real experimental data or business data

提交前建议检查：

```powershell
git status
git add -n .
```

如果已经暂存文件，提交前检查：

```powershell
git diff --cached --name-only
```

确认暂存列表不包含 secrets、运行数据、数据库、构建产物或依赖目录后，再执行正式提交。

## 相关文档

- `docs/Code_Structure.md`: 代码结构和主要目录说明。
- `docs/Data_Flow.md`: 数据创建、上传、解析、结构化和前端消费流程。
- `docs/Development_Guide.md`: 本地开发、环境变量、parser 修改和 Git 检查指南。
- `SCRmonitor/migrations/README.md`: SQLite migration 规则。
- `SCRmonitor/packaging/README_PACKAGING.md`: 打包说明。
- `SCRmonitor/packaging/installer/README_INSTALLER.md`: installer 构建说明。

