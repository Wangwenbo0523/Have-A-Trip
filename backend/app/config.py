"""配置。全部可用环境变量覆盖, 见 .env.example。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# 读哪一份 .env。默认 ".env"(相对启动时的 cwd); 环境变量给空串 = 一份都不读。
#
# 用例把这个开关设成空(见 tests/conftest.py): 开发机上按 README 配好 backend/.env 之后,
# 「什么都没配」那几条用例会从 .env 里拿到模型名与 key —— 本地红、CI 绿, 这类
# 只有一台机器能复现的红最难查。配置本身没错, 错的是用例不该读开发机的 .env。
_ENV_FILE = os.getenv("SETTINGS_ENV_FILE", ".env") or None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # 生产目标是 PostgreSQL; 测试会把它换成 SQLite 内存库
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/attraction_atlas"
    )
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    default_page_size: int = 20
    max_page_size: int = 100

    # 推荐结果的短 TTL 内存缓存(S2 用)。先不引 Redis。
    rec_cache_ttl_seconds: int = 60
    rec_default_limit: int = 10
    rec_max_limit: int = 50

    # ---------------------------------------------------------------- AI / 大模型
    #
    # 默认 none: 什么都不配时应用照常跑, AI 入口显示为不可用(见 app/llm/client.py)。
    # provider 取值: none | ollama | deepseek | openai | custom
    #   ollama              本地, 数据不出本机, 不需要 key
    #   deepseek / openai   云端, 需要 llm_api_key
    #   custom              任何 OpenAI 兼容网关, base_url 与 model 自己给
    # base_url 与 model 留空时用 provider 预设值。密钥只从环境变量来, 绝不写进仓库。
    llm_provider: str = "none"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    # 模型调用超时: 宁可降级成关键词检索, 也不让用户在页面上干等
    llm_timeout_seconds: float = 20.0
    # 每次请求的输出上限 —— 我们要的是几个查询条件, 不是文章
    llm_max_tokens: int = 400
    # 同一句话的解析结果缓存(秒), 0 表示不缓存
    llm_cache_ttl_seconds: int = 300
    # 采样种子。temperature=0 只说明"别自由发挥", 并不等于可复现 —— ollama 每次请求
    # 自己抽种子, 同一句话偶尔会解析出不同的条件集。要复现就得把种子也固定下来。
    # 给负数表示不带这个字段(个别自建网关不认未知字段, 会回 400)。
    llm_seed: int = 42

    # ------------------------------------------------------------ AI / 向量检索
    #
    # 与对话模型分开配置: 摘要模型与向量模型常常不是同一家, 也可能一个走云、一个走本机。
    # 默认 inherit: 跟随 llm_provider —— 只配了 LLM_* 的部署, 向量默认用同一家。
    # 取值: inherit | none | ollama | deepseek | openai | custom
    embedding_provider: str = "inherit"
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    # 0 = 自动: 以服务商返回的维度为准, 并把它写进 attraction_embedding.dim。
    # 给正数则强校验, 服务商维度不符时直接报错 —— 部署方想锁死维度时用。
    embedding_dim: int = 0
    embedding_timeout_seconds: float = 20.0
    # 一次请求塞多少条文本。批次太大有的网关会回 413
    embedding_batch_size: int = 16
    # 同一段文本的向量缓存(秒), 0 表示不缓存
    embedding_cache_ttl_seconds: int = 300

    semantic_default_limit: int = 10
    semantic_max_limit: int = 50
    # 混合相似度里向量分与结构化分的权重。与 recommend/content_based.py 的权重一样,
    # 集中放这里便于调参。两者都会被归一化到 0..1 再加权。
    semantic_vector_weight: float = 0.7
    semantic_structured_weight: float = 0.3

    # ---------------------------------------------------------------- 行程生成
    #
    # 行程是项目里第一个按次计费的能力, 所以限额与预算不是可选项, 见 app/quota.py。
    trip_days_min: int = 1
    trip_days_max: int = 14
    # 每个 owner 每天能提交几次。0 表示不限(只建议本地开发时这么配)
    trip_daily_limit: int = 5
    # 所有 owner 合计每天能烧多少 token, 超了新请求直接拒。0 表示不限
    trip_global_daily_token_budget: int = 200_000
    # 交给模型的候选景点条数。这是成本的主要旋钮
    trip_candidate_limit: int = 40
    trip_max_items_per_day: int = 6
    # 生成时的输出上限 —— 行程是结构化长文本, 不能用解析意图那个 400
    trip_max_tokens: int = 2000
    # 行程生成的调用超时。比解析意图长: 输出是一整份结构化长文本
    trip_timeout_seconds: float = 60.0
    # 前端轮询上限。写进响应, 让前端据此停轮询, 而不是各写各的超时
    trip_poll_max_seconds: int = 90
    # generating 状态超过这么久没心跳, 视为进程已死, 允许被回收
    trip_stale_after_seconds: int = 180
    trip_request_max_chars: int = 300
    # 输出不合法时的重试次数。模型偶尔会漏排某一天(例如要 3 天却只给第 3 天), 而
    # validator 对这种输出是**整份拒掉** —— 直接判失败对用户不公平, 带上失败原因
    # 再要一次通常就对了。0 表示不重试
    trip_generate_retries: int = 1

    # ------------------------------------------------------------ 按位置推荐
    #
    # 首页「出去走走」按 IP 猜你在哪儿, 把附近的景点排在前面 —— 只到城市级: 库里的
    # lat/lon 全是 NULL(见 db/README.md 的数据口径), 算不出公里数, 所以「近」只能是
    # **同城 -> 同省 -> 全国**这个层级。
    #
    # 默认关闭(GEO_IP_PROVIDER=none): 不配就一个外部请求都不发, /attractions/nearby
    # 直接退回全国随机, 并在响应里如实标 scope=nation。与 LLM_PROVIDER 同一思路 ——
    # 不配就不连外网。取值: none | ipapi | custom
    geo_ip_provider: str = "none"
    # custom 必填、ipapi 留空用预设。支持 {ip} 占位, 没有就拼在路径末尾(TLS 与否由地址决定)。
    # 取值字段名固定为 city / regionName(或 region) / countryCode, 不为一堆写法各加一条配置
    geo_ip_base_url: str = ""
    # 需要鉴权的服务, 带成 Authorization: Bearer <key>
    geo_ip_api_key: str = ""
    # 认位置是首页的锦上添花: 宁可超时退回随机, 也不让它拖慢首页
    geo_ip_timeout_seconds: float = 1.5
    # 反代后面才打开(GEO_TRUST_FORWARDED_FOR)。默认不信 X-Forwarded-For —— 那个头谁都
    # 能写, 信了就等于让伪造的头把所有人指到同一个城市
    geo_trust_forwarded_for: bool = False

    # ------------------------------------------------------------ 静态站点(单进程)
    #
    # 把 frontend/dist 挂在 API 进程上, 一个进程 = 整个应用。默认关闭: 生产形态是
    # nginx 托 dist、API 单独跑(见 docs/DEPLOY.md 第四节), 挂在这里只是为了「本机双击
    # 即用」不用装 nginx —— 与 GEO_IP_PROVIDER / LLM_PROVIDER 同一思路, 不配就不改变
    # 现有行为。
    #
    # 开了但没 build 过时**不报错也不挂空目录**: / 仍然给 API 自述, 免得界面上出现一个
    # 空白的 404。scripts/damo-app.ps1 会先确认 dist 在。
    serve_frontend: bool = False
    # 留空 = 仓库里的 frontend/dist(按本文件位置算, 与启动时的 cwd 无关)
    frontend_dist: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def frontend_dist_path(self) -> Path:
        """前端产物目录。相对路径按 cwd 解, 空值按仓库位置解。"""
        if self.frontend_dist.strip():
            return Path(self.frontend_dist).expanduser().resolve()
        return Path(__file__).resolve().parents[2] / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
