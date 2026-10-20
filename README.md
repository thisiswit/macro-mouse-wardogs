# Macro Mouse

Repositório: <https://github.com/thisiswit/macro-mouse-wardogs>

Auto-clicker para Windows, com janela. Você segura um atalho (por exemplo **Ctrl + Shift + Z** ou o botão lateral do mouse) e o mouse clica sozinho, muito rápido. Soltou, parou.

- Liga e desliga por um botão na janela
- Atalhos de teclado, do mouse ou combinações (Ctrl/Shift/Alt + tecla)
- Modo **segurar** (clica enquanto segura) ou **alternar** (aperta liga, aperta de novo desliga)
- Velocidade ajustável (cliques por segundo)
- Só precisa do Python. Nenhuma outra instalação.

> ⚠️ Jogos online com anti-cheat podem banir quem usa auto-clicker. Use por sua conta e risco.

## Sumário

1. [Requisitos](#requisitos)
2. [Caminho A: Windows](#caminho-a-windows) (recomendado)
3. [Caminho B: WSL (Linux dentro do Windows)](#caminho-b-wsl-linux-dentro-do-windows)
4. [Como usar](#como-usar)
5. [Problemas comuns](#problemas-comuns)
6. [Arquivos do projeto](#arquivos-do-projeto)

---

## Requisitos

- **Windows 10 ou 11.**
- **Python 3.11 ou mais novo, instalado no Windows.** O passo a passo abaixo instala para você.

**E no Linux?** O Macro Mouse usa recursos do próprio Windows para ouvir o teclado e o mouse e para clicar. Por isso:

- **Linux "de verdade"** (Ubuntu, Fedora etc. instalado direto no computador): **não funciona**.
- **WSL** (o Linux que roda dentro do Windows): **funciona**. Você abre o app pelo terminal do Linux, mas quem roda é o Python do Windows. É o [Caminho B](#caminho-b-wsl-linux-dentro-do-windows).

**Qual caminho escolher?**

- Só quer usar → **Caminho A**.
- Você já trabalha no terminal do WSL e quer abrir o app de lá → **Caminho B**.

**Sobre os comandos:** eles usam `$HOME` (no PowerShell) e `~` (no Linux), que já apontam para a sua pasta de usuário, e descobrem sozinhos onde ficam a Área de Trabalho e o Python. Não precisa trocar nenhum nome ou caminho: é só copiar e colar.

---

## Caminho A: Windows

### A1. Abrir o PowerShell

Aperte a tecla **Windows**, digite `PowerShell` e aperte **Enter**.

Todos os comandos do Caminho A são colados nessa janela. Para colar, use **Ctrl + V** ou **clique com o botão direito**. Depois aperte **Enter**.

### A2. Instalar o Python

> Já tem Python? Rode `py --version`. Se aparecer `Python 3.11` ou mais novo, pule para o [A3](#a3-baixar-o-macro-mouse).

Copie e cole:

```powershell
winget install -e --id Python.Python.3.13 --scope user --source winget --accept-source-agreements --accept-package-agreements
```

Espere aparecer `Instalado com êxito` (ou `Successfully installed`).

**Feche o PowerShell e abra de novo.** Isso é obrigatório: a janela antiga não enxerga o Python recém-instalado. Depois confira:

```powershell
py --version
py -c "import tkinter; print('tkinter OK')"
```

Deve aparecer algo como:

```
Python 3.13.15
tkinter OK
```

<details>
<summary><b>Apareceu "winget não é reconhecido"? Instale o Python pelo site</b></summary>

1. Abra <https://www.python.org/downloads/windows/> e baixe o **Windows installer (64-bit)** da versão mais nova.
2. Abra o arquivo baixado.
3. Na primeira tela, **marque a caixa "Add python.exe to PATH"** (fica embaixo).
4. Clique em **Install Now** e espere terminar.
5. Feche e abra o PowerShell de novo e rode os comandos de conferência acima.

</details>

### A3. Baixar o Macro Mouse

Escolha **uma** das opções. As duas colocam o programa na pasta `MacroMouse`, dentro da sua pasta de usuário.

**Opção 1: com Git**

Instale o Git:

```powershell
winget install -e --id Git.Git --source winget --accept-source-agreements --accept-package-agreements
```

**Feche e abra o PowerShell de novo** e baixe o projeto:

```powershell
git clone https://github.com/thisiswit/macro-mouse-wardogs.git "$HOME\MacroMouse"
```

**Opção 2: sem Git (baixa o ZIP)**

```powershell
$pasta = "$HOME\MacroMouse"
if (Test-Path $pasta) {
    "A pasta $pasta já existe. Apague ou renomeie essa pasta e rode de novo."
} else {
    $zip = "$env:TEMP\macro-mouse-wardogs.zip"
    curl.exe -fL -o $zip https://github.com/thisiswit/macro-mouse-wardogs/archive/refs/heads/main.zip
    Expand-Archive $zip -DestinationPath "$pasta-tmp" -Force
    Move-Item (Get-ChildItem "$pasta-tmp" -Directory)[0].FullName $pasta
    Remove-Item "$pasta-tmp", $zip -Recurse -Force
    "Pronto: $pasta"
}
```

> O ZIP é baixado na pasta temporária do Windows e apagado no fim, então não importa onde fica a sua pasta Downloads.

**Conferir** (deve responder `True`):

```powershell
Test-Path "$HOME\MacroMouse\MacroMouse.pyw"
```

### A4. Abrir o app

```powershell
& "$HOME\MacroMouse\iniciar.bat"
```

Outro jeito: abra a pasta com `explorer "$HOME\MacroMouse"` e dê **dois cliques em `iniciar.bat`**.

A janela do **Macro Mouse** abre com o botão verde **LIGADO**. Pronto, já está funcionando. Veja [Como usar](#como-usar).

> O app só funciona com a janela aberta. Pode **minimizar** à vontade. Se **fechar** a janela, o app para.

### A5. (Opcional) Ícone na Área de Trabalho

Cria um ícone **Macro Mouse** na Área de Trabalho, que abre o app direto. O comando acha o app sozinho, esteja ele no Windows (passo A3) ou no WSL (passo B3):

```powershell
$app = "$HOME\MacroMouse\MacroMouse.pyw"
if (-not (Test-Path $app) -and (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    $app = wsl.exe -e bash -c 'wslpath -w ~/macro-mouse/MacroMouse.pyw' 2>$null
}
if ($app -and (Test-Path -LiteralPath "$app")) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Macro Mouse.lnk")
    $lnk.TargetPath = (Get-Command pyw).Source
    $lnk.Arguments = "`"$app`""
    $lnk.WorkingDirectory = Split-Path $app
    $lnk.Save()
    "Ícone criado na Área de Trabalho, abrindo: $app"
} else {
    "Não achei o Macro Mouse. Confira o passo A3 (ou o B3, se você usa o WSL)."
}
```

### A6. (Opcional) Abrir junto com o Windows

Faz o Macro Mouse abrir sozinho toda vez que você liga o computador. Assim como o A5, acha o app no Windows ou no WSL:

```powershell
$app = "$HOME\MacroMouse\MacroMouse.pyw"
if (-not (Test-Path $app) -and (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    $app = wsl.exe -e bash -c 'wslpath -w ~/macro-mouse/MacroMouse.pyw' 2>$null
}
if ($app -and (Test-Path -LiteralPath "$app")) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Startup'))\Macro Mouse.lnk")
    $lnk.TargetPath = (Get-Command pyw).Source
    $lnk.Arguments = "`"$app`""
    $lnk.WorkingDirectory = Split-Path $app
    $lnk.Save()
    "Pronto: o Macro Mouse vai abrir junto com o Windows ($app)"
} else {
    "Não achei o Macro Mouse. Confira o passo A3 (ou o B3, se você usa o WSL)."
}
```

Para **desfazer** (parar de abrir com o Windows):

```powershell
Remove-Item "$([Environment]::GetFolderPath('Startup'))\Macro Mouse.lnk"
```

---

## Caminho B: WSL (Linux dentro do Windows)

Aqui o projeto fica dentro do Linux (WSL) e você abre o app com um comando no terminal do Ubuntu. O app em si roda no Windows, porque o Python do Linux não enxerga o teclado e o mouse do Windows. Por isso o Python precisa estar instalado **no Windows** (passo B2).

### B1. Instalar o WSL

> Já tem WSL com Ubuntu? Pule para o [B2](#b2-instalar-o-python-no-windows).

1. Aperte a tecla **Windows**, digite `PowerShell`, clique com o botão direito em **Windows PowerShell** e escolha **Executar como administrador**.
2. Copie e cole:

```powershell
wsl --install
```

3. **Reinicie o computador** se ele pedir.
4. Abra o **Ubuntu** pelo menu Iniciar. Na primeira vez ele pede um **nome de usuário** e uma **senha**. A senha não aparece enquanto você digita, e isso é normal.

### B2. Instalar o Python no Windows

Faça os passos [A1](#a1-abrir-o-powershell) e [A2](#a2-instalar-o-python) do Caminho A, num **PowerShell normal** (não precisa ser administrador).

Depois, **no terminal do Ubuntu**, confira se o Linux enxerga o Python do Windows:

```bash
py.exe --version
```

Deve aparecer `Python 3.13.15` (ou parecido). Se aparecer `command not found`, feche o Ubuntu e abra de novo. Se continuar, veja [Problemas comuns](#problemas-comuns).

### B3. Baixar o Macro Mouse dentro do WSL

No terminal do Ubuntu:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/thisiswit/macro-mouse-wardogs.git ~/macro-mouse
```

> O `sudo` pede a senha que você criou no B1.

### B4. Abrir o app

```bash
cd ~/macro-mouse
chmod +x iniciar.sh
./iniciar.sh
```

A janela do **Macro Mouse** abre no Windows e o terminal fica livre na hora. Pode fechar o terminal que o app continua aberto.

### B5. (Opcional) Comando `macromouse`

Para abrir o app de qualquer pasta só digitando `macromouse`. Funciona no bash e no zsh, e rodar de novo não duplica nada:

```bash
rc="$HOME/.$(basename "$SHELL")rc"
grep -qs "alias macromouse=" "$rc" || echo "alias macromouse='$HOME/macro-mouse/iniciar.sh'" >> "$rc"
source "$rc"
```

Teste:

```bash
macromouse
```

### B6. (Opcional) Ícone na Área de Trabalho ou abrir junto com o Windows

Rode no **PowerShell** (não no Ubuntu) os mesmos comandos do [A5](#a5-opcional-ícone-na-área-de-trabalho) ou do [A6](#a6-opcional-abrir-junto-com-o-windows). Quando o app não está numa pasta do Windows, eles perguntam ao WSL onde fica o `~/macro-mouse` e criam o atalho para lá.

> Se o WSL estiver desligado, o app demora alguns segundos a mais para abrir, porque o Windows liga o WSL para ler os arquivos.

---

## Como usar

| Parte da janela | O que faz |
|---|---|
| **LIGADO / DESLIGADO** (botão grande) | Liga ou desliga tudo. Desligado, as teclas e os botões do mouse funcionam normalmente. |
| **Cliques por segundo** | A velocidade. Vale na hora. Muitos jogos e sites não registram mais que 50 a 100. |
| **Avisos** | **Bolinha perto do mouse**: aparece ao lado do ponteiro enquanto o auto-clique está ativo. **Som ao começar e parar**: um bipe subindo quando começa e descendo quando para. Dá para desligar cada um. |
| **Atalhos**, caixinha **Usar** | Desmarque para pausar só aquele atalho. |
| **Atalhos**, **Modo** e **Botão clicado** | Dá para trocar direto na lista. |
| **Atalhos**, **Remover** | Apaga o atalho. |
| **● clicando** | Aparece ao lado do atalho que está clicando agora. |
| **Novo atalho** | Clique em **Gravar** e aperte a combinação no teclado ou o botão do mouse. Ou digite o atalho (veja a tabela abaixo). Escolha o modo e o botão e clique em **Adicionar**. |

### Atalhos que já vêm configurados

| Atalho | Modo | O que acontece |
|---|---|---|
| **Ctrl + Shift + Z** | segurar | Clique esquerdo enquanto as três teclas estiverem seguradas |
| **Botão lateral da frente** (MOUSE5) | segurar | Clique esquerdo enquanto você segura |
| **Botão lateral de trás** (MOUSE4) | segurar | Clique direito enquanto você segura |
| **F6** | alternar | Aperta uma vez, começa a clicar. Aperta de novo, para. |

### Nomes para digitar um atalho

| Tipo | Nomes |
|---|---|
| Mouse | `MOUSE4` (lateral de trás), `MOUSE5` (lateral da frente), `MEIO` (rodinha), `DIREITO`, `ESQUERDO` |
| Teclas de função | `F1` a `F24` |
| Letras e números | `A` a `Z`, `0` a `9`, `NUM0` a `NUM9` (teclado numérico) |
| Outras | `ESPACO`, `ENTER`, `TAB`, `CAPSLOCK`, `SHIFT`, `CTRL`, `ALT`, `INSERT`, `DELETE`, `HOME`, `END`, `PAGEUP`, `PAGEDOWN`, `PAUSE`, `SCROLLLOCK` |
| Combinações | Junte `CTRL`, `SHIFT` e/ou `ALT` com `+`. Exemplos: `CTRL+SHIFT+Z`, `ALT+X`, `SHIFT+MOUSE5` |

### Bom saber

- **Como saber se está clicando:** a bolinha ao lado do ponteiro pisca em **verde** enquanto clica e fica **amarela** quando está pausada (ponteiro em cima do app). A letra dentro dela é o botão clicado: **E** (esquerdo), **D** (direito) ou **M** (meio). Ela não atrapalha: os cliques passam através dela e ela não tira o foco do jogo. Em jogos em tela cheia "exclusiva" ela pode não aparecer, e aí o som avisa.
- **Combinações:** aperte primeiro o Ctrl/Shift/Alt e por último a tecla final. No modo segurar, soltar **qualquer** tecla do atalho para os cliques.
- **Trocar sem soltar:** se dois atalhos "segurar" terminam na mesma tecla (ex.: `CTRL+Z` e `CTRL+SHIFT+Z`), dá para trocar de um para o outro segurando o Z e apertando ou soltando o Shift.
- **Cliques limpos:** mesmo segurando Ctrl e Shift, os cliques saem como cliques normais (não viram Ctrl+clique).
- **O atalho é "engolido":** com o app ligado, a tecla final do atalho não chega no programa que está aberto. Por exemplo, o botão lateral deixa de "voltar página" no navegador e Ctrl+Shift+Z deixa de ser "refazer". Para voltar ao normal, desligue o app ou desmarque o atalho.
- **Onde clica:** o clique acontece onde o ponteiro do mouse estiver. Com o ponteiro **em cima da janela do Macro Mouse**, os cliques ficam pausados (aparece "● pausado"), para o app não apertar os próprios botões. Leve o ponteiro para onde quer clicar.
- **Configuração salva:** tudo fica salvo sozinho no arquivo `config.json`, na pasta do app. Para voltar à configuração original, feche o app, apague o `config.json` e abra de novo.
- **Só uma janela:** abrir o app de novo com ele já aberto só traz a janela para frente.

---

## Problemas comuns

**Dou dois cliques no `iniciar.bat` e aparece "Python nao encontrado"**
→ O Python não está instalado ou o terminal foi aberto antes de instalar. Faça o [A2](#a2-instalar-o-python), feche tudo e tente de novo.

**Abre a Microsoft Store quando digito `python`**
→ Esse `python` é só um atalho do Windows para a loja. Instale pelo [A2](#a2-instalar-o-python) e use `py` nos comandos.

**Nada acontece ao abrir (nenhuma janela, nenhum erro)**
→ Abra o app pelo terminal para ver a mensagem de erro. No PowerShell (Caminho A):

```powershell
py "$HOME\MacroMouse\MacroMouse.pyw"
```

No terminal do Ubuntu (Caminho B):

```bash
py.exe "$(wslpath -w ~/macro-mouse/MacroMouse.pyw)"
```

**Erro `No module named 'tkinter'`**
→ O Python foi instalado sem a parte de janelas. Baixe o instalador em <https://www.python.org/downloads/windows/>, abra, escolha **Modify**, marque **tcl/tk and IDLE** e conclua.

**Funciona no navegador mas não no jogo**
→ Alguns jogos rodam como administrador, e o Windows bloqueia cliques de programas comuns neles. Feche o Macro Mouse, clique com o botão direito em `iniciar.bat` e escolha **Executar como administrador**.

**O botão lateral do mouse não faz nada**
→ Programas do mouse (Logitech G HUB, Razer Synapse etc.) às vezes trocam a função desses botões. Clique em **Gravar** e aperte o botão lateral para ver o que o app recebe, e adicione o atalho com esse nome. Se nada for gravado, volte o botão para a função padrão ("voltar"/"avançar") no programa do mouse.

**Aparece "O Windows protegeu o computador"**
→ Clique em **Mais informações** e depois em **Executar assim mesmo**. Isso acontece quando os arquivos foram baixados pelo navegador. Para tirar o bloqueio de vez, rode no PowerShell:

```powershell
Get-ChildItem "$HOME\MacroMouse" | Unblock-File
```

**WSL: `Permission denied` ao rodar `./iniciar.sh`**
→ O arquivo perdeu a permissão de execução (acontece quando ele é editado pelo Windows). Rode:

```bash
chmod +x ~/macro-mouse/iniciar.sh
```

**WSL: `py.exe: command not found` ou `cmd.exe: command not found`**
→ A integração do WSL com o Windows está desligada. Veja o arquivo de configuração:

```bash
cat /etc/wsl.conf
```

Se aparecer `enabled = false` ou `appendWindowsPath = false`, abra o arquivo com `sudo nano /etc/wsl.conf` e troque para `true`. Salve com **Ctrl+O**, **Enter** e saia com **Ctrl+X**. Depois, no PowerShell do Windows:

```powershell
wsl --shutdown
```

Abra o Ubuntu de novo.

---

## Arquivos do projeto

| Arquivo | Para que serve |
|---|---|
| `MacroMouse.pyw` | A janela do app |
| `autoclicker.py` | O motor: escuta teclado e mouse e faz os cliques |
| `iniciar.bat` | Abre o app no Windows (dois cliques) |
| `iniciar.sh` | Abre o app pelo terminal do WSL |
| `config.json` | Suas configurações. É criado sozinho na primeira vez que o app abre. |
