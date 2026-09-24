"""把景点档案压成一段可向量化的稳定文本。

「稳定」是这里唯一重要的性质: 同一份档案在任何时候、任何机器上都必须拼出逐字节相同的
文本, 否则 content_hash 会漂, 全量重算会变成日常操作。

所以:
  * 字段顺序写死, 不依赖 dict 迭代顺序;
  * 标签按 slug 排序, 不依赖数据库返回顺序;
  * 正文截断到固定长度, 不把 description 整段塞进去 —— 超长正文对向量没有额外信息量,
    只会推高成本;
  * 拼串口径的版本号参与 hash: 改了拼法就整体失效重算, 不会新旧混用。
"""
from __future__ import annotations

import hashlib

from ..models import Attraction

# 拼串口径。改动 canonical_text 的字段或格式时必须 +1, 否则旧向量会被当成新的复用。
PIPELINE_VERSION = "1"

# 正文参与向量化的长度上限。summary 已经是一句话概括, description 只取开头。
DESCRIPTION_CHARS = 600


def _clean(value: object) -> str:
    """把 None / 空白统一成空串, 并压掉换行 —— 换行会让同一段内容拼出两种文本。"""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _level_label(attraction: Attraction) -> str:
    """等级的口径: A 级只适用于中国大陆景区, 境外看世界遗产类别。两者都可能为空。"""
    parts = []
    if attraction.a_level:
        parts.append("国家 %s 级景区" % attraction.a_level)
    heritage = {"cultural": "世界文化遗产", "natural": "世界自然遗产", "mixed": "世界文化与自然双遗产"}
    if attraction.heritage in heritage:
        parts.append(heritage[attraction.heritage])
    return " ".join(parts)


def canonical_text(attraction: Attraction) -> str:
    """景点的规范化文本。前台检索与离线批量必须都走这一个函数。"""
    tags = " ".join(sorted(_clean(tag.name) for tag in attraction.tags if tag.name))
    region = " ".join(
        part
        for part in (
            _clean(attraction.country_code),
            _clean(attraction.province),
            _clean(attraction.city),
        )
        if part
    )
    summary = _clean(attraction.summary)
    description = _clean(attraction.description)[:DESCRIPTION_CHARS]
    lines = [
        "名称: " + _clean(attraction.name),
        "英文名: " + _clean(attraction.name_en),
        "分类: " + _clean(attraction.category.name if attraction.category else ""),
        "地区: " + region,
        "等级: " + _level_label(attraction),
        "标签: " + tags,
        "最佳季节: " + _clean(attraction.best_season),
        "简介: " + summary,
        "详情: " + description,
    ]
    # 空字段留一行空的「xxx: 」而不是整行删掉: 两种拼法都能用, 但只能固定选一种。
    return "\n".join(lines)


def content_hash(text: str, model: str, pipeline_version: str = PIPELINE_VERSION) -> str:
    """档案指纹: 文本 + 模型标识 + 拼串版本。

    **模型必须进指纹**: 换了向量模型, 旧的 content_hash 依然对得上, 增量更新就会
    一条都不重建, 而新模型的查询向量与旧模型的库存向量根本不可比 —— 表现是
    「语义搜索整体返回空」, 界面上却看不出任何异常。这是最难查的一类故障。
    """
    raw = "%s|%s|%s" % (model, pipeline_version, text)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
