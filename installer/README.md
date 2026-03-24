# SQL Optimizer 安装包

本目录为 SQL Optimizer 的分发安装包。

## 详细文档

请参考项目根目录的 [README.md](../README.md) 获取完整使用说明。

## 目录结构

```
installer/
├── build.py              # 构建脚本
├── init.bat              # Windows 初始化脚本
├── init.sh               # Unix 初始化脚本
├── sqlopt.exe            # Windows 可执行文件（构建后）
├── sqlopt                # Linux/macOS 可执行文件（构建后）
└── config/              # 配置文件模板
```

## 快速开始

### 1. 运行初始化

```bash
# Windows
init.bat

# Linux/macOS
chmod +x init.sh && ./init.sh
```

### 2. 修改配置

编辑 `sqlopt.yml`，填入数据库信息。

### 3. 运行

```bash
sqlopt run init
sqlopt run parse
sqlopt run optimize
```

## 配置说明

详细配置说明请参考 [config/README_config.md](config/README_config.md)。
