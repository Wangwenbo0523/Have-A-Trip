"""离线批量生成景点简介草稿。

这一刀和前面两刀的根本区别: 生成出来的东西**会变成景点档案的一部分**, 会被用户
当成事实读。所以它不挂在任何请求路径上 —— 只在本地跑, 产物是**待审 SQL**, 由人
逐条核对后手工执行。`app/api/ai.py` 里没有任何端点会调到这个模块。

护栏
----
1. 模型的输入只有这个景点**已公开的档案字段**(复用 ask.facts), 提示词里写明
   「除了这份档案你没有别的信息」。
2. 数字必须可溯源(复用 ask.verify): 草稿里出现档案里没有的数字, 整条作废。
3. 长度上限。简介是一句话, 不是导览词。
4. 产物只写 `UPDATE attraction SET summary = …`, 不碰 source / license / status
   这些字段 —— 出处由人负责, 不由模型负责。
5. 模型不可用 / 编造 / 超长: 这条景点没有草稿, 记进 note, 不影响其它景点。

已知边界: 第 2 条拦的是「可机械判定的编造」。模型把档案里的话换个说法并保持
属实, 是这一刀想要的结果; 但它把定性描述写岔(「很适合发呆」)机械校验拦不住 ——
所以产物必须人审。这一点写在 docs/LICENSE-AUDIT.md「AI 与模型条款」里。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..models import Attraction
from .ask import facts, verify
from .client import LLMClient, LLMError

PROMPT_VERSION = "ai-draft-v1"

# 简介是一句话, 不是导览词。超过上限的直接不要。
DRAFT_MAX = 120

# 现有简介短于这个长度就算「没写完」, 默认只给这类景点出草稿。
MIN_EXISTING = 30

DISCLAIMER = "草稿由模型生成, 必须人工核对后再入库。"

SYSTEM_PROMPT = """你在给「Have-A-Trip 景点大全」写一句话简介。

下面是这个景点的**全部**档案。除了这份档案, 你没有别的信息。

硬规则:
1. 只写档案里有的内容。档案里没有的, 不要补常识, 不要猜。
2. 不要出现档案里没有的数字 —— 价格、时长、年份、面积、海拔、评分都不行。
3. 不要写开放时间、天气、交通方式、预约方式、电话这类档案里没有的主题。
4. 一句话, 不超过 %d 字, 中文。不要用「欢迎来到」「值得一游」这类套话。
5. 只输出一个 JSON 对象, 形如 {"summary": "…"}

档案:
%%s"""% DRAFT_MAX


@dataclass
class Draft:
    """一条待审草稿。text 为空表示这条没通过校验, 原因在 note 里。"""

    slug: str
    text: str
    grounded: bool              # 是否通过校验(可以拿去人审)
    degraded: bool              # 是否降级(没配模型 / 调用失败 / 校验没过)
    before: str = ""            # 原来的简介, 写进待审文件给审核者对照
    note: str = ""
    model: str | None = None


def needs_draft(attraction: Attraction, min_len: int = MIN_EXISTING) -> bool:
    """简介为空或短于门槛时才需要补一版草稿。已经写得挺全的不动它。"""
    return len((attraction.summary or "").strip()) < min_len


def build_system_prompt(attraction: Attraction) -> str:
    sheet = facts(attraction)
    return SYSTEM_PROMPT % "\n".join(sheet.values())


def _clean(raw: object, sheet: dict[str, str]) -> tuple[str, str]:
    """返回 (通过校验的草稿, 没通过的原因)。两个都为空表示模型什么也没说。"""
    text = raw.get("summary") if isinstance(raw, dict) else None
    if not isinstance(text, str) or not text.strip():
        return "", "模型没有给出简介"
    text = " ".join(text.split())
    if len(text) > DRAFT_MAX:
        return "", "草稿超过 %d 字" % DRAFT_MAX
    ok, why = verify(text, sheet)
    if not ok:
        return "", why
    return text, ""


def draft_one(client: LLMClient, attraction: Attraction) -> Draft:
    """一个景点一版草稿。任何模型侧问题都记成 note, 不抛给调用方。"""
    before = (attraction.summary or "").strip()
    sheet = facts(attraction)

    if not client.available:
        return Draft(slug=attraction.slug, text="", grounded=False, degraded=True, before=before,
                     note="未配置模型, 离线生成必须真的用模型, 这条跳过。")

    try:
        raw = client.chat_json(build_system_prompt(attraction), "请按上面的规则写一句话简介。")
    except LLMError as exc:
        return Draft(slug=attraction.slug, text="", grounded=False, degraded=True, before=before,
                     note="模型调用失败(%s), 这条跳过。" % exc, model=client.model)

    text, why = _clean(raw, sheet)
    if not text:
        return Draft(slug=attraction.slug, text="", grounded=False, degraded=True, before=before,
                     note="草稿没过校验(%s), 这条跳过。" % (why or "模型没有给出简介"),
                     model=client.model)

    return Draft(slug=attraction.slug, text=text, grounded=True, degraded=False,
                 before=before, model=client.model)


def drafts(client: LLMClient, attractions: list[Attraction]) -> list[Draft]:
    """批量。返回的条数与输入一致 —— 没通过的也在结果里, 好让人知道漏了哪些。"""
    return [draft_one(client, attraction) for attraction in attractions]


def _sql_str(value: str) -> str:
    return value.replace("'", "''")


def render_sql(results: list[Draft], model: str, generated_at: str | None = None) -> str:
    """把通过校验的草稿渲染成待审 SQL。

    只生成 `UPDATE attraction SET summary = …`。简介之外的一切(来源、许可、状态、
    分类)都不在这份文件的射程里。没通过的草稿一条都不写进去。
    """
    stamp = generated_at or dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        "-- 待审草稿, 由 scripts/draft_attraction_summaries.py 生成, 请勿直接执行。",
        "-- 生成时间: %s | 模型: %s | 提示词版本: %s" % (stamp, model or "未配置", PROMPT_VERSION),
        "-- 审核流程: 逐条核对是否属实(尤其数字与地名) -> 删掉不放心的行 -> 再手工执行。",
        "-- 只改 summary 一个字段; 来源与许可字段由人负责, 不由模型负责。",
        "-- 口径见 docs/LICENSE-AUDIT.md「AI 与模型条款」。",
        "",
    ]
    rows: list[str] = []
    for item in results:
        if not item.grounded or not item.text:
            continue
        rows.append("-- 原: " + (item.before.replace("\n", " ") or "(空)"))
        rows.append("UPDATE attraction SET summary = '%s' WHERE slug = '%s';"
                    % (_sql_str(item.text), _sql_str(item.slug)))
        rows.append("")
    if not rows:
        lines.append("-- 本次没有通过校验的草稿, 未生成任何语句。")
        lines.append("")
        return "\n".join(lines)
    lines.append("BEGIN;")
    lines.append("")
    lines.extend(rows)
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)
