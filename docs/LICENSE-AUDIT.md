# 许可证审查

「将来能闭源」是一条**持续维持**的状态，不是一次性动作。本文是审查记录与红线清单。

## 一、代码层：当前状态

用 `scripts/license_gate.py` 扫描（与 CI 同一脚本）：

| 项 | 数量 | 说明 |
|---|---|---|
| 违禁（GPL / AGPL / SSPL / CC-BY-NC） | **0** | 通过 |
| 告警（MPL-2.0） | 13 | `certifi`（Python 证书包）与 `lightningcss` 及其 12 个平台包（Vite 8 的 CSS 压缩器，仅构建期）。MPL 是文件级 copyleft，只要不修改这些包的文件就无义务。保持「只用不改」即可。 |
| 未标注许可 | 4 | `@mapbox/jsonlint-lines-primitives`、`sort-asc`、`sort-object`、`sort-desc` |

那 4 项未标注许可的包来自这条链（已验证）：

```
ol  ->  ol-mapbox-style  ->  @mapbox/mapbox-gl-style-spec  ->  { @mapbox/jsonlint-lines-primitives, sort-object }
                                                                        sort-object  ->  { sort-asc, sort-desc }
```

本项目不需要地图，删掉 `ol` 依赖后整条链连同这 4 个未标注项一起消失。这是「删除地图」的附带收益。

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
| `tuansuwu/china-5a-scenic-areas`（373 个 5A 景区） | CC-BY-SA-4.0 | 署名 + 相同方式共享 | 慎用 |
| `Iter-X/open-poi-datasets` | **MIT** | 保留版权声明 | **可用** |
| `Cathy-wang132/travel-guide-sharing-dataset` | 无 | — | **不可用** |
| `peterpan23/SenTARev-`（景点评论情感） | 无 | — | **不可用** |
| 官方文旅部门公开名录、自行采集 | 视发布方 | 逐条确认 | **推荐** |

### 处理原则

1. **优先自采或 MIT 数据源**。景点名录本质是事实信息，自己整理最干净。
2. 必须使用 ODbL / CC BY-SA 数据时，把该数据**隔离在明确边界内**（独立数据集、独立导入脚本），
   并在 `frontend/src/components/Credits.tsx` 对应的数据来源声明页里逐条署名。
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

## 四、操作清单

- [x] 根许可证存在于 `LICENSE`；两个基底的 LICENSE 随源码保留（`frontend/LICENSE` = MIT）
- [x] **根许可证已定为 MIT**（2026-09-25 由 Unlicense 换入），保住版权与再许可空间。见下节
- [x] 许可证卡口脚本 + CI 工作流
- [x] 基底钉版记录（`scripts/bases.lock.json`）含 commit 与许可
- [x] 两个基底的 LICENSE 随源码保留（`frontend/LICENSE`）
- [ ] **贡献者启用 DCO 签核**（见 `CONTRIBUTING.md`）——闭源保险的核心，别拖
- [ ] 上线前完成数据层逐条复核
- [ ] 定期跑 `python scripts/license_gate.py --strict`

> 以上是工程与合规判断，不构成法律意见。真要闭源时建议请律师过一遍。
