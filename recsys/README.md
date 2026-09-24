# recsys · RecBole 调用层

本目录放**调用 RecBole 的代码与配置**，不放 RecBole 源码（它是 pip 依赖，vendor 进来只会让升级变难）。

## 为什么必须是独立环境

| 证据 | 影响 |
|---|---|
| `ray>=1.13.0, <=2.6.3` | Ray 2.6.3 不支持 Python 3.12+，Python 上限锁死 3.11 |
| `hyperopt==0.2.5` | 2020 年的老包 |
| `setup.py` 无 `python_requires` | pip 不拦，装完运行期才炸 |

API 栈跑在 Python 3.13 + numpy 2.5，**两者不可能共存**。所以：

```
API 进程 (Python 3.13)  --×-->  绝不 import recbole
离线训练 (Python 3.11)  ---->    写入推荐结果表
```

`backend/tests/test_no_recbole.py` 用 AST 检查把这条线钉死：API 代码里出现 `import recbole` 就测试失败。

## 搭建

```bash
# 用 uv 拉一个独立解释器（不必和系统 Python 版本妥协）
uv venv --python 3.11 recsys/.venv
uv pip install --python recsys/.venv/Scripts/python.exe -r recsys/requirements.txt   # Windows
uv pip install --python recsys/.venv/bin/python      -r recsys/requirements.txt      # Linux / macOS
```

`python3.11 -m venv recsys/.venv` 也可以，只要解释器是 3.11。

### 四个装完真的跑不起来的坑

`requirements.txt` 里额外钉了 3 个版本 + 1 条配置。**这些不是「锁一下更稳」，松开任何一条链路都会挂**：

| 松开 | 现象 |
|---|---|
| `setuptools==80.9.0` | 81 起删了 `pkg_resources`，`ray` 在 import 期就 `ModuleNotFoundError` |
| `numpy==1.26.4` | numpy 2 删了 `np.bool8`，`ray/tune/logger/tensorboardx.py` 崩 |
| `torch==2.5.1` | torch 2.6 起 `torch.load` 默认 `weights_only=True`，读不了 RecBole 的 checkpoint（训练能跑完，到打分阶段才炸） |
| `config/recbole.yaml` 的 `encoding: utf-8` | 不写就回落系统 locale（中文 Windows 上是 GBK），城市名里一个中文就 `UnicodeDecodeError` |

`torch` 那条还有一层保险：`run_recbole.py` 自己 `torch.load(..., weights_only=False)`，不依赖上游默认值。

## 运行流程

三步，按顺序跑：

```
业务库 behavior_log + attraction(status='published')
      |  1. export_interactions.py
      v
recsys/dataset/attraction_atlas/    attraction_atlas.inter / .item / stats.json
      |  2. run_recbole.py
      v
recsys/saved/<batch_id>/*.pth                   模型
recsys/output/<batch_id>/predictions.tsv        预测
recsys/output/<batch_id>/meta.json              指标与元信息
      |  3. write_back.py
      v
rec_result  -->  API 只读这张表
```

```bash
export RECSYS_DATABASE_URL='postgresql://user:pass@host:5432/attraction_atlas'   # 或 DATABASE_URL

recsys/.venv/bin/python recsys/export_interactions.py
recsys/.venv/bin/python recsys/run_recbole.py
recsys/.venv/bin/python recsys/write_back.py --dry-run   # 先看要写什么
recsys/.venv/bin/python recsys/write_back.py
```

后两步都不带参数：默认取 `recsys/dataset/attraction_atlas/` 与 `recsys/output/` 下最新的一批。
批次号形如 `20260924T172755Z-27d7`，字典序即时间序。

### 交互口径

`common.py` 里的 `implicit_rating()` 把四种行为折算成隐式偏好强度：

| 行为 | 强度 |
|---|---|
| `rate` | 用户给的实际分（1–5） |
| `favorite` | 4.0 |
| `share` | 3.0 |
| `view` + 停留 ≥ 30s | 2.0 |
| `view` + 停留 < 30s | 1.0 |

**这不是评分。** 它只喂模型，不写回任何用户可见字段；`attraction.rating_avg` 只能由 `rate`
事件聚合得出（见 `db/README.md`）。同一个 `(用户, 景点)` 只取**最后一次**行为，与
`backend/app/aggregates.py` 的口径一致。

### 数据量不足是跳过，不是失败

门槛在 `common.py`：交互 < 200 条、用户 < 20 人、景点 < 20 个就不训练，只打一行 `SKIP` 并以
**退出码 0** 结束 —— 对 cron 来说「还没到火候」不是错误，不该告警。`--force` 可以硬训，不建议。

理由：协同过滤在几百条交互上只会过拟合，而 API 侧已经有内容相似度与热门兜底（S2）。
写一批噪声进 `rec_result`，不如让推荐接口走兜底。

## 回写口径

- 一整批**一个事务**：要么整批可见，要么旧结果原封不动，不会读到半拉子批次。
- `generated_at` 整批共用一个值，API 才能用 `max(generated_at)` 干净地切过去。
- 写回前校验死链：只保留「用户存在」且「景点 `status='published'`」的行。训练之后景点被下架是
  常态，推一个已下架的景点没有意义。被丢掉的行会打日志，不静默。
- 写完清掉同用户**更旧**的批次（`--no-prune` 可关）；只删更旧的，所以重跑一个历史批次不会误删
  更新的批次。
- 重跑同一批次是幂等的：先按 `batch_id` 删掉自己，再整体插入。
- 缺 `meta.json` 时会合成一个通用 `reason`，不会拿空值去顶 `NOT NULL`。

## 配置

`config/recbole.yaml` 已按本项目场景配好：

- 起步用 **BPR**——景点-用户交互数据量小的时候，深度模型只会过拟合
- 交互数据积累起来后换 `LightGCN`（图结构，适合「相似景点」）或 `SASRec`（时序，适合「最近在看什么」）
- 评估用 `Recall@K / NDCG@K / Hit@K`，`valid_metric: NDCG@10`
- `val_interval.rating: "[3,inf)"`：只有明确的正向反馈才算「感兴趣」

## 注意

- **日志不会落在仓库里**: RecBole 的 `recbole/utils/logger.py` 里 `init_logger` **硬编码**了
  `LOGROOT = "./log/"`，完全不看 `config["log_dir"]`；tensorboard 的 `log_tensorboard` 也是 cwd
  相对路径。所以 `run_recbole.py` 会先 `os.chdir()` 到本批次目录，让它们落在 `recsys/output/<batch_id>/`
  里，而不是在仓库根拉出两个野目录。
- 训练数据来自业务库，可能包含 ODbL / CC BY-SA 来源的景点数据。**推荐结果表是衍生物**，
  闭源前需按 `../docs/LICENSE-AUDIT.md` 第三节复核。
- 冷启动阶段（还没有行为数据）不要等 RecBole：API 侧用标签 / 分类 / 城市的内容相似度兜底即可。
- 训练产物（`recsys/dataset/`、`recsys/output/`、`recsys/saved/`、`log/`、`log_tensorboard/`）
  一律不进仓库，`.gitignore` 已覆盖。