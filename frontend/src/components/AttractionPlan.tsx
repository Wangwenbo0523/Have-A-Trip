import React from "react"

import type { Plan, PlanBudgetLevel, PlanStep } from "../types"
import "../styles/AttractionPlan.css"

/** 花费档次的中文说法。只给档次不给金额 —— 价格是易变信息, 见 db/README.md。 */
const BUDGET_LABELS: Record<PlanBudgetLevel, string> = {
  free: "几乎不花钱",
  low: "经济档",
  mid: "舒适档",
  high: "高阶档",
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

const PlanStepItem = ({ step }: { step: PlanStep }) => (
  <li className="plan__step">
    <p className="plan__stepTitle">
      {step.title}
      {step.duration_hours === null || step.duration_hours === undefined ? null : (
        <span className="plan__duration">约 {step.duration_hours} 小时</span>
      )}
    </p>
    <p className="plan__detail">{step.detail}</p>
    {step.tip ? <p className="plan__tip">小贴士: {step.tip}</p> : null}
  </li>
)

/** 一个景点的一份游玩方案。日期分组渲染, 同一天内按 sort 升序。 */
const AttractionPlan = ({ plan }: { plan: Plan }) => (
  <article className="plan">
    <header className="plan__head">
      <h4 className="plan__title">{plan.title}</h4>
      <ul className="plan__meta">
        <li>{plan.days} 天</li>
        {plan.budget_level ? <li>{BUDGET_LABELS[plan.budget_level]}</li> : null}
        {plan.best_for ? <li>适合{plan.best_for}</li> : null}
      </ul>
    </header>

    <p className="plan__summary">{plan.summary}</p>

    {groupByDay(plan.steps).map(([day, steps]) => (
      <section className="plan__day" key={day}>
        <h5 className="plan__dayTitle">第 {day} 天</h5>
        <ol className="plan__steps">
          {steps.map((step) => (
            <PlanStepItem key={`${step.day_no}-${step.sort}`} step={step} />
          ))}
        </ol>
      </section>
    ))}
  </article>
)

export default AttractionPlan
