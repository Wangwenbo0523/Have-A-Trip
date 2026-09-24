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

已 vendor 到 `frontend/`，**38 个文件 / 1.01 MB**，嵌套 `.git` 已摘除。只检出了 `src/`、`public/` 和根配置文件，`dist/` 是构建产物未检出。

### 它原本是什么

一个「目的地 → 活动」的浏览型站点：`CountryCard` 列国家，`Detail` 看详情，`MapView` 在地图上打点，`Credits` 声明数据来源。形态和我们的「景点大全」几乎一致，所以骨架可直接用。

### 本地已做的改造（相对上游 commit `a2c9f2d1`）

上游那个 commit 拿到手是**跑不起来**的。下面这些是落位时已经改掉的，升级基底时别把它们冲掉。

| 改动 | 原因 |
|---|---|
| `package.json`：`@testing-library/react` 13.4.0 → 16.3.3、`@testing-library/user-event` → 14.6.7、`react-spinners` 0.13.8 → 0.17.1 | 前两个声明 `react@^18`，而项目用 `react@19`，`npm ci` 直接 `ERESOLVE` 失败 |
| `vite.config.js`：`base` 由 `/travel-guide/` 改为 `/` | 上游是部署在 GitHub Pages 子路径，本项目独立部署 |
| `vite.config.js`：新增 `css.lightningcss.errorRecovery: true` | `tachyons@4.12`（2017 年的库）含 IE 时代的 `*zoom` hack，Vite 8 默认的 LightningCSS 压缩器视其为非法语法，直接让构建失败。剥离该声明无副作用，现代浏览器本来就忽略它 |
| `index.html`：删掉指向 `cdn.rawgit.com` 的 AOS 样式链接 | `rawgit.com` 2019 年已关停，是死链。改为从 npm 包引入（`src/index.tsx` 里 `import 'aos/dist/aos.css'`） |
| 路由前缀 `/travel-guide/*` → `/*` | 与 `base: '/'` 保持一致。涉及 `AppRouter.tsx`、`Header.tsx`、`Footer.tsx`、`Region.tsx`、`RegionCard.tsx`、`Detail.tsx` |
| `src/App.tsx`：删掉 `navigator.geolocation.getCurrentPosition(...)` | 它会让首屏加载时弹出定位授权请求，与「不需要地图跟踪」直接冲突，且原调用签名本身是错的 |
| 删除 `src/hero-pic.jpg`、`src/Google_Earth_Logo.svg`、`src/changed/Globe.svg` | 死资源，`src/` 内零引用（详见下方说明） |
| `package.json`：删 `jquery` | CRA 时代遗留，`src/` 内零引用 |
| 项目元信息 `name` / `description` / `repository` / `author` / `homepage` / `bugs` | 原本仍是上游的 `travel-guide-app` / `zero-to-mastery` |

> **纠正一处早先的误判**：`src/hero-pic.jpg`（7.75 MB）此前被记成「首屏必崩，必须先压缩」，
> 实际上它**没有被任何代码引用**，属于死资源，已直接删除。
> 真正进入产物的图片是 `src/img/BaganMyanmar.jpg`（675 KB，构建后原样输出为 `dist/assets/BaganMyanmar-*.jpg`）。
> **该图已于 S8 删除**（2026-09-25）：它的图片许可无从查证，MIT 覆盖的是仓库作者的贡献，
> 不等于贡献者有权授权别人的摄影作品。页头背景改用纯 CSS 渐变，顺带省掉首屏 675 KB。
> 详见 `docs/LICENSE-AUDIT.md` 第五节「图片资产」。

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
| `src/App.tsx` | 改造 | 应用外壳；不再打 `restcountries.com`，改取本项目 `/api/v1/categories` |
| `src/App.test.js` | 改写成 `src/App.test.tsx` | CRA 时代的裸渲染冒烟测试；S8 换成 Vitest + Testing Library，见下 |

**删除**

| 文件/依赖 | 原因 | 状态 |
|---|---|---|
| `src/components/MapView/MapView.tsx` + `.css` | 明确不需要地图 | **已删 (S3)** |
| `package.json` 里的 `ol`（OpenLayers 6） | 只有 MapView 用。删掉它连带移除 `ol-mapbox-style` -> `@mapbox/mapbox-gl-style-spec` -> `@mapbox/jsonlint-lines-primitives` / `sort-object` -> `sort-asc`/`sort-desc` 整条链（此链已验证），许可证扫描里的 4 个「未标注许可」项一并消失 | **已删 (S3)** |
| `package.json` 里的 `jquery`（4.0.0） | CRA 时代遗留，无引用 | **已删** |
| `src/hero-pic.jpg`（7.75 MB）、`src/changed/Globe.svg`（200 KB）、`src/Google_Earth_Logo.svg` | 死资源，零引用 | **已删** |
| `src/registerServiceWorker.js` | CRA 遗留；要做 PWA 再单独加 | **已删 (S3)** |

**替换**

| 文件 | 问题 | 状态 |
|---|---|---|
| ~~`src/img/BaganMyanmar.jpg`（675 KB）~~ | 许可来源无从查证 | **已删 (S8)**，页头改 CSS 渐变 |

保留的依赖：`react`、`react-dom`、`react-router-dom`、`axios`（用来打我们的 FastAPI）、`react-spinners`、`aos`、`tachyons`。

**S8 工程化收尾（2026-09-25）**

| 改动 | 说明 |
|---|---|
| 页面头图 | 删除来源不明的 `BaganMyanmar.jpg`，`Header.css` 改用纯 CSS 渐变 |
| 测试框架 | Vitest 5 + jsdom + Testing Library，配置在独立的 `vitest.config.js`（合并 `vite.config.js`）；`npm test` 从空脚本变成 `vitest run`，21 个用例 |
| `App.test.js` → `App.test.tsx` | 顺带覆盖「后端全挂时不白屏」 |
| `vite.config.js` | 删掉 `esbuild` 与 `optimizeDeps.esbuildOptions` 两段死配置 —— 它们是为上游那些写 JSX 的 `.js` 文件准备的，S4 之后 `src/` 里已无 `.js`；留着只会让 Vite 8 每次构建打废弃告警 |
| `package.json` | 补 `typecheck` / `test` / `test:watch`；删掉失效的 `predeploy` / `deploy`（`gh-pages` 从来没装）与 CRA 时代的 `eslintConfig`（`react-app` 那套插件也不存在） |
| `public/manifest.json` | 名字从 `Create React App Sample` 改成本项目 |
| CI | 新增 `frontend-build`（`npm ci` → typecheck → test → build → 断言产物 → 守线 grep）与 `dco`（逐个 commit 校验 sign-off） |

**S4 实际落地（2026-09-25）**

上面那张「原文件 → 改成」的表已全部执行完。与计划的差异：

| 项 | 计划 | 实际 |
|---|---|---|
| 页面拆分 | `AttractionList` / `CategoryPage` / `AttractionDetail` | 多拆了一个 `AttractionBrowser`（搜索 + 排序 + 分页的列表主体），`/attractions` 与 `/category/:slug` 共用，避免两处重复 |
| 路由 | 首页 / 分类 / 详情 / credits | 增加 `/attractions`（全部景点）与 `*`（404 兜底） |
| `Footer.tsx` | 保留 | 重写：上游的 Facebook/Instagram/Twitter 链指向的是原作者账号，不属于本项目；改为仓库、致谢页与基底署名 |
| `Header.tsx` | 保留 | 重写：去掉 giphy 内嵌 iframe；导航改为按 `/api/v1/categories` 动态生成（最多 6 个） |
| `tachyons` | 保留 | **仍保留**（`Credits.tsx` 还在用）。S5 重做致谢页时可以一并去掉，顺带能关掉 `vite.config.js` 里的 `lightningcss.errorRecovery` |
| `App.test.js` | 见待决 #2 | 未动 |

同时修掉三个上游遗留问题（与本次改动同一批文件，故一并处理）：

- `index.html` 里 `cdn.rawgit.com` 的 AOS `<script>` 是死链，`AOS.init()` 从未运行过；而 `aos.css` 会给 `[data-aos]` 元素初始 `opacity: 0` —— 结果**页头标题与页脚链接一直不可见**。改为在 `src/index.tsx` 里 `import AOS from "aos"` 并初始化。
- `index.css` 原本把 `body` 设成 `display: grid` + `padding-top: 10%`，还带一条全局 `img { height: 17em; width: 17em }`（会把景点配图压成正方形），并外链了第三方博客 CDN 的背景图。已重写为本地渐变 + 正常文档流。
- 依赖清理：删掉 `@types/react-router-dom@5`（react-router-dom 7 自带类型，装 v5 的类型包只会误导）。

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
| `recsys/requirements.txt` | 钉死 RecBole 版本的独立环境依赖（含 3 个必须钉的版本与原因） |
| `recsys/README.md` | 环境搭建与运行步骤 |
| `recsys/config/recbole.yaml` | 训练配置（数据集、模型、指标） |
| `recsys/common.py` | 三条脚本的共用部分：连库、路径、批次号、「行为 → 隐式强度」口径 |
| `recsys/export_interactions.py` | 从业务库导出 RecBole 原子文件（`.inter` / `.item` / `stats.json`） |
| `recsys/run_recbole.py` | 训练 BPR 并产出 Top-K 预测与 `meta.json` |
| `recsys/write_back.py` | 预测写回 `rec_result`，整批一个事务 |

---

## 以后要升级基底怎么办

1. 改 `scripts/bases.lock.json` 里的 commit / 版本。
2. 前端：`scripts/fetch-bases.ps1` 重新拉取，用 `git diff` 对比上游改动，挑需要的合进来（不要整目录覆盖，`frontend/` 已经被我们改过）。
3. 推荐引擎：只改 pip 版本号，跑一次离线训练验证再上线。
4. 每次动基底都要过 `LICENSE-AUDIT.md` 的检查清单。