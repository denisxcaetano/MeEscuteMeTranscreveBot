# 🚀 Guia Completo de Deploy

Instruções detalhadas para colocar o bot em produção.

---

## Opção 1: Railway.app (Recomendado)

### Por que Railway?
- ✅ 500 horas/mês grátis (suficiente para rodar 24/7 por ~20 dias)
- ✅ Deploy automático via GitHub
- ✅ Suporte nativo a Python + FFmpeg
- ✅ Variáveis de ambiente seguras
- ✅ Logs em tempo real no dashboard

### Passo a Passo

#### 1. Preparar o Repositório
```bash
# Inicializar git (se ainda não tiver)
git init
git add .
git commit -m "Initial commit: audio transcription bot"

# Criar repositório no GitHub e fazer push
git remote add origin https://github.com/seu-usuario/MeEscutaMeTranscreveBot.git
git branch -M main
git push -u origin main
```

#### 2. Criar Projeto no Railway
1. Acesse [railway.app](https://railway.app) e faça login com GitHub
2. Clique em **"New Project"**
3. Selecione **"Deploy from GitHub Repo"**
4. Escolha o repositório `MeEscutaMeTranscreveBot`
5. Railway detecta automaticamente o Python e o `railway.toml`

#### 3. Configurar Variáveis de Ambiente
No dashboard do Railway:
1. Clique no seu serviço
2. Vá em **Settings → Variables**
3. Adicione (uma por uma):

| Variável | Valor |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Token do @BotFather |
| `OPENAI_API_KEY` | Chave da OpenAI |
| `BOT_PASSWORD` | Sua senha de acesso ao bot |
| `MAX_AUDIO_SIZE_MB` | `25` (opcional) |
| `WHISPER_TEMPERATURE` | `0` (opcional) |

#### 4. Aguardar Deploy
- Railway faz build automaticamente ao detectar as variáveis
- Acompanhe o progresso em **Deployments**
- Quando aparecer ✅ **"Deploy Successful"**, o bot está online

#### 5. Verificar Logs
- Clique em **Deployments → Active Deployment → View Logs**
- Você deve ver:
  ```
  🎙️ Bot de Transcrição de Áudio — Iniciando
  📏 Tamanho máximo de áudio: 25MB
  🎯 Temperatura Whisper: 0.0
  🚀 Bot iniciado! Aguardando mensagens...
  ```

#### 6. Testar
1. Abra o Telegram e busque seu bot
2. Envie: `/start SUA_SENHA`
3. Envie um áudio curto
4. Verifique a transcrição

### Solução de Problemas (Railway)

| Problema | Solução |
|----------|---------|
| Build falha | Verifique se `requirements.txt` está correto |
| "Module not found" | Verifique se `nixpacks.toml` existe (FFmpeg) |
| Bot não responde | Verifique logs no dashboard |
| Deploy loop (restart) | Verifique variáveis de ambiente |

---

## Opção 2: Render.com (Alternativa)

### Deploy no Render

1. Acesse [render.com](https://render.com) e faça login com GitHub
2. **New → Web Service**
3. Conecte o repositório
4. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
5. Em **Environment → Add Environment Variable**:
   - Mesmas variáveis do Railway (tabela acima)
6. Clique em **Create Web Service**

> ⚠️ **Nota sobre FFmpeg no Render**: Adicione um arquivo `render.yaml` ou use Docker.
> Para simplificar, Railway é recomendado.

---

## Opção 3: VPS / Servidor Próprio

Se você tiver um servidor (DigitalOcean, AWS EC2, etc):

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/MeEscutaMeTranscreveBot.git
cd MeEscutaMeTranscreveBot

# 2. Instale FFmpeg
sudo apt update && sudo apt install -y ffmpeg python3.11 python3.11-venv

# 3. Crie ambiente virtual
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Instale dependências
pip install -r requirements.txt

# 5. Configure .env
cp .env.example .env
nano .env  # preencha com seus tokens

# 6. Execute com nohup (persiste após fechar SSH)
nohup python main.py > bot.log 2>&1 &

# 7. Verifique se está rodando
tail -f bot.log
```

### Manter rodando com systemd (recomendado para VPS):

```bash
# Criar arquivo de serviço
sudo nano /etc/systemd/system/transcribe-bot.service
```

Conteúdo:
```ini
[Unit]
Description=Telegram Audio Transcriber Bot
After=network.target

[Service]
Type=simple
User=seu-usuario
WorkingDirectory=/caminho/para/MeEscutaMeTranscreveBot
ExecStart=/caminho/para/MeEscutaMeTranscreveBot/.venv/bin/python main.py
Restart=on-failure
RestartSec=10
EnvironmentFile=/caminho/para/MeEscutaMeTranscreveBot/.env

[Install]
WantedBy=multi-user.target
```

```bash
# Ativar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable transcribe-bot
sudo systemctl start transcribe-bot

# Verificar status
sudo systemctl status transcribe-bot
```

---

## ⚠️ Notas Importantes

1. **Nunca commite o `.env`** — Sempre configure variáveis como secrets na plataforma
2. **FFmpeg é obrigatório** — Sem ele, a conversão de áudio falha
3. **Railway free tier**: 500h/mês (~20 dias rodando 24/7). Se precisar de mais, considere o plano pago ($5/mês) ou pausar quando não estiver usando
4. **Custos OpenAI**: $0.006/minuto de áudio. Monitore na [dashboard da OpenAI](https://platform.openai.com/usage)
