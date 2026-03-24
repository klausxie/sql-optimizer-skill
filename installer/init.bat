@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo SQL Optimizer 项目初始化
echo ========================================
echo.

if exist "sqlopt.yml" (
    echo 警告: sqlopt.yml 已存在
    set /p OVERWRITE="是否覆盖？ (y/n): "
    if /i not "!OVERWRITE!"=="y" (
        echo 取消初始化
        exit /b 1
    )
)

echo 请选择数据库类型:
echo   [1] PostgreSQL
echo   [2] MySQL
echo   [3] 仅测试 (mock 模式)
echo.
set /p DB_CHOICE="请输入选项 (1/2/3): "

if "!DB_CHOICE!"=="1" (
    set "TEMPLATE=config\templates\sqlopt.postgresql.yml.template"
) else if "!DB_CHOICE!"=="2" (
    set "TEMPLATE=config\templates\sqlopt.mysql.yml.template"
) else if "!DB_CHOICE!"=="3" (
    set "TEMPLATE=config\templates\sqlopt.example.yml.template"
) else (
    echo 错误: 无效选项
    exit /b 1
)

if not exist "!TEMPLATE!" (
    echo 错误: 模板文件不存在: !TEMPLATE!
    exit /b 1
)

echo.
echo 复制配置文件模板...
copy "!TEMPLATE!" "sqlopt.yml" >nul

echo.
echo 请修改配置文件中的以下内容:
echo   - db_host: 数据库主机地址
echo   - db_port: 端口
echo   - db_name: 数据库名称
echo   - db_user: 用户名
echo   - db_password: 密码
echo.

set /p EDIT_NOW="是否立即编辑配置文件？ (y/n): "
if /i "!EDIT_NOW!"=="y" (
    notepad sqlopt.yml 2>nul
)

echo.
echo ========================================
echo 初始化完成！
echo ========================================
echo.
echo 下一步:
echo   1. 编辑 sqlopt.yml 填入数据库信息
echo   2. 运行: sqlopt run init --config sqlopt.yml
echo.
endlocal
