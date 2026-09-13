import json
import io
import os
import random
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands


BASE_DIR = Path(__file__).resolve().parent
JOGADORES_FILE = BASE_DIR / "jogadores.json"
# Cole o token do bot entre as aspas ou defina DISCORD_TOKEN no ambiente.
TOKEN = "MTU0ODQxMTAwNjE0MzcwMTI0Mg.GS0Eny.iuehjk4VtkfwpoH3GzNzESuy8EpogU0-LkkSlA"
# Informe abaixo o ID do servidor ou defina DISCORD_GUILD_ID no ambiente.
GUILD_ID = "1548126299728650434"
LIMITE_RANKING = 10
VALOR_INICIAL_ATRIBUTO = 10
VALOR_MAXIMO_ATRIBUTO = 100

ATRIBUTOS = (
    ("💪", "Físico", "fisico", "FIS"),
    ("💨", "Velocidade", "velocidade", "VEL"),
    ("⚽", "Técnica", "tecnica", "TEC"),
    ("🎯", "Chute", "chute", "CHU"),
    ("🤝", "Passe", "passe", "PAS"),
    ("🛡️", "Defesa", "defesa", "DEF"),
    ("👁️", "Visão", "visao", "VIS"),
    ("🫁", "Resistência", "resistencia", "RES"),
    ("⚡", "Estamina", "estamina", "EST"),
)
ATRIBUTOS_EDITAVEIS = {campo for _, _, campo, _ in ATRIBUTOS}
MODIFICADOR_RE = re.compile(r"^\s*([+-]?)\s*(\d+(?:[.,]\d+)?)\s*(%)?\s*$")
MODIFICADOR_STATUS_RE = re.compile(
    r"^\s*([+-]?)\s*(\d+(?:[.,]\d+)?)\s*(%)?"
    r"(?:\s+([A-Za-zÀ-ÿ]+))?\s*$"
)
ABREVIACAO_PARA_ATRIBUTO = {
    abreviacao: campo for _, _, campo, abreviacao in ATRIBUTOS
}
MODIFICADORES_POSICAO = {
    "Zagueiro": {"defesa": 15, "fisico": 15, "velocidade": -15, "passe": -15},
    "Lateral": {"velocidade": 15, "resistencia": 15, "chute": -15, "visao": -15},
    "Volante": {"defesa": 15, "visao": 15, "chute": -15, "tecnica": -15},
    "Meia": {"passe": 15, "tecnica": 15, "defesa": -15, "fisico": -15},
    "Ponta": {"velocidade": 15, "tecnica": 15, "defesa": -15, "fisico": -15},
    "Atacante": {"chute": 15, "fisico": 15, "defesa": -15, "passe": -15},
}
MODIFICADORES_PORTE = {
    "ectomorfo": {"velocidade": 15, "fisico": -15},
    "atletico": {"resistencia": 10, "fisico": -5},
    "equilibrado": {},
    "mesomorfo": {"fisico": 10, "chute": 5},
    "tanque": {"fisico": 20, "velocidade": -15},
}
MODIFICADORES_ALTURA = {
    "baixo": {"velocidade": 15, "fisico": -15},
    "medio": {},
    "alto": {"fisico": 15, "velocidade": -15},
}
ROTULOS_PORTE = {
    "ectomorfo": "Ectomorfo Magro / Seco",
    "atletico": "Atlético Leve / Fibrado",
    "equilibrado": "Equilibrado / Porte Padrão",
    "mesomorfo": "Mesomorfo Forte / Denso",
    "tanque": "Tanque / Pesado",
}
ROTULOS_ALTURA = {
    "baixo": "Baixo (1,65 m a 1,73 m)",
    "medio": "Estatura Média (1,74 m a 1,85 m)",
    "alto": "Alto (1,86 m a 2,00 m)",
}

ACOES_INDIVIDUAIS = {
    "drible_de_corpo": {
        "nome": "Drible de Corpo",
        "categoria": "Dribles e Recursos Individuais",
        "custo_est": 10,
        "formula": "1d20 ((TEC + VIS) / 2)",
        "atributos": ("tecnica", "visao"),
        "efeito": (
            "Supera o defensor na zona atual. O defensor sofre -2 em VEL "
            "no próximo turno."
        ),
        "falha": "O defensor desarma o atacante de forma limpa.",
    },
    "caneta_janela": {
        "nome": "Caneta / Janela",
        "categoria": "Dribles e Recursos Individuais",
        "custo_est": 15,
        "formula": "1d20 (((TEC com -25%) + VIS) / 2)",
        "atributos": ("tecnica", "visao"),
        "modificador_status": "-25%",
        "efeito": (
            "Avança para a zona desejada; o defensor sofre -5 em VIS "
            "e -2 em DEF por dois turnos."
        ),
        "falha": "A bola é entregue nos pés do defensor.",
    },
    "pique_adiantado": {
        "nome": "Pique Adiantado",
        "categoria": "Dribles e Recursos Individuais",
        "custo_est": 15,
        "formula": "1d20 ((FIS + VEL) / 2)",
        "atributos": ("fisico", "velocidade"),
        "efeito": "Permite avançar até 2 zonas no mesmo turno.",
        "falha": "A bola vai para a lateral ou para o goleiro adversário.",
    },
    "giro_de_pivo": {
        "nome": "Giro de Pivô",
        "categoria": "Dribles e Recursos Individuais",
        "custo_est": 10,
        "formula": "1d20 + ((FIS + TEC) / 2)",
        "atributos": ("fisico", "tecnica"),
        "efeito": "Mantém a posse, supera o marcador e causa -10 EST ao defensor.",
        "falha": "O atacante é desarmado e cai no gramado.",
    },
    "dominio_orientado": {
        "nome": "Domínio Orientado",
        "categoria": "Domínio e Recepção Orientada",
        "custo_est": 5,
        "formula": "1d20 ((TEC + VEL) / 2)",
        "atributos": ("tecnica", "velocidade"),
        "efeito": "Concede +2 em VEL para a ação subsequente no mesmo turno.",
        "falha": "A bola escapa 1 zona à frente e vira bola dividida.",
    },
    "corta_luz": {
        "nome": "Corta-Luz",
        "categoria": "Domínio e Recepção Orientada",
        "custo_est": 10,
        "formula": "1d20 ((VIS + TEC) / 2)",
        "atributos": ("visao", "tecnica"),
        "efeito": "Defensores na zona sofrem -2 em VIS no turno atual.",
        "falha": "A zaga intercepta a bola sem rolar dados.",
    },
    "chute_colocado": {
        "nome": "Chute Colocado",
        "categoria": "Finalizações",
        "custo_est": 15,
        "formula": "1d20 + ((TEC + CHU - 10%) / 2)",
        "atributos": ("tecnica", "chute"),
        "formula_tipo": "soma_reduzida_dividida",
        "percentual": 10,
        "divisor": 2,
        "execucao": "Arremate de precisão buscando os ângulos da goleira.",
        "efeito": "Corta em -5 o atributo FIS do goleiro no teste de defesa.",
        "falha": "O goleiro segura a bola com firmeza, sem chance de rebote.",
    },
    "bomba_de_forca": {
        "nome": "Bomba de Força",
        "categoria": "Finalizações",
        "custo_est": 15,
        "formula": "1d20 + ((FIS + CHU - 10%) / 2)",
        "atributos": ("fisico", "chute"),
        "formula_tipo": "soma_reduzida_dividida",
        "percentual": 10,
        "divisor": 2,
        "execucao": "Chute brutal focado na velocidade da bola.",
        "efeito": (
            "O goleiro sofre -3 em TEC para segurar e, mesmo defendendo, "
            "deve espalmar, gerando rebote obrigatório."
        ),
        "falha": "Total menor que 8 isola a bola por cima do gol.",
    },
    "chute_de_trivela": {
        "nome": "Chute de Trivela",
        "categoria": "Finalizações",
        "custo_est": 20,
        "formula": "1d20 + ((TEC - 10% + CHU) / 2)",
        "atributos": ("tecnica", "chute"),
        "formula_tipo": "primeiro_reduzido_soma_dividida",
        "percentual": 10,
        "divisor": 2,
        "execucao": "Finalização com o lado externo do pé.",
        "efeito": "Aplica -5 em DEF do goleiro e dos zagueiros.",
        "falha": "A falha resulta em chute fraco ou torto e tiro de meta.",
    },
    "cavada_cobertura": {
        "nome": "Cavada / Cobertura",
        "categoria": "Finalizações",
        "custo_est": 20,
        "formula": "1d20 + ((CHU + TEC + VIS) / 3)",
        "atributos": ("chute", "tecnica", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 3,
        "efeito": "Com o goleiro fora do gol, o teste de defesa sofre -50%.",
        "falha": "Com o goleiro na linha, o resultado do chute é cortado pela metade.",
    },
    "finalizacao_de_primeira_sem_pulo": {
        "nome": "Finalização de Primeira / Sem Pulo",
        "categoria": "Finalizações",
        "custo_est": 10,
        "formula": "1d20 + ((VIS + CHU) / 2)",
        "atributos": ("visao", "chute"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "penalidade_execucao": "-10 em CHU",
        "penalidade_atributo": "chute",
        "penalidade_valor": -10,
        "efeito": "Reduz pela metade o bloqueio dos zagueiros e a reação do goleiro.",
        "falha": "Total inferior a 13 faz o atacante furar ou mandar a bola para fora.",
    },
    "bicicleta_acrobatico": {
        "nome": "Bicicleta / Acrobático",
        "categoria": "Finalizações",
        "custo_est": 25,
        "formula": "1d20 + ((TEC - 50% + CHU) / 2)",
        "atributos": ("tecnica", "chute"),
        "formula_tipo": "primeiro_reduzido_soma_dividida",
        "percentual": 50,
        "divisor": 2,
        "condicao": "Exige bola alçada no ar.",
        "efeito": "O goleiro sofre -5 em DEF e TEC devido ao fator surpresa.",
        "falha": "Total menor que 15 anula a jogada por falta técnica.",
    },
    "cabeceio": {
        "nome": "Cabeceio",
        "categoria": "Finalizações",
        "custo_est": 15,
        "formula": "1d20 + ((TEC + VIS) / 2)",
        "atributos": ("tecnica", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "condicao": "Exige cruzamento a meia-altura na zona de Zaga/Área.",
        "efeito": "Garante +2 em FIS no duelo aéreo e rebote frontal se defendido.",
        "falha": "Falha contra o zagueiro causa -10 EST e -1 em VEL no próximo turno.",
    },
    "chute_cruzado": {
        "nome": "Chute Cruzado",
        "categoria": "Finalizações",
        "custo_est": 10,
        "formula": "1d20 + ((TEC + CHU) / 2)",
        "atributos": ("tecnica", "chute"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Arremate em direção à trave mais distante.",
        "efeito": "O goleiro sofre -2 em VIS; rebote vai para o centro da área.",
        "falha": "Erros de precisão fazem a bola sair em tiro de meta.",
    },
    "chute_curvo": {
        "nome": "Chute Curvo",
        "categoria": "Finalizações",
        "custo_est": 20,
        "formula": "1d20 + ((CHU + VIS - 10%) / 2)",
        "atributos": ("chute", "visao"),
        "formula_tipo": "soma_reduzida_dividida",
        "percentual": 10,
        "divisor": 2,
        "execucao": "Arremate de média ou longa distância em que a bola oscila antes de cair bruscamente.",
        "efeito": "Aplica -3 em DEF e -2 em VIS no goleiro, dificultando a leitura da trajetória.",
        "falha": "Total inferior a 10 isola a bola por cima do travessão.",
    },
    "chute_de_letra_calcanhar": {
        "nome": "Chute de Letra / Calcanhar",
        "categoria": "Finalizações",
        "custo_est": 15,
        "formula": "1d20 + ((TEC - 10% + VIS - 10% + CHU - 10%) / 3)",
        "atributos": ("tecnica", "visao", "chute"),
        "formula_tipo": "tres_reduzidos_soma_dividida",
        "percentuais": (10, 10, 10),
        "divisor": 3,
        "condicao": "Exige estar a 1 zona do gol, de costas ou em ângulo desfavorável.",
        "efeito": "Engana a leitura do goleiro e reduz pela metade a pontuação final da defesa.",
        "falha": "O atacante se confunde, perde a posse instantaneamente e não efetua o chute.",
    },
    "voleio": {
        "nome": "Voleio",
        "categoria": "Finalizações",
        "custo_est": 15,
        "formula": "1d20 + ((CHU + TEC - 50%) / 2)",
        "atributos": ("chute", "tecnica"),
        "formula_tipo": "soma_reduzida_dividida",
        "percentual": 50,
        "divisor": 2,
        "execucao": "Rebate a bola no ar assim que ela cai de um passe ou cruzamento.",
        "efeito": "Aumenta a velocidade da bola, aplicando +5 ao resultado final do chute.",
        "falha": "Total inferior a 13 faz o atleta errar a bola e entregar a posse ao inimigo.",
        "bonus_resultado": 5,
    },
    "passe_curto": {
        "nome": "Passe Curto",
        "categoria": "Passes de Manutenção e Curto Alcance",
        "custo_est": 5,
        "formula": "1d20 + PAS",
        "atributos": ("passe",),
        "formula_tipo": "soma_dividida",
        "divisor": 1,
        "execucao": "Troca de passes simples para manter a posse na mesma zona ou zona adjacente.",
        "efeito": "Garante a posse com risco quase nulo.",
    },
    "tabela_um_dois": {
        "nome": "Tabela / Um-Dois",
        "categoria": "Passes de Manutenção e Curto Alcance",
        "custo_est": 10,
        "formula": "1d20 + ((PAS + VEL) / 2)",
        "atributos": ("passe", "velocidade"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Toca a bola para um companheiro e arranca imediatamente para receber a devolução à frente.",
        "efeito": "Supera o marcador direto; na devolução bem-sucedida, recebe a bola 1 zona à frente com +2 em VEL no próximo turno.",
    },
    "passe_de_calcanhar": {
        "nome": "Passe de Calcanhar",
        "categoria": "Passes de Manutenção e Curto Alcance",
        "custo_est": 10,
        "formula": "1d20 + ((PAS - 10% + TEC - 10%) / 2)",
        "atributos": ("passe", "tecnica"),
        "formula_tipo": "dois_reduzidos_soma_dividida",
        "percentuais": (10, 10),
        "divisor": 2,
        "execucao": "Toque rápido sem olhar, usando o calcanhar para surpreender a marcação.",
        "efeito": "Reduz em 10% a capacidade de interceptação dos defensores na zona.",
    },
    "passe_pifado": {
        "nome": "Passe Pifado",
        "categoria": "Passes de Profundidade e Ruptura",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + VIS) / 2)",
        "atributos": ("passe", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Passe milimétrico que rasga a linha de defesa e encontra o atacante em velocidade.",
        "efeito": "O atacante recebe livre de marcadores de linha e ganha +2 em VEL no duelo contra o goleiro.",
    },
    "lancamento_longo_de_inversao": {
        "nome": "Lançamento Longo de Inversão",
        "categoria": "Passes de Profundidade e Ruptura",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + FIS - 10%) / 2)",
        "atributos": ("passe", "fisico"),
        "formula_tipo": "soma_reduzida_dividida",
        "percentual": 10,
        "divisor": 2,
        "execucao": "Bola alçada que cruza o campo de um corredor lateral para o outro.",
        "efeito": "Ignora defensores nas zonas centrais e aplica -2 em VIS e DEF na zaga no próximo turno.",
    },
    "passe_de_trivela_em_profundidade": {
        "nome": "Passe de Trivela em Profundidade",
        "categoria": "Passes de Profundidade e Ruptura",
        "custo_est": 20,
        "formula": "1d20 + ((PAS - 25% + TEC) / 2)",
        "atributos": ("passe", "tecnica"),
        "formula_tipo": "primeiro_reduzido_soma_dividida",
        "percentual": 25,
        "divisor": 2,
        "execucao": "Passe com a parte externa do pé que faz uma curva por fora da linha dos zagueiros.",
        "efeito": "Ignora a primeira linha de interceptação e impede o goleiro de sair para interceptar a bola no ar.",
        "falha": "Total menor que 11 faz a bola pegar efeito excessivo e sair em tiro de meta.",
    },
    "cruzamento_de_linha_de_fundo": {
        "nome": "Cruzamento de Linha de Fundo",
        "categoria": "Cruzamentos e Bolas Alçadas",
        "custo_est": 10,
        "formula": "1d20 + ((PAS + TEC) / 2)",
        "atributos": ("passe", "tecnica"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Cobrança das zonas laterais visando a cabeça dos atacantes na Zaga/Área.",
        "efeito": "Coloca a bola na disputa aérea e dá +1 em FIS para o atacante que tentar o cabeceio.",
    },
    "cruzamento_tenso_rasante": {
        "nome": "Cruzamento Tenso / Rasante",
        "categoria": "Cruzamentos e Bolas Alçadas",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + FIS) / 2)",
        "atributos": ("passe", "fisico"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Bola cruzada à meia-altura, forte e rápida, cortando a pequena área.",
        "efeito": "Torna a bola extremamente difícil para o goleiro segurar, causando -3 em TEC.",
    },
    "cruzamento_cavado_curto": {
        "nome": "Cruzamento Cavado / Curto",
        "categoria": "Cruzamentos e Bolas Alçadas",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + VIS + TEC) / 3)",
        "atributos": ("passe", "visao", "tecnica"),
        "formula_tipo": "soma_dividida",
        "divisor": 3,
        "execucao": "Toque suave por cima do primeiro marcador para encobrir a zaga e achar o segundo pau.",
        "efeito": "Concede +3 em CHU ao atacante que receber a bola.",
    },
    "bote": {
        "nome": "Bote",
        "categoria": "Botes e Desarmes Diretos",
        "custo_est": 10,
        "formula": "1d20 + ((DEF + VEL) / 2)",
        "atributos": ("defesa", "velocidade"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Lê a intenção e ataca a bola no momento exato.",
        "efeito": "Rouba a bola de forma limpa e projeta para uma zona livre.",
        "falha": "O zagueiro é ultrapassado e sofre -2 em VEL no turno atual.",
    },
    "carrinho": {
        "nome": "Carrinho",
        "categoria": "Botes e Desarmes Diretos",
        "custo_est": 20,
        "formula": "1d20 + ((DEF + 5 + VEL) / 2)",
        "atributos": ("defesa", "velocidade"),
        "formula_tipo": "soma_constante_dividida",
        "constante": 5,
        "divisor": 2,
        "execucao": "Lança-se ao gramado para cortar a bola no limite.",
        "efeito": "Garante o desarme ou trava o chute/passe.",
        "falha": "Total inferior a 13 resulta em falta; inferior a 8, cartão amarelo.",
        "falha_critica": "Falha crítica resulta em cartão vermelho.",
    },
    "bote_de_cobertura": {
        "nome": "Bote de Cobertura",
        "categoria": "Botes e Desarmes Diretos",
        "custo_est": 15,
        "formula": "1d20 + ((DEF + VIS) / 2)",
        "atributos": ("defesa", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "condicao": "Acionado quando um companheiro é superado na mesma zona ou adjacente.",
        "efeito": "Anula o bônus de velocidade e força novo duelo imediato.",
    },
    "carga_de_ombro": {
        "nome": "Carga de Ombro",
        "categoria": "Jogo de Corpo e Condução Física",
        "custo_est": 10,
        "formula": "1d20 + ((DEF + FIS) / 2)",
        "atributos": ("defesa", "fisico"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Usa massa muscular e ombro para desestabilizar o atacante.",
        "efeito": "O atacante perde equilíbrio, posse e 10 EST.",
        "falha": "Total inferior a 9 resulta em falta.",
    },
    "sombra_protecao_de_bola": {
        "nome": "Sombra / Proteção de Bola",
        "categoria": "Jogo de Corpo e Condução Física",
        "custo_est": 10,
        "formula": "1d20 + ((FIS + VIS) / 2)",
        "atributos": ("fisico", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Coloca o corpo entre o atacante e a bola.",
        "efeito": "Garante tiro de meta ou lateral para a própria equipe.",
    },
    "contencao": {
        "nome": "Contenção",
        "categoria": "Jogo de Corpo e Condução Física",
        "custo_est": 5,
        "formula": "1d20 + ((DEF + VIS - 5) / 2)",
        "atributos": ("defesa", "visao"),
        "formula_tipo": "soma_constante_dividida",
        "constante": -5,
        "divisor": 2,
        "execucao": "Reduz o espaço e força o atacante a decidir sob pressão.",
        "efeito": "Impede avanço de zona e aplica -2 em CHU e PAS no turno.",
    },
    "bloqueio_de_muralha": {
        "nome": "Bloqueio de Muralha",
        "categoria": "Bloqueios e Jogo Aéreo",
        "custo_est": 15,
        "formula": "1d20 + ((FIS + VIS) / 2)",
        "atributos": ("fisico", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Projeta o corpo na trajetória de um arremate ou passe tenso.",
        "efeito": "Bloqueia chutes ao gol ou intercepta cruzamentos rasantes; em falha inferior a 50%, reduz a força da bola em 1d10.",
    },
    "cabeceio_defensivo": {
        "nome": "Cabeceio Defensivo",
        "categoria": "Bloqueios e Jogo Aéreo",
        "custo_est": 10,
        "formula": "1d20 + ((DEF + FIS + VIS) / 3)",
        "atributos": ("defesa", "fisico", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 3,
        "execucao": "Disputa no alto contra cruzamentos ou lançamentos longos na zona de Zaga/Área.",
        "efeito": "Afasta a bola para um campo adjacente aleatório.",
    },
    "armadilha_de_impedimento": {
        "nome": "Armadilha de Impedimento",
        "categoria": "Táticas Especiais e Arbitragem",
        "custo_est": 15,
        "formula": "1d20 + ((DEF + VIS - 5) / 2)",
        "atributos": ("defesa", "visao"),
        "formula_tipo": "soma_constante_dividida",
        "constante": -5,
        "divisor": 2,
        "execucao": "A linha de zagueiros avança em sincronia quando o passe é realizado.",
        "efeito": "Anula a jogada por impedimento e reverte a posse para a defesa via tiro livre indireto.",
    },
    "falta_tatica": {
        "nome": "Falta Tática",
        "categoria": "Táticas Especiais e Arbitragem",
        "custo_est": 20,
        "formula": "1d20 + DEF",
        "atributos": ("defesa",),
        "formula_tipo": "soma_dividida",
        "divisor": 1,
        "efeito": "Interrompe a jogada; a posse vai para o adversário com falta marcada e cartão amarelo obrigatório.",
        "falha": "Com total inferior a 8, o zagueiro é expulso.",
    },
    "marcacao_pressao": {
        "nome": "Marcação Pressão",
        "categoria": "Marcação e Anulação Posicional",
        "custo_est": 10,
        "formula": "1d20 + ((DEF + VEL) / 2)",
        "atributos": ("defesa", "velocidade"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Cola nas costas do atacante sem a bola.",
        "efeito": "Se receber passe, o alvo sofre -5 em TEC e -2 em VIS.",
    },
    "marcacao_espelho": {
        "nome": "Marcação Espelho",
        "categoria": "Marcação e Anulação Posicional",
        "custo_est": 5,
        "formula": "1d20 + ((DEF + VIS) / 2)",
        "atributos": ("defesa", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Acompanha o deslocamento e bloqueia o passe direto.",
        "efeito": "Passe Curto ou Tabela contra o alvo sofre penalidade de 50% em PAS.",
    },
    "leitura_de_interceptacao": {
        "nome": "Leitura de Interceptação",
        "categoria": "Marcação e Anulação Posicional",
        "custo_est": 15,
        "formula": "1d20 + ((DEF + VIS) / 2)",
        "atributos": ("defesa", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Prevê a trajetória do passe antes que chegue ao destino.",
        "efeito": "Corta o passe e recupera a posse de forma limpa.",
    },
}

ACOES_CONDUCAO = (
    "drible_de_corpo",
    "caneta_janela",
    "pique_adiantado",
    "giro_de_pivo",
    "dominio_orientado",
    "corta_luz",
)
ACOES_FINALIZACAO = (
    "chute_colocado",
    "bomba_de_forca",
    "chute_de_trivela",
    "cavada_cobertura",
    "finalizacao_de_primeira_sem_pulo",
    "bicicleta_acrobatico",
    "cabeceio",
    "chute_cruzado",
    "chute_curvo",
    "chute_de_letra_calcanhar",
    "voleio",
)
ACOES_PASSE = (
    "passe_curto",
    "tabela_um_dois",
    "passe_de_calcanhar",
    "passe_pifado",
    "lancamento_longo_de_inversao",
    "passe_de_trivela_em_profundidade",
    "cruzamento_de_linha_de_fundo",
    "cruzamento_tenso_rasante",
    "cruzamento_cavado_curto",
)
ACOES_DEFESA = (
    "bote",
    "carrinho",
    "bote_de_cobertura",
    "carga_de_ombro",
    "sombra_protecao_de_bola",
    "contencao",
    "bloqueio_de_muralha",
    "cabeceio_defensivo",
    "armadilha_de_impedimento",
    "falta_tatica",
    "marcacao_pressao",
    "marcacao_espelho",
    "leitura_de_interceptacao",
)


def carregar_jogadores() -> dict[str, dict[str, Any]]:
    if not JOGADORES_FILE.exists():
        return {}
    with JOGADORES_FILE.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if not isinstance(dados, dict):
        raise ValueError("O arquivo jogadores.json deve conter um objeto JSON.")
    return {
        str(chave): valor
        for chave, valor in dados.items()
        if isinstance(valor, dict)
    }


def salvar_jogadores(jogadores: dict[str, dict[str, Any]]) -> None:
    with JOGADORES_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(jogadores, arquivo, ensure_ascii=False, indent=2)


def interpretar_atributos_bot(valor: str) -> dict[str, int]:
    """Lê atributos no formato ``FIS=80 TEC=70 VIS=65``."""
    atributos = {
        campo: VALOR_INICIAL_ATRIBUTO
        for _, _, campo, _ in ATRIBUTOS
    }
    partes = re.split(r"[\s,;]+", valor.strip())
    if not valor.strip() or any("=" not in parte for parte in partes if parte):
        raise ValueError(
            "Use o formato FIS=80 TEC=70 VIS=65, separando os atributos por espaço."
        )

    encontrados: set[str] = set()
    for parte in partes:
        if not parte:
            continue
        abreviacao, texto_valor = parte.split("=", 1)
        campo = ABREVIACAO_PARA_ATRIBUTO.get(abreviacao.upper())
        if campo is None:
            abreviacoes = ", ".join(ABREVIACAO_PARA_ATRIBUTO)
            raise ValueError(
                f"Atributo inválido: {abreviacao}. Use: {abreviacoes}."
            )
        if campo in encontrados:
            raise ValueError(f"O atributo {abreviacao.upper()} foi informado mais de uma vez.")
        try:
            numero = int(texto_valor)
        except ValueError as erro:
            raise ValueError(f"O valor de {abreviacao.upper()} deve ser um inteiro.") from erro
        if not 0 <= numero <= VALOR_MAXIMO_ATRIBUTO:
            raise ValueError(
                f"O valor de {abreviacao.upper()} deve estar entre 0 e {VALOR_MAXIMO_ATRIBUTO}."
            )
        atributos[campo] = numero
        encontrados.add(campo)
    return atributos


def interpretar_modificador(valor: str | int | float | None) -> tuple[float, bool]:
    """Converte um modificador como '+5', '-10' ou '+20%' em valor e tipo."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return 0.0, False
    if isinstance(valor, (int, float)):
        return float(valor), False
    correspondencia = MODIFICADOR_RE.fullmatch(valor)
    if correspondencia is None:
        raise ValueError("O modificador deve estar no formato +5, -5, +20% ou -10%.")

    sinal, numero, percentual = correspondencia.groups()
    valor_numerico = float(numero.replace(",", "."))
    if sinal == "-":
        valor_numerico *= -1
    return valor_numerico, percentual == "%"


def interpretar_modificador_status(
    valor: str | int | float | None,
) -> tuple[float, bool, str | None]:
    """Converte um modificador e, opcionalmente, o status que ele altera."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return 0.0, False, None
    if isinstance(valor, (int, float)):
        return float(valor), False, None

    correspondencia = MODIFICADOR_STATUS_RE.fullmatch(valor)
    if correspondencia is None:
        raise ValueError(
            "O modificador deve estar no formato +5, -5, +20%, -10%, "
            "-5% DEF ou +10% CHU."
        )

    sinal, numero, percentual, abreviacao = correspondencia.groups()
    valor_numerico = float(numero.replace(",", "."))
    if sinal == "-":
        valor_numerico *= -1
    if abreviacao is None:
        return valor_numerico, percentual == "%", None

    atributo = ABREVIACAO_PARA_ATRIBUTO.get(abreviacao.upper())
    if atributo is None:
        abreviacoes = ", ".join(ABREVIACAO_PARA_ATRIBUTO)
        raise ValueError(f"Status inválido. Use uma destas abreviações: {abreviacoes}.")
    return valor_numerico, percentual == "%", atributo


def modificadores_contextuais(jogador: dict[str, Any]) -> tuple[dict[str, int], float]:
    modificadores: dict[str, int] = {}
    for grupo in (
        MODIFICADORES_POSICAO.get(str(jogador.get("posicao")), {}),
        MODIFICADORES_PORTE.get(str(jogador.get("peso")), {}),
        MODIFICADORES_ALTURA.get(str(jogador.get("altura")), {}),
    ):
        for campo, percentual in grupo.items():
            modificadores[campo] = modificadores.get(campo, 0) + percentual

    fator_estamina = 1.05 if jogador.get("peso") == "atletico" else 1.0
    return modificadores, fator_estamina


def aplicar_modificadores_contextuais(
    jogador: dict[str, Any],
    atributos: tuple[str, ...],
    valores: list[float],
) -> list[float]:
    modificadores, _ = modificadores_contextuais(jogador)
    return [
        max(0.0, valor * (1 + modificadores.get(campo, 0) / 100))
        for campo, valor in zip(atributos, valores)
    ]


def atributos_efetivos(jogador: dict[str, Any]) -> dict[str, float]:
    campos = tuple(campo for _, _, campo, _ in ATRIBUTOS)
    valores = [float(jogador[campo]) for campo in campos]
    valores_efetivos = aplicar_modificadores_contextuais(
        jogador,
        campos,
        valores,
    )
    return dict(zip(campos, valores_efetivos))


def calcular_teste_acao(
    jogador: dict[str, Any],
    atributos_status: tuple[str, ...] | list[str],
    modificador: str | int | float | None = None,
    dado: int | None = None,
    status_base_calculado: float | None = None,
    variacao_dinamica: int | None = None,
) -> dict[str, Any]:
    """Calcula uma ação usando 1d20, média de status e buff/debuff.

    ``dado`` é opcional para testes determinísticos; em produção, o valor é
    sorteado automaticamente entre 1 e 20.
    """
    if not 1 <= len(atributos_status) <= 3:
        raise ValueError("Uma ação deve usar entre um e três atributos de status.")
    atributos_invalidos = [
        campo for campo in atributos_status if campo not in jogador
    ]
    if atributos_invalidos:
        raise ValueError(
            f"Atributo(s) não encontrado(s): {', '.join(atributos_invalidos)}."
        )
    resultado_dado = random.randint(1, 20) if dado is None else int(dado)
    if not 1 <= resultado_dado <= 20:
        raise ValueError("O resultado de 1d20 deve estar entre 1 e 20.")

    valores_status = [float(jogador[campo]) for campo in atributos_status]
    status_base = (
        sum(valores_status) / len(valores_status)
        if status_base_calculado is None
        else float(status_base_calculado)
    )
    if variacao_dinamica is None:
        variacao_dinamica = random.randint(80, 120)
    if not 80 <= variacao_dinamica <= 120:
        raise ValueError("A variação dinâmica deve estar entre 80% e 120%.")
    fator_dinamico = variacao_dinamica / 100
    status_dinamico = status_base * fator_dinamico
    valor_modificador, eh_percentual = interpretar_modificador(modificador)
    status_ajustado = (
        status_dinamico * (1 + valor_modificador / 100)
        if eh_percentual
        else status_dinamico + valor_modificador
    )
    status_ajustado = max(0.0, status_ajustado)
    total = resultado_dado + status_ajustado

    return {
        "d20": resultado_dado,
        "atributos": list(atributos_status),
        "valores_atributos": valores_status,
        "status_base": status_base,
        "fator_dinamico": fator_dinamico,
        "variacao_dinamica": variacao_dinamica,
        "status_dinamico": status_dinamico,
        "modificador": valor_modificador,
        "modificador_percentual": eh_percentual,
        "status_ajustado": status_ajustado,
        "total": total,
    }


def calcular_acao_individual(
    jogador: dict[str, Any],
    acao: str,
    modificador: str | int | float | None = None,
    dado: int | None = None,
    variacao_dinamica: int | None = None,
) -> dict[str, Any]:
    """Calcula uma ação individual cadastrada em ``ACOES_INDIVIDUAIS``."""
    chave = unicodedata.normalize("NFKD", acao.strip().lower())
    chave = "".join(caractere for caractere in chave if not unicodedata.combining(caractere))
    chave = re.sub(r"[^a-z0-9]+", "_", chave).strip("_")
    dados_acao = ACOES_INDIVIDUAIS.get(chave)
    if dados_acao is None:
        raise ValueError(f"Ação individual não encontrada: {acao}.")

    atributos = tuple(dados_acao["atributos"])
    valores_status = [float(jogador[campo]) for campo in atributos]
    valores_status = aplicar_modificadores_contextuais(
        jogador,
        atributos,
        valores_status,
    )
    if chave == "caneta_janela":
        valores_status[0] *= 0.75
    valor_modificador, eh_percentual, atributo_modificado = (
        interpretar_modificador_status(modificador)
    )
    if atributo_modificado is not None:
        if atributo_modificado not in atributos:
            raise ValueError(
                f"O status {atributo_modificado.upper()} não participa desta ação."
            )
        indice = atributos.index(atributo_modificado)
        if eh_percentual:
            valores_status[indice] *= 1 + valor_modificador / 100
        else:
            valores_status[indice] += valor_modificador
        valores_status[indice] = max(0.0, valores_status[indice])
    penalidade_campo = dados_acao.get("penalidade_atributo")
    penalidade = float(dados_acao.get("penalidade_valor", 0))
    if penalidade_campo in atributos:
        indice = atributos.index(penalidade_campo)
        valores_status[indice] = max(0.0, valores_status[indice] + penalidade)

    formula_tipo = dados_acao.get("formula_tipo", "soma_dividida")
    divisor = float(dados_acao.get("divisor", len(valores_status)))
    if formula_tipo == "soma_reduzida_dividida":
        percentual = float(dados_acao.get("percentual", 0))
        status_base = (sum(valores_status) * (1 - percentual / 100)) / divisor
    elif formula_tipo == "primeiro_reduzido_soma_dividida":
        percentual = float(dados_acao.get("percentual", 0))
        primeiro = valores_status[0] * (1 - percentual / 100)
        status_base = (primeiro + sum(valores_status[1:])) / divisor
    elif formula_tipo == "dois_reduzidos_soma_dividida":
        percentuais = dados_acao.get("percentuais", (0, 0))
        reduzidos = [
            valor * (1 - float(percentual) / 100)
            for valor, percentual in zip(valores_status, percentuais)
        ]
        status_base = sum(reduzidos) / divisor
    elif formula_tipo == "tres_reduzidos_soma_dividida":
        percentuais = dados_acao.get("percentuais", (0, 0, 0))
        reduzidos = [
            valor * (1 - float(percentual) / 100)
            for valor, percentual in zip(valores_status, percentuais)
        ]
        status_base = sum(reduzidos) / divisor
    elif formula_tipo == "soma_constante_dividida":
        constante = float(dados_acao.get("constante", 0))
        status_base = (sum(valores_status) + constante) / divisor
    elif formula_tipo == "sem_status":
        status_base = 0.0
    elif formula_tipo == "soma_dividida":
        status_base = sum(valores_status) / divisor
    else:
        raise ValueError(f"Tipo de fórmula não suportado: {formula_tipo}.")

    resultado = calcular_teste_acao(
        jogador,
        atributos,
        modificador=None if atributo_modificado is not None else modificador,
        dado=dado,
        status_base_calculado=status_base,
        variacao_dinamica=variacao_dinamica,
    )
    resultado.update(
        {
            "acao": chave,
            "nome_acao": dados_acao["nome"],
            "categoria": dados_acao["categoria"],
            "custo_est": dados_acao["custo_est"],
            "formula": dados_acao["formula"],
            "execucao": dados_acao.get("execucao"),
            "condicao": dados_acao.get("condicao"),
            "penalidade_execucao": dados_acao.get("penalidade_execucao"),
            "efeito": dados_acao["efeito"],
            "falha": dados_acao.get("falha"),
            "falha_critica": dados_acao.get("falha_critica"),
            "bonus_resultado": dados_acao.get("bonus_resultado", 0),
            "status_base": status_base,
            "modificador_status": atributo_modificado,
        }
    )
    if atributo_modificado is not None:
        resultado["modificador"] = valor_modificador
        resultado["modificador_percentual"] = eh_percentual
        resultado["modificador_status"] = atributo_modificado
    resultado["total"] = round(resultado["total"] + resultado["bonus_resultado"])
    _, fator_estamina = modificadores_contextuais(jogador)
    resultado["estamina_maxima"] = round(
        int(jogador.get("estamina", 0)) * 10 * fator_estamina
    )
    resultado["estamina_atual"] = resultado["estamina_maxima"]
    resultado["estamina_suficiente"] = (
        resultado["estamina_maxima"] >= dados_acao["custo_est"]
    )
    return resultado


def validar_url_media(valor: str, campo: str) -> str:
    url = valor.strip()
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise ValueError(
            f"{campo} deve ser uma URL iniciada por http:// ou https://."
        )
    return url


async def obter_url_anexo(
    interaction: discord.Interaction,
    anexo: discord.Attachment,
) -> str:
    if interaction.channel is None:
        raise RuntimeError("Não foi possível publicar a mídia no canal da interação.")
    arquivo = discord.File(
        io.BytesIO(await anexo.read()),
        filename=anexo.filename,
    )
    mensagem = await interaction.channel.send(file=arquivo)
    if not mensagem.attachments:
        raise RuntimeError("O Discord não retornou uma URL para o arquivo enviado.")
    return mensagem.attachments[0].url


def calcular_xp_limite(nivel: int) -> int:
    return round(100 * (1.1**nivel))


def preparar_jogador(jogador: dict[str, Any], nome: str) -> bool:
    mudou = False
    defaults = {
        "nome": nome,
        "posicao": "Não definida",
        "numero": 0,
        "pe": "Não definido",
        "altura": "Não definida",
        "peso": "Não definido",
        "nacionalidade": "Não definida",
        "imagem_atributos": None,
        "nivel": 0,
        "xp": 0,
        "pontos_disponiveis": 0,
    }
    defaults.update(
        {campo: VALOR_INICIAL_ATRIBUTO for _, _, campo, _ in ATRIBUTOS}
    )
    for campo, valor in defaults.items():
        if campo not in jogador:
            jogador[campo] = valor
            mudou = True

    jogador["nome"] = str(jogador["nome"])
    jogador["posicao"] = str(jogador["posicao"])
    jogador["numero"] = max(0, int(jogador["numero"]))
    jogador["pe"] = str(jogador["pe"])
    jogador["altura"] = str(jogador["altura"])
    jogador["peso"] = str(jogador["peso"])
    jogador["nacionalidade"] = str(jogador["nacionalidade"])
    for campo in ("nivel", "xp", "pontos_disponiveis"):
        valor_atual = int(jogador[campo])
        valor_normalizado = max(0, valor_atual)
        jogador[campo] = valor_normalizado
        mudou = mudou or valor_atual != valor_normalizado

    for campo in ATRIBUTOS_EDITAVEIS:
        valor_atual = int(jogador[campo])
        valor_normalizado = min(VALOR_MAXIMO_ATRIBUTO, max(0, valor_atual))
        jogador[campo] = valor_normalizado
        mudou = mudou or valor_atual != valor_normalizado

    while jogador["xp"] >= calcular_xp_limite(jogador["nivel"]):
        jogador["xp"] -= calcular_xp_limite(jogador["nivel"])
        jogador["nivel"] += 1
        jogador["pontos_disponiveis"] += 5
        mudou = True
    return mudou


def barra_xp(jogador: dict[str, Any]) -> str:
    limite = calcular_xp_limite(int(jogador["nivel"]))
    xp = int(jogador["xp"])
    comprimento = 20
    preenchido = round((xp / limite) * comprimento) if limite else 0
    preenchido = min(comprimento, max(0, preenchido))
    return f"`{'█' * preenchido}{'░' * (comprimento - preenchido)}` {xp}/{limite} XP"


def criar_xp_embed(jogador: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Experiência de {jogador['nome']}",
        description=(
            f"**Nível:** `{jogador['nivel']}`\n"
            f"**Pontos disponíveis:** `{jogador['pontos_disponiveis']}`\n\n"
            f"{barra_xp(jogador)}"
        ),
        colour=discord.Colour.blurple(),
    )
    embed.set_footer(text="Sistema de experiência • FuteBot")
    return embed


def adicionar_campos_em_linhas(
    children: list[discord.ui.Item],
    campos: list[Any],
) -> None:
    for campo in campos:
        valor = str(campo.value).replace("``", "").replace("`", "")
        valor_formatado = f"``{valor}``" if "NÍVEL" not in campo.name else str(campo.value)
        children.append(
            discord.ui.TextDisplay(f"**{campo.name}:** {valor_formatado}")
        )


def formatar_cabecalho(texto: str) -> str:
    linhas = texto.replace("\n\n\n", "\n\n").splitlines()
    indice_nome = next(
        (indice for indice, linha in enumerate(linhas) if linha.startswith("# ")),
        None,
    )
    if indice_nome is None:
        return "\n".join(linhas)
    nome = linhas[indice_nome]
    restante = linhas[:indice_nome] + linhas[indice_nome + 1:]
    return "\n".join([nome, *restante])


def criar_layout_view(
    embed: discord.Embed,
    timeout: float = 180,
    content: str | None = None,
) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=timeout)
    texto = f"{content}\n\n" if content else ""
    texto += embed.description or ""
    texto = formatar_cabecalho(texto)

    thumbnail = embed.thumbnail.url
    if thumbnail:
        children: list[discord.ui.Item] = [
            discord.ui.Section(
                discord.ui.TextDisplay(texto),
                accessory=discord.ui.Thumbnail(thumbnail),
            )
        ]
    else:
        children = [discord.ui.TextDisplay(texto)]
    if embed.fields:
        children.append(
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small)
        )
        adicionar_campos_em_linhas(children, list(embed.fields))
    imagem = embed.image.url
    if imagem:
        children.append(
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small)
        )
        children.append(
            discord.ui.MediaGallery(discord.MediaGalleryItem(imagem))
        )
    if embed.footer and embed.footer.text:
        children.append(
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small)
        )
        children.append(discord.ui.TextDisplay(f"*{embed.footer.text}*"))

    view.add_item(
        discord.ui.Container(
            *children,
            accent_color=embed.colour,
        )
    )
    return view


def criar_personagem_embed(jogador: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        description=(
            "## ﹙🧾﹚ ATLETA\n"
            f"# {jogador['nome']}"
        ),
        color=discord.Colour.dark_green(),
    )
    if jogador.get("imagem"):
        embed.set_thumbnail(url=str(jogador["imagem"]))
    if jogador.get("banner"):
        embed.set_image(url=str(jogador["banner"]))
    embed.add_field(
        name="﹙🎖️﹚ NÍVEL",
        value=f"`{jogador['nivel']}` ({barra_xp(jogador)})",
        inline=False,
    )
    embed.add_field(name="﹙⚽﹚ POSIÇÃO", value=jogador["posicao"], inline=True)
    embed.add_field(name="﹙🔢﹚ CAMISA", value=f"{jogador['numero']}", inline=True)
    embed.add_field(name="﹙🦶﹚ PÉ DOMINANTE", value=jogador["pe"], inline=True)
    altura = ROTULOS_ALTURA.get(str(jogador["altura"]), str(jogador["altura"]))
    peso = ROTULOS_PORTE.get(str(jogador["peso"]), str(jogador["peso"]))
    embed.add_field(name="﹙📏﹚ ALTURA", value=altura, inline=True)
    embed.add_field(name="﹙⚖️﹚ PESO", value=peso, inline=True)
    embed.add_field(name="﹙🌎﹚ NACIONALIDADE", value=jogador["nacionalidade"], inline=True)
    embed.add_field(
        name="﹙📊﹚ ATRIBUTOS",
        value="Use `/atributos` para visualizar a tabela completa.",
        inline=False,
    )
    embed.set_footer(text="Ficha de atleta • Informações essenciais")
    return embed


def barra_atributo(valor: float) -> str:
    comprimento = 20
    valor_limitado = min(VALOR_MAXIMO_ATRIBUTO, max(0, valor))
    preenchido = round((valor_limitado / VALOR_MAXIMO_ATRIBUTO) * comprimento)
    return f"`{'█' * preenchido}{'░' * (comprimento - preenchido)}` {valor:.0f}/100"


def criar_atributos_embed(jogador: dict[str, Any]) -> discord.Embed:
    linhas = []
    valores_efetivos = atributos_efetivos(jogador)
    modificadores, fator_estamina = modificadores_contextuais(jogador)
    for emoji, nome, campo, abreviacao in ATRIBUTOS:
        valor = valores_efetivos[campo]
        percentual = modificadores.get(campo, 0)
        if campo == "estamina":
            percentual = round((fator_estamina - 1) * 100)
            estamina_maxima = round(valor * 10 * fator_estamina)
            descricao_valor = (
                f"{estamina_maxima} pontos ({percentual:+d}%) "
                f"({valor:.0f} × 10)"
            )
        else:
            descricao_valor = f"{valor:.0f} ({percentual:+d}%)"
        linhas.append(
            f"**{emoji} {nome} (`{abreviacao}`)** — {descricao_valor}\n"
            f"{barra_atributo(valor)}"
        )

    embed = discord.Embed(
        title=f"Atributos de {jogador['nome']}",
        description="\n\n".join(linhas),
        colour=discord.Colour.green(),
    )
    if jogador.get("imagem_atributos"):
        embed.set_image(url=str(jogador["imagem_atributos"]))
    embed.add_field(
        name="🎯 Pontos disponíveis",
        value=f"`{jogador['pontos_disponiveis']}`",
        inline=False,
    )
    embed.set_footer(text="Tabela de atributos • FuteBot")
    return embed


class AtributoSelect(discord.ui.Select):
    def __init__(self, tabela: "TabelaAtributosView") -> None:
        self.tabela = tabela
        super().__init__(
            placeholder="🔽 Selecione um atributo",
            options=[
                discord.SelectOption(
                    label=nome,
                    value=campo,
                    description=f"Distribuir pontos em {abreviacao}",
                )
                for _, nome, campo, abreviacao in ATRIBUTOS
            ],
        )

    def atualizar_selecao(self) -> None:
        selecionado = self.tabela.atributo_selecionado
        for opcao in self.options:
            opcao.default = opcao.value == selecionado
        if selecionado is None:
            self.placeholder = "🔽 Selecione um atributo"
            return
        opcao = next(
            opcao for opcao in self.options if opcao.value == selecionado
        )
        self.placeholder = f"✅ {opcao.label}"

    async def callback(self, interaction: discord.Interaction) -> None:
        self.tabela.atributo_selecionado = self.values[0]
        self.tabela.reconstruir_layout()
        await interaction.response.edit_message(view=self.tabela)


class QuantidadeAtributoModal(discord.ui.Modal, title="Adicionar pontos"):
    quantidade = discord.ui.TextInput(
        label="Quantidade de pontos",
        placeholder="Ex.: 5",
        min_length=1,
        max_length=3,
        required=True,
    )

    def __init__(self, tabela: "TabelaAtributosView") -> None:
        super().__init__()
        self.tabela = tabela

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            quantidade = int(str(self.quantidade.value))
        except ValueError:
            await interaction.response.send_message(
                "Informe uma quantidade inteira válida.",
                ephemeral=True,
            )
            return
        if quantidade <= 0:
            await interaction.response.send_message(
                "A quantidade deve ser maior que zero.",
                ephemeral=True,
            )
            return
        campo = self.tabela.atributo_selecionado
        if campo not in ATRIBUTOS_EDITAVEIS:
            await interaction.response.send_message(
                "Selecione um atributo válido antes de adicionar pontos.",
                ephemeral=True,
            )
            return
        atual = int(self.tabela.jogador.get(campo, 0))
        disponiveis = int(self.tabela.jogador.get("pontos_disponiveis", 0))
        permitido = min(quantidade, disponiveis, VALOR_MAXIMO_ATRIBUTO - atual)
        if permitido <= 0:
            await interaction.response.send_message(
                "Não há pontos disponíveis ou esse atributo já está no máximo.",
                ephemeral=True,
            )
            return
        self.tabela.alterar_atributo(campo, permitido)
        await self.tabela.atualizar_mensagem(interaction)


class TabelaAtributosView(discord.ui.LayoutView):
    def __init__(
        self,
        jogador: dict[str, Any],
        jogadores: dict[str, dict[str, Any]],
        chave: str,
        dono_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.jogador = jogador
        self.jogadores = jogadores
        self.chave = chave
        self.dono_id = dono_id
        self.atributo_selecionado: str | None = None
        self.salvo = False
        self.reconstruir_layout()

    def alterar_atributo(self, campo: str, delta: int) -> None:
        if campo not in ATRIBUTOS_EDITAVEIS or self.salvo:
            return
        pontos = int(self.jogador.get("pontos_disponiveis", 0))
        valor_atual = int(self.jogador.get(campo, 0))
        if delta > 0 and (pontos < delta or valor_atual + delta > VALOR_MAXIMO_ATRIBUTO):
            return
        if delta < 0 and valor_atual + delta < 0:
            return
        self.jogador[campo] = valor_atual + delta
        self.jogador["pontos_disponiveis"] = pontos - delta

    def reconstruir_layout(self) -> None:
        self.clear_items()
        seletor = AtributoSelect(self)
        seletor.atualizar_selecao()
        pontos = int(self.jogador.get("pontos_disponiveis", 0))
        valor_atual = (
            int(self.jogador.get(self.atributo_selecionado, 0))
            if self.atributo_selecionado
            else 0
        )
        aumentar = discord.ui.Button(
            label="➕",
            style=discord.ButtonStyle.success,
            disabled=(
                self.salvo
                or self.atributo_selecionado is None
                or pontos <= 0
                or valor_atual >= VALOR_MAXIMO_ATRIBUTO
            ),
        )
        diminuir = discord.ui.Button(
            label="➖",
            style=discord.ButtonStyle.secondary,
            disabled=(
                self.salvo
                or self.atributo_selecionado is None
                or valor_atual <= 0
            ),
        )
        salvar = discord.ui.Button(
            label="💾",
            style=discord.ButtonStyle.primary,
            disabled=self.salvo,
        )
        aumentar.callback = self._aumentar_callback
        diminuir.callback = self._diminuir_callback
        salvar.callback = self._salvar_callback
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    "Selecione um atributo, use ➕ para adicionar pontos "
                    "ou ➖ para remover um ponto. Clique em 💾 para salvar."
                ),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(criar_atributos_embed(self.jogador).description or ""),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(aumentar, salvar, diminuir),
                discord.ui.ActionRow(seletor),
                accent_color=discord.Colour.green(),
            )
        )

    async def atualizar_mensagem(self, interaction: discord.Interaction) -> None:
        self.reconstruir_layout()
        await interaction.response.edit_message(view=self)

    async def _aumentar_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(QuantidadeAtributoModal(self))

    async def _diminuir_callback(self, interaction: discord.Interaction) -> None:
        if self.atributo_selecionado:
            self.alterar_atributo(self.atributo_selecionado, -1)
        await self.atualizar_mensagem(interaction)

    async def _salvar_callback(self, interaction: discord.Interaction) -> None:
        self.salvo = True
        self.jogadores[self.chave] = self.jogador
        salvar_jogadores(self.jogadores)
        await self.atualizar_mensagem(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.dono_id:
            await interaction.response.send_message(
                "Apenas quem abriu esta tabela pode alterá-la.",
                ephemeral=True,
            )
            return False
        return True


def criar_ranking_embed(
    ranking: list[tuple[str, dict[str, Any]]],
) -> discord.Embed:
    linhas = [
        (
            f"`{indice:02}` **{discord.utils.escape_markdown(str(jogador['nome']))}** "
            f"• Nível `{jogador['nivel']}` • {barra_xp(jogador)}"
        )
        for indice, (_, jogador) in enumerate(ranking[:LIMITE_RANKING], start=1)
    ]
    embed = discord.Embed(
        title="Tabela de experiência",
        description="\n".join(linhas) if linhas else "Nenhum jogador registrado.",
        colour=discord.Colour.gold(),
    )
    embed.set_footer(text=f"Exibindo até {LIMITE_RANKING} jogadores")
    return embed


class FuteBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!",
            intents=intents,
            case_insensitive=True,
        )

    async def setup_hook(self) -> None:
        guild_id = GUILD_ID or os.getenv("DISCORD_GUILD_ID")
        if guild_id and guild_id.isdigit():
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
            except discord.Forbidden as erro:
                print(
                    "Não foi possível sincronizar os comandos no servidor "
                    f"{guild_id}: o bot não tem acesso a esse servidor. "
                    "Confira o ID e se o bot foi convidado com os escopos "
                    "bot e applications.commands."
                )
                self.tree.clear_commands(guild=guild)
                raise RuntimeError(
                    "DISCORD_GUILD_ID aponta para um servidor sem acesso para este bot."
                ) from erro
        else:
            await self.tree.sync()


bot = FuteBot()


@bot.event
async def on_ready() -> None:
    print(f"FuteBot conectado como {bot.user}")


def opcoes_de_acoes(
    chaves: tuple[str, ...],
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=ACOES_INDIVIDUAIS[chave]["nome"], value=chave)
        for chave in chaves
    ]


def criar_acao_embed(resultado: dict[str, Any]) -> discord.Embed:
    fator = f"{resultado['variacao_dinamica']}%"
    modificador = resultado["modificador"]
    sufixo_modificador = "%" if resultado["modificador_percentual"] else ""
    status_modificador = resultado.get("modificador_status")
    texto_modificador = f"{modificador:g}{sufixo_modificador}"
    if status_modificador:
        texto_modificador += f" {status_modificador.upper()}"
    descricao = (
        f"## ﹙⚽﹚ {resultado['categoria']}\n"
        f"# {resultado['nome_acao']}\n\n"
        f"**Fórmula:** `{resultado['formula']}`\n"
        f"**Custo de EST:** `{resultado['custo_est']}`\n"
        f"\n"
        f"**D20:** `{resultado['d20']}`\n"
        f"**Status base:** `{resultado['status_base']:.2f}`\n"
        f"**Variação dinâmica:** `{fator}`\n"
        f"**Modificador:** `{texto_modificador}`\n"
        f"## Total: `{resultado['total']}`"
    )
    embed = discord.Embed(
        title="Resultado da ação",
        description=descricao,
        colour=discord.Colour.orange(),
    )
    if resultado.get("condicao"):
        embed.add_field(name="Condição", value=resultado["condicao"], inline=False)
    if resultado.get("execucao"):
        embed.add_field(name="Execução", value=resultado["execucao"], inline=False)
    if resultado.get("penalidade_execucao"):
        embed.add_field(
            name="Penalidade de execução",
            value=resultado["penalidade_execucao"],
            inline=False,
        )
    embed.add_field(name="Efeito de sucesso", value=resultado["efeito"], inline=False)
    if resultado.get("falha"):
        embed.add_field(name="Risco / falha", value=resultado["falha"], inline=False)
    if resultado.get("falha_critica"):
        embed.add_field(
            name="Falha crítica",
            value=resultado["falha_critica"],
            inline=False,
        )
    if not resultado["estamina_suficiente"]:
        embed.set_footer(text="Atenção: estamina insuficiente para executar esta ação.")
    return embed


async def executar_acao_do_jogador(
    interaction: discord.Interaction,
    acao: str,
    modificador: str | None,
    variacao_dinamica: int | None,
    bot_alvo: str | None,
    categoria: tuple[str, ...],
) -> None:
    jogadores = carregar_jogadores()
    chave_jogador = str(interaction.user.id)
    nome_exibicao = interaction.user.display_name
    if bot_alvo:
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Somente administradores podem usar bots nas ações.",
                ephemeral=True,
            )
            return
        chave_nome = unicodedata.normalize("NFKD", bot_alvo.strip().lower())
        chave_nome = "".join(
            caractere
            for caractere in chave_nome
            if not unicodedata.combining(caractere)
        )
        chave_nome = re.sub(r"[^a-z0-9]+", "_", chave_nome).strip("_")
        chave_jogador = f"bot:{chave_nome}"
        nome_exibicao = bot_alvo.strip()

    jogador = jogadores.get(chave_jogador)
    if jogador is None:
        await interaction.response.send_message(
            (
                "Esse bot não existe. Confira o nome usado em `/criar_bot`."
                if bot_alvo
                else "Você ainda não possui uma ficha. Use `/criar`."
            ),
            ephemeral=True,
        )
        return
    dados_acao = ACOES_INDIVIDUAIS.get(acao)
    if dados_acao is None or not any(
        termo in dados_acao["categoria"] for termo in categoria
    ):
        await interaction.response.send_message(
            "Essa ação não pertence a este comando.",
            ephemeral=True,
        )
        return
    if preparar_jogador(jogador, nome_exibicao):
        salvar_jogadores(jogadores)
    try:
        resultado = calcular_acao_individual(
            jogador,
            acao,
            modificador,
            variacao_dinamica=variacao_dinamica,
        )
    except ValueError as erro:
        await interaction.response.send_message(str(erro), ephemeral=True)
        return
    await interaction.response.send_message(embed=criar_acao_embed(resultado))


@bot.tree.command(name="conducao", description="Executa uma ação de condução.")
@app_commands.describe(
    acao="Ação de drible, domínio ou recepção",
    modificador="Opcional: +5, -5, +20%, -10%, -5% DEF ou +10% CHU",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível somente para administradores",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_CONDUCAO))
async def conducao(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    modificador: str | None = None,
    variacao_dinamica: int | None = None,
    bot_alvo: str | None = None,
) -> None:
    await executar_acao_do_jogador(
        interaction,
        acao.value,
        modificador,
        variacao_dinamica,
        bot_alvo,
        ("Dribles", "Domínio"),
    )


@bot.tree.command(name="finalizacao", description="Executa uma finalização.")
@app_commands.describe(
    acao="Tipo de finalização",
    modificador="Opcional: +5, -5, +20%, -10%, -5% DEF ou +10% CHU",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível somente para administradores",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_FINALIZACAO))
async def finalizacao(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    modificador: str | None = None,
    variacao_dinamica: int | None = None,
    bot_alvo: str | None = None,
) -> None:
    await executar_acao_do_jogador(
        interaction,
        acao.value,
        modificador,
        variacao_dinamica,
        bot_alvo,
        ("Finalizações",),
    )


@bot.tree.command(name="passe", description="Executa uma ação de passe.")
@app_commands.describe(
    acao="Ação de passe, cruzamento ou lançamento",
    modificador="Opcional: +5, -5, +20%, -10%, -5% DEF ou +10% CHU",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível somente para administradores",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_PASSE))
async def passe(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    modificador: str | None = None,
    variacao_dinamica: int | None = None,
    bot_alvo: str | None = None,
) -> None:
    await executar_acao_do_jogador(
        interaction,
        acao.value,
        modificador,
        variacao_dinamica,
        bot_alvo,
        ("Passes", "Cruzamentos"),
    )


@bot.tree.command(name="defesa", description="Executa uma ação defensiva.")
@app_commands.describe(
    acao="Bote, carrinho, marcação ou interceptação",
    modificador="Opcional: +5, -5, +20%, -10%, -5% DEF ou +10% CHU",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível somente para administradores",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_DEFESA))
async def defesa(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    modificador: str | None = None,
    variacao_dinamica: int | None = None,
    bot_alvo: str | None = None,
) -> None:
    await executar_acao_do_jogador(
        interaction,
        acao.value,
        modificador,
        variacao_dinamica,
        bot_alvo,
        (
            "Botes",
            "Jogo de Corpo",
            "Bloqueios",
            "Táticas Especiais",
            "Marcação",
        ),
    )


@bot.tree.command(name="criar", description="Cria sua ficha de atleta.")
@app_commands.describe(
    nome="Nome do atleta",
    posicao="Posição principal em campo",
    numero="Número da camisa, entre 1 e 99",
    pe="Pé dominante",
    altura="Faixa de estatura",
    peso="Tipo físico",
    nacionalidade="Nacionalidade do atleta",
    imagem="URL opcional da imagem do atleta",
    banner="URL opcional do banner da ficha",
    imagem_arquivo="Arquivo opcional da imagem do atleta",
    banner_arquivo="Arquivo opcional do banner da ficha",
)
@app_commands.choices(
    posicao=[
        app_commands.Choice(name="Goleiro", value="Goleiro"),
        app_commands.Choice(name="Zagueiro", value="Zagueiro"),
        app_commands.Choice(name="Lateral", value="Lateral"),
        app_commands.Choice(name="Volante", value="Volante"),
        app_commands.Choice(name="Meia", value="Meia"),
        app_commands.Choice(name="Ponta", value="Ponta"),
        app_commands.Choice(name="Atacante", value="Atacante"),
    ],
    pe=[
        app_commands.Choice(name="Destro", value="Destro"),
        app_commands.Choice(name="Canhoto", value="Canhoto"),
        app_commands.Choice(name="Ambidestro", value="Ambidestro"),
    ],
    altura=[
        app_commands.Choice(name="Baixo (1,65 m a 1,73 m)", value="baixo"),
        app_commands.Choice(name="Estatura Média (1,74 m a 1,85 m)", value="medio"),
        app_commands.Choice(name="Alto (1,86 m a 2,00 m)", value="alto"),
    ],
    peso=[
        app_commands.Choice(name="Ectomorfo Magro / Seco", value="ectomorfo"),
        app_commands.Choice(name="Atlético Leve / Fibrado", value="atletico"),
        app_commands.Choice(name="Equilibrado / Porte Padrão", value="equilibrado"),
        app_commands.Choice(name="Mesomorfo Forte / Denso", value="mesomorfo"),
        app_commands.Choice(name="Tanque / Pesado", value="tanque"),
    ],
)
async def criar(
    interaction: discord.Interaction,
    nome: str,
    posicao: app_commands.Choice[str],
    numero: int,
    pe: app_commands.Choice[str],
    altura: app_commands.Choice[str],
    peso: app_commands.Choice[str],
    nacionalidade: str,
    imagem: str | None = None,
    banner: str | None = None,
    imagem_arquivo: discord.Attachment | None = None,
    banner_arquivo: discord.Attachment | None = None,
) -> None:
    if not 1 <= numero <= 99:
        await interaction.response.send_message(
            "O número da camisa deve estar entre 1 e 99.",
            ephemeral=True,
        )
        return
    if not nome.strip() or not nacionalidade.strip():
        await interaction.response.send_message(
            "Os campos informados não podem estar vazios.",
            ephemeral=True,
        )
        return
    try:
        imagem = (
            await obter_url_anexo(interaction, imagem_arquivo)
            if imagem_arquivo
            else validar_url_media(imagem, "A imagem")
            if imagem
            else None
        )
        banner = (
            await obter_url_anexo(interaction, banner_arquivo)
            if banner_arquivo
            else validar_url_media(banner, "O banner")
            if banner
            else None
        )
    except (ValueError, RuntimeError) as erro:
        await interaction.response.send_message(str(erro), ephemeral=True)
        return

    jogadores = carregar_jogadores()
    chave = str(interaction.user.id)
    if chave in jogadores:
        await interaction.response.send_message(
            "Você já possui uma ficha. Use `/personagem` para visualizá-la.",
            ephemeral=True,
        )
        return

    jogador: dict[str, Any] = {
        "nome": nome.strip(),
        "posicao": posicao.value,
        "numero": numero,
        "pe": pe.value,
        "altura": altura.value,
        "peso": peso.value,
        "nacionalidade": nacionalidade.strip(),
        "imagem": imagem,
        "banner": banner,
    }
    preparar_jogador(jogador, nome.strip())
    jogadores[chave] = jogador
    salvar_jogadores(jogadores)

    await interaction.response.send_message(
        view=criar_layout_view(
            criar_personagem_embed(jogador),
            content="Atleta criado com sucesso!",
        ),
    )


@bot.tree.command(name="editar", description="Edita sua ficha de atleta.")
@app_commands.describe(
    nome="Novo nome do atleta",
    posicao="Nova posição principal",
    numero="Novo número da camisa, entre 1 e 99",
    pe="Novo pé dominante",
    altura="Nova faixa de estatura",
    peso="Novo tipo físico",
    nacionalidade="Nova nacionalidade",
    imagem="Nova URL da imagem do atleta",
    banner="Nova URL do banner da ficha",
    imagem_atributos="Nova URL da imagem da tabela de atributos",
    imagem_arquivo="Novo arquivo da imagem do atleta",
    banner_arquivo="Novo arquivo do banner da ficha",
    imagem_atributos_arquivo="Novo arquivo da imagem dos atributos",
)
@app_commands.choices(
    posicao=[
        app_commands.Choice(name="Goleiro", value="Goleiro"),
        app_commands.Choice(name="Zagueiro", value="Zagueiro"),
        app_commands.Choice(name="Lateral", value="Lateral"),
        app_commands.Choice(name="Volante", value="Volante"),
        app_commands.Choice(name="Meia", value="Meia"),
        app_commands.Choice(name="Ponta", value="Ponta"),
        app_commands.Choice(name="Atacante", value="Atacante"),
    ],
    pe=[
        app_commands.Choice(name="Destro", value="Destro"),
        app_commands.Choice(name="Canhoto", value="Canhoto"),
        app_commands.Choice(name="Ambidestro", value="Ambidestro"),
    ],
    altura=[
        app_commands.Choice(name="Baixo (1,65 m a 1,73 m)", value="baixo"),
        app_commands.Choice(name="Estatura Média (1,74 m a 1,85 m)", value="medio"),
        app_commands.Choice(name="Alto (1,86 m a 2,00 m)", value="alto"),
    ],
    peso=[
        app_commands.Choice(name="Ectomorfo Magro / Seco", value="ectomorfo"),
        app_commands.Choice(name="Atlético Leve / Fibrado", value="atletico"),
        app_commands.Choice(name="Equilibrado / Porte Padrão", value="equilibrado"),
        app_commands.Choice(name="Mesomorfo Forte / Denso", value="mesomorfo"),
        app_commands.Choice(name="Tanque / Pesado", value="tanque"),
    ],
)
async def editar(
    interaction: discord.Interaction,
    nome: str | None = None,
    posicao: app_commands.Choice[str] | None = None,
    numero: int | None = None,
    pe: app_commands.Choice[str] | None = None,
    altura: app_commands.Choice[str] | None = None,
    peso: app_commands.Choice[str] | None = None,
    nacionalidade: str | None = None,
    imagem: str | None = None,
    banner: str | None = None,
    imagem_atributos: str | None = None,
    imagem_arquivo: discord.Attachment | None = None,
    banner_arquivo: discord.Attachment | None = None,
    imagem_atributos_arquivo: discord.Attachment | None = None,
) -> None:
    await interaction.response.defer()
    jogadores = carregar_jogadores()
    jogador = jogadores.get(str(interaction.user.id))
    if jogador is None:
        await interaction.followup.send(
            "Você ainda não possui uma ficha. Use `/criar`.",
            ephemeral=True,
        )
        return

    if numero is not None and not 1 <= numero <= 99:
        await interaction.followup.send(
            "O número da camisa deve estar entre 1 e 99.",
            ephemeral=True,
        )
        return
    try:
        nova_imagem = (
            await obter_url_anexo(interaction, imagem_arquivo)
            if imagem_arquivo
            else validar_url_media(imagem, "A imagem")
            if imagem
            else None
        )
        novo_banner = (
            await obter_url_anexo(interaction, banner_arquivo)
            if banner_arquivo
            else validar_url_media(banner, "O banner")
            if banner
            else None
        )
        nova_imagem_atributos = (
            await obter_url_anexo(interaction, imagem_atributos_arquivo)
            if imagem_atributos_arquivo
            else validar_url_media(imagem_atributos, "A imagem dos atributos")
            if imagem_atributos
            else None
        )
    except (ValueError, RuntimeError) as erro:
        await interaction.followup.send(str(erro), ephemeral=True)
        return

    alteracoes: dict[str, Any] = {}
    valores = {
        "nome": nome.strip() if nome is not None else None,
        "posicao": posicao.value if posicao is not None else None,
        "numero": numero,
        "pe": pe.value if pe is not None else None,
        "altura": altura.value if altura is not None else None,
        "peso": peso.value if peso is not None else None,
        "nacionalidade": (
            nacionalidade.strip() if nacionalidade is not None else None
        ),
        "imagem": nova_imagem,
        "banner": novo_banner,
        "imagem_atributos": nova_imagem_atributos,
    }
    alteracoes.update(
        {campo: valor for campo, valor in valores.items() if valor is not None}
    )
    if not alteracoes:
        await interaction.followup.send(
            "Informe pelo menos um campo para alterar.",
            ephemeral=True,
        )
        return
    if any(
        isinstance(valor, str) and not valor
        for valor in alteracoes.values()
    ):
        await interaction.followup.send(
            "Os campos de texto não podem ficar vazios.",
            ephemeral=True,
        )
        return

    jogador.update(alteracoes)
    preparar_jogador(jogador, str(jogador["nome"]))
    salvar_jogadores(jogadores)
    await interaction.followup.send(
        view=criar_layout_view(
            criar_personagem_embed(jogador),
            content="Ficha atualizada com sucesso!",
        ),
    )


@bot.tree.command(name="personagem", description="Mostra a ficha de um atleta.")
@app_commands.describe(usuario="Atleta cuja ficha será exibida")
async def personagem(
    interaction: discord.Interaction,
    usuario: discord.User | None = None,
) -> None:
    jogadores = carregar_jogadores()
    alvo = usuario or interaction.user
    jogador = jogadores.get(str(alvo.id))
    if jogador is None:
        await interaction.response.send_message(
            (
                "Você ainda não possui uma ficha. Use `/criar`."
                if usuario is None
                else f"{alvo.mention} ainda não possui uma ficha."
            ),
            ephemeral=True,
        )
        return

    if preparar_jogador(jogador, alvo.display_name):
        salvar_jogadores(jogadores)
    await interaction.response.send_message(
        view=criar_layout_view(criar_personagem_embed(jogador))
    )


@bot.tree.command(name="xp", description="Mostra seu nível e progresso de experiência.")
async def xp(interaction: discord.Interaction) -> None:
    jogadores = carregar_jogadores()
    jogador = jogadores.get(str(interaction.user.id))
    if jogador is None:
        jogador = {"nome": interaction.user.display_name}
        jogadores[str(interaction.user.id)] = jogador
        preparar_jogador(jogador, interaction.user.display_name)
        salvar_jogadores(jogadores)
    elif preparar_jogador(jogador, interaction.user.display_name):
        salvar_jogadores(jogadores)

    await interaction.response.send_message(
        embed=criar_xp_embed(jogador),
        ephemeral=True,
    )


@bot.tree.command(name="atributos", description="Mostra a tabela de atributos de um atleta.")
@app_commands.describe(usuario="Atleta cujos atributos serão exibidos")
async def atributos(
    interaction: discord.Interaction,
    usuario: discord.User | None = None,
) -> None:
    jogadores = carregar_jogadores()
    alvo = usuario or interaction.user
    jogador = jogadores.get(str(alvo.id))
    if jogador is None:
        jogador = {"nome": interaction.user.display_name}
        if usuario is not None:
            await interaction.response.send_message(
                f"{alvo.mention} ainda não possui uma ficha.",
                ephemeral=True,
            )
            return
        jogadores[str(interaction.user.id)] = jogador
        preparar_jogador(jogador, interaction.user.display_name)
        salvar_jogadores(jogadores)
    elif preparar_jogador(jogador, alvo.display_name):
        salvar_jogadores(jogadores)

    if usuario is None:
        await interaction.response.send_message(
            view=TabelaAtributosView(
                jogador,
                jogadores,
                str(interaction.user.id),
                interaction.user.id,
            ),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=criar_atributos_embed(jogador),
            ephemeral=True,
        )


@bot.tree.command(name="atributo", description="Mostra os atributos de um atleta.")
@app_commands.describe(usuario="Atleta cujos atributos serão exibidos")
async def atributo(
    interaction: discord.Interaction,
    usuario: discord.User | None = None,
) -> None:
    jogadores = carregar_jogadores()
    alvo = usuario or interaction.user
    jogador = jogadores.get(str(alvo.id))
    if jogador is None:
        if usuario is not None:
            await interaction.response.send_message(
                f"{alvo.mention} ainda não possui uma ficha.",
                ephemeral=True,
            )
            return
        jogador = {"nome": interaction.user.display_name}
        jogadores[str(interaction.user.id)] = jogador
        preparar_jogador(jogador, interaction.user.display_name)
        salvar_jogadores(jogadores)
    elif preparar_jogador(jogador, alvo.display_name):
        salvar_jogadores(jogadores)

    if usuario is None:
        await interaction.response.send_message(
            view=TabelaAtributosView(
                jogador,
                jogadores,
                str(interaction.user.id),
                interaction.user.id,
            ),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=criar_atributos_embed(jogador),
            ephemeral=True,
        )


@bot.tree.command(
    name="distribuir_atributo",
    description="Distribui seus pontos disponíveis em um atributo.",
)
@app_commands.describe(
    atributo="Atributo que receberá os pontos",
    quantidade="Quantidade de pontos para distribuir",
)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name=nome, value=campo)
        for _, nome, campo, _ in ATRIBUTOS
    ]
)
async def distribuir_atributo(
    interaction: discord.Interaction,
    atributo: app_commands.Choice[str],
    quantidade: int,
) -> None:
    if quantidade <= 0:
        await interaction.response.send_message(
            "A quantidade deve ser maior que zero.",
            ephemeral=True,
        )
        return

    jogadores = carregar_jogadores()
    jogador = jogadores.get(str(interaction.user.id))
    if jogador is None:
        await interaction.response.send_message(
            "Você ainda não possui um registro de jogador.",
            ephemeral=True,
        )
        return

    preparar_jogador(jogador, interaction.user.display_name)
    campo = atributo.value
    pontos = int(jogador["pontos_disponiveis"])
    valor_atual = int(jogador[campo])
    permitido = min(
        quantidade,
        pontos,
        VALOR_MAXIMO_ATRIBUTO - valor_atual,
    )
    if permitido <= 0:
        await interaction.response.send_message(
            "Você não possui pontos disponíveis ou esse atributo já está no máximo.",
            ephemeral=True,
        )
        return

    jogador[campo] = valor_atual + permitido
    jogador["pontos_disponiveis"] = pontos - permitido
    salvar_jogadores(jogadores)
    await interaction.response.send_message(
        f"**{permitido}** ponto(s) adicionados a **{atributo.name}**. "
        f"Novo valor: **{jogador[campo]}**.",
        ephemeral=True,
    )


@bot.tree.command(
    name="criar_bot",
    description="Cria um bot controlável pelo sistema de ações (administrador).",
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    nome="Nome único do bot",
    posicao="Posição obrigatória do bot",
    peso="Tipo físico obrigatório do bot",
    fis="Valor de FIS entre 0 e 100",
    vel="Valor de VEL entre 0 e 100",
    tec="Valor de TEC entre 0 e 100",
    chu="Valor de CHU entre 0 e 100",
    pas="Valor de PAS entre 0 e 100",
    defesa="Valor de DEF entre 0 e 100",
    vis="Valor de VIS entre 0 e 100",
    res="Valor de RES entre 0 e 100",
    est="Valor de EST entre 0 e 100",
)
@app_commands.choices(
    posicao=[
        app_commands.Choice(name="Zagueiro", value="Zagueiro"),
        app_commands.Choice(name="Lateral", value="Lateral"),
        app_commands.Choice(name="Volante", value="Volante"),
        app_commands.Choice(name="Meia", value="Meia"),
        app_commands.Choice(name="Ponta", value="Ponta"),
        app_commands.Choice(name="Atacante", value="Atacante"),
    ],
    peso=[
        app_commands.Choice(name="Ectomorfo Magro / Seco", value="ectomorfo"),
        app_commands.Choice(name="Atlético Leve / Fibrado", value="atletico"),
        app_commands.Choice(name="Equilibrado / Porte Padrão", value="equilibrado"),
        app_commands.Choice(name="Mesomorfo Forte / Denso", value="mesomorfo"),
        app_commands.Choice(name="Tanque / Pesado", value="tanque"),
    ],
)
async def criar_bot(
    interaction: discord.Interaction,
    nome: str,
    posicao: app_commands.Choice[str],
    peso: app_commands.Choice[str],
    fis: int,
    vel: int,
    tec: int,
    chu: int,
    pas: int,
    defesa: int,
    vis: int,
    res: int,
    est: int,
) -> None:
    nome_limpo = nome.strip()
    if not nome_limpo:
        await interaction.response.send_message(
            "O nome do bot não pode ficar vazio.",
            ephemeral=True,
        )
        return

    chave_nome = unicodedata.normalize("NFKD", nome_limpo.lower())
    chave_nome = "".join(
        caractere
        for caractere in chave_nome
        if not unicodedata.combining(caractere)
    )
    chave_nome = re.sub(r"[^a-z0-9]+", "_", chave_nome).strip("_")
    chave = f"bot:{chave_nome}"
    valores_atributos = {
        "fisico": fis,
        "velocidade": vel,
        "tecnica": tec,
        "chute": chu,
        "passe": pas,
        "defesa": defesa,
        "visao": vis,
        "resistencia": res,
        "estamina": est,
    }
    atributos_invalidos = [
        abreviacao
        for abreviacao, valor in zip(
            ("FIS", "VEL", "TEC", "CHU", "PAS", "DEF", "VIS", "RES", "EST"),
            valores_atributos.values(),
        )
        if not 0 <= valor <= VALOR_MAXIMO_ATRIBUTO
    ]
    if atributos_invalidos:
        await interaction.response.send_message(
            "Os atributos "
            f"{', '.join(atributos_invalidos)} devem estar entre 0 e "
            f"{VALOR_MAXIMO_ATRIBUTO}.",
            ephemeral=True,
        )
        return

    jogadores = carregar_jogadores()
    if chave in jogadores:
        await interaction.response.send_message(
            "Já existe um bot com esse nome. Use outro nome.",
            ephemeral=True,
        )
        return

    bot_jogador: dict[str, Any] = {
        "tipo": "bot",
        "nome": nome_limpo,
        "posicao": posicao.value,
        "peso": peso.value,
        "numero": 0,
        "pe": "Não definido",
        "altura": "Não definida",
        "peso": "Não definido",
        "nacionalidade": "Bot",
        "imagem": None,
        "banner": None,
    }
    bot_jogador.update(valores_atributos)
    preparar_jogador(bot_jogador, nome_limpo)
    jogadores[chave] = bot_jogador
    salvar_jogadores(jogadores)

    await interaction.response.send_message(
        view=criar_layout_view(
            criar_atributos_embed(bot_jogador),
            content=f"Bot **{nome_limpo}** criado com sucesso.",
        ),
        ephemeral=True,
    )


@bot.tree.command(
    name="alterar_atributo",
    description="Altera um atributo de um jogador (administrador).",
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    jogador="Jogador que terá o atributo alterado",
    atributo="Atributo que será alterado",
    valor="Novo valor entre 0 e 100",
)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name=nome, value=campo)
        for _, nome, campo, _ in ATRIBUTOS
    ]
)
async def alterar_atributo(
    interaction: discord.Interaction,
    jogador: discord.User,
    atributo: app_commands.Choice[str],
    valor: int,
) -> None:
    if not 0 <= valor <= VALOR_MAXIMO_ATRIBUTO:
        await interaction.response.send_message(
            "O valor do atributo deve estar entre 0 e 100.",
            ephemeral=True,
        )
        return

    jogadores = carregar_jogadores()
    dados = jogadores.setdefault(str(jogador.id), {"nome": jogador.display_name})
    preparar_jogador(dados, jogador.display_name)
    dados[atributo.value] = valor
    salvar_jogadores(jogadores)
    await interaction.response.send_message(
        f"O atributo **{atributo.name}** de {jogador.mention} "
        f"foi alterado para **{valor}**.",
        ephemeral=True,
    )


@bot.tree.command(
    name="alterar_xp",
    description="Adiciona XP a um jogador (administrador).",
)
@app_commands.checks.has_permissions(administrator=True)
async def alterar_xp(
    interaction: discord.Interaction,
    jogador: discord.User,
    quantidade: int,
) -> None:
    if quantidade < 0:
        await interaction.response.send_message(
            "A quantidade de XP não pode ser negativa.",
            ephemeral=True,
        )
        return

    jogadores = carregar_jogadores()
    chave = str(jogador.id)
    dados = jogadores.setdefault(chave, {"nome": jogador.display_name})
    preparar_jogador(dados, jogador.display_name)
    nivel_anterior = int(dados["nivel"])
    dados["xp"] += quantidade
    preparar_jogador(dados, jogador.display_name)
    salvar_jogadores(jogadores)

    mensagem_nivel = (
        f" O jogador subiu para o nível **{dados['nivel']}**."
        if int(dados["nivel"]) > nivel_anterior
        else f" Nível atual: **{dados['nivel']}**."
    )
    await interaction.response.send_message(
        f"**{quantidade} XP** adicionados a {jogador.mention}.{mensagem_nivel}",
        ephemeral=True,
    )


@bot.tree.command(name="ranking", description="Mostra a tabela dos maiores níveis.")
async def ranking(interaction: discord.Interaction) -> None:
    jogadores = carregar_jogadores()
    ranking_atual: list[tuple[str, dict[str, Any]]] = []
    mudou = False
    for chave, jogador in jogadores.items():
        mudou = preparar_jogador(jogador, str(jogador.get("nome", chave))) or mudou
        ranking_atual.append((chave, jogador))

    if mudou:
        salvar_jogadores(jogadores)
    ranking_atual.sort(
        key=lambda item: (int(item[1]["nivel"]), int(item[1]["xp"])),
        reverse=True,
    )
    await interaction.response.send_message(embed=criar_ranking_embed(ranking_atual))


if __name__ == "__main__":
    token = TOKEN or os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "Defina TOKEN no código ou a variável de ambiente DISCORD_TOKEN antes de iniciar o bot."
        )
    bot.run(token)
