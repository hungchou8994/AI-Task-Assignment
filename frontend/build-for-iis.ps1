# Build Frontend for IIS deployment
# Generates optimized static files in dist/

param(
    [string]$OutputPath = "dist"
)

Write-Host "Building Frontend for production..." -ForegroundColor Green

# Check if Node.js is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js is not installed. Please install Node.js first."
    exit 1
}

# Check if bun is installed (preferred) or npm
$packageManager = "npm"
if (Get-Command bun -ErrorAction SilentlyContinue) {
    $packageManager = "bun"
    Write-Host "Using Bun package manager" -ForegroundColor Cyan
} else {
    Write-Host "Using NPM package manager" -ForegroundColor Cyan
}

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    if ($packageManager -eq "bun") {
        bun install
    } else {
        npm install
    }
}

# Build for production
Write-Host "Building application..." -ForegroundColor Yellow
if ($packageManager -eq "bun") {
    bun run build
} else {
    npm run build
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed!"
    exit 1
}

# Check if dist folder was created
if (-not (Test-Path $OutputPath)) {
    Write-Error "Build output not found at $OutputPath"
    exit 1
}

# Copy web.config to dist folder
$webConfigSource = "web.config"
$webConfigDest = "$OutputPath\web.config"

if (Test-Path $webConfigSource) {
    Write-Host "Copying web.config to $OutputPath..." -ForegroundColor Yellow
    Copy-Item $webConfigSource -Destination $webConfigDest -Force
} else {
    Write-Warning "web.config not found. You may need to create it manually."
}

Write-Host "✓ Build completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Output directory: $OutputPath" -ForegroundColor Cyan
Write-Host "Total files: $((Get-ChildItem -Path $OutputPath -Recurse -File).Count)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Copy $OutputPath folder to your IIS server"
Write-Host "2. Create a new IIS website pointing to the dist folder"
Write-Host "3. Make sure URL Rewrite module is installed"
Write-Host "4. Ensure backend service is running on localhost:8000"
