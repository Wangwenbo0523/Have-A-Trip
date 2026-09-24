# 部署

形态：**前端静态产物 + API 进程 + PostgreSQL**。三个部件可以同机也可以分开，反正都不需要地图服务。

```
浏览器
  |  https
  v
反向代理 (nginx / Caddy)  --/-->  前端静态产物 dist/
                          --/api-->  FastAPI 进程 (uvicorn)
                                          |
                                          v
                                     PostgreSQL
                                          ^
                                          |  离线写入推荐结果
                                     RecBole 训练任务 (Python 3.11, cron)
```

## 一、先记住三件事

1. **`VITE_API_BASE` 是构建期变量**。Vite 会把它在 `npm run build` 时**写死进产物**，
   运行期改环境变量没用。改地址必须重新构建。
2. **API 进程绝不能装 RecBole**。RecBole 的依赖把 Python 上限锁在 3.11，与 API 的 3.13 不可能共存，
   也在 CI 里有守线（`backend/tests/test_no_recbole.py`）。两者用不同的 venv。
3. **`.env` 不进仓库**，`.env.example` 才是模板。

## 二、数据库

```bash
createdb attraction_atlas
psql -d attraction_atlas -f db/schema.sql      # 幂等: 重复执行不报错
psql -d attraction_atlas -f db/seed/seed.sql   # 种子数据, 生产按需
psql -d attraction_atlas -f db/seed/images.sql # 配图元数据, 生产按需
```

这三个文件都是 `CREATE ... IF NOT EXISTS` / `ON CONFLICT` 写法，
所以可以直接放进部署脚本重复执行，不需要单独的迁移框架。
`db/schema_version` 表记录了已应用的版本。

## 三、API 进程

```bash
cd backend
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # 改 DATABASE_URL 与 CORS_ORIGINS
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

生产建议跑在反向代理后面、只监听 127.0.0.1。systemd 单元示例：

```ini
[Unit]
Description=Have-A-Trip API
After=network.target postgresql.service

[Service]
WorkingDirectory=/srv/have-a-trip/backend
EnvironmentFile=/srv/have-a-trip/backend/.env
ExecStart=/srv/have-a-trip/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

需要配的环境变量：

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pw@host:5432/attraction_atlas` |
| `CORS_ORIGINS` | 前端 origin，逗号分隔。同源部署（由反向代理统一入口）时其实用不到，但留着不碍事 |
| `REC_CACHE_TTL_SECONDS` | 每用户推荐结果的短 TTL 缓存，默认 60 秒 |
| `LLM_PROVIDER` | `none`(默认) / `ollama` / `deepseek` / `openai` / `custom`。留空即关闭 AI 入口 |
| `LLM_MODEL`、`LLM_BASE_URL` | 留空用 provider 预设值；`custom` 必须自己给 |
| `LLM_API_KEY` | 云端 provider 需要。**只放环境变量**，绝不进仓库 |
| `LLM_TIMEOUT_SECONDS` | 模型调用超时，默认 20 秒。宁可降级成关键词检索，也不让用户干等 |
| `LLM_CACHE_TTL_SECONDS` | 同一句话解析结果的进程内缓存，默认 300 秒；`0` 表示不缓存 |
| `EMBEDDING_PROVIDER` | `inherit`(默认，跟随 `LLM_PROVIDER`) / `none` / `ollama` / `deepseek` / `openai` / `custom`。不配就是跟随 |
| `EMBEDDING_MODEL`、`EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY` | 留空用 provider 预设；`custom` 必须自己给 `EMBEDDING_BASE_URL` 与 `EMBEDDING_MODEL`。**注意 `deepseek` 预设没有向量模型**，那边只有对话接口 |
| `EMBEDDING_DIM` | `0`(默认) = 以服务商返回的维度为准；给正数则强校验，不符直接报错 |
| `EMBEDDING_BATCH_SIZE` | 一次请求塞多少条文本，默认 16。批次太大有的网关会回 413 |
| `SEMANTIC_DEFAULT_LIMIT`、`SEMANTIC_MAX_LIMIT` | 语义检索默认与上限条数 |
| `SEMANTIC_VECTOR_WEIGHT`、`SEMANTIC_STRUCTURED_WEIGHT` | 相似景点混合排序里向量分与结构化分的权重 |
| `TRIP_DAILY_LIMIT` | 每个 owner（登录按用户、匿名按设备）每天能提交几次行程，默认 5；`0` 表示不限 |
| `TRIP_GLOBAL_DAILY_TOKEN_BUDGET` | 全站合计每天能烧多少 token，默认 200000；超了新请求返回 429。`0` 表示不限 |
| `TRIP_CANDIDATE_LIMIT` | 交给模型的候选景点条数，默认 40。**这是成本的主要旋钮** |
| `TRIP_MAX_TOKENS`、`TRIP_TIMEOUT_SECONDS` | 行程生成的输出上限与调用超时（默认 2000 / 60 秒） |
| `TRIP_POLL_MAX_SECONDS` | 前端轮询上限（秒），随响应下发，默认 90 |
| `TRIP_STALE_AFTER_SECONDS` | `generating` 超过这么久没心跳视为进程已死，默认 180 |

健康检查用 `GET /api/v1/healthz`：数据库连不上时它返回 `degraded` 而不是 500，
所以不要拿 HTTP 200 当「一切正常」，要读 `status` 字段。

## 四、前端静态产物

```bash
cd frontend
npm ci
# 前端与 API 不同源时, 构建前先设好; 同源(反向代理统一入口)则留空即可
export VITE_API_BASE=https://example.com/api/v1
npm run build          # 产物在 dist/
```

把 `dist/` 交给 nginx 或任意静态托管即可。因为是单页应用，**需要把未知路径回落到 `index.html`**，
否则刷新 `/attraction/west-lake` 会 404：

```nginx
server {
    listen 443 ssl;
    server_name example.com;

    root /srv/have-a-trip/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;      # SPA 回落
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

同源部署（上面这种）时 `VITE_API_BASE` 留空，前端会请求 `/api/v1`，由 `/api/` 这条规则转发过去。

## 五、推荐离线任务

推荐结果由离线任务写进 `rec_result` 表，API 只读它。所以：

- 部署 API **之前**不需要先训练；`rec_result` 为空时推荐接口会自动走内容相似度 / 热门兜底，不会返回空。
- 训练任务跑在**独立的 Python 3.11 环境**里（`recsys/requirements.txt`），建议 cron 每天一次：

```bash
# /etc/cron.d/have-a-trip-recsys
45 2 * * * cd /srv/have-a-trip && ./recsys/.venv/bin/python recsys/export_interactions.py
0  3 * * * cd /srv/have-a-trip && ./recsys/.venv/bin/python recsys/run_recbole.py
15 3 * * * cd /srv/have-a-trip && ./recsys/.venv/bin/python recsys/write_back.py
```

三步缺一不可：先导出交互，再训练，最后回写。后两步不带参数，各自取上一步最新的一批产出。

数据量不足时脚本会明确跳过并留下日志，**退出码仍是 0** —— 冷启动阶段「还没到火候」不是故障，
不该让 cron 发告警。

## 五·五、向量与行程

**景点向量**由 `scripts/build_embeddings.py` 灌，它和 API 跑在**同一个环境**里
（不引 torch，走服务商的 `/embeddings`，所以没有第二套依赖要维护）：

```bash
export DATABASE_URL=postgresql+psycopg://user:pw@host:5432/attraction_atlas

# 灌之前先看要做什么
python scripts/build_embeddings.py --dry-run
python scripts/build_embeddings.py            # 增量: 只补缺的与指纹变了的
python scripts/build_embeddings.py --report   # 只看覆盖率
```

建议在 `seed.sql` 之后、首次对外之前跑一次，之后挂在 cron 上（景点档案改了就重跑，
脚本按 `content_hash` 判断，没变的不重算）。

**换向量模型**：改 `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` 之后必须重跑一次
`build_embeddings.py`。指纹里含模型标识，所以增量更新会**自动重建全部行** ——
不重建的话新查询向量与旧库存向量不可比，表现是语义检索整体返回空。旧模型的向量
可以留着（不会参与检索）也可以删掉，检索只认行数最多的那个模型。

**行程回收**：用户提交完就关页面的话，后台生成可能留下卡住的行。读取路径会自愈，
批量清理用：

```bash
python scripts/reclaim_itineraries.py --dry-run
python scripts/reclaim_itineraries.py
```

判据是**心跳过期**而不是「跑了多久」——多 worker 下按耗时一刀切会误杀别人正在跑的任务。

**限额按东八区自然日结算**，计数器在 `trip_quota` 表里，不依赖 Redis。
多实例部署时它天然是全局的（同一张表、同一条 `UPDATE ... WHERE used < :limit`）。

## 六、上线前检查清单

- [ ] `python scripts/license_gate.py --strict` 通过（**用装了 `backend/requirements.txt` 的解释器跑**）
- [ ] `cd backend && pytest -q` 通过；`TEST_DATABASE_URL` 已设置，schema 对拍测试没有跳过
- [ ] `cd frontend && npm run typecheck && npm test && npm run build` 通过
- [ ] `db/schema.sql` 在目标库上跑过至少两次（验幂等）
- [ ] `/api/v1/healthz` 的 `status` 是 `ok`
- [ ] `/api/v1/sources` 的 `needs_attention` 是 `false`（库里有 share-alike 来源却没登记修改状态时为 `true`，声明页会出红色告警）
- [ ] 配了 `LLM_PROVIDER` 时 `/api/v1/ai/status` 的 `available` 是 `true`；**没配时它必须是 `false`**（否则说明密钥或地址写错了，AI 入口会以不可用的状态对外，页面不显示）
- [ ] 若 `LLM_PROVIDER` 指向云端：确认数据出境已过合规，且 `LLM_API_KEY` 只存在于环境变量里（`git log -p -- .env` 应为空）
- [ ] 语义检索：`python scripts/build_embeddings.py --report` 的「已向量化」等于「已发布景点」；`/api/v1/ai/status` 的 `embedding_available` 与 `embedded` 与它一致
- [ ] **换过向量模型或改过拼串口径**：已重跑 `build_embeddings.py`，且 `--report` 里没有多种维度（同一模型出现两种维度会让检索整体退回关键词）
- [ ] 行程限额与预算按预期生效：`TRIP_DAILY_LIMIT` / `TRIP_GLOBAL_DAILY_TOKEN_BUDGET` 压到 1 试一次，第 2 次应返回 429 且 `detail.reason` 对得上
- [ ] `python scripts/reclaim_itineraries.py --dry-run` 没有长期积压的 `generating`
- [ ] 若 `EMBEDDING_PROVIDER` 指向云端：确认**景点档案文本**出境已过合规（离线向量化会把景点描述发给服务商，见 `docs/LICENSE-AUDIT.md` 第七节）
- [ ] 刷新 `/attraction/<某个 slug>` 不 404（SPA 回落生效）
- [ ] 静态素材与生成脚本一致：`python scripts/make_favicon.py --check` 与 `python scripts/make_attraction_covers.py --check` 都通过
- [ ] 前端产物里没有任何地图 SDK：`grep -rIn "leaflet\|mapbox\|ol/" dist/assets` 应为空
- [ ] （可选）要用模型补景点简介时, 在**本地**跑 `python scripts/draft_attraction_summaries.py`, 逐条核对生成的待审 SQL 后再抄进 `db/seed/seed.sql`;
      **不要在部署机上直接执行** `db/seed/drafts/` 里的文件
- [ ] 备份策略覆盖 PostgreSQL
