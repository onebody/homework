---
kind: dependency_management
name: Python 依赖管理（requirements.txt + venv）
category: dependency_management
scope:
    - '**'
source_files:
    - summer-homework-checkin/backend/requirements.txt
    - summer-homework-checkin/.gitignore
    - summer-homework-checkin/README.md
    - points-system/backend/run.py
---

本仓库包含两个独立的 Python FastAPI 后端子模块，均使用最基础的 pip + requirements.txt 方式管理第三方依赖，未引入 Poetry、pipenv、uv 等现代工具，也未使用 lockfile 或 vendoring。

1. 使用的系统与工具
- 包管理器：pip
- 依赖声明文件：summer-homework-checkin/backend/requirements.txt
- 虚拟环境：python -m venv venv（README 中给出标准流程）
- 无 package.json、go.mod、Cargo.toml、pyproject.toml、Pipfile、poetry.lock、uv.lock 等任何其它语言/工具的依赖清单；前端与游戏均为纯静态 HTML/CSS/JS，不经过构建器。

2. 关键文件与包
- summer-homework-checkin/backend/requirements.txt：唯一集中声明所有 Python 依赖的位置，包括 Web 框架（fastapi>=0.110、uvicorn[standard]>=0.27）、数据库（SQLAlchemy>=2.0）、人脸识别链路（insightface>=0.7、onnxruntime>=1.16、opencv-python-headless>=4.9、numpy>=1.24、pillow>=10.0）、上传支持（python-multipart>=0.0.9）。
- summer-homework-checkin/.gitignore 忽略 venv/，避免将虚拟环境提交到版本库。
- summer-homework-checkin/README.md 提供标准安装步骤：创建 venv、激活、pip install -r requirements.txt。
- points-system/backend/run.py 通过 import uvicorn 启动服务，但该子模块未在仓库中附带 requirements.txt，依赖来源不明。

3. 架构与约定
- 每个后端子模块独立维护自己的依赖集，不存在跨模块共享的顶层依赖清单。
- 仅使用 >= 宽松版本约束，未锁定具体版本号，也不存在 requirements.in / requirements-dev.txt 等分层清单。
- 无人工 vendoring（无 vendor/ 目录），无私有 PyPI 源配置（未见 pip.conf、setup.cfg、pyproject.toml 中的 index-url）。
- 无 Dockerfile / docker-compose / CI 流水线，部署时依赖宿主机自行执行 README 中的安装命令。

4. 开发者应遵循的规则
- 新增 Python 依赖必须同步写入 summer-homework-checkin/backend/requirements.txt，并采用 >=X.Y 形式记录最低兼容版本。
- 本地开发一律通过 python -m venv venv && source venv/bin/activate 隔离环境，不要全局安装项目依赖。
- 如需为 points-system 补充依赖清单，应在其 backend/ 下新建 requirements.txt 以保持与打卡系统一致。
- 当前仓库未使用 lockfile，升级依赖时应手动验证各子模块仍可正常运行后再更新 requirements.txt。