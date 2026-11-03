"""Adaptadores dos jogadores da arena (xadrex, xadrex+ae, bea, fraco).

Interface comum (duck typing, sem classe base):
    nome                       -> str
    iniciar_partida(cor, base_ms, inc_s)
    lance(board, relogio_ms)   -> chess.Move   (a arena cronometra esta chamada)
    encerrar_partida()
    eventos                    -> list[str] com falhas recuperadas/calibrações do último lance
"""
import math
import os
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

import chess
import chess.engine

PASTA_XADREX = Path(__file__).resolve().parent.parent  # arena/ fica dentro do repositório do xadrex
EXE_XADREX = PASTA_XADREX / "engines" / "stockfish-windows-x86-64-universal.exe"


def stockfish_padrao():
    """$ARENA_STOCKFISH, senão o stockfish do PATH, senão o .exe em engines/ (Windows). None se nada existir."""
    return (os.environ.get("ARENA_STOCKFISH") or shutil.which("stockfish")
            or (str(EXE_XADREX) if EXE_XADREX.is_file() else None))


STOCKFISH = stockfish_padrao()  # a arena troca por --stockfish antes de criar os adaptadores


class Bea:
    """Reimplementação fiel de chess-challenge/code/index.ipynb, célula 0 (o notebook não é importável:
    usa IPython.display e input()).

    - jogar() (linha 97): popen_uci("/opt/homebrew/bin/stockfish") UMA vez por partida, reutilizado; Threads padrão (1).
    - stockfish() (linhas 50-80), a cada lance: configure Skill Level=20, Move Overhead=15, Hash=5120, depois
      play(clone, Limit(time=2.0)). O python-chess só reenvia setoption quando o valor muda, então os 5 GB de
      Hash são alocados no primeiro lance (dentro do relógio, como no notebook).
    - A linha 74 (promoção automática) nunca dispara (compara Piece com int): o lance do motor é usado como veio.
    """
    nome = "bea"

    def __init__(self):
        self.eventos = []
        self.engine = None

    def iniciar_partida(self, cor, base_ms, inc_s):
        self.encerrar_partida()
        self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)  # fora do relógio, como em jogar()

    def lance(self, board, relogio_ms):
        self.eventos = []
        engine = self.engine
        engine.configure({"Skill Level": 20})
        engine.configure({"Move Overhead": 15})
        engine.configure({"Hash": 5120})
        resultado = engine.play(board.copy(), chess.engine.Limit(time=2.0))
        return resultado.move  # o notebook só aplica se for legal; aqui a arena valida (ilegal = derrota)

    def encerrar_partida(self):
        e, self.engine = self.engine, None
        if e is not None:
            try:
                e.quit()
            except Exception:
                pass


class Fraco:
    """Equipe mais fraca: Stockfish com Skill Level baixo, busca fixa curta e 1 thread. Um processo por partida
    (como o Bea). Não reproduz nenhum programa real; é um adversário de referência para o anti-empate."""
    nome = "fraco"

    def __init__(self, skill=5, tempo_s=1.0):
        self.skill, self.tempo_s = skill, tempo_s
        self.eventos = []
        self.engine = None

    def iniciar_partida(self, cor, base_ms, inc_s):
        self.encerrar_partida()
        self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)  # fora do relógio
        self.engine.configure({"Threads": 1, "Skill Level": self.skill})

    def lance(self, board, relogio_ms):
        self.eventos = []
        return self.engine.play(board.copy(), chess.engine.Limit(time=self.tempo_s)).move

    def encerrar_partida(self):
        e, self.engine = self.engine, None
        if e is not None:
            try:
                e.quit()
            except Exception:
                pass


class Xadrex:
    """Usa o código REAL de xadrex/xadrex.py + tempo.py, reproduzindo o fluxo de `partida()` com o relógio
    automático (commits f091a20 e 215637e).

    `antiempate` vira `xadrex.ANTIEMPATE` (lido por pensar em tempo de execução). A atribuição é feita mesmo que o
    módulo ainda não defina o atributo; nesse caso não tem efeito e `antiempate_no_modulo` fica False.
    Como o motor do xadrex é global no módulo, só cabe UM adaptador Xadrex por processo.

    Diferenças em relação ao programa interativo (todas exigidas pela automação):
    - COMANDO_MOTOR aponta para o binário da arena (--stockfish; OPCOES_MOTOR originais mantidas).
    - Relógio automático com medição perfeita: na arena o relógio volta a correr no instante em que a busca
      começa e toda a parte humana (ouvir, digitar, anunciar, mover, bater) vem depois do lance. Por isso o
      relógio em t0 é o relógio da arena (equivale a relogio_ao_pensar com OUVIR_MS exato e digitação zero) e o
      fechamento do lance anterior passa por tempo.fechar_lance numa linha do tempo virtual que reproduz o gasto
      real. O erro de OUVIR_MS (risco D7) e o ENTER esquecido NÃO são simulados.
    - Leitura do relógio físico só quando xadrex.leitura_obrigatoria() pede (na prática, só antes do 1º lance,
      que ainda não foi medido, e com relógio abaixo de 2 min): calibrar() com o relógio da arena truncado para
      segundos inteiros (o que o operador veria em mm:ss).
    - Não chama jogar_nosso_lance/salvar/iniciar/encerrar: nada é gravado em partida_atual.json nem em logs/.
    - O fluxo antigo (previsto -= gasto + atraso médio, k += 1) foi removido; ele está no commit 1fa1223.
    """

    def __init__(self, antiempate=False):
        sys.dont_write_bytecode = True  # não criar __pycache__ dentro do repo xadrex
        if str(PASTA_XADREX) not in sys.path:
            sys.path.insert(0, str(PASTA_XADREX))
        import tempo
        import xadrex
        xadrex.COMANDO_MOTOR = [STOCKFISH]
        self.antiempate_no_modulo = hasattr(xadrex, "ANTIEMPATE")
        setattr(xadrex, "ANTIEMPATE", bool(antiempate))  # as duas variantes gravam: a base fica explicitamente False
        self.nome = "xadrex+ae" if antiempate else "xadrex"
        self.x, self.tempo = xadrex, tempo
        self.est = None
        self.eventos = []

    def iniciar_partida(self, cor, base_ms, inc_s):
        # mesmo dicionário de iniciar(), sem os campos de arquivo (log/lances) que pensar() não usa
        self.est = {
            "cor": "w" if cor == chess.WHITE else "b",
            "base_s": base_ms / 1000,
            "inc_s": inc_s,
            "previsto_ms": base_ms,
            "k": 0,
            "exigir_leitura": False,
            "medido": False,
            "folga_ms": 0,
            "atraso": asdict(self.tempo.AtrasoHumano()),
            "aval_anterior": None,
        }
        self.nossa = cor
        self.aberto = None  # nosso último lance, à espera do fechamento (o ENTER ao bater o relógio)
        self.x.abrir_motor()  # como main(): motor aberto antes da partida, fora do relógio

    def fechar_anterior(self, relogio_ms):
        """fechar_relogio() do lance anterior. Linha do tempo virtual em segundos: t0 = 0; fim = gasto total do
        lance (busca + atraso, tirado do relógio da arena); inicio = OUVIR_MS depois de t0, para que
        gasto = (fim - inicio) + OUVIR_MS seja exatamente o gasto real (a arena não tem tempo antes de t0)."""
        est, a = self.est, self.aberto
        inc_ms = est["inc_s"] * 1000
        gasto_s = (a["relogio"] - relogio_ms + inc_ms) / 1000
        est["previsto_ms"], gasto, humano = self.tempo.fechar_lance(
            a["relogio"], self.tempo.OUVIR_MS / 1000, 0.0, gasto_s, a["busca"], inc_ms)
        est["medido"] = gasto is not None  # ENTRADA_SIMPLES não se aplica: a arena simula o leitor de teclas
        atraso = self.tempo.AtrasoHumano(**est["atraso"])
        atraso.observar(humano)
        est["atraso"] = asdict(atraso)
        self.eventos.append(f"humano={humano / 1000:.1f}s")

    def lance(self, board, relogio_ms):
        self.eventos = []
        x, est = self.x, self.est
        if self.aberto:
            self.fechar_anterior(relogio_ms)
        # em partida(): o lance adversário entra com leitura se leitura_obrigatoria(); senão relogio_ao_pensar
        if x.leitura_obrigatoria(est):
            leitura = max(0, math.floor(relogio_ms / 1000)) * 1000
            if x.calibrar(est, leitura):
                self.eventos.append(f"calibrou={x.fmt_relogio(leitura)}")
            else:  # o programa real recusaria e o operador teria de conferir; aqui só registramos
                est["previsto_ms"] = relogio_ms
                self.eventos.append(f"leitura-rejeitada={x.fmt_relogio(leitura)}")
        else:
            est["previsto_ms"] = relogio_ms
        # daqui em diante: espelho de jogar_nosso_lance()
        t0 = time.monotonic()
        motor_antes = x.motor
        lance, info, controle, motivo = x.pensar(board.copy(), est, self.nossa, t0)
        if x.motor is not motor_antes:  # pensar() reabriu o motor (falha recuperada na 2ª tentativa)
            self.eventos.append("motor-reaberto")
        busca_ms = (time.monotonic() - t0) * 1000
        if controle.aval is not None:
            est["aval_anterior"] = controle.aval
        if any(m in motivo for m in ("falha", "travou", "fallback")):
            self.eventos.append(f"recuperou={motivo}")
        self.aberto = {"relogio": relogio_ms, "busca": busca_ms}
        return lance

    def encerrar_partida(self):
        self.x.matar_motor()
