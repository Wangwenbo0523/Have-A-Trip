# Have-A-Trip 前端（景点大全）

景点档案的浏览、检索与推荐界面。**不做地图，不做定位**。

- 栈：React 19 + TypeScript + Vite 8 + react-router-dom 7 + axios
- 基底：MIT 许可的 [zero-to-mastery/travel-guide](https://github.com/zero-to-mastery/travel-guide)，见 `LICENSE` 与 `docs/BASES.md`
- 后端：仓库根目录下的 `backend/`（FastAPI）

## 页面与路由

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | `HomePage` | 推荐位 + 分类入口 + 最新收录 |
| `/attractions` | `AttractionBrowser` | 全部景点：关键字搜索、排序、分页 |
| `/category/:slug` | `CategoryPage` | 按分类浏览（复用 `AttractionBrowser`） |
| `/attraction/:slug` | `AttractionDetail` | 详情、图集、标签、评分、相似景点 |
| `/planner` | `ItineraryPlanner` | 帮我排行程：提交 → 轮询 → 结果，可打印行程单 |
| `/stats` | `StatsPage` | 数据看板：数字全部由 `GET /api/v1/stats` 现算，条形是手写 SVG |
| `/compare` | `ComparePage` | 景点对比：两个下拉各挑一个景点，选择记在 URL 查询串里 |
| `/credits` | `Credits` | 数据来源与许可声明，由 `GET /api/v1/sources` 从库里聚合 |
| 其它 | — | 404 兜底 |

## 起开发环境

前后端分开跑。后端起来之后：

```powershell
cd frontend
npm install
npm run start          # http://127.0.0.1:5173
```

前端默认请求**同源**的 `/api/v1`，`vite.config.js` 里的 `server.proxy` 会把 `/api`
转发到 `http://127.0.0.1:8000`，所以本地不需要配跨域。

前后端分开部署时，用环境变量指到真实地址（见 `.env.example`，复制为 `.env.local`）：

```
VITE_API_BASE=https://api.example.com/api/v1
```

**后端没起来会怎样**：页面不会白屏，而是显示明确的错误态与「重试」按钮，例如
「连不上后端 /api/v1, 请先启动 FastAPI 服务」。

## 命令

| 命令 | 作用 |
|---|---|
| `npm run start` | 开发服务器（Vite dev + HMR） |
| `npm run build` | 生产构建，产物在 `dist/` |
| `npm run preview` | 本地预览构建产物 |
| `npx tsc --noEmit` | 类型检查（构建不跑 tsc，类型问题要单独查） |

## 目录

```
src/
├── api/client.ts        # axios 实例 + 各接口的封装 + describeError/getDeviceId
├── config.ts            # 站点常量（项目名、仓库地址、基底署名）
├── hooks/               # useApi（加载/错误/重试）、useDebouncedValue
├── lib/display.ts      # 景点名按语种排版（name / name_en 的标题与副标题）
├── i18n/                # 中英双语文案表 + LanguageProvider / useI18n（无第三方依赖）
├── types/index.ts       # 与 backend/app/schemas.py 一一对应
├── components/
│   ├── HomePage.tsx     AttractionBrowser.tsx  CategoryPage.tsx
│   ├── AttractionDetail.tsx  AttractionList.tsx  AttractionCard.tsx
│   ├── CategoryCard.tsx  StateMessage.tsx  SearchBox.tsx
│   ├── Header.tsx  Footer.tsx  Credits.tsx
│   ├── StatsPage.tsx  ComparePage.tsx  ItineraryPlanner.tsx
│   ├── ThemeSwitch.tsx  LanguageSwitch.tsx
│   └── utils/Loader.tsx
├── routes/AppRouter.tsx # 路由表
├── styles/              # 各组件样式；全局变量与两套主题的调色板在 index.css 的 :root
└── index.tsx            # 入口（含 AOS 初始化）
```

## 行为埋点

详情页进入时上报一次 `view`，收藏与打分会分别上报 `favorite` / `rate`。
用途只有一个：给推荐系统提供原料。

设备标识是本地生成的随机串（`localStorage` 里的 `have-a-trip.device_id`），
**不是定位信息**，也不含任何位置数据。

## 中英双语

界面文案有**中文（默认）**与**英文**两套，切换按钮在页头右上角：中文界面显示 `EN`，英文界面显示 `中文`。
选择存在 `localStorage["have-a-trip:lang"]`，刷新与换页都保持；`<html lang>` 与页面标题跟着切换。

**只有界面文案**分语种。景点档案（`name` / `summary` / 方案 / 图注 / 来源与许可）与分类名、标签名
是数据库里的**内容**，两种语种下原样显示；后端返回的 `note` / `disclaimer` 同理。
唯一的例外是景点名：英文界面下 `name_en` 有值就用它当标题（见 `src/lib/display.ts`），
没有则回退中文名 —— **库里只填了少数几条英文名**，不替景点编一个。

实现是一张消息表（`src/i18n/messages.ts`）+ 一个 `t()`，**没有引入 i18n 依赖**（本仓库对新增依赖有许可证卡口）。
英文表缺键时回退中文串，`src/i18n/i18n.test.ts` 会校验两张表的键与占位符一一对应。

## 深浅色主题

页头右上角与语种按钮并排，按钮上写的是**目标主题**的名字（深色界面上显示「浅色」）。
默认**深色**，**不嗅探 `prefers-color-scheme`** —— 本站的视觉是围绕深色设计的，跟着系统走会让
同一台机器上的两个人看到两副样子（与语种不嗅探 `navigator.language` 是同一个口径）。
选择存在 `localStorage["have-a-trip:theme"]`。

两套主题**共用同一份组件样式**：浅色只覆盖 `src/index.css` 里 `:root[data-theme="light"]` 的一组变量，
不碰尺寸、间距与布局。所以**新组件只要用变量取色，浅色主题就自动成立**，不要在组件里写死颜色；
确实与主题无关的（等级徽章的金色渐变压在封面上）才允许硬编码。

`index.html` 里有一段内联脚本，在 React 挂载前读一次 `localStorage` 并把 `data-theme` 写到 `<html>` 上 ——
不这么做，选了浅色的用户每次刷新都会先看到一闪的深色底。那是**唯一**一处与 `src/theme` 重复
storage key 的地方，改 key 时两处都要改。

## 打印行程单

`/planner` 排好之后有「打印行程单」。`src/index.css` 的 `@media print` 把调色板整体换成白底黑字
（深色主题直接打印会把整页涂黑），并摘掉页头、页脚、表单与按钮；`styles/itinerary.css` 只管分页 ——
一个景点别被拆到两页，天标题别孤零零留在页尾。

## 契约

前端类型以 `backend/app/schemas.py` 为准，字段口径见 `db/README.md`。
改接口时两边一起改。
├── theme/               # 深浅色主题 + ThemeProvider / useTheme（无第三方依赖）
