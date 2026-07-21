"""研发分析Markdown报告模板。"""

from __future__ import annotations

from workflows.rnd_models import (
    RndAnalysisResult,
    RndAnalysisStatus,
)


class RndReportTemplate:
    """将研发分析结果RndAnalysisResult渲染为稳定的Markdown报告。"""

    def render(
        self,
        result: RndAnalysisResult,
    ) -> str:
        """生成研发问题分析报告。"""

        sections = [
            self._render_header(result),
            self._render_issue(result),
            self._render_known_facts(result),
            self._render_missing_information(result),
            self._render_hypotheses(result),
            self._render_experiments(result),
            self._render_assignments(result),
            self._render_dependencies(result),
            self._render_risks(result),
            self._render_unresolved_items(result),
            self._render_review_status(result),
            self._render_trace(result),
        ]

        return (
            "\n\n".join(sections).rstrip()
            + "\n"
        )

    @staticmethod
    def _render_header(
        result: RndAnalysisResult,
    ) -> str:
        """生成报告标题和总体状态。"""

        lines = [
            "# PowerAgent 研发问题分析报告",
            "",
            f"- 分析状态：`{result.status.value}`",
            (
                "- 总体风险等级："
                f"`{result.overall_risk_level.value}`"
            ),
            (
                "- 是否需要人工复核："
                f"{'是' if result.needs_human_review else '否'}"
            ),
            f"- 分析摘要：{result.summary}",
        ]

        if (
            result.status
            == RndAnalysisStatus.EXECUTION_FAILED
        ):
            lines.append(
                "- 失败原因："
                f"{result.failure_reason or '未提供'}"
            )

        return "\n".join(lines)

    @staticmethod
    def _render_issue(
        result: RndAnalysisResult,
    ) -> str:
        """生成研发问题概述。"""

        issue = result.issue

        symptoms = (
            "、".join(issue.symptoms)
            if issue.symptoms
            else "未提供"
        )

        conditions = [
            (
                f"{item.name}={item.value}"
                f"{item.unit}"
            )
            for item in issue.operating_conditions
        ]

        condition_text = (
            "、".join(conditions)
            if conditions
            else "未提供"
        )

        return "\n".join(
            [
                "## 1. 研发问题概述",
                "",
                f"- 原始问题：{issue.raw_text}",
                f"- 所属子系统：`{issue.subsystem.value}`",
                f"- 任务类型：`{issue.task_type.value}`",
                f"- 问题严重程度：`{issue.severity.value}`",
                f"- 异常现象：{symptoms}",
                f"- 运行条件：{condition_text}",
            ]
        )

    @staticmethod
    def _render_known_facts(
        result: RndAnalysisResult,
    ) -> str:
        """生成已知事实。"""

        lines = [
            "## 2. 已知事实",
        ]

        if not result.known_facts:
            lines.extend(
                [
                    "",
                    "当前没有经过审核的有效事实。",
                ]
            )
            return "\n".join(lines)

        for fact in result.known_facts:
            lines.extend(
                [
                    "",
                    f"### {fact.fact_id}",
                    f"- 内容：{fact.description}",
                    (
                        "- 所属子系统："
                        f"`{fact.subsystem.value}`"
                    ),
                    (
                        "- 证据来源："
                        f"`{fact.source.value}`"
                    ),
                    (
                        "- 来源标识："
                        f"{fact.source_reference or '未提供'}"
                    ),
                    (
                        "- 是否已验证："
                        f"{'是' if fact.is_verified else '否'}"
                    ),
                    f"- 可信度：{fact.confidence:.2f}",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_missing_information(
        result: RndAnalysisResult,
    ) -> str:
        """生成缺失信息。"""

        lines = [
            "## 3. 缺失信息",
        ]

        if not result.missing_information:
            lines.extend(["", "当前没有明确的缺失信息。"])
            return "\n".join(lines)

        for item in result.missing_information:
            lines.extend(
                [
                    "",
                    f"### {item.item_id}",
                    f"- 缺失内容：{item.description}",
                    f"- 影响：{item.impact}",
                    f"- 优先级：`{item.priority.value}`",
                    (
                        "- 是否影响根因确认："
                        f"{'是' if item.required_for_confirmation else '否'}"
                    ),
                    (
                        "- 关联根因："
                        + self_format_list(
                            item.related_hypothesis_ids
                        )
                    ),
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_hypotheses(
        result: RndAnalysisResult,
    ) -> str:
        """生成候选根因。"""

        lines = [
            "## 4. 候选根因及优先级",
        ]

        if not result.hypotheses:
            lines.extend(["", "当前未形成候选根因。"])
            return "\n".join(lines)

        for hypothesis in result.hypotheses:
            lines.extend(
                [
                    "",
                    f"### {hypothesis.hypothesis_id}",
                    f"- 根因描述：{hypothesis.description}",
                    (
                        "- 所属子系统："
                        f"`{hypothesis.subsystem.value}`"
                    ),
                    (
                        "- 证据状态："
                        f"`{hypothesis.status.value}`"
                    ),
                    (
                        "- 研发优先级："
                        f"`{hypothesis.priority.value}`"
                    ),
                    f"- 置信度：{hypothesis.confidence:.2f}",
                    (
                        "- 支持事实："
                        + self_format_list(
                            hypothesis.supporting_fact_ids
                        )
                    ),
                    (
                        "- 反向事实："
                        + self_format_list(
                            hypothesis.contradicting_fact_ids
                        )
                    ),
                    f"- 推理依据：{hypothesis.reasoning}",
                    (
                        "- 潜在影响："
                        f"{hypothesis.potential_impact}"
                    ),
                    (
                        "- 是否需要人工复核："
                        f"{'是' if hypothesis.needs_human_review else '否'}"
                    ),
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_experiments(
        result: RndAnalysisResult,
    ) -> str:
        """生成验证实验计划。"""

        lines = [
            "## 5. 验证实验计划",
        ]

        if not result.experiments:
            lines.extend(["", "当前没有验证实验计划。"])
            return "\n".join(lines)

        for experiment in result.experiments:
            lines.extend(
                [
                    "",
                    (
                        f"### {experiment.experiment_id}："
                        f"{experiment.title}"
                    ),
                    (
                        "- 关联根因："
                        + self_format_list(
                            experiment
                            .linked_hypothesis_ids
                        )
                    ),
                    f"- 实验目标：{experiment.objective}",
                    (
                        "- 所需输入："
                        + self_format_list(
                            experiment.required_inputs
                        )
                    ),
                    (
                        "- 控制变量："
                        + self_format_list(
                            experiment.controlled_variables
                        )
                    ),
                    (
                        "- 观察指标："
                        + self_format_list(
                            experiment.observed_metrics
                        )
                    ),
                    (
                        "- 预期现象："
                        f"{experiment.expected_observation}"
                    ),
                    (
                        "- 风险等级："
                        f"`{experiment.risk_level.value}`"
                    ),
                    (
                        "- 是否需要人工审批："
                        f"{'是' if experiment.needs_human_approval else '否'}"
                    ),
                    "- 实验步骤：",
                ]
            )

            lines.extend(
                f"  {index}. {step}"
                for index, step in enumerate(
                    experiment.steps,
                    start=1,
                )
            )

            lines.append("- 判定标准：")

            for criterion in experiment.criteria:
                lines.extend(
                    [
                        f"  - 指标：{criterion.metric}",
                        (
                            "    - 测量方法："
                            f"{criterion.measurement_method}"
                        ),
                        (
                            "    - 通过标准："
                            f"{criterion.pass_condition}"
                        ),
                        (
                            "    - 失败标准："
                            f"{criterion.fail_condition}"
                        ),
                    ]
                )

            lines.extend(
                [
                    (
                        "- 停止条件："
                        + self_format_list(
                            experiment.stop_conditions
                        )
                    ),
                    (
                        "- 安全要求："
                        + self_format_list(
                            experiment.safety_requirements
                        )
                    ),
                    (
                        "- 实验交付物："
                        + self_format_list(
                            experiment.deliverables
                        )
                    ),
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_assignments(
        result: RndAnalysisResult,
    ) -> str:
        """生成团队分工。"""

        lines = [
            "## 6. 团队分工",
        ]

        if not result.team_assignments:
            lines.extend(["", "当前没有团队任务。"])
            return "\n".join(lines)

        for assignment in result.team_assignments:
            lines.extend(
                [
                    "",
                    f"### {assignment.assignment_id}",
                    (
                        "- 关联实验："
                        + self_format_list(
                            assignment.experiment_ids
                        )
                    ),
                    f"- 负责团队：`{assignment.owner.value}`",
                    (
                        "- 协作团队："
                        + self_format_enum_list(
                            assignment.collaborators
                        )
                    ),
                    (
                        "- 审核团队："
                        + self_format_enum_list(
                            assignment.reviewers
                        )
                    ),
                    f"- 具体任务：{assignment.task}",
                    (
                        "- 输入依赖："
                        + self_format_list(
                            assignment.input_dependencies
                        )
                    ),
                    (
                        "- 交付物："
                        + self_format_list(
                            assignment.deliverables
                        )
                    ),
                    (
                        "- 完成标准："
                        + self_format_list(
                            assignment.completion_criteria
                        )
                    ),
                    (
                        "- 阻塞项："
                        + self_format_list(
                            assignment.blockers
                        )
                    ),
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_dependencies(
        result: RndAnalysisResult,
    ) -> str:
        """生成跨团队依赖。"""

        lines = [
            "## 7. 跨团队依赖",
        ]

        if not result.dependencies:
            lines.extend(["", "当前没有明确的任务交接依赖。"])
            return "\n".join(lines)

        for dependency in result.dependencies:
            lines.extend(
                [
                    "",
                    f"### {dependency.dependency_id}",
                    (
                        "- 上游任务："
                        f"`{dependency.upstream_assignment_id}`"
                    ),
                    (
                        "- 下游任务："
                        f"`{dependency.downstream_assignment_id}`"
                    ),
                    (
                        "- 必需交付物："
                        f"{dependency.required_deliverable}"
                    ),
                    (
                        "- 交接标准："
                        f"{dependency.handoff_criteria}"
                    ),
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_risks(
        result: RndAnalysisResult,
    ) -> str:
        """生成研发风险。"""

        lines = [
            "## 8. 风险与缓解措施",
        ]

        if not result.risks:
            lines.extend(["", "当前没有额外研发风险记录。"])
            return "\n".join(lines)

        for risk in result.risks:
            lines.extend(
                [
                    "",
                    f"### {risk.risk_id}",
                    f"- 风险描述：{risk.description}",
                    (
                        "- 风险等级："
                        f"`{risk.risk_level.value}`"
                    ),
                    (
                        "- 关联根因："
                        + self_format_list(
                            risk.related_hypothesis_ids
                        )
                    ),
                    (
                        "- 关联实验："
                        + self_format_list(
                            risk.related_experiment_ids
                        )
                    ),
                    f"- 缓解措施：{risk.mitigation}",
                    f"- 风险负责人：`{risk.owner.value}`",
                    (
                        "- 是否需要人工复核："
                        f"{'是' if risk.requires_human_review else '否'}"
                    ),
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _render_unresolved_items(
        result: RndAnalysisResult,
    ) -> str:
        """生成未解决事项。"""

        lines = [
            "## 9. 未解决事项",
            "",
        ]

        if not result.unresolved_items:
            lines.append("当前没有额外未解决事项。")
        else:
            lines.extend(
                f"- {item}"
                for item in result.unresolved_items
            )

        return "\n".join(lines)

    @staticmethod
    def _render_review_status(
        result: RndAnalysisResult,
    ) -> str:
        """生成人工复核说明。"""

        return "\n".join(
            [
                "## 10. 人工复核要求",
                "",
                (
                    "- 是否需要人工复核："
                    f"{'是' if result.needs_human_review else '否'}"
                ),
                (
                    "- 说明："
                    + (
                        "当前结果只能作为研发决策输入，"
                        "需要动力系统专业人员审核。"
                        if result.needs_human_review
                        else
                        "当前结果已通过结构化规则校验，"
                        "但仍不得直接作为真实控制指令。"
                    )
                ),
            ]
        )

    @staticmethod
    def _render_trace(
        result: RndAnalysisResult,
    ) -> str:
        """生成追踪信息。"""

        return "\n".join(
            [
                "## 11. 执行追踪",
                "",
                f"- Trace ID：`{result.trace_id}`",
                (
                    "- 生成方式：PowerAgent研发分析"
                    "结构化工作流"
                ),
            ]
        )


def self_format_list(
    items: list[str],
) -> str:
    """格式化普通字符串列表。"""

    return "、".join(items) if items else "无"


def self_format_enum_list(
    items: list,
) -> str:
    """格式化枚举列表。"""

    return (
        "、".join(item.value for item in items)
        if items
        else "无"
    )