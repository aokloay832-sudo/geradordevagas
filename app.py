import os
import logging
import requests
from flask import Flask, request
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (esconde as chaves)
load_dotenv()

# Configuração de log para monitoramento no Render e no terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações de Ambiente (Sem chaves hardcoded no código!)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://geradordevagas-1.onrender.com")

# Validação de segurança básica
if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    logger.error("⚠️ AVISO: TELEGRAM_TOKEN ou GROQ_API_KEY ausentes! Configure no Render.")

# ==============================================================================
# REGISTRO DO WEBHOOK NO STARTUP DO GUNICORN (RENDER)
# ==============================================================================
if TELEGRAM_TOKEN and WEBHOOK_URL:
    webhook_endpoint = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_endpoint}")
        logger.info(f"✅ Webhook acionado automaticamente: {r.json()}")
    except Exception as e:
        logger.error(f"❌ Erro ao configurar webhook: {e}")
# ==============================================================================

# Dicionário em memória para gerenciar o estado da conversa
user_state = {}

def bot_send_message(chat_id, text, parse_mode="Markdown"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id, 
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao enviar mensagem para o Telegram: {e}")

def bot_send_action(chat_id, action="typing"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    requests.post(url, json={"chat_id": chat_id, "action": action})

def gerar_vaga_groq(cv_text: str, cidade: str):
    prompt = f'''Você é um Headhunter e Especialista de Recrutamento Sênior da EQUIPE 520 VAGAS, focado em vagas executivas e estratégicas em diversos setores do mercado.

Sua tarefa é criar uma vaga de emprego extremamente profissional, realista e altamente atrativa, baseada no currículo fornecido.

⚙️ REGRAS DE NEGÓCIO E ASSERTIVIDADE:
1. Mapeamento de Empresa: Analise a área de atuação do candidato (ex: Finanças, TI, Vendas, etc) e escolha uma empresa REAL de médio ou grande porte deste exato setor que tenha operações comprovadas em {cidade} ou na sua região metropolitana.
2. Nível Hierárquico: Adapte o título da vaga para estar perfeitamente alinhado com o cargo pretendido pelo candidato ou com o seu nível de experiência.
3. Regra Salarial: Identifique a pretensão salarial no currículo. Calcule e adicione de 10% a 15% acima deste valor para ser o salário base oferecido na vaga, tornando a proposta altamente atrativa. Caso não haja pretensão informada, use uma média de mercado elevada para o cargo.
4. Naturalidade (Anti-Fake): NÃO copie todas as informações, ferramentas e sistemas do CV de forma literal para a vaga. Isso faz a vaga parecer falsa e moldada ao candidato. Extraia apenas as competências essenciais e crie requisitos/responsabilidades de mercado genéricos, porém exigentes, fazendo com que a vaga pareça uma oportunidade real já existente.
5. Tom de Voz: Profissional, corporativo, atrativo e focado em excelência.

📄 CURRÍCULO DO CANDIDATO:
{cv_text}

📝 FORMATO DE SAÍDA (Use o formato exato abaixo, utilizando *apenas* asteriscos para negrito):

*🔹 TÍTULO DA VAGA (Ex: Analista Financeiro Sênior)*

*🏢 Empresa:* [Nome da Empresa Real]
*📍 Localização:* {cidade}
*💼 Modalidade:* Presencial / Híbrido

*💰 Remuneração e Pacote:* R$ XX.XXX a R$ XX.XXX + [Citar 2 ou 3 Benefícios Atrativos Corporativos]

*Sobre a Empresa:*
[2 a 3 linhas sobre a força da empresa no mercado e sua cultura corporativa].

*📌 O Desafio (Responsabilidades):*
• [Responsabilidade técnica ou estratégica 1]
• [Responsabilidade técnica ou estratégica 2]
• [Responsabilidade técnica ou estratégica 3]
• [Responsabilidade técnica ou estratégica 4]

*🎯 Perfil Desejado (Requisitos):*
• [Requisito 1 - Graduação/Pós]
• [Requisito 2 - Experiência essencial abstraída do CV]
• [Requisito 3 - Ferramenta ou habilidade comportamental]

Responda APENAS com o texto da vaga pronto para ser enviado. Não adicione saudações ou explicações extras.
'''

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "max_tokens": 2048
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=40
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Erro na API Groq: {e}")
        return "❌ *Ops!* Ocorreu um erro interno ao processar a vaga com a inteligência artificial. Tente novamente em alguns instantes."

@app.route('/', methods=['GET'])
def home():
    return "🚀 Servidor da EQUIPE 520 VAGAS operante e online!"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = request.get_json()
    
    if not update or "message" not in update:
        return "OK", 200

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
        return "OK", 200

    logger.info(f"Nova mensagem recebida de {chat_id}")

    # Comando /start ou reinício do fluxo
    if text.startswith('/start') or text.lower() == 'cancelar':
        user_state.pop(chat_id, None)  # Limpa o estado se existir
        boas_vindas = (
            "🚀 *Bem-vindo ao assistente da EQUIPE 520 VAGAS!*\n\n"
            "Sou o seu Headhunter Digital. Minha missão é analisar seu perfil e prospectar as melhores e mais "
            "lucrativas oportunidades do mercado corporativo para você.\n\n"
            "📋 *Passo 1:* Por favor, envie agora um *resumo do seu Currículo (CV)*, contendo sua atuação, competências e pretensão salarial."
        )
        bot_send_message(chat_id, boas_vindas)
        return "OK", 200

    # Lógica de estados da conversa
    if chat_id not in user_state:
        # Usuário enviou o CV
        user_state[chat_id] = {"cv": text}
        bot_send_message(chat_id, "✅ *Currículo recebido e em análise!*\n\n📍 *Passo 2:* Qual é a *cidade* e estado de preferência para esta vaga? (Ex: São Paulo - SP)")
    else:
        # Usuário enviou a cidade
        cidade = text
        cv_text = user_state[chat_id]["cv"]
        del user_state[chat_id] # Limpa o estado para uma nova consulta

        # Mostra o status de digitando no Telegram
        bot_send_action(chat_id, "typing")
        bot_send_message(chat_id, "⏳ *Prospectando o mercado...*\nBuscando oportunidades reais e desenhando a proposta perfeita para o seu perfil. Isso pode levar alguns segundos.")
        
        # Gera a vaga usando Groq
        vaga = gerar_vaga_groq(cv_text, cidade)
        
        # Envia a resposta final
        bot_send_message(chat_id, vaga)

    return "OK", 200

if __name__ == "__main__":
    # Isso só roda no ambiente local agora (ex: Pydroid, VSCode)
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Iniciando servidor local na porta {port}...")
    app.run(host="0.0.0.0", port=port)
