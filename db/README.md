# db · 景点档案数据库

**目标库：PostgreSQL 14 及以上。** `db/schema.sql` 是权威定义，`backend/` 的 SQLAlchemy 模型与之对应。

## 文件

| 文件 | 说明 |
|---|---|
| `schema.sql` | 建表 DDL（幂等，可重复执行） |
| `seed/seed.sql` | 种子数据：7 个分类、8 个标签、3 个景点（幂等） |

## 执行

```bash
createdb attraction_atlas
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/schema.sql
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/seed.sql
```

两个文件都写成幂等的，重跑不会报错也不会重复插数据：

```bash
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/schema.sql   # 再跑一次
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/seed.sql
```

验证：

```bash
psql -d attraction_atlas -c "select count(*) from attraction;"                  # 3
psql -d attraction_atlas -c "select a.name, c.name from attraction a join category c on c.id = a.category_id;"
psql -d attraction_atlas -c "select * from schema_version;"
```

## 表

| 表 | 作用 |
|---|---|
| `schema_version` | 迁移记录 |
| `category` | 分类，支持 `parent_id` 二级 |
| `tag` | 自由标签 |
| `attraction` | 景点档案主表 |
| `attraction_tag` | 景点-标签多对多 |
| `attraction_image` | 图集，每条带 `credit` 与 `license` |
| `app_user` | 用户（一期只有匿名 `device_id`） |
| `behavior_log` | 行为日志，推荐原料 |
| `rec_result` | 推荐结果，**API 只读这一张** |

另有视图 `v_latest_rec`：每个用户最近一次生成的推荐结果，方便用 psql 直接查。
注意 API 用的是语义等价的子查询而不是这个视图 —— 视图只在 PostgreSQL 里存在，
用了它 SQLite 上的测试就跑不了。

## 字段口径（改字段前先读这一节）

| 约定 | 理由 |
|---|---|
| `attraction.source` / `attraction.license` **NOT NULL** | 数据来源与许可。S5 的许可声明页由它聚合生成，也是「将来可闭源」的数据层保险 |
| `attraction.status` 只有 `published` 才对外 | `draft` / `archived` 不得出现在任何接口与推荐里 |
| `rating_avg` / `rating_count` 仅由 `behavior_log` 聚合 | 种子数据里一律为 0。种子里写死一个好看的分数就是伪造 |
| `rec_result.rank` 从 1 开始，**API 按 `rank` 排序** | 不同算法的 `score` 不可比 |
| `rec_result.batch_id` 一次训练一个值 | 回写按 batch 原子切换，训练失败不影响线上已有结果 |
| `behavior_log` 的 `rating` 只有 `rate` 事件才有 | 由 CHECK 约束强制；`recsys` 导出时按它区分正负样本 |
| 时间统一 `TIMESTAMPTZ`，默认值由数据库给 | 应用层不传时间，避免时区混乱 |
| 文本统一 `TEXT`，不用 `VARCHAR(n)` | 长度限制在内容整理阶段只会带来迁移 |
| 经纬度只用于同城聚合 | 本项目**不做地图与定位**，`lat` / `lon` 不参与任何渲染 |

## 种子数据刻意留白的地方

- **没有评分**：`rating_avg` / `rating_count` 为 0，前端需处理「暂无评分」。
- **没有图片**：`attraction_image` 为空，图片素材在 S7 补齐，届时每条都带 `credit` 与 `license`。
- **门票价格需复核**：属于易变信息，S7 上线前逐条核对。
- **数据只来自自采**：`source` 写着「Have-A-Trip 自采（公开事实信息）」，不引入任何第三方数据集。

## 本地没有 PostgreSQL 时怎么验证

这台机器上没有 `psql`，所以本地的验证分两层：

1. **语法层**：用 `pglast`（libpg_query 的 Python 绑定）解析两个 SQL 文件，能过真实 PostgreSQL 语法树。
2. **行为层**：CI 里起一个 `postgres:16` service container，把 `schema.sql` 与 `seed.sql` **各跑两遍**，再断言表与行数。见 `.github/workflows/db-schema.yml`。

想在本机做行为层验证，最省事的是 Docker：

```bash
docker run --rm -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=attraction_atlas --name atlas-pg postgres:16
psql -h 127.0.0.1 -U postgres -d attraction_atlas -v ON_ERROR_STOP=1 -f db/schema.sql
docker rm -f atlas-pg
```

## 与推荐链路的关系

```
behavior_log  --(recsys/export_interactions.py)-->  .inter  --(RecBole 训练)-->  rec_result
                                                                                     |
                                        API 只读 v_latest_rec / rec_result <----------+
```

`rec_result` 是**衍生物**：如果景点数据里混进了 ODbL / CC BY-SA 来源，推荐结果也会沾上相同方式共享义务。
闭源前按 `docs/LICENSE-AUDIT.md` 第三节逐条复核。