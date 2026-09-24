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
| `/credits` | `Credits` | 数据来源与致谢（S5 会重做） |
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
├── types/index.ts       # 与 backend/app/schemas.py 一一对应
├── components/
│   ├── HomePage.tsx     AttractionBrowser.tsx  CategoryPage.tsx
│   ├── AttractionDetail.tsx  AttractionList.tsx  AttractionCard.tsx
│   ├── CategoryCard.tsx  StateMessage.tsx  SearchBox.tsx
│   ├── Header.tsx  Footer.tsx  Credits.tsx
│   └── utils/Loader.tsx
├── routes/AppRouter.tsx # 路由表
├── styles/              # 各组件样式；全局变量在 index.css 的 :root
└── index.tsx            # 入口（含 AOS 初始化）
```

## 行为埋点

详情页进入时上报一次 `view`，收藏与打分会分别上报 `favorite` / `rate`。
用途只有一个：给推荐系统提供原料。

设备标识是本地生成的随机串（`localStorage` 里的 `have-a-trip.device_id`），
**不是定位信息**，也不含任何位置数据。

## 契约

前端类型以 `backend/app/schemas.py` 为准，字段口径见 `db/README.md`。
改接口时两边一起改。
