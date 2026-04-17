from dataclasses import dataclass, field
from typing import Any, Optional, Union, Callable


@dataclass
class ConfigSimulation:
    start: float = 0.0
    end: float = 10.0
    strategy: str = "edf"
    num_processors: int = 1
    params: dict = field(default_factory=dict)


@dataclass
class ConfigTask:
    name: str
    execution_time: float
    period: Optional[float] = None
    deadline: Optional[float] = None
    priority: int = 0
    arrival_time: float = 0.0
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
