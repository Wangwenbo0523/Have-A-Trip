# Have-A-Trip · 景点大全

一个以「景点档案 + 推荐」为核心的旅游应用。**只做景点介绍、旅游方案、检索与推荐——不做地图，不做定位。**

前端是 React 单页应用，后端是 FastAPI，数据在 PostgreSQL，推荐结果由离线任务（RecBole）批量算好写回。
没有地图 SDK，没有地理围栏，没有轨迹上报。

![30 秒演示：首页、景点列表、AI 搜索、数据看板、景点对比、AI 排行程、中英双语与深浅色主题](docs/demo.gif)

## 现在能跑到什么程度

| 模块 | 状态 | 说明 |
|---|---|---|
| `db/` | ✅ | 16 张表 + 视图 + 触发器，幂等可重复执行；1385 个景点、10 个分类、32 个标签、156 个旅游方案（带方案的只有自采的那 156 条） |
| `backend/` | ✅ | 景点列表/详情/搜索、分类标签、来源与许可、看板数据源、行为埋点、推荐接口、随机抽取与就近推荐（按 IP 猜城市，默认关闭）、AI 能力（一句话检索 / 详情页追问 / 推荐理由润色 / 语义检索 / LLM 行程生成，默认关闭）、用户动态区（发动态 / 按景点或按设备看 / 作者删除，匿名无定位）；361 个用例（351 通过，另 10 个 schema 对拍用例需 PostgreSQL） |
| `frontend/` | ✅ | 首页（打开时弹出「出去走走」：按猜到的城市就近抽三个、推荐位带理由且可 AI 润色）、全部景点（含等级筛选与「用一句话找景点」）、分类页、详情页（含旅游方案、站外视频搜索、就这个景点追问）、帮我排行程（提交 → 轮询 → 结果，可打印行程单）、数据看板、景点对比、搜索、动态区（发动态、只看我的、删自己的；景点详情页带「大家在这儿说了什么」）、数据来源与许可页、错误态、页头中英双语与深浅色切换（默认中文、默认深色）；157 用例通过 |
| `recsys/` | ✅ | 三条脚本（导出 → 训练 → 回写）端到端跑通，BPR 离线结果已写回 `rec_result` |
| 数据量 | ✅ | 1385 个景点。**1229 条来自政府公开名录**（中国 A 级旅游景区，5A 331 / 4A 284 / 3A 614，覆盖 31 个省级行政区，`license` 为「政府公开信息（官方名录）」）；**156 条自采**（中国境内 116 + 境外 40，覆盖六大洲 30 个国家，`license` 为 MIT），带简介、标签、旅游方案与封面；配图每个景点一张（1255 张程序化自绘 SVG + 130 张抓自 Wikimedia Commons 的实景照片，作者与许可逐张登记在 `db/seed/photos.json`） |

施工顺序、依赖关系与每步验收标准见 **[`docs/PLAN.md`](docs/PLAN.md)（施工计划表）**。

## 体验与可视化

四件事，共同点是**前端不编造任何数据**，且**没有引入任何新依赖**（许可证卡口仍是零违禁）：

- **深浅色主题**：切换按钮在页头右上角、与语种按钮并排，按钮上写的是**目标主题**的名字。默认**深色**，
  不嗅探 `prefers-color-scheme`（与语种不嗅探 `navigator.language` 同一口径），选择存在
  `localStorage["have-a-trip:theme"]`。两套主题共用同一份组件样式 —— 浅色只覆盖 `frontend/src/index.css`
  里的一组 CSS 变量，不碰尺寸与布局；`index.html` 有一段内联脚本在 React 挂载前把主题写到
  `<html data-theme>`，否则选了浅色的用户每次刷新都会先看到一闪的深色底。
- **数据看板 `/stats`**：KPI、境内/境外、分类分布、A 级与世界遗产分布、来源与许可，全部由新增的
  `GET /api/v1/stats` 从库里现算，来源那一块**复用 `/sources` 的同一份聚合**，不另算一套。
  条形是手写 SVG，**没有引图表库** —— 为几条水平条背一个图表库不划算。档案里没填的取值归到
  `unknown` 档并显示为「未核实」，所以**各档之和一定等于总数**，不会有景点在图上凭空消失。
- **行程单打印**：`/planner` 排好之后有「打印行程单」。`@media print` 摘掉页头、页脚、表单与按钮，
  并把调色板整体换成白底黑字 —— 深色主题直接打印会把整页涂黑。
- **景点对比 `/compare`**：两侧各挑一个景点，八行字段并排。选择器是**可搜索的组合框**：输入即筛、
  ↑↓ 移动高亮、回车落定、Esc 放弃，中英文名都能搜 —— 库里 1385 个景点，原生下拉一次铺开既搜不了也扫不动，
  而这个数字只会继续涨。选择记在 URL 查询串里（`?a=&b=`），对比结果是一条可以直接发给别人的链接；
  **只有从列表里选中才会写回 URL**，手打半个名字不改值，免得发出去的链接指向不存在的景点。
  数据走已有的 `/attractions` 与 `/attractions/{slug}`，**没有为它开新接口**；只有评分标「更高」——
  票价低、时长长都不等于更好，标出来就是替用户下判断。

- **首页「出去走走」**：打开首页弹一次，三个景点由 `GET /attractions/nearby` 抽 —— **尽量近**。
  「近」只到**城市级**：后端拿访客 IP 问一次归属地服务（默认关闭，见 `GEO_IP_PROVIDER`），同城不够用同省补，
  再不够用**国内**补，连国内都不够才轮到全部景点。库里的 `lat/lon` 全是 NULL（见 `db/README.md` 的数据口径），
  算不出公里数，远近只能按「同城 → 同省 → 国内 → 全部」这个层级算；**同城/同省的排在最前面**。
  第三级收口到国内是有原因的：1385 条已发布里有 40 条在境外、摊在 30 来个国家，不收口的话一次要三个仍有
  百分之几的概率掺进境外景点 —— 首页第一屏推一张去加拿大的机票说不通。反过来也不为境外访客按国别抽：那边每个国家只有
  一两条，抽出来等于「就那一条」。这不是定位：位置只用于这一次查询，不落库、不写 cookie、不返回坐标，
  `X-Forwarded-For` 默认不信（谁都能写那个头）。认不出位置时**照常返回国内随机**并在响应里标 `scope=nation`，
  页面上那一行也如实说「没认出你在哪儿」—— 说不清依据的推荐位不如不写。弹窗里有「换一批」。**一次会话只弹一次**（`sessionStorage`）：从「全部景点」
  点回首页也算打开首页，每次都弹会把导航变成一串关窗动作；重开标签页或重开应用算新会话，那时会再弹一次。
  抽不到数据时**不弹**，也不在首页上留一个报错 —— 它是锦上添花，不该喧宾夺主。

## 中英双语

界面文案支持**中文（默认）/ 英文**两套，切换按钮在页头右上角 —— 按钮上写的是**目标语言**的名字：
中文界面显示 `EN`，英文界面显示 `中文`。选择存在 `localStorage["have-a-trip:lang"]`，刷新与换页都保持；
`<html lang>` 与页面标题跟着切换。没存过选择时一律中文，**不嗅探 `navigator.language`**。

**范围口径（重要）**：只有**界面文案**分语种。景点档案 —— 名称、简介、旅游方案、图集图注、来源与许可、
分类名与标签名，以及后端返回的 `note` / `disclaimer` —— 都是数据库里的**内容**，两种语种下原样显示。
所以英文界面下，景点内容仍是中文。

唯一的例外是景点名：英文界面下若 `attraction.name_en` 有值，就用它当标题、中文名当副标题（便于对着现场指示牌找地方）；
**库里只填了少数几条英文名**，缺的景点在英文界面下仍然显示中文名，不替它编一个。

实现见 `frontend/src/i18n/`（一张消息表 + 一个 `t()`，没有引入任何 i18n 依赖）：
`messages.ts` 放文案，`index.tsx` 放 `LanguageProvider` / `useI18n`，内容与文案的边界写在目录注释里。

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
      |            一句话检索: 模型只解析查询条件, 条目仍从库里查(默认关闭)
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
| `scripts/` | 基底钉版记录、许可证卡口、DCO 校验、提交前一把过（`verify_all.py` 跑完本机能跑的静态门禁并汇总）、静态素材生成（`make_favicon.py` 站点图标、`make_attraction_covers.py` 景点配图与 `db/seed/images.sql`、`fetch_commons_photos.py` 抓 Wikimedia Commons 实景照片——需要能出去的代理）、种子渲染（`build_cn_attractions.py` 把官方名录 CSV 渲成 SQL）、离线工具（`draft_attraction_summaries.py` 生成简介草稿，人审后入库）、演示脚本（`demo-offline.ps1` 跑出「不配模型也完整可用」的验收报告）、本机应用启动器（`damo-app.ps1` 单进程起应用并开窗口、`install-damo-app.ps1` 装桌面与开始菜单快捷方式）、打包脚本（`make_installer.ps1` 把仓库打成一个能直接发给别人的 zip） |
| `damo.cmd` | 双击入口（Windows）：起一个单进程应用并开一个独立窗口，见「当应用用」 |
| `installer/` | 简易安装包（Windows）：`install.ps1` 把包装到**当前用户**（复制文件 → 建 venv 装依赖 → 建库灌 schema 与三个种子 → 装快捷方式），`-Uninstall` 卸载，见「做安装包」 |
| `install.cmd` | 安装包的双击入口：解压后双击它就装，`install.cmd -Uninstall` 卸载（真实逻辑在 `installer/install.ps1`） |
| `docs/` | `PLAN.md` 施工计划、`BASES.md` 基底清单、`LICENSE-AUDIT.md` 许可审查、`DEPLOY.md` 部署 |

## 快速起步

需要：Python 3.13、Node 24、PostgreSQL 16。

### 一键起（推荐）

```powershell
# 依赖只装一次
$env:PYTHONUTF8 = 1   # 中文控制台(代码页 936)下 pip 按 GBK 解码 UTF-8 的 requirements 会报 UnicodeDecodeError
cd backend;  python -m venv .venv;  .venv\Scripts\pip install -r requirements-dev.txt;  cd ..
cd frontend; npm install; cd ..

# 连库 → 灌 schema 与种子 → 起后端(8000) → 起前端(5173)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-up.ps1

# 关掉它起的两个进程
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-up.ps1 -Down
```

`scripts/dev-up.ps1` 只干三件事：连一个**已经存在**的 PostgreSQL、按 `db/` 灌数据、起前后端。它不下载不安装任何东西，也不写 `.env`；日志与 pid 落在 `.dev/`（已 ignore）。找不到 `psql` 时打印起库指引后退出，不瞎猜。

| 常用参数 | 用途 |
|---|---|
| `-PgBin C:\pgtemp\pginstall\bin -PgPort 55432` | 指到便携实例（默认 `5432`，不通时自动试探 `55432`） |
| `-BackendPort 8010 -FrontendPort 5174` | 换端口；vite 代理跟着走（`DEV_API_PROXY`） |
| `-NoSeed` | 只灌 schema，不灌种子数据 |
| `-LlmProvider ollama` | 顺手把 AI 检索开成本地 ollama（其余 `LLM_*` 见 `backend/.env.example`） |
| `-NoBackend` / `-NoFrontend` | 只起一半 |

### 当应用用（双击 `damo.cmd`）

上面那条是**改代码**用的（dev server + 热更新）；想在机器上像应用一样用，走这条。依赖装法与上面完全相同，之后：

```powershell
# 起一个单进程应用(API 连托 frontend/dist), 用独立窗口打开, 关窗即停
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/damo-app.ps1

# 改了前端代码再进去
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/damo-app.ps1 -Rebuild

# 把 damo 放到桌面与开始菜单(当前用户, 不需要管理员)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-damo-app.ps1

# 收掉它起的实例
damo.cmd -Down
```

装好之后不用再开命令行：双击桌面上的 `damo` 就行（`damo.cmd` 是它的等价物）。

这一形态读的是同一份 `backend/.env`（已在 `.gitignore` 里，不进仓库）。按 `.env.example` 把 `LLM_PROVIDER=ollama` / `EMBEDDING_PROVIDER=ollama` 填上并 `ollama pull` 过模型之后，**双击入口就带 AI 能力**（一句话检索、详情追问、推荐理由润色），不必再开命令行；`/api/v1/ai/status` 会如实报告 `available` 与 `embedding_available`，没配就是降级成关键词检索，不是报错。

分工是**改代码 vs 用**：不开 `--reload`、不跑 vite dev server，而是让 FastAPI **一个进程**同时托 `frontend/dist` 与 `/api`（`SERVE_FRONTEND=true`），所以只有一个进程、一个端口，默认 `8100`（与 dev-up 的 8000/8010 错开，两边可以同时开着）。四条约定：

- 不动仓库：日志与 pid 只写 `.dev/`，不生成也不改 `.env`
- 认得出自己：端口上跑着本实例就直接复用，不会再起第二个；端口被**别的**程序占着时只报错退出，不去杀别人的进程
- 关窗即停：窗口一关就把服务收掉（想留着加 `-KeepServer`）
- 只绑 `127.0.0.1`：这是给人在这台机器上用的应用，不对局域网开口

| 常用参数 | 用途 |
|---|---|
| `-Rebuild` | 先重新 build 前端产物（改了前端代码就加它） |
| `-Port 8101` | 换端口 |
| `-DatabaseUrl ...` | 直接指定库；不给就按 dev-up 那套探测（`DATABASE_URL` → 5432 → 55432） |
| `-NoWindow` | 只起服务不开窗口（脚本 / CI 用） |
| `-Down` | 收掉本脚本起的实例 |

### 做安装包（发给别人）

上面两条都要求对方有 Node（得 build 前端）。要把这份东西交给一个只想用的人，走这条：

```powershell
# 打一个 zip 到 dist-installer\（默认用现有的 frontend/dist；它比前端源码旧就直接停下来）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_installer.ps1

# 想看看包里到底装了什么: 留着组装用的暂存目录
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_installer.ps1 -KeepStage
```

拿包的人**解压后双击 `install.cmd`** 就装上了，全程不需要 Node —— 前端产物已经在包里。他要有的只有 **Python 3.13 与 PostgreSQL 16**，这两样不代装：缺哪个就停下来告诉他去哪装。

装的是「用」的形态，落在 `%LOCALAPPDATA%\Programs\Have-A-Trip`（用户级目录，不需要管理员），并建桌面与开始菜单的 `damo` 图标。卸载走开始菜单里的「卸载 damo」，或 `install.cmd -Uninstall`（库与 `backend\.env` 留着不动）。

前端产物是不是新的，打包脚本自己看：`frontend/dist` 只要比 `frontend/src`、`frontend/public` 旧就硬失败（vite 把源在构建期写死进产物，发一份旧前端出去最难回头发现），加 `-Build` 重建即可。

包里装的是**git 跟踪的文件 + 预构建的 `frontend/dist`**：`.git` / `node_modules` / `.venv` / `.dev` / `.env` / 带第三方许可的 `景区名录/` 一律不进包。打包脚本会自己把包翻一遍验这个事，验出不该有的东西就删掉 zip，不让它发出去。

| 安装参数 | 用途 |
|---|---|
| `-TargetDir D:\Apps\Have-A-Trip` | 换安装位置 |
| `-PgBin C:\pgtemp\pginstall\bin -PgPort 55432` | 指到便携 PostgreSQL 实例 |
| `-Database have_a_trip -PgUser postgres -PgPassword ***` | 换库名 / 账号（口令只写进 `backend\.env`） |
| `-SkipDatabase` / `-SkipDeps` | 只复制文件 / 不建 venv（分步装的时候用） |
| `-Uninstall` | 卸载 |

### 离线演示（不配模型也完整可用）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo-offline.ps1 -PgBin C:\pgtemp\pginstall\bin -PgPort 55432
```

`scripts/demo-offline.ps1` 不是第二个启动脚本，而是一份**能跑出来的验收报告**：它自带一个 `attraction_atlas_demo` 库（不碰 `attraction_atlas`），起一个 `LLM_PROVIDER=none` 的后端，把关键接口挨个打一遍并逐条断言，最后给通过率和退出码。16 项里包含「AI 状态如实报不可用」「一句话检索退回关键词仍是 200」「追问降级成档案摘录而不是编」「行程失败必须给出原因」「假 token 一律 404」「超额拒绝带 `reason` 与 `retry_after`」。

默认跑完即关；`-KeepRunning` 留着看 `/docs`，`-Down` 收尾，`-Json` 出机器可读报告。

### 手工起（对照）

```bash
# 1. 数据库
createdb attraction_atlas
psql -d attraction_atlas -f db/schema.sql
psql -d attraction_atlas -f db/seed/seed.sql
psql -d attraction_atlas -f db/seed/attractions_cn.sql   # 官方 A 级景区名录 1229 条
psql -d attraction_atlas -f db/seed/images.sql

# 2. 后端 (http://127.0.0.1:8000, 文档 /docs)
cd backend
set PYTHONUTF8=1              # 同上: 中文控制台下装依赖前必须设
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
cp .env.example .env          # 按需改 DATABASE_URL
#                               想开 AI 检索就在 .env 里配 LLM_PROVIDER(见 .env.example)
.venv/Scripts/uvicorn app.main:app --reload

# 3. 前端 (http://127.0.0.1:5173)
cd frontend
npm install
npm run start                 # /api 由 vite 代理到 8000, 本地免跨域
```

没有 PostgreSQL 也能跑测试：后端测试默认走 SQLite 内存库。生产目标仍是 PostgreSQL。

## 接口一览

前缀 `/api/v1`。契约真身是 `backend/app/schemas.py`，前端类型按它写。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 健康检查（无库时返回 `degraded` 而不是 500） |
| GET | `/attractions` | 列表：`page` `size` `category` `city` `tag` `grade` `q` `sort=rating\|newest\|name` |
| GET | `/attractions/random` | 随机抽 `limit` 个已发布景点（默认 3，上限 12）。**不缓存**，也不问你在哪儿 —— 「随便看看」用它 |
| GET | `/attractions/nearby` | 按 IP 猜的归属地就近抽 `limit` 个（默认 3，上限 12）。四级降级：同城 → 同省 → 国内随机 → 全部景点；响应里带 `located` / `scope` / `city` / `region`。**不缓存**，默认配置（`GEO_IP_PROVIDER=none`）下不发任何外部请求，主页弹窗用它 |
| GET | `/attractions/{id_or_slug}` | 详情（含旅游方案、图集、标签、来源与许可） |
| GET | `/attractions/{id_or_slug}/similar` | 相似景点（内容相似度，不需要用户行为） |
| GET | `/stats` | 景点库总览：只统计已发布景点，与 `/sources` 同一口径。看板页据此渲染，数字不写死在前端 |
| GET | `/categories`、`/tags` | 分类与标签（只统计已发布景点） |
| GET | `/sources` | 数据来源与许可：从 `attraction` / `attraction_image` 聚合，声明页据此渲染 |
| POST | `/events` | 行为埋点：`view` / `favorite` / `rate` / `share` |
| GET | `/posts` | 用户动态列表：只出 `visible`，按时间倒序。筛选是**精确匹配**：`?attraction=<slug>`（某个景点下）、`?device_id=`（我的）；`?viewer=` 只用来算 `mine` 与当天已用名额。翻页两种给法**只能挑一个**：`?page=` 是偏移，`?before=<上一页的 next_cursor>` 是游标（列表与游标同按 `id` 倒序，翻页途中有人发新的也不会重复）；响应里的 `next_cursor` 为 `null` 表示到底了 |
| POST | `/posts` | 发一条动态：正文 1–500 字，可选署名与一个**已发布**景点（挂别的会 404）。不存任何定位 |
| DELETE | `/posts/{id}`?device_id=` | 作者删自己的动态（硬删，删完归还当天名额）。不是作者一律 404 |
| GET | `/recommendations` | 为你推荐，`user_id` 与 `device_id` 二选一 |
| GET | `/ai/status` | AI 入口是否可用。默认配置（`LLM_PROVIDER=none`）返回 `available=false` |
| POST | `/ai/search` | 用一句话找景点：模型把这句话解析成上面的筛选条件，**条目仍从库里查** |
| POST | `/ai/ask` | 就某个景点追问一句：答案只复述该景点的档案字段，档案里没有的一律不作答 |
| POST | `/ai/recommend-notes` | 润色推荐位的理由：**条目、顺序、分数都由 `/recommendations` 决定**，模型只改措辞 |

`grade` 取值 `5A` / `4A` / `3A` / `heritage`。前三个是中国景区的质量等级（GB/T 17775），
`heritage` 表示「已列入 UNESCO 世界遗产名录」—— 世界遗产没有 A 级，所以它与 A 级各占一个取值，
不合并成一条刻度。`a_level` / `heritage` 为空的景点表示该项**未核实**，不是「没有等级」。

`/attractions/nearby` 的 `scope` 取结果里**最远**的那一层（三个全在同城是 `city`，有同省补进来的算 `region`，
有国内（库内主国）景点补进来的算 `nation`，连国内都凑不满、掺进了境外景点才是 `world`）；`located` 表示
「在你**库里有收录**的城市/省份上对上了」，不是「认出了你的 IP」，所以 `located=false` 时主页那一行会如实说
位置没认出来。归属地只到城市级（直辖市常常只到区），境外城市多数对不上库内取值，同样会退回国内随机。
五种说法（同城 / 同省 / 就近不够 / 没认出来 / 连国内都不够）都在 `frontend/src/i18n/messages.ts` 的
`home.picks.*`，每一种都是真话。

`status != published` 的景点不会出现在任何接口与推荐里。`/recommendations` 保证非空：
离线结果 → 内容相似度 → 热门兜底，三级降级，每条都带 `reason`。

`/ai/*` 默认是关的（`LLM_PROVIDER=none`）：不配模型时应用照常运行，页面不显示 AI 入口。
开启方式见 `backend/.env.example`，本地 Ollama 与云端 API 用同一段代码，只换环境变量。
**模型只产出查询条件，不产出景点条目** —— 结果永远由上面的 `/attractions` 查询给出，
所以它没有编造景点的机会；取值对不上的一律丢弃并如实告诉用户。模型不可用或超时时
降级成关键词检索（HTTP 200 而非 500），不是错误页。完整口径见 `docs/LICENSE-AUDIT.md` 第七节。

动态区（`/posts`）是**唯一**由用户产出自由文本的地方，边界写在 `backend/app/api/posts.py` 的文件头：没有账号体系（匿名 `device_id` + 可选署名）、没有定位、没有图片上传、没有自动审核；限流 `POST_DAILY_LIMIT`（默认 10 条/设备/天，按东八区自然日），计数器与行程共用 `trip_quota` 但带 `post:` 前缀，两边名额互不吃。作者删除是**硬删**，运营下架是 `update post set status='hidden'`（软删）—— 两件事，不合成一个开关。

## AI 事实卡

评审最常追问的是「你做的 AI 部分，凭什么信得过」。下面每一条都是代码里已有的约束，不是口号；
「在哪能验证」一列给的是可以直接点开或直接跑的位置。

| 决策 | 为什么 | 在哪能验证 |
|---|---|---|
| 模型只把一句话解析成查询条件，**不产出景点条目** | 让模型写景点介绍就无法核实，也保证不了库里有这个地方。结果集永远由 `/attractions` 给出，它没有编造的机会 | 返回的 `items` 全部来自库；`backend/app/llm/interpret.py` |
| 取值走**白名单 + 库内双向校验** | 模型会写出「5A 级」「杭州」之外的写法，直接拿去查询就是空结果或错结果 | 越界取值逐条丢弃并如实说明；`backend/tests/test_ai.py` |
| 模型不可用时**降级而不是报错** | AI 是增强项不是主链路，它挂了不能把浏览与搜索一起拖垮 | `scripts/demo-offline.ps1` 断言 `degraded=true`、仍有结果、HTTP 200 |
| 追问只复述档案：**数字溯源 + 主题词两关** | 景点问答最容易编的恰恰是开放时间、票价、交通，而这几项库里没有 | 答案里每个数字都要能在档案里找到；档案里没依据的主题词一律不提，不过关就换成后端拼的档案摘录。`backend/app/llm/ask.py` |
| 行程里每个 `attraction_id` **必须在候选集内**，越界整份拒掉 | 模型会「顺手」加入不在候选里的景点，而这种错在页面上看起来还挺合理 | `backend/app/trip/validator.py`；`backend/tests/test_itinerary.py` |
| 候选**先按城市收窄** | 「北京三日」排进西安兵马俑这类错最难被发现 | 认城市靠扫库内城市名，不为它多调一次模型；同城排不满才放宽。`backend/app/trip/service.py` |
| 向量**存 JSON，不引 pgvector** | 引扩展会同时带来「建表要超级用户」「CI 换镜像」「SQLite 与 PG 两套查询路径」三份复杂度；全库百来条算全量余弦只要几毫秒 | `backend/app/search/vectors.py`；`license_gate.py --strict` 无新增依赖 |
| 向量指纹含 **model + dim + pipeline_version** | 换模型后旧向量必须整体失效，否则会拿两种模型的向量算余弦 —— 不报错，但结果毫无意义 | `backend/app/search/canonical.py`；`backend/tests/test_embedding_client.py` |
| 按次计费的能力**先有限额与预算** | 行程是第一个按次计费的能力，没有限额，一个脚本就能把当月预算烧完 | 单条 `UPDATE ... WHERE used < :limit` 加 `rowcount` 判断，不引 Redis；超额 429 带固定 `reason` 与 `retry_after` |
| 需求原文**不入库**，只存 hash；对外只用 token | 主键自增，用 id 取行程就能从 1 开始遍历所有人的需求原文，这类越权不需要任何技巧 | `backend/app/api/itineraries.py`；`backend/tests/test_itinerary.py` |
| 请求体带固定 **seed** | `temperature=0` 只说明「别自由发挥」，不等于可复现 —— ollama 每次请求自己抽种子 | `LLM_SEED`（给负值表示不带该字段）；`backend/app/config.py` |

> 这一节只列**已经落在代码里**的约束。想一次看完它们的效果，跑 `scripts/demo-offline.ps1`：
> 它会把「模型不可用时降级成关键词检索仍返回 200」「行程失败如实给原因」「超额拒绝带原因与重置时间」
> 这些口径当场断言一遍。

## 许可证纪律（重要）

「将来能闭源」靠纪律维持，不是靠运气：

```bash
python scripts/license_gate.py --strict    # 用装了项目依赖的解释器跑, 见下
```

检出 GPL/AGPL/SSPL/CC-BY-NC 即失败，CI 也跑同一个脚本（`.github/workflows/license-gate.yml`）。
当前状态：0 违禁，15 项告警（`certifi` 与 `lightningcss` 及其平台包共 13 项 MPL-2.0，
`psycopg` / `psycopg-binary` 2 项 LGPL）——都是未修改使用的依赖，不触发义务。

提交前想一次跑完这道卡口与其余静态门禁（生成物可复现、种子 SQL 与源文件一致、工作流可解析），
用 `python scripts/verify_all.py`；它会把没覆盖的检查逐条列出来，免得「这里过了」被当成「全过了」。

> 卡口扫的是**运行它的解释器里已安装的包**。用别的虚拟环境（比如自己装过 GPL 工具的）去跑会误报，
> 请用与 CI 一致的环境（`pip install -r backend/requirements.txt`）。

另外四件事必须从第一天做起，否则将来闭源要回头求人：

1. **贡献者签 DCO**（见 `CONTRIBUTING.md`）——没有版权集中，闭源需征得每个贡献者同意。
   CI 的 `dco` 工作流会逐个 commit 校验，`python scripts/check_dco.py` 也能本地跑。
2. **数据层许可单独审**——OSM 是 ODbL、CC BY-SA 有相同方式共享义务，代码干净不代表数据干净。
3. **图片同样算资产**——页头那张来源无从查证的实景照片已经删掉换成 CSS 渐变，见 `docs/LICENSE-AUDIT.md` 第五节。
4. **站外内容只给链接**——B 站等平台的视频仍归上传者与平台所有。本站只放搜索页外链：不内嵌播放器、
   不抓取、不转载、不用对方标识。抓回来的素材一旦进仓库，等于把版权风险一起收进来，见 `docs/LICENSE-AUDIT.md` 第六节。

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
| 5 | 站外内容形态 | **只给搜索页外链**。详情页挂「相关视频」跳 B 站搜索页；不内嵌、不抓取、不写「官方 / 合作」。加站点改 `frontend/src/lib/externalSearch.ts` |

## 相关文档

- `docs/PLAN.md` —— 施工计划表，每步的上下文、任务、验收标准
- `docs/BASES.md` —— 基底清单、文件级复用映射、上游遗留问题
- `docs/LICENSE-AUDIT.md` —— 许可审查：代码层红线、数据层风险、图片资产
- `docs/DEPLOY.md` —— 部署形态与步骤
