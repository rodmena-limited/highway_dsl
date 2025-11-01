import json
from datetime import timedelta, time, datetime  # Need datetime for the validator

try:
    from highway_dsl import (
        Workflow,
        WorkflowBuilder,
        TaskOperator,
        ConditionOperator,
        ParallelOperator,
        WaitOperator,
        ForEachOperator,
        WhileOperator,
        RetryPolicy,
        TimeoutPolicy,
        OperatorType,
    )
except ImportError:
    print("Error: highway_dsl library not found. Please install it.")
    exit()


def demonstrate_bank_etl_workflow():
    """
    Defines a massive, complex EOD banking ETL, risk, and
    regulatory reporting workflow.
    """

    builder = WorkflowBuilder("eod_financial_etl_v1")

    # --- PHASE 1: PARALLEL DATA INGESTION ---
    builder.parallel(
        "ingest_source_systems",
        branches={
            "core_banking": lambda b: b.task(
                "ingest_core_banking",
                "etl.ingest.from_mainframe_db2",
                args=["accounts", "balances"],
                result_key="core_data",
                retry_policy=RetryPolicy(max_retries=5),
            ),
            "card_transactions": lambda b: b.task(
                "ingest_card_txns",
                "etl.ingest.from_payment_gateway_sftp",
                result_key="card_data",
                timeout_policy=TimeoutPolicy(timeout=timedelta(hours=2)),
            ),
            "loan_systems": lambda b: b.task(
                "ingest_loan_systems",
                "etl.ingest.from_sql_server",
                args=["mortgages", "personal_loans"],
                result_key="loan_data",
            ),
            "payment_feeds": lambda b: b.task(
                "ingest_payment_feeds",
                "etl.ingest.from_swift_mq",
                result_key="payment_data",
            ),
        },
    )

    # --- PHASE 2: DATA VALIDATION & RECONCILIATION ---
    builder.task(
        "run_pre_reconciliation",
        "etl.validation.run_initial_checksums",
        args=["{{core_data}}", "{{card_data}}", "{{loan_data}}", "{{payment_data}}"],
        result_key="recon_status",
        dependencies=["ingest_source_systems"],
    )

    builder.while_loop(
        "reconciliation_loop",
        condition="{{recon_status.is_balanced}} == false",
        loop_body=lambda b: b.task(
            "find_discrepancies",
            "etl.reconciliation.find_discrepancies",
            args=["{{recon_status.report_id}}"],
            result_key="discrepancy_report",
        )
        .task(
            "apply_auto_adjustments",
            "etl.reconciliation.apply_adjustments",
            args=["{{discrepancy_report.adjustments_file}}"],
        )
        .task(
            "run_reconciliation_check",
            "etl.validation.run_initial_checksums",
            args=[
                "{{core_data}}",
                "{{card_data}}",
                "{{loan_data}}",
                "{{payment_data}}",
            ],
            result_key="recon_status",
        ),
        dependencies=["run_pre_reconciliation"],
    )

    # --- PHASE 3: CORE BUSINESS PROCESSING ---
    builder.parallel(
        "core_business_processing",
        branches={
            "accounts": lambda b: b.task(
                "update_account_balances", "etl.accounts.update_all_balances"
            ).task("process_overdrafts", "etl.accounts.process_overdrafts"),
            "loans": lambda b: b.task(
                "calculate_loan_interest", "etl.loans.calculate_eod_interest"
            ).task("process_loan_payments", "etl.loans.apply_scheduled_payments"),
            "credit_cards": lambda b: b.task(
                "get_card_accounts_list",
                "etl.cards.get_accounts_for_batch",
                result_key="card_accounts_list",
            ).foreach(
                "credit_card_batch_loop",
                items="{{card_accounts_list}}",
                loop_body=lambda fb: fb.task(
                    "calc_card_interest",
                    "etl.cards.calculate_interest",
                    args=["{{item.account_id}}"],
                )
                .task(
                    "apply_card_payments",
                    "etl.cards.apply_payments",
                    args=["{{item.account_id}}"],
                )
                .task(
                    "generate_card_statement_data",
                    "etl.cards.generate_statement",
                    args=["{{item.account_id}}"],
                ),
            ),
        },
        dependencies=["reconciliation_loop"],
    )

    # --- PHASE 4: RISK & REGULATORY REPORTING ---
    builder.parallel(
        "risk_and_regulatory_reporting",
        branches={
            "credit_risk": lambda b: b.task(
                "calculate_credit_risk", "etl.risk.calculate_eod_credit_exposure"
            ).task("update_risk_dashboards", "etl.risk.load_to_risk_db"),
            "market_risk": lambda b: b.task(
                "calculate_market_risk", "etl.risk.calculate_value_at_risk"
            ),
            "regulatory_aml": lambda b: b.task(
                "get_large_transactions",
                "etl.regulatory.get_large_transactions_for_review",
                result_key="large_txns",
            ).foreach(
                "aml_check_loop",
                items="{{large_txns}}",
                loop_body=lambda fb: fb.task(
                    "run_aml_check",
                    "etl.regulatory.check_aml_transaction",
                    args=["{{item.txn_id}}"],
                    result_key="aml_result",
                ).condition(
                    "check_aml_flag",
                    condition="{{aml_result.is_suspicious}} == true",
                    if_true=lambda true_b: true_b.task(
                        "create_suspicious_activity_report",
                        "etl.regulatory.file_sar_report",
                        args=["{{aml_result}}"],
                    ),
                    if_false=lambda false_b: false_b.task(
                        "mark_txn_aml_clear",
                        "etl.regulatory.mark_transaction_clear",
                        args=["{{item.txn_id}}"],
                    ),
                ),
            ),
            "central_bank_reports": lambda b: b.task(
                "generate_basel_report", "etl.reports.generate_basel_iii_report"
            ).task("generate_ccar_report", "etl.reports.generate_ccar_report"),
        },
        dependencies=["core_business_processing"],
    )

    # --- PHASE 5: FINALIZATION & DATA WAREHOUSE ---
    builder.task(
        "load_to_data_warehouse",
        "etl.load.load_all_to_warehouse",
        dependencies=["risk_and_regulatory_reporting"],
        timeout_policy=TimeoutPolicy(timeout=timedelta(hours=3)),
    )
    builder.task(
        "generate_management_dashboards",
        "etl.reports.refresh_management_bi_dashboards",
        dependencies=["load_to_data_warehouse"],
    )

    # Wait until 4:00 AM to archive old data
    builder.wait(
        "wait_for_archive_window",
        "time:04:00:00",  # <-- CORRECTED: Was time(4, 0)
        dependencies=["load_to_data_warehouse"],
    )

    builder.task(
        "archive_raw_data",
        "etl.archive.s3_archive_raw_feeds",
        dependencies=["wait_for_archive_window"],
    )

    workflow = builder.build()

    workflow.set_variables(
        {
            "sftp_host": "sftp.partner.com",
            "db2_connection_string": "...",
            "s3_archive_bucket": "bank-prod-raw-archive-us-east-1",
        }
    )

    return workflow


if __name__ == "__main__":
    bank_etl_workflow = demonstrate_bank_etl_workflow()

    print("--- BANK ETL WORKFLOW YAML (MASSIVE) ---")
    try:
        print(bank_etl_workflow.to_yaml())
        print("----------------------------------------")
        print("\n✅ Successfully generated massive bank ETL workflow YAML.")
        print(f"Total tasks defined: {len(bank_etl_workflow.tasks)}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
