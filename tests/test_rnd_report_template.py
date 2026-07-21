"""研发分析Markdown报告模板核心测试。"""

from report.rnd_report_template import (
    RndReportTemplate,
)
from tests.rnd_test_helpers import (
    make_valid_result,
)


def test_render_complete_rnd_report() -> None:
    """完整研发结果应生成全部核心章节。"""

    result = make_valid_result()

    report = RndReportTemplate().render(result)

    assert "# PowerAgent 研发问题分析报告" in report
    assert "## 4. 候选根因及优先级" in report
    assert "## 5. 验证实验计划" in report
    assert "## 6. 团队分工" in report
    assert result.trace_id in report


def test_report_keeps_relationship_ids() -> None:
    """报告必须保留根因、实验和任务之间的ID。"""

    result = make_valid_result()

    report = RndReportTemplate().render(result)

    hypothesis_id = (
        result.hypotheses[0].hypothesis_id
    )
    experiment_id = (
        result.experiments[0].experiment_id
    )
    assignment_id = (
        result.team_assignments[0].assignment_id
    )

    assert hypothesis_id in report
    assert experiment_id in report
    assert assignment_id in report


def test_report_render_is_deterministic() -> None:
    """相同输入必须生成相同报告。"""

    result = make_valid_result()
    template = RndReportTemplate()

    first = template.render(result)
    second = template.render(result)

    assert first == second