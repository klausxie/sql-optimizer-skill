"""Stage base classes and contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path


@dataclass
class StageContext:
    """阶段执行上下文

    Attributes:
        run_id: 运行ID
        config: 配置字典
        data_dir: 数据目录路径
        cache_dir: 缓存目录路径
        metadata: 元数据字典
    """

    run_id: str
    config: dict = field(default_factory=dict)
    data_dir: Path = field(default_factory=Path)
    cache_dir: Path = field(default_factory=Path)
    metadata: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """获取元数据值"""
        return self.metadata.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置元数据值"""
        self.metadata[key] = value


@dataclass
class StageResult:
    """阶段执行结果

    Attributes:
        success: 是否成功
        output_files: 输出文件列表
        artifacts: 产物字典
        errors: 错误列表
        warnings: 警告列表
    """

    success: bool
    output_files: list[Path] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Stage(ABC):
    """阶段基类

    所有阶段必须实现以下抽象方法:
    - execute: 执行阶段逻辑
    - get_input_contracts: 返回输入契约列表
    - get_output_contracts: 返回输出契约列表

    可选的钩子方法:
    - validate_input: 验证输入是否有效
    - cleanup: 清理资源
    - can_process: 判断是否能处理该SQL单元
    - on_stage_start: 阶段开始前调用
    - on_stage_end: 阶段结束后调用
    """

    name: str = "base"
    """阶段名称"""

    version: str = "1.0.0"
    """阶段版本"""

    dependencies: list[str] = []
    """依赖阶段列表"""

    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        """执行阶段

        Args:
            context: 阶段执行上下文

        Returns:
            StageResult: 阶段执行结果
        """
        pass

    @abstractmethod
    def get_input_contracts(self) -> list[str]:
        """获取输入契约列表

        Returns:
            list[str]: 输入契约名称列表
        """
        pass

    @abstractmethod
    def get_output_contracts(self) -> list[str]:
        """获取输出契约列表

        Returns:
            list[str]: 输出契约名称列表
        """
        pass

    def validate_input(self, context: StageContext) -> bool:
        """验证输入是否有效

        Args:
            context: 阶段执行上下文

        Returns:
            bool: 输入是否有效，默认为True
        """
        return True

    def cleanup(self, context: StageContext) -> None:
        """清理资源

        Args:
            context: 阶段执行上下文
        """
        pass

    def can_process(self, sql_unit: dict) -> bool:
        """判断是否能处理该SQL单元

        用于动态判断某个SQL单元是否应该由此阶段处理。
        子类可覆盖此方法实现自定义过滤逻辑。

        Args:
            sql_unit: SQL单元字典

        Returns:
            bool: 是否能处理，默认为True
        """
        return True

    def on_stage_start(self, context: StageContext) -> None:
        """阶段开始前钩子

        在execute()被调用之前执行。
        可用于初始化资源、记录日志等。

        Args:
            context: 阶段执行上下文
        """
        pass

    def on_stage_end(self, context: StageContext, result: StageResult) -> None:
        """阶段结束后钩子

        在execute()完成之后执行（无论成功或失败）。
        可用于资源清理、后置处理等。

        Args:
            context: 阶段执行上下文
            result: 阶段执行结果
        """
        pass
