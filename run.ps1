# Script tiện dụng cho Windows: tạo/kích hoạt venv, cài thư viện, rồi mở app.
# Chạy trong PowerShell:  .\run.ps1
# (Nếu PowerShell chặn script, chạy 1 lần: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)

$ErrorActionPreference = "Stop"

# 1) Tạo môi trường ảo nếu chưa có
if (-not (Test-Path ".venv")) {
    Write-Host "Tao moi truong ao (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
}

# 2) Kích hoạt venv
. .\.venv\Scripts\Activate.ps1

# 3) Cài thư viện (nhẹ, cài nhanh)
Write-Host "Cai dat thu vien..." -ForegroundColor Cyan
pip install -r requirements.txt

# 4) Nhắc tạo .env nếu chưa có
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Da tao .env tu .env.example — hay mo ra dien API key!" -ForegroundColor Yellow
}

# 5) Mở giao diện chat
Write-Host "Mo giao dien chat..." -ForegroundColor Green
streamlit run app.py
