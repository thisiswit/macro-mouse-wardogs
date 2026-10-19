@echo off
rem Abre o Macro Mouse sem janela de console. Usa o "pyw" (lancador do Python),
rem que o instalador sempre coloca no PATH, e o "pythonw" se ele nao existir.
where pyw >nul 2>nul && (start "" pyw "%~dp0MacroMouse.pyw" & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0MacroMouse.pyw" & exit /b 0)
echo Python nao encontrado. Siga o passo "Instalar o Python" do README.md.
pause
