# 🚂 Migração para Railway.app

O Render Free limitou o uso. O Railway é uma alternativa excelente para bots do Telegram pois não "dorme" tanto quanto o Render e oferece um crédito inicial generoso.

## Passo a Passo

### 1. Criar Conta
1. Acesse [railway.app](https://railway.app) e entre com seu **GitHub**.

### 2. Novo Projeto
1. Clique em **"New Project"**.
2. Selecione **"Deploy from GitHub repo"**.
3. Escolha seu repositório `MeEscutaMeTranscreveBot`.
4. Clique em **"Deploy Now"**.

### 3. Configurar Variáveis (CRÍTICO)
O Railway precisa das suas chaves para funcionar. No dashboard:
1. Clique no card do seu bot.
2. Vá na aba **"Variables"**.
3. Clique em **"New Variable"** e adicione estas exatamente como estão no seu `.env`:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `BOT_PASSWORD`
   - `PORT` = `8080` (Opcional, mas ajuda no health check)

### 4. Pronto!
O bot vai reiniciar automaticamente. Acompanhe os logs na aba **"Logs"**. Quando vir `🚀 Bot iniciado!`, ele já estará respondendo no Telegram.

---

> [!TIP]
> **Dica de Custo**: O Railway dá $5/mês de bônus no início. Para um bot pessoal, isso costuma durar o mês inteiro com folga. Se acabar, ele custará cerca de R$ 3,00 a R$ 5,00 por mês no plano "Hobbyist" (pago por uso).
