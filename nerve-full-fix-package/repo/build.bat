@echo off
REM Build script for Nerve
REM Uses cargo from Rust stable MSVC toolchain

echo Building Nerve...

REM Try to find cargo in common locations
if exist "C:\Program Files\Rust stable MSVC 1.93\bin\cargo.exe" (
    set CARGO="C:\Program Files\Rust stable MSVC 1.93\bin\cargo.exe"
) else if exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
    set CARGO="%USERPROFILE%\.cargo\bin\cargo.exe"
) else (
    set CARGO=cargo
)

%CARGO% build --release

if %ERRORLEVEL% neq 0 (
    echo Build failed!
    exit /b 1
)

echo Build successful: target\release\nerve.exe
