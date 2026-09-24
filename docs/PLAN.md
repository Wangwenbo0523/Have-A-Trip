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

### 明确不做（非目标）

| 不做 | 原因 |
|---|---|
| 地图、定位、轨迹 | 需求明确排除。`ol` 依赖与 `MapView/*` 在 S3 删除 |
| 路线规划、导航、订票、支付 | 与「景点大全」无关，且都是长期维护负担 |
| 浏览器定位权限 | `navigator.geolocation` 已删（commit `2f8ae7f`），后续任何改动都不得引入 |
| 用户上传 / UGC 内容 | 审核成本高，一期不做 |

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

**关键路径**：`S0 → S1 → S2 → S8`。S3/S4/S5 不在关键路径上，晚做不会拖整体。

---

## 五、每步执行简报

### S0 · 数据模型

**上下文**：`db/` 目前是空目录。这是全项目地基——S1 的实体、S2 的推荐结果、S6 的交互导出都读它，所以**先冻结表结构再写代码**，避免接口写完又改字段。

**任务清单**

1. `db/schema.sql`：9 张表（见下表）+ 迁移记录表
2. `db/seed/seed.sql`：分类、标签、3 个示例景点（够跑通接口，不追求内容量；S7 已扩到 50 个）
3. `db/README.md`：怎么建库、怎么执行、字段口径说明

**表设计**

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
| 数据来源 | **全部自采**，没有引入任何第三方数据集。50 条的 `source` 都是「Have-A-Trip 自采（公开事实信息）」、`license` 为 `MIT`，因此**不存在 share-alike 传染到数据库**的问题 |
| 内容规模 | 50 个景点覆盖 21 个省级行政区；7 个分类（自然 12 / 历史 10 / 博物馆 6 / 地标 6 / 古镇 6 / 宗教 5 / 乐园 5）、19 个标签、175 条标签关联 |
| 幂等写法 | `seed.sql` 改成**声明式**：分类 / 标签 / 景点用 `ON CONFLICT (slug) DO UPDATE`，标签关联按 `source` 认领后删掉重建。旧版的 `DO NOTHING` 不会修好早期跑过种子的库 |
| 不造假 | 坐标全 `NULL`、评分全 0、票价只在**确定免费**时写 `0`（5 条）、`attraction_image` 一条不插 |
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
| 2026-09-25 | v1.8 | 占位图标换成自绘：新增 `scripts/make_favicon.py`（标准库程序化生成 7 档尺寸），`public/earth.ico`（225 KB，出处无从查证）删除，图标落到约定路径 `public/favicon.ico`（8.5 KB）；`index.html`、`manifest.json`、`Credits.tsx`、`docs/LICENSE-AUDIT.md` 同步；`license-gate` 加一道 `make_favicon.py --check` |
