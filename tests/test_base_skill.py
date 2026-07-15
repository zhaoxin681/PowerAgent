"""Tests for the reusable BaseSkill abstraction."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from skills import (
    BaseSkill,
    SkillContext,
    SkillExecutionError,
    SkillInputValidationError,
    SkillOutputValidationError,
)

# “回声”契约输入：非空字符串text
class EchoInput(BaseModel):
    """Input contract used by the test skill."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)

# “回声”契约输出：echoed_text和trace_id
class EchoOutput(BaseModel):
    """Output contract used by the test skill."""

    model_config = ConfigDict(extra="forbid")

    echoed_text: str
    trace_id: str

"""
测试技能，分别模拟不同场景
"""
# 正常路径
class EchoSkill(BaseSkill[EchoInput, EchoOutput]):
    """Minimal valid skill used to verify the happy path."""

    name = "echo"
    description = "Echo validated text for framework testing."

    input_model = EchoInput
    output_model = EchoOutput

    def execute(
        self,
        skill_input: EchoInput,
        context: SkillContext,
    ) -> dict[str, str]:
        return {
            "echoed_text": skill_input.text,
            "trace_id": context.trace_id,
        }

class ModelOutputSkill(BaseSkill[EchoInput, EchoOutput]):
    """Skill that directly returns an output-model instance."""

    name = "model_output"
    description = "Return a validated output model directly."

    input_model = EchoInput
    output_model = EchoOutput

    def execute(
        self,
        skill_input: EchoInput,
        context: SkillContext,
    ) -> EchoOutput:
        return EchoOutput(
            echoed_text=skill_input.text,
            trace_id=context.trace_id,
        )
    
# 无效的技能名字
class InvalidNameSkill(BaseSkill[EchoInput, EchoOutput]):
    """Skill with deliberately invalid static metadata."""

    name = "Invalid-Skill-Name"
    description = "Verify that invalid skill names are rejected."

    input_model = EchoInput
    output_model = EchoOutput

    def execute(
        self,
        skill_input: EchoInput,
        context: SkillContext,
    ) -> EchoOutput:
        return EchoOutput(
            echoed_text=skill_input.text,
            trace_id=context.trace_id,
        )


# 模拟意外的内容异常：普通异常（非SkillError），异常信息包括敏感信息
class ExplodingSkill(BaseSkill[EchoInput, EchoOutput]):
    """Skill that raises an unexpected implementation exception."""

    name = "exploding"
    description = "Raise an exception to test execution error handling."

    input_model = EchoInput
    output_model = EchoOutput

    def execute(
        self,
        skill_input: EchoInput,
        context: SkillContext,
    ) -> EchoOutput:
        raise RuntimeError(
            "internal-path=C:/secret api_key=do-not-expose"
        )

# 模拟输出不合规：漏掉必填字段
class InvalidOutputSkill(BaseSkill[EchoInput, EchoOutput]):
    """Skill that deliberately violates its output contract."""

    name = "invalid_output"
    description = "Return invalid output to test output validation."

    input_model = EchoInput
    output_model = EchoOutput

    def execute(
        self,
        skill_input: EchoInput,
        context: SkillContext,
    ) -> dict[str, Any]:
        return {
            "echoed_text": skill_input.text,
            # trace_id is deliberately omitted.
        }

# 模拟技能主动抛出已声明的业务错误：SkillError，原样透传
class ExplicitSkillErrorSkill(BaseSkill[EchoInput, EchoOutput]):
    """Skill that deliberately raises a skill-layer exception."""

    name = "explicit_error"
    description = "Raise a declared SkillExecutionError."

    input_model = EchoInput
    output_model = EchoOutput

    def execute(
        self,
        skill_input: EchoInput,
        context: SkillContext,
    ) -> EchoOutput:
        raise SkillExecutionError(
            "Declared business failure.",
            skill_name=self.name,
        )

"""
逐个测试用例
"""
# 验证__init__阶段构造的SkillDefinition元数据是完整、正确的
def test_definition_contains_complete_metadata() -> None:
    skill = EchoSkill()

    assert skill.definition.name == "echo"
    assert skill.definition.description
    assert skill.definition.version == "1.0.0"
    assert skill.definition.input_model_name == "EchoInput"
    assert skill.definition.output_model_name == "EchoOutput"

# 验证run()能接受普通字典作为输入，自动校验转换，且返回值确实为Echoutput实例
def test_run_accepts_dictionary_input() -> None:
    skill = EchoSkill()

    result = skill.run(
        {"text": "battery voltage abnormal"},
        context={"trace_id": "trace-001", "source": "unit_test"},
    )

    assert isinstance(result, EchoOutput)
    assert result.echoed_text == "battery voltage abnormal"
    assert result.trace_id == "trace-001"

# 验证arguments传入已经是模型实例的情况也能正常工作
def test_run_accepts_existing_input_model() -> None:
    skill = EchoSkill()
    input_model = EchoInput(text="thermal warning")

    result = skill.run(input_model)

    assert result.echoed_text == "thermal warning"
    assert result.trace_id

# 不传context参数，验证_validate_context会用字典兜底，进而触发SkillContext里trace_id的default_factory不会报错
def test_run_creates_default_context() -> None:
    skill = EchoSkill()

    result = skill.run({"text": "charging analysis"})

    assert result.trace_id
    assert len(result.trace_id) > 0

# 不传必填的text字段，验证输入校验失败时抛出的是SkillInputValidationError，并且异常上正确携带了skill_name和错误码
def test_missing_required_input_field_raises_input_error() -> None:
    skill = EchoSkill()

    with pytest.raises(SkillInputValidationError) as exc_info:
        skill.run({})

    assert exc_info.value.skill_name == "echo"
    assert exc_info.value.code == "skill_input_validation_error"

# 多传未知字段触发SkillInputValidationError
def test_extra_input_field_raises_input_error() -> None:
    skill = EchoSkill()

    with pytest.raises(SkillInputValidationError):
        skill.run(
            {
                "text": "valid text",
                "unknown_field": "not allowed",
            }
        )

# id长度最小为1
def test_invalid_context_raises_input_error() -> None:
    skill = EchoSkill()

    with pytest.raises(SkillInputValidationError):
        skill.run(
            {"text": "valid text"},
            context={
                "trace_id": "",
                "source": "unit_test",
            },
        )


def test_unexpected_execution_error_is_wrapped() -> None:
    skill = ExplodingSkill()

    with pytest.raises(SkillExecutionError) as exc_info:
        skill.run({"text": "trigger failure"})

    error_text = str(exc_info.value)

    assert exc_info.value.skill_name == "exploding"
    assert "do-not-expose" not in error_text
    assert "C:/secret" not in error_text

# 安全性测试，原始异常信息不会泄露
def test_invalid_output_raises_output_validation_error() -> None:
    skill = InvalidOutputSkill()

    with pytest.raises(SkillOutputValidationError) as exc_info:
        skill.run({"text": "trigger output failure"})

    assert exc_info.value.skill_name == "invalid_output"
    assert exc_info.value.code == "skill_output_validation_error"

# execute()返回缺字段
def test_explicit_skill_error_is_not_double_wrapped() -> None:
    skill = ExplicitSkillErrorSkill()

    with pytest.raises(SkillExecutionError) as exc_info:
        skill.run({"text": "trigger declared failure"})

    assert exc_info.value.message == "Declared business failure."
    assert exc_info.value.skill_name == "explicit_error"

# 数据模型默认值陷阱
def test_skill_context_metadata_uses_independent_default_dicts() -> None:
    first = SkillContext()
    second = SkillContext()

    first.metadata["case_id"] = "case-001"

    assert first.metadata == {"case_id": "case-001"}
    assert second.metadata == {}
    assert first.metadata is not second.metadata

# 验证execute()可以返回字典，也可以直接返回输出模型
def test_execute_may_return_output_model_instance() -> None:
    skill = ModelOutputSkill()

    result = skill.run(
        {"text": "validated model output"},
        context={"trace_id": "trace-model-output"},
    )

    assert isinstance(result, EchoOutput)
    assert result.echoed_text == "validated model output"
    assert result.trace_id == "trace-model-output"

# 非法skill元数据在初始化阶段立即失败
def test_invalid_skill_definition_is_rejected_at_initialization() -> None:
    with pytest.raises(ValidationError):
        InvalidNameSkill()

# SkillDefinition的字段不能被运行时修改
def test_skill_definition_fields_cannot_be_reassigned() -> None:
    skill = EchoSkill()

    with pytest.raises(ValidationError):
        skill.definition.name = "changed_name"