"""PowerAgent Skill注册、发现和统一调用机制。形成一个统一的注册->查找->调用->导出工具Schema的管理层"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from agent_core.tool_schema import build_tool_schema
from skills import BaseSkill, SkillContext, SkillDefinition


class SkillRegistryError(Exception):
    """Skill注册表相关异常的基类。"""

    default_code = "skill_registry_error"

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

    def __str__(self) -> str:
        if self.skill_name:
            return (
                f"[{self.code}] skill={self.skill_name}: "
                f"{self.message}"
            )

        return f"[{self.code}] {self.message}"


class DuplicateSkillError(SkillRegistryError):
    """注册同名Skill且未允许覆盖。"""

    default_code = "duplicate_skill_error"


class SkillNotFoundError(SkillRegistryError):
    """根据名称未找到Skill。"""

    default_code = "skill_not_found_error"


class InvalidSkillDefinitionError(SkillRegistryError):
    """尝试注册的对象不是合法Skill。"""

    default_code = "invalid_skill_definition_error"


class SkillRegistry:
    """集中管理系统中可复用的Skill。

    Registry只负责注册、查找和调用，不负责：
    1. 决定应该调用哪个Skill；
    2. 解析大模型原始响应；
    3. 实现具体业务逻辑；
    4. 处理真实API请求。
    """

    # 内部存储结构
    def __init__(self) -> None:
        """创建空的Skill注册表。"""

        self._skills: dict[str, BaseSkill[Any, Any]] = {}  # 技能名->技能实例

    # 注册一个Skill
    def register(
        self,
        skill: BaseSkill[Any, Any],
        *,
        overwrite: bool = False,
    ) -> None:
        """注册一个Skill。

        Args:
            skill:
                BaseSkill实例。
            overwrite:
                是否允许显式覆盖已有同名Skill。

        Raises:
            InvalidSkillDefinitionError:
                注册对象不是BaseSkill实例。
            DuplicateSkillError:
                已存在同名Skill且未允许覆盖。
        """

        if not isinstance(skill, BaseSkill):
            raise InvalidSkillDefinitionError(
                "Only BaseSkill instances can be registered."
            )

        skill_name = skill.definition.name

        if skill_name in self._skills and not overwrite:
            raise DuplicateSkillError(
                "A skill with the same name is already registered.",
                skill_name=skill_name,
            )

        self._skills[skill_name] = skill

    # 按精确名称查找
    def get(self, name: str) -> BaseSkill[Any, Any]:
        """按照精确名称获取Skill。

        不执行大小写转换、别名匹配或模糊匹配，避免模型调用到
        非预期工具。
        """

        try:
            return self._skills[name]
        except KeyError as exc:
            raise SkillNotFoundError(
                "The requested skill is not registered.",
                skill_name=name,
            ) from exc

    # 列出所有已注册技能的元数据，tuple为不可变序列（防止意外修改）
    def list_skills(self) -> tuple[SkillDefinition, ...]:
        """按照Skill名称排序并返回不可变元数据序列。"""

        return tuple(
            self._skills[name].definition
            for name in sorted(self._skills)
        )

    # 统一调用入口
    def invoke(
        self,
        name: str,
        arguments: Mapping[str, Any] | BaseModel,
        context: SkillContext | Mapping[str, Any] | None = None,
    ) -> BaseModel:
        """根据名称调用Skill统一入口。

        Registry不会绕过BaseSkill.run，因此输入、上下文和输出
        仍然会经过Pydantic校验。
        """

        skill = self.get(name)

        return skill.run(
            arguments=arguments,
            context=context,
        )

    # 批量导出给LLM用的工具Schema
    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """生成全部已注册Skill的Tool Schema。

        按名称排序可以保证测试、日志和评测结果稳定。
        """

        return [
            build_tool_schema(self._skills[name])
            for name in sorted(self._skills)
        ]

    def __contains__(self, name: object) -> bool:
        """支持使用'in'判断Skill是否存在。"""

        return name in self._skills

    def __len__(self) -> int:
        """返回当前注册的Skill数量。"""

        return len(self._skills)