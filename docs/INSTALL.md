# SQL Optimizer 安装指南

SQL Optimizer 支持三种安装模式，适用于不同场景。

**前置要求**: Python 3.9+

---

## 1. 全局安装（推荐）

安装到 OpenCode 全局技能目录，所有项目均可使用。

### Linux / macOS

```bash
python3 install/install_skill.py
```

### Windows (PowerShell)

```powershell
python install/install_skill.py
```

安装位置:
- Linux/macOS: `~/.config/opencode/skills/sql-optimizer/`
- Windows: `%USERPROFILE%\.config\opencode\skills\sql-optimizer\`

---

## 2. 项目内安装

安装到指定项目的 `.opencode/skills/sql-optimizer/` 目录，技能仅对该项目可用。

### Linux / macOS

```bash
python3 install/install_skill.py --project /path/to/your/project
```

### Windows (PowerShell)

```powershell
python install/install_skill.py --project C:\path\to\project
```

安装后会在项目根目录生成 `sqlopt.yml` 配置文件。

---

## 3. 自定义目录安装

安装到任意指定目录。

### Linux / macOS

```bash
python3 install/install_skill.py --project /custom/path/sqlopt-skill
```

### Windows (PowerShell)

```powershell
python install/install_skill.py --project C:\custom\path\sqlopt-skill
```

---

## 4. 验证安装

安装完成后，运行验证脚本检查环境配置：

### Linux / macOS

```bash
bash install/doctor.sh
```

### Windows (PowerShell)

```powershell
python install/doctor.py
```

验证脚本会检查:
- Python 版本 (需 3.9+)
- 依赖包是否完整
- 数据库连接配置

### 验证 CLI 可用性

```bash
# 全局安装后，直接使用
sqlopt-cli --version

# 项目内安装，使用相对路径
./bin/sqlopt-cli --version
```

---

## 5. 卸载

### Linux / macOS

```bash
python3 install/uninstall_skill.py
```

### Windows (PowerShell)

```powershell
python install/uninstall_skill.py
```

卸载说明:
- 全局安装会移除 `~/.config/opencode/skills/sql-optimizer/`
- 项目内安装会移除 `<project>/.opencode/skills/sql-optimizer/`
- 项目的 `sqlopt.yml` 和 `runs/` 数据会被保留

---

## 6. PATH 配置（Windows）

Windows 系统若希望全局使用 `sqlopt-cli` 命令，需手动添加路径到 PATH。

### 添加用户 PATH

1. 按 `Win + R`，输入 `sysdm.cpl`，回车
2. 高级 → 环境变量
3. 用户变量中选择 `Path`，点击编辑
4. 添加以下路径（替换为实际安装路径）:
   ```
   %USERPROFILE%\.config\opencode\skills\sql-optimizer\bin
   ```
5. 保存并重启终端

### 验证 PATH

```powershell
# 检查路径是否生效
sqlopt-cli --version

# 如提示找不到命令，检查 PATH 配置
echo $env:PATH
```

---

## 7. 重新安装 / 更新

覆盖安装会自动移除旧版本：

```bash
# 全局安装
python3 install/install_skill.py --force

# 项目内安装
python3 install/install_skill.py --project /path/to/project --force
```

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `python: command not found` | 使用 `python3` 或确认 Python 已安装 |
| `sqlopt-cli: command not found` | 检查 PATH 配置或使用完整路径 |
| 依赖安装失败 | 手动执行 `pip install -r install/requirements.txt` |
| 验证脚本报错 | 查看错误信息，确保数据库配置正确 |

如需更多帮助，参见 [故障排查文档](TROUBLESHOOTING.md)。
