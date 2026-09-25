# 施工计划表 · Have-A-Trip（景点大全）

> **目标**：做一个「景点档案 + 推荐」的应用——只做景点介绍、搜索与推荐，**不做地图跟踪**。
> **版本**：v1 · 2026-09-25 · 基线 commit `88a15f1`
> **执行方式**：每一步都能独立开工（自带上下文简报，不需要读前面的步骤）。改步骤先改本文件，再动代码。

---

## 一、范围

### 做

| # | 能力 | 说明 |
|---|---|---|
| 1 | 景点档案 | 名称、简介、图文、分类、标签、城市、评分、游览信息 |
| 2 | 浏览与检索 | 列表分页、按分类/城市/标签筛选、关键字搜索 |
| 3 | 推荐 | 有行为数据时走 RecBole 离线结果；冷启动走内容相似度兜底 |
| 4 | 行为采集 | 浏览/收藏/评分的埋点入库，作为推荐原料（只记录行为，不做定位） |
| 6 | 动态区 | 用户发文字动态，可选挂一个景点；列表可按景点或按设备筛选，作者可删自己的（v4.0） |
| 5 | AI 四件套 | 一句话检索 / 详情页追问 / 推荐理由润色：模型只「解析条件」或「复述已有档案」，不产出景点内容；离线简介草稿**人审后入库**（S9） |

### 明确不做（非目标）

| 不做 | 原因 |
|---|---|
| 地图、定位、轨迹 | 需求明确排除。`ol` 依赖与 `MapView/*` 在 S3 删除 |
| 路线规划、导航、订票、支付 | 与「景点大全」无关，且都是长期维护负担 |
| 浏览器定位权限 | `navigator.geolocation` 已删（commit `2f8ae7f`），后续任何改动都不得引入 |
| 用户上传图片、账号体系、动态的自动审核 | 动态区只收**文字**（可挂一个景点）：没有图片上传、没有手机号/密码、没有机审。下架靠运营 `update post set status='hidden'`。这条在 v4.0 显式改写，边界见该条 |
| 模型直写数据库 | 简介草稿只出「待审 SQL」（`db/seed/drafts/`，不入版本库），入的是人核对过的句子 |

> **关于经纬度**：`attraction` 表仍保留 `lat` / `lon`，但它只参与「同城聚合」「同城推荐」这类**静态数据计算**，
> 与地图渲染和实时定位无关。这是一条刻意划出的边界，不是地图功能的伏笔。

---

## 二、起点基线（写这份计划时的状态；已经推进，每步的「实际做了什么」里是结果）

| 项 | 状态 |
|---|---|
| 仓库 | [Wangwenbo0523/Have-A-Trip](https://github.com/Wangwenbo0523/Have-A-Trip)，公开，`main` 与本地同步 |
| 根许可证 | MIT（2026-09-25 由 Unlicense 换入，见 `docs/LICENSE-AUDIT.md` 三·五） |
| 前端基底 | `frontend/`（vendor 自 travel-guide，MIT），38 文件 / 1.01 MB，`npm run build` 通过 |
| 推荐引擎 | `recsys/`（RecBole 1.2.1，MIT，pip 依赖 + 配置），未 vendor 源码 |
| 许可证卡口 | `scripts/license_gate.py`，CI 通过；0 违禁，13 项 MPL 告警，4 项已登记未标注 |
| 数据库 | `db/` **空目录** |
| 后端 | `backend/` **不存在** |

---

## 三、任务总览（计划表）

**执行顺序已定**（2026-09-25）：`S0 → S3 → S1 → S2 → S4 → S8 → S7 → S6`；`ecc-universal` 最后装。
也就是说先打地基与清理（S0 数据模型、S3 前端去地图化），再做后端与推荐，最后收尾。

下表按**执行顺序**排列（步骤编号是稳定标识，不代表先后）：

| 步骤 | 任务 | 主要产出 | 前置 | 并行组 | 关键验收 | 提交前缀 | 状态 |
|---|---|---|---|---|---|---|---|
| **S0** | 数据模型 | `db/schema.sql`、`db/seed/seed.sql`、`db/README.md` | — | G1 | 幂等可重复执行；外键与索引齐；种子数据可查 | `feat(db):` | ✅ `2f80afc` |
| **S3** | 前端去地图化 | 删 `MapView/`、`ol`、`registerServiceWorker.js`；清空卡口白名单 | — | G1 | 构建通过；`ol`/`MapView` 无残留；卡口 0 未标注项 | `refactor(frontend):` | ✅ `7361ce7` |
| **S1** | 后端骨架 | `backend/app/**`、`requirements.txt`、`tests/**` | S0 | G2 | `uvicorn` 起得来；`pytest` 通过；**不 import recbole** | `feat(api):` | ✅ `2802594` |
| **S2** | 推荐接口 + 冷启动 | `backend/app/recommend/*` | S1 | G3 | 无行为的新用户也能拿到非空推荐，且每条带 `reason` | `feat(rec):` | ✅ `29069bb` |
| **S4** | 前端 Attraction 化 | `types/index.ts` 重写、`Attraction*` 组件、`api/client.ts` | S1、S3 | G3 | 首页/分类/详情/搜索可用；无 `Country` 残留 | `feat(web):` | ✅ 本次提交 |
| **S6** | 离线训练链路 | `recsys/{common,export_interactions,run_recbole,write_back}.py` | S0 | G4 | 三条脚本端到端跑通，`rec_result` 有数据 | `feat(recsys):` | ✅ 本次提交 |
| **S7** | 内容与数据 | `db/seed/*.sql`（30–50 个景点）+ 来源清单 | S0 | G4 | 每个景点 `source` / `license` 非空且可用 | `data(seed):` | ✅ 本次提交 |
| **S5** | 数据来源与许可声明页 | `frontend/src/components/Credits.tsx` 改造 + `GET /api/v1/sources` | S4、S7 | G5 | 页面逐条列出来源与许可，与 S7 一致 | `feat(web):` | ✅ 本次提交 |
| **S8** | 工程化收尾 | CI 增 build/test、`README`、部署说明 | S2、S4、S6 | G6 | CI 三条工作流全绿且**真的会**变红 | `chore(ci):` | ✅ 本次提交 |
| **S9** | AI 接入（四刀） | `backend/app/llm/*`、`backend/app/api/ai.py`、`tests/test_ai*.py`、`scripts/draft_attraction_summaries.py` | S1、S4 | G7 | 默认不配模型也能跑；模型只解析需求、不产出景点 | `feat(ai):` | ✅ 四刀全部完成 |
| **S10** | 语义检索 + 行程生成 | `backend/app/search/*`、`backend/app/trip/*`、`backend/app/llm/embedding.py`、`app/api/{search,itineraries}.py`、`scripts/build_embeddings.py` | S9 | G8 | 向量可用时按语义召回、不可用时退回关键词；行程只能从候选集里挑景点 | `feat(ai):` | ✅ 本次提交 |

---

## 四、依赖图与并行安排

```
G1        S0 (数据模型)          S3 (前端去地图)
           |                       |
G2         +------> S1 (后端骨架) <--+   S3 独立, 可与 S0/S1 并行
           |          |
G3         |          +--> S2 (推荐+冷启动)
           |          +--> S4 (前端 Attraction 化)   <-- S4 依赖 S1 的接口契约, 不依赖 S1 完成
           |
G4         +--> S6 (离线训练)     S7 (内容与数据)
           |          |                  |
G5         |          |                  +--> S5 (许可声明页) <-- 也依赖 S4
G6         +----------+------------------+--> S8 (工程化收尾)
```

**并行机会**

| 组 | 可并行的步骤 | 说明 |
|---|---|---|
| G1 | S0 ∥ S3 | 互不相干：一个是 SQL，一个是删前端地图 |
| G3 | S2 ∥ S4 | 只要 S1 的接口契约先冻结，两边可同时开工 |
| G4 | S6 ∥ S7 | 训练脚本用种子数据就能跑；内容整理独立进行 |
| G7 | S9 ∥ 其余 | 后三刀（详情页追问 / 推荐理由润色 / 离线批量生成）互不依赖，可分别开工 |

**关键路径**：`S0 → S1 → S2 → S8`。S3/S4/S5 不在关键路径上，晚做不会拖整体。

**S9 的位置**：`S9`（AI 接入）是计划外追加的一步（2026-09-25，用户提出「接入 AI 大模型」）。
它只依赖 S1 的查询契约与 S4 的页面，**不改变已定的关键路径**，也不阻塞其余步骤。

---

## 五、每步执行简报

### S0 · 数据模型

**上下文**：`db/` 目前是空目录。这是全项目地基——S1 的实体、S2 的推荐结果、S6 的交互导出都读它，所以**先冻结表结构再写代码**，避免接口写完又改字段。

**任务清单**

1. `db/schema.sql`：9 张表（见下表）+ 迁移记录表
2. `db/seed/seed.sql`：分类、标签、3 个示例景点（够跑通接口，不追求内容量；S7 已扩到 50 个）
3. `db/README.md`：怎么建库、怎么执行、字段口径说明

**表设计**（S0 冻结的是下面这 9 张；后续各步新增的见 `db/README.md`，目前共 15 张）

| 表 | 作用 | 关键字段 |
|---|---|---|
| `attraction` | 景点档案主表 | `id, slug, name, name_en, summary, description, category_id, country_code, city, address, lat, lon, best_season, suggested_hours, ticket_price, rating_avg, rating_count, cover_image, status, source, license, created_at, updated_at` |
| `category` | 分类（自然风光 / 历史古迹 / 博物馆 / 主题乐园…） | `id, slug, name, parent_id, sort` |
| `tag` | 自由标签（亲子 / 免票 / 日出 / 徒步…） | `id, slug, name` |
| `attraction_tag` | 景点-标签多对多 | `attraction_id, tag_id` |
| `attraction_image` | 图集（每条带署名） | `id, attraction_id, url, caption, credit, license, sort` |
| `app_user` | 用户（一期只做匿名 `device_id`） | `id, device_id, nickname, created_at` |
| `behavior_log` | 行为日志，推荐的原料 | `id, user_id, attraction_id, event_type, rating, dwell_ms, created_at` |
| `rec_result` | 推荐结果表，**API 只读它** | `id, user_id, attraction_id, score, rank, algo, reason, batch_id, generated_at` |
| `schema_version` | 迁移记录 | `version, applied_at` |

**字段口径（现在定死，后面不返工）**

- `source` / `license` 对每个景点**必填**：数据来源与许可。S5 的声明页直接由它聚合生成，这是「将来闭源」的数据层保险。
- `status`：`draft / published / archived`。非 `published` 的景点不得出现在任何接口与推荐里。
- `behavior_log.event_type`：`view / favorite / rate / share`，与 `recsys` 导出的字段对齐（`rating` 只有 `rate` 有值）。
- `rec_result.rank` 从 1 开始；**API 按 `rank` 升序返回，不按 `score` 排序**——不同算法的分数不可比。

**验证命令**

```bash
createdb attraction_atlas
psql -d attraction_atlas -f db/schema.sql
psql -d attraction_atlas -f db/schema.sql     # 再跑一次, 验证幂等
psql -d attraction_atlas -f db/seed/seed.sql
psql -d attraction_atlas -c "select count(*) from attraction;"   # 应 > 0
```

**退出标准**

- [ ] `schema.sql` 连跑两次不报错（`CREATE TABLE IF NOT EXISTS` + 幂等索引）
- [ ] 所有外键有明确 `ON DELETE` 行为；`slug`、`category_id`、`city`、`attraction_id`、`rec_result(user_id, rank)` 有索引
- [ ] 种子数据可查，`source` / `license` 无空值
- [ ] `db/README.md` 说明清楚字段口径

**注意**：只有 `schema.sql` 与自采种子数据进仓库；真实景点数据按 `docs/LICENSE-AUDIT.md` 第三节隔离（`data/`、`dataset/` 已在 `.gitignore`）。
---

### S1 · 后端骨架（FastAPI）

**上下文**：`backend/` 尚不存在。API 跑 **Python 3.13**，且**绝不 import recbole**——RecBole 的 `ray<=2.6.3` / `hyperopt==0.2.5` 把 Python 上限锁在 3.11，两者不可能共存（理由见 `docs/BASES.md`）。API 只读 `rec_result` 表。

**任务清单**

1. 目录：`backend/app/{main.py, config.py, db.py, models.py, schemas.py}`、`backend/app/api/{attractions.py, categories.py, events.py, recommendations.py}`、`backend/tests/`
2. `backend/requirements.txt` 钉版：`fastapi`、`uvicorn[standard]`、`sqlalchemy`、`psycopg[binary]`、`pydantic-settings`、`pytest`、`httpx`
3. `GET /api/v1/healthz`
4. `GET /api/v1/attractions`：分页 `page/size`，筛选 `category/city/tag`，搜索 `q`（匹配 `name`/`summary`），排序 `sort=rating|newest`
5. `GET /api/v1/attractions/{id_or_slug}`：详情含图集与标签
6. `GET /api/v1/categories`、`GET /api/v1/tags`
7. `GET /api/v1/attractions/{id}/similar`：同分类 + 标签重合 + 同城 的内容相似度（S2 复用）
8. `POST /api/v1/events`：写 `behavior_log`
9. `.env.example`（`DATABASE_URL`）、`backend/README.md`（起服务、连库、跑测试）

**接口契约**（S4 前端按这个开工，不必等后端写完）

```json
GET /api/v1/attractions?page=1&size=20&category=nature&city=hangzhou&q=西湖
{
  "items": [{
    "id": 1, "slug": "west-lake", "name": "西湖", "summary": "...",
    "category": {"slug": "nature", "name": "自然风光"},
    "city": "杭州", "tags": ["免票", "日出"],
    "cover_image": "/img/west-lake.jpg",
    "rating_avg": 4.7, "rating_count": 128
  }],
  "page": 1, "size": 20, "total": 137
}
```

**验证命令**

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
curl http://127.0.0.1:8000/api/v1/healthz
.venv\Scripts\pytest -q
```

**退出标准**

- [ ] OpenAPI 文档可访问，每个接口都有 response schema
- [ ] `pytest` 通过，至少覆盖：列表分页、搜索命中、详情 404
- [ ] `rg "recbole" backend` 无结果（这条以后要写进 CI 断言）
- [ ] `status != published` 的景点不出现在任何接口

---

### S2 · 推荐接口 + 内容相似度冷启动

**上下文**：推荐走两条路。有行为数据时读 `rec_result`（S6 离线写入）；没有时**不能返回空**，改用内容相似度兜底。这个兜底是一期体验的关键——冷启动阶段必然没有用户行为，纯协同过滤一定推荐不出东西。

**任务清单**

1. `backend/app/recommend/service.py`：`get_recommendations(user_id, limit)`，先按 `rank` 查 `rec_result`，为空则走内容相似度
2. `backend/app/recommend/content_based.py`：标签重合度 + 同分类 + 同城 加权打分，权重走配置
3. 每条结果带 `reason`（如「因为你收藏过同类自然风光景点」「杭州热门」）
4. `GET /api/v1/recommendations?user_id=&limit=10`
5. 同一 `user_id` 的结果做短 TTL 内存缓存（先不引 Redis）

**验证命令**

```bash
curl "http://127.0.0.1:8000/api/v1/recommendations?limit=5"            # 无 user_id / 新用户
curl "http://127.0.0.1:8000/api/v1/recommendations?user_id=1&limit=5"
cd backend && .venv\Scripts\pytest -q tests/test_recommend.py
```

**退出标准**

- [ ] 无任何行为的新用户返回**非空**推荐（走内容兜底），不是 500，也不是 `[]`
- [ ] `rec_result` 有数据时优先采纳，返回顺序等于 `rank` 升序
- [ ] 每条结果都有非空 `reason`
- [ ] 本地 1 万景点以内，单次请求 P95 < 100 ms

---

### S3 · 前端去地图化

**上下文**：`frontend/` 现在还带 OpenLayers：`src/components/MapView/MapView.tsx` 与 `MapView.css`，被 `routes/AppRouter.tsx`、`components/CountryDetails/Detail.tsx` 引用，`Header.tsx` 里还有 `Map` 导航项。地图是明确非目标；而且 `ol` 拖进来 4 个**无许可证标注**的包，逼着许可证卡口维护一份白名单。

**任务清单**

1. 删 `frontend/src/components/MapView/`（`MapView.tsx` + `MapView.css`）
2. `routes/AppRouter.tsx`：去掉 `/map` 路由与 `WorldMap` import
3. `components/CountryDetails/Detail.tsx`：去掉 `CountryMap` import 与用法
4. `components/Header.tsx`：去掉导航里的 `Map` 项
5. `package.json`：删 `ol`；`npm.cmd install --package-lock-only` 重生成 lock
6. `scripts/license_gate.py`：删掉 `KNOWN_UNLABELED` 里那 4 个包，并同步 `docs/LICENSE-AUDIT.md`（第一节的「4 项未标注许可」整段随之失效）
7. 删 `src/registerServiceWorker.js` 及 `index.tsx` 里的引用（将来要做 PWA 再单独加）

**验证命令**

```bash
cd frontend
npm.cmd install --package-lock-only
npm.cmd run build
cd ..
python scripts/license_gate.py --strict
rg -n "components/MapView|WorldMap|registerServiceWorker" frontend/src    # 应为空
rg -n "\"ol\"|ol/ol.css|ol-mapbox-style|mapbox-gl-style-spec" frontend     # 应为空
```

**退出标准**

- [ ] `ol` 与 `MapView` 在 `frontend/` 无任何残留（含 lock 文件）
- [ ] `npm run build` 通过，产物里不含地图相关 chunk
- [ ] 卡口输出「未标注许可 0 项」，且「已登记」段落消失
- [ ] `docs/LICENSE-AUDIT.md` 与代码同步更新

---

### S4 · 前端 Attraction 化

**上下文**：文件级改造映射表见 `docs/BASES.md`。前端目前承载的是**国家**模型（数据来自 `restcountries.com`），要整体换成 `attraction` 模型 + 自家 API。**S1 的接口契约先冻结，S4 就能与 S1 并行开工。**

**任务清单**

1. `src/types/index.ts` 重写：删 `Country`，加 `Attraction`、`Category`、`Tag`、`Paged<T>`，与 S1 契约一一对应
2. 新增 `src/api/client.ts`（axios 实例 + `VITE_API_BASE`）；删掉 `App.tsx` 里对 `restcountries.com` 的调用
3. `RegionList.tsx` + `RegionCard.tsx` → `AttractionList.tsx` + `AttractionCard.tsx`
4. `CountryCard.tsx` → `CategoryCard.tsx`；`Region.tsx` → `CategoryPage.tsx`
5. `CountryDetails/Detail.tsx` → `AttractionDetail.tsx`（简介、图集、标签、评分、相似推荐位）
6. `routes/AppRouter.tsx` 路由表：`/`、`/category/:slug`、`/attraction/:slug`、`/credits`
7. `SearchBox.tsx` 接上 `q` 参数
8. 保留 `Header.tsx`、`Footer.tsx`、`utils/Loader.tsx`、`react-spinners`、`aos`、`tachyons`

**验证命令**

```bash
cd frontend
npm.cmd run build
rg -n "restcountries|Country" src      # 应为空
npm.cmd run dev                        # 手动过一遍: 首页 -> 分类 -> 详情 -> 搜索
```

**退出标准（2026-09-25 全部达成）**

- [x] 首页景点卡片流、分类页、详情页、搜索四条路径都可用 —— 用浏览器实测过，见下方「验证记录」
- [x] `src` 内无 `Country` / `restcountries` 残留
- [x] `npm run build` 通过（131 modules，JS 315.19 KB / gzip 102.62 KB，CSS 106.97 KB）
- [x] 后端未启动时页面给出明确错误态，不是白屏
- [x] 额外：`npx tsc --noEmit` 零错误（构建本身不跑 tsc，得单独查）

**与计划的偏差**：多拆了一个 `AttractionBrowser`（搜索 + 排序 + 分页的列表主体），
`/attractions` 与 `/category/:slug` 共用它；路由多了 `/attractions` 与 404 兜底。
`Footer.tsx` / `Header.tsx` 不是「保留」而是重写（上游的社交链指向原作者账号，giphy iframe 也不该留）。
`tachyons` 仍然保留（`Credits.tsx` 在用）。详见 `docs/BASES.md` 一节的「S4 实际落地」。

**验证记录**：用 SQLite 起真实后端（`uvicorn`）+ `vite` dev server + 内置浏览器实测 ——
首页推荐位带理由渲染、`/category/history` 出 2 个景点、`/attraction/west-lake` 详情完整、
搜索 `West` 命中「西湖」（验 `name_en` 匹配）、搜索无结果出空态、`/attraction/does-not-exist` 出错误态、
详情页浏览行为落进 `behavior_log`，随后推荐从 `popular-fallback` 自动切成内容相似并给出「因为它和你浏览过的「西湖」相似」。
控制台无报错（AOS 修复生效）。

---

### S5 · 数据来源与许可声明页

**上下文**：`Credits.tsx` 现在是上游的「素材致谢」。它必须改成**数据来源与许可声明页**——用了 ODbL（OSM）、CC BY-SA 的数据就有署名与标注义务，这是许可要求，不是可选项。

**任务清单**

1. 来源数据不手写：从 `db` 的 `source` / `license` 字段聚合（或构建期生成 JSON），避免页面与数据漂移
2. 逐条列出：来源名称、许可、链接、**是否修改过**（ODbL 明确要求标注）
3. 静态素材（字体、图标、图片）与代码依赖的许可分开列
4. 路由挂在 `/credits`，页脚已有入口

**实际做了什么**

| 项 | 结果 |
|---|---|
| 数据怎么来 | 新增 `GET /api/v1/sources`（`backend/app/api/sources.py`），每次从 `attraction` / `attraction_image` **现算**，前端不持有清单。这样引入新来源时页面自己会变，不靠谁记得改前端 |
| 页面 | `Credits.tsx` 从「上游贡献者致谢墙」重写成四段：景点数据来源、图片署名、代码与静态素材、这个应用不做什么。前两段走接口，后两段是仓库里的文件，接口挂了也照常显示 |
| 修改状态 | 许可判定为 share-alike（ODbL / CC BY-SA）时，必须在本项目自己维护的 `SOURCE_MODIFICATIONS` 里登记「已修改 / 未修改」；没登记就返回 `unregistered`，页面顶部弹红色告警。**这是把「别忘了标注」变成会红的闸，而不是写进文档的提醒** |
| 不适用则明说 | 不含 share-alike 义务的许可（MIT / CC0 / CC BY…）显示「无需标注」，不是留空 —— 空着会被误读成「忘了填」 |
| 图片 | 目前 `attraction_image` 是 0 行，页面给空态并说明原因（查不到出处的图不进仓库），而不是给一张空表格 |
| 样式 | `credits.css` 一并重写：上游那套贡献者卡片样式全部删掉。表格用「容器横向滚动 + `min-width`」兜窄屏 —— 试过 `table { display: block }`，会把「来源」列压成一列一个字 |

**验证记录**：本机 PostgreSQL 16.2 + `uvicorn` + `vite` dev server + 内置浏览器实测。页面显示
「Have-A-Trip 自采（公开事实信息） / MIT / 50 / 21 / 无需标注」，与 `db/README.md` 的聚合口径一致；
往库里临时插一条 `source='OpenStreetMap'`、`license='ODbL 1.0'` 的景点后刷新，顶部红色告警与表里的
「未登记」都如期出现，随后删除该行复原。接口挂掉时给出错误态 + 重试，代码与静态素材段落不受影响。

**退出标准（2026-09-25 全部达成）**

- [x] S7 种子数据里出现过的每个 `source` 都在页面上有对应条目 —— 页面就是按 `source` 聚合出来的，不是人工抄的
- [x] ODbL / CC BY-SA 来源标注了「已修改 / 未修改」—— 现在库里没有这类来源；一旦有，未登记会在页面上标红（已用临时数据实测）
- [x] 页面内容与 `docs/LICENSE-AUDIT.md` 第三节的数据源表一致 —— 两边都指向同一个聚合口径，且该节已补上「声明页已上线 + 登记闸在哪」

**与计划的偏差**：计划里只写了改 `Credits.tsx`。为了让「不手写」成立，多加了后端接口
`GET /api/v1/sources`（9 个新测试覆盖它），并把「是否修改过」做成会红的闸而不是文档提醒。

---

### S6 · 离线训练链路

**上下文**：`recsys/` 现在只有 `README.md`、`requirements.txt`、`config/recbole.yaml`，三个脚本是 README 里已经承诺的流程。**必须在独立 Python 3.11 环境跑**，与 API 的 3.13 物理隔离。

**任务清单**

1. `recsys/export_interactions.py`：从 `behavior_log` 导出 `.inter`（`user_id, attraction_id, rating, timestamp`），字段与 `config/recbole.yaml` 对齐
2. `recsys/run_recbole.py`：读 `config/recbole.yaml` 训练，起步模型 `BPR`（数据量小，深度模型只会过拟合）
3. `recsys/write_back.py`：TopN 写回 `rec_result`（带 `algo`、`batch_id`、`generated_at`），按 `batch_id` 原子切换，训练失败不影响线上已有结果
4. `recsys/README.md` 补完整命令序列
5. 交互量不足时（低于 `item_inter_num_interval: [5, inf)`）明确跳过并打印原因，**不要产出垃圾推荐**

**实际做了什么**

| 项 | 结果 |
|---|---|
| 脚本 | 拆成 4 个文件：`common.py`（连库 / 路径 / 批次号 / 「行为 → 隐式强度」口径）+ 原计划的三条脚本 |
| 导出 | 每个 `(用户, 景点)` 只取**最后一次**行为（窗口函数），与 `backend/app/aggregates.py` 重算评分的口径一致；只导 `status='published'` 的景点 |
| 强度口径 | `rate` 用实际分，`favorite` 4.0、`share` 3.0、`view` 按停留是否 ≥ 30s 记 2.0 / 1.0。**这不是评分**，只喂模型，不写回任何用户可见字段 |
| 训练 | BPR 起步。`run_recbole.py` 不走 `load_data_and_model`（torch ≥ 2.6 的 `weights_only` 默认值会炸），自己 `torch.load(..., weights_only=False)` + 重建 config/dataset/model，再 `full_sort_topk` 打分（自带把该用户历史景点置 `-inf`） |
| 跳过语义 | 数据量低于门槛（交互 200 / 用户 20 / 景点 20）就打印 `SKIP` 并**以退出码 0 结束** —— 对 cron 来说「没到火候」不是失败 |
| 回写 | 一个事务：先按 `batch_id` 删掉自己（重跑幂等）→ 整体插入 → 清掉同用户**更旧**的批次。`generated_at` 整批共用一个值，API 的 `max(generated_at)` 才能干净切换 |
| 死链校验 | 只保留「用户存在」+「景点 `published`」的行，丢掉的打日志。训练完景点被下架是常态，推出去没有意义 |
| 上游坑 | `setuptools` ≥ 81 删 `pkg_resources` 打到 `ray`；numpy 2 删 `np.bool8` 打到 `ray` 的 tensorboard logger；torch ≥ 2.6 的 `weights_only` 打到 RecBole 的 checkpoint；`config["encoding"]` 默认 `None` 会回落 GBK 打到中文城市名。四个都钉进 `requirements.txt` / `recbole.yaml` 并写明原因 |
| 野日志 | RecBole 的 `init_logger` 硬编码 `LOGROOT = "./log/"`（完全不看 `config["log_dir"]`），tensorboard 也用 cwd 相对路径。`run_recbole.py` 先 `os.chdir()` 到批次目录，让它们落进 `recsys/output/<batch_id>/`，而不是在仓库根拉出两个野目录 |

**实际跑出来的数据**（本机 PostgreSQL 16.2，`--epochs 3` 冒烟；测试行为由临时夹具灌入，不入库）

| 项 | 结果 |
|---|---|
| 导出 | 770 条交互 / 42 用户 / 50 景点；事件构成 `favorite 236, rate 255, share 75, view 204` |
| 训练集过滤后 | 39 用户 / 50 景点 / 531 交互（`item_inter_num_interval` 与 `user_inter_num_interval` 都生效） |
| 指标 | 验证集 `NDCG@10 = 0.1995`、`Recall@10 = 0.359`；测试集 `NDCG@10 = 0.0815` |
| 回写 | `rec_result` 780 行 / 39 用户 / rank 1–20，`v_latest_rec` 行数一致 |
| 端到端 | 后端 `get_recommendations` 对已知用户返回 `algo = BPR`（离线结果）；未知用户与匿名访客仍走 `popular-fallback`，三级降级链完好 |
| 幂等 | 同一批次连跑两次：批次内行数不变、旧行被替换；另造一个更旧的假批次，第二次回写把它清掉 |

**退出标准（2026-09-25 全部达成）**

- [x] 三条脚本端到端跑通，`rec_result` 有数据且 `batch_id` 是新值
- [x] 训练环境为 Python 3.11（`uv` 拉的 `cpython-3.11.16`），API 环境未被污染（`backend/tests/test_no_recbole.py` 用 AST 静态查 + 运行期 `sys.modules` 双查）
- [x] 数据量不足时打印 `SKIP` 并以退出码 0 结束，不崩溃、不写空表
- [x] 训练产物（`recsys/dataset/`、`recsys/output/`、`recsys/saved/`、`log/`、`log_tensorboard/`）不进仓库

---

### S7 · 内容与数据

**上下文**：项目最大的实际风险不在代码，在**数据来源与许可**。`docs/LICENSE-AUDIT.md` 第三节已列明：OSM 是 ODbL、Wikipedia/Wikivoyage 是 CC BY-SA，都有相同方式共享义务，会顺着数据传染到你的数据库；几个现成的中文景点数据集**无许可证，不可用**。

**任务清单**

1. 一期 30–50 个景点，**优先自采或 MIT 来源**（如 `Iter-X/open-poi-datasets`）
2. 每条记录填 `source` 与 `license`（S0 已设为必填）
3. 图片同理：每条 `attraction_image` 带 `credit` 与 `license`
4. 导出「数据来源清单」供 S5 页面使用
5. 若确实要用 ODbL / CC BY-SA 数据：隔离在独立导入脚本 + 独立数据集目录，不混进种子数据

**实际做了什么**

| 项 | 结果 |
|---|---|
| 数据来源 | **全部自采**，没有引入任何第三方数据集。90 条的 `source` 都是「Have-A-Trip 自采（公开事实信息）」、`license` 为 `MIT`，因此**不存在 share-alike 传染到数据库**的问题（S7 时 50 条，v2.0 扩到 90 条） |
| 内容规模 | S7 时 50 个景点覆盖 21 个省级行政区；7 个分类（自然 12 / 历史 10 / 博物馆 6 / 地标 6 / 古镇 6 / 宗教 5 / 乐园 5）、19 个标签、175 条标签关联。**v2.0 扩到 90 个景点（境内 50 + 境外 40，六大洲 30 个国家）、9 个分类、31 个标签、362 条标签关联，并新增 90 个旅游方案 / 307 条步骤**；`a_level` 40 条、`heritage` 59 条，其余留空表示未核实 |
| 幂等写法 | `seed.sql` 改成**声明式**：分类 / 标签 / 景点用 `ON CONFLICT (slug) DO UPDATE`，标签关联按 `source` 认领后删掉重建。旧版的 `DO NOTHING` 不会修好早期跑过种子的库 |
| 不造假 | 坐标全 `NULL`、评分全 0、票价只在**确定免费**时写 `0`（v2.0 为 9 条）、`attraction_image` 一条不插（v1.9 起改为自绘封面，v2.0 为 90 张）；旅游方案只给 `budget_level` 档次不给金额 |
| CI | `db-schema.yml` 把口径变成断言：行数、无坐标、无评分、无「不确定免费」的票价、无图片、无孤立标签；另加一步**先改坏再重跑**，证明种子确实会自愈 |
| 来源清单 | `db/README.md` 新增「数据来源清单」一节：给出聚合 SQL 与当前结果，S5 的声明页从库里聚合，不在前端写死 |

**退出标准（2026-09-25 达成）**

- [x] 每个景点的 `source`、`license` 非空 —— CI 直接断言「缺 source/license 的景点数 = 0」
- [x] 没有无许可证来源的数据 —— 50 条全部自采 + MIT，第三方数据集一条没用
- [x] 若含 share-alike 数据，能明确指出它落在哪些表、哪些行 —— **不含**。ODbL / CC BY-SA 的边界与处置写在 `docs/LICENSE-AUDIT.md` 第三节，将来真要用时按那里说的隔离

---

### S8 · 工程化收尾

**任务清单**

1. CI 补齐两条工作流：`frontend-build`（`npm ci` + `npm run build`）、`backend-test`（`pytest`，Python 3.13）。许可证卡口已有
2. 前端测试：`App.test.js` 是 CRA 时代遗留，`npm test` 目前是空脚本。决定用 vitest 接管（与 Vite 8 原生搭配）还是删除该文件 —— **见待决 #2**
3. 项目名统一：`README` / `recbole.yaml` 里的 `attraction-atlas`、`frontend/package.json` 里的 `have-a-trip-frontend`、仓库名 `Have-A-Trip` —— **见待决 #1**
4. README 与实际对齐（接口列表、目录说明、起步命令）
5. 核对 `CONTRIBUTING.md` 的 DCO 说明，确认每个贡献者都签名
6. 部署说明：前端静态产物 + API 进程 + PostgreSQL

**实际做了什么**

| 项 | 结果 |
|---|---|
| CI | 新增 `frontend-build`（`npm ci` → `npm run typecheck` → `npm test` → `npm run build` → 断言 `dist/index.html` → 用地名/地图/旧数据源 `grep` 守线）；`backend-test` 与许可证卡口原本就有。**另外补了 `dco`**：`CONTRIBUTING.md` 一直写着「CI 会校验 sign-off」，但当时并没有这条工作流，属于文档撒谎，现已补上 |
| 前端测试 | Vitest 5 + jsdom + Testing Library，配置在独立的 `vitest.config.js`；`App.test.js` → `App.test.tsx`；共 21 个用例覆盖卡片字段口径、空态/错误态/重试、搜索防抖、翻页边界、`describeError` 映射、后端全挂不白屏 |
| 项目名 | 统一为 `Have-A-Trip`；前端名字集中在 `src/config.ts`。`attraction_atlas`（数据库名）作为标识符保留 |
| README | 重写：进度表、架构、目录、四步起步、接口一览、许可纪律、已定决策 |
| 部署 | 新增 `docs/DEPLOY.md`：三部件形态、环境变量、systemd 单元、nginx（含 SPA 回落）、离线任务 cron、上线检查清单 |
| 其他 | 删掉来源不明的头图；清掉 Vite 8 的废弃配置告警；`package.json` 里失效的 `gh-pages` 脚本与 CRA 的 `eslintConfig` 一并删除 |

**退出标准（2026-09-25 全部达成）**

- [x] CI 全绿，且**确实会在构建失败时变红** —— 用一个临时分支故意塞进类型错误与 `leaflet` 依赖，确认 `frontend-build` 变红后删除该分支
- [x] 新克隆仓库的人按 README 能跑起来（四步：建库 → 后端 → 前端 → 卡口；后端测试不需要 PostgreSQL）
- [x] 根 `LICENSE` 仍为 MIT、`frontend/LICENSE` 仍在（卡口会拦）

---

### S9 · AI 接入（一句话检索）

**上下文**

需求原话：「能否将我的软件接入 AI 大模型？」。范围**只要**把用户那句话变成已有的查询条件 ——
「想找杭州安静点的古迹」→ `city=杭州市` + `category=history`，再交给 `/attractions` 那套既有的查询。
不做行程规划、不做问答机器人、不做景点内容生成。

**这个设计里最重要的一条**：模型**只产出查询条件，不产出景点条目**。
景点永远由数据库检索，所以它根本没有编造景点的机会 —— 编造是这类功能最大的风险，这里从结构上消掉。

**分批交付（按此顺序，一刀一个能验的成果）**

| # | 这一刀 | 产出 | 状态 |
|---|---|---|---|
| 1 | **自然语言检索** | `app/llm/{client,interpret}.py`、`app/api/ai.py`、`tests/test_ai.py` | ✅ `b829094` |
| 2 | 详情页追问 | 把「这个景点适合带小孩吗」这类问题，答成**站内字段的复述**（适合人群 / 建议时长 / 最佳季节） | ✅ 本次 |
| 3 | 推荐理由润色 | 把 `recommend` 已给出的 `reason` 说成人话；**推荐结果本身不交给模型** | ✅ 本次 |
| 4 | 离线批量生成 | 用模型给景点补简介草稿，**人审后入库**，产物进 `db/` 而非运行时 | ✅ 本次 |

**第一刀 · 任务清单**

1. 一层抽象同时支持云端 API 与本地 Ollama（`app/llm/client.py`）：两者都是 OpenAI 兼容的
   `/chat/completions`，只改环境变量切换；默认 `LLM_PROVIDER=none`
2. 意图解析与护栏（`app/llm/interpret.py`）：白名单字段 + 取值双向校验，模型给的取值必须能在库里对上
3. 接口：`GET /api/v1/ai/status`（入口是否可用）、`POST /api/v1/ai/search`（一句话检索）
4. 降级：模型不可用 / 超时 / 返回不是 JSON → 退回关键词检索，**HTTP 200 而不是 500**
5. 测试（`backend/tests/test_ai.py`、`test_llm_client.py`）：打桩 + 本机 HTTP 服务，CI 不需要任何 key，不打**真的**模型接口
6. 文档：`.env.example` 给 ollama / deepseek 两种配法；`docs/LICENSE-AUDIT.md` 增「AI 与模型条款」

**第一刀 · 验收标准**

- [x] 默认（`LLM_PROVIDER=none`）时 `/ai/status` 的 `available=false`；`/ai/search` 仍返回 200 且 `degraded=true`
- [x] 模型给的取值在库里对不上时一律丢弃，并在 `note` 里说明丢了什么
- [x] 模型试图指定 `status`、景点名等白名单外字段时一律无效；`draft` 景点绝不出现在结果里
- [x] 模型抛错（超时 / 连不上）时降级，HTTP 200，不是 500
- [x] 超长输入被截到 60 字，不会整段塞进提示词
- [x] 提示词里只有取值清单（分类 / 标签 / 城市），**不含任何景点条目**
- [x] 不引任何模型厂商的官方 SDK；`httpx`（BSD-3）提到运行时依赖
- [x] `pytest` 通过且不需要任何 key；`license_gate.py --strict` 通过

**第一刀 · 实际做了什么**

| 项 | 结果 |
|---|---|
| 客户端 | `app/llm/client.py`：provider 预设（ollama / deepseek / openai / custom）、进程内 TTL 缓存、带 `response_format` 请求 JSON、网关不认该字段（400）时去掉重试一次 |
| 解析器 | `app/llm/interpret.py`：`PROMPT_VERSION=ai-search-v1`；提示词由库里的真实取值现拼；城市做「杭州 → 杭州市」的唯一匹配归一 |
| 接口 | `app/api/ai.py`：两个端点；查询复用 `attractions.build_query / count_of / page_of` —— 与用户手点筛选**同一条路径**，不存在「AI 专用」的宽松查询 |
| 契约 | `app/schemas.py` 增 `AIFilters` / `AISearchIn` / `AISearchOut` / `AIStatusOut`；`AISearchOut.disclaimer` 是必填字段，前端想漏掉这句也漏不掉 |
| 测试 | `backend/tests/test_ai.py` 14 个用例：可用性、三类降级、越权与编造防护、提示词不含景点名、`extract_json` 的容错 |
| 客户端测试 | `backend/tests/test_llm_client.py` 8 个用例：起一个**本机** HTTP 服务, 把 URL 拼接 / 请求体形状 / 400 重试 / 缓存 / 错误映射都走一遍真路径 |
| 依赖修正 | `httpx` 原先只在 `requirements-dev.txt` —— 而它是 AI 客户端的**运行时**依赖，只装 `requirements.txt` 的生产环境会直接 ImportError。已提到运行时依赖 |
| 实测 | `pytest`：**84 passed / 3 skipped**（后端 65 → 87 条；3 skip 是既有的 parity 用例，需 `TEST_DATABASE_URL`）。前端 Vitest：**50 passed**（41 → 50） |
| 端到端 | 真起 `uvicorn` + 一个桩模型服务（OpenAI 兼容）逐条验过：正常解析命中；模型故意给 `category=雪山` / `status=draft` / 景点名时全部被丢且 note 如实说明；`LLM_PROVIDER=none` 与「模型连不上」两条路径都是 HTTP 200 + 降级；经 vite 同源代理再跑一遍，链路通 |

**第二刀 · 实际做了什么（详情页追问）**

| 项 | 结果 |
|---|---|
| 护栏模块 | `app/llm/ask.py`：`PROMPT_VERSION=ai-ask-v1`；17 个字段白名单（`FIELD_LABELS`），空字段不进提示词 —— 档案里没有的东西，模型看不见就没法编 |
| 两关机械校验 | `verify()`：① 答案里的**每个数字**都要能在档案里找到同一个数字（票价 / 时长 / 年份 / 人数 / 评分都拦得住）；② 档案里没有依据的主题词（开放时间 / 天气 / 交通 / 预约）不许提，除非档案自己写了或是否定式提及 |
| 降级 | 模型不可用 / 超时 / 校验没过 → 换成后端拼的**档案摘录**（`fallback_answer`），仍是 HTTP 200；`grounded` / `degraded` / `note` 三个字段把「这句话是谁写的」如实告诉前端 |
| 接口与契约 | `POST /ai/ask`（slug + question，404 口径与详情页一致）；`app/schemas.py` 增 `AIAskIn` / `AIAskOut`，`disclaimer` 必填 |
| 前端 | `AiAskBox.tsx`（3 个建议问题、结果 / 降级 / 错误三态）+ 抽出的 `useAIStatus` 共享 hook；`AttractionDetail` 在事实表后挂上 |
| 测试 | `tests/test_ai_ask.py` 20 用例；前端 `AiAskBox.test.tsx` 8 用例。后端 87 → 117 |
| 端到端 | 桩模型吐「门票 60 元」被数字溯源拦下并换成档案摘录；问灵隐寺「要逛多久」吐「4 小时」被拦（档案没有），问西湖同样的问题放行；「怎么去」吐「地铁 2 号线」被主题词与数字两道拦下；`draft-spot` 走 404；提示词里只有当前景点的字段 |

**第三刀 · 实际做了什么（推荐理由润色）**

| 项 | 结果 |
|---|---|
| 边界 | `app/llm/polish.py`：进来的 N 条推荐是后端**已经算好**的，模型只拿到「景点名 + 模板理由」，返回值只是 `{slug: 文案}` 的映射，条目 / 顺序 / 分数都不经过它 |
| 护栏 | ① 返回的 slug 必须是输入集合的子集，多出来的丢掉；② 少了的那几条用**原来的理由**兜底，页面不会出现空理由；③ 改写文案同样过数字溯源；④ 超长（>60 字）直接不要，理由位被撑成一段话就失去意义 |
| 接口与契约 | `POST /ai/recommend-notes`；`AIRecommendNotesIn` / `AIRefinedReason` / `AIRecommendNotesOut`。降级时 `polished=false` 且 `reasons` 就是原来的理由 |
| 前端 | 新增 `RecommendationGrid.tsx` 接管首页推荐位：模型可用时用润色文案并标出「AI 润色」+ 免责声明，不可用 / 失败时原样显示后端理由；顺手修掉「卡片 + 理由」在同一格子里互相压叠的布局缺陷 |
| 测试 | `tests/test_ai_polish.py` 13 用例；前端 `RecommendationGrid.test.tsx` 6 用例。后端 117 → 130，前端 58 → 64 |
| 端到端 | 桩模型给第一条塞「地铁 3 分钟」→ 被拦并回落成原理由（`dropped` 里如实记录）；末尾塞一个不存在的 slug `invented-spot` → 被丢；其余三条正常替换。前端真机看到「AI 润色」标记与免责声明 |

**第四刀 · 实际做了什么（离线批量生成）**

| 项 | 结果 |
|---|---|
| 定位 | 这一刀生成的内容**会变成景点档案的一部分**，所以它是离线的：`app/llm/draft.py` + `scripts/draft_attraction_summaries.py`，只出**待审 SQL**，产物落在 `db/seed/drafts/`（`.gitignore` 忽略，只有 README 入版本库） |
| 不碰运行时 | 脚本对库**只做 SELECT**；渲染出来的语句只有 `UPDATE attraction SET summary = …`，来源 / 许可 / 状态字段不在射程内；有一条测试遍历 OpenAPI 路径，确认没有任何路由通往这个模块 |
| 护栏 | 输入复用 `ask.facts`（只有已公开字段，来源与许可不给模型）；数字溯源复用 `ask.verify`；超长（>120 字）丢弃；模型未配置时**直接退出 code 2**，不降级凑数 |
| 人审工作流 | 生成的 SQL 里每条都带「`-- 原: …`」对照行与文件头（生成时间 / 模型 / 提示词版本 / 请勿直接执行）；核对通过的语句手工抄进 `db/seed/seed.sql`，随种子走 CI |
| 测试 | `tests/test_llm_draft.py` 17 用例：编造数字 / 超长 / 空回答 / 未配置 / 调用失败各一条，`render_sql` 只出 UPDATE 且转义单引号、未通过的草稿不进文件。后端 130 → 137（134 passed + 3 skipped） |
| 端到端 | 桩模型给「秦始皇兵马俑」编了「1987 年建成」→ 被数字溯源拦下、不进待审 SQL；另外两条正常生成并带「原」对照行 |

**UI 润色（本轮一并做的）**

| 项 | 结果 |
|---|---|
| 页头 | 每一页都要重复的页头压扁一档（2.3rem 品牌字、胶囊导航、与页面筛选同一套形状语言），首屏留给内容 |
| 节奏 | 页面内边距 / 区块间距 / 标题字号统一收一档；详情页标题 2.2 → 1.9rem |
| 细节 | 卡片 hover 加投影、事实表与面板统一圆角与底色、禁用的 AI 按钮不再是一块褪色橙、`:focus-visible` 键盘描边、深色底下的滚动条压成半透明白 |
| 修缺陷 | `.attractionGrid > li` 改纵向 flex（卡片不再被 `height:100%` 撑破格子把理由压到下一行）；理由盒给两行的下限高度，同行卡片不再被理由长短顶得参差 |

**第二刀起的护栏（后面几刀同样适用）**

- 详情页追问只能**复述站内字段**，不允许模型自答票价 / 开放时间 / 天气 / 交通
- 推荐理由润色只改写文案，**不改推荐结果本身**，也不改变排序
- 离线批量生成的产物必须**人审后入库**；不接受「模型直写数据库」
- 任何一刀都不得让「模型不可用」变成用户可见的报错页

---
### S10 · 语义检索 + LLM 行程生成

**上下文**

S9 把「一句话」变成了筛选条件。但那只能听懂**能写成 SQL 的需求**：「杭州的古迹」可以，
「适合发呆一下午的地方」不行。这一刀补两件事：

| 能力 | 一句话 |
|---|---|
| 语义检索 | 把文本向量化，按描述的相似度召回 —— 不需要对话模型，只配向量模型也能用 |
| 行程生成 | 自然语言需求 -> 按天编排的行程。模型只做**编排与措辞**，景点必须落在候选集内 |

**这一刀最重要的一条**（与 S9 同源）：模型**不产出景点**。行程里的每个 `attraction_id`
必须落在候选项里，越界**整份拒掉**而不是丢掉那一条 —— 越界说明模型在编景点，
那么它没越界的那几条也没有可信度。

**任务清单**

1. 向量客户端（`app/llm/embedding.py`）：与 `client.py` 同构的薄封装，走 OpenAI 兼容的 `/embeddings`；
   默认 `EMBEDDING_PROVIDER=inherit` 跟随 `LLM_PROVIDER`
2. 向量存储（`db/schema.sql` 的 `attraction_embedding`）：**JSON 文本，不引 pgvector**
3. 检索层（`app/search/`）：`canonical.py` 拼规范化文本 + 指纹；`semantic.py` 语义检索与混合相似度
4. 行程生成（`app/trip/`）：`prompt.py` 候选集约束、`validator.py` 规则表、`service.py` 异步三段式
5. 限额（`app/quota.py`）：`trip_quota` 表按 (owner, 自然日) 原子计数，管次数与全站 token 预算
6. 接口：`POST /api/v1/search/semantic`、`POST|GET /api/v1/itineraries`；`/attractions/{id}/similar` 升级为混合排序
7. 离线任务：`scripts/build_embeddings.py`（增量、指纹失效、`--dry-run` / `--report`）、
   `scripts/reclaim_itineraries.py`
8. 前端：`ItineraryPlanner` 三段式页面（提交 -> 轮询 -> 展示），四态分开显示

**与原蓝图（`Have-A-Trip-LLM升级方案.md`）的关键偏差**（都是有意的，原因写在这里）

| 原计划 | 实际做法 | 为什么改 |
|---|---|---|
| `pgvector` + `vector(n)` + HNSW，CI 换 `pgvector/pgvector:pg16` 镜像 | `attraction_embedding.embedding` 存 **JSON 文本**，余弦在应用层算 | 本仓库的 ORM 刻意只用可移植类型、测试跑 SQLite；引 pgvector 会同时带来「建表要超级用户装扩展」「CI 换镜像」「SQLite 与 PG 两套路径」三份复杂度。全库 90 条景点算全量余弦只要几毫秒，ANN 索引是过早优化。过万条时再换，`canonical`/`content_hash`/`cosine` 的接口不用动 |
| 「向量化批量任务走独立环境」 | 与 API **同一个 venv** | 那个前提是向量化要用 torch。这里走 HTTP 调服务商，依赖与 API 完全一样，独立环境没有任何东西可隔离 |
| 「表名改 `itinerary`；`CREATE EXTENSION` 与建表解耦」 | 采纳（表名与解耦都照做，只是不再需要扩展） | 与既有 `attraction_plan` 的区别写进了 `db/README.md` |
| 「指纹纳入 `model + dim + pipeline_version`」 | 采纳 | 见 `app/search/canonical.py`：**换模型必须让全部指纹失效** |
| 「行程用 `public_token` 对外」 | 采纳 | `GET` 只按 token 取；自增 id 递增就能读到别人的需求原文 |
| 「独立事务写 item / 独立事务写 succeeded」 | 合成**一个事务** | 分两个事务会造出「有条目但状态还是 generating」的中间态。合成一个后：要么成功的行程有全部条目，要么什么都不留；失败时先 rollback 再另起事务写 `failed` |
| 「另起心跳线程」 | 认领时写一次心跳，判死看 `coalesce(heartbeat_at, started_at)` | 生成是一次 60 秒内的同步调用，阈值 180 秒远大于调用超时，心跳线程是多余的活动部件 |
| 「请求原文不入库，只存 hash」 | 采纳 | `itinerary.request_hash`；原文只在内存里传给后台任务 |
| 「多轮对话式 Agent」「语音/图片输入」 | 仍然不做 | 一期只做单次「需求 -> 行程」 |

**验收标准**

- [x] 向量不可用 / 库内没向量 / 维度不一致 / 服务报错时，`/search/semantic` **一律退回关键词检索并照样返回条目**，HTTP 200
- [x] `/search/semantic` 与 `/attractions/{id}/similar` 都不会返回 `draft` 景点；`/similar` 任何情况下都不为空（热度兜底）
- [x] 同一模型下混了两种维度时检索拒绝使用这批数据（退回关键词而不是给乱序结果）
- [x] `content_hash` 含模型标识：换模型后增量任务会重建全部行（有测试断言）
- [x] 行程里每个 `attraction_id` 都在候选集内，越界整份拒掉（有专门测试）
- [x] validator 规则表**每条都有对应测试**：天数覆盖、`seq` 连续、每天上限、总条数上限、空行程按失败处理
- [x] 生成失败时不留半截条目，且 `failed` 确实落库（有测试断言最终状态）
- [x] 同一 owner 的同一份需求只调一次模型、只占一个名额（有测试断言调用次数）
- [x] 超额返回 429 且 `detail.reason` 是固定取值（`daily_limit_exceeded` / `global_budget_exhausted`）+ `retry_after`
- [x] `GET /itineraries/{token}` 用不可枚举 token；用数字 id 取不到任何东西
- [x] 心跳过期才回收，**正在跑的任务不被误杀**（两条测试：一条过期、一条新鲜）
- [x] 模型挂了 `/itineraries/{token}` 仍然 200，`status=failed` 带可读原因
- [x] 模型输出不合法（如漏排某一天）时**带着失败原因重试一次**再判失败，重试的 token 也计入限额（`TRIP_GENERATE_RETRIES`，有测试断言调用次数与用量累加）
- [x] 前端四态分开显示：生成中 / 失败 / 被限额 / 成功；超过 `max_poll_seconds` 停止轮询
- [x] 不引入任何新依赖（`httpx` 已在运行时依赖里），`license_gate.py --strict` 通过

**实际做了什么**

| 项 | 结果 |
|---|---|
| 向量客户端 | `app/llm/embedding.py`：provider 预设含 `embedding_model`、按 `index` 还原顺序、批次切分、维度校验（`EMBEDDING_DIM=0` 为自动）、TTL 缓存、`embedding_api_key` 可回退到 `llm_api_key` |
| 检索层 | `app/search/canonical.py`（拼串口径 `PIPELINE_VERSION` + 指纹）、`vectors.py`（编解码 + 余弦）、`semantic.py`（`active_model` / `model_dim` / `coverage` / 混合排序） |
| 候选召回 | 向量近邻优先，不可用时退回 `content_based.popular_attractions` —— 候选只是给模型的挑选范围，没有候选才真的排不出来 |
| 行程服务 | `app/trip/service.py`：`UNIQUE(owner_key, cache_key)` 当并发抢锁点、条件更新认领（`WHERE status='pending'`）、候选集约束、token 计量、`reclaim_one` 自愈；`_draft()` 在 validator 拒掉输出时把失败原因回灌进提示词重来（`TRIP_GENERATE_RETRIES`，默认 1 次），只在「输出不合法」重试 —— 连不上模型重发一遍只是把同一份钱再花一次 |
| 限额 | `app/quota.py`：单条 `UPDATE ... WHERE used < :limit` + `rowcount` 判断，不引 Redis；限额按东八区自然日 |
| 前端 | `ItineraryPlanner.tsx` + `itinerary.css` + 6 个用例；导航加「帮我排行程」；`types/index.ts` 与 `api/client.ts` 按 `schemas.py` 补齐 |
| 测试 | 后端新增 77 个用例（`test_semantic_search.py` 22、`test_itinerary.py` 31、`test_embedding_client.py` 19，另在 `test_schema_parity.py` 补 5 条对拍断言），合计 214 个用例（**206 通过 / 8 跳过**，对拍需 PostgreSQL）；前端 64 → 70 |

---

## 六、每一步都必须满足的护栏

| 护栏 | 检查方式 |
|---|---|
| 许可证卡口通过 | `python scripts/license_gate.py --strict` |
| 不引入 GPL/AGPL/无许可证的依赖或数据 | 同上；PR 里说明新增依赖来源 |
| 不做地图与定位 | `rg -n "components/MapView\|WorldMap\|geolocation\|leaflet" frontend/src backend` 应为空 |
| 提交带 DCO 签名 | `git commit -s`；`git log --format=%B -1` 里须有 `Signed-off-by` |
| 中文提交信息与文档 | 见 `AGENTS.md` 语言规范 |
| 许可相关改动同步更新文档 | `docs/LICENSE-AUDIT.md` + `docs/BASES.md` 一起改 |

---

## 七、风险登记

| 风险 | 影响 | 应对 |
|---|---|---|
| 数据层 share-alike 义务（ODbL / CC BY-SA） | 将来闭源受阻 | 优先自采 / MIT；必须用时隔离边界并署名；闭源前逐条复核 |
| 无许可证的中文景点数据集 | 版权来源不清，随时可能被追责 | 只看思路不抄数据（黑名单已记录在案） |
| RecBole 环境与 API 混装 | 线上服务直接崩 | 两个 venv 物理隔离；CI 加 `rg recbole backend` 断言 |
| 升级上游基底覆盖本地改动 | 已修好的问题复现 | `scripts/bases.lock.json` 记录 `localChanges`；升级时用 `git diff` 挑着合，不整目录覆盖 |
| 内容量不足导致推荐空转 | 推荐位体验差 | S2 的内容相似度兜底必须先于 S6 上线 |
| 无用户行为数据 | 协同过滤无意义 | 一期以内容推荐为主，RecBole 结果只在数据够时才启用 |

---

## 八、待决问题（已定）

| # | 问题 | 结论 | 落地位置 |
|---|---|---|---|
| 1 | 项目名 | **Have-A-Trip**（沿用仓库名）。`attraction-atlas` 只作为数据库名 `attraction_atlas` 保留，不再是产品名 | 前端集中在 `frontend/src/config.ts`；`recsys/config/recbole.yaml`、`public/manifest.json` 已改 |
| 2 | 前端测试框架 | **Vitest 接管**（与 Vite 8 原生搭配）。CRA 时代的 `App.test.js` 改写为 `App.test.tsx`，`npm test` 从空脚本变成真跑 | `frontend/vitest.config.js`、`frontend/src/**/*.test.tsx`、CI `frontend-build` |
| 3 | 数据库 | 生产 PostgreSQL，测试 SQLite 内存库（`BigIntPK` 类型变体兼容两边）；`schema.sql` 是真身，parity 测试做对拍 | `db/schema.sql`、`backend/tests/test_schema_parity.py` |
| 4 | 部署形态 | 前端静态产物 + API 进程 + PostgreSQL；同源由反向代理统一入口时 `VITE_API_BASE` 留空 | `docs/DEPLOY.md` |

> **关于 #1 的取舍**：`attraction_atlas` 这个名字仍出现在数据库名、CI 的 `POSTGRES_DB`、`recbole.yaml` 的
> `dataset` 字段里。那是**标识符**不是产品名，改名要动 CI 与训练配置，收益为零，故保留。
> 用户可见的产品名只有 `Have-A-Trip`。

---

## 九、变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-09-25 | v1 | 初版，基线 commit `88a15f1` |
| 2026-09-25 | v1.1 | 定下执行顺序 `S0 → S3 → S1 → S2 → S4 → S8 → S7 → S6` |
| 2026-09-25 | v1.2 | S0 / S3 / S1 / S2 全部完成并入 `main`；总览表加状态列 |
| 2026-09-25 | v1.3 | S4 完成：前端整体换成 attraction 模型，接自家 API；顺带修掉 AOS 死链导致页头不可见等上游遗留 |
| 2026-09-25 | v1.4 | S8 完成：CI 补 `frontend-build` 与 `dco` 两条工作流、前端接入 Vitest（21 用例）、项目名统一为 Have-A-Trip、新增 `docs/DEPLOY.md`；第八节待决问题全部定案 |
| 2026-09-25 | v1.5 | S6 完成：`recsys/` 四个脚本端到端跑通，BPR 离线结果写回 `rec_result`；钉死 4 个上游依赖坑；`run_recbole.py` 改 `chdir` 修掉仓库里的野 `log/` 目录 |
| 2026-09-25 | v1.6 | S5 完成：`Credits.tsx` 重写成数据来源与许可声明页，数据由新增的 `GET /api/v1/sources` 从库里现算；share-alike 来源未登记修改状态会在页面标红。全部计划步骤 S0–S8 至此收口 |
| 2026-09-25 | v1.7 | 收尾：`docs/DEPLOY.md` 检查清单补 `/api/v1/sources` 的 `needs_attention` 必须为 `false`；按既定顺序最后安装 `ecc-universal`（全局 npm `ecc-universal@2.2.1`，`ecc` CLI 可用；Codex 侧的 skill 仍由 `ecc@ecc` 插件提供，未重复落一份到 `~/.codex/`） |
| 2026-09-25 | v1.9 | 景点配图落地：新增 `scripts/make_attraction_covers.py` 按 slug 确定性生成 50 张自绘 SVG 封面（共 134 KB）与 `db/seed/images.sql`；每条 `attraction_image` 带 `credit` = Have-A-Trip 自绘、`license` = MIT。第三方图库路线（Wikimedia Commons / Openverse）实测本机不可达，故改为自绘，理由记在 `docs/LICENSE-AUDIT.md` 第五节。`db-schema.yml` 加跑 images.sql 与三条图片断言，`license-gate` 加 `--check` 闸 |
| 2026-09-25 | v2.0 | 世界景点与旅游方案：`attraction` 增 `a_level` / `heritage` 两列（各带 CHECK 与部分索引），新增 `attraction_plan` / `attraction_plan_step` 两张表（表数 9 → 11）；种子扩到 90 个景点（境内 50 + 境外 40，覆盖六大洲 30 个国家）、9 个分类、31 个标签、90 个方案 / 307 条步骤，配图 90 张自绘 SVG；`/attractions` 加 `grade=5A\|4A\|3A\|heritage` 筛选（A 级与世界遗产是两套刻度，各占一个取值），详情返回 `plans`；前端加等级徽章、等级筛选与「旅游方案」段，票价改成按国别渲染（不再硬编码人民币）；`db-schema.yml` 断言同步并新增等级 / 方案口径与重跑自愈检查 |
| 2026-09-25 | v1.8 | 占位图标换成自绘：新增 `scripts/make_favicon.py`（标准库程序化生成 7 档尺寸），`public/earth.ico`（225 KB，出处无从查证）删除，图标落到约定路径 `public/favicon.ico`（8.5 KB）；`index.html`、`manifest.json`、`Credits.tsx`、`docs/LICENSE-AUDIT.md` 同步；`license-gate` 加一道 `make_favicon.py --check` |
| 2026-09-25 | v2.1 | 详情页加「相关视频」站外入口：新增 `frontend/src/lib/externalSearch.ts`（只拼搜索页地址）与 `ExternalVideoSearch` 组件（4 个用例，前端 37 → 41）。**只给 B 站搜索页外链** —— 不内嵌播放器、不抓取视频、不用对方标识；具体视频一律不链（会死链，且等于替单条内容背书）。`Credits.tsx`「这个应用不做什么」与 `docs/LICENSE-AUDIT.md` 新增第六节同步口径 |
| 2026-09-25 | v2.3 | **S9 后三刀 + UI 润色**：详情页追问（`/ai/ask`，数字溯源 + 主题词两关）、推荐理由润色（`/ai/recommend-notes`，推荐结果不经过模型）、离线简介草稿（`scripts/draft_attraction_summaries.py`，只出待审 SQL、人审后入库）。后端 87 → 137（134 passed + 3 skipped），前端 50 → 64。前端新增 `AiAskBox` / `RecommendationGrid` 与共享 `useAIStatus`；顺手修掉推荐位「卡片 + 理由」压叠的布局缺陷，并做了一轮 UI 润色（页头瘦身、节奏统一、焦点态与滚动条）。至此 S9 四刀收口 |
| 2026-09-25 | v2.2 | **S9 第一刀（AI 接入 · 自然语言检索）**：新增 `backend/app/llm/{client,interpret}.py` 与 `GET /api/v1/ai/status`、`POST /api/v1/ai/search`。模型**只产出查询条件、不产出景点条目**，取值白名单 + 库内双向校验，解析失败一律降级成关键词检索（HTTP 200 而非 500）。默认 `LLM_PROVIDER=none`，不配模型应用照常跑。`tests/test_ai.py` 14 用例 + `tests/test_llm_client.py` 8 用例（后端 65 → 87）；前端加「用一句话找景点」面板（41 → 50 用例）。`httpx` 从开发依赖提到运行时依赖（AI 客户端要用）。剩三刀（详情页追问 / 推荐理由润色 / 离线批量生成）待开工 |
| 2026-09-25 | v2.4 | 本地一键起环境：新增 `scripts/dev-up.ps1`（连库 → 灌 schema 与种子 → 起前后端，幂等；不装东西、不写 `.env`，日志与 pid 落 `.dev/`；`-Down` 按 pid 连同子进程收尾）。为此 `frontend/vite.config.js` 的代理目标改为读进程环境变量 `DEV_API_PROXY`（默认 `http://127.0.0.1:8000`），换后端端口时前端不再打空。README「快速起步」改成一键起为主、手工三步为对照 |
| 2026-09-25 | v2.5 | 装依赖的坑写进文档：Windows 中文控制台（代码页 936）下 `pip` 按 GBK 解码 UTF-8 的 `requirements*.txt` 会报 `UnicodeDecodeError`，README 与 `backend/README.md` 都写明先 `$env:PYTHONUTF8 = 1`；安装命令统一到 `requirements-dev.txt`（含运行时 + pytest） |
| 2026-09-25 | v3.0 | **S10 收口（语义检索 + LLM 行程生成）**：新增 `backend/app/llm/embedding.py`（走 OpenAI 兼容的 `/embeddings`，`EMBEDDING_PROVIDER=inherit` 默认跟随对话模型，`EMBEDDING_DIM=0` 表示自动）与 `backend/app/search/{canonical,vectors,semantic}.py`；向量**存 JSON 文本、不引 pgvector**（ORM 保持可移植、测试仍跑 SQLite 内存库，90 条景点算全量余弦只要几毫秒），`content_hash` 纳入模型标识，换模型即全量失效。行程走「提交 → 轮询 → 取结果」三个接口，模型只做**编排与措辞**：每个 `attraction_id` 必须落在候选集内，越界**整份拒掉**；限额靠单条 `UPDATE ... WHERE used < :limit` 按东八区自然日原子计数（每人每日次数 + 全站 token 预算），`rejected` 与 `failed` 分开，对外只用不可枚举 `public_token`、需求原文只存 hash。前端新增 `/planner` 三段式页面（四态分开显示，超过 `max_poll_seconds` 停止轮询）。后端 137 → 214（206 通过 / 8 跳过），前端 64 → 70；不引入任何新依赖 |
| 2026-09-25 | v3.1 | **界面中英双语（默认中文）**：前端新增 `src/i18n/`（一张消息表 + `t()`，**不引 i18n 依赖**）、`LanguageProvider`/`useI18n`、页头右上角切换按钮与 `src/lib/display.ts`；切换只翻**界面文案**，景点档案、方案、图注、后端 `note`/`disclaimer` 是内容，两种语种下原样显示，唯一例外是 `attraction.name_en`（库里只填了少数几条，缺的回退中文名）。`describeError` 与 `useApi` 的错误提示跟着语种走。前端 70 → 82 用例（新增文案表键对齐、切换按钮、整站点切换三处断言）；`license_gate.py --strict` 仍通过 |
| 2026-09-25 | v3.2 | **体验与可视化（四件事）**：① 前端深浅色主题（新增 `src/theme/`，主题落 `<html data-theme>`，浅色只覆盖 `index.css` 里一组 CSS 变量、不碰布局；默认深色且**不嗅探 `prefers-color-scheme`**，与语种同一口径；`index.html` 加一段内联脚本防首屏闪色）；② 数据看板 `/stats`（数据由新增的 `GET /api/v1/stats` 现算，来源那块**复用 `/sources` 的同一份聚合**；条形是手写 SVG，**不引图表库**；没填的取值归到 `unknown` 档显示为「未核实」，各档之和恒等于总数）；③ 景点对比 `/compare`（选择记在 URL 查询串 `?a=&b=`，走已有的 `/attractions`，**没开新接口**；只有评分标「更高」）；④ 行程单打印（`@media print` 把调色板换成白底黑字以免深色主题打印时涂黑整页，并摘掉页头、页脚、表单与按钮）。后端 214 → 223 用例（新增 `tests/test_stats.py` 9 个），前端 82 → 107；**不引入任何新依赖**，`license_gate.py --strict` 仍通过 |
| 2026-09-25 | v3.3 | **R1–R6 收口（夜间实测的 6 个发现）**：① 一句话检索空结果时**逐条摘条件重查**，摘哪个由「摘完剩得最少」决定 —— 「下龙 + 5A」摘掉等级剩 1 条（下龙湾）、摘掉城市剩 32 条（全国的 5A），前者才是那句话的意思；最后一个条件不摘，摘光了等于把整库倒给用户，响应里用 `relaxed` 说明放宽了什么。② 摘完仍空就找**向量近邻兜底**（`semantic_fallback`），「冬天泡温泉」由 0 条变成长白山 / 华清宫。③ 校验前按 `,`/`、` 拆开多值再比白名单，取值合法但被写成一整串时不再整条丢掉。④ 请求体加固定 `seed`（`LLM_SEED`，负值表示不带）：`temperature=0` 并不等于可复现，ollama 每次请求自己抽种子（本轮 24 次调用没能复现出漂移，这条属加固而非修复）。⑤ 行程候选**先按城市收窄**，认城市靠扫库内城市名、不为它多调一次模型（这一步跑在限量限时的后台任务里），「北京三日」不再排进西安兵马俑，同城排不满一天才放宽。⑥ ollama 预设的向量模型 `nomic-embed-text` → `bge-m3`（中文实测明显更准，1024 维，换模型必须重跑 `build_embeddings.py`）。后端 223 → 236 用例，前端不变；**不引入任何新依赖**，`license_gate.py --strict` 通过 |
| 2026-09-25 | v3.4 | **中国城市的馆 · 园 · 地标（种子扩到 114）**：按「各城市的博物馆 / 游乐场 / 地标性建筑」补 24 条境内景点 —— 博物馆 8（上海自然博物馆、南京博物院、湖北省博物馆、河南博物院、湖南博物院、金沙遗址博物馆、广东省博物馆、中国科学技术馆）、主题乐园 8（广州长隆旅游度假区、北京 / 深圳 / 武汉 / 成都 / 重庆欢乐谷、上海海昌海洋公园、香港迪士尼乐园）、城市地标 8（上海中心大厦、中信大厦、深圳平安金融中心、洪崖洞、黄鹤楼、天津之眼、西安钟楼、澳门旅游塔）。口径不变：坐标全 `NULL`、评分全 0、票价一律留空（拿不准免费就不写 0）、`a_level` 只填能核实的两条（广州长隆旅游度假区、黄鹤楼，均 5A）。境内 50 → 74、总数 90 → 114，境内省级行政区 21 → 25（新增重庆市、天津市、香港特别行政区、澳门特别行政区），`province` 口径 59 → 63；`a_level` 40 → 42、标签关联 362 → 432、方案 90 → 114、步骤 307 → 381、封面 90 → 114。`db-schema.yml` 的 9 条断言与 `db/README.md`、`README.md` 的数字同步；本地实测：种子重跑两遍幂等、向量补到 114/114、`make_attraction_covers.py --check` 与 `license_gate.py --strict` 通过、后端 236 用例与前端 107 用例全过 |
| 2026-09-25 | v3.5 | **中国城市巡礼（种子扩到 140）**：继续按「一个城市一个馆或一处地标」补 26 条境内景点，覆盖此前仍空白的 24 个城市 —— 沈阳故宫（5A / 世界遗产）、伪满皇宫博物院、哈尔滨圣索菲亚教堂、内蒙古博物院、山西博物院、河北博物院、赵州桥、山东博物馆、趵突泉、青岛栈桥、安徽博物院、滕王阁（5A）、三坊七巷、鼓浪屿（5A / 世界遗产）、石林（5A / 世界自然遗产）、甲秀楼、广西民族博物馆、甘肃省博物馆、西夏陵、塔尔寺（5A）、新疆维吾尔自治区博物馆、天一阁、雁荡山（5A）、鼋头渚（5A）、佛山祖庙、泉州开元寺（世界遗产）。口径不变：坐标全 `NULL`、评分全 0、票价一律留空、`a_level` 只填能核实的（本批 7 条，全 5A）。境内 74 → 100、总数 114 → 140；境内省级行政区 25 → 32（新增辽宁省、黑龙江省、河北省、江西省、福建省、贵州省、宁夏回族自治区），`province` 口径 63 → 70；`a_level` 42 → 49（5A 41 + 4A 8）、`heritage` 59 → 63；标签关联 432 → 506、方案 114 → 140、步骤 381 → 459、封面 114 → 140。CI 的 9 条断言与两份 README 的数字同步；本地实测幂等（种子重跑两遍）、向量 140/140、封面 `--check` 与许可闸通过、后端 236 用例与前端 107 用例全过 |
| 2026-09-25 | v3.6 | **离线演示脚本**：新增 `scripts/demo-offline.ps1` —— 起一个 `LLM_PROVIDER=none` 的实例，把关键接口打一遍并逐条断言，输出「不配模型也完整可用」的验收报告（16 项）。自带 `attraction_atlas_demo` 库，不碰主库；默认跑完即关，另有 `-KeepRunning` / `-Down` / `-Json`。断言刻意盯住几处容易静默塌掉的口径：看板四组分布求和恒等于总数、列表与看板同口径、相似景点无向量时不为空、假 token 一律 404、限额拒绝必须带 `reason` 与 `retry_after`。实现上不用 `Start-Process` 的重定向 —— 那会让子进程继承标准句柄，脚本一旦被管道或重定向调用就永不返回；改成生成一个 bootstrap 让 uvicorn 自己写日志 |
| 2026-09-25 | v3.7 | **海南 · 台湾（种子扩到 156，境内省级行政区收满 34）**：补 16 条景点，把最后两处空白填上 —— 海南 8（三亚南山文化旅游区（5A）、天涯海角游览区、蜈支洲岛、呀诺达雨林文化旅游区、海口骑楼老街、海南省博物馆、博鳌亚洲论坛永久会址、五公祠）、台湾 8（台北故宫博物院、日月潭、阿里山、太鲁阁峡谷、九份老街、野柳地质公园、台北 101、安平古堡）。新增标签 `beach`（海滩）—— 两地的海滨是主要看点，原有的 `island` / `reef` 覆盖不到沙滩。口径不变：坐标全 `NULL`、评分全 0、`a_level` 只填能核实的（本批 1 条 5A），票价只在确定免费时写 0（骑楼老街、九份老街、太鲁阁、日月潭、海南省博物馆 5 条）。境内 100 → 116、总数 140 → 156；境内省级行政区 32 → **34（全满）**、`province` 口径 70 → 72；标签 31 → 32、标签关联 506 → 552、方案 140 → 156、步骤 459 → 506、封面 140 → 156、`a_level` 49 → 50（5A 42 + 4A 8）、`heritage` 仍 63。`db-schema.yml` 的断言同步，顺带修掉 v3.5 漏改的 `heritage` 断言（`expect 59` → 63，否则 CI 必红）；`docs/LICENSE-AUDIT.md` 里停在 v2.0 的规模数字一并刷新。本地实测：种子在临时库连跑两遍 exit 0、`make_attraction_covers.py --check` 通过 |
| 2026-09-25 | v3.8 | **修好 frontend-build 的守线卡口（它一直红着）**：`src` 里那三条界面文案 —— 「no maps or geolocation」—— 正是声明「不做定位」的句子，而守线用裸词 `grep`，于是把自己拦了下来；这一步在 `e82700b`、`3e41b93` 等**每个**提交上都失败，属既有问题而不是某次改动引入的。改法是把匹配收到**代码**上：只认 `import` / `require` / `from` 后面的依赖名（含 `react-leaflet`、`@mapbox/*` 这类带前缀的写法）、旧组件名与 `navigator.geolocation` 这类真实 API，注释与文案里的同名词一律放行。本地用 Git 自带的 bash 把该步骤原样跑了 9 个用例：7 个注入用例全部被拦下（含无括号的副作用导入 `import 'leaflet'` 与动态 `import()`），文案与注释里的同名词放行 |
| 2026-09-25 | v3.9 | **README 演示 GIF**：新增 `docs/demo.gif` —— 1000×625、19 帧、约 29 秒、3.4 MB，把真模型跑出来的十个界面串成一条循环演示挂在 README 顶部。**用 PIL 合成而不是 ffmpeg**（这台机器上没有 ffmpeg，PIL 是现成的）；录屏走 Edge headless + CDP，帧序按**状态流**排（功能 → 换语言 → 换主题），行程页从末尾提到换语言之前，否则切回深色中文会跳。两个坑记在这里免得下次再踩：受控 `input` 上直接改 `value` **不触发 React 的 `onChange`**（得走 `Input.insertText`），以及**字幕不参与交叉淡化**（否则两条字幕叠印）。 |
| 2026-09-25 | v3.10 | **输出不合法就重试 + 首页三个随机地方**：两件事。① 行程生成原先模型漏排某一天就直接判失败（`validator` 对天数没覆盖 1..N 是整份拒掉），现在 `_draft()` 把失败原因回灌进提示词再要一次，仍是「一次调用 = 一段对话」而不是多轮 Agent；重试的 token 一并累加进限额，只有「输出不合法」才重试（`TRIP_GENERATE_RETRIES`，默认 1，0 即老行为），两次都不行才判失败且错误里写明重试次数。② 新增 `GET /attractions/random`（默认 3 条、上限 12、**不缓存并回 `Cache-Control: no-store`**）：先数总数再随机取不重复下标，用 `ORDER BY id + OFFSET` 逐个取，比 `ORDER BY random()` 更可移植（SQLite 与 PG 的 `random()` 语义不同）；前端 `RandomPicks` 在打开首页时弹出三个地方，可「换一批」，`sessionStorage` 记账保证一次会话只弹一次、抽不到数据就不弹。测试：后端 236 → **245**（重试 3 条、随机接口 6 条），前端 108 → **116**（`RandomPicks` 8 条，按同一口径重数；此前几行记的 107 差 1）；`tsc --noEmit` exit 0，真机用内置浏览器验过弹窗、换一批与「重载不再弹、新标签页重新弹」 |
| 2026-09-25 | v3.10 | **修掉对比页「只认前 100 个景点」**：`ComparePage` 取候选时写死 `size: 100`，而后端 `max_page_size` 就是 100 —— 库里 156 条有 56 条进不了下拉。更糟的是别人发来的 `?a=<slug>` 链接会被 `known()` 判成「已下架」，静默换成第一页的景点：一条发出去的对比链接会悄悄变成另一条，而且**没有任何提示**。改成按响应里的 `total` / `size` 翻页取全（页数从**响应**推而不是从请求值推 —— 服务端有权把 size 压小），下拉与 `known()` 这才拿到全量；slug 真不存在时的自动补默认行为不变（实测 `forbidden-city` 不在库里，仍照旧兜底）。回归测试先红后绿：mock 出 100 + 1 两页，断言第二页的景点进得了下拉、且 URL 里的选择不被改写。本地实测真实接口：page1 = 100、page2 = 56、page3 = 0，并集 156 无重复；`west-lake`、`taipei-101`、`taroko-gorge` 原本都落在第一页之外。 |
| 2026-09-25 | v3.11 | **「随机三个地方」正名为「景区推荐」**：v3.10 那个弹窗的标题是按机制起的名（随机），这次改成按产品起名（景区推荐），并把名字一路对齐到代码：组件 `RandomPicks` → `AttractionPicks`、样式 `randomPicks.css` → `attractionPicks.css`（CSS 类同名替换）、i18n key `home.random.*` → `home.picks.*`、sessionStorage 键 `have-a-trip:random-picks-seen` → `have-a-trip:attraction-picks-seen`。**行为一个字没动**（仍是 `GET /attractions/random` 随机抽三个、仍不缓存）：名字变了而机制没变，所以标题下与页脚照旧写明「随机抽取, 与浏览记录无关」—— 叫推荐却不写清依据，就成了一个说不清来源的推荐位。英文标题 `Three random places` → `Featured attractions`。测试：`AttractionPicks.test.tsx` 8 条（用例名与断言跟着改，并加一条「标题是景区推荐」的断言） |
| 2026-09-25 | v3.12 | **对比页的下拉换成可搜索的组合框**：库里 156 个景点, 原生 `<select>` 一次铺开既搜不了也扫不动, 而这个数字只会继续涨。新增 `AttractionPicker`(输入即筛、↑↓ 移动高亮、回车落定、Esc 放弃; 中英文名都参与匹配)替掉对比页两个 `<select>`。两条规矩写进组件:**只有从列表里选中才写回 slug** —— 手打半个名字不改 URL, 否则分享出去的链接会指向不存在的景点(同 v3.10 那个坑); 以及**聚焦即清空输入框**进搜索态 —— 全选看着更聪明, 但 `select()` 会被点击带来的光标定位盖掉, 接着打的那几个字是**追加**在新名字后面("西湖" + "故宫"), 筛出个空结果。真机跑出来两个只有「焦点没离开输入框」时才会撞上的 bug, 一并修掉:① **选完接着打字**不触发 focus, `editing` 没置位, 于是筛选用的是空关键词(列表铺全量)、刚敲进去的字还会被受控 `value` 吞掉; ② **选完或按 Esc 之后再点一下**输入框同样不触发 focus, 列表再也叫不回来 —— 改成 onChange 里自己置位、onClick 兜底重开。浮层底色换成**实色** `var(--page-bg)`: 原来用半透明的 `--panel-bg-strong`, 展开时透出底下的表格文字, 读不出来。测试: 前端 116 → **128**(`AttractionPicker` 12 条, 覆盖筛选、键盘循环、Esc、手打不改值, 以及上面两个回归), 19 个文件全绿; `tsc --noEmit`、`vite build`、守线检查、`license_gate.py --strict` 全过。真机用 Edge headless + CDP 把 `/compare` 点了一遍(21 项断言: 展开铺满 156、按中文名筛、回车落定只写 slug、选完接着打字只剩新敲的字、Esc 复原、再点重开、手打不改 URL、控制台无报错), 顺带把演示 GIF 的第 6 帧按新界面重录 —— `docs/demo.gif` 仍 19 帧 / 29.4 秒 / 1000×625, 其余九帧未动。 |
| 2026-09-25 | v3.13 | **首页「景区推荐」改名「出去走走」, 同时按 IP 就近**：两件事一起做, 因为改名的理由正是机制变了。① 新增 `GET /attractions/nearby`（默认 3、上限 12、**不缓存**）：先按访客 IP 猜一次归属地, 再按**同城 → 同省 → 全国**三级抽, 结果按「先近后远」拼起来 —— 前两个在杭州、第三个在北京时, 前两个才是「近的」, 所以不再二次排序。为什么只有三级：库里的 `lat/lon` 全是 NULL（数据口径见 `db/README.md`）, 算不出公里数。② 位置这一层**默认关闭**（`GEO_IP_PROVIDER=none`）：不配就一个外部请求都不发, 接口直接退回全国随机并在响应里标 `scope=nation` —— 与 `LLM_PROVIDER` 同一思路, 不配就不连外网。新增 `backend/app/geo/ip_locate.py`（**不引任何新依赖**：私网判别走标准库 `ipaddress`）, 位置只用于这一次查询 —— 不落库、不写 cookie、不返回坐标, `X-Forwarded-For` 默认不信（那个头谁都能写）。三个只有实测才会知道的坑记在这里：(a) ip-api 的 `lang=zh-CN` 对**中国** IP 确实返回中文, 但写法与库内不一致 —— 实测 `223.5.5.5` → `杭州`/`浙江`, `114.114.114.114` → `济南市`/`山东`, 北京某 IP 干脆只到区（`西城区`）；所以匹配是**归一化后相等**（不是 LIKE：把人指到隔壁城市比不猜更糟）, 后缀（特别行政区/自治区/地区/市/省/县…）只从末尾剥**一次**, 且**不把「州」「区」当后缀** —— 库里的「苏州市」剥掉「市」已是全名, 两边若都再剥一次「州」会得到「苏」, 反而对不上；(b) Python 3.13 眼里 CGNAT（`100.64.0.0/10`）**既不是 private 也不是 global**, 只靠 `is_private` 会把它当公网送出去, 所以显式排除；(c) 本机开发时对端永远是私网地址（浏览器经 vite 代理打到 `127.0.0.1`）, 因此**本地一定走退化路径** —— 这不是 bug, `docs/DEPLOY.md` 的检查清单里写明了。响应带 `located`/`scope`/`city`/`region`（后两个是**库内取值**, 库里没有的写法如境外城市不报给前端）, 前端按四种组合分别说四句话（同城 / 同省 / 就近不够 / 没认出来）, 标题那一行与页脚都写明依据 —— 说不清依据的推荐位不如不写；页脚「不做地图与定位」也跟着改成「不做地图与**精确**定位」, 免得与新功能自相矛盾。真机验过：默认配置下 200 + `scope=nation`；用 `X-Forwarded-For` 喂 `223.5.5.5`（杭州）拿到 `scope=city` 且三个全在杭州市, 喂 `202.108.22.5`（ip-api 只到西城区）拿到 `scope=region` + 三个全在北京市（省级补齐真的生效）, 喂 `8.8.8.8`（美国）如实退回全国；内置浏览器里看过中文与英文两种弹窗。测试：后端 245 → **290**（`test_geo.py` 35 条 + `/nearby` 10 条, 覆盖私网/CGNAT 不外发、`provider=none` 不外发、三级顺序、draft 不出现、`limit` 边界、真 `Request` 接线）, 前端 128 → **134**（`AttractionPicks` 13 条, 含四种说法与英文文案）；`tsc --noEmit` exit 0, 守线检查、`license_gate.py --strict`、`make_attraction_covers.py --check` 全过。顺带把 README 接口表末尾一行走失的 `/stats` 归位。 |
| 2026-09-25 | v3.14 | **第三级「全国」其实是全世界 —— 收口成国内**：v3.13 把就近写成「同城 → 同省 → 全国」三级, 代码里第三级却没加国别过滤, 等于从**全部** 156 条里抽。实测打开 `/api/v1/attractions/nearby` 拿到的是班夫国家公园(CA) / 马拉喀什老城(MA) / 稻城亚丁, 而页面上那一行正写着「这三个是全国各地随机抽的」—— 说错的依据比不写更糟。数字: 156 条已发布 = 116 条境内 + 40 条境外(摊在 31 个国家), 一次要三个**全不中境外**的概率只有约 41%, 也就是近六成会掺进来。改法: 第三级按 `country_code = 库内主国 CN` 收口(新常量 `HOME_COUNTRY`, 与 `Attraction.country_code` 的默认值、`/stats` 的 by_country 同一口径, 刻意不做成配置项 —— 它是数据事实, 不是部署参数); 新增第四级 `world`, 连国内都不够才轮到全部景点; 访客**已知在境外**(`Location.country_code` 非 CN)时**跳过**第三级直接走第四级 —— 那边每个国家只有一两条, 按国别抽等于把「就近」变成「就那一条」。契约加 `NearbyScope = city / region / nation / world`, 前端那一行变成五种说法(nation 说的是「这批从国内抽的」, world 才是「从全部景点抽的」), 中英同步, 页脚那句「估不出来就退回全国随机」也跟着改成国内。测试 290 → **293**(三条新用例: 国内够用时 20 轮一次都不许掺境外 —— 不加收口时每轮有 5/6 的概率翻车, 20 轮全躲开的可能小于亿分之一; 国内凑不满时境外的只能补在最后且 scope 必须是 world; 已知在境外时不报 nation), 前端 134 → **135**(新增 world 那种说法, 并断言它与「国内各地」不会说串)。把收口临时摘掉验过这三条确实会红。README / DEPLOY(检查清单加「三个的 country_code 全是 CN」)同步。 |
| 2026-09-25 | v3.15 | **做成本机应用（单进程），护栏三遍**：需求是「把这软件做成一个应用 damo」。形态上不加第二个进程也不加 nginx —— 让 API 进程自己托 `frontend/dist`：新增 `backend/app/web.py`（`SERVE_FRONTEND` **默认关闭**；`api/` `docs` `openapi.json` `redoc` 前缀先判;拼出来的路径必须仍落在 `dist` 里;`/assets/**` immutable、`index.html` no-store），`config.py` 加 `SERVE_FRONTEND` / `FRONTEND_DIST`（留空按**仓库位置**算，与 cwd 无关），`main.py` 把静态路由**注册在根路由之后** —— `/{path:path}` 连 `/` 都匹配，注册在前会把首页抢走。新增 `scripts/damo-app.ps1`（默认 `8100`，与 dev-up 的 8000/8010 错开;只写 `.dev/`，不动仓库也不生成 `.env`;端口上已是本实例就复用、被**别的**程序占着只报错不杀别人的进程;用 `--app=` 开独立窗口，**关窗即停**;起不来时弹框指出日志在哪）、`damo.cmd`（纯 ASCII 双击入口）、`scripts/install-damo-app.ps1`（当前用户桌面与开始菜单快捷方式，不需要管理员）。真机验过：单进程下 `/` 给 HTML、`/attraction/west-lake` 回落外壳、同端口 `/api/v1/healthz` 给 JSON、`/assets/*.js` 带 immutable、`/docs` 与 `/openapi.json` 活着、`/api/v1/nope` 仍是 404 JSON，`-Down` 收干净且 dev 侧的 8010 / 5174 / 55432 三个进程没被误杀。测试 293 → **310**（`test_web.py` 12 条：含三种编码的穿越、开关关着时 dist 存在也不给 HTML、`/api/**` 不被壳吞;`test_launcher.py` 5 条把今天踩的坑变成断言：`.ps1` 必须带 UTF-8 BOM、不许出现 `0.0.0.0`、拉起 uvicorn 的那一行不许带 `--reload`、脚本里不许有密钥字面量、`damo.cmd` 必须全 ASCII）。**护栏三遍**：① 19 项（静态 11 + 动态 8）全绿；② 负向控制 —— 临时摘掉 `_inside`，同一组穿越探测立刻吐出 5 处泄漏，证明护栏承重、检查不是空转；随后按字节恢复并核对 sha256 一致；③ 恢复后全绿 + 后端 310 / 前端 135 / `tsc --noEmit` / `vite build` / 两个 `--check`，再推远端等四条工作流绿。顺带记两个写入期的坑：用 JS 写 `.ps1` 时 `\a` `\S` `\p` `\n` 会被当转义吃掉（`.venv\Scripts\python.exe` 变成 `.venvScriptspython.exe`，启动器因此卡在一个「找不到解释器」的模态弹框上，表现为脚本没有任何输出），PowerShell 字符串里也不能内嵌裸 `"`（得写 `\x22`）；另外 `$home` 这类变量名在 PowerShell 里与只读自动变量**大小写无关地**撞车。 |
| 2026-09-25 | v3.16 | **全量功能检测（「检测并调试所有功能」）—— 抓到并修掉三个真 bug（两个在实现里, 一个在测试隔离上）**：先把接口与 AI 挨个打了一遍（自制探针 `work/api_probe.py` 54 项、`work/ai_probe.py` 9 项，后者用真模型 qwen2.5:7b-instruct + bge-m3）。**探针自己有 19 处断言写错了**（Starlette 的响应头是小写、`category`/`tags` 是对象不是字符串、详情里是 `province` 没有 `region`、`SourcesOut` 是 `sources`/`images` 不是 `items`、`SemanticSearchOut` 的 `match` 在 `items[]` 里、`ItineraryStatus` 有五种取值、`sort=name` 的次序是本机 PG 的拼音 collation 不能拿 Python `sorted()` 对……），逐条查证后确认**实现是对的**，改的是探针。剩下三个是实现的错：① **行程把同一个景点排两次**。根因有三处：`validator` 压根不查重复；`prompt` 没写明「整份行程里最多一次」；`service._draft` 把每天站数写死成 `TRIP_MAX_ITEMS_PER_DAY`，杭州只有 4 个候选却要填 3 天 × 2 站 = 6 格，模型只能靠重复凑数。实测修前：西湖进第 1、2 天，宋城进第 1、3 天，两条 reason 一字不差 —— 这不是幻觉，是「看着正常」的错，比明显报错更难发现。改法：`validator` 加「同一 `attraction_id` 排两次整份拒掉」并报出冲突的「第 x 条与第 y 条」，错误文案写明「候选景点不够时可以少排几站, 不要用重复安排来凑数」；`prompt` 把去重升成第 4 条硬约束；`service` 按候选数收紧 `per_day = max(1, min(max_per_day, len(candidate_ids) // days))`（只是不把模型往违规方向推，兜底仍是 validator 那条硬规则）；`PROMPT_VERSION` `1` → `2`（它进缓存键，不改会让新旧两份行程撞在一起）。修后实测 3 天 3 站（西湖 / 杭州宋城 / 良渚古城遗址）零重复。② **查询向量与库内维度不符，被报成「没搜到」**。`vectors.cosine` 在两边维度不等时一律返回 0，于是每条都排不上，用户看到的是「没有找到语义相近的景点」—— 而真因是换过向量模型还没重灌（本机表里就同时躺着在用的 `bge-m3` 1024 维和旧的 `nomic-embed-text` 768 维 × 90）。改法：`semantic.py` 新增 `accepts_width(db, model, width)`（`model_dim` 只管库内自洽，它管「查询向量与库内是不是同一套」）；`api/search.py` 先取 `stored_dim`，不等就退回关键词并把话说清：「查询向量是 N 维, 库内向量(model)是 M 维, 两者无法比较; 换过向量模型就重跑一次 scripts/build_embeddings.py」；`api/ai.py` 的 `_semantic_hits` 也用 `accepts_width` 挡住，两条路径同一口径。顺带 `scripts/build_embeddings.py --report` 新增 `stray_models()`，把「换了模型留下的旧向量」报出来 —— 这批行检索用不到，界面上就完全看不见，只能一直占表。测试：后端 310 → **319**（行程 +5：同一景点跨天 / 同一天排两次都被拒、不同景点不受影响、候选不够时每天站数收紧、收紧只降不升；语义 +2：宽度不符的提示文案、`accepts_width` 三态；配置 +2：见下面第 ③ 条），前端 135 不动。验证：`pytest -q` 315 通过；`npx vitest run` 135 通过 / 19 文件；`tsc --noEmit` exit 0；`license_gate.py --strict` 通过；两个探针 54/0 与 9/0；`img_check.py` 156 封面 + 156 详情图坏链 0、缺署名 0。真机端到端（8100 单进程 + 真模型）也重验过：首页「出去走走」与换一批、AI 润色理由；列表页一句话检索 10 条（黄山 / 张家界国家森林公园 / 泰山）、关键字检索、空态、5A 筛 42 条、排序与分页 156 条 13 页；详情页事实表 + 方案 + 相似 6 条 + B 站外链 + 追问；行程 3 天 3 站；对比页 8 行 + 对调；看板 156/156/156/72；关于页来源表；404；中英与深浅色切换。截图在 `work/e2e2/`。护栏三遍（19 项静态 + 动态）全绿，`make_favicon.py --check` 与 `make_attraction_covers.py --check` 一致。③ **开发机的 `backend/.env` 会漏进用例**（这条是本轮检测的副产品，也是最值得修的）：README 让人把 AI 配置写进 `backend/.env`，而 `Settings` 的 `model_config` 里写着 `env_file=".env"` —— 于是「什么都没配」那 5 条用例（`test_ai.py` 3 条与 `test_semantic_search.py` 2 条）在本机会从 `.env` 里拿到 `qwen2.5:7b-instruct`，断言全红；CI 上因为没有 `.env`，同样的代码是绿的。本地红、CI 绿是最难查的一类红，而且它只在**按文档配过 AI 的机器**上出现。改法不是在用例里逐个覆盖字段（`Settings(...)` 有 46 处，漏一个就复发），而是给配置加一个开关：`SETTINGS_ENV_FILE`（默认 `.env`，给空串表示一份都不读），`tests/conftest.py` 在 `import app.*` **之前**把它设为空 —— 必须在导入之前，因为 `.env` 路径是模块导入时就定下来的。新增 `tests/test_config.py` 两条：一条断言「当前工作目录里摆着 `.env` 也不许被读到」（把 conftest 那行删掉就会红），一条用子类指到另一个文件、断言「开关不是摆设，给了路径照样读」。负向控制验过：把 `SETTINGS_ENV_FILE` 强制指回 `.env`，新用例与那 5 条一起立刻变红。顺带说明一条环境事实：`backend/.env`（不进仓库）里配好 ollama 之后，**双击 `damo.cmd` 就自带 AI 能力**，不用再开命令行。 |
| 2026-09-25 | v3.17 | **「出去走走」删掉副标题那一行**：标题下那句「每次打开都换一批, 尽量挑你附近的三个」说的是机制, 不是用户要看的信息, 按需求删掉。四处一起收才干净：组件里那个 `<p className="attractionPicks__lead">`、i18n 的 `home.picks.lead`（中英两张表一起删 —— 只删一张会被「两表键完全一致」那条用例拦下）、以及样式里只为它存在的 `.attractionPicks__lead` 规则。删完 `__where`（「没认出你在哪儿 —— 这三个是国内各地随机抽的。」）就从顶着 lead 排变成直接跟标题，上边距 4px → 6px, 免得贴着标题。测试 135 不动（没有用例断言这句文案）；`tsc --noEmit` exit 0；真机刷新（新会话，弹窗一次会话只弹一次）确认弹窗只剩标题 + 依据行 + 三张卡。 |
| 2026-09-25 | v4.0 | **动态区（推翻 v1 的「一期不做 UGC」）**：需求是「每个人可以在应用内地表发动态的区域」。边界一次说清：**没有账号体系**（沿用 localStorage 里的匿名 `device_id`，服务端映射成 `app_user` 一行，可选署名 ≤ 24 字）+ **没有任何定位**（不存 IP、不存经纬度）+ **没有图片上传**（一期用「挂一个已发布景点」代替晒图）+ **没有自动审核**（留 `post.status`，下架是运营动作 `update post set status='hidden'`，见 db/README.md）。数据层：`db/schema.sql` 新增 `post` 表（`author_name` / `attraction_name` 是**快照**；外键 `attraction_id` 用 `ON DELETE SET NULL` —— 景点被硬删不该连带删掉用户写的话；索引 `(status, created_at)` 与 `(user_id, created_at)`，**v4.1 已改名, 见下**）、`trg_post_updated_at` 触发器、`schema_version` 登记 `0004_posts`；`models.py` 同步 `Post` 与 `POST_STATUSES`。接口：`GET /api/v1/posts`（只出 `visible`，按时间倒序；两个筛选都是**精确匹配** —— `?attraction=<slug>`、`?device_id=`，不做自由文本搜索；`viewer` 只用来算 `mine` 与当天已用名额）、`POST /api/v1/posts`（201；正文 1–500 字 —— 接口口径 500、库里 CHECK 兜底 1000，**故意不合并成一个数字**；挂的景点必须 published，否则 404）、`DELETE /api/v1/posts/{id}`（**作者硬删**，不是作者一律 404，不区分「不存在」与「不是你的」以免试出谁发过什么；删完归还当天名额）。限流：`POST_DAILY_LIMIT` 默认 10，计数与行程**共用 trip_quota 表**但 `owner_key` 带 `post:` 前缀（`quota.py` 从 `app/trip/quota.py` **移到** `app/quota.py`，行程与动态共用一套原子自增；键统一取作者行 id `post:u:<id>`，因为删除那条路只有 user_id —— 一开始按 device_id 计，删完名额还不回去，这条 bug 由用例抓出来）。前端：「动态区」路由 `/posts`（页头导航新增一项）+ `PostComposer` / `PostList` / `PostsPage` 三个组件 + `styles/posts.css`；景点详情页加「大家在这儿说了什么」只读一块（同一条接口，前 5 条）并带「去动态区说一句」；「只看我的」用同一个 device_id 过滤；限额被拦时复用行程那条 429 结构化 detail 的提示（说清每天几条、什么时候能再来）。顺带把「取全库已发布景点」从 ComparePage 抽到 `lib/attractions.ts`（动态区的景点选择器要同一份，不重复实现）。测试：后端 319 → **354**（`test_posts.py` 33 条：发帖 / 署名回填 / 长度边界 / 两个 owner 同给被拒 / 草稿景点 404 / 限额 429 且 detail 带 reason 与 retry_after / 计数器只有 post: 那一个桶 / 默认只出 visible / 两种筛选 / 别人删不掉 / 作者删得掉且名额归还 / 景点下架后保留名字但不给链接）；前端 135 → **151**（`PostsPage.test.tsx` 13 条 + `client.test.ts` 3 条）；`test_schema_parity.py` 加 post 的列类型与索引 / 外键断言；`.github/workflows/db-schema.yml` 表数量断言 15 → 16、版本登记加 `0004_posts`、加 `post.status='live'` 与空正文被拒的负向断言。 |
| 2026-09-25 | v4.1 | **动态区加分页「加载更多」（游标分页, 不用偏移）**：需求是「给动态加分页「加载更多」」。做法：`GET /api/v1/posts` 新增整数游标参数 `before`（只取 `id` 比它小的），响应新增 `next_cursor`（= 本页最后一条的 `id`，`null` 表示到底了）；`page` / `size` 偏移那套**保留**（详情页取前 5 条、按 `?page=` 跳页都还在用），但 `page` 与 `before` **只能给一个** —— 一起给说不清从哪儿开始, 报 422。为什么加游标而不是继续用偏移：列表头部一直在长, 偏移翻页遇到「翻页途中有人发了新动态」会把上一页最后一条**再吐一遍**, 遇到删除又会**跳过一条**（两个方向的错都写成了用例钉住）。**为什么游标是 `id` 而不是 `(created_at, id)`（这里踩了一个真 bug）**：一开始按更专业的行值比较 `tuple_(created_at, id) < (ts, id)` 写, PostgreSQL 上没问题, 但**测试库 SQLite 的 `created_at` 只存到秒**（实测响应里五条全是 `2026-09-25T15:47:23`）, 而绑定参数带微秒 → 行值比较第一段永远「小于」, `id` 那一半的平局规则轮不上 → **同一秒里的行被整页重复吐出来**, 4 条用例全红但 PostgreSQL 上是绿的; 改成整数 `id` 后两种库结果一致（`id` 是 IDENTITY 单调递增, 按 `id` 倒序 = 插入顺序, 与 `created_at` 倒序实际同序）。索引跟着改：`idx_post_status_time` → **`idx_post_status_id (status, id DESC)`**、`idx_post_user_time` → **`idx_post_user_id (user_id, id DESC)`**（`models.py` 里不写 `desc()`，与既有 `idx_itinerary_item_order` 同风格；`db/schema.sql` 与 `db/README.md` 同步, `test_schema_parity.py` 的索引名断言跟着改）。取数改成 `.order_by(Post.id.desc()).limit(size + 1)` 多取一条判断「还有没有更旧的」, 有 `before` 时 `offset` 归零。前端 `PostsPage`：「加载更多」按钮 + `pages`（整页数组）/ `moreLoading` / `moreFailure` 三个 state, 第一页仍是 `useApi` 管的权威顺序, 后续页追在它后面并按 `id` 去重（删一条之后整体上移, 两页会撞上）；游标是**推导值**（有后续页时取最后一页的 `next_cursor`, 否则取第一页回的那个）—— 起初把游标也放进 state、用 effect 去写, 结果是**按钮比列表晚一帧出现, 这一帧在用例里就是竞态**：本机全量能过, 而 CI 上 `frontend-build` Run 28 就红在「要下一页失败时」这条(报「找不到『加载更多』按钮」), 红的是这一帧的差不是实现错; 改成推导后单文件连跑 5 次、全量 157 条都稳，`tsc --noEmit` 与 `vite build` 仍 exit 0；`useEffect([data])` 在第一页变了（切筛选、发完重拉、删完重拉）时**把后续页丢掉**（位置已经变了, 接着往下接只会把看过的东西再摆一遍） —— 那时位置已经变了, 接着往下接只会把看过的东西再摆一遍；翻页失败只提示、**不动游标**（再点一次还是这一页）；翻到底把按钮换成一句「没有更多了」；中英各 3 条文案（`posts.more` / `posts.more.busy` / `posts.more.end`）；`styles/posts.css` 加 `.posts__moreRow` / `.posts__more` / `.posts__moreError` / `.posts__end` 四条（沿用删除按钮那套细边框圆角语气, 只把 `disabled` 做成变灰）。测试：后端 354 → **361**（`test_posts.py` 33 → 40：游标只在一页没取完时出现 / 5 条 size=2 翻到底恰好 `第 4 条…第 0 条` 不重不漏 / **翻页途中插一条新的游标不受扰（同一条用例把偏移会重复钉成断言）** / **删一条之后游标不受扰（偏移那支漏一条, 同样钉住）** / 游标与景点筛选叠加 / `page` 与 `before` 一起给 422 / 坏游标 422）；前端 151 → **157**（`PostsPage.test.tsx` 13 → 19：按钮只在有游标时出现 / 点一次带上 `before=<游标>` / 两页拼起来 / 到底换文案 / 失败时按钮留着能再点 / 后续页与第一页撞上按 `id` 去重 / 第一页换了丢掉后续页 / 按景点看时翻页也带景点）。真机实测（8100 单进程 + 真 PostgreSQL, 用 25 个 device_id 造 25 条可辨识动态, 跑完全部回收、`post` 归 0）：`work/v5_probe.py` 20 项全过（含 `?size=2` 翻到底拿到全部 25 条且 25 个 id 互不重复、偏移第二页与游标第二页同序、筛选项下带游标也挂着同一个景点）；浏览器 `/posts` 首屏 20 张卡 + 「加载更多」→ 点一次 25 张卡、25 条正文**全部互不重复**、按钮消失并出现「没有更多了」；**翻页途中真发一条新的**（库内 26 条）再点「加载更多」→ 仍是 25 张卡、`分页测试 06` 只出现 1 次（偏移给法在这里会重复它）、`分页测试 新插入` 不混进旧页；截图 `work/v5-more-button.png` 与 `work/v5-more-end.png`。**首次推送后 `frontend-build` 红在一条新用例上**(就是上面那一帧竞态), 修完重建产物再真机复验一遍：首屏 20 张卡与「加载更多」同时出现, 点一次 25 张卡、去重后仍是 25、末条 `分页测试 01`, 按钮换成「没有更多了」。文档同步：`README.md` 与 `backend/README.md` 的 `/posts` 一行补 `?before=` 与 `next_cursor`、用例数改 361 / 157；`db/README.md` 新增「`post` 的两条索引为什么按 `id` 倒序」；`docs/DEPLOY.md` 检查清单加一条翻页核对。 |
