# 许可证审查

「将来能闭源」是一条**持续维持**的状态，不是一次性动作。本文是审查记录与红线清单。

## 一、代码层：当前状态

用 `scripts/license_gate.py` 扫描（与 CI 同一脚本）：

| 项 | 数量 | 说明 |
|---|---|---|
| 违禁（GPL / AGPL / SSPL / CC-BY-NC） | **0** | 通过 |
| 告警（弱 copyleft） | 15 | 13 项 MPL-2.0：`certifi`（Python 证书包）与 `lightningcss` 及其 12 个平台包（Vite 8 的 CSS 压缩器，仅构建期）。2 项 LGPL：`psycopg` / `psycopg-binary`（数据库驱动）。MPL 是文件级 copyleft，LGPL 是动态链接许可，两者只要**只用不改**就无义务。 |
| 未标注许可 | **0** | 原先那 4 项随 `ol` 依赖一并消失，见下 |

地图库 `ol` 已在 S3 删除（本项目不做地图与定位），它带进来的这条链随之消失：

```
ol  ->  ol-mapbox-style  ->  @mapbox/mapbox-gl-style-spec  ->  { @mapbox/jsonlint-lines-primitives, sort-object }
                                                                        sort-object  ->  { sort-asc, sort-desc }
```

`scripts/license_gate.py` 里的「已登记未标注许可」白名单因此清空，并新增了 `BANNED_NPM_PACKAGES`：
一旦 `ol` / `leaflet` / `mapbox-gl` / `ol-mapbox-style` 被加回 `frontend/package.json`，卡口直接失败。
把「删掉地图」的收益固化成了自动检查，而不是靠人记得。

## 二、代码层：红线

**禁止引入**（PR 一律拒绝）：

| 许可 | 为什么 |
|---|---|
| AGPL-3.0 | 最危险。即使只提供服务、不分发二进制，也触发向用户提供源码的义务 |
| GPL-2.0 / GPL-3.0 | 衍生作品必须同样开源 |
| SSPL / BUSL | 非 OSI 认可，商用受限 |
| CC-BY-NC | 禁止商用 |
| **无 LICENSE** | 默认保留所有权利。严格说连复制都未获授权，更不可能闭源 |

**需人工确认**：LGPL、MPL、EPL——动态/未修改使用通常可行，但要在 PR 里说明。

### 已明确排除的候选（勿引入）

| 项目 | 许可 | 备注 |
|---|---|---|
| `liketrek/TREK` | AGPL-3.0 | 功能最全的自托管行程规划，14.3k★，可惜 |
| `yyzwz/s023` | GPL-3.0 | 中文景点推荐系统里功能最全的（景点/行程/美食推荐 + 协同过滤） |
| `seanmorley15/AdventureLog` | GPL-3.0 | 3.8k★，自托管旅行记录 |
| `osmandapp/OsmAnd` | GPLv3 + 美术 CC-BY-NC-ND | 双重限制 |
| `1sdv/TripStar` | GPL-2.0 | 2.3k★，AI 文旅智能体，架构值得读，代码不能用 |
| `nanbouking/WeTravel` | 无 | 景区门户小程序，功能设计可参考 |
| `dingyuanyind/WeCulture` | 无 | 文旅小程序 |
| `dwsera/Tour-AI` | 无 | Next.js AI 旅游规划 |
| `coder-zrl/trip` | 无 | 知识图谱旅游推荐 |
| `1937983507/ai-tourism` | 无 | SpringBoot + LangChain4j |
| `small-bears/*` 系列 | 无 | 毕设类智慧景区平台 |

> 「无 LICENSE」的中文仓库大量存在，且常带「加 QQ 获取源码」字样——这类项目的代码来源与版权归属往往不清晰，
> 即使它自己标了许可证，声明也未必站得住。**只读思路，不抄代码。**

## 三、数据层：真正容易忽略的地方

代码干净 ≠ 数据干净。相同方式共享（share-alike）义务会**顺着数据传染到你的数据库**。

| 数据源 | 许可 | 义务 | 结论 |
|---|---|---|---|
| OpenStreetMap（`tourism=attraction`） | ODbL 1.0 | 署名 + **数据库层相同方式共享** | 慎用。闭源前必须评估 |
| Wikipedia / Wikivoyage 文本 | CC BY-SA 4.0 | 署名 + 相同方式共享 | 慎用 |
| `tuansuwu/china-5a-scenic-areas`（373 个 5A 景区） | CC-BY-SA-4.0 | 署名 + 相同方式共享 | **不用**。v2.0 评估过：这一份正好覆盖我们要的等级字段，但 share-alike 会顺着数据传染，与「将来可闭源」冲突，宁可把 `a_level` 留空也不引入 |
| `Iter-X/open-poi-datasets` | **MIT** | 保留版权声明 | **可用** |
| `Cathy-wang132/travel-guide-sharing-dataset` | 无 | — | **不可用** |
| `peterpan23/SenTARev-`（景点评论情感） | 无 | — | **不可用** |
| 官方文旅部门公开名录、自行采集 | 视发布方 | 逐条确认 | **推荐** |

### 本项目当前的数据状况（2026-09-25，S7 落数据）

| 项 | 现状 |
|---|---|
| 种子数据 | 90 个景点（中国境内 50 + 境外 40，覆盖六大洲 30 个国家）、31 个标签、362 条标签关联，全部自采 |
| 旅游方案 | 90 个方案、307 条步骤，同样是自采的行程建议（不是官方或旅行社线路） |
| 等级字段 | `a_level` 40 条、`heritage` 59 条，**逐条查证后才填**，查不到就留空 |
| `source` | `Have-A-Trip 自采（公开事实信息）`（90 / 90 条） |
| `license` | `MIT`（90 / 90 条） |
| 第三方数据集 | **一个都没有** —— 本节表格里那些源，至今一个没用；v2.0 还主动放弃了一份 CC BY-SA 的 5A 名录（见上表） |
| 图片 | `attraction_image` 90 行，全部是 `scripts/make_attraction_covers.py` 自绘的 SVG |
| share-alike | **无**。ODbL / CC BY-SA 义务不沾这个库，也没有可传染的衍生物 |

聚合口径与查询语句在 `db/README.md` 的「数据来源清单」一节。声明页 `/credits` 已经上线，
它读 `GET /api/v1/sources`，而后端每次都是从 `attraction` / `attraction_image` 现算的 ——
所以将来引入新来源时，页面会自己跟着变，不靠谁记得改前端。**引入新来源时仍要先回来更新本节。**

另一道闸在 `backend/app/api/sources.py`：许可一旦被判定为 share-alike（ODbL / CC BY-SA），
就必须在那个文件的 `SOURCE_MODIFICATIONS` 里登记「是否修改过」，否则接口返回 `unregistered`、
声明页顶部弹出红色告警。**没登记就上线不了，这是设计如此。**

### 处理原则

1. **优先自采或 MIT 数据源**。景点名录本质是事实信息，自己整理最干净。
2. 必须使用 ODbL / CC BY-SA 数据时，把该数据**隔离在明确边界内**（独立数据集、独立导入脚本），
   在 `/credits` 声明页（数据来自 `GET /api/v1/sources`）里逐条署名，并在
   `backend/app/api/sources.py` 的 `SOURCE_MODIFICATIONS` 里登记「是否修改过」—— 不登记页面就标红。
3. 数据层与代码层解耦——`data/`、`dataset/` 已在 `.gitignore` 中，第三方数据不进代码仓库。
4. 闭源前逐条复核本表，而不是假设它没变。

## 三·五、根许可证：已由 Unlicense 改为 MIT

建仓时 GitHub 默认选中的是 **Unlicense**，它把版权奉献给公有领域，与「将来可能闭源」直接冲突。
已于 2026-09-25 换成 **MIT**。两种许可对「将来闭源」的影响差别：

| | MIT（当前） | Unlicense（原状） |
|---|---|---|
| 版权归属 | 作者保留版权，授予宽泛许可 | **永久放弃版权** |
| 将来闭源 | 可以：新版本可换许可 | 勉强可以，但**无法对已发布版本行使任何权利** |
| 再许可 / 双许可 | 可以 | 不能 |
| 署名要求 | 要求保留版权声明 | 不要求 |

另外还有一处不一致：`frontend/` 里 vendor 了上游要求保留署名的 MIT 代码，
若整体宣称公有领域，等于「对外放弃权利、对内却负有署名义务」。改成 MIT 后两者自洽。

根 `LICENSE` 的署名为 `Copyright (c) 2026 Wangwenbo0523`。
vendor 进来的 `frontend/LICENSE`（`Copyright (c) 2019 Zero To Mastery`）原样保留——MIT 要求不得删除。

## 五、图片资产

图片和代码一样是资产，而且更容易漏——代码有 lockfile 可以扫，图片只能靠人记。

| 资产 | 来源 | 许可 | 处置 |
|---|---|---|---|
| `frontend/src/img/BaganMyanmar.jpg`（675 KB，页头背景） | 上游基底 `zero-to-mastery/travel-guide` 里的实景照片 | **无从查证**。MIT 覆盖的是仓库作者的贡献，不等于贡献者有权授权别人的摄影作品 | **已删除**（2026-09-25，S8）。页头背景改用纯 CSS 渐变，顺带省掉首屏 675 KB |
| `frontend/public/favicon.ico` | **自绘**，无第三方素材 | MIT（与仓库同许可） | **已换掉**（2026-09-25）。上游的 `earth.ico`（225 KB）与 `favicon.ico` 出处无从查证，已删除；现由 `scripts/make_favicon.py` 用标准库程序化生成（7 档尺寸、8.5 KB），改常量重跑即可复现 |
| `frontend/src/logo.svg` | 上游基底的 React 标志 | 零引用死资源 | 已删除（2026-09-25，S4） |
| 景点配图（90 张，`frontend/public/images/covers/*.svg`） | **自绘**，由 `scripts/make_attraction_covers.py` 程序化生成 | MIT（与仓库同许可） | 原计划用 CC0 / 公有领域图库（2026-09-25）：**Wikimedia Commons 与 Openverse 在本机网络下不可达**（连接超时），Unsplash / Pixabay 用的是各自的专有许可而非 CC0，且对中国具体景点的覆盖很薄。于是改为自绘——出处就是仓库里的脚本。每条仍走 `attraction_image.credit` / `.license`（NOT NULL），声明页会聚合出来 |

### 原则

1. **来源查不到出处的图片，一律不进仓库**。一张图的风险比一行依赖代码更隐蔽——没有工具会替你扫。
2. 景点配图优先自己拍或自绘，其次才是明确标注 CC0 / 公有领域的图库，并在 `attraction_image.credit` 里写明作者与许可。
   **不要**为了「有图」而放进许可不明或带相同方式共享义务的照片——前者是法律风险，后者给将来闭源添一道手续。
3. 图片的署名与许可**是数据库字段**，不是文档里的口头约定。`attraction_image.credit` / `.license` 都是 `NOT NULL`，
   声明页（`Credits.tsx`）由它们聚合生成——想漏也漏不掉。
4. `public/` 下的图标是**自绘**的（`scripts/make_favicon.py`）。换图形要改那个脚本再重跑，
   不要手工往 `public/` 里塞文件——脚本在，出处就查得到。`license-gate` 工作流会跑 `--check`，图标与脚本对不上就直接红。

## 六、站外内容（第三方平台链接）

详情页「相关视频」会跳 B 站搜索页。这是**链接**不是内容再分发，但口径仍要写死：

| 做法 | 为什么 |
|---|---|
| 只给**搜索页**地址，不给具体视频 | 具体视频会死链，而且等于替某一条内容背书；搜索页永远有效 |
| 不内嵌 iframe / 播放器 | 会把第三方脚本与 Cookie 引进来，等于在自己的页面上跑别人的代码 |
| 不用平台 logo 或商标图形 | 商标使用要有授权；纯文字站点名属于正常指称 |
| 不写「官方」「合作」字样 | 没有合作关系，写了就是误导 |
| 不抓取、不下载、不转载 | 视频版权归上传者；抓回来的素材进仓库，闭源时风险一并收进来 |
| 不接开放平台 API 拉视频列表 | 要资质与商用条款，且把「谁的接口」写进了依赖链 |

实现落在 `frontend/src/lib/externalSearch.ts`（站点数组）与
`frontend/src/components/ExternalVideoSearch.tsx`。**加站点前先确认那条搜索地址免登录可打开**，
再往数组里加一条 —— 组件本身与站点无关。

## 四、操作清单

- [x] 根许可证存在于 `LICENSE`；两个基底的 LICENSE 随源码保留（`frontend/LICENSE` = MIT）
- [x] **根许可证已定为 MIT**（2026-09-25 由 Unlicense 换入），保住版权与再许可空间。见下节
- [x] 许可证卡口脚本 + CI 工作流
- [x] 基底钉版记录（`scripts/bases.lock.json`）含 commit 与许可
- [x] 两个基底的 LICENSE 随源码保留（`frontend/LICENSE`）
- [x] **贡献者 DCO 签核已启用**：`scripts/check_dco.py` + `.github/workflows/dco.yml` 逐个 commit 校验（2026-09-25）
- [x] 图片资产已单独立节审查（见第五节），来源不明的那张已删除
- [x] `public/` 下的占位图标已换成自绘（2026-09-25）：`scripts/make_favicon.py` 生成，上游 `earth.ico` 已删除
- [x] 景点配图已落（2026-09-25）：90 张自绘封面，由 `scripts/make_attraction_covers.py` 生成；声明页显示「Have-A-Trip 自绘 · MIT · 90 张」
- [x] 境外 40 个景点同样自采（v2.0），没有引入任何第三方数据集；评估过一份 CC BY-SA 4.0 的 5A 名录，因 share-alike 与闭源路线冲突而放弃
- [x] 一期数据层已定案（2026-09-25，S7）：50 条全部自采、`license` 为 MIT，无第三方数据集，无图片
- [ ] 接入新数据源或图片时，回来更新第三、第五节并逐条复核
- [x] 站外内容口径已单独立节（见第六节）：详情页只给 B 站搜索页外链，不内嵌、不抓取、不转载（2026-09-25）
- [ ] 定期跑 `python scripts/license_gate.py --strict`

> 以上是工程与合规判断，不构成法律意见。真要闭源时建议请律师过一遍。
