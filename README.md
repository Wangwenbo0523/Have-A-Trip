# Have-A-Trip · 景点大全

一个以「景点档案 + 推荐」为核心的旅游应用。**只做景点介绍、检索与推荐——不做地图，不做定位。**

前端是 React 单页应用，后端是 FastAPI，数据在 PostgreSQL，推荐结果由离线任务（RecBole）批量算好写回。
没有地图 SDK，没有地理围栏，没有轨迹上报。

## 现在能跑到什么程度

| 模块 | 状态 | 说明 |
|---|---|---|
| `db/` | ✅ | 9 张表 + 视图 + 触发器，幂等可重复执行；50 个景点、19 个标签 |
| `backend/` | ✅ | 景点列表/详情/搜索、分类标签、来源与许可、行为埋点、推荐接口；65 用例通过 |
| `frontend/` | ✅ | 首页、全部景点、分类页、详情页、搜索、数据来源与许可页、错误态；28 用例通过 |
| `recsys/` | ✅ | 三条脚本（导出 → 训练 → 回写）端到端跑通，BPR 离线结果已写回 `rec_result` |
| 数据量 | ✅ | 50 个景点 / 19 个标签，覆盖 21 个省级行政区，全部自采（`license` 为 MIT） |

施工顺序、依赖关系与每步验收标准见 **[`docs/PLAN.md`](docs/PLAN.md)（施工计划表）**。

## 基底

| | 干什么 | 在哪 |
|---|---|---|
| [travel-guide](https://github.com/zero-to-mastery/travel-guide) | 前端基底（已 vendor，会改） | `frontend/` |
| [RecBole](https://github.com/RUCAIBox/RecBole) | 推荐引擎（当依赖，不改） | `recsys/` 调用层 |

完整清单、文件级复用映射、以及**为什么 RecBole 必须跑在独立 Python 3.11 环境**，见 `docs/BASES.md`。

## 架构

```
前端 React (frontend/)  React 19 + Vite + react-router
      |  HTTP / axios  /api/v1
      v
API 服务  FastAPI  Python 3.13     <-- 不 import recbole, 只读推荐结果表
      |            冷启动走内容相似度 -> 热门兜底
      v
PostgreSQL   景点档案 / 用户行为日志 / 推荐结果表
      ^
      |  离线批量写入
离线训练任务  Python 3.11 独立环境 + RecBole 1.2.1
```

推荐引擎与 API 环境**物理隔离**：RecBole 的依赖（`ray<=2.6.3`、`hyperopt==0.2.5`）把 Python 上限锁在 3.11，
和 API 的 3.13 不可能共存。隔离开还带来一个好处——训练挂了不影响线上服务。

## 目录

| 路径 | 说明 |
|---|---|
| `frontend/` | React 前端（MIT 基底，已摘除嵌套 .git），见 `frontend/README.md` |
| `backend/` | FastAPI 服务与测试，见 `backend/README.md` |
| `db/` | `schema.sql` + 种子数据 + 字段口径，见 `db/README.md` |
| `recsys/` | RecBole 调用层：依赖钉版、训练配置、离线脚本，见 `recsys/README.md` |
| `scripts/` | 基底钉版记录、许可证卡口、DCO 校验、站点图标生成（`make_favicon.py`） |
| `docs/` | `PLAN.md` 施工计划、`BASES.md` 基底清单、`LICENSE-AUDIT.md` 许可审查、`DEPLOY.md` 部署 |

## 快速起步

需要：Python 3.13、Node 24、PostgreSQL 16。

```bash
# 1. 数据库
createdb attraction_atlas
psql -d attraction_atlas -f db/schema.sql
psql -d attraction_atlas -f db/seed/seed.sql

# 2. 后端 (http://127.0.0.1:8000, 文档 /docs)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env          # 按需改 DATABASE_URL
.venv/Scripts/uvicorn app.main:app --reload

# 3. 前端 (http://127.0.0.1:5173)
cd frontend
npm install
npm run start                 # /api 由 vite 代理到 :8000, 本地免跨域
```

没有 PostgreSQL 也能跑测试：后端测试默认走 SQLite 内存库。生产目标仍是 PostgreSQL。

## 接口一览

前缀 `/api/v1`。契约真身是 `backend/app/schemas.py`，前端类型按它写。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 健康检查（无库时返回 `degraded` 而不是 500） |
| GET | `/attractions` | 列表：`page` `size` `category` `city` `tag` `q` `sort=rating\|newest\|name` |
| GET | `/attractions/{id_or_slug}` | 详情（含图集、标签、来源与许可） |
| GET | `/attractions/{id_or_slug}/similar` | 相似景点（内容相似度，不需要用户行为） |
| GET | `/categories`、`/tags` | 分类与标签（只统计已发布景点） |
| GET | `/sources` | 数据来源与许可：从 `attraction` / `attraction_image` 聚合，声明页据此渲染 |
| POST | `/events` | 行为埋点：`view` / `favorite` / `rate` / `share` |
| GET | `/recommendations` | 为你推荐，`user_id` 与 `device_id` 二选一 |

`status != published` 的景点不会出现在任何接口与推荐里。`/recommendations` 保证非空：
离线结果 → 内容相似度 → 热门兜底，三级降级，每条都带 `reason`。

## 许可证纪律（重要）

「将来能闭源」靠纪律维持，不是靠运气：

```bash
python scripts/license_gate.py --strict    # 用装了项目依赖的解释器跑, 见下
```

检出 GPL/AGPL/SSPL/CC-BY-NC 即失败，CI 也跑同一个脚本（`.github/workflows/license-gate.yml`）。
当前状态：0 违禁，15 项告警（`certifi` 与 `lightningcss` 及其平台包共 13 项 MPL-2.0，
`psycopg` / `psycopg-binary` 2 项 LGPL）——都是未修改使用的依赖，不触发义务。

> 卡口扫的是**运行它的解释器里已安装的包**。用别的虚拟环境（比如自己装过 GPL 工具的）去跑会误报，
> 请用与 CI 一致的环境（`pip install -r backend/requirements.txt`）。

另外三件事必须从第一天做起，否则将来闭源要回头求人：

1. **贡献者签 DCO**（见 `CONTRIBUTING.md`）——没有版权集中，闭源需征得每个贡献者同意。
   CI 的 `dco` 工作流会逐个 commit 校验，`python scripts/check_dco.py` 也能本地跑。
2. **数据层许可单独审**——OSM 是 ODbL、CC BY-SA 有相同方式共享义务，代码干净不代表数据干净。
3. **图片同样算资产**——页头那张来源无从查证的实景照片已经删掉换成 CSS 渐变，见 `docs/LICENSE-AUDIT.md` 第五节。

> 根目录 `LICENSE` 为 **MIT**（2026-09-25 由建仓时默认的 Unlicense 换入——Unlicense 会把版权永久奉献给公有领域，与「将来可能闭源」直接冲突）。
> 两个基底各自为 MIT，`frontend/LICENSE` 已随源码保留——MIT 要求保留该版权声明，不能删除。已发布的旧版本仍受当时许可约束，这不影响后续版本。
> 以上是工程判断，不构成法律意见。

## 已定的决策

| # | 问题 | 结论 |
|---|---|---|
| 1 | 项目名 | **Have-A-Trip**（沿用仓库名）。前端名字集中在 `frontend/src/config.ts`，改名只改一处 |
| 2 | 前端测试框架 | **Vitest**（与 Vite 8 原生搭配），CI 里真跑断言；CRA 时代的 `App.test.js` 已删 |
| 3 | 数据库 | 生产 PostgreSQL，测试 SQLite 内存库（模型用类型变体兼容两边） |
| 4 | 部署形态 | 前端静态产物 + API 进程 + PostgreSQL，见 `docs/DEPLOY.md` |

## 相关文档

- `docs/PLAN.md` —— 施工计划表，每步的上下文、任务、验收标准
- `docs/BASES.md` —— 基底清单、文件级复用映射、上游遗留问题
- `docs/LICENSE-AUDIT.md` —— 许可审查：代码层红线、数据层风险、图片资产
- `docs/DEPLOY.md` —— 部署形态与步骤
