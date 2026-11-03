"""Lote de validação do anti-empate: roda em sequência xadrex e xadrex+ae contra bea (forte) e fraco, com os mesmos
parâmetros e a mesma seed, e no fim imprime a tabela comparando as variantes contra cada adversário.

Comparação indireta: xadrex x xadrex+ae não roda no mesmo processo (motor global do xadrex). Cada combinação é
um processo da arena.py, então uma combinação que quebrar não derruba as outras.

Uso (ver --help):  python3 arena/lote.py --games 6 --seed 2026
Saídas em arena/resultados/<nome>/: uma pasta por combinação (saída normal da arena) e tabela.txt.
"""
import argparse
import json
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ARENA = Path(__file__).resolve().parent
COMBINACOES = [("xadrex", "bea"), ("xadrex+ae", "bea"), ("xadrex", "fraco"), ("xadrex+ae", "fraco")]


def pasta_de(a, b):
    return f"{a}_x_{b}".replace("+", "-")


def tabela(resultados):
    """resultados: {(a, b): resumo.json lido ou None}. Devolve o texto da tabela."""
    linhas = [f"{'variante':10} {'adversario':10} {'part':>4}  {'+V =E -D':12} {'3-1-0':>9} {'%':>6}  Elo [IC95]",
              "-" * 78]
    motivos = []
    for (a, b), r in resultados.items():
        if r is None:
            linhas.append(f"{a:10} {b:10} falhou (ver saída acima)")
            continue
        g = r["geral"]
        if not g["partidas"]:
            linhas.append(f"{a:10} {b:10} sem partidas")
            continue
        linhas.append(f"{a:10} {b:10} {g['partidas']:>4}  "
                      f"{'+%d =%d -%d' % (g['vitorias'], g['empates'], g['derrotas']):12} "
                      f"{'%d x %d' % (g['pontos_310_a'], g['pontos_310_b']):>9} {g['pontuacao_pct']:>5.1f}%  "
                      f"{g['elo_txt']}"
                      + ("  << ANTIEMPATE ausente no xadrex.py: sem efeito"
                         if a == "xadrex+ae" and r["config"].get("antiempate_no_modulo") is False else ""))
        motivos.append(f"  {a} x {b}: " + ", ".join(f"{k}: {v}" for k, v in r["motivos"].items()))
    linhas.append("")
    for b in dict.fromkeys(b for _, b in resultados):  # diferença ae - base contra o mesmo adversário
        base, ae = resultados.get(("xadrex", b)), resultados.get(("xadrex+ae", b))
        if base and ae and base["geral"]["partidas"] and ae["geral"]["partidas"]:
            gb, ga = base["geral"], ae["geral"]
            linhas.append(f"contra {b}: xadrex+ae - xadrex = {ga['pontos_310_a'] - gb['pontos_310_a']:+d} pontos 3-1-0 "
                          f"({ga['partidas']} e {gb['partidas']} partidas), "
                          f"{ga['pontuacao_pct'] - gb['pontuacao_pct']:+.1f} pontos percentuais")
    linhas.append("\nmotivos de término:")
    linhas += motivos
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=6, help="partidas por combinação (par: cores trocadas)")
    ap.add_argument("--seed", type=int, default=None, help="a mesma para as 4 combinações (padrão: sorteada)")
    ap.add_argument("--nome", default=None, help="pasta do lote em resultados/ (padrão: lote_<data e hora>)")
    ap.add_argument("--base-min", type=float, default=10.0)
    ap.add_argument("--inc-s", type=float, default=0.0)
    ap.add_argument("--delay-min", type=float, default=3.0)
    ap.add_argument("--delay-max", type=float, default=8.0)
    ap.add_argument("--fraco-skill", type=int, default=5)
    ap.add_argument("--fraco-tempo", type=float, default=1.0)
    ap.add_argument("--stockfish", default=None, help="repassado à arena (padrão: o mesmo da arena.py)")
    args = ap.parse_args()
    if args.games < 1:
        ap.error("--games precisa ser >= 1")
    if args.seed is None:
        args.seed = random.SystemRandom().randrange(2**31)
    nome = args.nome or f"lote_{datetime.now():%Y%m%d_%H%M%S}"
    pasta = ARENA / "resultados" / nome
    if pasta.exists():
        ap.error(f"{pasta} já existe; escolha outro --nome")

    comum = ["--games", str(args.games), "--seed", str(args.seed), "--base-min", f"{args.base_min:g}",
             "--inc-s", f"{args.inc_s:g}", "--delay-min", f"{args.delay_min:g}", "--delay-max", f"{args.delay_max:g}",
             "--fraco-skill", str(args.fraco_skill), "--fraco-tempo", f"{args.fraco_tempo:g}"]
    if args.stockfish:
        comum += ["--stockfish", args.stockfish]
    print(f"lote {nome} | {len(COMBINACOES)} combinações x {args.games} partidas | seed {args.seed}", flush=True)
    resultados = {}
    for i, (a, b) in enumerate(COMBINACOES, 1):
        print(f"\n##### [{i}/{len(COMBINACOES)}] {a} x {b} #####", flush=True)
        cmd = [sys.executable, str(ARENA / "arena.py"), "--a", a, "--b", b, "--nome", f"{nome}/{pasta_de(a, b)}"]
        codigo = subprocess.run(cmd + comum).returncode
        resumo = pasta / pasta_de(a, b) / "resumo.json"
        # resumo.json é regravado a cada partida: se a arena quebrou no meio, vale o que já foi jogado
        resultados[(a, b)] = json.loads(resumo.read_text(encoding="utf-8")) if resumo.exists() else None
        if codigo:
            print(f"!! {a} x {b} terminou com código {codigo}", flush=True)

    atraso = f"{args.delay_min:g}-{args.delay_max:g}s" if args.delay_max > 0 else "desligado"
    texto = (f"lote {nome} | seed {args.seed} | {args.base_min:g}+{args.inc_s:g} | atraso {atraso} | "
             f"fraco: Skill {args.fraco_skill}, {args.fraco_tempo:g} s\n"
             f"placar do ponto de vista da variante (pontos 3-1-0: variante x adversário)\n\n" + tabela(resultados))
    print("\n" + texto)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tabela.txt").write_text(texto + "\n", encoding="utf-8")
    print(f"\ntabela em {pasta / 'tabela.txt'}")


if __name__ == "__main__":
    main()
