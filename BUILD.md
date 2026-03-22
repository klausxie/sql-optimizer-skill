# SQL Optimizer Build Guide

## 打包为可执行文件

### Windows 用户

#### 方法一：使用 PyInstaller（推荐）

1. **安装 Python 3.9+**
   下载地址: https://www.python.org/downloads/windows/

2. **克隆项目**
   ```bash
   git clone https://github.com/Hzzzzzx/sql-optimizer-skill.git
   cd sql-optimizer-skill
   ```

3. **安装依赖**
   ```bash
   pip install pyinstaller
   ```

4. **构建可执行文件**
   ```bash
   python build.py --onefile
   ```

5. **找到可执行文件**
   ```
   dist/sqlopt.exe
   ```

#### 方法二：使用预编译包（待发布）

下载 releases 页面中的 `sqlopt-x.x.x-windows.zip`，解压后直接运行 `sqlopt.exe`。

### macOS / Linux 用户

```bash
git clone https://github.com/Hzzzzzx/sql-optimizer-skill.git
cd sql-optimizer-skill
pip install pyinstaller
python build.py --onefile
# 可执行文件在 dist/sqlopt
```

## 使用方法

### 1. 创建配置文件 sqlopt.yml

```yaml
config_version: v1

project:
  root_path: /path/to/your/project

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql  # 或 mysql
  dsn: postgresql://user:pass@host:5432/db

llm:
  enabled: false  # 使用启发式引擎，不需要 LLM
```

### 2. 运行优化

```bash
# 完整流程
sqlopt run --config sqlopt.yml

# 仅扫描阶段
sqlopt scan --config sqlopt.yml

# 查看帮助
sqlopt --help
```

## 目录结构

构建后：

```
sql-optimizer-skill/
├── sqlopt.exe          # Windows 可执行文件
├── sqlopt.yml          # 配置文件
├── sqlopt-test/        # 测试用例（可选）
└── README.md
```

## 数据库要求

| 数据库 | 版本 | 驱动 |
|--------|------|------|
| PostgreSQL | 9.6+ | psycopg2-binary |
| MySQL | 5.6+ | PyMySQL |

## 故障排查

### 报错：找不到数据库驱动
```
pip install psycopg2-binary PyMySQL
```

### 报错：编码错误（Windows）
确保控制台编码为 UTF-8：
```bash
chcp 65001
```

### 报错：权限拒绝
以管理员身份运行，或将 sqlopt 放到有权限的目录。
