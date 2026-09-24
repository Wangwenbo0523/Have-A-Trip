import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import type { Attraction } from "../types"
import AttractionCard from "./AttractionCard"

const attraction: Attraction = {
  id: 1,
  slug: "west-lake",
  name: "西湖",
  name_en: "West Lake",
  summary: "三面云山一面城的淡水湖。",
  category: { slug: "nature", name: "自然风光" },
  city: "杭州",
  province: "浙江",
  tags: [
    { slug: "free", name: "免票" },
    { slug: "sunrise", name: "日出" },
  ],
  cover_image: null,
  rating_avg: 4.7,
  rating_count: 128,
  ticket_price: 0,
  suggested_hours: 4,
}

const renderCard = (data: Attraction) =>
  render(
    <MemoryRouter>
      <AttractionCard attraction={data} />
    </MemoryRouter>,
  )

describe("AttractionCard", () => {
  it("把名称、英文名、城市省份、分类与标签都渲染出来", () => {
    renderCard(attraction)
    expect(screen.getByRole("heading", { name: "西湖" })).toBeInTheDocument()
    expect(screen.getByText("West Lake")).toBeInTheDocument()
    expect(screen.getByText("杭州 · 浙江")).toBeInTheDocument()
    expect(screen.getByText("自然风光")).toBeInTheDocument()
    expect(screen.getByText("免票")).toBeInTheDocument()
  })

  it("评分与票价按口径显示", () => {
    renderCard(attraction)
    expect(screen.getByText("4.7 分 · 128 人评")).toBeInTheDocument()
    expect(screen.getByText("免费")).toBeInTheDocument()
  })

  it("没有评分时不伪造数字", () => {
    renderCard({ ...attraction, rating_avg: 0, rating_count: 0, ticket_price: 60 })
    expect(screen.getByText("暂无评分")).toBeInTheDocument()
    expect(screen.getByText("¥60")).toBeInTheDocument()
  })

  it("没有配图时用首字占位, 不留破图", () => {
    renderCard(attraction)
    expect(screen.queryByRole("img")).not.toBeInTheDocument()
    expect(screen.getByText("西")).toBeInTheDocument()
  })

  it("有配图时渲染 img", () => {
    renderCard({ ...attraction, cover_image: "/img/west-lake.jpg" })
    expect(screen.getByRole("img", { name: "西湖" })).toHaveAttribute(
      "src",
      "/img/west-lake.jpg",
    )
  })

  it("整张卡片链到详情页", () => {
    renderCard(attraction)
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "/attraction/west-lake")
  })
})