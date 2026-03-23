from click.testing import CliRunner
from sqlopt.cli.main import cli


def test_cli_loads_without_errors():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "SQL Optimizer CLI" in result.output


def test_run_command_help_text():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "STAGE" in result.output
    assert "--config" in result.output


def test_run_with_valid_config():
    runner = CliRunner()
    config_path = "tests/real/mybatis-test/sqlopt.yml"
    result = runner.invoke(cli, ["run", "--config", config_path, "init"])
    assert result.exit_code == 0
    assert "Loading config from:" in result.output
    assert "Config loaded:" in result.output
    assert "completed successfully" in result.output


def test_run_with_invalid_config_path():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--config", "nonexistent.yml", "init"])
    assert result.exit_code == 1
    assert "Error: Config file not found" in result.output


def test_run_with_invalid_stage_name():
    runner = CliRunner()
    config_path = "tests/real/mybatis-test/sqlopt.yml"
    result = runner.invoke(cli, ["run", "--config", config_path, "invalid_stage"])
    assert result.exit_code == 1
    assert "Error: Stage 'invalid_stage' failed" in result.output
