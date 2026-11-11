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
import tkinter as tk
from tkinter import simpledialog

import chess

import xadrex

CASA = 64
CLARA, ESCURA, DESTAQUE = "#f0d9b5", "#b58863", "#f6f669"
PECAS = dict(zip("KQRBNPkqrbnp", "♔♕♖♗♘♙♚♛♜♝♞♟"))
NOMES = {chess.KING: "REI", chess.QUEEN: "DAMA", chess.ROOK: "TORRE", chess.BISHOP: "BISPO",
         chess.KNIGHT: "CAVALO", chess.PAWN: "PEÃO"}
FECHADA = object()  # resposta para o xadrex.py quando a janela fecha
PEDE_LANCE = ("ENTER ao bater", "Lance do advers")  # perguntas do xadrex.py que aceitam 'u' e 'pos'


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
        board = chess.Board(est.get("fen", chess.STARTING_FEN))
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
        xadrex.avisar_relogios = lambda rel: self.para_janela.put(("relogios", rel))

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
        # ---------- os dois relógios, ao vivo (clique para acertar) ----------
        self.rel = None  # último aviso do xadrex.py: {"nos", "adv", "correndo", "desde"}
        caixa = tk.Frame(lado)
        caixa.pack(fill="x", pady=(0, 6))
        self.rel_lbl = {}
        for lado_rel in ("adv", "nos"):
            quadro = tk.Frame(caixa, relief="ridge", bd=3, cursor="hand2")
            quadro.pack(side="left", fill="x", expand=True, padx=(0, 6) if lado_rel == "adv" else 0)
            nome = tk.Label(quadro, font=("Segoe UI", 11, "bold"))
            nome.pack(fill="x")
            mostrador = tk.Label(quadro, font=("Consolas", 30, "bold"))
            mostrador.pack(fill="x")
            for w in (quadro, nome, mostrador):
                w.bind("<Button-1>", lambda e, l=lado_rel: self.editar_relogio(l))
            self.rel_lbl[lado_rel] = (quadro, nome, mostrador)
        tk.Label(lado, text="clique num relógio para acertá-lo", font=("Segoe UI", 9), fg="#666").pack(anchor="e")
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
        # ---------- editor livre de posição ----------
        self.nossa, self.edicao, self.selecao = chess.WHITE, None, None
        self.mostrado = chess.Board()  # tabuleiro na tela: a edição parte dele (ler o arquivo na busca pode falhar)
        self.passos = []               # tabuleiros de antes de cada clique da edição (desfazer dentro da edição)
        self.pendente = []             # comandos para mandar quando o programa pedir o lance (motor pensando)
        self.vez = tk.StringVar(value="w")
        botoes = tk.Frame(lado)
        botoes.pack(fill="x")
        self.editar_btn = tk.Button(botoes, font=("Segoe UI", 11, "bold"), command=self.alternar)
        self.editar_btn.pack(side="left", fill="x", expand=True)
        tk.Button(botoes, text="↶ DESFAZER JOGADA", font=("Segoe UI", 11, "bold"), bg="#f7d5c5",
                  command=self.desfazer).pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.pausa_btn = tk.Button(botoes, text="⏸ PAUSAR RELÓGIOS", font=("Segoe UI", 11, "bold"),
                                   command=self.pausar)
        self.pausa_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.marcar_edicao(False)
        self.painel = tk.Frame(root)  # aparece só no modo de edição, embaixo do tabuleiro
        self.painel.grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))
        self.painel.grid_remove()
        tk.Label(self.painel, text="Clique na peça e depois na casa | botão direito apaga | peça abaixo + casa = põe"
                 " | DESFAZER JOGADA desfaz o último clique", font=("Segoe UI", 10)).grid(row=0, column=0,
                                                                                       columnspan=14, sticky="w")
        for i, s in enumerate("KQRBNPkqrbnp"):
            tk.Button(self.painel, text=PECAS[s], font=("Segoe UI Symbol", 18), width=2,
                      command=lambda s=s: self.escolher(chess.Piece.from_symbol(s))).grid(row=1, column=i)
        tk.Radiobutton(self.painel, text="vez das brancas", variable=self.vez, value="w").grid(row=2, column=0, columnspan=4, sticky="w")
        tk.Radiobutton(self.painel, text="vez das pretas", variable=self.vez, value="b").grid(row=2, column=4, columnspan=4, sticky="w")
        tk.Button(self.painel, text="DESCARTAR EDIÇÃO", command=self.cancelar).grid(row=2, column=8, columnspan=4)
        self.canvas.bind("<Button-1>", self.clique)
        self.canvas.bind("<Button-3>", self.apagar)
        self.desenhar_tabuleiro()
        self.entrada.focus_set()
        self.root.after(50, self.receber)
        self.contar()

    # ---------- entrada ----------
    def tecla(self, evento):
        if self.aberta and self.primeira is None and evento.keysym not in ("Return", "Tab"):
            self.primeira = xadrex.time.monotonic()  # como o leitor do terminal: o nosso relógio corre desde a 1ª tecla

    def enviar(self):
        if not self.aberta:
            return
        enter = xadrex.time.monotonic()
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
                elif msg[0] == "relogios":
                    self.rel = msg[1]
                    if self.rel.get("cor") and self.nossa != (self.rel["cor"] == "w") and self.edicao is None:  # 1º save
                        self.nossa = self.rel["cor"] == "w"
                        self.casas(self.mostrado, self.nossa, ())
                elif msg[0] == "pergunta":
                    _, prompt, com_teclas = msg
                    # o xadrex.py está parado esperando a resposta: ler o estado salvo agora não disputa o arquivo
                    self.desenhar_tabuleiro()
                    self.pergunta.config(text=prompt)
                    self.primeira, self.aberta = None, True
                    self.relogio.config(state="normal" if prompt.startswith("ENTER ao bater") else "disabled")
                    self.entrada.focus_set()
                    if self.pendente and prompt.startswith(PEDE_LANCE):  # um por pergunta, na ordem
                        self.mandar(self.pendente.pop(0))
                else:  # fim da partida (ou do programa)
                    if self.rel:  # congela os dois relógios onde estão
                        self.rel = {**self.rel, "nos": self.valor_relogio("nos"), "adv": self.valor_relogio("adv"),
                                    "correndo": None}
                    self.pergunta.config(text="Partida encerrada. Pode fechar a janela.")
                    self.entrada.config(state="disabled")
                    self.relogio.config(state="disabled")
                    return
        except queue.Empty:
            pass
        self.root.after(50, self.receber)

    def desenhar_tabuleiro(self):
        if self.edicao is not None:  # no meio da edição a posição da tela é a que está sendo montada
            return
        lido = ler_estado()
        if lido is None:
            self.titulo.config(text="Nova partida: responda às perguntas abaixo")
            self.lance.config(text="", bg=self.root.cget("bg"))
            self.mostrado = chess.Board()  # nossa cor: a do aviso dos relógios, se já veio
            self.casas(self.mostrado, self.nossa, ())
            return
        est, board = lido
        self.mostrado = board
        nossa = self.nossa = chess.WHITE if est["cor"] == "w" else chess.BLACK
        ultimo = board.move_stack[-1] if board.move_stack else None
        self.casas(board, nossa, (ultimo.from_square, ultimo.to_square) if ultimo else ())
        aval = est.get("aval_anterior")
        texto_aval = "-" if aval is None else ("mate" if abs(aval) > 90_000 else f"{aval / 100:+.2f}")
        self.titulo.config(text=f"Somos as {'brancas' if nossa else 'pretas'} | lance {board.fullmove_number} | "
                                f"aval {texto_aval}")
        if ultimo and board.turn != nossa:  # o último lance foi nosso: é o que a equipe tem que mover
            antes = board.copy()
            antes.pop()
            self.lance.config(text="NOSSO LANCE: " + descrever(antes, ultimo), bg="#c8f7c5")
        else:
            self.lance.config(text="Vez do adversário", bg=self.root.cget("bg"))

    def casas(self, board, nossa, destaques):
        c = self.canvas
        c.delete("all")
        for sq in chess.SQUARES:
            col, lin = chess.square_file(sq), chess.square_rank(sq)
            x, y = (col, 7 - lin) if nossa else (7 - col, lin)  # nossa cor sempre embaixo
            fundo = CLARA if (col + lin) % 2 else ESCURA
            if sq in destaques:
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

    # ---------- editor livre ----------
    def marcar_edicao(self, ligada):
        self.editar_btn.config(text="✎ EDIÇÃO LIGADA — clique para aplicar" if ligada else "✎ EDITAR POSIÇÃO",
                               bg="#f6f669" if ligada else self.root.cget("bg"))

    def alternar(self):
        if self.edicao is None:
            self.editar()
        else:
            self.concluir()

    def editar(self):
        lido = ler_estado()  # já tem o lance adversário recém-digitado; se o arquivo estiver ocupado, usa a tela
        self.edicao, self.selecao, self.passos = (lido[1] if lido else self.mostrado).copy(), None, []
        self.vez.set("w" if self.edicao.turn else "b")
        self.original = self.fen_editada()
        self.painel.grid()
        self.marcar_edicao(True)
        self.redesenhar_edicao()

    def concluir(self):
        fen = self.fen_editada()
        mudou = fen != self.original
        self.cancelar()
        if mudou:
            self.mandar("pos " + fen)

    def mandar(self, texto):
        """Responde com `texto` se o programa está pedindo o lance; senão (motor pensando) manda no próximo pedido."""
        if self.aberta and self.pergunta.cget("text").startswith(PEDE_LANCE):
            self.entrada.delete(0, "end")
            self.entrada.insert(0, texto)
            self.enviar()
        else:
            self.pendente.append(texto)
            self.escrever(f"(o motor está pensando: '{texto.split()[0]}' vai assim que ele terminar)\n")

    def desfazer(self):
        if self.edicao is None:
            self.mandar("u")  # o xadrex.py desfaz o par de lances (peças comidas voltam) ou a última edição
        elif self.passos:
            self.edicao, self.selecao = self.passos.pop(), None
            self.redesenhar_edicao()
        else:
            self.escrever("(nada para desfazer nesta edição; DESCARTAR EDIÇÃO volta ao tabuleiro do jogo)\n")

    # ---------- relógios ----------
    def valor_relogio(self, lado):
        r = self.rel
        andou = xadrex.time.monotonic() - r["desde"] if r["correndo"] == lado and r["desde"] is not None else 0
        return r[lado] - max(0.0, andou) * 1000

    def pausar(self):
        """Pausa/continua o tempo do programa inteiro: os dois relógios, o relógio automático e a conta do motor."""
        pausado = xadrex.relogio_pausavel.alternar()
        self.pausa_btn.config(text="▶ CONTINUAR RELÓGIOS" if pausado else "⏸ PAUSAR RELÓGIOS",
                              bg="#f6f669" if pausado else self.root.cget("bg"))
        self.escrever("(relógios PAUSADOS)\n" if pausado else "(relógios voltaram a correr)\n")

    def contar(self):
        """Redesenha os dois relógios 5x por segundo; o que está correndo fica verde (vermelho abaixo de 1 min,
        amarelo na pausa)."""
        pausado = xadrex.relogio_pausavel.desde is not None
        for lado, (quadro, nome, mostrador) in self.rel_lbl.items():
            cor = self.nossa if lado == "nos" else not self.nossa
            nome.config(text=("NÓS" if lado == "nos" else "ADVERSÁRIO") + f" ({'brancas' if cor else 'pretas'})")
            if self.rel is None:
                texto, fundo, tinta = "-:--", self.root.cget("bg"), "black"
            else:
                ms = self.valor_relogio(lado)
                texto = ("-" if ms < 0 else "") + xadrex.fmt_relogio(abs(ms))
                fundo = self.root.cget("bg")
                if self.rel["correndo"] == lado:
                    fundo = "#f6f669" if pausado else "#c8f7c5"
                    if pausado:
                        nome.config(text=nome.cget("text") + " ⏸")
                tinta = "#c00000" if ms < 60_000 else "black"
            mostrador.config(text=texto, fg=tinta)
            for w in (quadro, nome, mostrador):
                w.config(bg=fundo)
        self.root.after(200, self.contar)

    def editar_relogio(self, lado):
        # não vai para a fila: com o motor pensando o valor digitado já chegaria velho
        if not (self.aberta and self.pergunta.cget("text").startswith(PEDE_LANCE)):
            self.escrever("(espere o programa pedir o lance para acertar o relógio)\n")
            return
        quem = "NOSSO relógio" if lado == "nos" else "relógio do ADVERSÁRIO"
        atual = xadrex.fmt_relogio(self.valor_relogio(lado)) if self.rel else ""
        r = simpledialog.askstring("Acertar relógio", f"Quanto o {quem} mostra agora? (mm:ss)",
                                   initialvalue=atual, parent=self.root)
        if r is None:  # cancelou
            return
        try:
            xadrex.ler_relogio(r.strip())
        except ValueError:
            self.escrever(f"(relógio inválido: '{r}'. Use mm:ss, ex.: 8:31)\n")
            return
        self.mandar("relogio " + ("adv " if lado == "adv" else "") + r.strip())

    def redesenhar_edicao(self):
        sel = self.selecao
        self.casas(self.edicao, self.nossa, (sel,) if isinstance(sel, int) else ())
        texto = "nova peça: " + PECAS[sel.symbol()] if isinstance(sel, chess.Piece) else "clique numa peça"
        self.titulo.config(text=f"EDITANDO A POSIÇÃO ({texto}) — desligue a edição para aplicar")

    def casa_em(self, evento):
        x, y = int(evento.x // CASA), int(evento.y // CASA)
        if not (0 <= x < 8 and 0 <= y < 8):
            return None
        col, lin = (x, 7 - y) if self.nossa else (7 - x, y)  # inverso de casas()
        return chess.square(col, lin)

    def escolher(self, peca):
        if self.edicao is not None:
            self.selecao = peca
            self.redesenhar_edicao()

    def clique(self, evento):
        sq = self.casa_em(evento)
        if self.edicao is None or sq is None:
            return
        sel = self.selecao
        if isinstance(sel, chess.Piece):        # pôr peça nova da paleta
            self.passos.append(self.edicao.copy())
            self.edicao.set_piece_at(sq, sel)
            self.selecao = None
        elif isinstance(sel, int):              # mover a peça escolhida (por cima do que houver)
            if sq != sel:
                self.passos.append(self.edicao.copy())
                self.edicao.set_piece_at(sq, self.edicao.remove_piece_at(sel))
            self.selecao = None
        elif self.edicao.piece_at(sq):
            self.selecao = sq
        self.redesenhar_edicao()

    def apagar(self, evento):
        sq = self.casa_em(evento)
        if self.edicao is not None and sq is not None and self.edicao.piece_at(sq):
            self.passos.append(self.edicao.copy())
            self.edicao.remove_piece_at(sq)
            self.selecao = None
            self.redesenhar_edicao()

    def fen_editada(self):
        b = self.edicao.copy(stack=False)
        b.turn = self.vez.get() == "w"
        b.castling_rights = b.clean_castling_rights()  # roque só se rei e torre continuam na casa original
        b.ep_square = None
        return b.fen()

    def cancelar(self):
        self.edicao, self.selecao = None, None
        self.painel.grid_remove()
        self.marcar_edicao(False)
        if self.aberta:  # o xadrex.py está parado na pergunta: ler o estado agora não disputa o arquivo
            self.desenhar_tabuleiro()
        else:
            self.casas(self.mostrado, self.nossa, ())

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
