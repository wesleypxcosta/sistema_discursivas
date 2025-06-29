import os
import json
import google.generativeai as genai
import streamlit as st
import datetime
import re
import hashlib
import firebase_admin 
from firebase_admin import credentials, firestore

# --- ESTILIZAÇÃO CUSTOMIZADA DA INTERFACE (CSS INJETADO) ---
st.markdown(
    """
    <style>
    /* Estilo para o corpo geral do aplicativo */
    body {
        font-family: 'Arial', sans-serif;
        color: #262730; /* Cor do texto padrão */
    }

    /* Ajusta o tamanho da fonte para todos os textos principais */
    p, div, span, label, h1, h2, h3, h4, h5, h6 {
        font-size: 1em; /* 1 vezes o tamanho padrão */
        line-height: 1.6; /* Espaçamento entre linhas */
    }

    /* Títulos do Streamlit */
    h1 {
        font-size: 2em !important; /* !important força a aplicação do estilo */
        color: #0E4D92; /* Um azul mais escuro para o título principal */
    }
    h2 {
        font-size: 1.5em !important;
        color: #1A5E95; /* Tom de azul ligeiramente mais claro */
    }
    h3 {
        font-size: 1.5em !important;
        color: #2F7DBF; /* Tom de azul ainda mais claro */
    }

    /* Personaliza o campo de input de texto (pergunta, resposta) */
    .stTextArea, .stTextInput {
        font-size: 1.2em !important;
        background-color: #bfd7ea; /* Fundo levemente cinza */
        border-radius: 3px;
        /* border: 2px solid #ced4da; */
        padding: 0.5em; /* Preenchimento interno */
    }

    /* Estiliza os botões */
    .stButton > button {
        font-size: 1.1em !important;
        padding: 0.6em 1.2em; /* Preenchimento interno do botão */
        border-radius: 0px; /* Cantos mais arredondados */
        border: none;
        background-color: #bfd7ea; /* Um azul claro para botões primários cae9ff*/
        color: #13315c; /* Azul escuro para o texto do botão */ 
        cursor: pointer;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); /* Sombra suave para profundidade */
        font-weight: bold; /* Negrito para destaque */ 
        transition: background-color 0.3s ease; /* Efeito de transição suave */
    }
    .stButton > button:hover {
        background-color: #415a77; /* Cinza um pouco escuro ao passar o mouse */
        color: #ffffff; /* Texto branco ao passar o mouse */
        font-weight: bold; /* Negrito ao passar o mouse */
    }

    /* Estilo para botões secundários (como "Limpar Histórico") */
    .stButton[data-testid="baseButtonSecondary"] > button {
        background-color: #6c757d; /* Cinza para secundário */
    }
    .stButton[data-testid="baseButtonSecondary"] > button:hover {
        background-color: #5a6268;
    }


    /* Estilo para os blocos de informação (st.info, st.success, st.warning) */
    .stAlert {
        font-size: 1.0em !important;
        border-radius: 5px;
    }

    /* Estilo específico para o feedback do Gemini */
    div[data-testid="stMarkdownContainer"] h3 {
        color: #2F7DBF; /* Cor diferente para os subtítulos do feedback */
        font-size: 1.2em !important;
    }
    div[data-testid="stMarkdownContainer"] strong {
        color: #333; /* Cor mais escura para negritos */
    }

    /* Ajuste para as abas */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
      font-size:1.1em; /* Tamanho da fonte dos títulos das abas */
    }

    </style>
    """,
    unsafe_allow_html=True
)
# --- FIM DA ESTILIZAÇÃO CUSTOMIZADA ---

# --- Configuração do Gemini ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    st.error("Erro: A chave de API do Gemini (GEMINI_API_KEY) não está configurada. Por favor, defina a variável de ambiente.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')

# --- CONFIGURAÇÃO DO FIRESTORE ---
# Caminho para o arquivo JSON da sua chave de serviço do Google Cloud para TESTE LOCAL
SERVICE_ACCOUNT_KEY_PATH_LOCAL = "gcp_service_account_key.json"

# Nomes das Coleções no Firestore
USERS_COLLECTION = "users"
CARDS_COLLECTION = "user_cards" # Para armazenar cartões de cada usuário (subcoleção)
FEEDBACK_COLLECTION = "feedback_history" # Para armazenar histórico de feedback de cada usuário (subcoleção)

# Tenta inicializar o Firebase Admin SDK
try:
    firebase_admin.get_app() # Tenta obter o app, se já inicializado
except ValueError: # Este erro ocorre se o app não foi inicializado
    try:
        # **SOLUÇÃO: PRIORIZA O ARQUIVO LOCAL PRIMEIRO, E SÓ DEPOIS TENTA OS SECRETS/PADRÃO**
        if os.path.exists(SERVICE_ACCOUNT_KEY_PATH_LOCAL):
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH_LOCAL)
            firebase_admin.initialize_app(cred)
            st.success(f"Firebase inicializado via arquivo local: {SERVICE_ACCOUNT_KEY_PATH_LOCAL}")
        # EM SEGUNDO, TENTA CARREGAR DE STREAMLIT SECRETS (para deploy na nuvem)
        elif st.secrets.get("FIRESTORE_CREDENTIALS_JSON") and st.secrets.get("GOOGLE_CLOUD_PROJECT_ID"): # <-- USAR .get()
            cred_info_json = json.loads(st.secrets["FIRESTORE_CREDENTIALS_JSON"])
            project_id_from_secrets = st.secrets["GOOGLE_CLOUD_PROJECT_ID"]
            
            cred = credentials.Certificate(cred_info_json)
            firebase_admin.initialize_app(cred, {'projectId': project_id_from_secrets})
            st.success("Firebase inicializado via Streamlit Secrets!")
        # SE NENHUM DOS ANTERIORES, TENTA INICIALIZAÇÃO PADRÃO (para GCP nativo)
        else:
            firebase_admin.initialize_app()
            st.success("Firebase inicializado via credenciais padrão do Google Cloud.")
            
    except Exception as e:
        st.error(f"Erro CRÍTICO ao inicializar Firebase: {e}. Verifique as credenciais e o Project ID.")
        st.stop() # Interrompe a execução se não conseguir conectar ao Firebase

db = firestore.client() # Inicializa o cliente Firestore

# Nomes das Coleções no Firestore
USERS_COLLECTION = "users"
CARDS_COLLECTION = "user_cards" # Para armazenar cartões de cada usuário (subcoleção)
FEEDBACK_COLLECTION = "feedback_history" # Para armazenar histórico de feedback de cada usuário (subcoleção)

# --- Constantes para Nomes de Arquivo e Diretório Base (para compatibilidade/local) ---
BASE_DATA_DIR = "data"
CARDS_FILENAME = "cards.json" # nome do arquivo de cartões dentro da pasta do usuário (localmente, se ainda usado)
FEEDBACK_HISTORY_FILENAME = "feedback_history.json" # (localmente, se ainda usado)
USERS_FILE = os.path.join(BASE_DATA_DIR, "users.json") # (localmente, para inicializar_admin_existencia)

# --- DEFINIÇÃO DO ADMINISTRADOR ---
ADMIN_USERNAME = "admin"

# --- Funções Auxiliares para Caminhos de Arquivo por Usuário (e Global, se ainda usado localmente) ---
def get_user_data_path(username):
    user_dir = os.path.join(BASE_DATA_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_cards_file_path(username): # Ainda presente, mas não mais a fonte de dados primária
    return os.path.join(get_user_data_path(username), CARDS_FILENAME)

def get_feedback_history_file_path(username):
    return os.path.join(get_user_data_path(username), FEEDBACK_HISTORY_FILENAME)

# --- Funções de Manipulação de Cartões (AGORA NO FIRESTORE, POR USUÁRIO) ---
def carregar_cartoes(username): # AGORA CARREGA CARTÕES DO USUÁRIO
    """
    Carrega os cartões do Firestore para um usuário específico,
    incluindo o ID do documento do Firestore.
    """
    cartoes = []
    try:
        # Acessa a subcoleção 'user_cards' dentro do documento do usuário
        # O ID do documento do usuário é o próprio username
        docs = db.collection(USERS_COLLECTION).document(username).collection(CARDS_COLLECTION).stream()
        for doc in docs:
            card_data = doc.to_dict()
            card_data['doc_id'] = doc.id # **CRUCIAL**: Salva o ID do documento
            cartoes.append(card_data)
        return cartoes
    except Exception as e:
        st.error(f"Erro ao carregar cartões de '{username}' do Firestore: {e}")
        return []

def adicionar_cartao_firestore(card_data, username): # NOVA FUNÇÃO
    """Adiciona um único cartão ao Firestore e retorna o doc_id."""
    try:
        # Remove 'doc_id' se ele existe (não queremos salvá-lo como um campo de dado)
        card_to_add = card_data.copy()
        if 'doc_id' in card_to_add:
            del card_to_add['doc_id']
        
        doc_ref = db.collection(USERS_COLLECTION).document(username).collection(CARDS_COLLECTION).add(card_to_add)
        st.success(f"Cartão adicionado com ID: {doc_ref[1].id}")
        return doc_ref[1].id # Retorna o ID do documento criado
    except Exception as e:
        st.error(f"Erro ao adicionar cartão no Firestore: {e}")
        return None

def atualizar_cartao_firestore(doc_id, card_data, username): # NOVA FUNÇÃO
    """Atualiza um cartão existente no Firestore pelo seu doc_id."""
    try:
        card_to_update = card_data.copy()
        if 'doc_id' in card_to_update: # Não precisamos do doc_id no próprio documento
            del card_to_update['doc_id']
        
        db.collection(USERS_COLLECTION).document(username).collection(CARDS_COLLECTION).document(doc_id).update(card_to_update)
        st.success(f"Cartão com ID {doc_id} atualizado no Firestore.")
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar cartão com ID {doc_id} no Firestore: {e}")
        return False

def excluir_cartao_firestore(doc_id, username): # NOVA FUNÇÃO
    """Exclui um cartão específico do Firestore pelo seu doc_id."""
    try:
        db.collection(USERS_COLLECTION).document(username).collection(CARDS_COLLECTION).document(doc_id).delete()
        st.success(f"Cartão com ID {doc_id} excluído do Firestore.")
        return True
    except Exception as e:
        st.error(f"Erro ao excluir cartão com ID {doc_id} do Firestore: {e}")
        return False


# Funções de histórico de feedback (JÁ ESTAVAM OTIMIZADAS PARA ADD)
def carregar_historico_feedback(username):
    """
    Carrega o histórico de feedback do Firestore para um usuário específico.
    """
    historico = []
    try:
        docs = db.collection(USERS_COLLECTION).document(username).collection(FEEDBACK_COLLECTION).order_by('timestamp').stream()
        for doc in docs:
            historico.append(doc.to_dict())
        return historico
    except Exception as e:
        st.error(f"Erro ao carregar histórico de feedback de '{username}' do Firestore: {e}")
        return []

def salvar_historico_feedback(historico_data, username):
    """
    Salva as novas entradas de histórico de feedback no Firestore para um usuário específico.
    Assume que o 'historico_data' contém todas as entradas, e apenas a última é nova.
    Se a lista está vazia, limpa a coleção.
    """
    try:
        user_feedback_ref = db.collection(USERS_COLLECTION).document(username).collection(FEEDBACK_COLLECTION)
        
        if historico_data: # Se há algo no histórico para salvar/atualizar
            last_entry = historico_data[-1] # Pega a última entrada adicionada ao histórico em memória
            user_feedback_ref.add(last_entry) # Adiciona como um novo documento no Firestore
        else: # Se a lista de histórico na sessão está vazia, significa que o usuário limpou.
            # Limpa a coleção inteira no Firestore para este usuário.
            current_docs_refs = user_feedback_ref.stream()
            for doc_ref in current_docs_refs:
                doc_ref.reference.delete()
        
    except Exception as e:
        st.error(f"Erro ao salvar histórico de feedback de '{username}' no Firestore: {e}")


# --- Funções para Gerenciamento de Usuários e Senhas (AGORA NO FIRESTORE) ---
def hash_password(password):
    """Gera o hash SHA256 de uma senha."""
    return hashlib.sha256(password.encode()).hexdigest()

def carregar_usuarios():
    """Carrega os usuários e seus hashes de senha do Firestore."""
    users = {}
    try:
        docs = db.collection(USERS_COLLECTION).stream() # Acessa a coleção 'users' principal
        for doc in docs:
            user_data = doc.to_dict()
            users[doc.id] = user_data.get('password_hash') # ID do documento é o username
        return users
    except Exception as e:
        st.error(f"Erro ao carregar usuários do Firestore: {e}")
        return {}

def salvar_usuarios(users_data):
    """Salva os usuários e seus hashes de senha no Firestore."""
    try:
        # Para cada usuário no users_data, atualiza/cria um documento no Firestore
        for username, password_hash in users_data.items():
            db.collection(USERS_COLLECTION).document(username).set({
                'password_hash': password_hash,
                'last_updated': datetime.datetime.now() # Opcional: adicionar timestamp
            })
        st.success("Usuários salvos no Firestore com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar usuários no Firestore: {e}")

# Garante que o usuário admin exista na primeira execução
def inicializar_admin_existencia():
    users = carregar_usuarios()
    if ADMIN_USERNAME not in users:
        st.sidebar.warning(f"O usuário administrador ('{ADMIN_USERNAME}') não existe. Por favor, crie-o manualmente no Firestore ou via aba 'Gerenciar Usuários' depois de criar um admin inicial.")
        st.stop() # App não pode iniciar sem admin para criar outros usuários
    return True


# --- Função de Interação com o Gemini ---
def comparar_respostas_com_gemini(pergunta, resposta_usuario, resposta_esperada): # <-- ADICIONADO 'pergunta' AQUI
    """
    Envia a resposta do usuário e a resposta esperada para o Gemini
    e pede para ele comparar o sentido, apontar erros gramaticais/grafia,
    sugerir modificações, dar uma pontuação e indicar lacunas de conteúdo.
    O feedback será sucinto.
    """
    if not resposta_usuario.strip() or not resposta_esperada.strip():
        return "Por favor, forneça ambas as respostas para comparação."

    prompt = f"""
    Sua tarefa é fornecer um feedback **sucinto e objetivo** para a 'Resposta do Usuário' em relação à 'Resposta Esperada' e, crucialmente, em relação à **Pergunta** feita.
    A ideia é que o usuário ganhe agilidade no aprendizado, focando nos pontos essenciais **relevantes para a Pergunta**.

    Ao avaliar, desconsidere detalhes da 'Resposta Esperada' (como número de artigo, formatação, ordem exata de enumeração, ou informações contextuais que a Pergunta NÃO solicitou explicitamente).
    Foque se a 'Resposta do Usuário' aborda os pontos essenciais que a **Pergunta** exigia, conforme os critérios contidos na 'Resposta Esperada'.

    O feedback deve ser dividido em seções claras, sem rodeios.

    Quanto às sugestões de melhoria textual, elas devem ser **concisas** e diretas, focando em clareza, concisão e correção, sem entrar em detalhes excessivos. Verifique ainda, se o texto do usuário possui ambiguidades, se há falhas de paralelismo sintático, se a estrutura gramatical é confusa. Verifique se há caso de repetição de palavras redundantes, exceto aquelas utilizadas para manter o paralelismo sintático. Observe-se que, em regra, a resposta do usuário deve ser em texto corrido e, portanto, mesmo que na Resposta Esperada contenha bullet points, o usuário não precisa utilizá-los em sua resposta. Aponte as melhorias de forma direta e prática, sem rodeios.

    **Estrutura de Feedback Requerida:**

    **1. Pontuação de Sentido (0-100):**
    [Uma pontuação numérica de 0 a 100% baseada na similaridade de sentido com a Resposta Esperada, **considerando a relevância para a Pergunta**. 100% = sentido idêntico e completo **para a Pergunta**.]

    **2. Avaliação Principal do Sentido:**
    [Feedback qualitativo muito breve (ex: "Excelente.", "Bom, mas faltou X.", "Incompleto.", "Incorreto.").]

    **3. Lacunas de Conteúdo:**
    [Liste os pontos-chave da Resposta Esperada que NÃO foram abordados ou foram abordados de forma insuficiente na Resposta do Usuário **E que são relevantes para a Pergunta**. Use bullet points sucintos. Se não houver lacunas, diga "Nenhuma lacuna significativa."]

    **4. Erros Gramaticais/Ortográficos:**
    [Liste os principais erros encontrados na 'Resposta do Usuário'. Formato: 'Palavra/Frase Incorreta' -> 'Sugestão de Correção'. Se não houver, diga "Nenhum erro encontrado."]

    **5. Sugestões Rápidas de Melhoria:**
    [Sugestões muito concisas para aprimorar a resposta em termos de clareza, concisão e correção, baseadas nos erros e lacunas. Use bullet points.]

    ---
    Pergunta:
    {pergunta}

    ---
    Resposta Esperada:
    {resposta_esperada}

    ---
    Resposta do Usuário:
    {resposta_usuario}
    ---

    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao comunicar com o Gemini: {e}"

# --- FUNÇÃO AUXILIAR PARA PARSEAR E EXIBIR SEÇÕES DO FEEDBACK (GLOBAL E OTIMIZADA) ---
def parse_feedback_sections(full_feedback_text):
    """
    Analisa o feedback estruturado do Gemini e retorna um dicionário com as seções.
    Retorna dicionário com chaves 'score', 'meaning_eval', 'content_gaps', etc.
    """
    section_keys = {
        "score": "1. Pontuação de Sentido (0-100):",
        "meaning_eval": "2. Avaliação Principal do Sentido:",
        "content_gaps": "3. Lacunas de Conteúdo:",
        "grammar_errors": "4. Erros Gramaticais/Ortográficos:",
        "suggestions": "5. Sugestões Rápidas de Melhoria:"
    }
    
    parsed_data = {key: "Não disponível." for key in section_keys.keys()} # Default values

    # Função auxiliar para extrair conteúdo entre chaves
    def extract_content(full_text, start_key_title, next_key_title=None):
        start_index = full_text.find(f"**{start_key_title}**")
        if start_index == -1: return None
        content_start = start_index + len(f"**{start_key_title}**")
        
        # Ajuste para lidar com o caractere ':' logo após a chave
        if content_start < len(full_text) and full_text[content_start] == ':':
            content_start += 1 
        
        if next_key_title:
            next_index = full_text.find(f"**{next_key_title}**", content_start)
            if next_index != -1: return full_text[content_start:next_index].strip()
            else: return full_text[content_start:].strip().split('---')[0].strip()
        else: return full_text[content_start:].strip().split('---')[0].strip()

    try:
        # Extrai cada seção usando a ordem definida
        for i, (key, title) in enumerate(section_keys.items()):
            next_title = None
            if i + 1 < len(section_keys):
                next_title = list(section_keys.values())[i+1]
            
            content = extract_content(full_feedback_text, title, next_title)
            if content is not None:
                parsed_data[key] = content
            
    except Exception as e:
        return {"raw_feedback": full_feedback_text, "error": str(e)}

    return parsed_data


# --- INICIALIZAÇÃO DOS ESTADOS DO STREAMLIT ---
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# st.session_state.user_cartoes para os cartões do usuário logado
if 'user_cartoes' not in st.session_state:
    st.session_state.user_cartoes = []

# global_cartoes foi removido.

if 'feedback_history' not in st.session_state:
    st.session_state.feedback_history = []

if 'current_card_index' not in st.session_state:
    st.session_state.current_card_index = 0
if 'show_expected_answer' not in st.session_state:
    st.session_state.show_expected_answer = False

if 'last_gemini_feedback_display_parsed' not in st.session_state:
    st.session_state.last_gemini_feedback_display_parsed = None

if 'last_gemini_feedback_question' not in st.session_state:
    st.session_state.last_gemini_feedback_question = None

if 'last_gemini_expected_answer' not in st.session_state:
    st.session_state.last_gemini_expected_answer = None

if 'add_card_form_key_suffix' not in st.session_state:
    st.session_state.add_card_form_key_suffix = 0

if 'last_materia_input' not in st.session_state:
    st.session_state.last_materia_input = ""
if 'last_assunto_input' not in st.session_state:
    st.session_state.last_assunto_input = ""

if 'ordered_cards_for_session' not in st.session_state:
    st.session_state.ordered_cards_for_session = []

if 'difficult_cards_for_session' not in st.session_state:
    st.session_state.difficult_cards_for_session = []

if 'current_card_index_difficult' not in st.session_state:
    st.session_state.current_card_index_difficult = 0


# --- LÓGICA PRINCIPAL DO APP ---
# Garante que o admin exista antes de prosseguir com qualquer outra coisa
if not inicializar_admin_existencia(): 
    st.stop() # Se o admin não existe e o formulário de criação está sendo exibido, pare aqui.

# Se o usuário não estiver logado, exibe a tela de login
if st.session_state.logged_in_user is None:
    st.title("Treinamento de Discursivas")
    st.subheader("Seja bem-vindo! Informe seus dados de acesso.")

    username_login = st.text_input("Usuário:", key="username_login_input_form")
    password_login = st.text_input("Senha:", type="password", key="password_login_input_form")
    
    col_login_btns_1, col_login_btns_2 = st.columns(2)

    with col_login_btns_1:
        if st.button("Entrar", key="login_button"):
            if username_login.strip() and password_login.strip():
                users_data = carregar_usuarios()
                if username_login.strip() in users_data and users_data[username_login.strip()] == hash_password(password_login.strip()):
                    st.session_state.logged_in_user = username_login.strip()
                    st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user)
                    st.session_state.user_cartoes = carregar_cartoes(st.session_state.logged_in_user)
                    
                    # --- Lógica de Reordenação da aba "Todas as Perguntas" (no Login) ---
                    card_latest_scores = {}
                    for entry in reversed(st.session_state.feedback_history):
                        card_id = (entry["pergunta"], entry["materia"], entry["assunto"])
                        if card_id not in card_latest_scores:
                            card_latest_scores[card_id] = entry.get("nota_sentido")

                    cards_for_ordering = []
                    for card in st.session_state.user_cartoes: 
                        card_id = (card["pergunta"], card["materia"], card["assunto"])
                        score_to_order = card_latest_scores.get(card_id, -1) 
                        cards_for_ordering.append((card, score_to_order))

                    st.session_state.ordered_cards_for_session = [card_obj for card_obj, _ in sorted(cards_for_ordering, key=lambda x: x[1])]
                    # --- FIM DA REORDENAÇÃO DA ABA "TODAS AS PERGUNTAS" NO LOGIN ---

                    # --- Lógica para Identificar Perguntas Mais Difíceis (no Login) ---
                    difficult_cards = []
                    for card in st.session_state.user_cartoes: 
                        card_id = (card["pergunta"], card["materia"], card["assunto"])
                        if card_id in card_latest_scores and card_latest_scores[card_id] is not None and card_latest_scores[card_id] < 80:
                            difficult_cards.append(card)
                    st.session_state.difficult_cards_for_session = difficult_cards
                    # --- FIM DA LÓGICA DE DIFÍCEIS NO LOGIN ---

                    # Resetar outros estados para o novo usuário
                    st.session_state.current_card_index = 0
                    st.session_state.current_card_index_difficult = 0
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()
                else:
                    st.error("Nome de usuário ou senha incorretos.")
            else:
                st.warning("Por favor, digite nome de usuário e senha.")
        with col_login_btns_2:
            pass
    
    pass 
    
else: # Usuário logado
    st.title("Treinamento de Discursivas")
    st.write("Fortaleça sua **memória** e aprimore sua **escrita** com correções instantâneas do **Gemini**.")
    st.write(f"Bem-vindo(a), **{st.session_state.logged_in_user}**.")

    # Botão de Logout
    if st.sidebar.button("Sair", key="logout_button"):
        st.session_state.logged_in_user = None
        st.session_state.feedback_history = []
        st.session_state.user_cartoes = []
        st.session_state.current_card_index = 0
        st.session_state.current_card_index_difficult = 0
        st.session_state.show_expected_answer = False
        st.session_state.last_gemini_feedback_display_parsed = None
        st.session_state.ordered_cards_for_session = []
        st.session_state.difficult_cards_for_session = []
        st.rerun()

    # Define quais abas serão exibidas e cria as referências para os blocos 'with'
    tab_options = []
    if st.session_state.logged_in_user == ADMIN_USERNAME:
        tab_options = ["Todas as Perguntas", "Perguntas Mais Difíceis", "Gerenciar Cartões", "Métricas de Desempenho", "Gerenciar Usuários"]
    else:
        tab_options = ["Todas as Perguntas", "Perguntas Mais Difíceis", "Gerenciar Cartões", "Métricas de Desempenho"]

    selected_tab = st.sidebar.radio("Navegar entre Seções:", tab_options, key="main_tab_selector")

    # --- Funções de Renderização de Conteúdo por Aba ---
    # As funções de renderização devem estar definidas DENTRO do 'else' do login,
    # para que tenham acesso aos estados do usuário logado (st.session_state.logged_in_user)
    # e para que não sejam redefinidas desnecessariamente.

    def render_tab_all_questions():
        st.header("Prática: todas as perguntas")
        
        current_practice_cards_tab1 = st.session_state.ordered_cards_for_session 
        
        available_materias_tab1 = sorted(list(set([card["materia"] for card in current_practice_cards_tab1]))) if current_practice_cards_tab1 else []
        selected_materia_tab1 = st.selectbox("Filtrar por Matéria:", ["Todas"] + available_materias_tab1, key="filter_materia_tab1")

        filtered_cards_tab1 = current_practice_cards_tab1
        if selected_materia_tab1 != "Todas":
            filtered_cards_tab1 = [card for card in filtered_cards_tab1 if card["materia"] == selected_materia_tab1]

        available_assuntos_tab1 = sorted(list(set([card["assunto"] for card in filtered_cards_tab1]))) if filtered_cards_tab1 else []
        selected_assunto_tab1 = st.selectbox("Filtrar por Assunto:", ["Todos"] + available_assuntos_tab1, key="filter_assunto_tab1")

        if selected_assunto_tab1 != "Todos":
            filtered_cards_tab1 = [card for card in filtered_cards_tab1 if card["assunto"] == selected_assunto_tab1]

        if not filtered_cards_tab1:
            st.info("Nenhum cartão encontrado com os filtros selecionados. Altere os filtros ou adicione novos cartões.")
            return

        if st.session_state.current_card_index >= len(filtered_cards_tab1):
            st.session_state.current_card_index = 0

        current_card_tab1 = filtered_cards_tab1[st.session_state.current_card_index]

        st.subheader(f"Pergunta ({st.session_state.current_card_index + 1}/{len(filtered_cards_tab1)}):")
        st.info(current_card_tab1["pergunta"])

        user_answer_tab1 = st.text_area("Sua Resposta:",
                                    height=200,
                                    key=f"user_answer_input_tab1_{st.session_state.current_card_index}")

        if st.button("Verificar Resposta", key="check_response_btn_tab1"):
            if user_answer_tab1.strip():
                with st.spinner("Analisando com Gemini..."):
                    # Passa a pergunta também para o Gemini
                    full_feedback_text_tab1 = comparar_respostas_com_gemini(current_card_tab1["pergunta"], user_answer_tab1, current_card_tab1["resposta_esperada"]) 
                    parsed_feedback_tab1 = parse_feedback_sections(full_feedback_text_tab1)
                    
                    st.session_state.last_gemini_feedback_display_parsed = parsed_feedback_tab1
                    st.session_state.last_gemini_feedback_question = current_card_tab1["pergunta"]
                    st.session_state.last_gemini_expected_answer = current_card_tab1["resposta_esperada"]
                
                stored_score_tab1 = None
                if parsed_feedback_tab1.get('score'):
                    score_match_tab1 = re.search(r"(\d+)", parsed_feedback_tab1['score'])
                    if score_match_tab1:
                        try:
                            stored_score_tab1 = int(score_match_tab1.group(1))
                        except ValueError:
                            pass 
                lacunas_stored_tab1 = parsed_feedback_tab1.get('content_gaps')

                st.session_state.feedback_history.append({
                    "materia": current_card_tab1["materia"],
                    "assunto": current_card_tab1["assunto"],
                    "pergunta": current_card_tab1["pergunta"],
                    "nota_sentido": stored_score_tab1,
                    "lacunas_conteudo": lacunas_stored_tab1,
                    "timestamp": datetime.datetime.now().isoformat()
                })
                salvar_historico_feedback(st.session_state.feedback_history, st.session_state.logged_in_user)

                st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user) 
                
                difficult_cards_updated = []
                last_scores_for_difficult = {}
                for entry in reversed(st.session_state.feedback_history):
                    card_id_entry = (entry["pergunta"], entry["materia"], entry["assunto"])
                    if card_id_entry not in last_scores_for_difficult:
                        last_scores_for_difficult[card_id_entry] = entry.get("nota_sentido")

                for card_item in st.session_state.user_cartoes: 
                    card_id_item = (card_item["pergunta"], card_item["materia"], card_item["assunto"])
                    if card_id_item in last_scores_for_difficult and last_scores_for_difficult[card_id_item] is not None and last_scores_for_difficult[card_id_item] < 80:
                        difficult_cards_updated.append(card_item)
                st.session_state.difficult_cards_for_session = difficult_cards_updated
            else:
                st.warning("Por favor, digite sua resposta antes de verificar.")

        if (st.session_state.last_gemini_feedback_display_parsed is not None and
            st.session_state.last_gemini_feedback_question == current_card_tab1["pergunta"]):
            
            parsed_feedback_to_display = st.session_state.last_gemini_feedback_display_parsed
            st.subheader("Feedback do Gemini:")
            if "error" in parsed_feedback_to_display:
                st.warning("Erro ao formatar feedback. Exibindo como texto bruto.")
                st.write(parsed_feedback_to_display["raw_feedback"])
            else:
                st.markdown(f"**Pontuação de Sentido:** {parsed_feedback_to_display.get('score', 'N/A')}")
                st.markdown(f"**Avaliação Principal do Sentido:** {parsed_feedback_to_display.get('meaning_eval', 'N/A')}")
                st.markdown(f"**Lacunas de Conteúdo:** {parsed_feedback_to_display.get('content_gaps', 'N/A')}")
                st.markdown(f"**Erros Gramaticais/Ortográficos:** {parsed_feedback_to_display.get('grammar_errors', 'N/A')}")
                st.markdown(f"**Sugestões Rápidas de Melhoria:** {parsed_feedback_to_display.get('suggestions', 'N/A')}")

            st.subheader("Resposta Esperada:")
            st.success(current_card_tab1["resposta_esperada"])
        
        elif st.button("Revelar Resposta Esperada", key="reveal_btn_tab1"):
            st.session_state.show_expected_answer = True
            st.session_state.last_gemini_feedback_display_parsed = None
            
        if st.session_state.show_expected_answer:
            st.subheader("Resposta Esperada:")
            st.success(current_card_tab1["resposta_esperada"])

        nav_col1_tab1, nav_col2_tab1, nav_col3_tab1, nav_col4_tab1 = st.columns(4)
        with nav_col1_tab1:
            if st.button("Primeiro", key="first_card_btn_tab1"):
                st.session_state.current_card_index = 0
                st.session_state.show_expected_answer = False
                st.session_state.last_gemini_feedback_display_parsed = None
                st.rerun()
        with nav_col2_tab1:
            if st.button("Anterior", key="prev_card_btn_tab1"):
                if st.session_state.current_card_index > 0:
                    st.session_state.current_card_index -= 1
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()
                else:
                    st.info("Você está no primeiro cartão.")
        with nav_col3_tab1:
            if st.button("Próximo", key="next_card_btn_tab1"):
                if st.session_state.current_card_index < len(filtered_cards_tab1) - 1:
                    st.session_state.current_card_index += 1
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()
                else:
                    st.info("Você está no último cartão.")
        with nav_col4_tab1:
            if st.button("Último", key="last_card_btn_tab1"):
                st.session_state.current_card_index = len(filtered_cards_tab1) - 1
                st.session_state.show_expected_answer = False
                st.session_state.last_gemini_feedback_display_parsed = None
                st.rerun()


    def render_tab_manage_cards():
        st.header("Gerenciar Cartões")
        
        st.subheader("Adicionar Novo Cartão")
        with st.form("add_card_form"): 
            nova_materia = st.text_input("Matéria:",
                                         value=st.session_state.last_materia_input,
                                         key="new_materia_input")
            nova_assunto = st.text_input("Assunto:",
                                         value=st.session_state.last_assunto_input,
                                         key="new_assunto_input")
            
            nova_pergunta = st.text_area("Nova Pergunta:",
                                         height=200,
                                         key=f"new_q_input_{st.session_state.add_card_form_key_suffix}")
            nova_resposta = st.text_area("Nova Resposta Esperada:",
                                         height=200,
                                         key=f"new_a_input_{st.session_state.add_card_form_key_suffix}")
            
            submitted = st.form_submit_button("Adicionar Cartão")
            if submitted:
                if nova_materia.strip() and nova_assunto.strip() and nova_pergunta.strip() and nova_resposta.strip():
                    new_card_data = { # Dados do novo cartão sem doc_id ainda
                        "materia": nova_materia.strip(),
                        "assunto": nova_assunto.strip(),
                        "pergunta": nova_pergunta.strip(),
                        "resposta_esperada": nova_resposta.strip()
                    }
                    # Adiciona o cartão ao Firestore e pega o doc_id gerado
                    new_doc_id = adicionar_cartao_firestore(new_card_data, st.session_state.logged_in_user)
                    
                    if new_doc_id: # Se o cartão foi adicionado com sucesso
                        new_card_data['doc_id'] = new_doc_id # Adiciona o doc_id à cópia em memória
                        st.session_state.user_cartoes.append(new_card_data) # Adiciona à lista em memória
                        
                        st.session_state.last_materia_input = nova_materia.strip()
                        st.session_state.last_assunto_input = nova_assunto.strip()
                        st.session_state.add_card_form_key_suffix += 1
                        
                        # --- ATUALIZAÇÃO DA ORDEM E LISTA DE DIFÍCEIS APÓS ADIÇÃO/EDIÇÃO/EXCLUSÃO ---
                        st.session_state.user_cartoes = carregar_cartoes(st.session_state.logged_in_user) # Recarrega os cartões mais recentes
                        st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user) # Recarrega o histórico
                        
                        # Recalcula ordered_cards_for_session
                        card_latest_scores_recalc = {}
                        for entry in reversed(st.session_state.feedback_history):
                            card_id = (entry["pergunta"], entry["materia"], entry["assunto"])
                            if card_id not in card_latest_scores_recalc:
                                card_latest_scores_recalc[card_id] = entry.get("nota_sentido")
                        cards_for_ordering_recalc = []
                        for card in st.session_state.user_cartoes:
                            card_id = (card["pergunta"], card["materia"], card["assunto"])
                            score_to_order = card_latest_scores_recalc.get(card_id, -1)
                            cards_for_ordering_recalc.append((card, score_to_order))
                        st.session_state.ordered_cards_for_session = [card_obj for card_obj, _ in sorted(cards_for_ordering_recalc, key=lambda x: x[1])]

                        # Recalcula difficult_cards_for_session
                        difficult_cards_updated_recalc = []
                        for card in st.session_state.user_cartoes:
                            card_id = (card["pergunta"], card["materia"], card["assunto"])
                            if card_id in card_latest_scores_recalc and card_latest_scores_recalc[card_id] is not None and card_latest_scores_recalc[card_id] < 80:
                                difficult_cards_updated_recalc.append(card)
                        st.session_state.difficult_cards_for_session = difficult_cards_updated_recalc
                        # --- FIM DA ATUALIZAÇÃO ---

                        st.rerun()
                else:
                    st.warning("Por favor, preencha todos os campos para adicionar um cartão.")

        st.subheader("Cartões Existentes")
        available_materias_manage = sorted(list(set([card["materia"] for card in st.session_state.user_cartoes]))) if st.session_state.user_cartoes else []
        selected_materia_manage = st.selectbox("Filtrar por Matéria:", ["Todas"] + available_materias_manage, key="filter_materia_manage")

        displayed_cards = st.session_state.user_cartoes
        if selected_materia_manage != "Todas":
            displayed_cards = [card for card in displayed_cards if card["materia"] == selected_materia_manage]
        
        available_assuntos_manage = sorted(list(set([card["assunto"] for card in displayed_cards]))) if displayed_cards else []
        selected_assunto_manage = st.selectbox("Filtrar por Assunto:", ["Todos"] + available_assuntos_manage, key="filter_assunto_manage")

        if selected_assunto_manage != "Todos":
            displayed_cards = [card for card in displayed_cards if card["assunto"] == selected_assunto_manage]

        if not displayed_cards: # Tratamento para caso sem cartões
            if st.session_state.user_cartoes:
                st.info("Nenhum cartão encontrado com os filtros selecionados. Altere os filtros.")
            else:
                st.info("Nenhum cartão adicionado ainda. Use o formulário acima para criar seu primeiro cartão.")
            return 

        for i, card in enumerate(displayed_cards):
            # Para edição/exclusão, precisamos do doc_id do Firestore
            # Assumimos que o card já tem 'doc_id' por causa de carregar_cartoes
            card_doc_id = card.get('doc_id') 

            with st.expander(f"Cartão ({card.get('doc_id', 'Sem ID')[:6]}...) {card['materia']} - {card['assunto']}: {card['pergunta'][:50]}..."): # Mostra o ID do doc
                st.write("**Matéria:**", card["materia"])
                st.write("**Assunto:**", card["assunto"])
                st.write("**Pergunta:**", card["pergunta"])
                st.write("**Resposta Esperada:**", card["resposta_esperada"])

                col_edit, col_delete = st.columns(2)
                with col_edit:
                    # Botão Editar dentro do loop
                    if st.button(f"Editar", key=f"edit_card_btn_{card_doc_id}"): # Key única
                        st.session_state.edit_index_doc_id = card_doc_id # Armazena o doc_id do cartão a ser editado
                        # Carrega os dados do cartão para os inputs do formulário de edição
                        st.session_state.edit_materia = card["materia"]
                        st.session_state.edit_assunto = card["assunto"]
                        st.session_state.edit_pergunta = card["pergunta"]
                        st.session_state.edit_resposta = card["resposta_esperada"]
                        st.rerun()

                with col_delete:
                    if st.button(f"Excluir", key=f"delete_card_{card_doc_id}"): # Usa doc_id para key
                        # Exclui do Firestore
                        if excluir_cartao_firestore(card_doc_id, st.session_state.logged_in_user):
                            # Remove da lista em memória
                            st.session_state.user_cartoes = [c for c in st.session_state.user_cartoes if c.get('doc_id') != card_doc_id]
                        
                            # --- ATUALIZAÇÃO DA ORDEM E LISTA DE DIFÍCEIS APÓS EXCLUSÃO ---
                            st.session_state.user_cartoes = carregar_cartoes(st.session_state.logged_in_user) # Recarrega os cartões mais recentes
                            st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user) # Recarrega o histórico
                            
                            # Recalcula ordered_cards_for_session
                            card_latest_scores_recalc = {}
                            for entry in reversed(st.session_state.feedback_history):
                                card_id = (entry["pergunta"], entry["materia"], entry["assunto"])
                                if card_id not in card_latest_scores_recalc:
                                    card_latest_scores_recalc[card_id] = entry.get("nota_sentido")
                            cards_for_ordering_recalc = []
                            for card in st.session_state.user_cartoes:
                                card_id = (card["pergunta"], card["materia"], card["assunto"])
                                score_to_order = card_latest_scores_recalc.get(card_id, -1)
                                cards_for_ordering_recalc.append((card, score_to_order))
                            st.session_state.ordered_cards_for_session = [card_obj for card_obj, _ in sorted(cards_for_ordering_recalc, key=lambda x: x[1])]

                            # Recalcula difficult_cards_for_session
                            difficult_cards_updated_recalc = []
                            for card in st.session_state.user_cartoes:
                                card_id = (card["pergunta"], card["materia"], card["assunto"])
                                if card_id in card_latest_scores_recalc and card_latest_scores_recalc[card_id] is not None and card_latest_scores_recalc[card_id] < 80:
                                    difficult_cards_updated_recalc.append(card)
                            st.session_state.difficult_cards_for_session = difficult_cards_updated_recalc
                            # --- FIM DA ATUALIZAÇÃO ---

                            if st.session_state.current_card_index >= len(st.session_state.user_cartoes):
                                st.session_state.current_card_index = 0
                            st.rerun()
                st.markdown("---")

        # --- Formulário de Edição (FORA DO LOOP de exibição de cartões) ---
        # Este formulário só é renderizado se st.session_state.edit_index_doc_id não for None
        if 'edit_index_doc_id' in st.session_state and st.session_state.edit_index_doc_id is not None: 
            st.subheader(f"Editar Cartão (ID: {st.session_state.edit_index_doc_id[:6]}...)")
            
            # A CHAVE DO FORMULÁRIO É AGORA ÚNICA POR MEIO DO doc_id
            with st.form(key=f"edit_card_form_for_{st.session_state.edit_index_doc_id}"): # <-- CHAVE AGORA É DINÂMICA
                edited_materia = st.text_input("Matéria:", value=st.session_state.edit_materia, key="edit_m_input")
                edited_assunto = st.text_input("Assunto:", value=st.session_state.edit_assunto, key="edit_a_input")
                edited_pergunta = st.text_area("Pergunta:", value=st.session_state.edit_pergunta, height=200, key="edit_q_input")
                edited_resposta = st.text_area("Resposta Esperada:", value=st.session_state.edit_resposta, height=200, key="edit_ans_input")
                col_save, col_cancel = st.columns(2)
                with col_save:
                    edited_submitted = st.form_submit_button("Salvar Edição")
                with col_cancel:
                    cancel_edit = st.form_submit_button("Cancelar Edição")

                if edited_submitted:
                    if edited_materia.strip() and edited_assunto.strip() and edited_pergunta.strip() and edited_resposta.strip():
                        updated_card_data = { # Dados atualizados para enviar ao Firestore
                            "materia": edited_materia.strip(),
                            "assunto": edited_assunto.strip(),
                            "pergunta": edited_pergunta.strip(),
                            "resposta_esperada": edited_resposta.strip()
                        }
                        # Atualiza no Firestore usando o doc_id
                        if atualizar_cartao_firestore(st.session_state.edit_index_doc_id, updated_card_data, st.session_state.logged_in_user):
                            # Atualiza na lista em memória
                            for i, card in enumerate(st.session_state.user_cartoes):
                                if card.get('doc_id') == st.session_state.edit_index_doc_id:
                                    st.session_state.user_cartoes[i].update(updated_card_data)
                                    break
                        
                            # --- ATUALIZAÇÃO DA ORDEM E LISTA DE DIFÍCEIS APÓS EDIÇÃO ---
                            st.session_state.user_cartoes = carregar_cartoes(st.session_state.logged_in_user) # Recarrega os cartões mais recentes
                            st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user) # Recarrega o histórico
                            
                            # Recalcula ordered_cards_for_session
                            card_latest_scores_recalc = {}
                            for entry in reversed(st.session_state.feedback_history):
                                card_id = (entry["pergunta"], entry["materia"], entry["assunto"])
                                if card_id not in card_latest_scores_recalc:
                                    card_latest_scores_recalc[card_id] = entry.get("nota_sentido")
                            cards_for_ordering_recalc = []
                            for card in st.session_state.user_cartoes:
                                card_id = (card["pergunta"], card["materia"], card["assunto"])
                                score_to_order = card_latest_scores_recalc.get(card_id, -1)
                                cards_for_ordering_recalc.append((card, score_to_order))
                            st.session_state.ordered_cards_for_session = [card_obj for card_obj, _ in sorted(cards_for_ordering_recalc, key=lambda x: x[1])]

                            # Recalcula difficult_cards_for_session
                            difficult_cards_updated_recalc = []
                            for card in st.session_state.user_cartoes:
                                card_id = (card["pergunta"], card["materia"], card["assunto"])
                                if card_id in card_latest_scores_recalc and card_latest_scores_recalc[card_id] is not None and card_latest_scores_recalc[card_id] < 80:
                                    difficult_cards_updated_recalc.append(card)
                            st.session_state.difficult_cards_for_session = difficult_cards_updated_recalc
                            # --- FIM DA ATUALIZAÇÃO ---

                            st.session_state.edit_index_doc_id = None # Limpa o estado de edição
                            st.rerun()
                        else:
                            st.warning("Por favor, preencha todos os campos para salvar a edição.")
                    elif cancel_edit:
                        st.session_state.edit_index_doc_id = None
                        st.rerun()


    def render_tab_metrics():
        st.header("Métricas de Desempenho")
        st.write("Aqui você pode acompanhar seu histórico de respostas e o feedback do Gemini.")

        available_materias_metrics = sorted(list(set([entry["materia"] for entry in st.session_state.feedback_history]))) if st.session_state.feedback_history else []
        selected_materia_metrics = st.selectbox("Filtrar Histórico por Matéria:", ["Todas"] + available_materias_metrics, key="filter_materia_metrics")

        filtered_history = st.session_state.feedback_history
        if selected_materia_metrics != "Todas":
            filtered_history = [entry for entry in filtered_history if entry["materia"] == selected_materia_metrics]
        
        available_assuntos_metrics = sorted(list(set([entry["assunto"] for entry in filtered_history]))) if filtered_history else []
        selected_assunto_metrics = st.selectbox("Filtrar Histórico por Assunto:", ["Todos"] + available_assuntos_metrics, key="filter_assunto_metrics")

        if selected_assunto_metrics != "Todos":
            filtered_history = [entry for entry in filtered_history if entry["assunto"] == selected_assunto_metrics]

        if not filtered_history:
            st.info("Nenhuma resposta foi avaliada com os filtros selecionados. Comece a praticar na aba 'Todas as Perguntas'!")
            return 
            
        st.subheader("Resumo dos Feedbacks:")
        
        total_pontuacao = 0
        pontuacoes_validas = 0

        for entry in filtered_history:
            if entry.get("nota_sentido") is not None:
                total_pontuacao += entry["nota_sentido"]
                pontuacoes_validas += 1

        total_feedbacks = len(filtered_history)

        st.write(f"**Total de Respostas Avaliadas (com filtros):** {total_feedbacks}")
        if pontuacoes_validas > 0:
            st.markdown(f"**Pontuação Média de Sentido (com filtros):** **{total_pontuacao / pontuacoes_validas:.1f}%**")
        else:
            st.markdown(f"**Pontuação Média de Sentido (com filtros):** N/A (sem pontuações registradas)")

        st.subheader("Histórico Detalhado:")
        if st.button("Limpar Histórico de Desempenho", type="secondary"):
            st.session_state.feedback_history = []
            salvar_historico_feedback(st.session_state.feedback_history, st.session_state.logged_in_user)
            st.rerun()

        for i, entry in enumerate(reversed(filtered_history)):
            st.markdown(f"**--- Resposta {len(filtered_history) - i} ({entry['timestamp'].split('T')[0]}) ---**")
            st.write(f"**Matéria:** {entry['materia']}")
            st.write(f"**Assunto:** {entry['assunto']}")
            st.write(f"**Pergunta:** {entry['pergunta']}")
            
            st.markdown(f"**Nota de Sentido:** {entry.get('nota_sentido', 'N/A')}%")
            if entry.get('lacunas_conteudo'):
                st.markdown(f"**Lacunas de Conteúdo:** {entry['lacunas_conteudo']}")
            else:
                st.markdown("**Lacunas de Conteúdo:** Nenhuma lacuna significativa.")
            
            st.markdown("---")


    def render_tab_difficult_questions():
        st.header("Prática: perguntas mais difíceis")

        current_practice_cards_difficult = st.session_state.difficult_cards_for_session
        
        available_materias_difficult = sorted(list(set([card["materia"] for card in current_practice_cards_difficult]))) if current_practice_cards_difficult else []
        selected_materia_difficult = st.selectbox("Filtrar por Matéria:", ["Todas"] + available_materias_difficult, key="filter_materia_difficult")

        filtered_cards_difficult = current_practice_cards_difficult
        if selected_materia_difficult != "Todas":
            filtered_cards_difficult = [card for card in filtered_cards_difficult if card["materia"] == selected_materia_difficult]

        available_assuntos_difficult = sorted(list(set([card["assunto"] for card in filtered_cards_difficult]))) if filtered_cards_difficult else []
        selected_assunto_difficult = st.selectbox("Filtrar por Assunto:", ["Todos"] + available_assuntos_difficult, key="filter_assunto_difficult")

        if selected_assunto_difficult != "Todos":
            filtered_cards_difficult = [card for card in filtered_cards_difficult if card["assunto"] == selected_assunto_difficult]

        if not filtered_cards_difficult: # Tratamento para caso sem cartões
            st.info("Parabéns! Não há perguntas classificadas como 'difíceis' com os filtros selecionados, ou elas ainda não foram respondidas e pontuadas abaixo de 80%.")
            return # Sai da função se não há cartões para exibir

        if st.session_state.current_card_index_difficult >= len(filtered_cards_difficult):
            st.session_state.current_card_index_difficult = 0 # Reseta se o índice for inválido

        current_card_difficult = filtered_cards_difficult[st.session_state.current_card_index_difficult]

        st.subheader(f"Pergunta ({st.session_state.current_card_index_difficult + 1}/{len(filtered_cards_difficult)}):")
        st.info(current_card_difficult["pergunta"])

        user_answer_difficult = st.text_area("Sua Resposta:",
                                    height=150,
                                    key=f"user_answer_input_difficult_{st.session_state.current_card_index_difficult}")

        if st.button("Verificar Resposta", key="check_response_btn_difficult"):
            if user_answer_difficult.strip():
                with st.spinner("Analisando com Gemini..."):
                    # Passa a pergunta também para o Gemini
                    full_feedback_text_difficult = comparar_respostas_com_gemini(current_card_difficult["pergunta"], user_answer_difficult, current_card_difficult["resposta_esperada"]) 
                    parsed_feedback_difficult = parse_feedback_sections(full_feedback_text_difficult)
                    
                    st.session_state.last_gemini_feedback_display_parsed = parsed_feedback_difficult # Usa o mesmo para exibir
                    st.session_state.last_gemini_feedback_question = current_card_difficult["pergunta"]
                    st.session_state.last_gemini_expected_answer = current_card_difficult["resposta_esperada"]
                
                stored_score_difficult = None
                if parsed_feedback_difficult.get('score'):
                    score_match_difficult = re.search(r"(\d+)", parsed_feedback_difficult['score'])
                    if score_match_difficult:
                        try:
                            stored_score_difficult = int(score_match_difficult.group(1))
                        except ValueError:
                            pass 
                lacunas_stored_difficult = parsed_feedback_difficult.get('content_gaps')

                st.session_state.feedback_history.append({
                    "materia": current_card_difficult["materia"],
                    "assunto": current_card_difficult["assunto"],
                    "pergunta": current_card_difficult["pergunta"],
                    "nota_sentido": stored_score_difficult,
                    "lacunas_conteudo": lacunas_stored_difficult,
                    "timestamp": datetime.datetime.now().isoformat()
                })
                salvar_historico_feedback(st.session_state.feedback_history, st.session_state.logged_in_user)

                # NÃO ATUALIZA A LISTA DE DIFÍCEIS AQUI. APENAS NO RESPOSTA NA ABA "TODAS AS PERGUNTAS" OU NO LOGIN.
                # Isso garante o comportamento especificado de que responder aqui não altera a lista de difíceis.
            else:
                st.warning("Por favor, digite sua resposta antes de verificar.")

        if (st.session_state.last_gemini_feedback_display_parsed is not None and
            st.session_state.last_gemini_feedback_question == current_card_difficult["pergunta"]):
            
            parsed_feedback_to_display = st.session_state.last_gemini_feedback_display_parsed
            st.subheader("Feedback do Gemini:")
            if "error" in parsed_feedback_to_display:
                st.warning("Erro ao formatar feedback. Exibindo como texto bruto.")
                st.write(parsed_feedback_to_display["raw_feedback"])
            else:
                st.markdown(f"**Pontuação de Sentido:** {parsed_feedback_to_display.get('score', 'N/A')}")
                st.markdown(f"**Avaliação Principal do Sentido:** {parsed_feedback_to_display.get('meaning_eval', 'N/A')}")
                st.markdown(f"**Lacunas de Conteúdo:** {parsed_feedback_to_display.get('content_gaps', 'N/A')}")
                st.markdown(f"**Erros Gramaticais/Ortográficos:** {parsed_feedback_to_display.get('grammar_errors', 'N/A')}")
                st.markdown(f"**Sugestões Rápidas de Melhoria:** {parsed_feedback_to_display.get('suggestions', 'N/A')}")

            st.subheader("Resposta Esperada:")
            st.success(current_card_difficult["resposta_esperada"])
        
        elif st.button("Revelar Resposta Esperada", key="reveal_btn_difficult"):
            st.session_state.show_expected_answer = True
            st.session_state.last_gemini_feedback_display_parsed = None
            
        if st.session_state.show_expected_answer:
            st.subheader("Resposta Esperada:")
            st.success(current_card_difficult["resposta_esperada"])

        nav_col1_d, nav_col2_d, nav_col3_d, nav_col4_d = st.columns(4)
        with nav_col1_d:
            if st.button("Primeiro", key="first_card_btn_difficult"):
                st.session_state.current_card_index_difficult = 0
                st.session_state.show_expected_answer = False
                st.session_state.last_gemini_feedback_display_parsed = None
                st.rerun()
            with nav_col2_d:
                if st.button("Anterior", key="prev_card_btn_difficult"):
                    if st.session_state.current_card_index_difficult > 0:
                        st.session_state.current_card_index_difficult -= 1
                        st.session_state.show_expected_answer = False
                        st.session_state.last_gemini_feedback_display_parsed = None
                        st.rerun()
                    else:
                        st.info("Você está no primeiro cartão difícil.")
            with nav_col3_d:
                if st.button("Próximo", key="next_card_btn_difficult"):
                    if st.session_state.current_card_index_difficult < len(filtered_cards_difficult) - 1:
                        st.session_state.current_card_index_difficult += 1
                        st.session_state.show_expected_answer = False
                        st.session_state.last_gemini_feedback_display_parsed = None
                        st.rerun()
                    else:
                        st.info("Você está no último cartão difícil.")
            with nav_col4_d:
                if st.button("Último", key="last_card_btn_difficult"):
                    st.session_state.current_card_index_difficult = len(filtered_cards_difficult) - 1
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()


    def render_tab_manage_users(): # NOVA FUNÇÃO PARA GERENCIAR USUÁRIOS
        st.header("Gerenciar Usuários")
        if st.session_state.logged_in_user != ADMIN_USERNAME:
            st.warning("Você não tem permissão para gerenciar usuários.")
            return

        users_data = carregar_usuarios()

        st.subheader("Criar Nova Conta de Usuário")
        with st.form("create_user_form"):
            new_username = st.text_input("Nome de Usuário:", key="create_user_input")
            new_password = st.text_input("Senha:", type="password", key="create_password_input")
            confirm_new_password = st.text_input("Confirme a Senha:", type="password", key="create_confirm_password_input")
            if st.form_submit_button("Criar Usuário"):
                if new_username.strip() and new_password.strip() and new_password == confirm_new_password:
                    if new_username.strip() == ADMIN_USERNAME:
                        st.error(f"O nome de usuário '{ADMIN_USERNAME}' é reservado.")
                    elif new_username.strip() in users_data:
                        st.error(f"O nome de usuário '{new_username.strip()}' já existe.")
                    else:
                        users_data[new_username.strip()] = hash_password(new_password.strip())
                        salvar_usuarios(users_data)
                        st.success(f"Usuário '{new_username.strip()}' criado com sucesso!")
                        st.rerun()
                else:
                    st.error("Preencha todos os campos, as senhas devem coincidir e não podem ser vazias.")

        st.subheader("Alterar Senha ou Excluir Usuário Existente")
        # Mostra a lista de usuários para gerenciar, excluindo o próprio admin
        users_list_for_manage = [u for u in users_data.keys() if u != ADMIN_USERNAME]

        if users_list_for_manage: # Só mostra o seletor se houver outros usuários
            selected_user = st.selectbox("Selecione o Usuário:", users_list_for_manage, key="select_user_to_manage") 
            
            if selected_user: # Garante que um usuário foi selecionado
                st.write(f"Gerenciando usuário: **{selected_user}**")
                
                # Formulário para alterar senha
                with st.form(f"change_password_form_{selected_user}"): # <-- CHAVE DINÂMICA AQUI
                    new_pass_change = st.text_input("Nova Senha:", type="password", key=f"new_pass_change_{selected_user}")
                    confirm_pass_change = st.text_input("Confirme Nova Senha:", type="password", key=f"confirm_pass_change_{selected_user}")
                    if st.form_submit_button("Alterar Senha"):
                        if new_pass_change.strip() and new_pass_change == confirm_pass_change:
                            users_data[selected_user] = hash_password(new_pass_change.strip())
                            salvar_usuarios(users_data)
                            st.success(f"Senha do usuário '{selected_user}' alterada com sucesso!")
                            st.rerun()
                        else:
                            st.error("As senhas não coincidem ou estão vazias.")
                
                # Botão para excluir usuário
                if st.button(f"Excluir Usuário '{selected_user}'", key=f"delete_user_btn_{selected_user}", type="secondary"):
                    # Pedido de confirmação para exclusão
                    st.warning(f"Tem certeza que deseja excluir o usuário '{selected_user}'? Essa ação é irreversível e excluirá todos os seus cartões e histórico!", icon="⚠️")
                    confirm_delete = st.button("Confirmar Exclusão (irreversível)", key=f"confirm_delete_user_{selected_user}")
                    if confirm_delete:
                        del users_data[selected_user]
                        salvar_usuarios(users_data)
                        
                        # Excluir a pasta de dados do usuário
                        user_data_path_to_delete = get_user_data_path(selected_user)
                        if os.path.exists(user_data_path_to_delete):
                            import shutil
                            shutil.rmtree(user_data_path_to_delete) # Remove a pasta e todo o seu conteúdo
                        
                        st.success(f"Usuário '{selected_user}' excluído com sucesso.")
                        st.rerun()
        else:
            st.info("Nenhum usuário registrado além do administrador.")


    # --- Lógica de Renderização das Abas (Chamadas de Função) ---
    # selected_tab é obtido do st.sidebar.radio. Apenas a aba selecionada é renderizada.
    if selected_tab == "Todas as Perguntas":
        render_tab_all_questions()
    elif selected_tab == "Gerenciar Cartões":
        render_tab_manage_cards()
    elif selected_tab == "Métricas de Desempenho":
        render_tab_metrics()
    elif selected_tab == "Perguntas Mais Difíceis":
        render_tab_difficult_questions()
    elif selected_tab == "Gerenciar Usuários" and st.session_state.logged_in_user == ADMIN_USERNAME:
        render_tab_manage_users()
