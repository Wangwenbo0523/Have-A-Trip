# 待审草稿目录

这里放 `scripts/draft_attraction_summaries.py` 生成的**待审**简介草稿。
生成的文件不参与运行时, 也不直接入库 —— 它们是给人看的中间产物。

## 流程

1. 配好模型(见 `.env.example` 的 `LLM_PROVIDER`), 指向库里需要补简介的景点:

   ```bash
   python scripts/draft_attraction_summaries.py                  # 简介为空或过短的
   python scripts/draft_attraction_summaries.py --all --limit 20  # 全部景点都来一版
   ```

2. 逐条核对生成的 `ai_summary_draft.sql`。**每一条都要**:
   - 数字、地名、等级与库里的 `source` 对得上;
   - 删掉自己查不到出处的句子(模型善于把常识写得像事实);
   - 不整段照抄, 简介要像人写的。
3. 核对通过的语句手工抄进 `db/seed/seed.sql` 对应的景点条目, 随种子一起走 CI;
   不执行本目录里的 `.sql` 文件本身。

## 为什么生成物不进版本库

- 简介会变成**用户读到的事实**, 版本库里只应该有**已经人工核对过**的版本;
- 机器生成的一大串候选留在 `git log` 里没有价值, 只会让 `git blame` 变吵;
- `source` / `license` 由人负责, 不由模型负责 —— 这条边界写进了
  `docs/LICENSE-AUDIT.md` 的「AI 与模型条款」。

所以 `.gitignore` 里忽略本目录的 `*.sql`, 只保留这份说明。
