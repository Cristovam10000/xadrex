"""Adaptadores dos dois programas comparados na arena.

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


class Xadrex:
    """Usa o código REAL de xadrex/xadrex.py + tempo.py, reproduzindo o fluxo de `partida()`/`jogar_nosso_lance()`.

    Diferenças em relação ao programa interativo (todas exigidas pela automação):
    - COMANDO_MOTOR aponta para o binário da arena (--stockfish; OPCOES_MOTOR originais mantidas).
    - A leitura do relógio físico é simulada: quando tempo.precisa_leitura() pede, chama calibrar() com o
      relógio da arena truncado para segundos inteiros (o que o operador veria em mm:ss).
    - Não chama jogar_nosso_lance/salvar/iniciar/encerrar: nada é gravado em partida_atual.json nem em logs/.
    """
    nome = "xadrex"

    def __init__(self):
        sys.dont_write_bytecode = True  # não criar __pycache__ dentro do repo xadrex
        if str(PASTA_XADREX) not in sys.path:
            sys.path.insert(0, str(PASTA_XADREX))
        import tempo
        import xadrex
        xadrex.COMANDO_MOTOR = [STOCKFISH]
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
            "atraso": asdict(self.tempo.AtrasoHumano()),
            "aval_anterior": None,
        }
        self.nossa = cor
        self.leituras = self.leituras_rejeitadas = 0
        self.x.abrir_motor()  # como main(): motor aberto antes da partida, fora do relógio

    def lance(self, board, relogio_ms):
        self.eventos = []
        x, est = self.x, self.est
        # em partida(): a leitura é pedida ao entrar o lance adversário, antes do nosso lance
        if est.get("exigir_leitura") or self.tempo.precisa_leitura(est["previsto_ms"], est["k"]):
            leitura = max(0, math.floor(relogio_ms / 1000)) * 1000
            if x.calibrar(est, leitura):
                self.leituras += 1
                self.eventos.append(f"calibrou={x.fmt_relogio(leitura)}")
            else:  # o programa real recusaria e o operador teria de conferir; aqui só registramos
                self.leituras_rejeitadas += 1
                self.eventos.append(f"leitura-rejeitada={x.fmt_relogio(leitura)}")
        # daqui em diante: espelho de jogar_nosso_lance() (xadrex.py, linhas 283-292)
        t0 = time.monotonic()
        relogio = est["previsto_ms"]
        motor_antes = x.motor
        lance, info, controle, motivo = x.pensar(board.copy(), est, self.nossa, t0)
        if x.motor is not motor_antes:  # pensar() reabriu o motor (falha recuperada na 2ª tentativa)
            self.eventos.append("motor-reaberto")
        gasto = time.monotonic() - t0
        atraso = self.tempo.AtrasoHumano(**est["atraso"])
        est["previsto_ms"] = relogio - gasto * 1000 + est["inc_s"] * 1000 - atraso.media
        est["k"] += 1
        if controle.aval is not None:
            est["aval_anterior"] = controle.aval
        if any(m in motivo for m in ("falha", "travou", "fallback")):
            self.eventos.append(f"recuperou={motivo}")
        return lance

    def encerrar_partida(self):
        self.x.matar_motor()
