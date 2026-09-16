@echo off
echo Starting CargoProof API...
start "CargoProof API" cmd /k "npm run server"
timeout /t 2 >nul
echo Starting frontend...
start "CargoProof Frontend" cmd /k "npm run frontend"
echo Open http://localhost:5173
