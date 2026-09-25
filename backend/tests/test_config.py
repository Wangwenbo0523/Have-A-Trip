"""配置夹具的可复现性。

开发机上按 README 配好 `backend/.env` 之后, 用例必须仍然跑在「什么都没配」的默认值上 ——
否则同一份代码本地红、CI 绿, 而 CI 绿会让人以为没问题。这两条用例把那条边界钉住。
"""
from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from app import config
from app.config import Settings


def test_local_env_file_does_not_leak_into_settings(monkeypatch, tmp_path):
    """当前工作目录里摆一份 .env, 用例里的 Settings 也不该读它。

    这一条在 conftest 那行开关被删掉时会红: 那时 .env 会被读, llm_provider 变成 deepseek。
    """
    assert config._ENV_FILE is None, "测试进程必须关掉 .env(见 tests/conftest.py)"
    (tmp_path / ".env").write_text(
        "LLM_PROVIDER=deepseek" + chr(10) + "LLM_API_KEY=sk-should-not-be-read" + chr(10),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.llm_provider == "none"
    assert settings.llm_model is None
    assert settings.llm_api_key is None


def test_env_file_switch_can_point_at_another_file(tmp_path):
    """开关不是摆设: 给一个路径就照读, 这是它被关掉之前的正常语义。"""
    env_file = tmp_path / "custom.env"
    env_file.write_text("LLM_PROVIDER=ollama" + chr(10) + "LLM_MODEL=qwen2.5:7b-instruct" + chr(10), encoding="utf-8")

    class WithFile(Settings):
        model_config = SettingsConfigDict(env_file=str(env_file), extra="ignore")

    settings = WithFile()
    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "qwen2.5:7b-instruct"
