"""Interface gráfica do Xadrex (tkinter, já vem com o Python): a MESMA partida do xadrex.py, jogada pela janela.

O laço da partida, o relógio automático, o anti-empate, o estado salvo e o log são os do xadrex.py, sem cópia: ele
roda numa thread e só a entrada e a saída mudam. O que ele perguntaria no terminal aparece na caixa de texto da
janela, e o instante da 1ª tecla e do ENTER vão para o relógio automático como no leitor de teclas do terminal.
Se a janela fechar, `interface.py` ou `xadrex.py` retomam do mesmo ponto (partida_atual.json).
Rodar: .venv\\Scripts\\python.exe interface.py
"""
import json
import queue
import threading
import time
import tkinter as tk

import chess

import xadrex

CASA = 64
CLARA, ESCURA, DESTAQUE = "#f0d9b5", "#b58863", "#f6f669"
PECAS = dict(zip("KQRBNPkqrbnp", "♔♕♖♗♘♙♚♛♜♝♞♟"))
NOMES = {chess.KING: "REI", chess.QUEEN: "DAMA", chess.ROOK: "TORRE", chess.BISHOP: "BISPO",
         chess.KNIGHT: "CAVALO", chess.PAWN: "PEÃO"}
FECHADA = object()  # resposta para o xadrex.py quando a janela fecha


def descrever(board, lance):
    """'CAVALO g1 → f3' (+ captura, roque, promoção): para quem move a peça não confundir a casa de origem."""
    peca = NOMES[board.piece_type_at(lance.from_square)]
    texto = f"{peca} {chess.square_name(lance.from_square)} → {chess.square_name(lance.to_square)}"
    if board.is_castling(lance):
        texto += " (roque)"
    elif board.is_capture(lance):
        alvo = board.piece_at(lance.to_square)
        texto += f" captura {NOMES[alvo.piece_type]}" if alvo else " captura PEÃO (en passant)"
    if lance.promotion:
        texto += f" promove a {NOMES[lance.promotion]}"
    return texto


def ler_estado():
    """(est, board) da partida salva, ou None (sem partida, ou arquivo ilegível)."""
    try:
        est = json.loads(xadrex.ESTADO.read_text(encoding="utf-8-sig"))  # -sig: aceita arquivo com BOM
        board = chess.Board()
        for u in est["lances"]:
            board.push_uci(u)
        return est, board
    except (OSError, ValueError, KeyError):
        return None


class Ponte:
    """Troca a entrada e a saída do xadrex.py (thread da partida) pela janela (thread do tkinter)."""

    def __init__(self):
        self.para_janela = queue.Queue()   # ("texto", s) | ("pergunta", prompt, com_teclas) | ("fim", None)
        self.respostas = queue.Queue()     # (texto, 1ª tecla, ENTER) ou FECHADA

    def print(self, *args, sep=" ", end="\n", **_):
        self.para_janela.put(("texto", sep.join(str(a) for a in args) + end))

    def _perguntar(self, prompt, com_teclas):
        self.para_janela.put(("pergunta", prompt, com_teclas))
        r = self.respostas.get()
        if r is FECHADA:
            raise EOFError  # partida(): volta sem mexer no estado salvo
        return r

    def input(self, prompt=""):
        return self._perguntar(prompt, False)[0]

    def ler_linha(self, prompt):
        return self._perguntar(prompt, True)

    def instalar(self):
        # nomes globais do módulo xadrex têm precedência sobre os embutidos: print/input dele passam pela janela
        xadrex.print, xadrex.input, xadrex.ler_linha = self.print, self.input, self.ler_linha
        xadrex.desenhar = lambda board: None  # o tabuleiro é desenhado na janela

    def rodar(self):
        try:
            xadrex.main()
        except EOFError:
            pass  # janela fechada numa pergunta inicial
        except Exception as e:  # erro inesperado: mostra em vez de sumir com a janela
            self.print(f"!! erro: {e!r}. A partida salva continua guardada; rode de novo para retomar.")
        finally:
            self.para_janela.put(("fim", None))


class Janela:
    def __init__(self, root, ponte):
        self.root, self.ponte = root, ponte
        self.primeira = None  # instante da 1ª tecla da pergunta atual
        self.aberta = False   # há pergunta esperando resposta
        root.title("Xadrex — III Chess Challenge")
        root.protocol("WM_DELETE_WINDOW", self.fechar)
        self.canvas = tk.Canvas(root, width=8 * CASA, height=8 * CASA, highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=5, padx=10, pady=10, sticky="n")
        lado = tk.Frame(root)
        lado.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        root.columnconfigure(1, weight=1)
        self.titulo = tk.Label(lado, font=("Segoe UI", 13, "bold"), anchor="w")
        self.titulo.pack(fill="x")
        self.lance = tk.Label(lado, font=("Segoe UI", 22, "bold"), anchor="w", justify="left", wraplength=420)
        self.lance.pack(fill="x", pady=6)
        self.saida = tk.Text(lado, height=14, width=58, font=("Consolas", 10), state="disabled", wrap="word")
        self.saida.pack(fill="both", expand=True)
        self.pergunta = tk.Label(lado, font=("Segoe UI", 12, "bold"), anchor="w", justify="left", wraplength=420)
        self.pergunta.pack(fill="x", pady=(8, 2))
        self.entrada = tk.Entry(lado, font=("Consolas", 20))
        self.entrada.pack(fill="x")
        self.entrada.bind("<Key>", self.tecla)
        self.entrada.bind("<Return>", lambda e: self.enviar())
        self.relogio = tk.Button(lado, text="BATI O RELÓGIO  (ENTER vazio)", font=("Segoe UI", 13, "bold"),
                                 bg="#c8f7c5", command=self.bati, state="disabled")
        self.relogio.pack(fill="x", pady=6)
        self.desenhar_tabuleiro()
        self.entrada.focus_set()
        self.root.after(50, self.receber)

    # ---------- entrada ----------
    def tecla(self, evento):
        if self.aberta and self.primeira is None and evento.keysym not in ("Return", "Tab"):
            self.primeira = time.monotonic()  # como o leitor do terminal: o nosso relógio corre desde a 1ª tecla

    def enviar(self):
        if not self.aberta:
            return
        enter = time.monotonic()
        texto = self.entrada.get()
        self.entrada.delete(0, "end")
        self.escrever(f"{self.pergunta.cget('text')}{texto}\n")
        self.aberta = False
        self.relogio.config(state="disabled")
        self.ponte.respostas.put((texto, self.primeira or enter, enter))

    def bati(self):
        self.entrada.delete(0, "end")
        self.enviar()
        self.entrada.focus_set()

    # ---------- saída ----------
    def escrever(self, s):
        self.saida.config(state="normal")
        self.saida.insert("end", s)
        self.saida.see("end")
        self.saida.config(state="disabled")

    def receber(self):
        try:
            while True:
                msg = self.ponte.para_janela.get_nowait()
                if msg[0] == "texto":
                    self.escrever(msg[1])
                elif msg[0] == "pergunta":
                    _, prompt, com_teclas = msg
                    # o xadrex.py está parado esperando a resposta: ler o estado salvo agora não disputa o arquivo
                    self.desenhar_tabuleiro()
                    self.pergunta.config(text=prompt)
                    self.primeira, self.aberta = None, True
                    self.relogio.config(state="normal" if prompt.startswith("ENTER ao bater") else "disabled")
                    self.entrada.focus_set()
                else:  # fim da partida (ou do programa)
                    self.pergunta.config(text="Partida encerrada. Pode fechar a janela.")
                    self.entrada.config(state="disabled")
                    self.relogio.config(state="disabled")
                    return
        except queue.Empty:
            pass
        self.root.after(50, self.receber)

    def desenhar_tabuleiro(self):
        lido = ler_estado()
        if lido is None:
            self.titulo.config(text="Nova partida: responda às perguntas abaixo")
            self.lance.config(text="", bg=self.root.cget("bg"))
            self.casas(chess.Board(), chess.WHITE, None)
            return
        est, board = lido
        nossa = chess.WHITE if est["cor"] == "w" else chess.BLACK
        ultimo = board.move_stack[-1] if board.move_stack else None
        self.casas(board, nossa, ultimo)
        aval = est.get("aval_anterior")
        texto_aval = "-" if aval is None else ("mate" if abs(aval) > 90_000 else f"{aval / 100:+.2f}")
        self.titulo.config(text=f"Somos as {'brancas' if nossa else 'pretas'} | lance {board.fullmove_number} | "
                                f"aval {texto_aval} | relógio ~{xadrex.fmt_relogio(est['previsto_ms'])}")
        if ultimo and board.turn != nossa:  # o último lance foi nosso: é o que a equipe tem que mover
            antes = board.copy()
            antes.pop()
            self.lance.config(text="NOSSO LANCE: " + descrever(antes, ultimo), bg="#c8f7c5")
        else:
            self.lance.config(text="Vez do adversário", bg=self.root.cget("bg"))

    def casas(self, board, nossa, ultimo):
        c = self.canvas
        c.delete("all")
        for sq in chess.SQUARES:
            col, lin = chess.square_file(sq), chess.square_rank(sq)
            x, y = (col, 7 - lin) if nossa else (7 - col, lin)  # nossa cor sempre embaixo
            fundo = CLARA if (col + lin) % 2 else ESCURA
            if ultimo and sq in (ultimo.from_square, ultimo.to_square):
                fundo = DESTAQUE
            c.create_rectangle(x * CASA, y * CASA, (x + 1) * CASA, (y + 1) * CASA, fill=fundo, width=0)
            p = board.piece_at(sq)
            if p:
                c.create_text(x * CASA + CASA / 2, y * CASA + CASA / 2, text=PECAS[p.symbol()],
                              font=("Segoe UI Symbol", int(CASA * 0.62)))
            if y == 7:
                c.create_text(x * CASA + CASA - 6, y * CASA + CASA - 8, text=chess.FILE_NAMES[col], font=("Segoe UI", 9))
            if x == 0:
                c.create_text(7, y * CASA + 9, text=str(lin + 1), font=("Segoe UI", 9))

    def fechar(self):
        # o estado já foi salvo no último lance; matar o motor solta a thread se ela estiver no meio da busca
        self.ponte.respostas.put(FECHADA)
        xadrex.matar_motor()
        self.root.destroy()


def iniciar():
    ponte = Ponte()
    ponte.instalar()
    raiz = tk.Tk()
    janela = Janela(raiz, ponte)
    threading.Thread(target=ponte.rodar, daemon=True).start()
    return raiz, janela


if __name__ == "__main__":
    iniciar()[0].mainloop()
