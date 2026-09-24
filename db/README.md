# db · 景点档案数据库

**目标库：PostgreSQL 14 及以上。** `db/schema.sql` 是权威定义，`backend/` 的 SQLAlchemy 模型与之对应。

## 文件

| 文件 | 说明 |
|---|---|
| `schema.sql` | 建表 DDL（幂等，可重复执行） |
| `seed/seed.sql` | 种子数据：9 个分类、31 个标签、140 个景点、506 条标签关联、140 个旅游方案、459 条方案步骤（幂等） |
| `seed/images.sql` | 景点配图：140 条 `attraction_image`，每条带 `credit` 与 `license`。**由 `scripts/make_attraction_covers.py` 生成，不要手改** |

## 执行

```bash
createdb attraction_atlas
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/schema.sql
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/seed.sql
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/images.sql
```

三个文件都写成幂等的，重跑不会报错也不会重复插数据：

```bash
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/schema.sql    # 再跑一次
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/seed.sql
psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/images.sql
```

验证：

```bash
psql -d attraction_atlas -c "select count(*) from attraction;"                  # 140
psql -d attraction_atlas -c "select count(*) from attraction_plan;"            # 140
psql -d attraction_atlas -c "select a.slug, p.title, p.days from attraction_plan p join attraction a on a.id = p.attraction_id limit 5;"
psql -d attraction_atlas -c "select a.name, c.name from attraction a join category c on c.id = a.category_id limit 5;"
psql -d attraction_atlas -c "select a.name, string_agg(t.name, ' / ') from attraction a join attraction_tag at on at.attraction_id = a.id join tag t on t.id = at.tag_id group by a.id, a.name limit 5;"
psql -d attraction_atlas -c "select count(*) from attraction_image;"           # 140
psql -d attraction_atlas -c "select credit, license, count(*) from attraction_image group by 1, 2;"
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
| `attraction_image` | 图集，每条带 `credit` 与 `license`；目前是 140 条自绘封面 |
| `attraction_plan` | 景点的旅游方案（自采行程建议），一条一个方案 |
| `attraction_plan_step` | 方案里的有序步骤，按 `day_no` 分组、组内按 `sort` 升序 |
| `app_user` | 用户（一期只有匿名 `device_id`） |
| `behavior_log` | 行为日志，推荐原料 |
| `rec_result` | 推荐结果，**API 只读这一张** |
| `attraction_embedding` | 景点描述的向量，语义检索用。**存 JSON 文本，不引 pgvector** |
| `itinerary` | LLM 生成的用户行程（一次生成一行），见下面与 `attraction_plan` 的区别 |
| `itinerary_item` | 行程里的一站，按 `(day_index, seq)` 排序 |
| `trip_quota` | 行程的限额与 token 预算计数器，按 `(owner_key, day)` 原子自增 |

### `itinerary` 与 `attraction_plan` 的区别

两个名字都叫「计划」，但**不是一类东西**，改哪个之前先认清：

| | `attraction_plan` | `itinerary` |
|---|---|---|
| 是谁的 | 景点自带的，全网共用一份 | **某个用户的一次请求**产出的 |
| 谁写的 | 人（`db/seed/seed.sql` 里审过的） | LLM 编排，人没看过 |
| 能不能有假的 | 不能，是档案的一部分 | 可能排得不合适，所以前端标注「出行前请核实」 |
| 生命周期 | 跟景点走 | 跟请求走，可以重生成 |
| 对外标识 | `slug`（可读） | `public_token`（随机，因为按 id 取会泄漏别人的需求） |

`itinerary_item.attraction_name` 是**快照**：景点改名或下架（`status='archived'`）之后，
回看历史行程仍然显示当时的那一刻。它的外键是 `ON DELETE RESTRICT` —— 景点硬删前
要想清楚这些历史行程怎么办。

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
| `attraction.a_level` / `heritage` 可为 `NULL`，且 **`NULL` 表示「未核实」而不是「没有」** | 景区名录与世界遗产名录都会调整，核实不了就留空。`a_level` 只对（中国大陆）景区有意义，境外景点一律留空，它们的「等级」看 `heritage` |
| `attraction_plan.budget_level` 只给档次不给金额 | 与 `ticket_price` 同理：具体价格是易变信息。四档 `free` / `low` / `mid` / `high` |
| 一个景点可以有多个方案，方案 slug 恒为 `<景点slug>-plan` | 便于按景点反查，也让 CI 能断言两者一致 |
| `attraction_embedding` 的 `embedding` 存 JSON 文本，**不用 pgvector** | 本仓库的 ORM 刻意只用可移植类型，测试跑 SQLite 内存库、本地不装 PostgreSQL。引 pgvector 会同时带来「建表要超级用户装扩展」「CI 要换镜像」「SQLite 与 PG 两套代码路径」三份复杂度，而全库 140 条景点用纯 Python 算余弦只要几毫秒。目录过万条时再换，接口不用改（见 `backend/app/search/vectors.py`） |
| `attraction_embedding` 的联合唯一键是 `(attraction_id, model)`，`model` 形如 `ollama:bge-m3:auto` | 切换模型期间新旧向量可以并存；`dim` 一并存下来，因为「维度」是数据的一部分，只放配置里的话配置一改旧向量就成了静默的垃圾 |
| `itinerary.status` 的 `rejected` 与 `failed` **必须分开** | `rejected` = 被限额拦下、一分钱没花；`failed` = 调了模型但失败。前端提示语完全不同，混在一起用户会以为是自己输入有问题 |
| `itinerary` 只存 `request_hash`，**不存需求原文** | 原文里常有同行人、预算这类个人信息。不存就不需要额外背一套保留期与删除机制，而生成并不需要回读原文 |
| `itinerary.unit_price` 是**单价快照** | 服务商调价后，历史行程的成本仍然按当时的价算 |
| `trip_quota` 的限额靠单条 `UPDATE ... WHERE used < :limit` + `rowcount` | 「先查条数再写入」在任何隔离级别下都不是原子的，两个并发请求会同时通过检查。单条语句的读-改-写在 PostgreSQL 与 SQLite 上都原子，所以限额不需要 Redis |
| 限额按**东八区自然日**结算，`day` 存 `YYYY-MM-DD` 文本 | 用文本而不是 `DATE`：两种数据库的时区处理不一样，这里要的只是「哪个自然日」这个分组键 |

## 种子数据的口径

140 个景点：**中国境内 100 个 + 境外 40 个（覆盖亚洲、欧洲、非洲、北美洲、南美洲、大洋洲）**，
全部为**自采的公开事实信息**，没有引入任何第三方数据集
（为什么这一点重要，见 `docs/LICENSE-AUDIT.md` 第三节）。分布：

| 分类 | slug | 个数 |
|---|---|---|
| 自然风光 | `nature` | 31 |
| 博物馆 | `museum` | 25 |
| 城市地标 | `landmark` | 22 |
| 宗教场所 | `religion` | 13 |
| 主题乐园 | `theme-park` | 13 |
| 历史古迹 | `history` | 11 |
| 考古遗址 | `archaeology` | 11 |
| 古镇村落 | `ancient-town` | 9 |
| 宫殿城堡 | `palace` | 5 |
| **合计** | | **140** |

覆盖 32 个省级行政区（中国境内）与 30 个境外国家（`province` 口径下合计 70 个），共 31 个标签。
用得最多的是 `world-heritage`（63）、`photography`（59）、`family`（42）、`ancient-architecture`（39）、
`indoor`（39）、`must-see`（37）与 `night-view`（36）。

**等级两列填了多少：** `a_level` 49 条（5A 41 + 4A 8），`heritage` 63 条。
剩下的是**未核实**而不是「没有等级」—— 中国景区质量等级与 UNESCO 名录都只能逐条查证，
查不到就留空，不猜。境外 40 条 `a_level` 全空，它们的等级看 `heritage`。

**旅游方案：** 140 个景点各一个方案，共 459 条步骤（1 天 121 个、2 天 15 个、3 天 3 个、4 天 1 个）。
方案与步骤同样是自采内容（`source` = `Have-A-Trip 自采（公开事实信息）`），
只给花费档次（`free` 4 / `low` 57 / `mid` 63 / `high` 16），不给金额。

### 刻意不写的数据

| 留白 | 原因 |
|---|---|
| 评分 `rating_avg` / `rating_count` 一律为 0 | 评分只能由 `behavior_log` 聚合得出。种子里写死一个好看的分数就是伪造，前端要会处理「暂无评分」 |
| 坐标 `lat` / `lon` 一律为 `NULL` | 不编造坐标。一期不做地图与定位，这两个字段只留给将来的同城聚合 |
| 票价只在**确定免费**时写 `0`，其余为 `NULL` | 票价是易变信息，写进种子的数字迟早会过期。目前只有 9 条写了 `0`（西湖、中国国家博物馆、苏州博物馆、外滩、橘子洲，以及查理大桥、大堡礁、米尔福德峡湾、圣托里尼这几处不收费的开放区域） |
| 景区等级 `a_level` 与世界遗产 `heritage` 只填能查证的 | `NULL` 是**未核实**。名录会调整，宁可空着也不猜；前端把两者都为空处理成「不显示徽章」 |
| 方案只给 `budget_level` 档次，不给金额 | 与票价同理，具体价格随季节浮动，写死就会过期 |
| 配图是**自绘**的，不是照片 | 原打算用 CC0 / 公有领域图库。实测 Wikimedia Commons 与 Openverse 在本机网络下不可达，Unsplash / Pixabay 又各有各的专有许可（不是 CC0），且对中国具体景点覆盖很薄。于是改成程序化生成 SVG（`scripts/make_attraction_covers.py`），出处就是脚本本身。每条仍走 `credit` 与 `license`（两列均为 `NOT NULL`），声明页会聚合出来 |
| `source_url` 为 `NULL` | 内容是逐条整理的公开事实，没有单一可引的页面；等有了再补，不为填空而填 |

### 幂等与自愈

`seed.sql` 是**声明式**的：重跑会把内容列同步成文件里的版本，而不是「已存在就跳过」。

- 分类 / 标签 / 景点用 `ON CONFLICT (slug) DO UPDATE`，所以修好的文案、补上的标签重跑就会生效；
- `rating_avg` / `rating_count` **不在** `DO UPDATE` 的列里 —— 那是用户行为攒出来的，重跑种子不许把它们抹掉；
- 景点标签先按 `source` 认领后 `DELETE` 再重建，所以把某个标签从清单里删掉，库里也会跟着删。

这条链路 CI 会真的验一遍：`db-schema.yml` 里先手工把一行改坏（改名称、塞坐标与票价、改 `a_level` 与 `heritage`），
再删掉它的标签关联与方案步骤，然后重跑种子，断言内容被修回来、坐标清回 `NULL`、`a_level` / `heritage` 回到文件里的值、
标签关联与方案步骤被重建。旧版种子用的是 `DO NOTHING`，遇到早期跑过种子的库不会自愈，换写法就是为了这个。

等级那两列不在景点 INSERT 的列清单里，而是单独一块 `UPDATE ... FROM (VALUES ...)`：
加进列清单会让每条老记录都要改一遍，而且它们的口径与其它字段不同（留空 = 未核实），单独一块更好核对。
方案步骤与标签一样是「先按 `source` 认领后删除再重建」，所以从清单里删掉一个方案，库里也会跟着删。

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
| Have-A-Trip 自采（公开事实信息） | MIT | 140 | 70 |

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
