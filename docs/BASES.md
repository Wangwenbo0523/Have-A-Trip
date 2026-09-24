# 两个基底的落位清单

本文是「景点大全 App」的两个开源基底的**唯一权威记录**。改基底前先看这里。

| | 基底 A：前端 | 基底 B：推荐引擎 |
|---|---|---|
| 上游 | `zero-to-mastery/travel-guide` | `RUCAIBox/RecBole` |
| 版本 | commit `a2c9f2d1` | v1.2.1 / commit `7b02be5e` |
| 许可证 | **MIT** | **MIT** |
| 我们怎么用 | **Vendor 进 `frontend/`，会改它** | **当依赖库，不改它源码** |
| 落地位置 | `frontend/` | `recsys/`（调用层）+ pip 依赖 |
| 技术栈 | React 19 + TS + Vite 8 + react-router 7 | PyTorch 推荐框架，35+ 模型 |

两个都是 MIT，所以你保有闭源的退路。**任何 GPL/AGPL 代码一律不得进入本仓库**（见 `LICENSE-AUDIT.md`）。

---

## 基底 A：travel-guide（前端）

已 vendor 到 `frontend/`，41 个文件 / 8.81 MB，嵌套 `.git` 已摘除。只检出了 `src/`、`public/` 和根配置文件，`dist/` 是构建产物未检出。

### 它原本是什么

一个「目的地 → 活动」的浏览型站点：`CountryCard` 列国家，`Detail` 看详情，`MapView` 在地图上打点，`Credits` 声明数据来源。形态和我们的「景点大全」几乎一致，所以骨架可直接用。

### 文件级复用映射

**直接保留**

| 文件 | 用途 |
|---|---|
| `src/components/SearchBox.tsx` | 景点搜索输入框 |
| `src/components/utils/Loader.tsx` | 加载态 |
| `src/components/Header.tsx`、`Footer.tsx` | 导航与页脚 |
| `src/routes/AppRouter.tsx` | 路由骨架（改路由表） |
| `src/index.tsx`、`index.html`、`vite.config.js`、`tsconfig.json` | 构建骨架不动 |

**改造（主要工作量）**

| 原文件 | 改成 | 说明 |
|---|---|---|
| `src/components/RegionList.tsx` + `RegionCard.tsx` | `AttractionList` + `AttractionCard` | 国家列表 → 景点卡片流，这是首页主体 |
| `src/components/CountryDetails/Detail.tsx` | `AttractionDetail` | 景点详情：简介、图集、标签、评分、推荐位 |
| `src/components/Region.tsx` | `CategoryPage` | 国家聚合 → 分类/省份聚合 |
| `src/components/CountryCard.tsx` | `CategoryCard` | 分类入口卡 |
| `src/types/index.ts` | 重写 | `Country` 类型 → `Attraction` 类型（对齐 `db/schema.sql`） |
| `src/components/Credits.tsx` | **改为数据来源与许可声明页** | 必须做：用了 OSM(ODbL)、CC BY-SA 数据就得署名 |
| `src/App.tsx`、`App.test.js` | 改造 | 应用外壳与测试 |

**删除**

| 文件/依赖 | 原因 |
|---|---|
| `src/components/MapView/MapView.tsx` + `.css` | 明确不需要地图 |
| `package.json` 里的 `ol`（OpenLayers 6） | 只有 MapView 用。删掉它连带移除 `ol-mapbox-style` -> `@mapbox/mapbox-gl-style-spec` -> `@mapbox/jsonlint-lines-primitives` / `sort-object` -> `sort-asc`/`sort-desc` 整条链（此链已验证），许可证扫描里的 4 个「未标注许可」项一并消失 |
| `package.json` 里的 `jquery`（4.0.0） | CRA 时代遗留，无引用 |
| `src/changed/Globe.svg`（206 KB）、`src/Google_Earth_Logo.svg` | 地图/地球相关素材 |
| `src/registerServiceWorker.js` | CRA 遗留；要做 PWA 再单独加 |

**替换**

| 文件 | 问题 |
|---|---|
| `src/hero-pic.jpg` | **7.9 MB**，必须先压缩，否则首屏必崩 |
| `src/img/BaganMyanmar.jpg`（675 KB） | 同上，转 WebP |

保留的依赖：`react`、`react-dom`、`react-router-dom`、`axios`（用来打我们的 FastAPI）、`react-spinners`、`aos`、`tachyons`。

---

## 基底 B：RecBole（推荐引擎）

**不 vendor 源码**——它是 pip 依赖，复制进仓库只会造成后续难以升级。

```
pip install recbole==1.2.1
```

### 硬约束：必须独立 Python 3.11 环境

我从它的 `requirements.txt` 和 `setup.py` 挖出来的实际问题：

| 证据 | 影响 |
|---|---|
| `ray>=1.13.0, <=2.6.3` | Ray 2.6.3 不支持 Python 3.12+，把上限锁死在 3.11 |
| `hyperopt==0.2.5` | 2020 年的老包，不支持新版 Python |
| `colorlog>=4.7.2`、`colorama>=0.4.4` | 实际安装会解析到旧版本 |
| `setup.py` 里**没有声明 `python_requires`** | pip 会照装不误，然后在运行时报错——比装不上更坑 |
| `numpy>=1.17.2` 无上限，但代码面向 numpy 1.x | 与 numpy 2.x 有风险 |

而我们的 API 栈（FastAPI）跑在 **Python 3.13 + numpy 2.5**。**两者不可能共存于同一环境。**

### 因此架构上这样分工

```
前端 React (frontend/, 来自 travel-guide)
        |  HTTP / axios
        v
API 服务  FastAPI  Python 3.13        <-- 绝不 import recbole
        |           读取推荐结果表；冷启动走内容相似度兜底
        v
PostgreSQL   景点档案 / 用户行为日志 / 推荐结果表
        ^
        |  离线批量写入
离线训练任务  Python 3.11 独立环境  +  RecBole 1.2.1
```

**RecBole 的唯一职责**：拿 `user_id, attraction_id, 行为` 交互数据训练，产出 TopN 写回推荐结果表。API 只读结果表。这样依赖冲突被物理隔离，且训练失败不影响线上服务。

### `recsys/` 目录

| 文件 | 作用 |
|---|---|
| `recsys/requirements.txt` | 钉死 RecBole 版本的独立环境依赖 |
| `recsys/README.md` | 环境搭建与运行步骤 |
| `recsys/config/recbole.yaml` | 训练配置（数据集、模型、指标） |

---

## 以后要升级基底怎么办

1. 改 `scripts/bases.lock.json` 里的 commit / 版本。
2. 前端：`scripts/fetch-bases.ps1` 重新拉取，用 `git diff` 对比上游改动，挑需要的合进来（不要整目录覆盖，`frontend/` 已经被我们改过）。
3. 推荐引擎：只改 pip 版本号，跑一次离线训练验证再上线。
4. 每次动基底都要过 `LICENSE-AUDIT.md` 的检查清单。
