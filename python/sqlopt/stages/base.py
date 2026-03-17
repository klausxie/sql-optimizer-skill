"""Stage base classes"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path


@dataclass
class StageContext:
    """阶段执行上下文"""
    run_id: str
    config: dict = field(default_factory=dict)
    data_dir: Path = field(default_factory=Path)
    cache_dir: Path = field(default_factory=Path)
    metadata: dict = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)
    
    def set(self, key: str, value: Any):
        self.metadata[key] = value


@dataclass
class StageResult:
    """阶段执行结果"""
    success: bool
    output_files: list[Path] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Stage(ABC):
    """阶段基类"""
    
    name: str = "base"
    version: str = "1.0.0"
    dependencies: list[str] = []
    
    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        """执行阶段"""
        pass
    
    @abstractmethod
    def get_input_contracts(self) -> list[str]:
        """输入契约"""
        pass
    
    @abstractmethod
    def get_output_contracts(self) -> list[str]:
        """输出契约"""
        pass
    
    def validate_input(self, context: StageContext) -> bool:
        """验证输入"""
        return True
    
    def cleanup(self, context: StageContext):
        """清理资源"""
        pass
