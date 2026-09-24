"""第二步：训练 RecBole 模型，并产出 Top-K 预测文件。

```
recsys/dataset/<dataset>/  --(RecBole BPR)-->  recsys/saved/<batch_id>/*.pth
                           --(full-sort 打分)-->  recsys/output/<batch_id>/predictions.tsv
                                                   recsys/output/<batch_id>/meta.json
```

三件事值得单独说：

1. **数据量不够就跳过，不产垃圾推荐。** 协同过滤在几百条交互上只会过拟合，
   而 API 已经有内容相似度与热门兜底（S2）。所以门槛不过时本脚本打印 `SKIP` 并
   **以退出码 0 结束** —— 对定时任务来说「跳过」不是失败，别让它告警。
2. **必须跑在 Python 3.11 的独立环境**，且不要把它 import 进 backend（见 `../docs/BASES.md`）。
3. **预测用 full-sort 打分**：对每个用户给全部候选景点打分排序，并把该用户历史里
   出现过的景点置为 -inf（RecBole 的 `full_sort_topk` 自带这个行为），所以回写的结果
   不含「已经看过/收藏过」的景点。

命令行里的参数刻意用空格分隔的写法（`--k 20`）而不是 `--k=20`：RecBole 会自己解析
`sys.argv` 里 `--键=值` 形式的参数并当成训练超参（见 `recbole/config/configurator.py`）。
写成等号形式就会悄悄改掉训练配置。
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys

import common


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="训练 RecBole 模型并导出 Top-K 预测")
    common.add_common_args(parser)
    parser.add_argument("--config", default=None, help="训练配置, 默认 recsys/config/recbole.yaml")
    parser.add_argument("--out-dir", default=None, help="输出根目录, 默认 recsys/output")
    parser.add_argument("--saved-dir", default=None, help="模型保存根目录, 默认 recsys/saved")
    parser.add_argument("--k", type=int, default=None,
                        help="每个用户产出多少个推荐, 默认取配置里 topk 的最大值")
    parser.add_argument("--epochs", type=int, default=None, help="覆盖配置里的 epochs")
    parser.add_argument("--users-per-batch", type=int, default=512,
                        help="打分时每批多少个用户, 控制显存/内存")
    parser.add_argument("--force", action="store_true", help="数据量低于门槛也硬训(不建议)")
    parser.add_argument("--min-ndcg", type=float, default=None,
                        help="设了就卡口: 验证集 NDCG@10 低于它就不回写(默认不卡)")
    return parser.parse_args(argv)


def check_thresholds(stats: dict, force: bool, log) -> bool:
    """返回 True 表示可以训练。"""
    gates = [("MIN_INTERACTIONS", common.MIN_INTERACTIONS, stats.get("interactions", 0)),
             ("MIN_USERS", common.MIN_USERS, stats.get("users", 0)),
             ("MIN_ITEMS", common.MIN_ITEMS, stats.get("items", 0))]
    thin = [f"{name}={got} < {need}" for name, need, got in gates if got < need]
    if not thin:
        return True
    if force:
        log.warning("数据量低于门槛(%s), 但 --force 要求继续。", "; ".join(thin))
        return True
    log.warning("SKIP: 数据量不足(%s), 不训练、不产出预测。", "; ".join(thin))
    log.warning("这是预期行为: 让 API 走内容相似度兜底, 比推一堆噪音好。")
    return False


def main(argv=None) -> int:
    args = parse_args(argv)
    common.setup_logging(args.verbose)
    log = common.log()

    dataset_dir = common.DATASET_DIR / args.dataset
    inter_path = dataset_dir / f"{args.dataset}.inter"
    stats_path = dataset_dir / "stats.json"

    if not inter_path.is_file():
        log.error("找不到 %s。先跑 export_interactions.py。", inter_path)
        return 2
    if not stats_path.is_file():
        log.error("找不到 %s。先跑 export_interactions.py(它会顺手写下规模统计)。", stats_path)
        return 2

    stats = common.read_json(stats_path)
    log.info("数据集 %s: 交互 %d 条 / 用户 %d 人 / 景点 %d 个(统计时间 %s)",
             args.dataset, stats.get("interactions", 0), stats.get("users", 0),
             stats.get("items", 0), stats.get("generated_at", "?"))
    if not check_thresholds(stats, args.force, log):
        return 0

    # RecBole 会自己解析 sys.argv, 所以训练参数一律通过 config_dict 显式传, 不靠命令行拼接
    import numpy as np
    import torch
    from recbole.config import Config
    from recbole.data import create_dataset, data_preparation
    from recbole.quick_start import run_recbole
    from recbole.utils import get_model, init_logger, init_seed
    from recbole.utils.case_study import full_sort_topk

    batch_id = common.new_batch_id()
    batch_ts = common.utcnow()
    # 路径先定死: 下面会 chdir, 之后相对路径的基准就变了
    config_path = (pathlib.Path(args.config) if args.config else common.CONFIG_PATH).resolve()
    out_dir = (pathlib.Path(args.out_dir) if args.out_dir else common.OUTPUT_DIR) / batch_id
    saved_dir = (pathlib.Path(args.saved_dir) if args.saved_dir else common.SAVED_DIR) / batch_id
    saved_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # RecBole 的 init_logger 把日志根目录硬编码成 "./log/"(完全不看
    # config["log_dir"]), tensorboard 的 "log_tensorboard" 也是 cwd 相对路径。
    # 直接在仓库里跑就会拉出 recsys/log/ 与 recsys/log_tensorboard/
    # 两个野目录, 事后追着改 .gitignore 不如让它们落在该落的地方。
    os.chdir(out_dir)

    overrides = {
        # 用绝对路径, 这样从任何目录执行都一样
        "data_path": str(common.DATASET_DIR),
        "checkpoint_dir": str(saved_dir),
        "log_dir": str(out_dir / "log"),
    }
    if args.epochs is not None:
        overrides["epochs"] = args.epochs

    log.info("批次 %s, 配置 %s", batch_id, config_path)
    before = set(saved_dir.glob("*.pth"))

    result = run_recbole(
        config_file_list=[str(config_path)],
        config_dict=overrides,
        model=None,
        dataset=None,
    )
    valid = result.get("best_valid_result") or {}
    test = result.get("test_result") or {}
    log.info("验证集: %s", {k: round(float(v), 4) for k, v in valid.items()})
    log.info("测试集: %s", {k: round(float(v), 4) for k, v in test.items()})

    new_checkpoints = sorted(set(saved_dir.glob("*.pth")) - before)
    if not new_checkpoints:
        log.error("训练结束了但没找到新的模型文件, 检查 checkpoint_dir=%s", saved_dir)
        return 3
    model_file = new_checkpoints[-1]
    log.info("模型文件: %s", model_file)

    ndcg = None
    for key, value in valid.items():
        if key.upper() == "NDCG@10":
            ndcg = float(value)
    if args.min_ndcg is not None and (ndcg is None or ndcg < args.min_ndcg):
        log.warning("SKIP: 验证集 NDCG@10=%s 低于门槛 %s, 不回写预测。",
                    "n/a" if ndcg is None else round(ndcg, 4), args.min_ndcg)
        log.warning("模型与预测都不写盘 —— 宁可让 API 走兜底, 也不推没学出东西的结果。")
        shutil.rmtree(saved_dir, ignore_errors=True)
        return 0

    # ---------------------------------------------------------------- 加载模型
    # 这里不直接用 recbole.quick_start.load_data_and_model: 它 torch.load 时没关
    # weights_only, 而 torch >= 2.6 默认把 weights_only 打开, RecBole 的 checkpoint 里
    # 存着 Config 这类自定义对象, 会直接反序列化失败。下面的流程与它逐行等价。
    checkpoint = torch.load(model_file, weights_only=False)
    # Config 会自动在 data_path 后面接上数据集名(见 recbole/config/configurator.py),
    # 所以这里传的仍然是 recsys/dataset 这一层, 不要自己再加一遍。
    config = Config(config_file_list=[str(config_path)], config_dict=overrides)
    dataset = create_dataset(config)
    train_data, _valid_data, test_data = data_preparation(config, dataset)
    model = get_model(config["model"])(config, train_data._dataset).to(config["device"])
    model.load_state_dict(checkpoint["state_dict"])
    model.load_other_parameter(checkpoint.get("other_parameter"))

    topk = args.k or max(int(x) for x in config["topk"])
    log.info("数据集过滤后: 用户 %d / 景点 %d / 交互 %d, 每个用户产出 Top-%d",
             dataset.user_num - 1, dataset.item_num - 1, dataset.inter_num, topk)

    # ---------------------------------------------------------------- 打分
    uid_field, iid_field = dataset.uid_field, dataset.iid_field
    internal_uids = np.arange(1, dataset.user_num, dtype=np.int64)
    user_tokens = dataset.id2token(uid_field, internal_uids)

    rows = 0
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = out_dir / "predictions.tsv"
    with predictions_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("user_id\trank\tattraction_id\tscore\n")
        for start in range(0, len(internal_uids), args.users_per_batch):
            chunk = internal_uids[start:start + args.users_per_batch]
            scores, index = full_sort_topk(chunk, model, test_data, topk, device=config["device"])
            item_tokens = dataset.id2token(iid_field, index.cpu().numpy())
            for row, (score_row, item_row) in enumerate(zip(scores.cpu().numpy(), item_tokens)):
                user_token = str(user_tokens[start + row])
                for rank, (value, item_token) in enumerate(zip(score_row, item_row), start=1):
                    fh.write(f"{user_token}\t{rank}\t{item_token}\t{float(value):.6f}\n")
                    rows += 1

    if rows == 0:
        log.warning("SKIP: 一个预测都没产出, 回写没有意义。")
        return 0

    algo = str(config["model"])
    meta = {
        "batch_id": batch_id,
        "generated_at": common.iso(batch_ts),
        "algo": algo,
        "k": topk,
        "users": int(len(internal_uids)),
        "predictions": rows,
        "dataset": args.dataset,
        "dataset_filtered": {
            "users": int(dataset.user_num - 1),
            "items": int(dataset.item_num - 1),
            "interactions": int(dataset.inter_num),
        },
        "dataset_stats": stats,
        "valid_metrics": {k: float(v) for k, v in valid.items()},
        "test_metrics": {k: float(v) for k, v in test.items()},
        "model_file": str(model_file),
        "config_file": str(config_path),
        "hyper": {
            "epochs": int(config["epochs"]),
            "learning_rate": float(config["learning_rate"]),
            "seed": int(config["seed"]),
            "eval_mode": str(config["eval_args"]["mode"]),
            "val_interval": config["val_interval"],
        },
        # 回写时写进 rec_result.reason 的那句话。它是给用户看的, 所以要像人话。
        "reason": f"{algo} 离线推荐: 根据与你兴趣相近的人看过、收藏过、评过高分的景点挑选",
        "predictions_file": predictions_path.name,
    }
    common.write_json(out_dir / "meta.json", meta)
    log.info("预测 %d 行 -> %s", rows, predictions_path)
    log.info("下一步: python recsys/write_back.py %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
