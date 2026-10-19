"""
Macro Mouse: janela para ligar/desligar o auto-clicker e configurar os atalhos.

Abra com dois cliques em iniciar.bat (ou: pythonw MacroMouse.pyw).
As configurações ficam salvas em config.json, nesta mesma pasta.
"""

import ctypes
import json
import queue
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox, ttk

from autoclicker import CLIQUES, MODOS, AutoClicker, criar_gatilho, kernel32, user32

TITULO = "Macro Mouse"
ARQUIVO_CONFIG = Path(__file__).with_name("config.json")
PADRAO = {
    "ligado": True,
    "cps": 50,
    "atalhos": [
        {"atalho": "CTRL+SHIFT+Z", "modo": "segurar",  "botao": "esquerdo", "habilitado": True},
        {"atalho": "MOUSE5",       "modo": "segurar",  "botao": "esquerdo", "habilitado": True},
        {"atalho": "MOUSE4",       "modo": "segurar",  "botao": "direito",  "habilitado": True},
        {"atalho": "F6",           "modo": "alternar", "botao": "esquerdo", "habilitado": True},
    ],
}

VERDE, VERDE_ESCURO = "#16a34a", "#15803d"
CINZA, CINZA_ESCURO = "#6b7280", "#4b5563"
FONTE_ATALHO = ("Segoe UI", 10, "bold")

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
kernel32.CreateMutexW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
user32.FindWindowW.restype = ctypes.c_void_p
user32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)


def carregar_config():
    """Lê o config.json (ou usa o padrão). Devolve (ligado, cps, [(Gatilho, habilitado)], avisos)."""
    avisos = []
    try:
        dados = json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        dados = PADRAO
    except (OSError, ValueError) as erro:
        avisos.append(f"Não consegui ler o config.json ({erro}). Usando a configuração padrão.")
        dados = PADRAO
    if not isinstance(dados, dict):
        avisos.append("O config.json está num formato estranho. Usando a configuração padrão.")
        dados = PADRAO

    cps = dados.get("cps", 50)
    if not isinstance(cps, int) or not 1 <= cps <= 1000:
        cps = 50
    atalhos, usados = [], set()
    for item in dados.get("atalhos", []):
        try:
            g = criar_gatilho(item["atalho"], item["modo"], item["botao"])
        except (KeyError, TypeError, AttributeError, ValueError) as erro:
            avisos.append(f"Atalho ignorado {item!r}: {erro}")
            continue
        if (g.tecla, g.modificadores) in usados:
            avisos.append(f"Atalho repetido ignorado: {g.nome}")
            continue
        usados.add((g.tecla, g.modificadores))
        atalhos.append((g, bool(item.get("habilitado", True))))
    return bool(dados.get("ligado", True)), cps, atalhos, avisos


class LinhaAtalho:
    """Uma linha da lista: usar, atalho, modo, botão, estado e remover."""

    def __init__(self, app, gatilho, habilitado):
        self.gatilho = gatilho
        self.habilitado = tk.BooleanVar(value=habilitado)
        self.modo = tk.StringVar(value=gatilho.modo)
        self.botao = tk.StringVar(value=gatilho.botao)
        pai = app.lista
        modo = ttk.Combobox(pai, textvariable=self.modo, values=MODOS, state="readonly", width=9)
        botao = ttk.Combobox(pai, textvariable=self.botao, values=list(CLIQUES), state="readonly", width=9)
        self.estado = ttk.Label(pai, width=10, foreground=VERDE)
        self.widgets = [
            ttk.Checkbutton(pai, variable=self.habilitado, command=app.aplicar),
            ttk.Label(pai, text=gatilho.nome, font=FONTE_ATALHO),
            modo,
            botao,
            self.estado,
            ttk.Button(pai, text="Remover", width=8, command=lambda: app.remover(self)),
        ]
        for caixa in (modo, botao):
            caixa.bind("<<ComboboxSelected>>", lambda _: self._mudou(app))

    def _mudou(self, app):
        self.gatilho = criar_gatilho(self.gatilho.nome, self.modo.get(), self.botao.get())
        app.aplicar()

    def posicionar(self, linha):
        for coluna, widget in enumerate(self.widgets):
            widget.grid(row=linha, column=coluna, padx=4, pady=3, sticky="w")

    def destruir(self):
        for widget in self.widgets:
            widget.destroy()


class App:
    def __init__(self, raiz):
        self.raiz = raiz
        self.motor = AutoClicker()
        self.linhas = []
        self.gravando = False
        self._avisou_salvar = False

        ligado, cps, atalhos, avisos = carregar_config()
        self.motor.definir_ligado(ligado)
        self.motor.cps = cps

        raiz.title(TITULO)
        raiz.resizable(False, False)
        quadro = ttk.Frame(raiz, padding=16)
        quadro.grid(sticky="nsew")
        quadro.columnconfigure(0, weight=1)

        # Liga/desliga
        self.botao_ligar = tk.Button(quadro, font=("Segoe UI", 15, "bold"), fg="white",
                                     activeforeground="white", relief="flat", bd=0,
                                     cursor="hand2", pady=10, command=self.alternar_ligado)
        self.botao_ligar.grid(row=0, column=0, sticky="ew")
        self.dica_ligar = ttk.Label(quadro, foreground=CINZA)
        self.dica_ligar.grid(row=1, column=0, pady=(4, 12))

        # Velocidade
        linha_cps = ttk.Frame(quadro)
        linha_cps.grid(row=2, column=0, sticky="w")
        ttk.Label(linha_cps, text="Cliques por segundo:").pack(side="left")
        self.cps = tk.StringVar(value=str(cps))
        caixa_cps = ttk.Spinbox(linha_cps, from_=1, to=1000, increment=5, width=6, textvariable=self.cps)
        caixa_cps.pack(side="left", padx=(8, 0))
        caixa_cps.bind("<FocusOut>", lambda _: self.cps.set(str(self.motor.cps)))
        self.cps.trace_add("write", self._cps_mudou)

        # Atalhos
        self.lista = ttk.LabelFrame(quadro, text="Atalhos", padding=(10, 6))
        self.lista.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        for coluna, titulo in enumerate(("Usar", "Atalho", "Modo", "Botão clicado")):
            ttk.Label(self.lista, text=titulo, foreground=CINZA).grid(row=0, column=coluna, padx=4, sticky="w")
        self.vazio = ttk.Label(self.lista, text="Nenhum atalho ainda. Adicione um abaixo.", foreground=CINZA)
        for gatilho, habilitado in atalhos:
            self.linhas.append(LinhaAtalho(self, gatilho, habilitado))
        self._reposicionar()

        # Novo atalho
        novo = ttk.LabelFrame(quadro, text="Novo atalho", padding=(10, 6))
        novo.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.novo_atalho = tk.StringVar()
        self.novo_modo = tk.StringVar(value="segurar")
        self.novo_botao = tk.StringVar(value="esquerdo")
        ttk.Entry(novo, textvariable=self.novo_atalho, width=18).grid(row=0, column=0, padx=(0, 4))
        self.botao_gravar = ttk.Button(novo, text="Gravar", width=9, command=self.alternar_gravacao)
        self.botao_gravar.grid(row=0, column=1, padx=4)
        ttk.Combobox(novo, textvariable=self.novo_modo, values=MODOS, state="readonly",
                     width=9).grid(row=0, column=2, padx=4)
        ttk.Combobox(novo, textvariable=self.novo_botao, values=list(CLIQUES), state="readonly",
                     width=9).grid(row=0, column=3, padx=4)
        ttk.Button(novo, text="Adicionar", command=self.adicionar).grid(row=0, column=4, padx=(4, 0))
        ttk.Label(novo, foreground=CINZA, justify="left", text=(
            "Clique em Gravar e aperte a combinação, ou digite (ex.: CTRL+SHIFT+Z, MOUSE5, F6).\n"
            "segurar: clica enquanto segura   ·   alternar: aperta liga, aperta de novo desliga"
        )).grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))

        self.status = ttk.Label(quadro, padding=(0, 12, 0, 0))
        self.status.grid(row=5, column=0, sticky="w")

        raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self._pintar_botao()
        self.motor.iniciar()
        self.aplicar()
        self._atualizar()
        if avisos:
            messagebox.showwarning(TITULO, "\n".join(avisos), parent=raiz)

    def aplicar(self):
        """Passa os atalhos marcados para o motor e salva."""
        self.motor.definir_gatilhos([l.gatilho for l in self.linhas if l.habilitado.get()])
        self.salvar()

    def salvar(self):
        dados = {
            "ligado": self.motor.ligado,
            "cps": self.motor.cps,
            "atalhos": [{"atalho": l.gatilho.nome, "modo": l.gatilho.modo, "botao": l.gatilho.botao,
                         "habilitado": l.habilitado.get()} for l in self.linhas],
        }
        try:
            ARQUIVO_CONFIG.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as erro:
            if not self._avisou_salvar:
                self._avisou_salvar = True
                messagebox.showwarning(TITULO, f"Não consegui salvar a configuração:\n{erro}", parent=self.raiz)

    def alternar_ligado(self):
        self.motor.definir_ligado(not self.motor.ligado)
        self._pintar_botao()
        self.salvar()

    def _pintar_botao(self):
        if self.motor.ligado:
            self.botao_ligar.config(text="●  LIGADO", bg=VERDE, activebackground=VERDE_ESCURO)
            self.dica_ligar.config(text="Clique para desligar")
        else:
            self.botao_ligar.config(text="○  DESLIGADO", bg=CINZA, activebackground=CINZA_ESCURO)
            self.dica_ligar.config(text="Clique para ligar. Desligado, teclas e botões funcionam normalmente.")

    def _cps_mudou(self, *_):
        try:
            cps = int(self.cps.get())
        except ValueError:
            return
        if 1 <= cps <= 1000 and cps != self.motor.cps:
            self.motor.cps = cps
            self.salvar()

    def alternar_gravacao(self):
        self.gravando = not self.gravando
        if self.gravando:
            self.motor.gravar()
        else:
            self.motor.cancelar_gravacao()
        self.botao_gravar.config(text="Cancelar" if self.gravando else "Gravar")

    def adicionar(self):
        try:
            g = criar_gatilho(self.novo_atalho.get(), self.novo_modo.get(), self.novo_botao.get())
        except ValueError as erro:
            messagebox.showwarning("Atalho inválido", str(erro), parent=self.raiz)
            return
        if any((l.gatilho.tecla, l.gatilho.modificadores) == (g.tecla, g.modificadores) for l in self.linhas):
            messagebox.showwarning("Atalho repetido", f"{g.nome} já está na lista.", parent=self.raiz)
            return
        self.linhas.append(LinhaAtalho(self, g, True))
        self._reposicionar()
        self.novo_atalho.set("")
        self.aplicar()

    def remover(self, linha):
        linha.destruir()
        self.linhas.remove(linha)
        self._reposicionar()
        self.aplicar()

    def _reposicionar(self):
        for i, linha in enumerate(self.linhas, start=1):
            linha.posicionar(i)
        if self.linhas:
            self.vazio.grid_remove()
        else:
            self.vazio.grid(row=1, column=0, columnspan=6, sticky="w", pady=4)

    def _atualizar(self):
        """Roda a cada 50 ms: mostra quem está clicando e recebe o atalho gravado."""
        try:
            gravado = self.motor.capturas.get_nowait()
        except queue.Empty:
            pass
        else:
            self.novo_atalho.set(gravado)
            self.gravando = False
            self.botao_gravar.config(text="Gravar")

        clicando = []
        for linha in self.linhas:
            ativo = self.motor.ligado and linha.gatilho.ativo
            linha.estado.config(text="● clicando" if ativo else "")
            if ativo:
                clicando.append(linha.gatilho.nome)

        if self.gravando:
            texto = "Aperte a combinação no teclado ou um botão do mouse…"
        elif not self.motor.ligado:
            texto = "Desligado."
        elif clicando:
            texto = "Clicando: " + ", ".join(clicando)
        else:
            texto = "Pronto. Use um atalho para clicar."
        self.status.config(text=texto)
        self.raiz.after(50, self._atualizar)

    def fechar(self):
        self.motor.parar()
        self.raiz.destroy()


def ja_esta_aberto():
    """Se o app já estiver aberto, traz a janela dele para frente e devolve True."""
    global _mutex  # fica aberto até o programa fechar
    _mutex = kernel32.CreateMutexW(None, False, "Local\\MacroMouse")
    if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        return False
    janela = user32.FindWindowW(None, TITULO)
    if janela:
        user32.ShowWindow(janela, SW_RESTORE)
        user32.SetForegroundWindow(janela)
    return True


def mostrar_erro(tipo, valor, tb):
    messagebox.showerror(f"{TITULO}: erro", "".join(traceback.format_exception(tipo, valor, tb)))


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # janela nítida com zoom de tela (125%, 150%...)
    except (AttributeError, OSError):
        pass
    if ja_esta_aberto():
        return
    raiz = tk.Tk()
    raiz.report_callback_exception = mostrar_erro
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Com pythonw não existe console, então o erro aparece numa janela.
        messagebox.showerror(f"{TITULO}: erro", traceback.format_exc())
