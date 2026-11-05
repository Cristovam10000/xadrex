"""Base de aberturas: junta as partidas da arena (arena/resultados/**/partidas.jsonl) e as partidas reais
(logs/partida_*.log) em arena/resultados/aberturas.csv e imprime o placar por abertura e nossa cor.

  python3 arena/aberturas.py            (Windows: .venv\\Scripts\\python.exe arena\\aberturas.py)

Na arena a abertura é imposta (lista ABERTURAS de arena.py); nos logs ela é reconhecida pelos lances jogados.
Partida de log sem a linha '# FIM' (encerrada no meio, teste) entra com resultado '?' e fica fora do placar.
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import chess

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
from arena import ABERTURAS  # noqa: E402

# linhas que o Stockfish escolhe sozinho nas partidas reais e que não estão na lista da arena
EXTRAS = [
    ("Ruy Lopez (Berlim)", "e2e4 e7e5 g1f3 b8c6 f1b5 g8f6"),
    ("Escocesa", "e2e4 e7e5 g1f3 b8c6 d2d4"),
    ("Aberta 1.e4 e5", "e2e4 e7e5"),
    ("Siciliana", "e2e4 c7c5"),
    ("Peão da Dama", "d2d4"),
]
CONHECIDAS = [(nome, seq.split()) for nome, seq in ABERTURAS + EXTRAS]


def nomear(lances):
    """Abertura conhecida com o maior prefixo igual aos lances; senão, os 6 primeiros lances."""
    melhor = max(((len(s), n) for n, s in CONHECIDAS if lances[:len(s)] == s), default=None)
    return melhor[1] if melhor else "outra: " + " ".join(lances[:6])


def da_arena():
    for f in sorted((RAIZ / "arena" / "resultados").glob("**/partidas.jsonl")):
        for linha in f.read_text(encoding="utf-8").splitlines():
            p = json.loads(linha)
            nos = p.get("a", "xadrex")  # runs antigos (match_10min) não tinham 'a'
            pts = p.get("pontos_a", p.get("pontos_xadrex"))
            yield {"fonte": f.parent.relative_to(RAIZ / "arena" / "resultados").as_posix(), "nos": nos,
                   "adversario": p["pretas"] if p["brancas"] == nos else p["brancas"],
                   "cor": "brancas" if p["brancas"] == nos else "pretas", "abertura": p["abertura"],
                   "resultado": {1: "V", 0.5: "E", 0: "D"}[pts], "motivo": p["motivo"],
                   "meios_lances": p["meios_lances"]}


def dos_logs():
    for f in sorted((RAIZ / "logs").glob("partida_*.log")):
        cor, lances, fim = None, [], None
        for linha in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("# nossa cor:"):
                cor = linha.split(":")[1].split("|")[0].strip()
            elif linha.startswith("# FIM:"):
                fim = linha[6:].strip()
            elif linha.startswith("lance=") and " uci=" in linha:
                lances.append(linha.split(" uci=")[1].split()[0])
        if not lances or cor not in ("brancas", "pretas"):
            continue
        board = chess.Board()
        try:
            for u in lances:
                board.push_uci(u)
        except ValueError:  # lance desfeito com 'u' deixa o log fora de ordem: só a abertura vale
            pass
        resultado = "?"
        o = board.outcome(claim_draw=True)
        if fim is not None and o is not None:
            resultado = "E" if o.winner is None else ("V" if o.winner == (cor == "brancas") else "D")
        yield {"fonte": "logs/" + f.name, "nos": "xadrex", "adversario": "manual", "cor": cor,
               "abertura": nomear(lances), "resultado": resultado, "motivo": fim or "sem FIM",
               "meios_lances": len(lances)}


def main():
    partidas = list(da_arena()) + list(dos_logs())
    saida = RAIZ / "arena" / "resultados" / "aberturas.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:  # -sig: o Excel abre com acentos
        w = csv.DictWriter(f, fieldnames=list(partidas[0]))
        w.writeheader()
        w.writerows(partidas)

    placar = defaultdict(Counter)
    for p in partidas:
        if p["resultado"] != "?":
            placar[(p["abertura"], p["cor"], p["adversario"])][p["resultado"]] += 1
    print(f"{'abertura':28} {'cor':8} {'adversário':10} {'n':>3}  V  E  D  pts3-1-0")
    for (ab, cor, adv), c in sorted(placar.items()):
        n = sum(c.values())
        pts = 3 * c["V"] + c["E"]
        print(f"{ab:28} {cor:8} {adv:10} {n:3} {c['V']:2} {c['E']:2} {c['D']:2}  {pts:3}/{3 * n} ({pts / (3 * n):.0%})")
    sem = sum(p["resultado"] == "?" for p in partidas)
    print(f"\n{len(partidas)} partidas em {saida}; {sem} sem resultado (log sem '# FIM')")


if __name__ == "__main__":
    main()
