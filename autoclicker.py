"""
Motor do auto-clicker: escuta o teclado e o mouse no Windows inteiro e clica
sozinho quando um atalho dispara. A janela fica em MacroMouse.pyw.
"""

import sys

if sys.platform != "win32":
    sys.exit("Rode com o Python do Windows (não o do WSL/Linux).")

import ctypes
import queue
import threading
import time
from ctypes import wintypes

TECLAS = {
    **{f"F{i}": 0x6F + i for i in range(1, 25)},
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): 0x30 + d for d in range(10)},
    **{f"NUM{d}": 0x60 + d for d in range(10)},
    "ESPACO": 0x20, "ENTER": 0x0D, "TAB": 0x09, "CAPSLOCK": 0x14,
    "SHIFT": 0xA0, "CTRL": 0xA2, "ALT": 0xA4,
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22, "PAUSE": 0x13, "SCROLLLOCK": 0x91,
}
# O hook diferencia esquerda e direita; aqui os dois lados viram o mesmo nome.
NOME_DA_TECLA = {vk: nome for nome, vk in TECLAS.items()} | {0xA1: "SHIFT", 0xA3: "CTRL", 0xA5: "ALT"}
BOTOES_DO_MOUSE = ("ESQUERDO", "DIREITO", "MEIO", "MOUSE4", "MOUSE5")
MODIFICADORES = {"CTRL": (0xA2, 0xA3), "SHIFT": (0xA0, 0xA1), "ALT": (0xA4, 0xA5)}  # (esquerda, direita)
TECLA_MASCARA = 0xE8  # código de tecla sem uso, ver soltar_modificadores()

# "segurar": clica enquanto o atalho estiver pressionado; soltou qualquer tecla dele, para.
# "alternar": aperta uma vez liga, aperta de novo desliga.
MODOS = ("segurar", "alternar")

# botão clicado -> (flag de apertar, flag de soltar) do SendInput
CLIQUES = {
    "esquerdo": (0x0002, 0x0004),
    "direito":  (0x0008, 0x0010),
    "meio":     (0x0020, 0x0040),
}

# Marca colocada em tudo que este programa simula, para os hooks não
# confundirem com o que você aperta de verdade.
MARCA = 0x4155544F

# ------------------------------- Win32 -------------------------------------

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_QUIT = 0x0012
WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104
WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
MENSAGENS_DO_MOUSE = {
    0x0201: ("ESQUERDO", True), 0x0202: ("ESQUERDO", False),
    0x0204: ("DIREITO", True),  0x0205: ("DIREITO", False),
    0x0207: ("MEIO", True),     0x0208: ("MEIO", False),
}
PM_NOREMOVE = 0
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x0001, 0x0002
TECLAS_ESTENDIDAS = (0xA3, 0xA5)  # CTRL e ALT da direita

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                                wintypes.UINT, wintypes.UINT)
user32.PeekMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
user32.GetCursorPos.restype = wintypes.BOOL
user32.WindowFromPoint.argtypes = (wintypes.POINT,)
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentProcessId.restype = wintypes.DWORD

MEU_PID = kernel32.GetCurrentProcessId()

# ---------------------------------------------------------------------------


class Gatilho:
    def __init__(self, nome, tecla, modificadores, modo, botao):
        self.nome = nome                    # como aparece na tela, ex.: "CTRL+SHIFT+Z"
        self.tecla = tecla                  # última tecla do atalho, a que dispara
        self.modificadores = modificadores  # as que precisam já estar seguradas
        self.modo = modo
        self.botao = botao
        self.ativo = False      # clicando agora?
        self.segurando = False  # o atalho continua pressionado desde que disparou?


def ler_atalho(texto):
    """'shift+ctrl+z' -> ('CTRL+SHIFT+Z', 'Z', {'CTRL', 'SHIFT'})"""
    if not texto.strip():
        raise ValueError("Escolha um atalho.")
    *modificadores, tecla = [parte.strip().upper() for parte in texto.split("+")]
    if tecla not in TECLAS and tecla not in BOTOES_DO_MOUSE:
        raise ValueError(f'"{tecla}" não existe (no atalho "{texto}").')
    for m in modificadores:
        if m not in MODIFICADORES:
            raise ValueError(f'"{m}" não pode vir antes do "+" no atalho "{texto}" '
                             f'(use CTRL, SHIFT ou ALT).')
    nome = "+".join([*(m for m in MODIFICADORES if m in modificadores), tecla])
    return nome, tecla, frozenset(modificadores)


def criar_gatilho(atalho, modo, botao):
    """criar_gatilho("CTRL+SHIFT+Z", "segurar", "esquerdo") -> Gatilho. ValueError se inválido."""
    modo, botao = modo.lower(), botao.lower()
    if modo not in MODOS:
        raise ValueError(f'modo "{modo}" inválido (use "segurar" ou "alternar").')
    if botao not in CLIQUES:
        raise ValueError(f'botão "{botao}" inválido (use "esquerdo", "direito" ou "meio").')
    return Gatilho(*ler_atalho(atalho), modo, botao)


def montar_clique(botao):
    apertar, soltar = CLIQUES[botao]
    entradas = (INPUT * 2)()
    for entrada, flag in zip(entradas, (apertar, soltar)):
        entrada.type = INPUT_MOUSE
        entrada.mi.dwFlags = flag
        entrada.mi.dwExtraInfo = MARCA
    return entradas


def soltar_modificadores(modificadores):
    """Diz ao Windows que CTRL/SHIFT/ALT foram soltos, mesmo que você ainda os segure.

    Antes vai uma tecla sem uso (a "máscara"): sem ela, o Windows veria
    CTRL+SHIFT ou ALT apertados e soltos sozinhos, o que troca o layout do
    teclado ou abre o menu da janela.
    """
    eventos = [(TECLA_MASCARA, False), (TECLA_MASCARA, True)]
    eventos += [(vk, True) for m in modificadores for vk in MODIFICADORES[m]]
    entradas = (INPUT * len(eventos))()
    for entrada, (vk, soltar) in zip(entradas, eventos):
        entrada.type = INPUT_KEYBOARD
        entrada.ki.wVk = vk
        entrada.ki.wScan = user32.MapVirtualKeyW(vk, 0)
        entrada.ki.dwFlags = ((KEYEVENTF_KEYUP if soltar else 0)
                              | (KEYEVENTF_EXTENDEDKEY if vk in TECLAS_ESTENDIDAS else 0))
        entrada.ki.dwExtraInfo = MARCA
    user32.SendInput(len(eventos), entradas, ctypes.sizeof(INPUT))


def mouse_sobre_o_app():
    """O ponteiro está em cima de uma janela deste programa?

    Aí não clicamos: o clique cairia nos botões do próprio app (desligaria o app,
    apertaria "Adicionar", "Remover"...).
    """
    ponto = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(ponto))
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.WindowFromPoint(ponto), ctypes.byref(pid))
    return pid.value == MEU_PID


def botao_do_mouse(w_param, mouse_data):
    """Traduz uma mensagem do hook de mouse em (nome do botão, apertou?)."""
    if w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
        lateral = {1: "MOUSE4", 2: "MOUSE5"}.get(mouse_data >> 16)
        return lateral, w_param == WM_XBUTTONDOWN
    return MENSAGENS_DO_MOUSE.get(w_param, (None, False))


class AutoClicker:
    """Hooks de teclado/mouse numa thread e os cliques em outra, em segundo plano.

    A interface mexe em `cps`, definir_ligado() e definir_gatilhos() enquanto roda.
    """

    def __init__(self):
        self.gatilhos = []
        self.cps = 50
        self.ligado = True
        self.capturas = queue.Queue()  # atalhos gravados depois de gravar()
        self.pausado = False  # tem atalho ativo, mas o ponteiro está em cima do app
        self._gravando = False
        self._seguradas = set()  # teclas/botões fisicamente pressionados agora
        self._engolidas = set()  # dispararam um atalho; ficam escondidas do Windows até soltar
        self._soltas = set()     # CTRL/SHIFT/ALT seguradas que o Windows acha que foram soltas
        self._acordar = threading.Event()
        self._rodando = False
        self._erro = None
        self._thread_hooks = self._thread_cliques = None
        self._id_thread_hooks = None

    # --- usado pela interface ---

    def iniciar(self):
        self._rodando = True
        pronto = threading.Event()
        self._thread_hooks = threading.Thread(target=self._loop_hooks, args=(pronto,), daemon=True)
        self._thread_hooks.start()
        pronto.wait()
        if self._erro:
            self._rodando = False
            raise self._erro
        self._thread_cliques = threading.Thread(target=self._loop_cliques, daemon=True)
        self._thread_cliques.start()

    def parar(self):
        self._rodando = False
        self._acordar.set()
        if self._id_thread_hooks:
            user32.PostThreadMessageW(self._id_thread_hooks, WM_QUIT, 0, 0)
        for thread in (self._thread_hooks, self._thread_cliques):
            if thread:
                thread.join(1)

    def definir_ligado(self, ligado):
        self.ligado = ligado
        if not ligado:
            for g in self.gatilhos:
                g.ativo = g.segurando = False

    def definir_gatilhos(self, gatilhos):
        antigos, self.gatilhos = self.gatilhos, list(gatilhos)
        for g in antigos:
            if g not in self.gatilhos:
                g.ativo = g.segurando = False

    def gravar(self):
        """A próxima tecla/botão apertado não dispara nada e vai para `capturas`."""
        self._gravando = True

    def cancelar_gravacao(self):
        self._gravando = False

    # --- chamado pelos hooks ---

    def evento(self, nome, apertou):
        """Retorna True para bloquear o evento original."""
        if not apertou:
            self._seguradas.discard(nome)
            self._soltas.discard(nome)
            for g in self.gatilhos:
                if g.segurando and (nome == g.tecla or nome in g.modificadores):
                    g.segurando = False
                    if g.modo == "segurar":
                        g.ativo = False
            engolida = nome in self._engolidas
            self._engolidas.discard(nome)
            if nome in MODIFICADORES:
                self._trocar_atalho_segurado()
            return engolida

        self._seguradas.add(nome)
        # Repetição automática de uma tecla segurada que o Windows não deve ver de novo
        # (a última tecla de um atalho, ou um CTRL/SHIFT/ALT que já soltamos para ele).
        if nome in self._engolidas or nome in self._soltas:
            return True
        if self._gravando:
            return self._gravar(nome)
        if not self.ligado:
            return False
        g = self._atalho_disparado(nome)
        if g is None:
            # Se este CTRL/SHIFT/ALT trocou o atalho segurado, o atalho novo já o inclui
            # e o Windows não precisa vê-lo (senão o clique sairia com Shift+clique).
            return nome in MODIFICADORES and self._trocar_atalho_segurado()
        self._disparar(g)
        return True

    def _disparar(self, g):
        self._engolidas.add(g.tecla)
        if g.modificadores:
            self._soltar(g.modificadores)
        g.segurando = True
        g.ativo = True if g.modo == "segurar" else not g.ativo
        self._acordar.set()

    def _soltar(self, modificadores):
        soltar_modificadores(modificadores)
        self._soltas.update(modificadores)

    def _trocar_atalho_segurado(self):
        """CTRL/SHIFT/ALT mudou com a última tecla de um atalho "segurar" ainda apertada.

        Passa a valer o atalho que bate com o que está segurado agora. Ex.: segurando
        CTRL+Z e apertando SHIFT, vira CTRL+SHIFT+Z; soltando o SHIFT, volta para CTRL+Z.
        Retorna True se algum atalho novo disparou.
        """
        if not self.ligado or self._gravando:
            return False
        disparou = False
        for tecla in {g.tecla for g in self.gatilhos if g.modo == "segurar"} & self._engolidas:
            atual = next((g for g in self.gatilhos if g.segurando and g.tecla == tecla), None)
            novo = self._atalho_disparado(tecla)
            if novo is atual or (atual and atual.modo != "segurar") or (novo and novo.modo != "segurar"):
                continue
            if atual:
                atual.segurando = atual.ativo = False
            if novo:
                self._disparar(novo)
                disparou = True
        return disparou

    def _gravar(self, nome):
        # CTRL/SHIFT/ALT sozinhos ainda não fecham o atalho, e o clique esquerdo
        # continua livre para usar a janela (dá para digitar "ESQUERDO" à mão).
        if nome in MODIFICADORES or nome == "ESQUERDO":
            return False
        self._gravando = False
        self._engolidas.add(nome)
        modificadores = [m for m in MODIFICADORES if m in self._seguradas]
        if modificadores:
            self._soltar(modificadores)
        self.capturas.put("+".join([*modificadores, nome]))
        return True

    def _atalho_disparado(self, tecla):
        """Atalho cuja última tecla é `tecla` e cujos modificadores estão segurados.

        Se mais de um servir (ex.: "Z" e "CTRL+SHIFT+Z"), vence o mais completo.
        """
        candidatos = [g for g in self.gatilhos
                      if g.tecla == tecla and g.modificadores <= self._seguradas]
        return max(candidatos, key=lambda g: len(g.modificadores), default=None)

    # --- threads ---

    def _loop_cliques(self):
        cliques = {botao: montar_clique(botao) for botao in CLIQUES}
        proximo = time.perf_counter()
        while self._rodando:
            botoes = {g.botao for g in self.gatilhos if g.ativo} if self.ligado else set()
            if not botoes:
                self.pausado = False
                self._acordar.wait(0.25)
                self._acordar.clear()
                proximo = time.perf_counter()
                continue
            self.pausado = mouse_sobre_o_app()
            if not self.pausado:
                for botao in botoes:
                    user32.SendInput(2, cliques[botao], ctypes.sizeof(INPUT))
            proximo += 1.0 / self.cps
            espera = proximo - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            else:
                proximo = time.perf_counter()  # atrasou: não compensa com rajada

    def _loop_hooks(self, pronto):
        @HOOKPROC
        def hook_teclado(n_code, w_param, l_param):
            if n_code == 0:
                info = KBDLLHOOKSTRUCT.from_address(l_param)
                if info.dwExtraInfo != MARCA:
                    nome = NOME_DA_TECLA.get(info.vkCode)
                    if nome and self.evento(nome, w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)):
                        return 1
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        @HOOKPROC
        def hook_mouse(n_code, w_param, l_param):
            if n_code == 0:
                info = MSLLHOOKSTRUCT.from_address(l_param)
                if info.dwExtraInfo != MARCA:
                    nome, apertou = botao_do_mouse(w_param, info.mouseData)
                    if nome and self.evento(nome, apertou):
                        return 1
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        msg = wintypes.MSG()
        # Cria a fila de mensagens da thread antes de alguém mandar WM_QUIT para ela.
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)
        self._id_thread_hooks = kernel32.GetCurrentThreadId()
        modulo = kernel32.GetModuleHandleW(None)
        hooks = [user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_teclado, modulo, 0),
                 user32.SetWindowsHookExW(WH_MOUSE_LL, hook_mouse, modulo, 0)]
        if all(hooks):
            pronto.set()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        else:
            self._erro = ctypes.WinError(ctypes.get_last_error())
            pronto.set()
        for h in filter(None, hooks):
            user32.UnhookWindowsHookEx(h)
