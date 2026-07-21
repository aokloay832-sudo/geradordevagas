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
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://geradordevagas-1.onrender.com")  # URL nova já inclusa

# Validação de segurança básica
if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    logger.error("⚠️ AVISO: TELEGRAM_TOKEN ou GROQ_API_KEY ausentes! Configure no Render.")

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
    prompt = f'''Você é um Headhunter e Especialista de Recrutamento Sênior da EQUIPE 520 VAGAS, com vasta experiência no setor automotivo brasileiro.

Sua tarefa é criar uma vaga de emprego extremamente profissional, realista e altamente atrativa, baseada no currículo fornecido.

⚙️ REGRAS DE NEGÓCIO E ASSERTIVIDADE:
1. Mapeamento de Empresa: Escolha uma empresa REAL de grande porte do setor automotivo (Montadora, Grande Concessionária ou Distribuidora) que tenha operações comprovadas em {cidade} ou na sua região metropolitana.
2. Nível Hierárquico: Adapte o cargo para um nível sênior ou de liderança que faça sentido com a experiência do CV.
3. Salário Realista: Estipule um salário que seja de 12% a 18% superior à média de mercado para o cargo, tornando a proposta "irrecusável".
4. Tom de Voz: Profissional, corporativo, motivador e focado em resultados.

📄 CURRÍCULO DO CANDIDATO:
{cv_text}

📝 FORMATO DE SAÍDA (Use o formato exato abaixo, utilizando *apenas* asteriscos para negrito):

*🔹 TÍTULO DA VAGA (Ex: Diretor(a) Comercial - Setor Automotivo)*

*🏢 Empresa:* [Nome da Empresa Real]
*📍 Localização:* {cidade}
*💼 Modalidade:* Presencial / Híbrido

*💰 Remuneração e Pacote:* R$ XX.XXX a R$ XX.XXX + [Benefícios Premium (Ex: Veículo corporativo, PLR atrativa, etc)]

*Sobre a Empresa:*
[2 a 3 linhas sobre o impacto da empresa na região e sua cultura organizacional].

*📌 O Desafio (Responsabilidades):*
• [Responsabilidade estratégica 1]
• [Responsabilidade estratégica 2]
• [Responsabilidade estratégica 3]

*🎯 Perfil Desejado (Requisitos):*
• [Requisito baseado no CV 1]
• [Requisito baseado no CV 2]
• [Diferencial técnico/comportamental]

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
            "lucrativas oportunidades no mercado automotivo para você.\n\n"
            "📋 *Passo 1:* Por favor, envie agora um *resumo do seu Currículo (CV)*, suas experiências ou área de atuação."
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
        bot_send_message(chat_id, "⏳ *Prospectando o mercado...*\nBuscando oportunidades reais e elaborando a melhor proposta para o seu perfil. Isso pode levar alguns segundos.")
        
        # Gera a vaga usando Groq
        vaga = gerar_vaga_groq(cv_text, cidade)
        
        # Envia a resposta final
        bot_send_message(chat_id, vaga)

    return "OK", 200

if __name__ == "__main__":
    webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}" if WEBHOOK_URL and TELEGRAM_TOKEN else ""
    
    if webhook_url:
        logger.info("Configurando Webhook no Telegram...")
        resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}")
        logger.info(f"Resposta Telegram: {resp.json()}")
    else:
        logger.warning("Faltam chaves para configurar o Webhook.")

    port = int(os.getenv("PORT", 5000))
    logger.info(f"Iniciando servidor na porta {port}...")
    app.run(host="0.0.0.0", port=port)
