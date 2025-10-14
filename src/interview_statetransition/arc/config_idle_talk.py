from __future__ import annotations
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os, json, yaml
from typing import Optional, Literal


# --- モデル ---
class ModelConfig(BaseModel):
    provider: str = Field(default="openai")  # "openai" or "google"
    name: str = Field(default="gpt-4o-2024-11-20")
    temperature: float = 0.0


class IntervieweeConfig(BaseModel):
    mode: Literal["llm", "human"] = "llm"
    input_file: Optional[str] = None  # human mode only
    wait_human_sec: Optional[int] = 300  # human mode only


class RunConfig(BaseModel):
    wait_time: int = 5
    out_dir: str = "out"


class InterviewConfig(BaseModel):
    max_total_count: int = 40
    min_total_count: int = 34
    estimate_persona: str | None = None
    persona_attribute_candidates: list[str] = []
    slots: dict = {}


class PathsPrompts(BaseModel):
    idle_talk: str
    fill_slots: str
    generate_slots: str
    generate_slots_2: str
    generate_questions: str
    user_simulator: str
    career_topic: str
    end_conversation: str
    estimate_persona: str


class PathsConfig(BaseModel):
    prompts: PathsPrompts
    persona_settings: str
    self_evaluation: str


class AppConfig(BaseSettings):
    # .env からも読み取る（LINE_TOKEN 等）
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig")

    model: ModelConfig = ModelConfig()
    run: RunConfig = RunConfig()
    interview: InterviewConfig = InterviewConfig()
    paths: PathsConfig
    interviewee: IntervieweeConfig = IntervieweeConfig()

    # 任意: YAMLを読み込んで反映するクラスメソッド
    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        with open(path, "r", encoding="utf-8-sig") as f:
            data = yaml.safe_load(f)
        # .env の環境変数も BaseSettings が自動で適用
        return cls(**data)


def load_config(config_path: str | None = None) -> AppConfig:
    # 優先度: default.yaml -> local.yaml(存在すればマージ) -> .env/環境変数
    base = Path(__file__).resolve().parents[2] / "configs"
    default_path = base / "default.yaml"
    cfg = AppConfig.from_yaml(default_path)

    local_path = base / "local.yaml"
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8-sig") as f:
            local = yaml.safe_load(f)
        # shallow だと困る所は手でマージ or OmegaConf に任せる
        cfg = AppConfig(**{**cfg.model_dump(), **local})

    # 明示パスがあればさらに上書き
    if config_path:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            extra = yaml.safe_load(f)
        cfg = AppConfig(**{**cfg.model_dump(), **extra})

    return cfg
