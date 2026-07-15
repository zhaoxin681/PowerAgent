"""Base abstraction for reusable PowerAgent skills. 形成一套统一的“输入校验->执行->输出校验”框架"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from skills.exceptions import (
    SkillError,
    SkillExecutionError,
    SkillInputValidationError,
    SkillOutputValidationError,
)
from skills.schemas import SkillContext, SkillDefinition


InputModelT = TypeVar("InputModelT", bound=BaseModel)
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)


class BaseSkill(ABC, Generic[InputModelT, OutputModelT]):
    """Base class for all reusable PowerAgent skills.

    A concrete skill must define stable metadata, an input model, an output
    model, and the deterministic business logic implemented by ``execute``.
    """

    name: str
    description: str
    version: str = "1.0.0"

    input_model: type[InputModelT]
    output_model: type[OutputModelT]

    def __init__(self) -> None:
        """Validate and cache the skill's static definition."""

        self._definition = SkillDefinition(
            name=self.name,
            description=self.description,
            version=self.version,
            input_model_name=self.input_model.__name__,
            output_model_name=self.output_model.__name__,
        )

    # 只读属性
    @property
    def definition(self) -> SkillDefinition:
        """Return immutable metadata describing this skill."""

        return self._definition

    # 核心执行入口（模板方法模式），固定流程，具体业务逻辑交给子类的execute()
    def run(
        self,
        arguments: Mapping[str, Any] | InputModelT,
        context: SkillContext | Mapping[str, Any] | None = None,
    ) -> OutputModelT:
        """Validate input, execute the skill, and validate its output.

        Args:
            arguments:
                Raw dictionary-like arguments or an existing input-model
                instance.
            context:
                Optional invocation context or a dictionary that can be
                validated as ``SkillContext``.

        Returns:
            A validated instance of the skill's output model.

        Raises:
            SkillInputValidationError:
                If the context or business arguments violate their contracts.
            SkillExecutionError:
                If the concrete skill fails during business execution.
            SkillOutputValidationError:
                If the concrete skill returns an invalid result.
        """

        validated_context = self._validate_context(context) # 把传入的context统一校验/转换成合法的skillcontext
        validated_input = self._validate_input(arguments) # 把arguments校验成input_model实例
        # 调用子类实现的抽象方法，拿到原始结果
        try:
            raw_output = self.execute(
                skill_input=validated_input,
                context=validated_context,
            )
        except SkillError:
            # Preserve an explicit skill-layer exception raised by a
            # concrete implementation.
            raise
        except Exception as exc:
            # Do not expose the original exception message because it may
            # contain sensitive business data or implementation details.
            raise SkillExecutionError(
                "The skill failed during business execution.",
                skill_name=self.name,
            ) from exc

        return self._validate_output(raw_output) # 把execute()返回的原始结果校验成output_model实例，最终返回

    # 三个私有校验方法，结构都为：调用Pydantic的model_validate->捕获ValidationError->转换成对应的自定义异常
    def _validate_context(
        self,
        context: SkillContext | Mapping[str, Any] | None,
    ) -> SkillContext:
        """Validate or create the invocation context."""

        context_data: SkillContext | Mapping[str, Any]

        if context is None:
            context_data = {}
        else:
            context_data = context

        try:
            return SkillContext.model_validate(context_data)
        except ValidationError as exc:
            raise SkillInputValidationError(
                (
                    "Skill context validation failed with "
                    f"{exc.error_count()} error(s)."
                ),
                skill_name=self.name,
            ) from exc

    def _validate_input(
        self,
        arguments: Mapping[str, Any] | InputModelT,
    ) -> InputModelT:
        """Validate raw business arguments against the input model."""

        try:
            return self.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise SkillInputValidationError(
                (
                    "Skill input validation failed with "
                    f"{exc.error_count()} error(s)."
                ),
                skill_name=self.name,
            ) from exc

    def _validate_output(self, raw_output: Any) -> OutputModelT:
        """Validate the business result against the output model."""

        try:
            return self.output_model.model_validate(raw_output)
        except ValidationError as exc:
            raise SkillOutputValidationError(
                (
                    "Skill output validation failed with "
                    f"{exc.error_count()} error(s)."
                ),
                skill_name=self.name,
            ) from exc

    # 抽象方法：每个具体技能唯一需要实现的方法
    @abstractmethod
    def execute(
        self,
        skill_input: InputModelT,
        context: SkillContext,
    ) -> OutputModelT | Mapping[str, Any]:
        """Implement deterministic business logic for a concrete skill."""