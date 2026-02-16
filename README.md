# 🎙️ MeEscutaMeTranscreve Bot

Bot pessoal de transcrição de áudio para Telegram usando OpenAI Whisper API.

Recebe áudios em qualquer formato, detecta automaticamente o idioma e retorna a transcrição com **máxima precisão** (temperatura 0, sem alucinações).

---

## ✨ Features

| Feature | Descrição |
|---------|-----------|
| 🎯 **Máxima Precisão** | `temperature=0`, sem prompts indutivos |
| 🌍 **Multi-idioma** | Auto-detect de 50+ idiomas (foco: PT-BR, EN, ES) |
| 🔒 **Acesso protegido** | Autenticação por senha (uso pessoal) |
| 🎵 **Multi-formato** | MP3, OGG, WAV, M4A, FLAC, AAC, OPUS, WebM |
| 🔄 **Conversão automática** | Converte para MP3 mono 16kHz (ideal para STT) |
| 📏 **Limite de 25MB** | Validação antes do processamento |
| ⚡ **Retry automático** | 3 tentativas com backoff exponencial |
| 📝 **Logs detalhados** | Cada etapa é logada para debugging |

---

## 🚀 Deploy em 5 Minutos (Railway)

### Pré-requisitos
- Conta no [Railway.app](https://railway.app) (plano gratuito: 500h/mês)
- Token do bot Telegram (via [@BotFather](https://t.me/BotFather))
- Chave da API OpenAI (via [platform.openai.com](https://platform.openai.com/api-keys))

### Passo a Passo

1. **Fork este repositório** no GitHub

2. **Crie um projeto no Railway**:
   - Acesse [railway.app](https://railway.app)
   - New Project → Deploy from GitHub Repo
   - Selecione o repositório forkado

3. **Configure as variáveis de ambiente** (Settings → Variables):
   ```
   TELEGRAM_BOT_TOKEN=seu_token_aqui
   OPENAI_API_KEY=sua_chave_aqui
   BOT_PASSWORD=sua_senha_forte_aqui
   ```

4. **Deploy automático** acontece ao salvar. Aguarde ~2 minutos.

5. **Teste**: Abra seu bot no Telegram, envie `/start SUA_SENHA`

📖 Guia detalhado: [docs/DEPLOY.md](docs/DEPLOY.md)

---

## 💻 Desenvolvimento Local

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/brain-MeEscutaMeTranscreveBot.git
cd brain-MeEscutaMeTranscreveBot
```

### 2. Instale FFmpeg
```bash
# Windows (Chocolatey)
choco install ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg
```

### 3. Crie o ambiente virtual
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 4. Instale dependências
```bash
pip install -r requirements.txt
```

### 5. Configure as variáveis de ambiente
```bash
cp .env.example .env
# Edite o .env com seus tokens e senha
```

### 6. Execute o bot
```bash
python main.py
```

---

## 🤖 Usando o Bot

### Comandos

| Comando | Descrição |
|---------|-----------|
| `/start [senha]` | Autenticar no bot |
| `/help` | Ver instruções de uso |

### Fluxo de Uso

1. Envie `/start SUA_SENHA` para autenticar (apenas na primeira vez)
2. Envie qualquer áudio ou mensagem de voz
3. Aguarde a transcrição (~10% da duração do áudio)
4. Receba o texto com idioma detectado automaticamente

### Exemplo de Resposta

```
📝 Transcrição
─────────────────
Olá, este é um exemplo de transcrição do meu áudio.
─────────────────
🌐 Idioma: 🇧🇷 Português
⏱️ Duração: 30s
⚡ Processado em: 5s
```

---

## 📁 Estrutura do Projeto

```
├── main.py             # Entry point (inicia o bot)
├── config/
│   └── settings.py     # Variáveis de ambiente (validação)
├── bot/
│   ├── auth.py         # Autenticação por senha (hmac)
│   ├── handlers.py     # Comandos e handlers do Telegram
│   ├── transcription.py # API Whisper (precisão máxima)
│   ├── audio_processor.py # Download, conversão, validação
│   └── utils.py        # Helpers (formatação, idiomas)
├── data/               # Dados persistentes (gitignored)
├── requirements.txt    # Dependências Python
├── railway.toml        # Config de deploy Railway
└── nixpacks.toml       # Pacotes do sistema (ffmpeg)
```

---

## 🔧 Arquitetura

```
Usuário → Telegram API → Bot (handlers.py)
                              ↓
                         auth.py (verifica senha)
                              ↓
                         audio_processor.py (download + conversão MP3)
                              ↓
                         transcription.py (Whisper API, temp=0)
                              ↓
                         handlers.py (formata resposta)
                              ↓
                         Telegram API → Usuário
```

### Decisões Técnicas

| Decisão | Motivo |
|---------|--------|
| `temperature=0` | Zero alucinações, máxima fidelidade |
| `language=None` | Auto-detect puro, sem viés |
| MP3 mono 16kHz | Formato ideal para speech-to-text |
| `hmac.compare_digest` | Resistente a timing attacks |
| Retry com backoff | Resiliente a erros temporários da API |
| Long polling | Não requer URL pública ou SSL |

---

## 💰 Custos

| Serviço | Custo |
|---------|-------|
| Telegram Bot API | **Grátis** |
| Railway.app | **Grátis** (500h/mês) |
| OpenAI Whisper | $0.006/minuto de áudio |

**Estimativa de uso pessoal**: ~$1-5/mês (dependendo da quantidade de áudios).

---

## 🔒 Segurança

- ✅ Chaves API em variáveis de ambiente (nunca no código)
- ✅ `.env` no `.gitignore` (nunca commitado)
- ✅ Autenticação por senha com `hmac.compare_digest`
- ✅ Arquivos temporários removidos após processamento
- ✅ Logs sem exposição de dados sensíveis

---

## ❓ Troubleshooting

| Problema | Solução |
|----------|---------|
| "Variáveis de ambiente não configuradas" | Configure TELEGRAM_BOT_TOKEN, OPENAI_API_KEY e BOT_PASSWORD no .env |
| "Erro ao processar áudio" | Verifique se FFmpeg está instalado: `ffmpeg -version` |
| "Timeout na transcrição" | Áudio muito longo. Tente um trecho menor (<10 min) |
| "Formato não suportado" | Envie em MP3, OGG, WAV, M4A, FLAC, AAC ou OPUS |
| Bot não responde | Verifique os logs no Railway Dashboard |
| "Senha incorreta" | Confira a variável BOT_PASSWORD no .env |

---

## 🛠️ Stack Tecnológica

- **Python 3.11+** — Linguagem principal
- **python-telegram-bot 21.0** — Framework para bots Telegram (async)
- **OpenAI Whisper API** — Transcrição com IA (modelo whisper-1)
- **pydub** — Manipulação e conversão de áudio
- **FFmpeg** — Backend de conversão de áudio
- **Railway.app** — Hosting serverless gratuito

---

## 📄 Licença

Projeto pessoal. Uso livre para fins educacionais.
