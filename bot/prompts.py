"""
bot/prompts.py - Prompts para processamento de texto com GPT.

Contém os templates de prompt para os diferentes formatos de saída:
- Resumo Executivo (BLUF)
- Ata Profissional
- Transcrição Corrigida
"""

PROMPTS = {
    "summary": """TAREFA: Extraia os pontos principais desta transcrição em formato executivo.
FORMATO OBRIGATÓRIO:
DECISÕES TOMADAS:

[Lista numerada de decisões concretas]

PONTOS PRINCIPAIS:

[6-8 bullet points máximo]
[Foco em informação acionável]

PRÓXIMOS PASSOS:

[Lista de ações identificadas]

REGRAS:

Máximo 250 palavras
Um ponto = uma linha
Zero interpretação ou opinião
Se não houver decisões/ações, omita a seção
Mantenha termos técnicos no idioma original

IDIOMA: Mesmo da transcrição
TRANSCRIÇÃO:
{transcription_text}""",

    "minutes": """TAREFA: Estruture esta transcrição como ata corporativa.
FORMATO OBRIGATÓRIO:
ATA - [INFERIR TIPO: Reunião/Apresentação/Discussão]
Data: [Inferir ou "Não especificada"]

PARTICIPANTES
[Listar se identificados | "Não identificados"]

ASSUNTOS TRATADOS

Assunto 1
Assunto 2

DISCUSSÕES
[Por tema, em parágrafos curtos - máx 3 linhas cada]

DELIBERAÇÕES

[Decisões numeradas]

RESPONSABILIDADES ATRIBUÍDAS

Ação: [descrição] | Responsável: [nome ou "A definir"] | Prazo: [se mencionado]

ENCAMINHAMENTOS

[Próximos passos]

REGRAS:

Linguagem formal, objetiva
Omita seções vazias
Máximo 400 palavras
Identifique speakers como P1, P2 se não nomeados
Zero especulação

IDIOMA: Mesmo da transcrição
TRANSCRIÇÃO:
{transcription_text}""",

    "corrected": """TAREFA: Corrija SOMENTE pontuação, ortografia e formatação. Zero alteração de conteúdo.
PERMITIDO:
✓ Adicionar vírgulas, pontos, interrogações
✓ Corrigir ortografia
✓ Capitalização (maiúsculas/minúsculas)
✓ Separar em parágrafos (máx 4-5 linhas cada)
✓ Usar travessão (—) para mudança de speaker
PROIBIDO:
✗ Remover, adicionar ou reordenar palavras
✗ Resumir ou sintetizar
✗ Corrigir gírias ou erros factuais
✗ Alterar ordem de frases
✗ Remover hesitações ("ãh", "né", "tipo")
FORMATO:

Parágrafos separados por linha em branco
Máximo 5 linhas por parágrafo
Aspas para citações diretas

RETORNE: Apenas o texto corrigido. Zero comentários.
TRANSCRIÇÃO ORIGINAL:
{transcription_text}"""
}
