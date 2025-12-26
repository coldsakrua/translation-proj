@echo off
echo 🔍 检查ES容器状态...
docker ps -a | findstr my_rag_es >nul
if %errorlevel% equ 0 (
    echo 🚀 启动ES容器...
    docker start my_rag_es
) else (
    echo ⚠️  ES容器不存在，重新创建...
    docker run -d --name my_rag_es -p 9200:9200 -e "discovery.type=single-node" -e "xpack.security.enabled=false" elasticsearch:7.17.0
)

echo ⏳ 等待ES启动（5秒）...
timeout /t 5 /nobreak >nul

echo ✅ 验证ES是否启动...
curl http://localhost:9200
if %errorlevel% equ 0 (
    echo 🎉 ES启动成功！
) else (
    echo ❌ ES启动失败，请检查Docker容器！
)
pause