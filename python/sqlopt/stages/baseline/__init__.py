"""
Baseline Stage Module

Performance baseline collection and testing.
Re-exports from the main baseline module.
"""

# Re-export main functions from the monolithic baseline module
from sqlopt.baseline.performance_collector import collect_performance
from sqlopt.baseline.parameter_parser import parse_parameters
from sqlopt.baseline.parameter_binder import bind_parameters
from sqlopt.baseline.data_generator import generate_row, generate_test_value
from sqlopt.baseline.reporter import generate_baseline_report, write_report_jsonl

__all__ = [
    "collect_performance",
    "parse_parameters",
    "bind_parameters",
    "generate_row",
    "generate_test_value",
    "generate_baseline_report",
    "write_report_jsonl",
]
