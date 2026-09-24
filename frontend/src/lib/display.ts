import type { Lang } from "../i18n/messages"

/**
 * 名称的呈现方式。
 *
 * 中文界面: 中文名当标题, 英文名当副标题(加 i18n 之前就是这样)。
 * 英文界面: 角色对调 —— 有 name_en 就用它当标题, 中文名当副标题(便于对着现场
 * 指示牌找地方); 没有 name_en 的景点仍然显示中文名, 因为**库里的英文名只填了一
 * 部分**(见 db/README.md 的字段口径), 不替它编一个。
 */
export function namesFor(
  lang: Lang,
  item: { name: string; name_en?: string | null },
): { title: string; subtitle: string | null } {
  const english = (item.name_en ?? "").trim()
  if (lang === "en") {
    return english ? { title: english, subtitle: item.name } : { title: item.name, subtitle: null }
  }
  return { title: item.name, subtitle: english || null }
}

/** 只要标题的地方用它(卡片、表格、站外搜索关键词)。 */
export function localizedName(lang: Lang, item: { name: string; name_en?: string | null }): string {
  return namesFor(lang, item).title
}
