# attraction-atlas · 景点大全

一个以「景点档案 + 推荐」为核心的旅游应用。**不做地图跟踪**——只做景点介绍与推荐。

## 为什么这样选基底

目标是「现在开源、将来可能闭源」。这条约束直接排除了所有 GPL/AGPL 项目（一旦引入就永久无法闭源），
所以两个基底都选了 MIT：

| | 干什么 | 在哪 |
|---|---|---|
| [travel-guide](https://github.com/zero-to-mastery/travel-guide) | 前端基底（已 vendor，会改） | `frontend/` |
| [RecBole](https://github.com/RUCAIBox/RecBole) | 推荐引擎（当依赖，不改） | `recsys/` 调用层 |

完整清单、文件级复用映射、以及**为什么 RecBole 必须跑在独立 Python 3.11 环境**，见 `docs/BASES.md`。

## 架构

```
前端 React (frontend/, 来自 travel-guide)
      |  HTTP / axios
      v
API 服务  FastAPI  Python 3.13     <-- 不 import recbole，只读推荐结果表
      |            冷启动走内容相似度兜底
      v
PostgreSQL   景点档案 / 用户行为日志 / 推荐结果表
      ^
      |  离线批量写入
离线训练任务  Python 3.11 独立环境 + RecBole 1.2.1
```

推荐引擎与 API 环境物理隔离：RecBole 的依赖（`ray<=2.6.3`、`hyperopt==0.2.5`）会把 Python 上限锁在 3.11，
和 API 的 3.13 不可能共存；隔离开还带来一个好处——训练挂了不影响线上服务。

## 目录

| 路径 | 说明 |
|---|---|
| `frontend/` | 前端基底（MIT，来自 travel-guide，已摘除嵌套 .git） |
| `recsys/` | RecBole 调用层：依赖钉版、训练配置 |
| `db/` | 景点实体表设计 |
| `scripts/` | 基底钉版记录、重拉脚本、**许可证卡口** |
| `docs/` | **`PLAN.md` 施工计划表**、`BASES.md` 基底清单、`LICENSE-AUDIT.md` 许可审查 |

## 许可证纪律（重要）

「将来能闭源」靠纪律维持，不是靠运气：

```bash
python scripts/license_gate.py --strict
```

检出 GPL/AGPL/SSPL/CC-BY-NC 即失败，CI 也跑同一个脚本（`.github/workflows/license-gate.yml`）。
当前状态：0 违禁，13 项 MPL-2.0 告警（`certifi`、`lightningcss`，均为未修改使用的传递依赖，可接受）。

另外两件事必须从第一天做起，否则将来闭源要回头求人：

1. **贡献者签 DCO**（见 `CONTRIBUTING.md`）——没有版权集中，闭源需征得每个贡献者同意。
2. **数据层许可单独审**——OSM 是 ODbL、CC BY-SA 有相同方式共享义务，代码干净不代表数据干净。见 `docs/LICENSE-AUDIT.md`。

> 根目录 `LICENSE` 为 **MIT**（2026-09-25 由建仓时默认的 Unlicense 换入——Unlicense 会把版权永久奉献给公有领域，与「将来可能闭源」直接冲突）。
> 两个基底各自为 MIT，`frontend/LICENSE` 已随源码保留——MIT 要求保留该版权声明，不能删除。已发布的旧版本仍受当时许可约束，这不影响后续版本。
> 以上是工程判断，不构成法律意见。

## 起步

```bash
# 前端
cd frontend && npm install && npm run dev

# 许可证卡口
python scripts/license_gate.py

# 重拉上游基底做对比（不会覆盖 frontend/）
powershell -File scripts/fetch-bases.ps1
```

## 待办

施工顺序、依赖关系与每步的验收标准见 **`docs/PLAN.md`（施工计划表）**。摘要：

- [ ] `db/schema.sql`：景点档案、分类、标签、行为日志、推荐结果
- [ ] `backend/`：FastAPI 服务（景点列表/详情/搜索 + 推荐接口 + 内容相似度冷启动）
- [ ] 前端改造：按 `docs/BASES.md` 的映射表把 Country 模型换成 Attraction，删除 MapView 与 `ol`
- [ ] `recsys/`：交互数据导出 → RecBole 训练 → 结果回写