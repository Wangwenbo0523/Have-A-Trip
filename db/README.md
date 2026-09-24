# db · 景点档案数据库

**目标库：PostgreSQL 14 及以上。** `db/schema.sql` 是权威定义，`backend/` 的 SQLAlchemy 模型与之对应。

## 文件

| 文件 | 说明 |
|---|---|
| `schema.sql` | 建表 DDL（幂等，可重复执行） |
| `seed/seed.sql` | 种子数据：7 个分类、19 个标签、50 个景点、175 条标签关联（幂等） |

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
psql -d attraction_atlas -c "select count(*) from attraction;"                  # 50
psql -d attraction_atlas -c "select a.name, c.name from attraction a join category c on c.id = a.category_id limit 5;"
psql -d attraction_atlas -c "select a.name, string_agg(t.name, ' / ') from attraction a join attraction_tag at on at.attraction_id = a.id join tag t on t.id = at.tag_id group by a.id, a.name limit 5;"
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

## 种子数据的口径

一期 50 个景点，全部为**自采的公开事实信息**，没有引入任何第三方数据集
（为什么这一点重要，见 `docs/LICENSE-AUDIT.md` 第三节）。分布：

| 分类 | slug | 个数 |
|---|---|---|
| 自然风光 | `nature` | 12 |
| 历史古迹 | `history` | 10 |
| 博物馆 | `museum` | 6 |
| 城市地标 | `landmark` | 6 |
| 古镇村落 | `ancient-town` | 6 |
| 宗教场所 | `religion` | 5 |
| 主题乐园 | `theme-park` | 5 |
| **合计** | | **50** |

覆盖 21 个省级行政区。19 个标签里用得最多的是 `photography`（23）、`world-heritage`（23）、
`family`（21）、`night-view`（17）、`ancient-architecture`（17）。

### 刻意不写的数据

| 留白 | 原因 |
|---|---|
| 评分 `rating_avg` / `rating_count` 一律为 0 | 评分只能由 `behavior_log` 聚合得出。种子里写死一个好看的分数就是伪造，前端要会处理「暂无评分」 |
| 坐标 `lat` / `lon` 一律为 `NULL` | 不编造坐标。一期不做地图与定位，这两个字段只留给将来的同城聚合 |
| 票价只在**确定免费**时写 `0`，其余为 `NULL` | 票价是易变信息，写进种子的数字迟早会过期。目前只有 5 条写了 `0`（西湖、中国国家博物馆、苏州博物馆、外滩、橘子洲） |
| `attraction_image` 一条都没有 | 没有可靠出处的图不进仓库。图片是 S7 之后单独一项工作，落一条就要带 `credit` 与 `license`（两列均为 `NOT NULL`） |
| `source_url` 为 `NULL` | 内容是逐条整理的公开事实，没有单一可引的页面；等有了再补，不为填空而填 |

### 幂等与自愈

`seed.sql` 是**声明式**的：重跑会把内容列同步成文件里的版本，而不是「已存在就跳过」。

- 分类 / 标签 / 景点用 `ON CONFLICT (slug) DO UPDATE`，所以修好的文案、补上的标签重跑就会生效；
- `rating_avg` / `rating_count` **不在** `DO UPDATE` 的列里 —— 那是用户行为攒出来的，重跑种子不许把它们抹掉；
- 景点标签先按 `source` 认领后 `DELETE` 再重建，所以把某个标签从清单里删掉，库里也会跟着删。

这条链路 CI 会真的验一遍：`db-schema.yml` 里先手工把一行改坏、再删掉它的标签关联，然后重跑种子，
断言内容被修回来、坐标清回 `NULL`、标签关联被重建。旧版种子用的是 `DO NOTHING`，
遇到早期跑过种子的库不会自愈，换写法就是为了这个。

### 数据来源清单

S5 的许可声明页**从数据库聚合生成**，不要在前端写死一份。查询：

```sql
select source, license, count(*) as records,
       count(distinct province) as provinces
from attraction
where status = 'published'
group by source, license
order by records desc;
```

当前结果（一期）：

| source | license | 景点数 | 覆盖省份 |
|---|---|---|---|
| Have-A-Trip 自采（公开事实信息） | MIT | 50 | 21 |

只有一行是**刻意**的：只要将来引入别的来源，这里就会多一行，声明页跟着变。
任何 ODbL（OpenStreetMap）或 CC BY-SA（Wikipedia / Wikivoyage）数据都必须先隔离在独立的
导入脚本与数据集目录里，再决定要不要进这张表 —— 详见 `docs/LICENSE-AUDIT.md` 第三节。

## 本地没有 PostgreSQL 时怎么验证

这台机器上没有 `psql`，所以本地的验证分两层：

1. **语法层**：用 `pglast`（libpg_query 的 Python 绑定）解析两个 SQL 文件，能过真实 PostgreSQL 语法树。
2. **行为层**：CI 里起一个 `postgres:16` service container，把 `schema.sql` 与 `seed.sql` **各跑两遍**，再断言表、行数与 CHECK 约束。见 `.github/workflows/db-schema.yml`。

想在本机做行为层验证，最省事的是 Docker：

```bash
docker run --rm -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=attraction_atlas --name atlas-pg postgres:16
psql -h 127.0.0.1 -U postgres -d attraction_atlas -v ON_ERROR_STOP=1 -f db/schema.sql
docker rm -f atlas-pg
```

CI 里那几行 `expect` 是**把口径变成断言**：种子改了行数、写了坐标、写了「不确定免费」的票价、
插了图片，CI 都会红。所以改 `seed.sql` 时记得同步改 `.github/workflows/db-schema.yml` 里的数字。

## 与推荐链路的关系

```
behavior_log  --(recsys/export_interactions.py)-->  .inter  --(RecBole 训练)-->  rec_result
                                                                                     |
                                        API 只读 v_latest_rec / rec_result <----------+
```

`rec_result` 是**衍生物**：如果景点数据里混进了 ODbL / CC BY-SA 来源，推荐结果也会沾上相同方式共享义务。
闭源前按 `docs/LICENSE-AUDIT.md` 第三节逐条复核。
