Write-Host "🚀 Starting PatientAgent Setup..." -ForegroundColor Cyan

# Check if Docker is running
if (!(Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️ Warning: Docker Desktop does not seem to be running. Please start it for the best experience." -ForegroundColor Yellow
}

Write-Host "📦 Building and starting containers..." -ForegroundColor Green
docker-compose up --build -d

Write-Host "✅ System is up!" -ForegroundColor Green
Write-Host "🌐 Frontend: http://localhost:8080" -ForegroundColor Blue
Write-Host "📡 Backend:  http://localhost:5000/api/patients" -ForegroundColor Blue

Write-Host "`nTo view logs, run: docker-compose logs -f" -ForegroundColor Gray
