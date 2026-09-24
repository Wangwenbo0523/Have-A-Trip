import type { MessageKey } from "../i18n/messages"
import type { Heritage } from "../types"

/**
 * 世界遗产类别的**文案键**。
 *
 * 这里存 key 而不是中文串: 翻译归 i18n 管, 这一层只负责「取值 -> 用哪句话」。
 * 中文串见 src/i18n/messages.ts 的 grade.heritage.*(short 用于徽章,
 * full 用于 title 提示)。
 */
export const HERITAGE_TEXT: Record<Heritage, { short: MessageKey; full: MessageKey }> = {
  cultural: { short: "grade.heritage.cultural.short", full: "grade.heritage.cultural.full" },
  natural: { short: "grade.heritage.natural.short", full: "grade.heritage.natural.full" },
  mixed: { short: "grade.heritage.mixed.short", full: "grade.heritage.mixed.full" },
}
