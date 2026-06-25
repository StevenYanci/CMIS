# CMIS Git快捷提交脚本
# 用法: .\gitcommit.ps1 "本次更新内容"
param(
    [Parameter(Position=0, ValueFromRemainingArguments=$true)]
    [string]$Message
)

$repo = "D:\work\CMIS"

if (-not $Message) {
    $Message = Read-Host "请输入提交信息"
}

if (-not $Message) {
    Write-Host "提交信息不能为空" -ForegroundColor Red
    exit 1
}

Set-Location $repo

Write-Host "Git repository: $repo" -ForegroundColor Cyan
Write-Host ""

# 0. git pull remote log first
Write-Host "Step 0: git pull" -ForegroundColor Yellow
git pull



# 1. git status
Write-Host "Step 1: git status" -ForegroundColor Yellow
git status --short

# 2. git add .
Write-Host ""
Write-Host "Step 2: git add ." -ForegroundColor Yellow
git add .

# 3. git commit
Write-Host ""
Write-Host "Step 3: git commit" -ForegroundColor Yellow
git commit -m $Message

if ($LASTEXITCODE -ne 0) {
    Write-Host "Commit failed" -ForegroundColor Red
    exit 1
}

# 4. git push
Write-Host ""
Write-Host "Step 4: git push" -ForegroundColor Yellow
git push

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Done! All steps completed successfully." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Push failed. Please check network or remote repo status." -ForegroundColor Red
}

#5. add time tag
date