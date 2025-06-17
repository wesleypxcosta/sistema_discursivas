import os
import json
import google.generativeai as genai
import streamlit as st
import datetime
import re
import hashlib

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
        font-size: 1em; /* 1.1 vezes o tamanho padrão */
        line-height: 1.6; /* Espaçamento entre linhas */
    }

    /* Títulos do Streamlit */
    h1 {
        font-size: 2.2em !important; /* !important força a aplicação do estilo */
        color: #0E4D92; /* Um azul mais escuro para o título principal */
    }
    h2 {
        font-size: 1.8em !important;
        color: #1A5E95; /* Tom de azul ligeiramente mais claro */
    }
    h3 {
        font-size: 1.5em !important;
        color: #2F7DBF; /* Tom de azul ainda mais claro */
    }

    /* Personaliza o campo de input de texto (pergunta, resposta) */
    .stTextArea, .stTextInput {
        font-size: 1.05em !important;
        background-color: #f8f9fa; /* Fundo levemente cinza */
        border-radius: 5px;
        border: 1px solid #ced4da;
    }

    /* Estiliza os botões */
    .stButton > button {
        font-size: 1.1em !important;
        padding: 0.6em 1.2em; /* Preenchimento interno do botão */
        border-radius: 8px; /* Cantos mais arredondados */
        border: none;
        background-color: #4CAF50; /* Um verde bacana para botões primários */
        color: white;
        transition: background-color 0.3s ease; /* Efeito de transição suave */
    }
    .stButton > button:hover {
        background-color: #45a049; /* Verde um pouco mais escuro ao passar o mouse */
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

# --- Constantes para Nomes de Arquivo e Diretório Base ---
BASE_DATA_DIR = "data"
GLOBAL_CARDS_FILE = os.path.join(BASE_DATA_DIR, "global_cards.json")
FEEDBACK_HISTORY_FILENAME = "feedback_history.json"
USERS_FILE = os.path.join(BASE_DATA_DIR, "users.json")

# --- DEFINIÇÃO DO ADMINISTRADOR ---
ADMIN_USERNAME = "admin"

# --- Funções Auxiliares para Caminhos de Arquivo por Usuário (e Global) ---
def get_user_data_path(username):
    """Retorna o caminho do diretório de dados para um usuário específico."""
    user_dir = os.path.join(BASE_DATA_DIR, username)
    os.makedirs(user_dir, exist_ok=True) # Cria o diretório se não existir
    return user_dir

def get_feedback_history_file_path(username):
    """Retorna o caminho completo do arquivo de histórico para um usuário."""
    return os.path.join(get_user_data_path(username), FEEDBACK_HISTORY_FILENAME)

# --- Funções de Manipulação de Cartões (Global) ---
def carregar_cartoes_globais():
    """
    Carrega as perguntas e respostas esperadas do arquivo global de cartões.
    """
    try:
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        with open(GLOBAL_CARDS_FILE, 'r', encoding='utf-8') as f:
            cartoes = json.load(f)
        return cartoes
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.error(f"Erro: O arquivo de cartões global '{GLOBAL_CARDS_FILE}' está mal formatado (JSON inválido).")
        return []

def salvar_cartoes_globais(cartoes_data):
    """
    Salva a lista de cartões no arquivo global de cartões.
    """
    try:
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        with open(GLOBAL_CARDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cartoes_data, f, indent=4, ensure_ascii=False)
        st.success(f"Cartões globais salvos com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar cartões globais: {e}")

# Funções de histórico de feedback (com username)
def carregar_historico_feedback(username):
    """
    Carrega o histórico de feedback de um arquivo JSON para um usuário específico.
    """
    caminho_arquivo = get_feedback_history_file_path(username)
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            historico = json.load(f)
        return historico
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.error(f"Erro: O arquivo de histórico de '{username}' está mal formatado (JSON inválido).")
        return []

def salvar_historico_feedback(historico_data, username):
    """
    Salva o histórico de feedback em um arquivo JSON para um usuário específico.
    """
    caminho_arquivo = get_feedback_history_file_path(username)
    try:
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(historico_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Erro ao salvar histórico de feedback de '{username}': {e}")

# --- Funções para Gerenciamento de Usuários e Senhas ---
def hash_password(password):
    """Gera o hash SHA256 de uma senha."""
    return hashlib.sha256(password.encode()).hexdigest()

def carregar_usuarios():
    """Carrega os usuários e seus hashes de senha do users.json."""
    try:
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        return users
    except FileNotFoundError:
        return {} # Retorna dicionário vazio se o arquivo não existe
    except json.JSONDecodeError:
        st.error(f"Erro: O arquivo de usuários '{USERS_FILE}' está mal formatado (JSON inválido).")
        return {}

def salvar_usuarios(users_data):
    """Salva os usuários e seus hashes de senha no users.json."""
    try:
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Erro ao salvar usuários: {e}")

# Garante que o usuário admin exista na primeira execução
def inicializar_admin():
    users = carregar_usuarios()
    if ADMIN_USERNAME not in users:
        st.sidebar.warning(f"O usuário administrador ('{ADMIN_USERNAME}') não existe. Por favor, crie-o agora.")
        with st.form("admin_creation_form"):
            admin_password = st.text_input(f"Defina a senha para '{ADMIN_USERNAME}':", type="password", key="admin_pass_init")
            confirm_admin_password = st.text_input("Confirme a senha:", type="password", key="admin_pass_confirm_init")
            if st.form_submit_button("Criar Usuário Administrador"):
                if admin_password == confirm_admin_password and admin_password.strip():
                    users[ADMIN_USERNAME] = hash_password(admin_password)
                    salvar_usuarios(users)
                    st.success(f"Usuário '{ADMIN_USERNAME}' criado com sucesso! Por favor, faça login.")
                    st.rerun()
                else:
                    st.error("As senhas não coincidem ou estão vazias. Tente novamente.")
        return False # Indica que a criação está emS andamento, não prossegue para o login
    return True # Indica que o admin existe e pode prosseguir para o login


# --- Função de Interação com o Gemini ---
def comparar_respostas_com_gemini(resposta_usuario, resposta_esperada):
    """
    Envia a resposta do usuário e a resposta esperada para o Gemini
    e pede para ele comparar o sentido, apontar erros gramaticais/grafia,
    sugerir modificações, dar uma pontuação e indicar lacunas de conteúdo.
    O feedback será sucinto.
    """
    if not resposta_usuario.strip() or not resposta_esperada.strip():
        return "Por favor, forneça ambas as respostas para comparação."

    prompt = f"""
    Sua tarefa é fornecer um feedback **sucinto e objetivo** para a 'Resposta do Usuário' em comparação com la 'Resposta Esperada'.
    A ideia é que o usuário ganhe agilidade no aprendizado, focando nos puntos esenciales.

    O feedback deve ser dividido en seções claras, sem rodeios.

    **Estrutura de Feedback Requerida:**

    **1. Pontuação de Sentido (0-100):**
    [Uma pontuação numérica de 0 a 100% baseada na similaridade de sentido com a Resposta Esperada. 100% = sentido idêntico e completo.]

    **2. Avaliação Principal do Sentido:**
    [Feedback qualitativo muito breve (ex: "Excelente.", "Bom, mas faltou X.", "Incompleto.", "Incorreto.").]

    **3. Lacunas de Conteúdo:**
    [Liste os pontos chave da Resposta Esperada que NÃO foram abordados ou foram abordados de forma insuficiente na Resposta do Usuário. Use bullet points sucintos. Se não houver lacunas, diga "Nenhuma lacuna significativa."]

    **4. Erros Gramaticais/Ortográficos:**
    [Liste os principais erros encontrados na 'Resposta do Usuário'. Formato: 'Palavra/Frase Incorreta' -> 'Sugestão de Correção'. Se não houver, diga "Nenhum erro encontrado."]

    **5. Sugestões Rápidas de Melhoria:**
    [Sugestões muito concisas para aprimorar a resposta em termos de clareza, concisão e correção, baseadas nos erros e lacunas. Use bullet points.]

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
# IMPORTANTES: Garante que as variáveis de sessão são inicializadas antes de serem usadas
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# Acesso global aos cartões (sempre carregado)
if 'global_cartoes' not in st.session_state:
    st.session_state.global_cartoes = carregar_cartoes_globais()

# Inicialização do histórico de feedback, mas só é carregado após login
if 'feedback_history' not in st.session_state:
    st.session_state.feedback_history = [] # Inicializa vazio, será carregado no login

if 'current_card_index' not in st.session_state:
    st.session_state.current_card_index = 0
if 'show_expected_answer' not in st.session_state:
    st.session_state.show_expected_answer = False

# Estado para armazenar o feedback completo do Gemini para exibição persistente
if 'last_gemini_feedback_display_parsed' not in st.session_state: # AGORA ARMAZENA O DICIONÁRIO PARSEADO
    st.session_state.last_gemini_feedback_display_parsed = None

# Estado para armazenar a pergunta do último feedback (para exibir junto ao feedback persistente)
if 'last_gemini_feedback_question' not in st.session_state:
    st.session_state.last_gemini_feedback_question = None

# Estado para armazenar a resposta esperada do último feedback (para exibir junto ao feedback persistente)
if 'last_gemini_expected_answer' not in st.session_state:
    st.session_state.last_gemini_expected_answer = None

# Estado para controlar o key dinâmico dos campos de Pergunta e Resposta para limpeza
if 'add_card_form_key_suffix' not in st.session_state:
    st.session_state.add_card_form_key_suffix = 0

# NOVO: Estados para persistir valores de Matéria e Assunto no formulário de adição
if 'last_materia_input' not in st.session_state:
    st.session_state.last_materia_input = ""
if 'last_assunto_input' not in st.session_state:
    st.session_state.last_assunto_input = ""

# Estado para armazenar a ordem de cartões reordenada para a sessão atual do usuário
if 'ordered_cards_for_session' not in st.session_state:
    st.session_state.ordered_cards_for_session = [] # Será preenchido no login

# Estado para armazenar a lista de cartões "difíceis" para a sessão atual do usuário
if 'difficult_cards_for_session' not in st.session_state:
    st.session_state.difficult_cards_for_session = []

# Estado para controlar o índice do cartão na aba "Perguntas Mais Difíceis"
if 'current_card_index_difficult' not in st.session_state:
    st.session_state.current_card_index_difficult = 0


# --- LÓGICA PRINCIPAL DO APP ---
# Se o usuário não estiver logado, exibe a tela de login
if st.session_state.logged_in_user is None:
    # Garante que o admin exista na primeira execução
    users = carregar_usuarios()
    if ADMIN_USERNAME not in users:
        st.sidebar.warning(f"O usuário administrador ('{ADMIN_USERNAME}') não existe. Por favor, crie-o agora.")
        with st.form("admin_creation_form"):
            admin_password = st.text_input(f"Defina a senha para '{ADMIN_USERNAME}':", type="password", key="admin_pass_init")
            confirm_admin_password = st.text_input("Confirme a senha:", type="password", key="admin_pass_confirm_init")
            if st.form_submit_button("Criar Usuário Administrador"):
                if admin_password == confirm_admin_password and admin_password.strip():
                    users[ADMIN_USERNAME] = hash_password(admin_password)
                    salvar_usuarios(users)
                    st.success(f"Usuário '{ADMIN_USERNAME}' criado com sucesso! Por favor, faça login.")
                    st.rerun()
                else:
                    st.error("As senhas não coincidem ou estão vazias. Tente novamente.")
        st.stop()


    st.title("Bem-vindo ao Sistema de Treino!")
    st.subheader("Por favor, faça login para continuar:")

    username_login = st.text_input("Nome de Usuário:", key="username_login_input_form")
    password_login = st.text_input("Senha:", type="password", key="password_login_input_form")
    
    col_login_btns_1, col_login_btns_2 = st.columns(2)

    with col_login_btns_1:
        if st.button("Entrar", key="login_button"):
            if username_login.strip() and password_login.strip():
                users_data = carregar_usuarios()
                if username_login.strip() in users_data and users_data[username_login.strip()] == hash_password(password_login.strip()):
                    st.session_state.logged_in_user = username_login.strip()
                    st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user)
                    
                    # --- Lógica de Reordenação da aba "Todas as Perguntas" (no Login) ---
                    # Calcula a última nota para cada cartão global para ordenação
                    card_latest_scores = {}
                    for entry in reversed(st.session_state.feedback_history):
                        card_id = (entry["pergunta"], entry["materia"], entry["assunto"])
                        if card_id not in card_latest_scores: # Pega apenas a primeira (última) ocorrência
                            card_latest_scores[card_id] = entry.get("nota_sentido")

                    cards_for_ordering = []
                    for card in st.session_state.global_cartoes:
                        card_id = (card["pergunta"], card["materia"], card["assunto"])
                        # Se o cartão tem uma nota, usa a última; senão, usa -1 para priorizar
                        score_to_order = card_latest_scores.get(card_id, -1) 
                        cards_for_ordering.append((card, score_to_order))

                    # Ordena: Menor nota primeiro (pior desempenho vem antes)
                    st.session_state.ordered_cards_for_session = [card_obj for card_obj, _ in sorted(cards_for_ordering, key=lambda x: x[1])]
                    # --- FIM DA REORDENAÇÃO DA ABA "TODAS AS PERGUNTAS" NO LOGIN ---

                    # --- Lógica para Identificar Perguntas Mais Difíceis (no Login) ---
                    difficult_cards = []
                    for card in st.session_state.global_cartoes:
                        card_id = (card["pergunta"], card["materia"], card["assunto"])
                        # Uma pergunta é difícil se foi respondida E a última nota foi < 80%
                        if card_id in card_latest_scores and card_latest_scores[card_id] is not None and card_latest_scores[card_id] < 80:
                            difficult_cards.append(card)
                    st.session_state.difficult_cards_for_session = difficult_cards
                    # --- FIM DA LÓGICA DE DIFÍCEIS NO LOGIN ---

                    # Resetar outros estados para o novo usuário
                    st.session_state.current_card_index = 0
                    st.session_state.current_card_index_difficult = 0 # Reseta o índice da aba difícil
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None # Limpa feedback anterior
                    st.rerun()
                else:
                    st.error("Nome de usuário ou senha incorretos.")
            else:
                st.warning("Por favor, digite nome de usuário e senha.")
    with col_login_btns_2:
        # Botão para criar novo usuário (não-admin)
        if st.button("Criar Nova Conta", key="create_account_button"):
            st.session_state.creating_new_account = True
            st.rerun()

    # Lógica de criação de nova conta (fora do formulário de login)
    if st.session_state.get('creating_new_account', False):
        st.subheader("Criar Nova Conta")
        with st.form("create_new_account_form"):
            new_username = st.text_input("Novo Nome de Usuário:", key="new_user_input")
            new_password = st.text_input("Nova Senha:", type="password", key="new_pass_input")
            confirm_new_password = st.text_input("Confirme a Senha:", type="password", key="confirm_new_pass_input")
            col_create, col_cancel_create = st.columns(2)
            with col_create:
                if st.form_submit_button("Registrar"):
                    if new_username.strip() and new_password.strip() and new_password == confirm_new_password:
                        users_data = carregar_usuarios()
                        if new_username.strip() == ADMIN_USERNAME:
                            st.error(f"O nome de usuário '{ADMIN_USERNAME}' é reservado para o administrador.")
                        elif new_username.strip() in users_data:
                            st.error(f"O nome de usuário '{new_username.strip()}' já existe.")
                        else:
                            users_data[new_username.strip()] = hash_password(new_password.strip())
                            salvar_usuarios(users_data)
                            st.success(f"Conta para '{new_username.strip()}' criada com sucesso! Por favor, faça login.")
                            st.session_state.creating_new_account = False
                            st.rerun()
                    else:
                        st.error("Preencha todos os campos, as senhas devem coincidir e não podem ser vazias.")
            with col_cancel_create:
                if st.form_submit_button("Cancelar"):
                    st.session_state.creating_new_account = False
                    st.rerun()

else: # Usuário logado
    # --- INTERFACE PRINCIPAL DO APLICATIVO ---
    st.title(f"Sistema de Treino para Provas Discursivas de {st.session_state.logged_in_user}")
    st.write("Bem-vindo! Este é o seu sistema de flashcards inteligente com feedback do Gemini!")

    # Botão de Logout
    if st.sidebar.button("Sair", key="logout_button"):
        st.session_state.logged_in_user = None
        st.session_state.feedback_history = []
        st.session_state.current_card_index = 0
        st.session_state.current_card_index_difficult = 0 # Reseta
        st.session_state.show_expected_answer = False
        st.session_state.last_gemini_feedback_display_parsed = None # Limpa feedback ao sair
        st.session_state.ordered_cards_for_session = [] # Limpa a ordem também
        st.session_state.difficult_cards_for_session = [] # Reseta também
        st.rerun()

    # Define quais abas serão exibidas e cria as referências para os blocos 'with'
    if st.session_state.logged_in_user == ADMIN_USERNAME:
        tab_names_list = ["Todas as Perguntas", "Gerenciar Cartões", "Métricas de Desempenho", "Perguntas Mais Difíceis"]
        tab1_comp, tab2_comp, tab3_comp, tab4_comp = st.tabs(tab_names_list)
    else:
        tab_names_list = ["Todas as Perguntas", "Métricas de Desempenho", "Perguntas Mais Difíceis"]
        tab1_comp, tab3_comp, tab4_comp = st.tabs(tab_names_list)
        tab2_comp = None # Garante que tab2_comp não seja usado se o usuário não for admin

    # --- Funções de Renderização de Conteúdo por Aba ---
    def render_tab_all_questions():
        st.header("Modo de Prática: Todas as Perguntas") # NOVO NOME
        
        # current_practice_cards PARA ABA 1: baseada na ordem definida no login
        current_practice_cards_tab1 = st.session_state.ordered_cards_for_session 
        
        # Seletores de Matéria e Assunto para Filtragem na Prática (aba 1)
        available_materias_tab1 = sorted(list(set([card["materia"] for card in current_practice_cards_tab1]))) if current_practice_cards_tab1 else []
        selected_materia_tab1 = st.selectbox("Filtrar por Matéria:", ["Todas"] + available_materias_tab1, key="filter_materia_tab1")

        filtered_cards_tab1 = current_practice_cards_tab1
        if selected_materia_tab1 != "Todas":
            filtered_cards_tab1 = [card for card in filtered_cards_tab1 if card["materia"] == selected_materia_tab1]

        available_assuntos_tab1 = sorted(list(set([card["assunto"] for card in filtered_cards_tab1]))) if filtered_cards_tab1 else []
        selected_assunto_tab1 = st.selectbox("Filtrar por Assunto:", ["Todos"] + available_assuntos_tab1, key="filter_assunto_tab1")

        if selected_assunto_tab1 != "Todos":
            filtered_cards_tab1 = [card for card in filtered_cards_tab1 if card["assunto"] == selected_assunto_tab1]

        # AQUI FOI ONDE O 'else' ESTAVA DANDO ERRO. Ele estava no nível do 'if filtered_cards_tab1:'.
        # Ao adicionar o 'return' no 'if not filtered_cards_tab1', o 'else' ficava "solto".
        # A forma correta é que, se não houver cartões, a função simplesmente retorna.
        # Caso contrário, o resto da função é executado.
        if not filtered_cards_tab1:
            st.info("Nenhum cartão encontrado com os filtros selecionados. Altere os filtros ou adicione novos cartões.")
            return # Sai da função se não há cartões para exibir

        # O restante do código da aba 1 (renderização do cartão, botões, feedback) segue aqui.
        if st.session_state.current_card_index >= len(filtered_cards_tab1):
            st.session_state.current_card_index = 0

        current_card_tab1 = filtered_cards_tab1[st.session_state.current_card_index]

        st.subheader(f"Pergunta ({st.session_state.current_card_index + 1}/{len(filtered_cards_tab1)}):")
        st.info(current_card_tab1["pergunta"])

        user_answer_tab1 = st.text_area("Sua Resposta:",
                                    height=150,
                                    key=f"user_answer_input_tab1_{st.session_state.current_card_index}")

        # Botão "Verificar Resposta com Gemini" (para aba 1)
        if st.button("Verificar Resposta com Gemini", key="check_response_btn_tab1"):
            if user_answer_tab1.strip():
                with st.spinner("Analisando com Gemini..."):
                    full_feedback_text_tab1 = comparar_respostas_com_gemini(user_answer_tab1, current_card_tab1["resposta_esperada"])
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

                st.session_state.feedback_history = carregar_historico_feedback(st.session_state.logged_in_user) # Recarrega para a atualização da lista de difíceis
                
                difficult_cards_updated = []
                last_scores_for_difficult = {}
                for entry in reversed(st.session_state.feedback_history):
                    card_id_entry = (entry["pergunta"], entry["materia"], entry["assunto"])
                    if card_id_entry not in last_scores_for_difficult:
                        last_scores_for_difficult[card_id_entry] = entry.get("nota_sentido")

                for card_item in st.session_state.global_cartoes:
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
            if st.button("Primeiro Cartão", key="first_card_btn_tab1"):
                st.session_state.current_card_index = 0
                st.session_state.show_expected_answer = False
                st.session_state.last_gemini_feedback_display_parsed = None
                st.rerun()
        with nav_col2_tab1:
            if st.button("Cartão Anterior", key="prev_card_btn_tab1"):
                if st.session_state.current_card_index > 0:
                    st.session_state.current_card_index -= 1
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()
                else:
                    st.info("Você está no primeiro cartão.")
        with nav_col3_tab1:
            if st.button("Próximo Cartão", key="next_card_btn_tab1"):
                if st.session_state.current_card_index < len(filtered_cards_tab1) - 1:
                    st.session_state.current_card_index += 1
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()
                else:
                    st.info("Você está no último cartão.")
        with nav_col4_tab1:
            if st.button("Último Cartão", key="last_card_btn_tab1"):
                st.session_state.current_card_index = len(filtered_cards_tab1) - 1
                st.session_state.show_expected_answer = False
                st.session_state.last_gemini_feedback_display_parsed = None
                st.rerun()

        # REMOVIDO: O bloco 'else' que estava causando o SyntaxError
        # A mensagem de "Nenhum cartão carregado" já é tratada por 'if not filtered_cards_tab1: return'

    def render_tab_manage_cards():
        st.header("Gerenciar Cartões")
        if st.session_state.logged_in_user != ADMIN_USERNAME:
            st.warning("Você não tem permissão para gerenciar cartões.")
            return # Sai da função se não for admin

        st.subheader("Adicionar Novo Cartão")
        with st.form("add_card_form"): 
            nova_materia = st.text_input("Matéria:",
                                         value=st.session_state.last_materia_input,
                                         key="new_materia_input")
            nova_assunto = st.text_input("Assunto:",
                                         value=st.session_state.last_assunto_input,
                                         key="new_assunto_input")
            
            nova_pergunta = st.text_area("Nova Pergunta:",
                                         height=100,
                                         key=f"new_q_input_{st.session_state.add_card_form_key_suffix}")
            nova_resposta = st.text_area("Nova Resposta Esperada:",
                                         height=100,
                                         key=f"new_a_input_{st.session_state.add_card_form_key_suffix}")
            
            submitted = st.form_submit_button("Adicionar Cartão")
            if submitted:
                if nova_materia.strip() and nova_assunto.strip() and nova_pergunta.strip() and nova_resposta.strip():
                    new_card = {
                        "materia": nova_materia.strip(),
                        "assunto": nova_assunto.strip(),
                        "pergunta": nova_pergunta.strip(),
                        "resposta_esperada": nova_resposta.strip()
                    }
                    st.session_state.global_cartoes.append(new_card)
                    salvar_cartoes_globais(st.session_state.global_cartoes) 
                    
                    st.session_state.last_materia_input = nova_materia.strip()
                    st.session_state.last_assunto_input = nova_assunto.strip()
                    st.session_state.add_card_form_key_suffix += 1
                    
                    st.rerun()
                else:
                    st.warning("Por favor, preencha todos os campos para adicionar um cartão.")

        st.subheader("Cartões Existentes")
        available_materias_manage = sorted(list(set([card["materia"] for card in st.session_state.global_cartoes]))) if st.session_state.global_cartoes else []
        selected_materia_manage = st.selectbox("Filtrar por Matéria:", ["Todas"] + available_materias_manage, key="filter_materia_manage")

        displayed_cards = st.session_state.global_cartoes
        if selected_materia_manage != "Todas":
            displayed_cards = [card for card in displayed_cards if card["materia"] == selected_materia_manage]
        
        available_assuntos_manage = sorted(list(set([card["assunto"] for card in displayed_cards]))) if displayed_cards else []
        selected_assunto_manage = st.selectbox("Filtrar por Assunto:", ["Todos"] + available_assuntos_manage, key="filter_assunto_manage")

        if selected_assunto_manage != "Todos":
            displayed_cards = [card for card in displayed_cards if card["assunto"] == selected_assunto_manage]

        if not displayed_cards: # ATUALIZADO: Usando um IF para a mensagem
            if st.session_state.global_cartoes:
                st.info("Nenhum cartão encontrado com os filtros selecionados. Altere os filtros.")
            else:
                st.info("Nenhum cartão adicionado ainda. Use o formulário acima para criar seu primeiro cartão.")
            return # Sai da função se não há cartões para exibir

        # O restante do código de exibição/edição/exclusão de cartões segue aqui
        for i, card in enumerate(displayed_cards):
            original_index = st.session_state.global_cartoes.index(card)

            with st.expander(f"Cartão {original_index+1} ({card['materia']} - {card['assunto']}): {card['pergunta'][:50]}..."):
                st.write("**Matéria:**", card["materia"])
                st.write("**Assunto:**", card["assunto"])
                st.write("**Pergunta:**", card["pergunta"])
                st.write("**Resposta Esperada:**", card["resposta_esperada"])

                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button(f"Editar", key=f"edit_card_{original_index}"):
                        st.session_state.edit_index = original_index
                        st.session_state.edit_materia = card["materia"]
                        st.session_state.edit_assunto = card["assunto"]
                        st.session_state.edit_pergunta = card["pergunta"]
                        st.session_state.edit_resposta = card["resposta_esperada"]
                        st.rerun()

                with col_delete:
                    if st.button(f"Excluir", key=f"delete_card_{original_index}"):
                        st.session_state.global_cartoes.pop(original_index)
                        salvar_cartoes_globais(st.session_state.global_cartoes)
                        if st.session_state.current_card_index >= len(st.session_state.global_cartoes):
                            st.session_state.current_card_index = 0
                        st.rerun()
            st.markdown("---")

        if 'edit_index' in st.session_state and st.session_state.edit_index is not None:
            st.subheader(f"Editar Cartão {st.session_state.edit_index + 1}")
            with st.form("edit_card_form"):
                edited_materia = st.text_input("Matéria:", value=st.session_state.edit_materia, key="edit_m_input")
                edited_assunto = st.text_input("Assunto:", value=st.session_state.edit_assunto, key="edit_a_input")
                edited_pergunta = st.text_area("Pergunta:", value=st.session_state.edit_pergunta, height=100, key="edit_q_input")
                edited_resposta = st.text_area("Resposta Esperada:", value=st.session_state.edit_resposta, height=100, key="edit_ans_input")
                col_save, col_cancel = st.columns(2)
                with col_save:
                    edited_submitted = st.form_submit_button("Salvar Edição")
                with col_cancel:
                    cancel_edit = st.form_submit_button("Cancelar Edição")

                if edited_submitted:
                    if edited_materia.strip() and edited_assunto.strip() and edited_pergunta.strip() and edited_resposta.strip():
                        st.session_state.global_cartoes[st.session_state.edit_index] = {
                            "materia": edited_materia.strip(),
                            "assunto": edited_assunto.strip(),
                            "pergunta": edited_pergunta.strip(),
                            "resposta_esperada": edited_resposta.strip()
                        }
                        salvar_cartoes_globais(st.session_state.global_cartoes)
                        st.session_state.edit_index = None
                        st.rerun()
                    else:
                        st.warning("Por favor, preencha todos os campos para salvar a edição.")
                elif cancel_edit: # Corrigido para 'elif'
                    st.session_state.edit_index = None
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

        if not filtered_history: # ATUALIZADO: Usando um IF para a mensagem
            st.info("Nenhuma resposta foi avaliada com os filtros selecionados. Comece a praticar na aba 'Todas as Perguntas'!")
            return # Sai da função se não há histórico para exibir
            
        # O restante do código de métricas segue aqui.
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
        st.header("Modo de Prática: Perguntas Mais Difíceis")

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

        # AQUI FOI ONDE O 'else' ESTAVA DANDO ERRO.
        if not filtered_cards_difficult: # ATUALIZADO: Usando um IF para a mensagem
            st.info("Parabéns! Não há perguntas classificadas como 'difíceis' com os filtros selecionados, ou elas ainda não foram respondidas e pontuadas abaixo de 80%.")
            return # Sai da função se não há cartões para exibir

        # O restante do código da aba Difíceis segue aqui.
        if st.session_state.current_card_index_difficult >= len(filtered_cards_difficult):
            st.session_state.current_card_index_difficult = 0 # Reseta se o índice for inválido

        current_card_difficult = filtered_cards_difficult[st.session_state.current_card_index_difficult]

        st.subheader(f"Pergunta ({st.session_state.current_card_index_difficult + 1}/{len(filtered_cards_difficult)}):")
        st.info(current_card_difficult["pergunta"])

        user_answer_difficult = st.text_area("Sua Resposta:",
                                    height=150,
                                    key=f"user_answer_input_difficult_{st.session_state.current_card_index_difficult}")

        if st.button("Verificar Resposta com Gemini (Difíceis)", key="check_response_btn_difficult"):
            if user_answer_difficult.strip():
                with st.spinner("Analisando com Gemini..."):
                    full_feedback_text_difficult = comparar_respostas_com_gemini(user_answer_difficult, current_card_difficult["resposta_esperada"])
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
        
        elif st.button("Revelar Resposta Esperada (Difíceis)", key="reveal_btn_difficult"):
            st.session_state.show_expected_answer = True
            st.session_state.last_gemini_feedback_display_parsed = None
            
        if st.session_state.show_expected_answer:
            st.subheader("Resposta Esperada:")
            st.success(current_card_difficult["resposta_esperada"])

        nav_col1_d, nav_col2_d, nav_col3_d, nav_col4_d = st.columns(4)
        with nav_col1_d:
            if st.button("Primeiro (Difíceis)", key="first_card_btn_difficult"):
                st.session_state.current_card_index_difficult = 0
                st.session_state.show_expected_answer = False
                st.session_state.last_gemini_feedback_display_parsed = None
                st.rerun()
            with nav_col2_d:
                if st.button("Anterior (Difíceis)", key="prev_card_btn_difficult"):
                    if st.session_state.current_card_index_difficult > 0:
                        st.session_state.current_card_index_difficult -= 1
                        st.session_state.show_expected_answer = False
                        st.session_state.last_gemini_feedback_display_parsed = None
                        st.rerun()
                    else:
                        st.info("Você está no primeiro cartão difícil.")
            with nav_col3_d:
                if st.button("Próximo (Difíceis)", key="next_card_btn_difficult"):
                    if st.session_state.current_card_index_difficult < len(filtered_cards_difficult) - 1:
                        st.session_state.current_card_index_difficult += 1
                        st.session_state.show_expected_answer = False
                        st.session_state.last_gemini_feedback_display_parsed = None
                        st.rerun()
                    else:
                        st.info("Você está no último cartão difícil.")
            with nav_col4_d:
                if st.button("Último (Difíceis)", key="last_card_btn_difficult"):
                    st.session_state.current_card_index_difficult = len(filtered_cards_difficult) - 1
                    st.session_state.show_expected_answer = False
                    st.session_state.last_gemini_feedback_display_parsed = None
                    st.rerun()


    # --- Lógica de Renderização das Abas (Chamadas de Função) ---
    # As funções de renderização são chamadas dentro dos blocos 'with' dos st.tabs().
    with tab1_comp:
        render_tab_all_questions()
    if tab2_comp: # Apenas se o admin estiver logado
        with tab2_comp:
            render_tab_manage_cards()
    with tab3_comp:
        render_tab_metrics()
    if tab4_comp: # Apenas se a aba existir (visível para não-admin também)
        with tab4_comp:
            render_tab_difficult_questions()
