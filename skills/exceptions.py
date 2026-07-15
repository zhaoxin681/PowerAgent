"""Exceptions raised by the PowerAgent skill system."""

from __future__ import annotations

# 基类异常
class SkillError(Exception):
    """Base exception for all skill-layer failures."""

    default_code = "skill_error"

    def __init__(
        self,
        message: str,
        *,
        skill_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.skill_name = skill_name
        self.code = self.default_code
    # 异常打印格式，方便排查
    def __str__(self) -> str:
        if self.skill_name:
            return f"[{self.code}] skill={self.skill_name}: {self.message}"
        return f"[{self.code}] {self.message}"


# 三个子类：对应技能调用生命周期三个阶段
class SkillInputValidationError(SkillError):
    """Raised when raw arguments do not satisfy the skill input contract."""

    default_code = "skill_input_validation_error"


class SkillExecutionError(SkillError):
    """Raised when the skill fails while executing its business logic."""

    default_code = "skill_execution_error"


class SkillOutputValidationError(SkillError):
    """Raised when a skill result does not satisfy its output contract."""

    default_code = "skill_output_validation_error"