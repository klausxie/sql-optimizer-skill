#!/bin/bash
echo "========================================"
echo "SQL Optimizer 项目初始化"
echo "========================================"
echo ""

if [ -f "sqlopt.yml" ]; then
    echo "警告: sqlopt.yml 已存在"
    read -p "是否覆盖？ (y/n): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "取消初始化"
        exit 1
    fi
fi

echo "请选择数据库类型:"
echo "  [1] PostgreSQL"
echo "  [2] MySQL"
echo "  [3] 仅测试 (mock 模式)"
echo ""
read -p "请输入选项 (1/2/3): " DB_CHOICE

case "$DB_CHOICE" in
    1) TEMPLATE="config/templates/sqlopt.postgresql.yml.template" ;;
    2) TEMPLATE="config/templates/sqlopt.mysql.yml.template" ;;
    3) TEMPLATE="config/templates/sqlopt.example.yml.template" ;;
    *) echo "错误: 无效选项"; exit 1 ;;
esac

if [ ! -f "$TEMPLATE" ]; then
    echo "错误: 模板文件不存在: $TEMPLATE"
    exit 1
fi

echo ""
echo "复制配置文件模板..."
cp "$TEMPLATE" "sqlopt.yml"

echo ""
echo "请修改配置文件中的以下内容:"
echo "  - db_host: 数据库主机地址"
echo "  - db_port: 端口"
echo "  - db_name: 数据库名称"
echo "  - db_user: 用户名"
echo "  - db_password: 密码"
echo ""

read -p "是否立即编辑配置文件？ (y/n): " EDIT_NOW
if [ "$EDIT_NOW" = "y" ] || [ "$EDIT_NOW" = "Y" ]; then
    if command -v nano >/dev/null 2>&1; then
        nano sqlopt.yml
    elif command -v vim >/dev/null 2>&1; then
        vim sqlopt.yml
    else
        echo "请手动编辑 sqlopt.yml 文件"
    fi
fi

echo ""
echo "========================================"
echo "初始化完成！"
echo "========================================"
echo ""
echo "下一步:"
echo "  1. 编辑 sqlopt.yml 填入数据库信息"
echo "  2. 运行: ./sqlopt run init --config sqlopt.yml"
echo ""
