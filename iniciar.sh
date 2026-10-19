#!/usr/bin/env bash
# Abre o Macro Mouse no Windows a partir do terminal do WSL.
# O app roda no Python do Windows: o Python do WSL não enxerga o teclado e o mouse do Windows.
set -e
app="$(wslpath -w "$(dirname "$(realpath "$0")")/MacroMouse.pyw")"
# Abre o pythonw solto do terminal (sem herdar a saída dele): o comando volta na hora
# e fechar o terminal não fecha o app.
abrir='
import os, subprocess, sys
pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
subprocess.Popen([pythonw, sys.argv[1]], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, creationflags=subprocess.DETACHED_PROCESS)
'
# py.exe é o lançador do Python; python.exe pode ser só o atalho da Microsoft Store.
for python in py.exe python.exe; do
    if command -v "$python" >/dev/null && "$python" -c "$abrir" "$app"; then
        exit 0
    fi
done
echo 'Python do Windows não encontrado. Siga o passo "Instalar o Python" do README.md.' >&2
exit 1
