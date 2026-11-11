"""Xadrex — programa de partida do III Chess Challenge (linha de comando, offline)."""
import codecs
import json
import logging
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import chess
import chess.engine

import empate
import tempo

RAIZ = Path(__file__).resolve().parent
COMANDO_MOTOR = [str(RAIZ / "engines" / "stockfish-windows-x86-64-universal.exe")]
ESTADO = RAIZ / "partida_atual.json"
LOGS = RAIZ / "logs"
OPCOES_MOTOR = {"Threads": max(1, (os.cpu_count() or 4) - 4), "Hash": 512}
# Windows (medido em 04/11 no notebook do evento, 16 núcleos lógicos): com prioridade normal o Stockfish usou ~4
# núcleos (1,9 M nós/s). Acima do normal com 12 threads: 6,0 M nós/s e o Python sem travar mais de ~110 ms.
# Prioridade alta com 14 threads chegou a travar o Python por 2 s (teclado, vigia e relógio automático rodam nele).
PRIORIDADE_MOTOR = {"creationflags": subprocess.ABOVE_NORMAL_PRIORITY_CLASS} if os.name == "nt" else {}
# chave de emergência (leitor de teclas com problema no dia): input() simples, sem o instante da 1ª tecla
ENTRADA_SIMPLES = os.environ.get("XADREX_ENTRADA_SIMPLES") == "1"
# anti-empate (empate.py): ligado por padrão desde 04/11 (arena: 80 x 58 pontos 3-1-0 contra o bea, D13);
# XADREX_ANTIEMPATE=0 desliga. Lido a cada lance (a arena liga e desliga pelo atributo)
ANTIEMPATE = os.environ.get("XADREX_ANTIEMPATE", "1") != "0"
AJUDA = ("Comandos: <lance UCI> [mm:ss do nosso relógio] | u (desfaz último par de lances) | tab | sair | fim\n"
         "pos <FEN> troca a posição do tabuleiro (sem regra; o histórico de lances recomeça dali).\n"
         "relogio mm:ss acerta o NOSSO relógio interno (sem conferir se é plausível); relogio adv mm:ss, o do adversário.\n"
         "Depois do nosso lance, aperte ENTER ao bater o relógio: o programa mede o nosso tempo sozinho.\n"
         "Ex.: 'e7e5 12:31' registra o lance e corrige o relógio interno com o relógio físico (opcional).")

_monotonic_real = time.monotonic


class Pausavel:
    """time.monotonic() que para durante a pausa: com o botão PAUSAR da janela nenhum relógio anda (os dois da tela,
    o relógio automático e o orçamento do motor), porque todos leem o tempo daqui (`xadrex.time`)."""
    sleep = staticmethod(time.sleep)

    def __init__(self):
        self.parado = 0.0    # segundos pausados já encerrados
        self.desde = None    # instante real do início da pausa atual

    def monotonic(self):
        real = _monotonic_real()
        return real - self.parado - (real - self.desde if self.desde is not None else 0.0)

    def alternar(self):
        """Pausa ou continua; devolve True se ficou pausado."""
        if self.desde is None:
            self.desde = _monotonic_real()
        else:
            self.parado += _monotonic_real() - self.desde
            self.desde = None
        return self.desde is not None


relogio_pausavel = Pausavel()
time = relogio_pausavel  # noqa: F811 (de propósito: o módulo inteiro passa a ler o tempo pausável)

motor = None
logging.getLogger("asyncio").setLevel(logging.CRITICAL)  # motor morto pelo vigia gera aviso inofensivo no console


def abrir_motor():
    global motor
    matar_motor()
    # setpgrp: o Ctrl+C do console não chega ao Stockfish (senão ele morre junto)
    motor = chess.engine.SimpleEngine.popen_uci(COMANDO_MOTOR, setpgrp=True, timeout=5, **PRIORIDADE_MOTOR)
    motor.configure(OPCOES_MOTOR)
    motor.timeout = 2.0  # prazo para comandos fora da busca, inclusive para a análise *começar* (padrão: 10 s)


def matar_motor():
    global motor
    m, motor = motor, None
    if m is not None:
        try:
            m.close()
        except Exception:
            pass


def ler_lance(board, texto):
    """Retorna o lance legal ou uma mensagem de erro (nunca levanta exceção)."""
    try:
        lance = chess.Move.from_uci(texto)
    except chess.InvalidMoveError:
        return f"'{texto}' não é UCI (ex.: e2e4, g1f3, e7e8q)."
    if lance in board.legal_moves:
        return lance
    return f"Lance ilegal: {texto}. Legais: {' '.join(sorted(m.uci() for m in board.legal_moves))}"


def desfazer(board, nossa):
    """Volta para antes do último lance do adversário (tira nosso lance e o dele)."""
    if len(board.move_stack) >= 2 and board.turn != nossa:
        board.pop()
        board.pop()
        return True
    return False


def fim_de_jogo(board):
    """Só o que já ocorreu: outcome(claim_draw=True) também conta repetição/50 lances possíveis no PRÓXIMO lance."""
    o = board.outcome()
    if o:
        return f"{o.result()} ({o.termination.name})"
    if board.is_repetition(3):
        return "1/2-1/2 (tripla repetição)"
    if board.is_fifty_moves():
        return "1/2-1/2 (regra dos 50 lances)"
    return None


def fmt_aval(score, nossa):
    if score is None:
        return "-"
    s = score.pov(nossa)
    return f"#{s.mate()}" if s.is_mate() else f"{s.score() / 100:+.2f}"


def fmt_relogio(ms):
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


def ler_relogio(texto):
    m, s = (int(x) for x in texto.split(":"))
    if m < 0 or not 0 <= s < 60:
        raise ValueError(texto)
    return (m * 60 + s) * 1000


def calibrar(est, leitura_ms):
    """Leitura do relógio físico no momento da entrada do lance adversário: corrige a estimativa e,
    se houve lances nossos desde a última leitura, ensina ao gestor o atraso humano médio deles.
    Devolve False (sem alterar nada) se a leitura for impossível, ex.: 2:00 digitado no lugar de 0:20."""
    atraso = tempo.AtrasoHumano(**est["atraso"])
    if not tempo.leitura_plausivel(est["previsto_ms"], est["k"], atraso, leitura_ms, est.get("folga_ms", 0)):
        return False
    if est["k"] > 0:
        atraso.observar(atraso.media + (est["previsto_ms"] - leitura_ms) / est["k"])
        est["atraso"] = asdict(atraso)
    est["previsto_ms"], est["k"], est["exigir_leitura"], est["folga_ms"] = leitura_ms, 0, False, 0
    return True


def leitura_obrigatoria(est):
    """Com o relógio automático confiável a leitura é opcional; sem ele vale a regra de precisa_leitura.
    Depois de 'u', sempre (o lance desfeito já tinha saído do relógio interno)."""
    return est.get("exigir_leitura") or (not est.get("medido") and tempo.precisa_leitura(est["previsto_ms"], est["k"]))


def ler_teclas(tecla, eco):
    """Monta uma linha tecla a tecla, com eco e backspace. Devolve (texto, instante da 1ª tecla, instante do ENTER)
    em time.monotonic(). Ctrl+C vira KeyboardInterrupt; setas e outras teclas especiais são ignoradas."""
    texto, primeira, escape = [], None, 0
    while True:
        c = tecla()
        agora = time.monotonic()
        if primeira is None:
            primeira = agora
        if escape == 1:  # sequência do terminal (setas no macOS/Linux): ESC [ ... letra final
            escape = 2 if c in "[O" else 0
        elif escape == 2:
            escape = 0 if "@" <= c <= "~" else 2
        elif c in "\r\n":
            eco("\n")
            return "".join(texto), primeira, agora
        elif c == "\x03":
            raise KeyboardInterrupt
        elif c in "\x00\xe0":  # Windows: tecla especial chega em dois códigos; o segundo é descartado
            tecla()
        elif c == "\x1b":
            escape = 1
        elif c in "\x08\x7f":
            if texto:
                texto.pop()
                eco("\b \b")
        elif c.isprintable():
            texto.append(c)
            eco(c)


def _eco(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def ler_linha(prompt):
    """Linha do operador com o instante da 1ª tecla (o nosso relógio já corria). Devolve (texto, 1ª tecla, ENTER).
    Fora de um terminal (testes, pipe) ou com ENTRADA_SIMPLES não há teclas: os dois instantes são o fim da leitura."""
    if ENTRADA_SIMPLES or not sys.stdin.isatty():
        texto = input(prompt)
        t = time.monotonic()
        return texto, t, t
    _eco(prompt)
    if os.name == "nt":
        import msvcrt
        return ler_teclas(msvcrt.getwch, _eco)
    import termios
    import tty
    fd = sys.stdin.fileno()
    antes = termios.tcgetattr(fd)
    decodificar = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def tecla():
        while True:
            b = os.read(fd, 1)
            if not b:
                raise EOFError
            c = decodificar.decode(b)
            if c:
                return c
    try:
        tty.setcbreak(fd)  # sem eco nem espera do ENTER; Ctrl+C continua gerando KeyboardInterrupt
        return ler_teclas(tecla, _eco)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, antes)


def hora(instante):
    """time.monotonic() -> hora do relógio de parede, para o log."""
    if instante is None:
        return "-"
    return f"{datetime.now() - timedelta(seconds=time.monotonic() - instante):%H:%M:%S.%f}"[:-3]


def desenhar(board):
    for i, linha in enumerate(str(board).splitlines()):
        print(8 - i, linha)
    print("  a b c d e f g h")


def registrar(log, linha):
    try:
        log.write(linha + "\n")
    except OSError as e:
        print(f"!! falha ao gravar o log ({e}); a partida continua")


def salvar(est, board):
    est["lances"] = [m.uci() for m in board.move_stack]
    est["fen"] = board.root().fen()  # posição de onde os lances partem (muda com 'pos')
    tmp = ESTADO.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(est, indent=1), encoding="utf-8")
        tmp.replace(ESTADO)  # troca atômica: queda no meio da escrita não corrompe o estado
    except OSError as e:  # ex.: antivírus segurando o arquivo no Windows
        print(f"!! falha ao salvar o estado ({e}); a partida continua")


def perguntar(msg, padrao):
    r = input(f"{msg} [{padrao}]: ").strip()
    return r or padrao


def perguntar_num(msg, padrao, minimo):
    while True:
        try:
            v = float(perguntar(msg, padrao).replace(",", "."))
            if math.isfinite(v) and v >= minimo:
                return v
        except ValueError:
            pass
        print(f"Digite um número >= {minimo:g}.")


def carregar_estado():
    """Lê e valida a partida salva; devolve (est, board) ou levanta exceção."""
    est = json.loads(ESTADO.read_text(encoding="utf-8"))
    if est["cor"] not in ("w", "b") or not all(isinstance(est[k], (int, float)) for k in ("previsto_ms", "inc_s", "k")):
        raise ValueError("campos inválidos")
    tempo.AtrasoHumano(**est["atraso"])
    str(est["log"])
    board = chess.Board(est.get("fen", chess.STARTING_FEN))  # estado antigo, sem 'fen': posição inicial
    for u in est["lances"]:
        board.push_uci(u)  # levanta exceção se algum lance for ilegal
    return est, board


def iniciar():
    if ESTADO.exists():
        try:
            est, board = carregar_estado()
        except Exception as e:
            ruim = ESTADO.with_name(f"partida_invalida_{datetime.now():%Y%m%d_%H%M%S}.json")
            ESTADO.replace(ruim)
            print(f"!! partida salva inválida ({e!r}); guardada em {ruim.name}. Começando nova partida.")
        else:
            cor = "brancas" if est["cor"] == "w" else "pretas"
            if perguntar(f"Retomar partida salva ({cor}, {len(board.move_stack)} meios-lances)? s/n", "s").lower() == "s":
                while True:
                    r = perguntar("Nosso relógio agora (mm:ss)", fmt_relogio(est["previsto_ms"]))
                    try:
                        est["previsto_ms"], est["k"], est["exigir_leitura"] = ler_relogio(r), 0, False
                        est["medido"], est["folga_ms"] = False, 0  # relógio automático recomeça do zero
                        break
                    except ValueError:
                        print("Use mm:ss")
                while True:
                    r = perguntar("Relógio do ADVERSÁRIO agora (mm:ss)", fmt_relogio(relogios(est)["adv"]))
                    try:
                        relogios(est).update(nos=est["previsto_ms"], adv=ler_relogio(r))
                        return est, board
                    except ValueError:
                        print("Use mm:ss")
    cor = ""
    while cor not in ("b", "p"):
        cor = perguntar("Nossa cor: b = brancas, p = pretas", "b").lower()
    base = perguntar_num("Tempo base em minutos", "10", 1)  # Errata nº 01: 10 min por equipe, sem incremento
    inc = perguntar_num("Incremento em segundos", "0", 0)
    LOGS.mkdir(exist_ok=True)
    est = {
        "cor": "w" if cor == "b" else "b",
        "base_s": base * 60,
        "inc_s": inc,
        "previsto_ms": base * 60_000,  # relógio interno em t0 (busca); do ENTER ao bater até o próximo lance
                                       # adversário, o relógio de quando o nosso voltar a correr
        "k": 0,                        # lances nossos desde a última leitura do relógio físico
        "exigir_leitura": False,       # ligado após 'u': o incremento creditado pode não ter existido
        "medido": False,               # último lance nosso fechado pelo relógio automático com todos os instantes
        "folga_ms": 0,                 # quanto o relógio automático pode ter contado a mais (ENTER esquecido)
        "atraso": asdict(tempo.AtrasoHumano()),
        "aval_anterior": None,
        "log": str(LOGS / f"partida_{datetime.now():%Y%m%d_%H%M%S}.log"),
        "lances": [],
    }
    with open(est["log"], "a", encoding="utf-8") as f:
        f.write(
            f"# Xadrex — {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"# motor: Stockfish 19 (sf_19) {OPCOES_MOTOR}; gestão de tempo: tempo.py (autoria da equipe)\n"
            f"# nossa cor: {'brancas' if est['cor'] == 'w' else 'pretas'} | tempo: {base:g} min + {inc:g} s"
            f" | anti-empate: {'ligado' if ANTIEMPATE else 'desligado'}\n"
            f"# aval = ponto de vista da nossa cor, em peões (#N = mate em N)\n"
        )
    return est, chess.Board()


def buscar(board, controle, nossa, ultimo, prazo_ms, root_moves=None):
    """Roda a busca do Stockfish sob o comando do gestor de tempo. `ultimo` recebe a última iteração completa;
    passado `prazo_ms` sem bestmove, o motor é morto e vale a última iteração completa.
    `root_moves` restringe a busca a esses lances (anti-empate)."""
    t0 = time.monotonic()
    motivo = None
    an = motor.analysis(board, chess.engine.Limit(time=controle.maximo / 1000), info=chess.engine.INFO_ALL,
                        root_moves=root_moves)
    try:
        while True:
            try:
                while not an.would_block():
                    info = an.get()
                    if "pv" in info and "score" in info and not info.get("lowerbound") and not info.get("upperbound"):
                        controle.iteracao(info.get("depth", 0), info["pv"][0], tempo.aval_cp(info["score"].pov(nossa)))
                        ultimo.clear()
                        ultimo.update(info)
            except chess.engine.AnalysisComplete:
                break
            ms = (time.monotonic() - t0) * 1000
            if motivo is None:
                motivo = controle.parar(ms)
                if motivo:
                    an.stop()
            if ms > prazo_ms:  # não respondeu ao stop a tempo: travado
                matar_motor()
                if controle.lance is None:
                    raise RuntimeError("motor travou sem nenhuma iteração completa")
                return controle.lance, dict(ultimo), "motor-travou;melhor-da-busca"
            time.sleep(0.005)
    except BaseException:
        if motor is not None:
            try:
                an.stop()
            except Exception:
                pass
        raise
    melhor = an.wait().move
    info = dict(an.info)  # nós e tempo totais
    if ultimo.get("pv") and ultimo["pv"][0] == melhor:  # profundidade/avaliação/PV da última iteração completa
        info.update({k: ultimo[k] for k in ("depth", "seldepth", "score", "pv") if k in ultimo})
    return melhor, info, motivo or "maximo"


def pensar(board, est, nossa, t0):
    """Pede o lance ao motor sob o gestor; se falhar, reinicia uma vez com busca curta e, no fim, joga um lance legal.
    O relógio usado é o previsto na entrada do lance adversário menos o que já passou desde então (t0)."""
    atraso = tempo.AtrasoHumano(**est["atraso"])
    unico = board.legal_moves.count() == 1
    for tentativa in range(2):
        relogio = est["previsto_ms"] - (time.monotonic() - t0) * 1000
        if tentativa == 0:
            alvo, maximo = tempo.orcamento(relogio, est["inc_s"] * 1000, atraso, tempo.fase(board),
                                           board.fullmove_number)
        else:  # 2ª tentativa curta, depois de uma falha que já gastou relógio
            alvo = maximo = min(500, max(tempo.EMERGENCIA_MS, (relogio - atraso.media) / 4))
        controle = tempo.ControleBusca(alvo, maximo, est["aval_anterior"], unico)
        # o vigia nunca espera além do que o relógio físico permite (menos a parte humana do lance)
        prazo = min(maximo + tempo.VIGIA_MS, max(maximo + 300, relogio - atraso.media))
        ultimo = {}
        try:
            if tentativa or motor is None:
                abrir_motor()
            lance, info, motivo = buscar(board, controle, nossa, ultimo, prazo)
            if lance in board.legal_moves:
                if ANTIEMPATE and tentativa == 0 and motor is not None:
                    return antiempate(board, est, nossa, t0, lance, info, controle, motivo)
                return lance, info, controle, motivo
        except Exception as e:
            print(f"!! motor falhou ({e!r})")
            if controle.lance is not None and controle.lance in board.legal_moves:
                return controle.lance, dict(ultimo), controle, "falha-motor;melhor-da-busca"
    return next(iter(board.legal_moves)), {}, controle, "fallback=primeiro-lance-legal"


def antiempate(board, est, nossa, t0, lance, info, controle, motivo):
    """Depois da busca normal: se o lance escolhido mantém um empate (empate.gatilho) e nenhum freio vale, faz uma
    2ª busca curta só entre lances que não repetem e troca se a melhor alternativa ficar acima de empate.PISO_CP.
    Qualquer erro mantém o lance original. O resumo vai em info["antiempate"] (log) e, se desviou, no motivo."""
    reg = {"gatilho": "-", "freio": "-", "candidatos": "-", "alt": "-", "decisao": "manteve", "busca2": "-"}
    try:
        reg["gatilho"] = empate.gatilho(board, lance, controle.aval) or "-"
        if reg["gatilho"] != "-":
            atraso = tempo.AtrasoHumano(**est["atraso"])
            gasto = (time.monotonic() - t0) * 1000
            relogio = est["previsto_ms"] - gasto
            orc = empate.tempo_busca(controle.alvo, controle.maximo, gasto)
            reg["freio"] = empate.freio(board, nossa, relogio) or ("sem-tempo" if orc < tempo.MIN_MS else "-")
            cands = empate.candidatos(board, lance, reg["gatilho"]) if reg["freio"] == "-" else []
            reg["candidatos"] = str(len(cands)) if reg["freio"] == "-" else "-"
            if cands:
                c2 = tempo.ControleBusca(orc, orc)
                prazo = min(orc + tempo.VIGIA_MS, max(orc + 300, relogio - atraso.media))  # mesmo vigia de pensar
                t2 = time.monotonic()
                try:
                    alt, info2, _ = buscar(board, c2, nossa, {}, prazo, root_moves=cands)
                except Exception:
                    matar_motor()  # motor em estado incerto: pensar() reabre no próximo lance
                    raise
                finally:
                    reg["busca2"] = f"{time.monotonic() - t2:.2f}s"
                aval2 = c2.aval if c2.lance == alt else None  # avaliação só de iteração completa do lance jogado
                if aval2 is not None:
                    reg["alt"] = f"{alt.uci()}({aval2 / 100:+.2f})"
                if alt in cands and alt in board.legal_moves and empate.desviar(aval2):
                    reg["decisao"] = "desviou"
                    controle.lance, controle.aval = alt, aval2  # aval_anterior da próxima busca
                    info2["antiempate"] = reg
                    return alt, info2, controle, f"{motivo};antiempate-desviou"
    except Exception as e:  # nunca pode piorar a robustez: fica o lance da busca normal
        reg["decisao"] = f"manteve(erro:{type(e).__name__})"
    info["antiempate"] = reg
    return lance, info, controle, motivo


def jogar_nosso_lance(board, est, nossa, log, t0):
    """Pensa, joga e mostra o nosso lance. Devolve o tempo de busca (ms desde t0); o relógio interno só fecha no
    ENTER ao bater o relógio (fechar_relogio)."""
    print("... pensando")
    relogio = est["previsto_ms"]
    lance, info, controle, motivo = pensar(board, est, nossa, t0)
    gasto = time.monotonic() - t0
    num, san = board.fullmove_number, board.san(lance)
    board.push(lance)
    atraso = tempo.AtrasoHumano(**est["atraso"])
    if controle.aval is not None:  # só iteração completa: linhas lowerbound/upperbound não são avaliação exata
        est["aval_anterior"] = controle.aval
    aval = fmt_aval(info.get("score"), nossa)
    print(f"\n>>> NOSSO LANCE: {lance.uci()}   ({san})")
    print(f"    aval {aval} | prof {info.get('depth', '-')} | {gasto:.1f}s (alvo {controle.alvo / 1000:.1f}s, "
          f"parou: {motivo}) | relógio ~{fmt_relogio(relogio - gasto * 1000)} agora\n")
    pv = " ".join(m.uci() for m in info.get("pv", []))
    registrar(log,
              f"lance={num} cor={'brancas' if nossa else 'pretas'} uci={lance.uci()} prof={info.get('depth', '-')} "
              f"nos={info.get('nodes', '-')} aval={aval} pv={pv or '-'} tempo={gasto:.2f}s "
              f"relogio_inicio={fmt_relogio(relogio)} alvo={controle.alvo / 1000:.1f}s max={controle.maximo / 1000:.1f}s "
              f"parada={motivo} atraso={atraso.media / 1000:.1f}s/{atraso.seguro / 1000:.1f}s"
              + ("" if "antiempate" not in info else " antiempate=" + ",".join(
                  f"{k}:{v}" for k, v in info["antiempate"].items())))
    return gasto * 1000


def fechar_relogio(est, aberto, fim, por_enter, log):
    """Fecha o nosso tempo no ENTER ao bater o relógio. Se o operador já digitou o lance adversário, `fim` é a
    1ª tecla dele: conta a mais (lado seguro), não ensina o atraso humano e vira folga para a próxima leitura."""
    est["previsto_ms"], gasto, humano = tempo.fechar_lance(aberto["relogio"], aberto["inicio"], aberto["t0"], fim,
                                                           aberto["busca"], est["inc_s"] * 1000)
    correr(est, "adv", fim, nos=est["previsto_ms"])  # batemos o relógio: o nosso para, o do adversário corre
    est["medido"] = gasto is not None and not ENTRADA_SIMPLES
    if ENTRADA_SIMPLES:  # sem a 1ª tecla o tempo de digitar não sai do relógio interno (conta a menos): volta a
        est["k"] += 1    # exigir leitura a cada LEITURA_A_CADA lances, como antes do relógio automático
    atraso = tempo.AtrasoHumano(**est["atraso"])
    if humano is not None and por_enter:
        atraso.observar(humano)
        est["atraso"] = asdict(atraso)
    if not por_enter:
        est["folga_ms"] = est.get("folga_ms", 0) + (fim - aberto["mostrado"]) * 1000
    seg = lambda ms: "-" if ms is None else f"{ms / 1000:.2f}s"  # noqa: E731
    registrar(log, f"relogio lance={aberto['num']} inicio={hora(aberto['inicio'])} fim={hora(fim)} "
                   f"fim_por={'enter' if por_enter else 'tecla'} gasto={seg(gasto)} busca={seg(aberto['busca'])} "
                   f"humano={seg(humano)} relogio={fmt_relogio(est['previsto_ms'])} "
                   f"atraso={atraso.media / 1000:.1f}s/{atraso.seguro / 1000:.1f}s")
    print(f"(nosso relógio ~{fmt_relogio(est['previsto_ms'])}"
          + (f"; parte humana {humano / 1000:.1f}s)" if humano is not None and por_enter else ")"))


def avisar_relogios(rel):
    """Gancho: a interface troca por uma função que mostra os dois relógios correndo ao vivo."""


def relogios(est):
    """Os dois relógios: valor em ms no instante `desde` (time.monotonic) do que está `correndo` ('nos'/'adv')."""
    return est.setdefault("relogios", {"nos": est["previsto_ms"], "adv": est.get("base_s", 600) * 1000,
                                       "correndo": None, "desde": None})


def correr(est, lado, parou, comecou=None, **valores):
    """O relógio que está correndo para em `parou` (mais o incremento, se o lance acabou); `lado` corre desde
    `comecou` (padrão: `parou`). `valores` (nos=, adv=) acertam os relógios depois disso."""
    r = relogios(est)
    if r["correndo"] and r["desde"] is not None:
        r[r["correndo"]] -= max(0.0, parou - r["desde"]) * 1000
        if r["correndo"] != lado:
            r[r["correndo"]] += est["inc_s"] * 1000
    r.update(valores)
    r["correndo"], r["desde"] = lado, parou if comecou is None else comecou
    avisar_relogios({**r, "cor": est.get("cor")})


def encerrar(log, motivo):
    registrar(log, f"# FIM: {motivo}")
    print(f"\nFIM: {motivo}")
    ESTADO.unlink(missing_ok=True)


def partida(est, board, log):
    nossa = chess.WHITE if est["cor"] == "w" else chess.BLACK
    print(f"Anti-empate: {'LIGADO' if ANTIEMPATE else 'DESLIGADO'} (XADREX_ANTIEMPATE=0 desliga)")
    print(AJUDA)
    desenhar(board)
    t0 = time.monotonic()
    relogios(est)["correndo"] = None  # 'desde' salvo é de outro processo: recomeça a contar daqui
    correr(est, "nos" if board.turn == nossa else "adv", t0, nos=est["previsto_ms"])
    inicio = None  # 1ª tecla na vez do adversário: o nosso relógio corre desde ~OUVIR_MS antes
    aberto = None  # nosso lance já mostrado, à espera do ENTER ao bater o relógio
    while True:
        fim = fim_de_jogo(board)  # o árbitro declara repetição e 50 lances sem reclamação
        if fim:
            encerrar(log, fim)
            return
        if board.turn == nossa:
            if relogios(est)["correndo"] != "nos":  # ex.: 'pos' deu a vez para nós
                correr(est, "nos", time.monotonic(), nos=est["previsto_ms"])
            relogio, num = est["previsto_ms"], board.fullmove_number
            try:
                busca = jogar_nosso_lance(board, est, nossa, log, t0)
            except KeyboardInterrupt:
                print("\n(Ctrl+C ignorado; recalculando. Use 'sair' para fechar.)")
                continue
            aberto = {"relogio": relogio, "inicio": inicio, "t0": t0, "busca": busca, "mostrado": time.monotonic(),
                      "num": num}
            inicio = None
            salvar(est, board)
            continue
        exigir = leitura_obrigatoria(est)
        if aberto:
            prompt = "ENTER ao bater o relógio (ou já digite o lance do adversário): "
        elif exigir:
            prompt = "Lance do adversário + NOSSO RELÓGIO (ex.: e7e5 1:31): "
        else:
            prompt = "Lance do adversário (UCI) [mm:ss]: "
        try:
            texto, primeira, enter = ler_linha(prompt)
        except KeyboardInterrupt:
            print("\n(use 'sair' para fechar)")
            continue
        except EOFError:
            return
        bruto = texto.strip()
        texto = bruto.lower()
        if aberto:  # ENTER esquecido: a 1ª tecla do lance adversário fecha o nosso tempo (a mais = lado seguro)
            fechar_relogio(est, aberto, enter if not texto else primeira, not texto, log)
            aberto = None
            salvar(est, board)
            if not texto:
                continue
            exigir = leitura_obrigatoria(est)
        if texto.split()[:1] in (["relogio"], ["relógio"]):  # acerto direto, como na retomada
            partes = texto.split()[1:]
            lado = "adv" if partes[:1] == ["adv"] else "nos"
            try:
                lido = ler_relogio(partes[-1])
            except (IndexError, ValueError):
                print("Use: relogio mm:ss (o nosso) ou relogio adv mm:ss (o do adversário)")
                continue
            r = relogios(est)
            if lado == "nos":  # na vez do adversário o nosso está parado: o valor é o de quando ele voltar a correr
                est["previsto_ms"], est["k"], est["exigir_leitura"] = lido, 0, False
                est["medido"], est["folga_ms"] = False, 0
            if r["correndo"] == lado:
                r["desde"] = time.monotonic()
            r[lado] = lido
            avisar_relogios({**r, "cor": est.get("cor")})
            registrar(log, f"# relógio {'do adversário' if lado == 'adv' else 'nosso'} acertado: {fmt_relogio(lido)}")
            salvar(est, board)
            print(f"(relógio {'do adversário' if lado == 'adv' else 'nosso'} acertado para {fmt_relogio(lido)})")
            continue
        if texto.startswith("pos "):  # posição editada à mão: o operador assume o risco (pedido da equipe)
            inicio = None
            try:
                novo = chess.Board(bruto.split(None, 1)[1])  # FEN diferencia maiúsculas: usa o texto sem lower()
            except ValueError as e:
                print(f"FEN inválida ({e}).")
                continue
            if not novo.is_valid():
                print(f"!! POSIÇÃO IMPOSSÍVEL ({novo.status()!r}): o Stockfish pode cair e o programa jogaria um "
                      "lance legal qualquer. Corrija com outro 'pos' (ou EDITAR POSIÇÃO) se não foi de propósito.")
            # guarda a posição de antes: 'u' sem lance para desfazer volta a ela
            est.setdefault("edicoes", []).append({"fen": board.root().fen(),
                                                  "lances": [m.uci() for m in board.move_stack]})
            board.set_fen(novo.fen())  # zera o histórico: 'u' e repetição só contam daqui em diante
            registrar(log, f"# posição editada: {board.fen()}")
            salvar(est, board)
            desenhar(board)
            continue
        nova = inicio is None
        if nova:  # 1ª linha da vez do adversário; tab e linha vazia não contam (podem vir antes do lance dele)
            inicio = primeira
        if texto == "sair":
            print(f"Estado salvo em {ESTADO.name}; rode de novo para retomar.")
            return
        if texto == "fim":
            encerrar(log, input("Motivo (ex.: abandono, tempo, empate acordado): ").strip() or "encerrada pelo operador")
            return
        if texto in ("tab", "?"):
            if nova:
                inicio = None
            desenhar(board)
            print(f"lances: {' '.join(m.uci() for m in board.move_stack) or '-'}")
            print(AJUDA)
            continue
        if texto == "u":
            inicio = None
            if desfazer(board, nossa):
                # o lance desfeito já saiu do relógio interno (e o incremento pode não existir): só a leitura corrige
                est["k"], est["exigir_leitura"], est["medido"] = 0, True, False
                registrar(log, f"# desfeito: voltou para {len(board.move_stack)} meios-lances")
                salvar(est, board)
                print("Desfeito. Digite o lance correto do adversário.")
            elif est.get("edicoes"):  # nada a desfazer desde a última edição: volta para antes dela
                antes = est["edicoes"].pop()
                board.set_fen(antes["fen"])
                for u in antes["lances"]:
                    board.push_uci(u)
                est["k"], est["exigir_leitura"], est["medido"] = 0, True, False
                registrar(log, f"# edição desfeita: voltou para {board.fen()}")
                salvar(est, board)
                desenhar(board)
                print("Edição desfeita: posição de antes restaurada.")
            else:
                print("Nada para desfazer.")
            continue
        partes = texto.split()
        if not partes or len(partes) > 2:
            if not partes and nova:
                inicio = None
            print(AJUDA)
            continue
        leitura = None
        if len(partes) == 2:
            try:
                leitura = ler_relogio(partes[1])
            except ValueError:
                print("Relógio inválido: use mm:ss (segundos de 00 a 59), ex.: e7e5 12:31")
                continue
        if leitura is None and exigir:
            print("Agora a leitura do NOSSO relógio é obrigatória (a estimativa já pode estar errada). Ex.: e7e5 1:31")
            continue
        lance = ler_lance(board, partes[0])
        if isinstance(lance, str):
            print(lance)
            continue
        if leitura is not None and not calibrar(est, leitura):
            a = tempo.AtrasoHumano(**est["atraso"])
            maximo = est["previsto_ms"] + est["k"] * a.media + est.get("folga_ms", 0) + tempo.TOLERANCIA_LEITURA_MS
            print(f"Leitura {fmt_relogio(leitura)} impossível (no máximo ~{fmt_relogio(maximo)}). Confira o relógio. "
                  "Se estiver certa, use 'sair' e retome informando o relógio.")
            continue
        num = board.fullmove_number
        board.push(lance)
        t0 = enter  # a busca começa no ENTER do lance adversário
        extra = f" inicio={hora(inicio)} enter={hora(enter)}"
        if leitura is None:  # o relógio interno marcava o nosso relógio ao voltar a correr; desconta ouvir e digitar
            est["previsto_ms"] = tempo.relogio_ao_pensar(est["previsto_ms"], inicio, t0)
        else:  # calibrar já pôs a leitura física
            a = tempo.AtrasoHumano(**est["atraso"])
            extra += f" leitura={fmt_relogio(leitura)} atraso={a.media / 1000:.1f}s/{a.seguro / 1000:.1f}s"
            print(f"(relógio calibrado; atraso humano ~{a.media / 1000:.1f}s, reserva {a.seguro / 1000:.1f}s)")
        # o adversário bateu o relógio ~OUVIR_MS antes da 1ª tecla; o nosso vale previsto_ms em t0 (como na busca)
        correr(est, "nos", inicio - tempo.OUVIR_MS / 1000 if inicio is not None else enter, t0, nos=est["previsto_ms"])
        registrar(log, f"lance={num} cor={'pretas' if nossa else 'brancas'} uci={lance.uci()} (adversário){extra}")
        salvar(est, board)


def main():
    try:
        try:  # antes das perguntas: na retomada, o relógio informado já não inclui o tempo de abrir o motor
            abrir_motor()
        except Exception as e:  # sem motor, pensar() jogaria o primeiro lance legal: melhor não começar
            print(f"!! O motor não abriu ({e!r}).\n   Esperado em: {COMANDO_MOTOR[0]}\n"
                  "   Veja a seção 'Instalação' do README. Nenhuma partida foi iniciada"
                  + ("; a partida salva continua guardada." if ESTADO.exists() else "."))
            return 1
        est, board = iniciar()
        with open(est["log"], "a", encoding="utf-8", buffering=1) as log:
            partida(est, board, log)
    finally:  # sem fechar, a thread do motor segura o processo aberto após um erro
        matar_motor()


if __name__ == "__main__":
    sys.exit(main())
