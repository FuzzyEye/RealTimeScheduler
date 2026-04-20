from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ConfigSimulation:
    start: int = 0
    end: int = 10
    strategy: str = "edf"
    params: dict = field(default_factory=dict)


@dataclass
class ConfigTask:
    name: str
    execution_time: int
    period: Optional[int] = None
    deadline: Optional[int] = None
    priority: int = 0
    arrival_time: int = 0
    value: Any = None


@dataclass
class ConfigStrategy:
    name: str
    type: str
    description: str = ""
    selector: Optional[str] = None
    fallback: Optional[str] = None
    priority_key: Optional[str] = None
    condition: Optional[dict] = None
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None
    params: dict = field(default_factory=dict)
    module: Optional[str] = None
    class_name: Optional[str] = None


@dataclass
class Config:
    tasks: list[ConfigTask] = field(default_factory=list)
    simulation: ConfigSimulation = field(default_factory=ConfigSimulation)
    strategies: list[ConfigStrategy] = field(default_factory=list)

