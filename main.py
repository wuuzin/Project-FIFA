import asyncio
import ast
import json
import math
import io
import os
import random
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.request import urlopen
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
CARGO_USO_BOTS_ID = 1550366349585424495
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
    ("⚡", "Estamina", "estamina", "EST"),
)
ATRIBUTOS_EDITAVEIS = {campo for _, _, campo, _ in ATRIBUTOS}
MODIFICADOR_RE = re.compile(r"^\s*([+-]?)\s*(\d+(?:[.,]\d+)?)\s*(%)?\s*$")
MODIFICADOR_STATUS_RE = re.compile(
    r"^\s*([+-]?)\s*(\d+(?:[.,]\d+)?)\s*(%)?"
    r"(?:\s+([A-Za-zÀ-ÿ]+))?\s*$"
)
# Detecta tokens como "+5", "-10%", "+25% CHU", "+10 PAS".
TOKEN_MODIFICADOR_RE = re.compile(
    r"([+-]?)\s*(\d+(?:[.,]\d+)?)(?:\s*(%))?(?:\s+([A-Za-zÀ-ÿ]+))?"
)
ABREVIACAO_PARA_ATRIBUTO = {
    abreviacao: campo for _, _, campo, abreviacao in ATRIBUTOS
}
MODIFICADORES_POSICAO = {
    "Zagueiro": {"defesa": 15, "fisico": 15, "chute": -15, "velocidade": -15},
    "Lateral": {"velocidade": 15, "passe": 15, "chute": -15, "visao": -15},
    "Volante": {"defesa": 15, "visao": 15, "chute": -15, "tecnica": -15},
    "Meia": {"passe": 15, "visao": 15, "chute": -15, "velocidade": -15},
    "Meia Central": {"passe": 15, "visao": 15, "chute": -15, "velocidade": -15},
    "Meia Direita": {"passe": 10, "velocidade": 10, "chute": -15, "defesa": -15},
    "Meia Esquerda": {"passe": 10, "velocidade": 10, "chute": -15, "defesa": -15},
    "Meia-Atacante": {"passe": 15, "chute": 15, "defesa": -15, "fisico": -15},
    "Ponta": {"velocidade": 15, "tecnica": 15, "defesa": -15, "fisico": -15},
    "Atacante": {"chute": 15, "fisico": 15, "defesa": -15, "passe": -15},
    "Segundo Atacante": {"tecnica": 15, "chute": 15, "defesa": -15, "fisico": -15},
}
MODIFICADORES_PORTE = {
    "ectomorfo": {"velocidade": 15, "fisico": -15},
    "atletico": {"fisico": -5},
    "equilibrado": {},
    "mesomorfo": {"fisico": 10, "chute": 5},
    "tanque": {"fisico": 20, "velocidade": -15},
}
MODIFICADORES_ALTURA = {
    "baixo": {"velocidade": 15, "fisico": -15},
    "medio": {},
    "alto": {"fisico": 15, "velocidade": -15},
}
MODIFICADORES_PEJOGADOR = {
    "destro": {"passe": 5, "velocidade": 5},
    "canhoto": {"chute": 7, "tecnica": 7},
    "ambidestro": {"passe": 10, "chute": 10},
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
        "bonus_condicional": {"peso": {"atletico": {"tecnica": 5}}},
        "execucao": (
            "Usa fintas de tronco para desbalancear o marcador sem mudar "
            "bruscamente de velocidade. Biotipo atlético recebe +5 em TEC."
        ),
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
        "formula": "1d20 + ((TEC - 25% + VIS) / 2)",
        "atributos": ("tecnica", "visao"),
        "formula_tipo": "primeiro_reduzido_soma_dividida",
        "percentual": 25,
        "divisor": 2,
        "execucao": "Passa a bola entre as pernas do defensor e o ultrapassa pelo outro lado.",
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
        "bonus_condicional": {"peso": {"ectomorfo": {"velocidade": 5}}},
        "execucao": (
            "Adianta a bola no espaço vazio e ganha do marcador na corrida "
            "pura. Biotipo ectomorfo recebe +5 em VEL."
        ),
        "efeito": "Permite avançar até 2 zonas no mesmo turno.",
        "falha": "A bola vai para a lateral ou para o goleiro adversário.",
    },
    "giro_de_pivo": {
        "nome": "Giro de Pivô",
        "categoria": "Dribles e Recursos Individuais",
        "custo_est": 10,
        "formula": "1d20 + ((FIS + TEC) / 2)",
        "atributos": ("fisico", "tecnica"),
        "bonus_condicional": {"peso": {"tanque": {"fisico": 5}}},
        "execucao": (
            "Protege a bola com as costas voltadas para o zagueiro e gira "
            "usando o corpo como alavanca. Biotipo Tanque recebe +5 em FIS."
        ),
        "efeito": "Mantém a posse, supera o marcador e causa -10 EST ao defensor.",
        "falha": "O atacante é desarmado e cai no gramado.",
    },
    "dominio_orientado": {
        "nome": "Domínio Orientado",
        "categoria": "Domínio e Recepção Orientada",
        "custo_est": 5,
        "formula": "1d20 ((TEC + VEL) / 2)",
        "atributos": ("tecnica", "velocidade"),
        "execucao": (
            "Controla o passe já projetando a bola e o corpo na direção da "
            "corrida."
        ),
        "efeito": "Concede +2 em VEL para a ação subsequente no mesmo turno.",
        "falha": "A bola escapa 1 zona à frente e vira bola dividida.",
    },
    "corta_luz": {
        "nome": "Corta-Luz",
        "categoria": "Domínio e Recepção Orientada",
        "custo_est": 10,
        "formula": "1d20 ((VIS + TEC) / 2)",
        "atributos": ("visao", "tecnica"),
        "execucao": (
            "Ameaça dominar o passe, mas deixa a bola passar entre as pernas "
            "para um companheiro livre atrás."
        ),
        "efeito": "Defensores na zona sofrem -2 em VIS no turno atual.",
        "falha": "A zaga intercepta a bola sem rolar dados.",
    },
    "firula": {
        "nome": "Firula",
        "categoria": "Dribles e Recursos Individuais",
        "custo_est": 15,
        "formula": "1d20 + TEC",
        "atributos": ("tecnica",),
        "formula_tipo": "soma_dividida",
        "divisor": 1,
        "bonus_condicional": {"peso": {"ectomorfo": {"tecnica": 5}}},
        "execucao": (
            "Ação técnica ousada, como chapéu, calcanhar, letra, pedalada "
            "rápida ou elástico, usada para desestabilizar a marcação ou "
            "encobrir o marcador. Biotipo ectomorfo recebe +5 em TEC."
        ),
        "efeito": "Desestabiliza a marcação e supera o defensor na zona.",
        "falha": "O defensor lê o recurso e recupera a posse.",
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
        "execucao": "Arremate de precisão buscando os ângulos do goleiro. Biotipo equilibrado recebe +5 em CHU.",
        "bonus_condicional": {"peso": {"equilibrado": {"chute": 5}}},
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
        "execucao": "Chute brutal focado na velocidade da bola. Biotipo forte recebe +5 em FIS.",
        "bonus_condicional": {"peso": {"mesomorfo": {"fisico": 5}}},
        "efeito": (
            "Se for no gol, o goleiro sofre -5 em TEC para segurar e, mesmo "
            "defendendo, deve espalmar, gerando rebote obrigatório."
        ),
        "falha": "Total menor que 10 isola a bola por cima do gol.",
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
        "execucao": "Finalização com o lado externo do pé. Biotipo atlético recebe +5 em CHU.",
        "bonus_condicional": {"peso": {"atletico": {"chute": 5}}},
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
        "bonus_condicional": {"peso": {"atletico": {"chute": 5}}},
        "execucao": "Biotipo atlético recebe +5 em CHU para esta tática.",
        "efeito": "Com o goleiro fora do gol, o teste de defesa sofre -50%.",
        "falha": "Com o goleiro na linha, o resultado do chute é cortado pela metade.",
    },
    "chute_normal": {
        "nome": "Chute Normal",
        "categoria": "Finalizações",
        "custo_est": 10,
        "formula": "1d20 + CHU",
        "atributos": ("chute",),
        "formula_tipo": "soma_dividida",
        "divisor": 1,
        "efeito": (
            "Ação básica de finalização direta em direção à meta, "
            "executada de dentro ou de fora da grande área."
        ),
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
        "bonus_condicional": {"peso": {"atletico": {"chute": 5}}},
        "efeito": "Reduz pela metade o bloqueio dos zagueiros e a reação do goleiro.",
        "falha": "Rolagens no total inferiores a 10 fazem o atacante furar ou mandar a bola para fora.",
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
        "bonus_condicional": {"altura": {"alto": {"chute": 5}}},
        "efeito": "O goleiro sofre -10 em DEF e TEC devido ao fator surpresa.",
        "falha": "Total menor que 18 anula a jogada por falta técnica.",
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
        "bonus_condicional": {"altura": {"alto": {"tecnica": 5}}},
        "efeito": "Garante +2 em FIS no duelo aéreo e rebote frontal se defendido.",
        "falha": "Falha contra o zagueiro causa -10 EST e -5 em VEL no próximo turno.",
    },
    "chute_cruzado": {
        "nome": "Chute Cruzado",
        "categoria": "Finalizações",
        "custo_est": 10,
        "formula": "1d20 + ((TEC + CHU - 5) / 2)",
        "atributos": ("tecnica", "chute"),
        "formula_tipo": "soma_constante_dividida",
        "constante": -5,
        "divisor": 2,
        "execucao": "Arremate em direção à trave mais distante. Anula o debuff de lado de campo para canhotos e destros.",
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
        "efeito": "Aplica -3 em DEF nos defensores e -3 em DEF no goleiro, dificultando a leitura da trajetória.",
        "bonus_condicional": {"peso": {"equilibrado": {"chute": 5}}},
        "falha": "Rolagens no total inferiores a 10 isolam a bola por cima do travessão.",
    },
    "chute_de_letra_calcanhar": {
        "nome": "Chute de Letra / Calcanhar",
        "categoria": "Finalizações",
        "custo_est": 15,
        "formula": "1d20 + ((TEC - 15% + VIS - 15% + CHU - 15%) / 3)",
        "atributos": ("tecnica", "visao", "chute"),
        "formula_tipo": "tres_reduzidos_soma_dividida",
        "percentuais": (15, 15, 15),
        "divisor": 3,
        "condicao": "Exige estar a 1 zona do gol, de costas ou em ângulo desfavorável.",
        "efeito": "Engana a leitura do goleiro e reduz pela metade a pontuação final da defesa.",
        "bonus_condicional": {"altura": {"baixo": {"chute": 5}}},
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
        "bonus_condicional": {"peso": {"atletico": {"chute": 5}}},
        "falha": "Rolagens no total inferiores a 15 fazem o atleta errar a bola e entregar a posse ao inimigo.",
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
        "bonus_condicional": {"peso": {"equilibrado": {"passe": 5}}},
        "execucao": (
            "Troca de passes simples para manter a posse na mesma zona ou zona "
            "adjacente. Biotipo equilibrado recebe +5 em PAS."
        ),
        "efeito": "Garante a posse com risco quase nulo.",
    },
    "tabela_um_dois": {
        "nome": "Tabela",
        "categoria": "Passes de Manutenção e Curto Alcance",
        "custo_est": 10,
        "formula": "1d20 + ((PAS + VEL) / 2)",
        "atributos": ("passe", "velocidade"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Toca a bola para um companheiro e arranca imediatamente para receber a devolução à frente.",
        "efeito": (
            "Se a devolução for bem-sucedida, o passador original recebe a "
            "bola 1 zona à frente com +5 em VEL no próximo turno."
        ),
    },
    "passe_de_calcanhar": {
        "nome": "Passe de Calcanhar",
        "categoria": "Passes de Manutenção e Curto Alcance",
        "custo_est": 10,
        "formula": "1d20 + ((PAS - 20% + TEC - 10%) / 2)",
        "atributos": ("passe", "tecnica"),
        "formula_tipo": "dois_reduzidos_soma_dividida",
        "percentuais": (20, 10),
        "divisor": 2,
        "bonus_condicional": {"peso": {"equilibrado": {"passe": 5}}},
        "execucao": (
            "Toque rápido sem olhar, usando o calcanhar para pegar a marcação "
            "de surpresa. Biotipo equilibrado recebe +5 em PAS."
        ),
        "efeito": "Reduz em 10% a capacidade de interceptação dos defensores na zona.",
    },
    "passe_pifado": {
        "nome": "Passe em Profundidade",
        "categoria": "Passes de Profundidade e Ruptura",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + VIS) / 2)",
        "atributos": ("passe", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "execucao": "Passe milimétrico que rasga a linha de defesa e encontra o atacante em velocidade.",
        "efeito": "O atacante recebe +5 em VEL nos duelos subsequentes.",
    },
    "lancamento_longo_de_inversao": {
        "nome": "Inversão",
        "categoria": "Passes de Profundidade e Ruptura",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + FIS - 10%) / 2)",
        "atributos": ("passe", "fisico"),
        "formula_tipo": "soma_reduzida_dividida",
        "percentual": 10,
        "divisor": 2,
        "execucao": "Bola alçada que cruza o campo de um corredor lateral para o outro.",
        "efeito": "Ignora defensores nas zonas centrais e aplica -5 em VIS na zaga adversária no próximo turno.",
    },
    "passe_de_trivela_em_profundidade": {
        "nome": "Passe de Trivela",
        "categoria": "Passes de Profundidade e Ruptura",
        "custo_est": 20,
        "formula": "1d20 + ((PAS - 25% + TEC) / 2)",
        "atributos": ("passe", "tecnica"),
        "formula_tipo": "primeiro_reduzido_soma_dividida",
        "percentual": 25,
        "divisor": 2,
        "execucao": "Passe com a parte externa do pé que faz uma curva por fora da linha dos zagueiros.",
        "efeito": (
            "Ignora completamente a primeira linha de interceptação dos "
            "volantes/zagueiros centrais. Quem receber o passe recebe +5 de CHU."
        ),
        "falha": "Total menor que 15 faz a bola pegar efeito excessivo e sair em tiro de meta.",
    },
    "cruzamento_de_linha_de_fundo": {
        "nome": "Cruzamento Lateral",
        "categoria": "Cruzamentos e Bolas Alçadas",
        "custo_est": 10,
        "formula": "1d20 + ((PAS + TEC) / 2)",
        "atributos": ("passe", "tecnica"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "bonus_condicional": {"peso": {"equilibrado": {"passe": 5}}},
        "execucao": (
            "Cobrança das zonas laterais visando a cabeça dos atacantes na "
            "Zaga/Área. Biotipo equilibrado recebe +5 em PAS."
        ),
        "efeito": "Coloca a bola na disputa aérea e dá +4 em FIS para o atacante que tentar o cabeceio.",
    },
    "cruzamento_tenso_rasante": {
        "nome": "Cruzamento Rasante",
        "categoria": "Cruzamentos e Bolas Alçadas",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + FIS) / 2)",
        "atributos": ("passe", "fisico"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "bonus_condicional": {"peso": {"atletico": {"passe": 5}}},
        "execucao": (
            "Bola cruzada à meia-altura, forte e rápida, cortando a pequena "
            "área. Biotipo atlético recebe +5 em PAS."
        ),
        "efeito": "Diminui em 5 o total do goleiro caso haja finalização.",
    },
    "cruzamento_cavado_curto": {
        "nome": "Cruzamento Curto",
        "categoria": "Cruzamentos e Bolas Alçadas",
        "custo_est": 15,
        "formula": "1d20 + ((PAS + VIS + TEC) / 3)",
        "atributos": ("passe", "visao", "tecnica"),
        "formula_tipo": "soma_dividida",
        "divisor": 3,
        "bonus_condicional": {"peso": {"atletico": {"passe": 5}}},
        "execucao": (
            "Toque suave por cima do primeiro marcador para encobrir a zaga e "
            "achar o segundo pau. Biotipo atlético recebe +5 em PAS."
        ),
        "efeito": "Concede +5 em CHU ao atacante que receber a bola.",
    },
    "bote": {
        "nome": "Bote",
        "categoria": "Botes e Desarmes Diretos",
        "custo_est": 10,
        "formula": "1d20 + DEF",
        "atributos": ("defesa",),
        "formula_tipo": "soma_dividida",
        "divisor": 1,
        "bonus_condicional": {"peso": {"tanque": {"defesa": 5}}},
        "execucao": "Lê a intenção e ataca a bola no momento exato.",
        "efeito": (
            "Rouba a bola de forma limpa e projeta para uma zona livre ou "
            "para um companheiro na mesma zona. Biotipo Tanque recebe +5 em DEF."
        ),
    },
    "carrinho": {
        "nome": "Carrinho",
        "categoria": "Botes e Desarmes Diretos",
        "custo_est": 20,
        "formula": "1d20 + ((DEF + VEL) / 2)",
        "atributos": ("defesa", "velocidade"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "bonus_condicional": {"altura": {"alto": {"defesa": 5}}},
        "execucao": "Lança-se ao gramado para cortar a bola no limite.",
        "efeito": (
            "Garante o desarme ou trava o chute/passe. Se a margem de vitória "
            "for pelo menos o dobro, a defesa mantém a posse; caso contrário, "
            "a bola sai pela lateral ou escanteio. Atletas altos recebem +5 em DEF."
        ),
        "falha": (
            "Total inferior a 10 resulta em falta; inferior a 5, cartão "
            "amarelo; falha crítica resulta em cartão vermelho."
        ),
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
        "bonus_condicional": {"peso": {"tanque": {"defesa": 5}}},
        "execucao": "Usa massa muscular e ombro para desestabilizar o atacante.",
        "efeito": (
            "O atacante perde equilíbrio e posse, que fica livre na zona, "
            "perdendo também 10 EST. Biotipo Tanque recebe +5 em DEF."
        ),
        "falha": "Total inferior a 10 resulta em falta.",
    },
    "sombra_protecao_de_bola": {
        "nome": "Proteção de Bola",
        "categoria": "Jogo de Corpo e Condução Física",
        "custo_est": 10,
        "formula": "1d20 + ((FIS + VIS) / 2)",
        "atributos": ("fisico", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 2,
        "bonus_condicional": {"peso": {"tanque": {"defesa": 5}}},
        "execucao": (
            "Coloca o corpo entre o atacante e a bola e escolta sua trajetória "
            "até a linha de fundo ou lateral sem tocá-la."
        ),
        "efeito": (
            "Garante tiro de meta ou lateral para a própria equipe, sem risco "
            "de escanteio. Biotipo Tanque recebe +5 em DEF."
        ),
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
        "efeito": (
            "Impede avanço de zona e aplica -5 em CHU e -5 em PAS para qualquer "
            "ação do atacante no turno."
        ),
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
        "efeito": (
            "Bloqueia chutes ao gol ou intercepta cruzamentos rasantes. Caso "
            "a falha seja inferior à metade, reduz a força da bola em 1d10."
        ),
    },
    "cabeceio_defensivo": {
        "nome": "Cabeceio Defensivo",
        "categoria": "Bloqueios e Jogo Aéreo",
        "custo_est": 10,
        "formula": "1d20 + ((DEF + FIS + VIS) / 3)",
        "atributos": ("defesa", "fisico", "visao"),
        "formula_tipo": "soma_dividida",
        "divisor": 3,
        "bonus_condicional": {"altura": {"alto": {"defesa": 5}}},
        "execucao": "Disputa no alto contra cruzamentos ou lançamentos longos na zona de Zaga/Área.",
        "efeito": (
            "Afasta a bola para um campo adjacente aleatório. Altura alta "
            "aumenta DEF em +5."
        ),
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
        "falha": "Com total inferior a 10, o zagueiro é expulso.",
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

for dados_acao in ACOES_INDIVIDUAIS.values():
    dados_acao["custo_est"] = (int(dados_acao["custo_est"]) + 1) // 2

ACOES_CONDUCAO = (
    "drible_de_corpo",
    "caneta_janela",
    "pique_adiantado",
    "giro_de_pivo",
    "dominio_orientado",
    "corta_luz",
    "firula",
)
ACOES_FINALIZACAO = (
    "chute_colocado",
    "bomba_de_forca",
    "chute_de_trivela",
    "cavada_cobertura",
    "chute_normal",
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


_jogadores_lock = asyncio.Lock()


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


def adicionar_xp_jogador(jogador: dict[str, Any], quantidade: int) -> int:
    """Adiciona XP uma vez e processa level-ups. Retorna o nível anterior."""
    nivel_anterior = int(jogador["nivel"])
    jogador["xp"] = int(jogador["xp"]) + quantidade
    preparar_jogador(jogador, str(jogador.get("nome", "")))
    return nivel_anterior


def normalizar_nome_busca(nome: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nome.strip().casefold())
    return "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )


def normalizar_pe(valor: Any) -> str:
    return normalizar_nome_busca(str(valor))


def pode_usar_bots(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    if interaction.user.guild_permissions.administrator:
        return True
    return any(
        cargo.id == CARGO_USO_BOTS_ID
        for cargo in getattr(interaction.user, "roles", ())
    )


def localizar_jogador_por_nome(
    jogadores: dict[str, dict[str, Any]],
    nome: str,
) -> tuple[str, dict[str, Any]] | None:
    procurado = normalizar_nome_busca(nome)
    encontrados = [
        (chave, jogador)
        for chave, jogador in jogadores.items()
        if normalizar_nome_busca(str(jogador.get("nome", ""))) == procurado
    ]
    if len(encontrados) == 1:
        return encontrados[0]
    if len(encontrados) > 1:
        raise ValueError("Há mais de um personagem com esse nome.")
    return None


async def autocompletar_bots(
    _interaction: discord.Interaction,
    valor: str,
) -> list[app_commands.Choice[str]]:
    procurado = normalizar_nome_busca(valor)
    bots = []
    for chave, jogador in carregar_jogadores().items():
        if not chave.startswith("bot:"):
            continue
        nome = str(jogador.get("nome", chave[4:]))
        if procurado in normalizar_nome_busca(nome):
            bots.append(
                app_commands.Choice(name=nome[:100], value=nome[:100])
            )
    return bots[:25]


async def autocompletar_personagens(
    _interaction: discord.Interaction,
    valor: str,
) -> list[app_commands.Choice[str]]:
    procurado = normalizar_nome_busca(valor)
    personagens: list[app_commands.Choice[str]] = []
    nomes_vistos: set[str] = set()
    for jogador in carregar_jogadores().values():
        nome = str(jogador.get("nome", "")).strip()
        if not nome:
            continue
        chave_nome = normalizar_nome_busca(nome)
        if chave_nome in nomes_vistos:
            continue
        if procurado and procurado not in chave_nome:
            continue
        nomes_vistos.add(chave_nome)
        personagens.append(
            app_commands.Choice(name=nome[:100], value=nome[:100])
        )
    personagens.sort(key=lambda escolha: escolha.name.casefold())
    return personagens[:25]


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


def formatar_modificadores(
    modificadores: list[tuple[float, bool, str | None]],
) -> str:
    """Formata modificadores para exibição, ex.: ``+25% CHU, +25% PAS``."""
    if not modificadores:
        return "0"
    mapa = {campo: abreviacao for _, _, campo, abreviacao in ATRIBUTOS}
    partes: list[str] = []
    for valor, eh_percentual, atributo in modificadores:
        texto = f"{valor:+g}"
        if eh_percentual:
            texto += "%"
        if atributo is not None:
            texto += f" {mapa.get(atributo, atributo).upper()}"
        partes.append(texto)
    return ", ".join(partes)


def interpretar_modificadores(
    valor: str | int | float | None,
) -> list[tuple[float, bool, str | None]]:
    """Lê um ou mais modificadores, ex.: ``+25% CHU, +25% PAS``."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return []
    if isinstance(valor, (int, float)):
        return [(float(valor), False, None)]

    texto = valor.strip().strip("()[]")
    ocorrencias = list(TOKEN_MODIFICADOR_RE.finditer(texto))
    if not ocorrencias:
        raise ValueError(
            "O modificador deve estar no formato +5, -5, +20%, -10%, "
            "-5% DEF, +10% CHU ou +25% CHU, +25% PAS."
        )

    sobra = TOKEN_MODIFICADOR_RE.sub(" ", texto)
    sobra = re.sub(r"[,;\s]+", "", sobra)
    if sobra:
        raise ValueError(
            "O modificador deve estar no formato +5, -5, +20%, -10%, "
            "-5% DEF, +10% CHU ou +25% CHU, +25% PAS."
        )

    modificadores: list[tuple[float, bool, str | None]] = []
    for ocorrencia in ocorrencias:
        sinal, numero, percentual, abreviacao = ocorrencia.groups()
        valor_numerico = float(numero.replace(",", "."))
        if sinal == "-":
            valor_numerico *= -1
        atributo: str | None = None
        if abreviacao is not None:
            atributo = ABREVIACAO_PARA_ATRIBUTO.get(abreviacao.upper())
            if atributo is None:
                abreviacoes = ", ".join(ABREVIACAO_PARA_ATRIBUTO)
                raise ValueError(
                    f"Status inválido ({abreviacao}). Use: {abreviacoes}."
                )
        modificadores.append((valor_numerico, percentual == "%", atributo))
    return modificadores


def interpretar_modificador(valor: str | int | float | None) -> tuple[float, bool]:
    """Converte um modificador global como '+5', '-10' ou '+20%'."""
    modificadores = interpretar_modificadores(valor)
    if not modificadores:
        return 0.0, False
    if len(modificadores) != 1 or modificadores[0][2] is not None:
        raise ValueError("O modificador deve estar no formato +5, -5, +20% ou -10%.")
    valor_numerico, eh_percentual, _ = modificadores[0]
    return valor_numerico, eh_percentual


def interpretar_modificador_status(
    valor: str | int | float | None,
) -> tuple[float, bool, str | None]:
    """Compatibilidade: devolve o primeiro modificador interpretado."""
    modificadores = interpretar_modificadores(valor)
    if not modificadores:
        return 0.0, False, None
    return modificadores[0]


def aplicar_modificadores_em_valores(
    valores: list[float],
    campos: tuple[str, ...] | list[str],
    modificadores: list[tuple[float, bool, str | None]],
    *,
    exigir_na_acao: bool = False,
) -> tuple[float, float]:
    """Aplica mods por atributo em ``valores`` e devolve (percentual global, fixo global)."""
    indices = {campo: indice for indice, campo in enumerate(campos)}
    percentual_global = 0.0
    fixo_global = 0.0
    for valor_mod, eh_percentual, atributo in modificadores:
        if atributo is None:
            if eh_percentual:
                percentual_global += valor_mod
            else:
                fixo_global += valor_mod
            continue
        if atributo not in indices:
            mapa = {campo: abr for _, _, campo, abr in ATRIBUTOS}
            rotulo = mapa.get(atributo, atributo).upper()
            if exigir_na_acao:
                raise ValueError(
                    f"O status {rotulo} não participa desta ação."
                )
            raise ValueError(f"O status {rotulo} não existe na ficha.")
        indice = indices[atributo]
        if eh_percentual:
            valores[indice] *= 1 + valor_mod / 100
        else:
            valores[indice] += valor_mod
    return percentual_global, fixo_global


def calcular_roll_personagem(
    jogador: dict[str, Any],
    equacao: str,
    modificador: str | int | float | None = None,
    variacao_dinamica: int | None = None,
) -> tuple[
    float,
    dict[str, float],
    list[tuple[str, int]],
    int,
    list[tuple[float, bool, str | None]],
    float,
    float,
]:
    """Avalia uma equação e aplica os multiplicadores ao resultado dos status."""
    if not equacao.strip() or len(equacao) > 200:
        raise ValueError("A equação deve ter entre 1 e 200 caracteres.")

    atributos = {
        abreviacao: float(jogador[campo])
        for _, _, campo, abreviacao in ATRIBUTOS
    }
    modificadores_manuais = interpretar_modificadores(modificador)
    for valor_mod, eh_percentual, atributo in modificadores_manuais:
        if atributo is None:
            continue
        if atributo not in {campo for _, _, campo, _ in ATRIBUTOS}:
            mapa = {campo: abr for _, _, campo, abr in ATRIBUTOS}
            raise ValueError(
                f"O status {mapa.get(atributo, atributo).upper()} não existe na ficha."
            )
        abreviacao = next(
            abr for _, _, campo, abr in ATRIBUTOS if campo == atributo
        )
        if eh_percentual:
            atributos[abreviacao] *= 1 + valor_mod / 100
        else:
            atributos[abreviacao] += valor_mod

    nomes = sorted(atributos, key=len, reverse=True)
    expressao = equacao.upper()
    metricas_usadas = {
        nome
        for nome in re.findall(r"\b[A-Z][A-Z0-9_]*\b", expressao)
        if nome in atributos
    }
    dados: list[tuple[str, int]] = []

    def substituir_dado(correspondencia: re.Match[str]) -> str:
        quantidade = int(correspondencia.group(1) or 1)
        lados = int(correspondencia.group(2))
        if quantidade < 1 or quantidade > 20 or lados < 2 or lados > 1000:
            raise ValueError("Dados permitidos: até 20 dados com 2 a 1000 lados.")
        resultados = [random.randint(1, lados) for _ in range(quantidade)]
        dados.extend(
            (f"{quantidade}d{lados}", resultado) for resultado in resultados
        )
        return str(sum(resultados))

    expressao = re.sub(
        r"(?<![A-Z0-9_])(\d*)D(\d+)(?![A-Z0-9_])",
        substituir_dado,
        expressao,
    )
    percentuais = re.compile(r"(?<![A-Z0-9_.])([+-]?\d+(?:[.,]\d+)?)\s*%")

    def substituir_percentual(correspondencia: re.Match[str]) -> str:
        valor_percentual = float(correspondencia.group(1).replace(",", "."))
        return str(valor_percentual / 100)

    expressao = percentuais.sub(substituir_percentual, expressao)
    identificadores = set(re.findall(r"\b[A-Z][A-Z0-9_]*\b", expressao))
    desconhecidos = identificadores - set(nomes)
    if desconhecidos:
        nomes_validos = ", ".join(nomes)
        raise ValueError(
            f"Métrica(s) inválida(s): {', '.join(sorted(desconhecidos))}. "
            f"Use: {nomes_validos}."
        )
    for nome in nomes:
        expressao = re.sub(rf"\b{nome}\b", str(atributos[nome]), expressao)

    try:
        arvore = ast.parse(expressao, mode="eval")
    except SyntaxError as erro:
        raise ValueError(
            "Equação inválida. Use números, métricas, percentuais (ex.: -10%) "
            "e + - * / ( )."
        ) from erro

    operadores = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)
    for no in ast.walk(arvore):
        if isinstance(no, ast.Expression | ast.Constant):
            continue
        if isinstance(no, ast.operator | ast.unaryop):
            if not isinstance(no, operadores):
                raise ValueError("A equação contém uma operação não permitida.")
            continue
        if isinstance(no, ast.BinOp) and isinstance(no.op, operadores):
            continue
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, operadores):
            continue
        raise ValueError("A equação contém uma operação não permitida.")

    try:
        valor = float(_avaliar_arvore_roll(arvore.body))
    except (ZeroDivisionError, ValueError, TypeError) as erro:
        raise ValueError("Não foi possível calcular essa equação.") from erro
    if not math.isfinite(valor):
        raise ValueError("O resultado da equação precisa ser finito.")
    if variacao_dinamica is None:
        variacao_dinamica = random.randint(80, 120)
    if not 80 <= variacao_dinamica <= 120:
        raise ValueError("A variação dinâmica deve estar entre 80% e 120%.")
    total_dados = sum(resultado for _, resultado in dados)
    status_base = valor - total_dados
    campos_usados = {
        campo
        for _, _, campo, abreviacao in ATRIBUTOS
        if abreviacao in metricas_usadas
    }
    modificadores, _ = modificadores_contextuais(jogador)
    percentual_contextual = sum(
        modificadores.get(campo, 0) for campo in campos_usados
    )
    percentual_manual = sum(
        valor_mod
        for valor_mod, eh_percentual, atributo in modificadores_manuais
        if atributo is None and eh_percentual
    )
    valor_fixo = sum(
        valor_mod
        for valor_mod, eh_percentual, atributo in modificadores_manuais
        if atributo is None and not eh_percentual
    )
    percentual_total = (
        percentual_contextual + percentual_manual + variacao_dinamica - 100
    )
    status_com_variacao = (
        status_base * (1 + percentual_total / 100)
        + valor_fixo
    )
    return (
        total_dados + max(0.0, status_com_variacao),
        atributos,
        dados,
        variacao_dinamica,
        modificadores_manuais,
        status_base,
        status_com_variacao,
    )


def _avaliar_arvore_roll(no: ast.AST) -> float:
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return float(no.value)
    if isinstance(no, ast.BinOp):
        esquerda = _avaliar_arvore_roll(no.left)
        direita = _avaliar_arvore_roll(no.right)
        if isinstance(no.op, ast.Add):
            return esquerda + direita
        if isinstance(no.op, ast.Sub):
            return esquerda - direita
        if isinstance(no.op, ast.Mult):
            return esquerda * direita
        if isinstance(no.op, ast.Div):
            return esquerda / direita
    if isinstance(no, ast.UnaryOp):
        valor = _avaliar_arvore_roll(no.operand)
        if isinstance(no.op, ast.USub):
            return -valor
        if isinstance(no.op, ast.UAdd):
            return valor
    raise ValueError("Nó de equação não permitido.")


def modificadores_contextuais(jogador: dict[str, Any]) -> tuple[dict[str, int], float]:
    modificadores: dict[str, int] = {}
    posicao = str(jogador.get("posicao")).casefold()
    posicoes = {
        unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().casefold(): nome
        for nome in MODIFICADORES_POSICAO
    }
    posicao = posicoes.get(
        unicodedata.normalize("NFKD", posicao).encode("ascii", "ignore").decode(),
        posicao,
    )
    for grupo in (
        MODIFICADORES_POSICAO.get(posicao, {}),
        bonus_dominancia_meia(jogador),
        MODIFICADORES_PORTE.get(str(jogador.get("peso")), {}),
        MODIFICADORES_ALTURA.get(str(jogador.get("altura")), {}),
        MODIFICADORES_PEJOGADOR.get(normalizar_pe(jogador.get("pe")), {}),
    ):
        for campo, percentual in grupo.items():
            modificadores[campo] = modificadores.get(campo, 0) + percentual

    fator_estamina = (
        1.05 if jogador.get("peso") in {"atletico", "equilibrado"} else 1.0
    )
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


def bonus_dominancia_meia(jogador: dict[str, Any]) -> dict[str, int]:
    """Retorna o bônus de 10% em PAS das meias direita/esquerda."""
    posicao = normalizar_nome_busca(str(jogador.get("posicao")))
    pe = normalizar_pe(jogador.get("pe"))
    if posicao == "meia direita" and pe in {"destro", "ambidestro"}:
        return {"passe": 10}
    if posicao == "meia esquerda" and pe in {"canhoto", "ambidestro"}:
        return {"passe": 10}
    return {}


def aplicar_bonus_condicional(
    jogador: dict[str, Any],
    dados_acao: dict[str, Any],
    atributos: tuple[str, ...],
    valores: list[float],
) -> list[float]:
    valores_ajustados = list(valores)
    for campo_condicao, opcoes in dados_acao.get(
        "bonus_condicional",
        {},
    ).items():
        valor_jogador = str(jogador.get(campo_condicao))
        for valor_esperado, bonus_por_atributo in opcoes.items():
            if valor_jogador != valor_esperado:
                continue
            for atributo, bonus in bonus_por_atributo.items():
                if atributo in atributos:
                    indice = atributos.index(atributo)
                    valores_ajustados[indice] += float(bonus)
    return valores_ajustados


def bonus_condicionais_aplicados(
    jogador: dict[str, Any],
    dados_acao: dict[str, Any],
    atributos: tuple[str, ...],
) -> dict[str, float]:
    aplicados: dict[str, float] = {}
    for campo_condicao, opcoes in dados_acao.get("bonus_condicional", {}).items():
        valor_jogador = str(jogador.get(campo_condicao)).casefold()
        for valor_esperado, bonus_por_atributo in opcoes.items():
            if valor_jogador != str(valor_esperado).casefold():
                continue
            for atributo, bonus in bonus_por_atributo.items():
                if atributo in atributos:
                    aplicados[atributo] = aplicados.get(atributo, 0) + float(bonus)
    return aplicados


def calcular_teste_acao(
    jogador: dict[str, Any],
    atributos_status: tuple[str, ...] | list[str],
    modificador: str | int | float | None = None,
    dado: int | None = None,
    status_base_calculado: float | None = None,
    variacao_dinamica: int | None = None,
    bonus_fixo: float = 0,
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
    status_ajustado = status_dinamico + bonus_fixo
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
        "bonus_fixo": bonus_fixo,
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
    modificadores_contextuais_acao, _ = modificadores_contextuais(jogador)
    bonus_condicionais = bonus_condicionais_aplicados(
        jogador,
        dados_acao,
        atributos,
    )
    valores_status = [
        float(jogador[campo])
        * (1 + modificadores_contextuais_acao.get(campo, 0) / 100)
        for campo in atributos
    ]
    modificadores_manuais = interpretar_modificadores(modificador)
    percentual_modificador, fixo_modificador = aplicar_modificadores_em_valores(
        valores_status,
        atributos,
        modificadores_manuais,
        exigir_na_acao=True,
    )
    penalidade_campo = dados_acao.get("penalidade_atributo")
    penalidade = float(dados_acao.get("penalidade_valor", 0))

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

    if variacao_dinamica is None:
        variacao_dinamica = random.randint(80, 120)
    if not 80 <= variacao_dinamica <= 120:
        raise ValueError("A variação dinâmica deve estar entre 80% e 120%.")
    percentual_total = percentual_modificador + variacao_dinamica - 100
    status_base_com_buffs = status_base * (1 + percentual_total / 100)
    bonus_fixo = sum(bonus_condicionais.values()) + fixo_modificador
    if penalidade_campo in atributos:
        bonus_fixo += penalidade
    resultado = calcular_teste_acao(
        jogador,
        atributos,
        modificador=None,
        dado=dado,
        status_base_calculado=status_base_com_buffs,
        variacao_dinamica=100,
        bonus_fixo=bonus_fixo,
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
            "modificadores_manuais": modificadores_manuais,
            "modificador_texto": formatar_modificadores(modificadores_manuais),
            "modificador_status": (
                modificadores_manuais[0][2] if len(modificadores_manuais) == 1 else None
            ),
            "modificadores_contextuais": {
                campo: percentual
                for campo, percentual in modificadores_contextuais_acao.items()
                if campo in atributos and percentual
            },
            "bonus_condicionais": bonus_condicionais,
            "status_base_formula": status_base,
            "percentual_contextual": percentual_total,
            "status_base_com_buffs": status_base_com_buffs,
            "bonus_fixo": bonus_fixo,
            "modificador": (
                modificadores_manuais[0][0] if len(modificadores_manuais) == 1 else 0.0
            ),
            "modificador_percentual": (
                modificadores_manuais[0][1] if len(modificadores_manuais) == 1 else False
            ),
            "variacao_dinamica": variacao_dinamica,
        }
    )
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


def validar_hex_cor(valor: str, campo: str = "A cor do embed") -> str:
    cor = valor.strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", cor):
        raise ValueError(
            f"{campo} deve estar no formato hexadecimal, por exemplo #5865F2."
        )
    return f"#{cor.upper()}"


def cor_hex_embed(valor: str | None) -> discord.Colour | None:
    if not valor:
        return None
    return discord.Colour(int(valor.lstrip("#"), 16))


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
    if "resistencia" in jogador:
        del jogador["resistencia"]
        mudou = True
    defaults = {
        "nome": nome,
        "posicao": "Não definida",
        "numero": 0,
        "pe": "Não definido",
        "altura": "Não definida",
        "peso": "Não definido",
        "nacionalidade": "Não definida",
        "imagem_atributos": None,
        "cor_embed": None,
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
    jogador["pe"] = {
        "destro": "Destro",
        "canhoto": "Canhoto",
        "ambidestro": "Ambidestro",
    }.get(normalizar_pe(jogador["pe"]), jogador["pe"])
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


def extrair_cor_predominante(url: str) -> tuple[int, int, int] | None:
    try:
        from PIL import Image

        with urlopen(url, timeout=5) as resposta:
            imagem = Image.open(io.BytesIO(resposta.read()))
            imagem = imagem.convert("RGB")
            imagem.thumbnail((128, 128))
            imagem_quantizada = imagem.quantize(colors=1)
            paleta = imagem_quantizada.getpalette()
            if not paleta or len(paleta) < 3:
                return None
            return tuple(paleta[:3])
    except (ImportError, OSError, ValueError):
        return None


async def obter_cor_banner(
    url: str | None,
    fallback: discord.Colour,
) -> discord.Colour:
    if not url:
        return fallback
    rgb = await asyncio.to_thread(extrair_cor_predominante, str(url))
    return discord.Colour.from_rgb(*rgb) if rgb else fallback


async def obter_cor_embed(
    jogador: dict[str, Any],
    imagem: str | None,
    fallback: discord.Colour,
) -> discord.Colour:
    cor_personalizada = cor_hex_embed(jogador.get("cor_embed"))
    if cor_personalizada is not None:
        return cor_personalizada
    return await obter_cor_banner(imagem, fallback)


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


def criar_personagem_embed(
    jogador: dict[str, Any],
    cor: discord.Colour | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        description=(
            "## ﹙🧾﹚ ATLETA\n"
            f"# {jogador['nome']}"
        ),
        color=cor or discord.Colour.dark_green(),
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


def criar_atributos_embed(
    jogador: dict[str, Any],
    cor: discord.Colour | None = None,
) -> discord.Embed:
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

    cabecalho = (
        f"**⭐ Nível:** `{jogador.get('nivel', 0)}`  •  "
        f"**🎯 Pontos disponíveis:** `{jogador.get('pontos_disponiveis', 0)}`"
    )
    embed = discord.Embed(
        title=f"Atributos de {jogador['nome']}",
        description=f"{cabecalho}\n\n" + "\n\n".join(linhas),
        colour=cor or discord.Colour.green(),
    )
    if jogador.get("imagem_atributos"):
        embed.set_image(url=str(jogador["imagem_atributos"]))
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
        cor: discord.Colour | None = None,
        editavel: bool = True,
    ) -> None:
        super().__init__(timeout=300)
        self.jogador = jogador
        self.jogadores = jogadores
        self.chave = chave
        self.dono_id = dono_id
        self.cor = cor or discord.Colour.green()
        self.editavel = editavel
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
        if delta < 0 and valor_atual + delta < VALOR_INICIAL_ATRIBUTO:
            return
        self.jogador[campo] = valor_atual + delta
        self.jogador["pontos_disponiveis"] = pontos - delta

    def reconstruir_layout(self) -> None:
        self.clear_items()
        seletor = AtributoSelect(self)
        seletor.disabled = not self.editavel
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
                not self.editavel
                or self.salvo
                or self.atributo_selecionado is None
                or pontos <= 0
                or valor_atual >= VALOR_MAXIMO_ATRIBUTO
            ),
        )
        salvar = discord.ui.Button(
            label="💾",
            style=discord.ButtonStyle.primary,
            disabled=not self.editavel or self.salvo,
        )
        aumentar.callback = self._aumentar_callback
        salvar.callback = self._salvar_callback
        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(
                (
                    "Selecione um atributo, use ➕ para adicionar pontos. "
                    "Os atributos não podem ser reduzidos abaixo de 10. "
                    "Clique em 💾 para salvar."
                    if self.editavel
                    else "Tabela de atributos em modo somente leitura."
                )
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                criar_atributos_embed(self.jogador, self.cor).description or ""
            ),
        ]
        imagem_atributos = self.jogador.get("imagem_atributos")
        if imagem_atributos:
            children.extend(
                (
                    discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                    discord.ui.MediaGallery(
                        discord.MediaGalleryItem(str(imagem_atributos))
                    ),
                )
            )
        children.extend(
            (
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(aumentar, salvar),
                discord.ui.ActionRow(seletor),
            )
        )
        self.add_item(
            discord.ui.Container(
                *children,
                accent_color=self.cor,
            )
        )

    async def atualizar_mensagem(self, interaction: discord.Interaction) -> None:
        self.reconstruir_layout()
        await interaction.response.edit_message(view=self)

    async def _aumentar_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(QuantidadeAtributoModal(self))

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
    pagina: int = 1,
) -> discord.Embed:
    inicio = (pagina - 1) * LIMITE_RANKING
    jogadores_pagina = ranking[inicio:inicio + LIMITE_RANKING]
    linhas = [
        (
            f"`{inicio + indice:02}` **{discord.utils.escape_markdown(str(jogador['nome']))}**\n"
            f"> 🏷️ {jogador.get('posicao', 'Não definida')} "
            f"• 👕 Camisa `{jogador.get('numero', 'N/A')}` "
            f"• ⭐ Nível `{jogador['nivel']}`\n"
            f"> {barra_xp(jogador)}"
        )
        for indice, (_, jogador) in enumerate(jogadores_pagina, start=1)
    ]
    embed = discord.Embed(
        title="Tabela de experiência",
        description="\n".join(linhas) if linhas else "Nenhum jogador registrado.",
        colour=discord.Colour.gold(),
    )
    total_paginas = max(1, (len(ranking) + LIMITE_RANKING - 1) // LIMITE_RANKING)
    embed.set_footer(
        text=f"Página {pagina}/{total_paginas} • {len(ranking)} jogadores registrados"
    )
    return embed


class RankingView(discord.ui.LayoutView):
    def __init__(self, ranking: list[tuple[str, dict[str, Any]]]) -> None:
        super().__init__(timeout=300)
        self.ranking = ranking
        self.pagina = 1
        self.reconstruir_layout()

    @property
    def total_paginas(self) -> int:
        return max(
            1,
            (len(self.ranking) + LIMITE_RANKING - 1) // LIMITE_RANKING,
        )

    def reconstruir_layout(self) -> None:
        self.clear_items()
        embed = criar_ranking_embed(self.ranking, self.pagina)
        anterior = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=self.pagina <= 1,
        )
        proxima = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=self.pagina >= self.total_paginas,
        )
        anterior.callback = self._pagina_anterior
        proxima.callback = self._proxima_pagina
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"# {embed.title}\n"
                    f"## Página {self.pagina}\n\n"
                    f"{embed.description or ''}"
                ),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(anterior, proxima),
                discord.ui.TextDisplay(f"*{embed.footer.text}*"),
                accent_color=discord.Colour.gold(),
            )
        )

    async def _pagina_anterior(self, interaction: discord.Interaction) -> None:
        if self.pagina > 1:
            self.pagina -= 1
        self.reconstruir_layout()
        await interaction.response.edit_message(view=self)

    async def _proxima_pagina(self, interaction: discord.Interaction) -> None:
        if self.pagina < self.total_paginas:
            self.pagina += 1
        self.reconstruir_layout()
        await interaction.response.edit_message(view=self)


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
        if not guild_id or not guild_id.isdigit():
            raise RuntimeError(
                "GUILD_ID ou DISCORD_GUILD_ID deve conter o ID numérico do servidor."
            )

        guild = discord.Object(id=int(guild_id))
        self.tree.clear_commands(guild=guild)
        self.tree.copy_global_to(guild=guild)
        try:
            await self.tree.sync(guild=guild)
            # Evita comandos duplicados no servidor (global + guild).
            if self.application_id is not None:
                await self.http.bulk_upsert_global_commands(self.application_id, [])
        except discord.Forbidden as erro:
            print(
                "Não foi possível sincronizar os comandos no servidor "
                f"{guild_id}: o bot não tem acesso a esse servidor. "
                "Confira o ID e se o bot foi convidado com os escopos "
                "bot e applications.commands."
            )
            self.tree.clear_commands(guild=guild)
            raise RuntimeError(
                "GUILD_ID aponta para um servidor sem acesso para este bot."
            ) from erro


bot = FuteBot()


@bot.event
async def on_ready() -> None:
    print(f"FuteBot conectado como {bot.user}")


def opcoes_de_acoes(
    chaves: tuple[str, ...],
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(
            name=f"{ACOES_INDIVIDUAIS[chave]['nome']} ({formatar_atributos_acao(ACOES_INDIVIDUAIS[chave]['atributos'])})",
            value=chave,
        )
        for chave in chaves
    ]


def formatar_atributos_acao(campos: tuple[str, ...] | list[str]) -> str:
    """Retorna abreviações dos status usados, ex.: ``TEC + VIS``."""
    mapa = {campo: abreviacao for _, _, campo, abreviacao in ATRIBUTOS}
    return " + ".join(mapa[campo] for campo in campos if campo in mapa)


def criar_acao_embed(resultado: dict[str, Any]) -> discord.Embed:
    fator = f"{resultado['variacao_dinamica']}%"
    texto_modificador = resultado.get("modificador_texto")
    if not texto_modificador:
        modificador = resultado["modificador"]
        sufixo_modificador = "%" if resultado["modificador_percentual"] else ""
        status_modificador = resultado.get("modificador_status")
        texto_modificador = f"{modificador:g}{sufixo_modificador}"
        if status_modificador:
            texto_modificador += f" {status_modificador.upper()}"
    modificadores = resultado.get("modificadores_contextuais", {})
    bonus_condicionais = resultado.get("bonus_condicionais", {})
    linhas_buffs = []
    for campo, percentual in modificadores.items():
        abreviacao = next(
            abreviacao
            for _, _, nome_campo, abreviacao in ATRIBUTOS
            if nome_campo == campo
        )
        linhas_buffs.append(f"`{abreviacao}` {percentual:+g}%")
    for campo, bonus in bonus_condicionais.items():
        abreviacao = next(
            abreviacao
            for _, _, nome_campo, abreviacao in ATRIBUTOS
            if nome_campo == campo
        )
        linhas_buffs.append(f"`{abreviacao}` {bonus:+g} (bônus da tática)")
    texto_buffs = ", ".join(linhas_buffs) if linhas_buffs else "Nenhum"
    atributos_usados = formatar_atributos_acao(resultado.get("atributos", []))
    texto_atributos = atributos_usados or "Nenhum"
    descricao = (
        f"## ﹙⚽﹚ {resultado['categoria']}\n"
        f"# {resultado['nome_acao']}\n\n"
        f"**Atributos usados:** `{texto_atributos}`\n"
        f"**Fórmula:** `{resultado['formula']}`\n"
        f"**Custo de EST:** `{resultado['custo_est']}`\n"
        f"\n"
        f"**D20:** `{resultado['d20']}`\n"
        f"**Status base:** `{resultado['status_base']:.2f}`\n"
        f"**Status com buffs:** `{resultado['status_base_com_buffs']:.2f}` "
        f"({resultado['percentual_contextual']:+g}%)\n"
        f"**Valores fixos:** `{resultado.get('bonus_fixo', 0):+g}`\n"
        f"**Variação dinâmica:** `{fator}`\n"
        f"**Modificador:** `{texto_modificador}`\n"
        f"**Buffs aplicados:** {texto_buffs}\n"
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
        if not pode_usar_bots(interaction):
            await interaction.response.send_message(
                "Somente administradores ou membros com o cargo autorizado podem usar bots nas ações.",
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
    modificador="Opcional: +5, +20%, +10% CHU ou +25% CHU, +25% PAS",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível para administradores ou cargo autorizado",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_CONDUCAO))
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
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
    modificador="Opcional: +5, +20%, +10% CHU ou +25% CHU, +25% PAS",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível para administradores ou cargo autorizado",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_FINALIZACAO))
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
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
    modificador="Opcional: +5, +20%, +10% CHU ou +25% CHU, +25% PAS",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível para administradores ou cargo autorizado",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_PASSE))
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
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
    modificador="Opcional: +5, +20%, +10% CHU ou +25% CHU, +25% PAS",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível para administradores ou cargo autorizado",
)
@app_commands.choices(acao=opcoes_de_acoes(ACOES_DEFESA))
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
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
    cor_embed="Cor opcional do embed em hexadecimal, por exemplo #5865F2",
)
@app_commands.choices(
    posicao=[
        app_commands.Choice(name="Goleiro", value="Goleiro"),
        app_commands.Choice(name="Zagueiro", value="Zagueiro"),
        app_commands.Choice(name="Lateral", value="Lateral"),
        app_commands.Choice(name="Volante", value="Volante"),
        app_commands.Choice(name="Meia Central", value="Meia Central"),
        app_commands.Choice(name="Meia Direita", value="Meia Direita"),
        app_commands.Choice(name="Meia Esquerda", value="Meia Esquerda"),
        app_commands.Choice(name="Meia-Atacante", value="Meia-Atacante"),
        app_commands.Choice(name="Ponta", value="Ponta"),
        app_commands.Choice(name="Atacante", value="Atacante"),
        app_commands.Choice(name="Segundo Atacante", value="Segundo Atacante"),
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
    cor_embed: str | None = None,
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
        cor_embed = (
            validar_hex_cor(cor_embed)
            if cor_embed is not None
            else None
        )
    except ValueError as erro:
        await interaction.response.send_message(str(erro), ephemeral=True)
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
        "cor_embed": cor_embed,
    }
    preparar_jogador(jogador, nome.strip())
    jogadores[chave] = jogador
    salvar_jogadores(jogadores)
    cor_banner = await obter_cor_embed(
        jogador,
        jogador.get("banner"),
        discord.Colour.dark_green(),
    )

    await interaction.response.send_message(
        view=criar_layout_view(
            criar_personagem_embed(jogador, cor_banner),
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
    cor_embed="Nova cor opcional do embed em hexadecimal, por exemplo #5865F2",
    imagem_arquivo="Novo arquivo da imagem do atleta",
    banner_arquivo="Novo arquivo do banner da ficha",
    imagem_atributos_arquivo="Novo arquivo da imagem dos atributos",
    bot_alvo="Nome do bot criado; disponível somente para administradores",
)
@app_commands.choices(
    posicao=[
        app_commands.Choice(name="Goleiro", value="Goleiro"),
        app_commands.Choice(name="Zagueiro", value="Zagueiro"),
        app_commands.Choice(name="Lateral", value="Lateral"),
        app_commands.Choice(name="Volante", value="Volante"),
        app_commands.Choice(name="Meia Central", value="Meia Central"),
        app_commands.Choice(name="Meia Direita", value="Meia Direita"),
        app_commands.Choice(name="Meia Esquerda", value="Meia Esquerda"),
        app_commands.Choice(name="Meia-Atacante", value="Meia-Atacante"),
        app_commands.Choice(name="Ponta", value="Ponta"),
        app_commands.Choice(name="Atacante", value="Atacante"),
        app_commands.Choice(name="Segundo Atacante", value="Segundo Atacante"),
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
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
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
    cor_embed: str | None = None,
    imagem_arquivo: discord.Attachment | None = None,
    banner_arquivo: discord.Attachment | None = None,
    imagem_atributos_arquivo: discord.Attachment | None = None,
    bot_alvo: str | None = None,
) -> None:
    await interaction.response.defer()
    jogadores = carregar_jogadores()
    chave_jogador = str(interaction.user.id)
    if bot_alvo is not None:
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                "Somente administradores podem editar bots.",
                ephemeral=True,
            )
            return
        encontrado = localizar_jogador_por_nome(jogadores, bot_alvo)
        if encontrado is None or not encontrado[0].startswith("bot:"):
            await interaction.followup.send(
                "Bot não encontrado. Selecione um bot criado na lista.",
                ephemeral=True,
            )
            return
        chave_jogador, jogador = encontrado
    else:
        jogador = jogadores.get(chave_jogador)
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
        nova_cor_embed = (
            validar_hex_cor(cor_embed)
            if cor_embed is not None
            else None
        )
    except ValueError as erro:
        await interaction.followup.send(str(erro), ephemeral=True)
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
        "cor_embed": nova_cor_embed,
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

    nome_anterior = str(jogador["nome"])
    jogador.update(alteracoes)
    preparar_jogador(jogador, str(jogador["nome"]))
    if chave_jogador.startswith("bot:") and nome != nome_anterior:
        novo_nome = normalizar_nome_busca(str(jogador["nome"]))
        nova_chave = f"bot:{re.sub(r'[^a-z0-9]+', '_', novo_nome).strip('_')}"
        if nova_chave != chave_jogador and nova_chave in jogadores:
            await interaction.followup.send(
                "Já existe outro bot com esse nome.",
                ephemeral=True,
            )
            return
        jogadores.pop(chave_jogador)
        jogadores[nova_chave] = jogador
    salvar_jogadores(jogadores)
    cor_banner = await obter_cor_embed(
        jogador,
        jogador.get("banner"),
        discord.Colour.dark_green(),
    )
    await interaction.followup.send(
        view=criar_layout_view(
            criar_personagem_embed(jogador, cor_banner),
            content=(
                "Bot atualizado com sucesso!"
                if chave_jogador.startswith("bot:")
                else "Ficha atualizada com sucesso!"
            ),
        ),
    )


@bot.tree.command(name="personagem", description="Mostra a ficha de um atleta.")
@app_commands.describe(
    usuario="Usuário cuja ficha será exibida",
    personagem_nome="Nome do personagem cuja ficha será exibida",
)
@app_commands.autocomplete(personagem_nome=autocompletar_personagens)
async def personagem(
    interaction: discord.Interaction,
    usuario: discord.User | None = None,
    personagem_nome: str | None = None,
) -> None:
    if usuario is not None and personagem_nome:
        await interaction.response.send_message(
            "Informe usuário ou nome do personagem, não os dois.",
            ephemeral=True,
        )
        return
    jogadores = carregar_jogadores()
    alvo = usuario or interaction.user
    chave = str(alvo.id)
    if personagem_nome:
        try:
            encontrado = localizar_jogador_por_nome(jogadores, personagem_nome)
        except ValueError as erro:
            await interaction.response.send_message(str(erro), ephemeral=True)
            return
        if encontrado is None:
            await interaction.response.send_message(
                "Nenhum personagem foi encontrado com esse nome.",
                ephemeral=True,
            )
            return
        chave, jogador = encontrado
        nome_atualizacao = str(jogador.get("nome", personagem_nome))
    else:
        jogador = jogadores.get(chave)
        nome_atualizacao = alvo.display_name
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

    if preparar_jogador(jogador, nome_atualizacao):
        salvar_jogadores(jogadores)
    cor_banner = await obter_cor_embed(
        jogador,
        jogador.get("banner"),
        discord.Colour.dark_green(),
    )
    await interaction.response.send_message(
        view=criar_layout_view(criar_personagem_embed(jogador, cor_banner))
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


@bot.tree.command(
    name="roll",
    description="Rola uma equação usando os atributos da sua ficha.",
)
@app_commands.describe(
    equacao="Ex.: 1d20 + ((FIS - 10% + VEL) / 2)",
    modificador="Opcional: +5, +20%, +10% CHU ou +25% CHU, +25% PAS",
    variacao_dinamica="Variação manual entre 80 e 120; vazio usa sorteio",
    bot_alvo="Nome do bot criado; disponível para administradores ou cargo autorizado",
)
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
async def roll(
    interaction: discord.Interaction,
    equacao: str,
    modificador: str | None = None,
    variacao_dinamica: int | None = None,
    bot_alvo: str | None = None,
) -> None:
    jogadores = carregar_jogadores()
    chave_jogador = str(interaction.user.id)
    nome_exibicao = interaction.user.display_name
    if bot_alvo:
        if not pode_usar_bots(interaction):
            await interaction.response.send_message(
                "Somente administradores ou membros com o cargo autorizado podem usar bots no `/roll`.",
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
                else "Você ainda não possui uma ficha. Use `/criar` primeiro."
            ),
            ephemeral=True,
        )
        return

    preparar_jogador(jogador, nome_exibicao)
    try:
        (
            resultado,
            _,
            dados,
            variacao_dinamica,
            modificadores_manuais,
            status_base,
            status_com_buffs,
        ) = calcular_roll_personagem(
            jogador,
            equacao,
            modificador,
            variacao_dinamica,
        )
    except ValueError as erro:
        await interaction.response.send_message(str(erro), ephemeral=True)
        return

    expressao_roll = equacao.upper()
    metricas_usadas = {
        nome
        for nome in re.findall(r"\b[A-Z][A-Z0-9_]*\b", expressao_roll)
        if nome in {abreviacao for _, _, _, abreviacao in ATRIBUTOS}
    }
    modificadores, _ = modificadores_contextuais(jogador)
    campos_usados = {
        campo
        for _, _, campo, abreviacao in ATRIBUTOS
        if abreviacao in metricas_usadas
    }
    percentual_contextual = sum(
        modificadores.get(campo, 0) for campo in campos_usados
    )
    percentual_manual = sum(
        valor_mod
        for valor_mod, eh_percentual, atributo in modificadores_manuais
        if atributo is None and eh_percentual
    )
    percentual_total = (
        percentual_contextual
        + percentual_manual
        + variacao_dinamica
        - 100
    )
    texto_modificador = formatar_modificadores(modificadores_manuais)
    linhas_buffs = []
    for campo, percentual in modificadores.items():
        if campo not in campos_usados or not percentual:
            continue
        abreviacao = next(
            abreviacao
            for _, _, nome_campo, abreviacao in ATRIBUTOS
            if nome_campo == campo
        )
        linhas_buffs.append(f"`{abreviacao}` {percentual:+g}%")
    texto_buffs = ", ".join(linhas_buffs) if linhas_buffs else "Nenhum"
    texto_d20 = (
        ", ".join(f"`{nome}` = `{valor}`" for nome, valor in dados)
        if dados
        else "Nenhum"
    )
    embed = discord.Embed(
        title=f"Roll de {jogador['nome']}",
        description=(
            f"**Fórmula:** `{equacao}`\n"
            f"\n"
            f"**D20:** {texto_d20}\n"
            f"**Status base:** `{status_base:.2f}`\n"
            f"**Status com buffs:** `{status_com_buffs:.2f}` "
            f"({percentual_total:+g}%)\n"
            f"**Variação dinâmica:** `{variacao_dinamica}%`\n"
            f"**Modificador:** `{texto_modificador}`\n"
            f"**Buffs aplicados:** {texto_buffs}\n"
            f"\n"
            f"## Total: `{round(resultado)}`"
        ),
        colour=discord.Colour.orange(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="atributos", description="Mostra a tabela de atributos de um atleta.")
@app_commands.describe(
    usuario="Usuário cujos atributos serão exibidos",
    personagem_nome="Nome do personagem cujos atributos serão exibidos",
)
@app_commands.autocomplete(personagem_nome=autocompletar_personagens)
async def atributos(
    interaction: discord.Interaction,
    usuario: discord.User | None = None,
    personagem_nome: str | None = None,
) -> None:
    if usuario is not None and personagem_nome:
        await interaction.response.send_message(
            "Informe usuário ou nome do personagem, não os dois.",
            ephemeral=True,
        )
        return
    jogadores = carregar_jogadores()
    alvo = usuario or interaction.user
    chave = str(alvo.id)
    if personagem_nome:
        try:
            encontrado = localizar_jogador_por_nome(jogadores, personagem_nome)
        except ValueError as erro:
            await interaction.response.send_message(str(erro), ephemeral=True)
            return
        if encontrado is None:
            await interaction.response.send_message(
                "Nenhum personagem foi encontrado com esse nome.",
                ephemeral=True,
            )
            return
        chave, jogador = encontrado
        nome_atualizacao = str(jogador.get("nome", personagem_nome))
    else:
        jogador = jogadores.get(chave)
        nome_atualizacao = alvo.display_name
    if jogador is None:
        jogador = {"nome": interaction.user.display_name}
        if usuario is not None:
            await interaction.response.send_message(
                f"{alvo.mention} ainda não possui uma ficha.",
                ephemeral=True,
            )
            return
        jogadores[chave] = jogador
        preparar_jogador(jogador, nome_atualizacao)
        salvar_jogadores(jogadores)
    elif preparar_jogador(jogador, nome_atualizacao):
        salvar_jogadores(jogadores)

    cor_banner = await obter_cor_embed(
        jogador,
        jogador.get("imagem_atributos"),
        discord.Colour.green(),
    )
    await interaction.response.send_message(
        view=TabelaAtributosView(
            jogador,
            jogadores,
            chave,
            interaction.user.id,
            cor_banner,
            editavel=usuario is None and personagem_nome is None,
        ),
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
    pe="Pé dominante do bot",
    peso="Tipo físico obrigatório do bot",
    altura="Faixa de estatura do bot",
    nacionalidade="Nacionalidade do bot",
    fis="Valor de FIS entre 0 e 100",
    vel="Valor de VEL entre 0 e 100",
    tec="Valor de TEC entre 0 e 100",
    chu="Valor de CHU entre 0 e 100",
    pas="Valor de PAS entre 0 e 100",
    defesa="Valor de DEF entre 0 e 100",
    vis="Valor de VIS entre 0 e 100",
    est="Valor de EST entre 0 e 100",
)
@app_commands.choices(
    posicao=[
        app_commands.Choice(name="Zagueiro", value="Zagueiro"),
        app_commands.Choice(name="Lateral", value="Lateral"),
        app_commands.Choice(name="Volante", value="Volante"),
        app_commands.Choice(name="Meia Central", value="Meia Central"),
        app_commands.Choice(name="Meia Direita", value="Meia Direita"),
        app_commands.Choice(name="Meia Esquerda", value="Meia Esquerda"),
        app_commands.Choice(name="Meia-Atacante", value="Meia-Atacante"),
        app_commands.Choice(name="Ponta", value="Ponta"),
        app_commands.Choice(name="Atacante", value="Atacante"),
        app_commands.Choice(name="Segundo Atacante", value="Segundo Atacante"),
    ],
    pe=[
        app_commands.Choice(name="Destro", value="Destro"),
        app_commands.Choice(name="Canhoto", value="Canhoto"),
        app_commands.Choice(name="Ambidestro", value="Ambidestro"),
    ],
    peso=[
        app_commands.Choice(name="Ectomorfo Magro / Seco", value="ectomorfo"),
        app_commands.Choice(name="Atlético Leve / Fibrado", value="atletico"),
        app_commands.Choice(name="Equilibrado / Porte Padrão", value="equilibrado"),
        app_commands.Choice(name="Mesomorfo Forte / Denso", value="mesomorfo"),
        app_commands.Choice(name="Tanque / Pesado", value="tanque"),
    ],
    altura=[
        app_commands.Choice(name="Baixo (1,65 m a 1,73 m)", value="baixo"),
        app_commands.Choice(name="Estatura Média (1,74 m a 1,85 m)", value="medio"),
        app_commands.Choice(name="Alto (1,86 m a 2,00 m)", value="alto"),
    ],
)
async def criar_bot(
    interaction: discord.Interaction,
    nome: str,
    posicao: app_commands.Choice[str],
    pe: app_commands.Choice[str],
    peso: app_commands.Choice[str],
    altura: app_commands.Choice[str],
    nacionalidade: str,
    fis: int,
    vel: int,
    tec: int,
    chu: int,
    pas: int,
    defesa: int,
    vis: int,
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
        "estamina": est,
    }
    atributos_invalidos = [
        abreviacao
        for abreviacao, valor in zip(
            ("FIS", "VEL", "TEC", "CHU", "PAS", "DEF", "VIS", "EST"),
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
        "pe": pe.value,
        "peso": peso.value,
        "altura": altura.value,
        "numero": 0,
        "nacionalidade": nacionalidade.strip() or "Bot",
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
    bot_alvo="Nome do bot criado",
)
@app_commands.choices(
    atributo=[
        app_commands.Choice(name=nome, value=campo)
        for _, nome, campo, _ in ATRIBUTOS
    ]
)
@app_commands.autocomplete(bot_alvo=autocompletar_bots)
async def alterar_atributo(
    interaction: discord.Interaction,
    atributo: app_commands.Choice[str],
    valor: int,
    jogador: discord.User | None = None,
    bot_alvo: str | None = None,
) -> None:
    if not 0 <= valor <= VALOR_MAXIMO_ATRIBUTO:
        await interaction.response.send_message(
            "O valor do atributo deve estar entre 0 e 100.",
            ephemeral=True,
        )
        return

    if jogador is not None and bot_alvo is not None:
        await interaction.response.send_message(
            "Informe um jogador ou um bot, não os dois.",
            ephemeral=True,
        )
        return
    if jogador is None and bot_alvo is None:
        await interaction.response.send_message(
            "Informe o jogador ou o nome do bot.",
            ephemeral=True,
        )
        return

    jogadores = carregar_jogadores()
    if bot_alvo is not None:
        encontrado = localizar_jogador_por_nome(jogadores, bot_alvo)
        if encontrado is None or not encontrado[0].startswith("bot:"):
            await interaction.response.send_message(
                "Bot não encontrado. Selecione um bot criado na lista.",
                ephemeral=True,
            )
            return
        chave, dados = encontrado
        nome_alvo = str(dados.get("nome", bot_alvo))
    else:
        assert jogador is not None
        chave = str(jogador.id)
        dados = jogadores.setdefault(chave, {"nome": jogador.display_name})
        nome_alvo = jogador.display_name
    preparar_jogador(dados, nome_alvo)
    dados[atributo.value] = valor
    salvar_jogadores(jogadores)
    alvo = (
        f"o bot **{nome_alvo}**"
        if bot_alvo is not None
        else f"{jogador.mention if jogador is not None else nome_alvo}"
    )
    await interaction.response.send_message(
        f"O atributo **{atributo.name}** de {alvo} "
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

    # Confirma a interação antes de gravar. Se outra instância do bot já
    # respondeu (comando processado em duplicata), aborta sem alterar o XP.
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.InteractionResponded:
        return
    except discord.HTTPException as erro:
        # 40060 = Unknown interaction / already acknowledged
        if erro.code in {10062, 40060}:
            return
        raise

    async with _jogadores_lock:
        jogadores = carregar_jogadores()
        chave = str(jogador.id)
        dados = jogadores.setdefault(chave, {"nome": jogador.display_name})
        preparar_jogador(dados, jogador.display_name)
        nivel_anterior = adicionar_xp_jogador(dados, quantidade)
        salvar_jogadores(jogadores)

    mensagem_nivel = (
        f" O jogador subiu para o nível **{dados['nivel']}**."
        if int(dados["nivel"]) > nivel_anterior
        else f" Nível atual: **{dados['nivel']}**."
    )
    await interaction.followup.send(
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
    await interaction.response.send_message(
        view=RankingView(ranking_atual)
    )


if __name__ == "__main__":
    token = TOKEN or os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "Defina TOKEN no código ou a variável de ambiente DISCORD_TOKEN antes de iniciar o bot."
        )
    bot.run(token)
