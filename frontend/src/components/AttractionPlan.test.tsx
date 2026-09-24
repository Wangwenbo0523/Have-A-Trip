import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { Plan } from "../types"
import AttractionPlan, { groupByDay } from "./AttractionPlan"

const plan: Plan = {
  slug: "west-lake-plan",
  title: "西湖两日慢游",
  days: 2,
  budget_level: "low",
  best_for: "第一次到杭州",
  summary: "第一天环湖, 第二天上山。",
  steps: [
    { day_no: 2, sort: 1, title: "北高峰", detail: "坐索道上山。", duration_hours: 3, tip: null },
    { day_no: 1, sort: 2, title: "苏堤", detail: "傍晚走苏堤。", duration_hours: 1.5, tip: "日落最好" },
    { day_no: 1, sort: 1, title: "断桥", detail: "从断桥起步。", duration_hours: 1, tip: null },
  ],
}

describe("AttractionPlan", () => {
  it("按天分组, 组内按 sort 升序", () => {
    const groups = groupByDay(plan.steps)
    expect(groups.map(([day]) => day)).toEqual([1, 2])
    expect(groups[0][1].map((step) => step.title)).toEqual(["断桥", "苏堤"])
  })

  it("渲染方案标题、天数、花费档次与适合人群", () => {
    render(<AttractionPlan plan={plan} />)
    expect(screen.getByRole("heading", { name: "西湖两日慢游", level: 4 })).toBeInTheDocument()
    expect(screen.getByText("2 天")).toBeInTheDocument()
    expect(screen.getByText("经济档")).toBeInTheDocument()
    expect(screen.getByText("适合第一次到杭州")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "第 1 天", level: 5 })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "第 2 天", level: 5 })).toBeInTheDocument()
  })

  it("时长与小贴士按口径显示, 没有就不渲染", () => {
    render(<AttractionPlan plan={plan} />)
    expect(screen.getByText("约 1.5 小时")).toBeInTheDocument()
    expect(screen.getByText("小贴士: 日落最好")).toBeInTheDocument()
    expect(screen.getAllByText(/^约 .* 小时$/)).toHaveLength(3)
    expect(screen.getAllByText(/^小贴士/)).toHaveLength(1)
  })
})
