# backend · FastAPI 服务

景点档案的浏览、搜索与推荐接口。**不做地图与定位。**

## 环境

| | 要求 | 原因 |
|---|---|---|
| Python | **3.13** | 与 `recsys/` 的 3.11 物理隔离，两个环境的依赖不可能共存（见 `docs/BASES.md`） |
| RecBole | **绝不安装到这里** | API 只读 `db/rec_result` 表。有测试（`tests/test_no_recbole.py`）在守这条线 |
| 数据库 | PostgreSQL 14+ | 测试默认跑 SQLite 内存库，本地不需要装 PostgreSQL |

## 起服务

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env            # 按需改 DATABASE_URL

.venv\Scripts\uvicorn app.main:app --reload
# 文档: http://127.0.0.1:8000/docs
```

> Windows 中文控制台（代码页 936）下 `pip` 会用 GBK 去解 `requirements*.txt`（UTF-8，含中文注释），
> 直接报 `UnicodeDecodeError`。装依赖前先 `$env:PYTHONUTF8 = 1`（或 `chcp 65001`）。

## 测试

```bash
cd backend
.venv\Scripts\python -m pytest
```

- 默认跑在 **SQLite 内存库**上，本地不需要 PostgreSQL，214 个用例（8 个对拍用例无 PostgreSQL 时跳过）约 25 秒。
- `pytest.ini` 把 `app.*` 抛出的 DeprecationWarning 提升为 error —— 依赖库的废弃用法不会再悄悄积累。
- 需要 PostgreSQL 的对拍测试（`tests/test_schema_parity.py`）在没有 `TEST_DATABASE_URL` 时**跳过**，不会假装通过：

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/attraction_atlas .venv\Scripts\python -m pytest
```

## 接口

前缀 `/api/v1`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 健康检查。数据库连不上返回 `degraded` 而不是 500 |
| GET | `/attractions` | 列表：分页 + 分类/城市/标签筛选 + 关键字 + 排序 |
| GET | `/attractions/{id_or_slug}` | 详情（含图集、来源与许可） |
| GET | `/attractions/{id_or_slug}/similar` | 相似景点，内容相似度，**不需要任何用户行为** |
| GET | `/categories` | 分类 + 各分类下已发布景点数 |
| GET | `/tags` | 标签 + 数量（只返回有景点的） |
| POST | `/events` | 行为埋点：`view` / `favorite` / `rate` / `share` |
| GET | `/recommendations` | 推荐。`user_id` 或 `device_id` 二选一 |
| GET | `/ai/status` | AI 入口是否可用。**永远 200**，不配模型时 `available=false`，前端据此隐藏入口 |
| POST | `/ai/search` | 用一句话找景点。模型只产出筛选条件、**不产出景点**，解析失败降级成关键词检索 |
| POST | `/ai/ask` | 就某个景点问一句。答案受该景点档案约束，数字要能在档案里溯源 |
| POST | `/ai/recommend-notes` | 润色推荐理由。**推荐顺序不经过模型**，只改措辞 |
| POST | `/search/semantic` | 按意思找景点。向量不可用 / 没有向量 / 维度不一致时**退回关键词检索**，仍返回 200 |
| POST | `/itineraries` | 提交一次行程生成。202 受理并返回 token；命中同一 owner 的同一份需求返回 200，不重复计费 |
| GET | `/itineraries/{token}` | 按**不可枚举** token 取行程：`pending` / `generating` / `succeeded` / `failed` / `rejected` |

### 列表参数

| 参数 | 说明 |
|---|---|
| `page` / `size` | 1 起。`size` 默认 20，超过 `max_page_size`(100) 会被压到上限 |
| `category` / `tag` | slug |
| `city` | 精确匹配 |
| `q` | 关键字，匹配 `name` / `name_en` / `summary`，大小写不敏感 |
| `sort` | `rating`(默认) / `newest` / `name`。都以 `id` 作为最后的排序键，保证分页稳定 |

### 示例

```bash
curl "http://127.0.0.1:8000/api/v1/attractions?city=杭州市&tag=free&q=湖"
```

```json
{
  "items": [{
    "id": 1, "slug": "west-lake", "name": "西湖", "name_en": "West Lake",
    "summary": "三面环山的淡水湖",
    "category": {"slug": "nature", "name": "自然风光"},
    "city": "杭州市", "province": "浙江省",
    "tags": [{"slug": "free", "name": "免票"}],
    "cover_image": null, "rating_avg": 0.0, "rating_count": 0,
    "ticket_price": 0.0, "suggested_hours": 4.0
  }],
  "page": 1, "size": 20, "total": 1
}
```

## 设计要点

- **只有 `published` 对外**。`draft` / `archived` 在列表、详情、埋点里一律 404 或不出现。
- **推荐不在这个进程里算模型**。`/recommendations` 走三级降级，**任何情况下都不返回空列表**：
  1. `rec_result` 里有该用户最新一批 → 直接用，`algo` 与 `reason` 来自表（训练之后被下架的景点会被过滤掉）
  2. 没有 → 拿用户最近互动过的景点当种子，用内容相似度算（`content_based.py`），已互动过的不再推
  3. 连种子都没有（新用户）→ 评分最高的已发布景点兜底，`algo=popular-fallback`
  结果按 `(user_id, limit)` 做 60 秒 TTL 内存缓存；上报行为时立刻作废该用户的缓存。
- **评分只从 `behavior_log` 聚合**。`POST /events` 收到 `rate` 后会重算该景点的
  `rating_avg` / `rating_count`（`app/aggregates.py`）。口径是「同一用户只算最后一次评分」——
  否则反复改分的人会获得更高权重。种子数据里评分为 0，不伪造。
- **`rating` 只属于 `rate` 事件**。数据库用 CHECK 拦「rate 缺 rating」，API 两个方向都拦。
- **与 `db/schema.sql` 是双份 DDL**，靠 `tests/test_schema_parity.py` 在 CI 的 PostgreSQL 上对拍，
  表名与列名不一致直接失败。

## 目录

| 路径 | 说明 |
|---|---|
| `app/main.py` | 应用入口、CORS、路由挂载 |
| `app/config.py` | 配置（环境变量覆盖） |
| `app/db.py` | 引擎与会话 |
| `app/models.py` | ORM 模型，与 `db/schema.sql` 对应 |
| `app/schemas.py` | 出入参 Pydantic 模型（前端按它写类型） |
| `app/aggregates.py` | 从 `behavior_log` 重算评分聚合 |
| `app/api/` | 路由：health / attractions / categories / events |
| `app/recommend/content_based.py` | 内容相似度打分（纯静态字段，不需要行为数据） |
| `app/recommend/service.py` | 三级降级、理由生成、TTL 缓存 |
