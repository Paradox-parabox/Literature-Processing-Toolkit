# GitHub 部署脚本
# 使用方法：
# 1. 将此文件保存为 deploy.ps1
# 2. 在PowerShell中运行：./deploy.ps1 -RemoteUrl "https://github.com/你的用户名/仓库名.git"

param(
    [Parameter(Mandatory=$true)]
    [string]$RemoteUrl
)

Write-Host "正在初始化Git仓库..." -ForegroundColor Green
git init

Write-Host "正在添加所有文件..." -ForegroundColor Green
git add .

Write-Host "正在创建初始提交..." -ForegroundColor Green
git commit -m "Initial commit: Academic Literature Processing Toolkit"

Write-Host "正在添加远程仓库..." -ForegroundColor Green
git remote add origin $RemoteUrl

Write-Host "正在推送代码到GitHub..." -ForegroundColor Green
git branch -M main
git push -u origin main

Write-Host "部署完成！" -ForegroundColor Green
Write-Host "你的代码已成功推送到 $RemoteUrl" -ForegroundColor Cyan