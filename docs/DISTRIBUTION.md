# SQL Optimizer Skill 分发说明

本文档用于发布方和使用方快速完成打包、分发、安装、自检。

## 1. 发布方：生成分发包

在仓库根目录执行：

Linux/macOS:

```bash
python3 install/build_bundle.py
```

Windows PowerShell:

```powershell
python install/build_bundle.py
```

生成产物：

```text
dist/sql-optimizer-skill-bundle-v<version>.tar.gz
```

将该 `tar.gz` 上传到制品库或发给使用方。

## 2. 使用方：安装

先解压 `sql-optimizer-skill-bundle-v<version>.tar.gz`，进入解压目录。

Linux/macOS:

```bash
python3 install/install_skill.py --project /path/to/your/project
python3 install/doctor.py --project /path/to/your/project
```

Windows PowerShell:

```powershell
python install/install_skill.py --project C:\path\to\your\project
python install/doctor.py --project C:\path\to\your\project
```

可选：若项目使用直连 LLM，请同时在项目 `sqlopt.yml` 配置：
1. `llm.provider: direct_openai_compatible`
2. `llm.api_base`
3. `llm.api_key`
4. `llm.api_model`

## 3. 安装后验证

Linux/macOS:

```bash
$HOME/.opencode/skills/sql-optimizer/bin/sqlopt-cli --help
```

Windows PowerShell:

```powershell
$env:USERPROFILE\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd --help
```

## 4. 常见问题

1. `opencode` 找不到：重开终端后重试 `doctor.py`。  
2. 网络受限导致 pip 安装失败：先处理代理/网络，再重跑安装。  
3. 若安装中断，可加 `--force` 覆盖重装：

Linux/macOS:

```bash
python3 install/install_skill.py --project /path/to/your/project --force
```

Windows PowerShell:

```powershell
python install/install_skill.py --project C:\path\to\your\project --force
```

4. 如果 preflight 报 `PREFLIGHT_LLM_UNREACHABLE`：
   - `opencode_run`：先验证 `opencode run --format json --variant minimal "ping"`。
   - `direct_openai_compatible`：检查 `api_base/api_key/api_model` 和网络连通性。
