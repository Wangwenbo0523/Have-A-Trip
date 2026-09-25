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
| `TRIP_GENERATE_RETRIES` | 模型输出不合法(如漏排某一天)时带着失败原因重试几次，默认 1；`0` 表示不重试。重试花的 token 照样计入限额 |
| `TRIP_POLL_MAX_SECONDS` | 前端轮询上限（秒），随响应下发，默认 90 |
| `TRIP_STALE_AFTER_SECONDS` | `generating` 超过这么久没心跳视为进程已死，默认 180 |
| `GEO_IP_PROVIDER` | `none`(默认) / `ipapi` / `custom`。首页「出去走走」按 IP 猜城市用，**默认关闭**：不配就一个外部请求都不发，接口直接退回全国随机 |
| `GEO_IP_BASE_URL`、`GEO_IP_API_KEY` | `custom` 必须给地址（支持 `{ip}` 占位，没有就拼在路径末尾）；需要鉴权的服务会带成 `Authorization: Bearer <key>` |
| `GEO_IP_TIMEOUT_SECONDS` | 归属地查询超时，默认 1.5 秒。宁可退回随机，也不让它拖慢首页 |
| `GEO_TRUST_FORWARDED_FOR` | 默认 `false`。在反向代理后面部署时要打开，否则后端只看到代理的地址（多半是私网，等于永远认不出位置）。打开前请确认代理**覆盖**而不是追加 `X-Forwarded-For` |
| `SERVE_FRONTEND` | `false`(默认) / `true`。让这个 API 进程自己托前端产物（单进程形态，见第四·五节）。不设就等于以前的行为 |
| `FRONTEND_DIST` | 前端产物目录，只在 `SERVE_FRONTEND=true` 时有意义。留空按仓库位置算（`<仓库>/frontend/dist`），与进程 cwd 无关 |

健康检查用 `GET /api/v1/healthz`：数据库连不上时它返回 `degraded` 而不是 500，
所以不要拿 HTTP 200 当「一切正常」，要读 `status` 字段。

**按位置推荐（可选）**：配了 `GEO_IP_PROVIDER` 之后，首页「出去走走」会拿访客 IP 去问一次归属地，
只取城市/省份名做**同城 → 同省 → 国内 → 全部**的四级就近抽取（库里的 `lat/lon` 全是 NULL，算不出公里数）。
第三级按**库内主国**（`country_code=CN`，与 `/stats` 的境内/境外同一口径）收口，因为库里 40 条境外景点摊在
30 来个国家，不收口首页第一屏就会推出境外的景点；访客**已知在境外**时跳过这一级，直接走全部随机，不为
每个国家只有一两条的地方做国别特判。四条边界：① 位置只用于这一次查询 —— 不落库、不写 cookie、不返回坐标，
日志里也不记；② 服务超时/连不上/返回的写法对不上库内取值时一律**退回国内随机**并在响应里标 `scope=nation`，
不是报错；③ ip-api 免费档
45 次/分钟且只提供 http，按「每次打开首页一次」的量级够用，量大了请换自建服务（`GEO_IP_PROVIDER=custom`）。
**不要把 `GEO_TRUST_FORWARDED_FOR` 当默认打开**：那个头谁都能写，信了就等于让伪造的头把所有人指到同一个城市。

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

## 四·五、单进程形态（不用 nginx：本机应用 / 单机部署）

前端产物也可以**由 API 进程自己托**，省掉中间那一层：

```bash
cd backend
SERVE_FRONTEND=true FRONTEND_DIST=/srv/have-a-trip/frontend/dist \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100
```

打开 `http://127.0.0.1:8100/` 就是应用：界面与 `/api` 同源同端口。仓库里 Windows 那条**本机应用**路径（`damo.cmd` / `scripts/damo-app.ps1`）走的就是这个形态 —— 装一次依赖，双击即用，关窗即停。

四条边界（都在 `backend/app/web.py`，`backend/tests/test_web.py` 逐条断言）：

- **默认关闭**：`SERVE_FRONTEND` 不设或为 `false` 时行为与以前完全一致（`/` 返回 API 自述 JSON，未知路径 404 JSON）；`dist` 不存在时同样退回 JSON，不会 500
- **不抢 API 的路**：`api/`、`docs`、`openapi.json`、`redoc` 前缀先判，`/api/no-such` 仍是 404 JSON，不会被 SPA 壳吞成 200
- **不认字面路径以外的东西**：拼出来的文件路径必须仍落在 `dist` 里才算数（`../` 与指向外部的符号链接一律挡掉，命中就回落 `index.html`），`dist` 外的一个字节都读不到
- **缓存分开对待**：`/assets/**` 是 vite 带内容哈希的产物，回 `public, max-age=31536000, immutable`；`index.html` 回 `no-store`，否则改版后用户拿到的是旧壳

> `FRONTEND_DIST` 留空时按**仓库位置**算（`<仓库>/frontend/dist`），与进程 cwd 无关 —— 从别处起服务也认得出产物在哪。
> 生产上仍建议「反向代理 + 静态托管」那套（上面第四节）：静态文件交给 nginx / Caddy 比让 Python 读磁盘更划算，还能顺手做 gzip 与 CDN。这条形态的价值在**本机应用**与不需要代理的单机部署。

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
- [ ] 动态区：`db/schema.sql` 已把 `post` 表与 `0004_posts` 版本记录建出来（`select count(*) from information_schema.tables where table_schema='public';` 应为 16，`select version from schema_version;` 里有 `0004_posts`）；`POST_DAILY_LIMIT` 压到 1 试一次，第 2 次应返回 429 且 `detail.reason` 是 `daily_limit_exceeded`；发一条再删掉，`GET /api/v1/posts?device_id=<你的>` 的 `used_today` 应回到 0
- [ ] 动态翻页：库里造满一页以上（> `DEFAULT_PAGE_SIZE`，默认 20）时 `GET /api/v1/posts?size=1` 的 `next_cursor` 不为 `null`，
      拿它当 `?before=` 取下一页不重复（`?page=` 与 `?before=` 一起给是 422），一直翻到 `next_cursor` 为 `null` 为止条数刚好等于 `total`
- [ ] 若 `EMBEDDING_PROVIDER` 指向云端：确认**景点档案文本**出境已过合规（离线向量化会把景点描述发给服务商，见 `docs/LICENSE-AUDIT.md` 第七节）
- [ ] 若开了 `GEO_IP_PROVIDER`：从公网访问 `/api/v1/attractions/nearby` 能拿到 `scope=city` 或 `scope=region`（本机 `127.0.0.1` 一定走 `nation`，那是正常的）；反代部署时 `GEO_TRUST_FORWARDED_FOR` 已打开，且代理是**覆盖**而不是追加该头
- [ ] 若没开 `GEO_IP_PROVIDER`：`/api/v1/attractions/nearby` 仍返回三个、`scope=nation`，且三个的
      `country_code` 全是 `CN`（这就是库内主国那一级在起作用），过程中没有任何外部归属地请求
- [ ] 刷新 `/attraction/<某个 slug>` 不 404（SPA 回落生效）
- [ ] 静态素材与生成脚本一致：`python scripts/make_favicon.py --check`、`python scripts/make_attraction_covers.py --check`
      与 `python scripts/build_cn_attractions.py --check` 都通过（一次跑完用 `python scripts/verify_all.py`）
- [ ] 前端产物里没有任何地图 SDK：`grep -rIn "leaflet\|mapbox\|ol/" dist/assets` 应为空
- [ ] （可选）要用模型补景点简介时, 在**本地**跑 `python scripts/draft_attraction_summaries.py`, 逐条核对生成的待审 SQL 后再抄进 `db/seed/seed.sql`;
      **不要在部署机上直接执行** `db/seed/drafts/` 里的文件
- [ ] 用单进程形态（`SERVE_FRONTEND=true`）时：`/` 给的是 `dist/index.html` 且 `Cache-Control: no-store`，`/assets/*` 是 `immutable`，`/api/no-such` 仍是 404 JSON
- [ ] 用单进程形态时：`curl --path-as-is 'http://127.0.0.1:8100/..%2f..%2fpackage.json'` 拿不到 `dist` 外的文件，且监听地址只有回环（`ss -ltnp | grep 8100`）
- [ ] 备份策略覆盖 PostgreSQL
- [ ] `/api/v1/stats` 的 `attraction_total` 与 `/api/v1/sources` 的一致，`needs_attention` 同为一个值 —— 看板与声明页看的是同一份聚合，两边对不上说明有人改了一边
