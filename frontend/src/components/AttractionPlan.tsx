import React from "react"

import { useI18n, type MessageKey } from "../i18n"
import type { Plan, PlanBudgetLevel, PlanStep } from "../types"
import "../styles/AttractionPlan.css"

/**
 * 花费档次 -> **文案键**。只给档次不给金额 —— 价格是易变信息, 见 db/README.md。
 * 存 key 而不是中文串: 模块级常量拿不到当前语种。
 */
const BUDGET_KEYS: Record<PlanBudgetLevel, MessageKey> = {
  free: "plan.budget.free",
  low: "plan.budget.low",
  mid: "plan.budget.mid",
  high: "plan.budget.high",
}

/** 按 day_no 分组, 组内按 sort 升序。后端已经排好, 这里再排一次以防上游改动。 */
export const groupByDay = (steps: PlanStep[]): [number, PlanStep[]][] => {
  const days = new Map<number, PlanStep[]>()
  const ordered = [...steps].sort((a, b) => a.day_no - b.day_no || a.sort - b.sort)
  for (const step of ordered) {
    const bucket = days.get(step.day_no)
    if (bucket) {
      bucket.push(step)
    } else {
      days.set(step.day_no, [step])
    }
  }
  return [...days.entries()]
}

const PlanStepItem = ({ step }: { step: PlanStep }) => {
  const { t } = useI18n()

  return (
    <li className="plan__step">
      <p className="plan__stepTitle">
        {step.title}
        {step.duration_hours === null || step.duration_hours === undefined ? null : (
          <span className="plan__duration">
            {t("plan.step.duration", { hours: step.duration_hours })}
          </span>
        )}
      </p>
      <p className="plan__detail">{step.detail}</p>
      {step.tip ? <p className="plan__tip">{t("plan.step.tip", { tip: step.tip })}</p> : null}
    </li>
  )
}

/** 一个景点的一份游玩方案。日期分组渲染, 同一天内按 sort 升序。 */
const AttractionPlan = ({ plan }: { plan: Plan }) => {
  const { t } = useI18n()

  return (
    <article className="plan">
      <header className="plan__head">
        <h4 className="plan__title">{plan.title}</h4>
        <ul className="plan__meta">
          {/* 英文的 1 与其余要分开说(1 day / 3 days), 文案表里给单数留了 .one 键 */}
          <li>{plan.days === 1 ? t("plan.days.one") : t("plan.days", { days: plan.days })}</li>
          {plan.budget_level ? <li>{t(BUDGET_KEYS[plan.budget_level])}</li> : null}
          {plan.best_for ? <li>{t("plan.bestFor", { text: plan.best_for })}</li> : null}
        </ul>
      </header>

      <p className="plan__summary">{plan.summary}</p>

      {groupByDay(plan.steps).map(([day, steps]) => (
        <section className="plan__day" key={day}>
          <h5 className="plan__dayTitle">{t("plan.dayTitle", { day })}</h5>
          <ol className="plan__steps">
            {steps.map((step) => (
              <PlanStepItem key={`${step.day_no}-${step.sort}`} step={step} />
            ))}
          </ol>
        </section>
      ))}
    </article>
  )
}

export default AttractionPlan
