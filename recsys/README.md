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

## 搭建

```bash
# Python 3.11 独立环境
py -3.11 -m venv .venv-recsys
.venv-recsys\Scripts\activate        # Windows
# source .venv-recsys/bin/activate   # Linux/macOS

pip install -r recsys/requirements.txt
```

## 运行流程

```
backend 业务库 (user 行为)
      |  1. export_interactions.py  -> RecBole 原子文件格式 .inter
      v
recsys/dataset/attraction_atlas/
      |  2. run_recbole.py --config config/recbole.yaml   训练
      v
recsys/output/  (模型与预测)
      |  3. write_back.py  -> 推荐结果表
      v
backend 读结果表出推荐
```

## 配置

`config/recbole.yaml` 已按本项目场景配好：

- 起步用 **BPR**——景点-用户交互数据量小的时候，深度模型只会过拟合
- 交互数据积累起来后换 `LightGCN`（图结构，适合「相似景点」）或 `SASRec`（时序，适合「最近在看什么」）
- 评估用 `Recall@K / NDCG@K / Hit@K`，`valid_metric: NDCG@10`

## 注意

- 训练数据来自业务库，可能包含 ODbL / CC BY-SA 来源的景点数据。**推荐结果表是衍生物**，
  闭源前需按 `../docs/LICENSE-AUDIT.md` 第三节复核。
- 冷启动阶段（还没有行为数据）不要等 RecBole：API 侧用标签/分类/城市的内容相似度兜底即可。