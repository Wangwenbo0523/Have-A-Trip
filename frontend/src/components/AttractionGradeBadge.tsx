import React from "react"

import { HERITAGE_LABELS, aLevelText } from "../lib/grade"
import type { ALevel, Heritage } from "../types"
import "../styles/AttractionGradeBadge.css"

interface AttractionGradeBadgeProps {
  aLevel: ALevel | null
  heritage: Heritage | null
}

/**
 * 等级徽章。a_level 与 heritage 是两套刻度 —— 世界遗产没有 A 级, 所以有 A 级就先
 * 显示 A 级。两者都为空表示「未核实」, 此时不渲染任何东西, 免得把未核实画成无等级。
 */
const AttractionGradeBadge = ({ aLevel, heritage }: AttractionGradeBadgeProps) => {
  if (aLevel) {
    return (
      <span className="gradeBadge gradeBadge--aLevel" title={aLevelText(aLevel)}>
        {aLevel}
      </span>
    )
  }
  if (heritage) {
    return (
      <span className="gradeBadge gradeBadge--heritage" title={HERITAGE_LABELS[heritage].full}>
        {HERITAGE_LABELS[heritage].short}
      </span>
    )
  }
  return null
}

export default AttractionGradeBadge
