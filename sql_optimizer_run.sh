#!/bin/bash
# 运行当前目录的 SQL 优化到 patch_generate 阶段
#
# 用法:
#   sql_optimizer_run.sh [options]
#
# 选项:
#   --max-steps N        最大处理步数 (默认: 不限制)
#   --max-seconds N      最大运行秒数 (默认: 不限制)
#   --run-id RUN_ID      继续指定运行
#   --to-stage STAGE     目标阶段 (默认: patch_generate)
#
# 示例:
#   cd /path/to/project && ./sql_optimizer_run.sh
#   cd /path/to/project && ./sql_optimizer_run.sh --max-steps 5
#   cd /path/to/project && ./sql_optimizer_run.sh --max-seconds 300

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查配置文件
if [ ! -f "sqlopt.yml" ]; then
    echo "Error: sqlopt.yml not found in current directory"
    echo "Usage: $(basename "$0") [--max-steps N] [--run-id RUN_ID] [--to-stage STAGE]"
    exit 1
fi

# 设置 PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/python:$PYTHONPATH"

# 运行优化 (默认到 patch_generate 阶段, 不限制步数和时间)
# 默认 max-steps=0 表示不限制, max-seconds=0 表示不限制
python3 "$SCRIPT_DIR/scripts/run_until_budget.py" --config sqlopt.yml --to-stage patch_generate --max-steps 0 --max-seconds 0 "$@"