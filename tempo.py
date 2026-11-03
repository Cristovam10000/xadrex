"""Gestor de tempo da equipe — componente decisório de autoria própria.

Decide quanto tempo o Stockfish pode pensar em cada lance, considerando que o nosso relógio
físico também corre enquanto pessoas digitam, anunciam, movem a peça e apertam o relógio.

Três partes:
1. AtrasoHumano: aprende quanto a operação humana custa por lance, a partir das leituras do
   relógio físico que o operador digita (ex.: "e7e5 12:31"). Usa o mesmo estimador do tempo de
   retransmissão do TCP (RFC 6298): média suavizada + 4 x desvio suavizado.
2. orcamento(): transforma relógio, incremento, atraso humano e fase da partida em um tempo-alvo
   e um tempo máximo para a busca, sempre guardando reserva para a parte humana do lance.
3. ControleBusca: durante a busca, a cada iteração completa, estende ou encurta o alvo conforme
   a estabilidade do melhor lance e a queda da avaliação, e decide quando parar.
"""
from dataclasses import dataclass, field

import chess

MIN_MS = 200           # busca mínima normal: ainda produz profundidade/avaliação para o log
EMERGENCIA_MS = 50     # busca quando nem o mínimo cabe no relógio
PISO_MS = 1000         # folga fixa além da reserva humana
SEGURO_MIN_MS = 3000   # nenhuma equipe anuncia, move e aperta o relógio em menos que isto
VIGIA_MS = 3000        # passou do máximo + isto sem resposta: motor considerado travado
MATE = 90_000          # avaliações acima disto (em centipeões) representam mate
LEITURA_A_CADA = 8     # sem leitura, o erro da previsão acumula a cada lance
LEITURA_ABAIXO_MS = 120_000  # relógio baixo: erro acumulado vira perda por tempo
TOLERANCIA_LEITURA_MS = 5000

PESO_FASE = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}  # 24 na posição inicial


@dataclass
class AtrasoHumano:
    media: float = 5000.0
    desvio: float = 2500.0
    amostras: int = 0

    def observar(self, amostra_ms):
        amostra = min(max(amostra_ms, 0.0), 60_000.0)  # leitura absurda não destrói a estimativa
        if self.amostras == 0:  # RFC 6298: primeira medida substitui o palpite inicial
            self.media, self.desvio = amostra, amostra / 2
        else:
            self.desvio = 0.75 * self.desvio + 0.25 * abs(amostra - self.media)
            self.media = 0.875 * self.media + 0.125 * amostra
        self.amostras += 1

    @property
    def seguro(self):
        return max(self.media + 4 * self.desvio, SEGURO_MIN_MS)


def precisa_leitura(previsto_ms, k):
    """A previsão do relógio acumula o erro do atraso humano a cada lance sem leitura do relógio físico."""
    return k >= LEITURA_A_CADA or previsto_ms < LEITURA_ABAIXO_MS


def leitura_plausivel(previsto_ms, k, atraso, leitura_ms):
    """O relógio real não pode passar da previsão somada ao atraso humano descontado nos k lances (atraso >= 0)."""
    return leitura_ms <= previsto_ms + k * atraso.media + TOLERANCIA_LEITURA_MS


def fase(board):
    """1.0 = todas as peças (abertura), 0.0 = só reis e peões."""
    total = sum(PESO_FASE[p.piece_type] for p in board.piece_map().values() if p.piece_type in PESO_FASE)
    return min(total, 24) / 24


def orcamento(relogio_ms, inc_ms, atraso, fase_partida, numero_lance=99):
    """Devolve (alvo_ms, maximo_ms) para este lance."""
    # saldo de cada lance futuro: incremento menos a parte humana. Sem incremento ele é negativo:
    # cada lance que ainda vem vai custar relógio mesmo que o motor jogue na hora.
    liquido = inc_ms - atraso.media
    if liquido > 0:
        lances_restantes = 18 + 27 * fase_partida  # horizonte: ~45 lances na abertura, ~18 no final
    else:
        # sem saldo, subestimar a duração da partida é perder por tempo; horizonte escolhido na simulação
        # (test_tempo.py): 25+0 sem perdas até 80 lances, sem zerar o tempo de busca no Armageddon
        lances_restantes = 40 + 15 * fase_partida
    util = relogio_ms - (atraso.seguro + PISO_MS)  # o que pode ir para a busca sem arriscar a parte humana
    if util <= 0:  # emergência: o mínimo cede ao relógio físico
        m = min(MIN_MS, max(EMERGENCIA_MS, (relogio_ms - atraso.media) / 4))
        return m, m
    alvo = util / lances_restantes + (0.75 * liquido if liquido > 0 else liquido)
    # abertura: lances conhecidos e alternativas de valor parecido; rampa de 46% (lance 1) a 100% (lance 10)
    alvo *= min(1.0, 0.4 + 0.06 * numero_lance)
    if alvo <= MIN_MS:
        return MIN_MS, MIN_MS
    maximo = min(4 * alvo, 0.3 * util)             # nunca gasta o incremento antes de recebê-lo
    alvo = min(alvo, maximo)
    return max(alvo, MIN_MS), max(maximo, MIN_MS)


@dataclass
class ControleBusca:
    alvo: float
    maximo: float
    aval_anterior: float | None = None  # avaliação da nossa busca anterior (centipeões, nosso ponto de vista)
    lance_unico: bool = False
    lance: str | None = None
    aval: float | None = None
    profundidade: int = 0
    estavel: int = 0
    trocas: list = field(default_factory=list)  # profundidades em que o melhor lance mudou

    def iteracao(self, profundidade, lance, aval_cp):
        """Registra uma iteração completa da busca (melhor lance e avaliação naquela profundidade)."""
        if lance == self.lance:
            self.estavel += 1
        else:
            if self.lance is not None:
                self.trocas.append(profundidade)
            self.estavel = 1
        self.lance, self.aval, self.profundidade = lance, aval_cp, profundidade

    def limite(self):
        trocas_recentes = sum(1 for d in self.trocas if d > self.profundidade - 4)
        instabilidade = 1 + 0.5 * trocas_recentes
        queda = 1.0
        if self.aval_anterior is not None and self.aval is not None and self.aval < self.aval_anterior - 30:
            queda = min(2.0, 1 + (self.aval_anterior - self.aval) / 200)
        estabilidade = 0.6 if self.estavel >= 8 else 1.0
        fator = min(max(instabilidade * queda * estabilidade, 0.5), 3.0)
        return min(self.alvo * fator, self.maximo)

    def parar(self, decorrido_ms):
        """Motivo para parar agora, ou None para continuar buscando."""
        if decorrido_ms >= self.maximo:
            return "maximo"
        if self.lance is None:
            return None
        if self.lance_unico:
            return "lance-unico"
        if self.aval is not None and self.aval > MATE and self.estavel >= 3:
            return "mate-encontrado"
        if decorrido_ms >= self.limite():
            return f"alvo(x{self.limite() / self.alvo:.2f})"
        return None


def aval_cp(score):
    """PovScore já no nosso ponto de vista -> centipeões, com mate como valor grande."""
    return score.score(mate_score=100_000)
