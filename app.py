import os
import logging
import requests
from flask import Flask, request
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# Configuração de log para monitoramento
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações de Ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://geradordevagas-1.onrender.com")

# ==============================================================================
# CONFIGURAÇÕES PERSONALIZADAS DO TEXTO DE DISPARO (ALTERE AQUI SE DESEJAR)
# ==============================================================================
NOME_RECRUTADOR = "Renato Monteiro"
EMPRESA_RECRUTADORA = "EQUIPE 520 VAGAS"
EMPRESA_PARCEIRA = "520 VAGAS RECRUTAMENTO"
LINK_CADASTRO = "https://equipe520vagas.com.br/app"
# ==============================================================================

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

# Dicionário em memória para gerenciar o estado da conversa por usuário
user_state = {}

def bot_send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id, 
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
        
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao enviar mensagem para o Telegram: {e}")

def bot_send_action(chat_id, action="typing"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    requests.post(url, json={"chat_id": chat_id, "action": action})

def enviar_menu_principal(chat_id):
    user_state.pop(chat_id, None)  # Reseta qualquer fluxo pendente
    texto = (
        "🚀 *Bem-vindo ao assistente da EQUIPE 520 VAGAS!*\n\n"
        "Selecione uma das opções abaixo no menu para começar:"
    )
    reply_markup = {
        "inline_keyboard": [
            [{"text": "💼 GERADOR DE VAGAS", "callback_data": "btn_gerar_vaga"}],
            [{"text": "📲 GERAR TEXTO PRA DISPARO", "callback_data": "btn_gerar_disparo"}]
        ]
    }
    bot_send_message(chat_id, texto, reply_markup=reply_markup)

def gerar_vaga_groq(cv_text: str, cidade: str):
    prompt = f'''Você é um Headhunter e Especialista de Recrutamento Sênior da EQUIPE 520 VAGAS, focado em vagas executivas e estratégicas em diversos setores do mercado.

Sua tarefa é criar uma vaga de emprego extremamente profissional, realista e altamente atrativa, baseada no currículo fornecido.

⚙️ REGRAS DE NEGÓCIO, VARIABILIDADE E ASSERTIVIDADE:
1. Mapeamento Dinâmico de Empresa: 
   - Analise a área de atuação do candidato e a cidade {cidade}.
   - Mapeie mentalmente uma lista de pelo menos 5 a 10 empresas REAIS (grandes multinacionais, indústrias, redes de grande porte ou empresas locais consolidadas) que operam em {cidade} ou região metropolitana.
   - IMPORTANTE: Não escolha sempre a empresa mais óbvia ou famosa da cidade. Alterne e selecione aleatoriamente UMA dessas empresas reais da lista para ser a contratante desta vaga, garantindo diversidade de marcas a cada consulta.

2. Nível Hierárquico: Adapte o título da vaga para estar perfeitamente alinhado com o cargo pretendido pelo candidato ou com o seu nível de experiência.

3. Regra Salarial: Identifique a pretensão salarial no currículo. Calcule e adicione de 10% a 15% acima deste valor para ser o salário base oferecido na vaga. Caso não haja pretensão informada, use uma média de mercado elevada para o cargo.

4. Naturalidade (Anti-Fake): NÃO copie todas as informações do CV de forma literal. Extraia apenas as competências essenciais e crie requisitos e responsabilidades genéricos do mercado corporativo para parecer uma vaga real de prateleira do RH.

5. Tom de Voz: Profissional, corporativo, atrativo e focado em excelência.

📄 CURRÍCULO DO CANDIDATO:
{cv_text}

📝 FORMATO DE SAÍDA (Use o formato exato abaixo, utilizando *apenas* asteriscos para negrito):

*🔹 TÍTULO DA VAGA (Ex: Analista Financeiro Sênior)*

*🏢 Empresa:* [Nome da Empresa Real Escolhida do Mapeamento]
*📍 Localização:* {cidade}
*💼 Modalidade:* Presencial / Híbrido

*💰 Remuneração e Pacote:* R$ XX.XXX a R$ XX.XXX + [Citar 2 ou 3 Benefícios Atrativos Corporativos]

*Sobre a Empresa:*
[2 a 3 linhas sobre a força desta empresa no mercado e sua cultura corporativa].

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
        "temperature": 0.8,
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

def montar_texto_disparo(dados: dict) -> str:
    primeiro_nome = dados.get("nome", "").strip().split()[0]
    candidato_info = dados.get("candidato_info", "")
    whatsapp = dados.get("whatsapp", "")
    vaga_pronta = dados.get("vaga", "")

    template = f"""{candidato_info}
{whatsapp}

(DADOS FICTÍCIOS)

=================================================
Boa tarde, *{primeiro_nome}*. Tudo bem?
Meu nome é {Renato Monteiro} e falo em nome da *{EB CORPORATE RH}*. Somos parceiros da empresa *{CATHO}* e selecionamos o seu currículo para uma *vaga* alinhada ao seu perfil.
Caso tenha interesse, estou à disposição para fornecer mais informações sobre a oportunidade.
Aguardamos seu retorno!
=======================================
{vaga_pronta}
==========================================================================================

Para dar continuidade ao processo, basta se cadastrar no site, baixar nosso app pelo link abaixo e fazer o login:
👉 {https://ebcrecursoshumanos.com}

Qualquer dúvida, pode me chamar aqui que te ajudo!
Atenciosamente,
{Renato Monteiro}
Recruiter

========================================================================================
Para liberar o acesso às vagas, faça login com seu CPF e senha e complete a verificação de documentos no seu perfil.
Essa verificação é obrigatória e garante sua legibilidade para as oportunidades de emprego.
É rápido e simples! Assim que for aprovado(a), você já poderá se candidatar.
Qualquer dúvida, estamos à disposição.
Sucesso! 💼
========================================================================================
"""
    return template

@app.route('/', methods=['GET'])
def home():
    return "🚀 Servidor da EQUIPE 520 VAGAS operante e online!"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = request.get_json()
    if not update:
        return "OK", 200

    # 1. TRATAMENTO DE BOTÕES INLINE (CALLBACK QUERIES)
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        action = cb["data"]

        if action == "btn_gerar_vaga":
            user_state[chat_id] = {"flow": "gerar_vaga", "step": "aguardando_cv"}
            bot_send_message(
                chat_id, 
                "📋 *Opção selecionada: Gerador de Vagas*\n\nPor favor, envie o *resumo do Currículo (CV)*, contendo atuação, competências e pretensão salarial."
            )
        elif action == "btn_gerar_disparo":
            user_state[chat_id] = {"flow": "gerar_disparo", "step": "aguardando_info_candidato"}
            bot_send_message(
                chat_id, 
                "📲 *Opção selecionada: Gerar Texto para Disparo*\n\n"
                "Por favor, envie as informações básicas do candidato no seguinte formato:\n\n"
                "*Exemplo:*\n"
                "Rafaela dos Santos azevedo\n"
                "37 anos, Solteira - Alfenas, MG - jd alvorada"
            )
        return "OK", 200

    # 2. TRATAMENTO DE MENSAGENS DE TEXTO
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        if not text:
            return "OK", 200

        # Comando /start, /menu ou 'cancelar' força a volta ao menu principal
        if text.startswith('/start') or text.startswith('/menu') or text.lower() == 'cancelar':
            enviar_menu_principal(chat_id)
            return "OK", 200

        state = user_state.get(chat_id)

        # Se o usuário mandou mensagem sem escolher uma opção no menu
        if not state:
            enviar_menu_principal(chat_id)
            return "OK", 200

        # FLUXO 1: GERADOR DE VAGAS
        if state.get("flow") == "gerar_vaga":
            if state.get("step") == "aguardando_cv":
                state["cv"] = text
                state["step"] = "aguardando_cidade"
                bot_send_message(
                    chat_id, 
                    "✅ *Currículo recebido!*\n\n📍 *Passo 2:* Qual é a *cidade* e estado de preferência para esta vaga? (Ex: São Paulo - SP)"
                )
            elif state.get("step") == "aguardando_cidade":
                cidade = text
                cv_text = state.get("cv")
                user_state.pop(chat_id, None)

                bot_send_action(chat_id, "typing")
                bot_send_message(
                    chat_id, 
                    "⏳ *Prospectando o mercado...*\nBuscando oportunidades reais e desenhando a proposta perfeita para o seu perfil. Aguarde um instante."
                )

                vaga = gerar_vaga_groq(cv_text, cidade)
                bot_send_message(chat_id, vaga)
                
                # Exibe o menu novamente ao finalizar
                enviar_menu_principal(chat_id)

        # FLUXO 2: GERAR TEXTO PRA DISPARO
        elif state.get("flow") == "gerar_disparo":
            if state.get("step") == "aguardando_info_candidato":
                # Armazena o bloco com Nome + Idade/Endereço
                linhas = text.split("\n")
                state["nome"] = linhas[0].strip() if linhas else text
                state["candidato_info"] = text
                state["step"] = "aguardando_whatsapp"
                bot_send_message(
                    chat_id, 
                    "📱 *Passo 2:* Envie o *WhatsApp / Telefone* do candidato.\n(Ex: (35) 98883-1403)"
                )
            elif state.get("step") == "aguardando_whatsapp":
                state["whatsapp"] = text
                state["step"] = "aguardando_vaga"
                bot_send_message(
                    chat_id, 
                    "📄 *Passo 3:* Cole aqui a *Vaga Pronta* (gerada na função anterior)."
                )
            elif state.get("step") == "aguardando_vaga":
                state["vaga"] = text
                dados_finais = state
                user_state.pop(chat_id, None)

                texto_formatado = montar_texto_disparo(dados_finais)

                bot_send_message(
                    chat_id, 
                    "✅ *Texto de Disparo Gerado com Sucesso!*\n\nCopie o bloco abaixo:"
                )
                # Envia o texto limpo para facilidade de cópia (sem parse_mode para evitar erros de Markdown no texto colado)
                bot_send_message(chat_id, texto_formatado, parse_mode=None)

                # Reexibe o menu principal
                enviar_menu_principal(chat_id)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Iniciando servidor local na porta {port}...")
    app.run(host="0.0.0.0", port=port)
