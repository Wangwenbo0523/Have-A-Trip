import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { describe, expect, it, vi } from "vitest"

import type { Attraction } from "../types"
import AttractionPicker from "./AttractionPicker"

const item = (id: number, slug: string, name: string, nameEn: string | null = null): Attraction => ({
  id,
  slug,
  name,
  name_en: nameEn,
  summary: null,
  category: { slug: "nature", name: "自然风光" },
  city: null,
  province: null,
  tags: [],
  cover_image: null,
  rating_avg: 0,
  rating_count: 0,
  ticket_price: null,
  suggested_hours: null,
  country_code: "CN",
  a_level: null,
  heritage: null,
})

const WEST_LAKE = item(1, "west-lake", "西湖", "West Lake")
const PALACE = item(2, "palace-museum", "故宫博物院", "Palace Museum")
const TERRACOTTA = item(3, "terracotta-army", "秦始皇兵马俑")

const OPTIONS = [WEST_LAKE, PALACE, TERRACOTTA]

const renderPicker = (value = "west-lake") => {
  const onChange = vi.fn()
  render(
    <AttractionPicker id="pick" label="景点 A" value={value} options={OPTIONS} onChange={onChange} />,
  )
  return { onChange, input: screen.getByLabelText("景点 A") as HTMLInputElement }
}

/** 受控包装: 选完之后 slug 会写回, 用来复现「选完接着打字 / 再点一下」这两个只有受控才有的场景。 */
const ControlledPicker = () => {
  const [slug, setSlug] = useState("west-lake")
  return (
    <AttractionPicker id="pick" label="景点 A" value={slug} options={OPTIONS} onChange={setSlug} />
  )
}

describe("AttractionPicker", () => {
  it("没展开时不铺列表, 输入框显示当前选中的名字", () => {
    const { input } = renderPicker()

    expect(input).toHaveValue("西湖")
    expect(input).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
  })

  it("聚焦即进搜索态: 输入框清空, 候选铺全", async () => {
    const { input } = renderPicker()
    await userEvent.click(input)

    expect(input).toHaveValue("")
    expect(input).toHaveAttribute("aria-expanded", "true")
    expect(input.getAttribute("aria-controls")).toBe(screen.getByRole("listbox").id)
    expect(screen.getAllByRole("option")).toHaveLength(3)
  })

  it("输入即筛 —— 聚焦清空之后打进来的字是干净的, 不会跟旧名字拼在一起", async () => {
    const { input } = renderPicker()
    await userEvent.click(input)
    await userEvent.type(input, "故宫")

    const left = screen.getAllByRole("option")
    expect(left).toHaveLength(1)
    expect(left[0]).toHaveTextContent("故宫博物院")
  })

  it("中文界面下按英文名也搜得到", async () => {
    const { input } = renderPicker()
    await userEvent.click(input)
    await userEvent.type(input, "palace")

    const left = screen.getAllByRole("option")
    expect(left).toHaveLength(1)
    expect(left[0]).toHaveTextContent("故宫博物院")
  })

  it("上下键移动高亮, 回车落定", async () => {
    const { input, onChange } = renderPicker()
    await userEvent.click(input)

    await userEvent.keyboard("{ArrowDown}{Enter}")

    expect(onChange).toHaveBeenCalledWith("palace-museum")
  })

  it("高亮是循环的: 在第一条往上走回到最后一条", async () => {
    const { input, onChange } = renderPicker()
    await userEvent.click(input)

    await userEvent.keyboard("{ArrowUp}{Enter}")

    expect(onChange).toHaveBeenCalledWith("terracotta-army")
  })

  it("手打的名字不会变成值 —— 只有从列表里选中才写回 slug", async () => {
    const { input, onChange } = renderPicker()
    await userEvent.click(input)
    await userEvent.type(input, "秦")
    expect(onChange).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("option", { name: "秦始皇兵马俑" }))
    expect(onChange).toHaveBeenCalledWith("terracotta-army")
  })

  it("Esc 放弃这次输入, 名字回到当前选中的那个, 也不改值", async () => {
    const { input, onChange } = renderPicker()
    await userEvent.click(input)
    await userEvent.type(input, "故宫")
    await userEvent.keyboard("{Escape}")

    expect(input).toHaveValue("西湖")
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
  })

  it("没有匹配时说明一句, 不当成选项", async () => {
    const { input } = renderPicker()
    await userEvent.click(input)
    await userEvent.type(input, "没有这个地方")

    expect(screen.queryAllByRole("option")).toHaveLength(0)
    expect(screen.getByText("没有匹配的景点")).toBeInTheDocument()
  })

  it("展开时高亮落在当前选中的那一条上, 并标出 aria-selected", async () => {
    const { input } = renderPicker("palace-museum")
    await userEvent.click(input)

    expect(screen.getByRole("option", { name: /故宫博物院/ })).toHaveAttribute(
      "aria-selected",
      "true",
    )
    expect(input).toHaveAttribute("aria-activedescendant", "pick-option-1")
  })

  it("选完之后接着打字: 只认新敲进去的那个字, 不拼在旧名字后面", async () => {
    render(<ControlledPicker />)
    const input = screen.getByLabelText("景点 A") as HTMLInputElement

    await userEvent.click(input)
    await userEvent.click(screen.getByRole("option", { name: "秦始皇兵马俑" }))
    expect(input).toHaveValue("秦始皇兵马俑")

    // 焦点从头到尾没离开输入框, 所以这一下不会再有 focus 事件; 光标停在名字末尾,
    // 真实浏览器里会打成 "秦始皇兵马俑西" —— 组件该只认后面那个字。
    // skipClick 就是为了造出这个「不点、直接打」的场景(userEvent.type 默认会先点一下)。
    await userEvent.type(input, "西", { skipClick: true })

    const left = screen.getAllByRole("option")
    expect(left).toHaveLength(1)
    expect(left[0]).toHaveTextContent("西湖")
  })

  it("选完之后再点一下输入框, 列表重新铺开", async () => {
    render(<ControlledPicker />)
    const input = screen.getByLabelText("景点 A") as HTMLInputElement

    await userEvent.click(input)
    await userEvent.click(screen.getByRole("option", { name: "秦始皇兵马俑" }))
    expect(input).toHaveValue("秦始皇兵马俑")
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument()

    // 焦点还在输入框里, 这一下同样不触发 focus; 少了 onClick 里的兜底, 列表就再也叫不回来
    await userEvent.click(input)

    expect(input).toHaveValue("")
    expect(screen.getAllByRole("option")).toHaveLength(3)
  })
})
