from sqlopt.contracts_next import (
    BranchCandidate,
    ColumnDistribution,
    ColumnMetadata,
    ExecutionBaseline,
    GlobalReport,
    GlobalReportSummary,
    IndexMetadata,
    OptimizationValidation,
    ParameterSlot,
    PlanFlags,
    ResultSignature,
    RootCauseHit,
    SlowSQLFinding,
    StageManifest,
    StageTotals,
    TableMetadata,
    TopValueStat,
)


def test_stage_manifest_round_trip() -> None:
    manifest = StageManifest(
        schema_version="next-v1",
        run_id="run-001",
        stage_name="recognition",
        status="completed",
        totals=StageTotals(statements=10, branches=20, cases=30, findings=5),
    )

    restored = StageManifest.from_json(manifest.to_json())

    assert restored.run_id == "run-001"
    assert restored.totals.cases == 30
    assert restored.stage_name == "recognition"


def test_table_metadata_round_trip() -> None:
    table = TableMetadata(
        table_name="user",
        row_count=1000,
        data_bytes=2048,
        columns=[ColumnMetadata(name="id", type="bigint", nullable=False)],
        indexes=[IndexMetadata(name="idx_user_id", is_unique=True, columns=["id"])],
    )

    restored = TableMetadata.from_json(table.to_json())

    assert restored.table_name == "user"
    assert restored.columns[0].name == "id"
    assert restored.indexes[0].columns == ["id"]


def test_column_distribution_round_trip() -> None:
    distribution = ColumnDistribution(
        table_name="user",
        column_name="status",
        distinct_count=5,
        null_count=0,
        null_ratio=0.0,
        top_values=[TopValueStat(value="ACTIVE", count=90)],
        skew_score=0.91,
    )

    restored = ColumnDistribution.from_json(distribution.to_json())

    assert restored.column_name == "status"
    assert restored.top_values[0].value == "ACTIVE"
    assert restored.skew_score == 0.91


def test_branch_candidate_round_trip() -> None:
    branch = BranchCandidate(
        statement_key="com.foo.UserMapper.search",
        path_id="branch_000127",
        branch_type="static_sampled",
        expanded_sql="SELECT * FROM user WHERE status = #{status}",
        parameter_slots=[
            ParameterSlot(
                param_name="status",
                column_name="status",
                predicate_type="eq",
            )
        ],
        static_risk_score=88.1,
    )

    restored = BranchCandidate.from_json(branch.to_json())

    assert restored.statement_key.endswith("search")
    assert restored.parameter_slots[0].param_name == "status"
    assert restored.static_risk_score == 88.1


def test_slow_sql_finding_round_trip() -> None:
    finding = SlowSQLFinding(
        finding_id="finding-1",
        statement_key="com.foo.UserMapper.search",
        path_id="branch_000127",
        case_id="case_hot_value_001",
        is_slow=True,
        severity="high",
        impact_score=91.4,
        confidence=0.93,
        root_causes=[
            RootCauseHit(
                code="full_table_scan",
                severity="high",
                message="execution plan shows sequential scan",
            )
        ],
        explain_ref="explain/shards/part-00001.jsonl#10",
        execution_ref="execution/shards/part-00001.jsonl#20",
        optimization_ready=True,
    )

    restored = SlowSQLFinding.from_json(finding.to_json())

    assert restored.is_slow is True
    assert restored.root_causes[0].code == "full_table_scan"
    assert restored.optimization_ready is True


def test_execution_baseline_round_trip() -> None:
    baseline = ExecutionBaseline(
        statement_key="com.foo.UserMapper.search",
        path_id="branch_000127",
        case_id="case_hot_value_001",
        run_count=5,
        avg_time_ms=842.5,
        p95_time_ms=901.2,
        rows_returned=120,
        rows_examined=18500000,
        result_signature=ResultSignature(
            row_count=120,
            ordered_key_digest="abc",
            sample_digest="def",
            ordering_columns=["id"],
        ),
    )

    restored = ExecutionBaseline.from_json(baseline.to_json())

    assert restored.result_signature is not None
    assert restored.result_signature.ordering_columns == ["id"]
    assert restored.avg_time_ms == 842.5


def test_optimization_validation_round_trip() -> None:
    validation = OptimizationValidation(
        proposal_id="proposal-1",
        finding_id="finding-1",
        statement_key="com.foo.UserMapper.search",
        path_id="branch_000127",
        case_id="case_hot_value_001",
        result_equivalent=True,
        after_explain_cost=8000.0,
        after_avg_time_ms=95.0,
        after_rows_examined=1000,
        after_result_signature=ResultSignature(
            row_count=120,
            ordered_key_digest="abc",
            sample_digest="def",
            ordering_columns=["id"],
        ),
        gain_ratio=0.88,
    )

    restored = OptimizationValidation.from_json(validation.to_json())

    assert restored.result_equivalent is True
    assert restored.after_result_signature is not None
    assert restored.after_result_signature.row_count == 120


def test_global_report_round_trip() -> None:
    report = GlobalReport(
        summary=GlobalReportSummary(
            statements_scanned=120,
            branches_generated=640,
            explain_executed=1000,
            execution_baselines=120,
            verified_slow_sql=18,
            high_risk_candidates=25,
        )
    )

    restored = GlobalReport.from_json(report.to_json())

    assert restored.summary.verified_slow_sql == 18
    assert restored.summary.high_risk_candidates == 25


def test_plan_flags_defaults() -> None:
    flags = PlanFlags()
    assert flags.full_table_scan is False
    assert flags.filesort is False
