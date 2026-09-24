# 贡献指引

## 为什么要有这份文档

项目当前开源，但**保留将来闭源的可能**。开源转闭源最常见的翻车点是：项目里已经有外部贡献者的代码，
闭源时必须征得每一位贡献者同意，否则无法执行。

所以从第一天起就要把版权约定清楚。这不是形式主义，是保住退路。

## 一、必须签 DCO（Developer Certificate of Origin）

每个 commit 都要带 sign-off：

```bash
git commit -s -m "feat: 景点详情页"
```

这会在 commit message 末尾加上：

```
Signed-off-by: 你的名字 <you@example.com>
```

含义是你声明：这段代码是你写的，或你有权以本项目许可证提交它。用真名或稳定的常用 ID。

CI 会校验 PR 的每个 commit 是否带 sign-off。

## 二、许可证红线（PR 会被直接拒绝）

**禁止引入任何 copyleft 或非商用许可的代码**：

- 禁止：GPL-2.0 / GPL-3.0 / AGPL-3.0（AGPL 尤其危险，提供网络服务也触发开源义务）
- 禁止：SSPL、BUSL、CC-BY-NC
- 禁止：从无 LICENSE 的仓库复制粘贴代码（默认保留所有权利，等于没有授权）
- 谨慎：LGPL / MPL / EPL——需在 PR 里说明用法并等维护者确认

提 PR 前请自己先跑：

```bash
python scripts/license_gate.py --strict
```

**特别注意**：网上大量中文「旅游推荐系统」仓库没有许可证（或被标注为毕设源码售卖）。看可以，
一行代码都不要抄进来。

## 三、数据不能随便加

景点数据同样受许可约束。新增数据源必须同时更新 `docs/LICENSE-AUDIT.md`，注明：

- 来源与获取方式
- 许可证类型
- **是否带相同方式共享（share-alike）义务**——OSM 的 ODbL、CC BY-SA 都有，会往你的数据库传染

不接受来源不明的抓取数据。

## 四、代码约定

- 前端：沿用 `frontend/` 现有风格（React + TS + 函数组件 + `src/styles/` 下的 CSS）
- 后端：Python 3.13，FastAPI + SQLAlchemy，类型标注齐全
- **不要在 API 进程里 `import recbole`**——见 `docs/BASES.md` 的环境隔离说明
- 提 PR 前跑测试与卡口