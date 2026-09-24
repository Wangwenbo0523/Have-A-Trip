import type { ALevel, Heritage } from "../types"

/** 世界遗产类别的中文说法。徽章上用短说法, title 与详情页用完整说法。 */
export const HERITAGE_LABELS: Record<Heritage, { short: string; full: string }> = {
  cultural: { short: "文化遗产", full: "世界文化遗产" },
  natural: { short: "自然遗产", full: "世界自然遗产" },
  mixed: { short: "双重遗产", full: "世界双重遗产" },
}

/** A 级的完整说法。 */
export const aLevelText = (level: ALevel) => `国家 ${level} 级旅游景区`
