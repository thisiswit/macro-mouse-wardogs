"""
Macro Mouse: janela para ligar/desligar o auto-clicker e configurar os atalhos.

Abra com dois cliques em iniciar.bat (ou: pythonw MacroMouse.pyw).
As configurações ficam salvas em config.json, nesta mesma pasta.
"""

import ctypes
import json
import math
import queue
import struct
import threading
import time
import tkinter as tk
import traceback
import winsound
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk

from autoclicker import CLIQUES, MODOS, AutoClicker, criar_gatilho, kernel32, user32

TITULO = "Macro Mouse"
ARQUIVO_CONFIG = Path(__file__).with_name("config.json")
PADRAO = {
    "ligado": True,
    "cps": 50,
    "indicador": True,
    "som": True,
    "atalhos": [
        {"atalho": "CTRL+SHIFT+Z", "modo": "segurar",  "botao": "esquerdo", "habilitado": True},
        {"atalho": "MOUSE5",       "modo": "segurar",  "botao": "esquerdo", "habilitado": True},
        {"atalho": "MOUSE4",       "modo": "segurar",  "botao": "direito",  "habilitado": True},
        {"atalho": "F6",           "modo": "alternar", "botao": "esquerdo", "habilitado": True},
    ],
}

VERDE, VERDE_ESCURO, VERDE_CLARO = "#16a34a", "#15803d", "#4ade80"
CINZA, CINZA_ESCURO = "#6b7280", "#4b5563"
AMARELO = "#f59e0b"
FONTE_ATALHO = ("Segoe UI", 10, "bold")

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_LAYERED, WS_EX_NOACTIVATE = 0x20, 0x80, 0x80000, 0x08000000
HWND_TOPMOST = ctypes.c_void_p(-1)
SWP_NOSIZE, SWP_NOACTIVATE = 0x0001, 0x0010
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
kernel32.CreateMutexW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
user32.FindWindowW.restype = ctypes.c_void_p
user32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
user32.GetWindowLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int)
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint)


def gerar_som(notas, volume=0.3, taxa=22050):
    """Arquivo WAV (em memória) tocando as notas [(frequência em Hz, milissegundos), ...]."""
    dados = bytearray()
    borda = taxa // 200  # 5 ms subindo e descendo o volume, para não estalar
    for freq, ms in notas:
        n = taxa * ms // 1000
        for i in range(n):
            envelope = min(1.0, i / borda, (n - 1 - i) / borda)
            dados += struct.pack("<h", int(32767 * volume * envelope * math.sin(2 * math.pi * freq * i / taxa)))
    return (b"RIFF" + struct.pack("<I", 36 + len(dados)) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, taxa, taxa * 2, 2, 16)
            + b"data" + struct.pack("<I", len(dados)) + bytes(dados))


SOM_COMECOU = gerar_som([(880, 60), (1320, 80)])  # sobe: começou a clicar
SOM_PAROU = gerar_som([(1320, 60), (880, 80)])    # desce: parou


class Som:
    """Toca os avisos numa thread própria (o PlaySound só volta quando o som acaba)."""

    def __init__(self):
        self._fila = queue.Queue()
        threading.Thread(target=self._tocar_fila, daemon=True).start()

    def tocar(self, wav):
        self._fila.put(wav)

    def _tocar_fila(self):
        for wav in iter(self._fila.get, None):
            try:
                winsound.PlaySound(wav, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
            except RuntimeError:
                pass  # computador sem saída de som


class Indicador:
    """Bolinha que acompanha o ponteiro do mouse enquanto o auto-clique está ativo.

    É uma janela sem borda, sempre por cima, que o mouse atravessa (os cliques
    passam direto por ela) e que nunca pega o foco do jogo/programa em uso.
    """

    TRANSPARENTE = "#ff00ff"  # cor que o Windows deixa de desenhar

    def __init__(self, raiz):
        escala = raiz.winfo_fpixels("1i") / 96  # zoom da tela (125%, 150%...)
        self.tamanho = round(26 * escala)
        self.distancia = round(16 * escala)  # fica ao lado do ponteiro, não embaixo dele
        self.janela = tk.Toplevel(raiz, bg=self.TRANSPARENTE)
        self.janela.title("Macro Mouse indicador")
        self.janela.overrideredirect(True)
        self.janela.attributes("-topmost", True, "-transparentcolor", self.TRANSPARENTE)
        self.janela.geometry(f"{self.tamanho}x{self.tamanho}")
        self.tela = tk.Canvas(self.janela, width=self.tamanho, height=self.tamanho,
                              bg=self.TRANSPARENTE, highlightthickness=0)
        self.tela.pack()
        self.janela.update_idletasks()
        self.hwnd = int(self.janela.wm_frame(), 16)
        estilo = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, estilo | WS_EX_LAYERED | WS_EX_TRANSPARENT
                                 | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        self._desenho = None

    def mostrar(self, cor, letras):
        if self._desenho != (cor, letras):
            t = self.tamanho
            self.tela.delete("all")
            self.tela.create_oval(1, 1, t - 2, t - 2, fill=cor, outline="white", width=2)
            self.tela.create_text(t / 2, t / 2, text=letras, fill="white", font=("Segoe UI", 8, "bold"))
            self._desenho = (cor, letras)
        ponto = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(ponto))
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, ponto.x + self.distancia, ponto.y + self.distancia,
                            0, 0, SWP_NOSIZE | SWP_NOACTIVATE)

    def esconder(self):
        # A janela continua lá, mas sem nada desenhado ela fica invisível.
        if self._desenho is not None:
            self.tela.delete("all")
            self._desenho = None


def carregar_config():
    """Lê o config.json (ou usa o padrão). Devolve (opções, [(Gatilho, habilitado)], avisos)."""
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
    opcoes = {
        "ligado": bool(dados.get("ligado", True)),
        "cps": cps,
        "indicador": bool(dados.get("indicador", True)),
        "som": bool(dados.get("som", True)),
    }
    return opcoes, atalhos, avisos


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
        self._estava_clicando = False

        opcoes, atalhos, avisos = carregar_config()
        self.motor.definir_ligado(opcoes["ligado"])
        self.motor.cps = opcoes["cps"]

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
        self.cps = tk.StringVar(value=str(opcoes["cps"]))
        caixa_cps = ttk.Spinbox(linha_cps, from_=1, to=1000, increment=5, width=6, textvariable=self.cps)
        caixa_cps.pack(side="left", padx=(8, 0))
        caixa_cps.bind("<FocusOut>", lambda _: self.cps.set(str(self.motor.cps)))
        self.cps.trace_add("write", self._cps_mudou)

        # Avisos de que está clicando
        linha_avisos = ttk.Frame(quadro)
        linha_avisos.grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(linha_avisos, text="Avisos:").pack(side="left")
        self.usar_indicador = tk.BooleanVar(value=opcoes["indicador"])
        self.usar_som = tk.BooleanVar(value=opcoes["som"])
        ttk.Checkbutton(linha_avisos, text="Bolinha perto do mouse", variable=self.usar_indicador,
                        command=self.salvar).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(linha_avisos, text="Som ao começar e parar", variable=self.usar_som,
                        command=self.salvar).pack(side="left", padx=(12, 0))
        self.indicador = Indicador(raiz)
        self.som = Som()

        # Atalhos
        self.lista = ttk.LabelFrame(quadro, text="Atalhos", padding=(10, 6))
        self.lista.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        for coluna, titulo in enumerate(("Usar", "Atalho", "Modo", "Botão clicado")):
            ttk.Label(self.lista, text=titulo, foreground=CINZA).grid(row=0, column=coluna, padx=4, sticky="w")
        self.vazio = ttk.Label(self.lista, text="Nenhum atalho ainda. Adicione um abaixo.", foreground=CINZA)
        for gatilho, habilitado in atalhos:
            self.linhas.append(LinhaAtalho(self, gatilho, habilitado))
        self._reposicionar()

        # Novo atalho
        novo = ttk.LabelFrame(quadro, text="Novo atalho", padding=(10, 6))
        novo.grid(row=5, column=0, sticky="ew", pady=(12, 0))
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
        self.status.grid(row=6, column=0, sticky="w")

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
            "indicador": self.usar_indicador.get(),
            "som": self.usar_som.get(),
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
        """Roda a cada 30 ms: mostra quem está clicando, cuida dos avisos e recebe o atalho gravado."""
        try:
            gravado = self.motor.capturas.get_nowait()
        except queue.Empty:
            pass
        else:
            self.novo_atalho.set(gravado)
            self.gravando = False
            self.botao_gravar.config(text="Gravar")

        pausado = self.motor.pausado
        clicando, botoes = [], []
        for linha in self.linhas:
            ativo = self.motor.ligado and linha.gatilho.ativo
            linha.estado.config(text=("● pausado" if pausado else "● clicando") if ativo else "",
                                foreground=CINZA if pausado else VERDE)
            if ativo:
                clicando.append(linha.gatilho.nome)
                botoes.append(linha.gatilho.botao)
        self._avisar(bool(clicando), pausado, botoes)

        if self.gravando:
            texto = "Aperte a combinação no teclado ou um botão do mouse…"
        elif not self.motor.ligado:
            texto = "Desligado."
        elif clicando and pausado:
            texto = "Pausado: tire o mouse de cima desta janela para clicar."
        elif clicando:
            texto = "Clicando: " + ", ".join(clicando)
        else:
            texto = "Pronto. Use um atalho para clicar."
        self.status.config(text=texto)
        self.raiz.after(30, self._atualizar)

    def _avisar(self, clicando, pausado, botoes):
        """Som quando começa/para de clicar e bolinha no ponteiro enquanto clica."""
        if clicando != self._estava_clicando:
            self._estava_clicando = clicando
            if self.usar_som.get():
                self.som.tocar(SOM_COMECOU if clicando else SOM_PAROU)
        if clicando and self.usar_indicador.get():
            if pausado:
                cor = AMARELO
            else:
                cor = VERDE if int(time.monotonic() * 6) % 2 else VERDE_CLARO  # pisca 3x por segundo
            letras = "".join(dict.fromkeys(b[0].upper() for b in botoes))  # E, D ou M
            self.indicador.mostrar(cor, letras)
        else:
            self.indicador.esconder()

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
