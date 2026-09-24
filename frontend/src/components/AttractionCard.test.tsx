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
  country_code: "CN",
  a_level: null,
  heritage: null,
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

  it("有 A 级时显示等级徽章", () => {
    renderCard({ ...attraction, a_level: "5A" })
    expect(screen.getByText("5A")).toHaveAttribute("title", "国家 5A 级旅游景区")
  })

  it("没有 A 级但列入世界遗产时显示遗产徽章", () => {
    renderCard({ ...attraction, heritage: "cultural" })
    const badge = screen.getByText("文化遗产")
    expect(badge).toHaveAttribute("title", "世界文化遗产")
  })

  it("两者都未核实时不渲染徽章", () => {
    renderCard(attraction)
    expect(screen.queryByText("5A")).not.toBeInTheDocument()
    expect(screen.queryByText("文化遗产")).not.toBeInTheDocument()
  })

  it("境外景点不硬写人民币符号", () => {
    renderCard({ ...attraction, country_code: "US", ticket_price: 25 })
    expect(screen.getByText("需购票")).toBeInTheDocument()
    expect(screen.queryByText("¥25")).not.toBeInTheDocument()
  })

  it("整张卡片链到详情页", () => {
    renderCard(attraction)
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "/attraction/west-lake")
  })
})