import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { askAboutAttraction, fetchAIStatus } from "../api/client"
import type { AIAskResult, AIStatus } from "../types"
import AiAskBox from "./AiAskBox"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchAIStatus: vi.fn(), askAboutAttraction: vi.fn() }
})

const mockedStatus = vi.mocked(fetchAIStatus)
const mockedAsk = vi.mocked(askAboutAttraction)

const available: AIStatus = {
  available: true,
  provider: "ollama",
  model: "qwen2.5:7b-instruct",
  disclaimer: "结果全部来自本站景点档案, AI 只参与理解你这句需求。",
}

const result = (overrides: Partial<AIAskResult> = {}): AIAskResult => ({
  slug: "west-lake",
  question: "要逛多久?",
  grounded: true,
  degraded: false,
  model: "qwen2.5:7b-instruct",
  answer: "建议游览 4 小时, 目前免票。",
  note: "",
  cited: ["suggested_hours"],
  dropped: [],
  disclaimer: "答案只依据本站景点档案里的字段; 档案里没有的信息一律不作答。",
  ...overrides,
})

const renderBox = () =>
  render(<AiAskBox slug="west-lake" name="西湖" />)

beforeEach(() => {
  mockedStatus.mockReset()
  mockedAsk.mockReset()
})

describe("AiAskBox", () => {
  it("后端说不可用时整个区块不渲染", async () => {
    mockedStatus.mockResolvedValue({ available: false, provider: "none", model: null, disclaimer: "" })
    renderBox()
    await waitFor(() => expect(mockedStatus).toHaveBeenCalled())
    expect(screen.queryByLabelText("就这个景点问一句")).not.toBeInTheDocument()
    expect(screen.queryByText("问一句")).not.toBeInTheDocument()
  })

  it("状态接口失败也当作不可用", async () => {
    mockedStatus.mockRejectedValue(new Error("连不上后端"))
    renderBox()
    await waitFor(() => expect(mockedStatus).toHaveBeenCalled())
    expect(screen.queryByLabelText("就这个景点问一句")).not.toBeInTheDocument()
  })

  it("可用时给出建议问题, 点一下就填进输入框", async () => {
    mockedStatus.mockResolvedValue(available)
    renderBox()
    const input = await screen.findByLabelText("就这个景点问一句")

    await userEvent.click(screen.getByRole("button", { name: "要逛多久?" }))
    expect(input).toHaveValue("要逛多久?")
  })

  it("提交后显示答案与免责声明", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedAsk.mockResolvedValue(result())
    renderBox()

    await userEvent.type(await screen.findByLabelText("就这个景点问一句"), "要逛多久?")
    await userEvent.click(screen.getByRole("button", { name: "问问看" }))

    expect(mockedAsk).toHaveBeenCalledWith("west-lake", "要逛多久?")
    expect(await screen.findByText("建议游览 4 小时, 目前免票。")).toBeInTheDocument()
    expect(screen.getByText(result().disclaimer)).toBeInTheDocument()
  })

  it("降级时把「这句话不是模型写的」说出来", async () => {
    // 未配置模型时后端返回 200 + degraded=true, 答案换成档案摘录
    mockedStatus.mockResolvedValue(available)
    mockedAsk.mockResolvedValue(
      result({
        grounded: false,
        degraded: true,
        model: null,
        answer: "档案里没有能直接回答这个问题的内容。现有信息: 建议游览 4 小时。",
        note: "未配置模型, 下面是档案里的现成信息。",
      }),
    )
    renderBox()

    await userEvent.type(await screen.findByLabelText("就这个景点问一句"), "要逛多久?")
    await userEvent.click(screen.getByRole("button", { name: "问问看" }))

    expect(await screen.findByText("未配置模型, 下面是档案里的现成信息。")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("请求失败显示错误态", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedAsk.mockRejectedValue(new Error("连不上后端"))
    renderBox()

    await userEvent.type(await screen.findByLabelText("就这个景点问一句"), "要逛多久?")
    await userEvent.click(screen.getByRole("button", { name: "问问看" }))

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("问不出来")
    expect(alert).toHaveTextContent("连不上后端")
  })

  it("清除后回到建议问题", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedAsk.mockResolvedValue(result())
    renderBox()

    await userEvent.type(await screen.findByLabelText("就这个景点问一句"), "要逛多久?")
    await userEvent.click(screen.getByRole("button", { name: "问问看" }))
    await screen.findByText(result().answer)

    await userEvent.click(screen.getByRole("button", { name: "清除" }))
    expect(screen.queryByText(result().answer)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "什么季节去最好?" })).toBeInTheDocument()
  })

  it("空输入不发起请求", async () => {
    mockedStatus.mockResolvedValue(available)
    renderBox()
    const button = await screen.findByRole("button", { name: "问问看" })
    expect(button).toBeDisabled()
    expect(mockedAsk).not.toHaveBeenCalled()
  })
})