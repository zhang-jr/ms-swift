#!/bin/bash
# 修复 /app/data 目录的权限问题
# 确保所有文件和文件夹都有正确的读取权限

echo "Fixing permissions for /app/data..."

# 设置文件夹权限为 755 (drwxr-xr-x)
find /app/data -type d -exec chmod 755 {} \;

# 设置文件权限为 644 (-rw-r--r--)
find /app/data -type f -exec chmod 644 {} \;

echo "Done! All permissions fixed."
echo ""
echo "Directory permissions (should be drwxr-xr-x):"
ls -la /app/data/

echo ""
echo "File permissions inside directories:"
for dir in /app/data/*/; do
    if [ -d "$dir" ]; then
        echo "$(basename "$dir"):"
        ls -la "$dir" | head -5
    fi
done
