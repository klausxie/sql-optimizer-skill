"""Error message mappings with detailed explanations and suggestions."""

from __future__ import annotations

ERROR_MESSAGES = {
    "RUN_NOT_FOUND": {
        "title": "未找到运行记录",
        "description": "指定的运行 ID 不存在于运行索引中。",
        "causes": [
            "运行 ID 输入有误",
            "运行记录创建于不同的项目目录",
            "运行索引文件损坏或丢失"
        ],
        "suggestions": [
            "检查运行 ID 是否有拼写错误",
            "使用 'status' 命令列出可用运行",
            "验证当前项目目录是否正确",
            "检查项目中是否存在 runs/ 目录"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#run-not-found"
    },
    "CONFIG_NOT_FOUND": {
        "title": "未找到配置文件",
        "description": "指定的配置文件不存在。",
        "causes": [
            "配置文件路径不正确",
            "配置文件尚未创建",
            "没有足够的权限读取文件"
        ],
        "suggestions": [
            "验证 --config 路径是否正确",
            "从模板创建 sqlopt.yml：cp templates/sqlopt.example.yml sqlopt.yml",
            "检查文件权限",
            "如果相对路径不起作用，使用绝对路径"
        ],
        "doc_link": "docs/INSTALL.md#configuration"
    },
    "CONFIG_INVALID": {
        "title": "配置无效",
        "description": "配置文件包含无效或缺失的必填字段。",
        "causes": [
            "必填字段缺失",
            "字段值无效",
            "YAML 语法错误"
        ],
        "suggestions": [
            "将配置与 templates/sqlopt.example.yml 进行比较",
            "检查 YAML 语法错误（缩进、冒号、引号）",
            "确保所有必填字段存在：project.root_path, db.dsn, scan.mapper_globs",
            "运行：python3 install/doctor.py --project <path> 验证配置"
        ],
        "doc_link": "docs/INSTALL.md#configuration"
    },
    "SCANNER_JAR_NOT_FOUND": {
        "title": "未找到 Java Scanner JAR",
        "description": "Java scanner JAR 文件丢失或无法访问（仅 legacy Java scanner 路径）。",
        "causes": [
            "JAR 文件未构建",
            "配置中的路径不正确",
            "技能安装不正确"
        ],
        "suggestions": [
            "优先使用默认 Python fallback scanner（无需配置 scan.java_scanner.jar_path）",
            "重新安装技能：python3 install/install_skill.py --project <path>",
            "验证 JAR 文件在指定路径存在",
            "如需手动构建 JAR：cd java/scan-agent && mvn package"
        ],
        "doc_link": "docs/INSTALL.md#java-scanner"
    },
    "DB_CONNECTION_FAILED": {
        "title": "数据库连接失败",
        "description": "无法连接到数据库。",
        "causes": [
            "数据库未运行",
            "连接字符串 (DSN) 不正确",
            "网络连通性问题",
            "认证失败"
        ],
        "suggestions": [
            "验证数据库正在运行",
            "检查配置文件中的 db.dsn",
            "手动测试连接：psql <connection_string>",
            "验证用户名、密码、主机、端口和数据库名称",
            "检查防火墙和网络设置",
            "数据库恢复后执行 resume 继续当前 run"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#database-connection"
    },
    "SCHEMA_VALIDATION_FAILED": {
        "title": "Schema 验证失败",
        "description": "输出数据不符合预期的 JSON schema。",
        "causes": [
            "阶段输出格式不正确",
            "Schema 版本不匹配",
            "阶段实现中存在 bug"
        ],
        "suggestions": [
            "检查错误详情，了解哪个字段验证失败",
            "验证 runs/<run-id>/control/state.json 中的 contract_version",
            "查看错误中提到的阶段输出文件",
            "如果问题持续，请报告：https://github.com/your-org/sql-optimizer/issues"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#schema-validation"
    },
    "RUNTIME_RETRY_EXHAUSTED": {
        "title": "重试次数已用尽",
        "description": "操作在多次重试后仍失败。",
        "causes": [
            "持久性外部服务故障（LLM、数据库）",
            "资源限制（超时、内存）",
            "阶段逻辑中存在不可恢复的错误"
        ],
        "suggestions": [
            "检查 runs/<run-id>/control/manifest.jsonl 中的详细错误",
            "验证外部服务（LLM 提供商、数据库）可访问",
            "使用 'resume' 命令从失败点重试"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#retry-exhausted"
    },
    "LLM_TIMEOUT": {
        "title": "LLM 请求超时",
        "description": "LLM 请求超过超时限制。",
        "causes": [
            "LLM 服务缓慢或过载",
            "网络延迟",
            "请求过于复杂"
        ],
        "suggestions": [
            "在配置中增加 llm.timeout_ms",
            "检查 LLM 服务状态",
            "尝试不同的 LLM 提供商",
            "缩小运行范围，例如只针对单个 sql-key 做局部 run",
            "检查到 LLM 端点的网络连通性"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#llm-timeout"
    },
    "LLM_PROVIDER_ERROR": {
        "title": "LLM 提供商错误",
        "description": "LLM 提供商返回错误。",
        "causes": [
            "API 密钥或凭据无效",
            "超过速率限制",
            "服务不可用",
            "请求格式无效"
        ],
        "suggestions": [
            "验证配置中的 llm.api_key（如果使用 direct_openai_compatible）",
            "检查 LLM 提供商服务状态",
            "如果超过速率限制，请等待后重试",
            "切换到不同的提供商：llm.provider=heuristic（不需要 LLM）",
            "检查 llm.api_base URL 是否正确"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#llm-provider"
    },
    "PATCH_CONFLICT": {
        "title": "检测到补丁冲突",
        "description": "生成的补丁与现有代码冲突。",
        "causes": [
            "源文件在扫描后被修改",
            "多个补丁针对同一位置",
            "模板结构已更改"
        ],
        "suggestions": [
            "查看补丁结果中的冲突详情",
            "手动解决源文件中的冲突",
            "如果源文件发生重大变化，重新运行扫描",
            "谨慎使用 'apply' 命令并审查更改"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#patch-conflicts"
    },
    "VERIFICATION_GATE_FAILED": {
        "title": "验证门失败",
        "description": "关键输出在没有完整验证证据的情况下生成。",
        "causes": [
            "PASS 验收结果在验证账簿中被标记为 UNVERIFIED",
            "可应用的补丁在验证账簿中被标记为 UNVERIFIED",
            "关键输出的验证证据不完整"
        ],
        "suggestions": [
            "检查 `artifacts/acceptance.jsonl` 和 `artifacts/patches.jsonl` 中嵌入的 verification 记录",
            "查看 runs/<run-id>/report.json 中的 blockers 和 next_action",
            "修复缺失的证据路径后重新执行 resume 或 report 重建",
            "在重新运行发布验收之前先确认 verify 输出已收口"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#verification"
    },
    "INSUFFICIENT_PERMISSIONS": {
        "title": "权限不足",
        "description": "无法读取或写入所需的文件。",
        "causes": [
            "文件或目录权限过于严格",
            "使用错误的用户运行",
            "文件被另一个进程锁定"
        ],
        "suggestions": [
            "检查文件和目录权限",
            "确保对 mapper XML 文件有读取权限",
            "确保对 runs/ 目录有写入权限",
            "使用适当的用户权限运行"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#permissions"
    }
}


def get_error_details(reason_code: str) -> dict[str, any]:
    """获取错误原因代码的详细信息。

    Args:
        reason_code: 错误原因代码

    Returns:
        包含错误详情的字典，包括标题、描述、原因和建议
    """
    return ERROR_MESSAGES.get(reason_code, {
        "title": "未知错误",
        "description": f"发生错误，代码：{reason_code}",
        "causes": ["未知原因"],
        "suggestions": [
            "检查错误消息获取更多信息",
            "查看 runs/<run-id>/control/manifest.jsonl 获取详细日志",
            "报告此问题：https://github.com/your-org/sql-optimizer/issues"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md"
    })


def format_error_message(reason_code: str, original_message: str) -> dict[str, any]:
    """格式化带有详细信息的错误消息。

    Args:
        reason_code: 错误原因代码
        original_message: 原始错误消息

    Returns:
        包含格式化错误信息的字典
    """
    details = get_error_details(reason_code)
    return {
        "reason_code": reason_code,
        "message": original_message,
        "title": details["title"],
        "description": details["description"],
        "possible_causes": details["causes"],
        "suggestions": details["suggestions"],
        "doc_link": details["doc_link"]
    }
