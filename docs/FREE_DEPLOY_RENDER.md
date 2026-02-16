# 🚀 Guia de Deploy 100% Gratuito (Render.com)

Este guia ensina como hospedar seu bot **gratuitamente para sempre** usando o Render.com.

---

## 🏗️ Como funciona o plano gratuito?

O Render oferece hospedagem grátis para "Web Services", mas tem duas regras:
1. **Dorme após inatividade**: Se ngm acessar por 15min, ele desliga.
2. **Requer porta HTTP**: O app precisa ter um site respondendo.

**Nossa Solução:**
- Adicionei um "site falso" no bot (`main.py`) para o Render ficar feliz.
- Usaremos um **monitor gratuito** (UptimeRobot) para acessar esse site a cada 5 min, impedindo que o bot durma.

---

## 👣 Passo a Passo

### 1. Preparar o GitHub
Se ainda não fez, envie seu código para o GitHub:
```bash
git add .
git commit -m "Preparando para Render"
git push
```
*(Certifique-se de que o arquivo `Dockerfile` novo está no repositório)*

### 2. Criar conta no Render
1. Acesse [dashboard.render.com](https://dashboard.render.com)
2. Faça login com GitHub

### 3. Criar Web Service
1. Clique em **New +** → **Web Service**
2. Selecione "Build and deploy from a Git repository"
3. Conecte seu repositório `MeEscutaMeTranscreveBot`
4. Configure:
   - **Name**: `meu-bot-transcricao` (ou o que preferir)
   - **Region**: Escolha a mais próxima (ex: Ohio US)
   - **Runtime**: **Docker** (IMPORTANTE! Não escolha Python)
   - **Instance Type**: Free

5. **Variáveis de Ambiente (Environment Variables)**:
   Adicione as 3 chaves do seu arquivo `.env`:

   | Key | Value |
   |-----|-------|
   | `TELEGRAM_BOT_TOKEN` | `seu_token_aqui` |
   | `OPENAI_API_KEY` | `sk-...` |
   | `BOT_PASSWORD` | `sua_senha` |
   | `PYTHON_VERSION` | `3.11.0` (opcional) |

6. Clique em **Create Web Service**.

> O Render vai iniciar o deploy. Pode demorar uns 3-5 minutos na primeira vez.
> Aguarde aparecer "Live" verdinho no topo.

### 4. Impedir que o bot durma (UptimeRobot)
O Render desliga o bot se não houver tráfego. Vamos enganar ele:

1. Copie a URL do seu bot no Render (ex: `https://meu-bot.onrender.com`)
   - *Dica: Ao abrir essa URL no navegador, deve aparecer "Bot is running!"*
2. Crie uma conta grátis no [UptimeRobot.com](https://uptimerobot.com)
3. Clique em **Add New Monitor**
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: Meu Bot
   - **URL**: A URL do seu bot no Render
   - **Monitoring Interval**: 5 minutes (IMPORTANTE)
4. Salve.

Pronto! O UptimeRobot vai "cutucar" seu bot a cada 5 minutos, mantendo ele acordado 24/7 de graça.

---

## ⚠️ Limitações do Grátis
- O hardware é modesto (0.5 CPU, 512MB RAM). Para conversão de áudio, funciona bem, mas áudios MUITO longos (>1h) podem demorar um pouco mais.
- O primeiro request após um deploy pode ser lento.
- **Custos da API**: Lembre-se que a hospedagem é grátis, mas a API da OpenAI (Whisper) cobra $0.006/minuto de áudio.

---

## 🔄 Como atualizar o bot?
Sempre que você fizer um `git push` no seu repositório, o Render detecta e atualiza o bot automaticamente.
