import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    abort
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)

from flask_migrate import Migrate
from sqlalchemy import text

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

# =========================
# CONFIGURAÇÃO
# =========================

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-super-secreta')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'database.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

MAX_DURACAO_LEILAO = timedelta(days=365)
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
FOTO_PADRAO = 'sem-imagem.png'


# =========================
# PERMISSÕES
# =========================

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if not current_user.is_authenticated:
                return redirect(url_for('login'))

            if current_user.role not in roles:
                abort(403)

            return f(*args, **kwargs)

        return decorated_function
    return decorator

def pode_editar_leilao(leilao):

    if current_user.role == 'Admin':
        return True

    if current_user.id == leilao.criador_id:
        return True

    return False


def validar_data_hora_encerramento(valor):
    valor = (valor or '').strip()

    if not valor:
        return None, "Informe a data e o horário de encerramento do leilão."

    try:
        data_fim = datetime.strptime(valor, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None, "Data ou horário inválido. Use uma data e horário existentes no formato correto."

    agora = datetime.now()
    limite_maximo = agora + MAX_DURACAO_LEILAO

    if data_fim <= agora:
        return None, "A data e o horário de encerramento devem ser posteriores ao momento atual."

    if data_fim > limite_maximo:
        return None, "A data de encerramento não pode ser superior a 1 ano a partir de agora."

    return data_fim, None


def finalizar_leilao(leilao):
    if leilao.encerrado:
        return

    leilao.encerrado = True

    maior_lance = Lance.query.filter_by(
        leilao_id=leilao.id
    ).order_by(
        Lance.valor.desc()
    ).first()

    if maior_lance:
        leilao.vencedor_id = maior_lance.usuario_id
        leilao.valor_final = maior_lance.valor
    else:
        leilao.vencedor_id = None
        leilao.valor_final = None


def finalizar_leiloes_expirados():
    leiloes = Leilao.query.filter(
        Leilao.encerrado.is_(False),
        Leilao.data_fim.isnot(None),
        Leilao.data_fim <= datetime.now()
    ).all()

    for leilao in leiloes:
        finalizar_leilao(leilao)

    if leiloes:
        db.session.commit()


def usuario_pode_ver_contatos(leilao):
    if not leilao.encerrado:
        return False

    return (
        current_user.is_authenticated
        and (
            current_user.id == leilao.criador_id
            or current_user.id == leilao.vencedor_id
        )
    )


def nome_publico(usuario):
    if not usuario:
        return "Usuario"

    return usuario.nome_exibicao or usuario.nome_completo or usuario.username


def tempo_de_cadastro(usuario):
    if not usuario or not usuario.criado_em:
        return "data nao informada"

    dias = (datetime.now() - usuario.criado_em).days

    if dias <= 0:
        return "desde hoje"

    if dias == 1:
        return "ha 1 dia"

    if dias < 30:
        return f"ha {dias} dias"

    meses = dias // 30

    if meses < 12:
        return f"ha {meses} mes" if meses == 1 else f"ha {meses} meses"

    anos = dias // 365
    return f"ha {anos} ano" if anos == 1 else f"ha {anos} anos"


def estatisticas_usuario(usuario):
    leiloes_criados = Leilao.query.filter_by(criador_id=usuario.id).count()
    vendas_realizadas = Leilao.query.filter_by(
        criador_id=usuario.id,
        encerrado=True
    ).filter(
        Leilao.vencedor_id.isnot(None)
    ).count()
    compras_realizadas = Leilao.query.filter_by(
        vencedor_id=usuario.id,
        encerrado=True
    ).count()

    return {
        'leiloes_criados': leiloes_criados,
        'vendas_realizadas': vendas_realizadas,
        'compras_realizadas': compras_realizadas,
        'reputacao': "Sem avaliacoes"
    }


def extensao_permitida(nome_arquivo):
    return (
        '.' in nome_arquivo
        and nome_arquivo.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def salvar_foto_perfil(arquivo):
    if not arquivo or not arquivo.filename:
        return None, None

    if not extensao_permitida(arquivo.filename):
        return None, "Formato de imagem inválido. Use JPG, JPEG, PNG ou WEBP."

    nome_seguro = secure_filename(arquivo.filename)
    extensao = nome_seguro.rsplit('.', 1)[1].lower()
    nome_arquivo = f"user_{current_user.id}_{int(datetime.now().timestamp())}.{extensao}"
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    arquivo.save(caminho)

    return nome_arquivo, None


def registrar_log(acao, detalhes=None, usuario_id=None):
    log = LogAcao(
        usuario_id=usuario_id or (current_user.id if current_user.is_authenticated else None),
        acao=acao,
        detalhes=detalhes
    )
    db.session.add(log)


def garantir_schema_sqlite():
    if not db.engine.url.drivername.startswith('sqlite'):
        return

    colunas_user = {
        row[1]
        for row in db.session.execute(text("PRAGMA table_info(user)")).fetchall()
    }
    colunas_leilao = {
        row[1]
        for row in db.session.execute(text("PRAGMA table_info(leilao)")).fetchall()
    }

    colunas_user_sql = {
        'foto': 'VARCHAR(200)',
        'nome_completo': 'VARCHAR(120)',
        'telefone': 'VARCHAR(30)',
        'email': 'VARCHAR(120)',
        'cidade': 'VARCHAR(80)',
        'estado': 'VARCHAR(2)',
        'nome_exibicao': 'VARCHAR(80)',
        'biografia': 'TEXT',
        'criado_em': 'DATETIME',
        'motivo_banimento': 'TEXT',
        'data_banimento': 'DATETIME',
        'data_desbanimento': 'DATETIME',
        'pref_email': 'BOOLEAN DEFAULT 1',
        'pref_novos_lances': 'BOOLEAN DEFAULT 1',
        'pref_leiloes_encerrados': 'BOOLEAN DEFAULT 1',
        'mostrar_cidade': 'BOOLEAN DEFAULT 1',
        'mostrar_telefone': 'BOOLEAN DEFAULT 0',
        'mostrar_email': 'BOOLEAN DEFAULT 0',
        'banido': 'BOOLEAN DEFAULT 0',
    }

    for coluna, tipo in colunas_user_sql.items():
        if coluna not in colunas_user:
            db.session.execute(text(f"ALTER TABLE user ADD COLUMN {coluna} {tipo}"))

    if 'valor_final' not in colunas_leilao:
        db.session.execute(text("ALTER TABLE leilao ADD COLUMN valor_final FLOAT"))

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS log_acao (
            id INTEGER NOT NULL PRIMARY KEY,
            usuario_id INTEGER,
            acao VARCHAR(100) NOT NULL,
            detalhes TEXT,
            data DATETIME,
            FOREIGN KEY(usuario_id) REFERENCES user (id)
        )
    """))

    db.session.commit()

# =========================
# MODELOS
# =========================

class User(UserMixin, db.Model):
    
    foto = db.Column(
    db.String(200),
    default=FOTO_PADRAO
)

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default='Usuario'
    )

    nome_completo = db.Column(
        db.String(120)
    )

    telefone = db.Column(
        db.String(30)
    )

    email = db.Column(
        db.String(120)
    )

    cidade = db.Column(
        db.String(80)
    )

    estado = db.Column(
        db.String(2)
    )

    nome_exibicao = db.Column(
        db.String(80)
    )

    biografia = db.Column(
        db.Text
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    motivo_banimento = db.Column(
        db.Text
    )

    data_banimento = db.Column(
        db.DateTime
    )

    data_desbanimento = db.Column(
        db.DateTime
    )

    pref_email = db.Column(
        db.Boolean,
        default=True
    )

    pref_novos_lances = db.Column(
        db.Boolean,
        default=True
    )

    pref_leiloes_encerrados = db.Column(
        db.Boolean,
        default=True
    )

    mostrar_cidade = db.Column(
        db.Boolean,
        default=True
    )

    mostrar_telefone = db.Column(
        db.Boolean,
        default=False
    )

    mostrar_email = db.Column(
        db.Boolean,
        default=False
    )
    
    banido = db.Column(
    db.Boolean,
    default=False
)
    

class Leilao(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    titulo = db.Column(
        db.String(100),
        nullable=False
    )

    descricao = db.Column(
        db.Text
    )

    preco_inicial = db.Column(
        db.Float,
        nullable=False
    )

    lance_atual = db.Column(
        db.Float
    )

    imagem = db.Column(
        db.String(200),
        default='sem-imagem.jpg'
    )

    data_fim = db.Column(
        db.DateTime
    )

    criador_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    categoria = db.Column(
        db.String(50)
    )

    encerrado = db.Column(
        db.Boolean,
        default=False
    )

    vencedor_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    valor_final = db.Column(
        db.Float
    )

    criador = db.relationship(
        'User',
        foreign_keys=[criador_id]
    )

    vencedor = db.relationship(
        'User',
        foreign_keys=[vencedor_id]
    )
    
class Lance(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    valor = db.Column(
        db.Float,
        nullable=False
    )

    data = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    leilao_id = db.Column(
        db.Integer,
        db.ForeignKey('leilao.id')
    )

    usuario = db.relationship(
        'User'
    )

# =========================
# MODELOS NOVOS
# =========================




class Favorito(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    leilao_id = db.Column(
        db.Integer,
        db.ForeignKey('leilao.id')
    )


class LogAcao(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    acao = db.Column(
        db.String(100),
        nullable=False
    )

    detalhes = db.Column(
        db.Text
    )

    data = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    
# =========================
# LOGIN
# =========================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_request
def bloquear_usuario_banido():
    rotas_livres = {'login', 'logout', 'static', 'cadastro'}

    if (
        current_user.is_authenticated
        and current_user.banido
        and request.endpoint not in rotas_livres
    ):
        logout_user()
        flash("Sua conta foi suspensa. Entre em contato com a administração.")
        return redirect(url_for('login'))



# =========================
# ROTAS
# =========================

@app.route('/')
@login_required
def home():
    finalizar_leiloes_expirados()

    categoria = request.args.get(
        'categoria'
    )

    if categoria:

        leiloes = Leilao.query.filter_by(
            categoria=categoria
        ).all()

    else:

        leiloes = Leilao.query.all()

    return render_template(
        'home.html',
        leiloes=leiloes
    )

# =========================
# LOGIN
# =========================

@app.route(
    '/login',
    methods=['GET','POST']
)
def login():

    if request.method == 'POST':

        user = User.query.filter_by(
            username=request.form['username']
        ).first()

        if not user:

            flash(
                "Usuário não encontrado"
            )

            return redirect(
                url_for('login')
            )

        # bloqueia usuário banido
        if user.banido:

            flash(
                "Sua conta foi suspensa. Entre em contato com a administração."
            )

            return redirect(
                url_for('login')
            )

        # verifica senha
        if check_password_hash(
            user.password,
            request.form['password']
        ):

            login_user(user)

            flash(
                "Login realizado!"
            )

            return redirect(
                url_for('home')
            )

        flash(
            "Senha incorreta"
        )

    return render_template(
        'login.html'
    )
    
# =========================
# CADASTRO
# =========================

@app.route('/cadastro', methods=['GET','POST'])
def cadastro():

    if request.method == 'POST':

        usuario_existe = User.query.filter_by(
            username=request.form['username']
        ).first()

        if usuario_existe:

            flash("Usuário já existe")

            return redirect(
                url_for('cadastro')
            )

        novo = User(
            username=request.form['username'],
            password=generate_password_hash(
                request.form['password']
            ),
            role='Usuario',
            nome_completo=request.form.get('nome_completo'),
            nome_exibicao=request.form.get('nome_completo'),
            telefone=request.form.get('telefone'),
            email=request.form.get('email'),
            cidade=request.form.get('cidade'),
            estado=(request.form.get('estado') or '').upper()
        )

        db.session.add(novo)
        db.session.flush()
        registrar_log("cadastro_usuario", f"Usuário {novo.username} criou conta.", novo.id)
        db.session.commit()

        flash("Conta criada")

        return redirect(
            url_for('login')
        )

    return render_template(
        'cadastro.html'
    )


# =========================
# LOGOUT
# =========================

@app.route('/logout')
@login_required
def logout():

    logout_user()

    return redirect(
        url_for('login')
    )



# =========================
# DAR LANCE
# =========================

@app.route('/lance/<int:id>', methods=['POST'])
@login_required
def dar_lance(id):

    finalizar_leiloes_expirados()

    leilao = Leilao.query.get_or_404(id)

    if leilao.encerrado or (leilao.data_fim and datetime.now() > leilao.data_fim):
        finalizar_leilao(leilao)
        db.session.commit()
        flash("Leilão Encerrado.")
        return redirect(url_for('ver_leilao', id=leilao.id))

    if current_user.id == leilao.criador_id:
        flash("O proprietário não pode participar do próprio leilão.")
        return redirect(url_for('ver_leilao', id=leilao.id))

    valor_texto = request.form.get('valor', '').strip()

    if not valor_texto:
        flash("Digite um valor para o lance.")
        return redirect(url_for('home'))

    try:
        valor = float(valor_texto)

    except ValueError:

        flash("Digite um valor válido.")
        return redirect(url_for('home'))

    lance_atual = leilao.lance_atual or leilao.preco_inicial

    if valor <= lance_atual:

        flash(
            "O lance precisa ser maior que o atual."
        )

        return redirect(
            url_for('home')
        )

    novo_lance = Lance(
        valor=valor,
        usuario_id=current_user.id,
        leilao_id=leilao.id
    )

    db.session.add(novo_lance)

    leilao.lance_atual = valor

    db.session.commit()

    flash(
        "Lance realizado com sucesso!"
    )

    return redirect(
        url_for('home')
    )
    
# =========================
# CRIAR LEILÃO
# =========================

@app.route(
    '/criar_leilao',
    methods=['GET','POST']
)
@login_required
def criar_leilao():

    if request.method == 'POST':

        arquivo = request.files.get(
            'imagem'
        )

        nome_arquivo = "sem-imagem.jpg"

        if arquivo and arquivo.filename:

            nome_arquivo = secure_filename(
                arquivo.filename
            )

            caminho = os.path.join(
                app.config['UPLOAD_FOLDER'],
                nome_arquivo
            )

            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            arquivo.save(caminho)

        try:

            preco = float(
                request.form['preco']
            )

        except ValueError:

            flash(
                "Preço inválido."
            )

            return redirect(
                url_for(
                    'criar_leilao'
                )
            )

        data_final, erro_data = validar_data_hora_encerramento(
            request.form.get('data')
        )

        if erro_data:
            flash(
                erro_data
            )

            return redirect(
                url_for(
                    'criar_leilao'
                )
            )

        novo = Leilao(

            titulo=request.form[
                'titulo'
            ],

            descricao=request.form[
                'descricao'
            ],

            preco_inicial=preco,

            lance_atual=preco,

            imagem=nome_arquivo,

            data_fim=data_final,

            criador_id=current_user.id,
            
            categoria=request.form['categoria'],
        )

        db.session.add(
            novo
        )

        db.session.commit()

        flash(
            "Leilão criado!"
        )

        return redirect(
            url_for(
                'home'
            )
        )

    return render_template(
        'criar_leilao.html'
    )
    
    # =========================
# EDITAR LEILÃO
# =========================

@app.route(
    '/editar_leilao/<int:id>',
    methods=['GET','POST']
)
@login_required
def editar_leilao(id):

    leilao = Leilao.query.get_or_404(id)

    if not pode_editar_leilao(leilao):
        abort(403)

    if request.method == 'POST':

        leilao.titulo = request.form['titulo']

        leilao.descricao = request.form['descricao']
        
        leilao.categoria = request.form['categoria']

        # valida preço
        try:

            leilao.preco_inicial = float(
                request.form['preco']
            )

        except ValueError:

            flash(
                "Preço inválido."
            )

            return redirect(
                url_for(
                    'editar_leilao',
                    id=id
                )
            )

        # imagem opcional
        arquivo = request.files.get(
            'imagem'
        )

        if arquivo and arquivo.filename:

            nome = secure_filename(
                arquivo.filename
            )

            caminho = os.path.join(
                app.config['UPLOAD_FOLDER'],
                nome
            )

            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            arquivo.save(
                caminho
            )

            leilao.imagem = nome

        data_final, erro_data = validar_data_hora_encerramento(
            request.form.get('data')
        )

        if erro_data:
            flash(
                erro_data
            )

            return redirect(
                url_for(
                    'editar_leilao',
                    id=id
                )
            )

        leilao.data_fim = data_final
        leilao.encerrado = False

        db.session.commit()

        flash(
            "Leilão atualizado!"
        )

        return redirect(
            url_for(
                'home'
            )
        )

    return render_template(
        'editar_leilao.html',
        leilao=leilao
    )
    
    
# =========================
# VER LEILÃO
# =========================

@app.route('/leilao/<int:id>')
@login_required
def ver_leilao(id):
    finalizar_leiloes_expirados()

    leilao = Leilao.query.get_or_404(id)
    vendedor = leilao.criador
    stats_vendedor = estatisticas_usuario(vendedor) if vendedor else None

    lances = Lance.query.filter_by(
        leilao_id=id
    ).order_by(
        Lance.valor.desc()
    ).all()

    vencedor = None

    if leilao.vencedor_id:

        vencedor = User.query.get(
            leilao.vencedor_id
        )

    return render_template(
        'leilao.html',
        leilao=leilao,
        lances=lances,
        vencedor=vencedor,
        vendedor=vendedor,
        stats_vendedor=stats_vendedor,
        tempo_cadastro_vendedor=tempo_de_cadastro(vendedor) if vendedor else "data nao informada",
        pode_ver_contatos=usuario_pode_ver_contatos(leilao)
    )


@app.route('/meus_leiloes')
@login_required
def meus_leiloes():
    finalizar_leiloes_expirados()

    leiloes_abertos = Leilao.query.filter_by(
        criador_id=current_user.id,
        encerrado=False
    ).order_by(
        Leilao.data_fim.asc()
    ).all()

    leiloes_encerrados = Leilao.query.filter_by(
        criador_id=current_user.id,
        encerrado=True
    ).order_by(
        Leilao.data_fim.desc()
    ).all()

    return render_template(
        'meus_leiloes.html',
        leiloes_abertos=leiloes_abertos,
        leiloes_encerrados=leiloes_encerrados
    )
    
    
# =========================
# DELETAR LEILÃO
# =========================

@app.route(
    '/remover_lance/<int:id>',
    methods=['POST']
)
@login_required
def remover_lance(id):
    lance = Lance.query.get_or_404(id)
    leilao = Leilao.query.get_or_404(lance.leilao_id)

    if current_user.role != 'Admin' and current_user.id != leilao.criador_id:
        abort(403)

    db.session.delete(lance)

    maior_lance = Lance.query.filter(
        Lance.leilao_id == leilao.id,
        Lance.id != lance.id
    ).order_by(
        Lance.valor.desc()
    ).first()

    leilao.lance_atual = maior_lance.valor if maior_lance else leilao.preco_inicial

    if leilao.encerrado:
        leilao.vencedor_id = maior_lance.usuario_id if maior_lance else None
        leilao.valor_final = maior_lance.valor if maior_lance else None

    registrar_log(
        "remover_lance",
        f"Lance {id} removido do leilão {leilao.id}."
    )
    db.session.commit()

    flash("Lance removido com sucesso.")
    return redirect(url_for('ver_leilao', id=leilao.id))


@app.route(
    '/deletar_leilao/<int:id>',
    methods=['POST']
)
@login_required
def deletar_leilao(id):

    leilao = Leilao.query.get_or_404(id)

    if not pode_editar_leilao(leilao):

        abort(403)

    Lance.query.filter_by(leilao_id=leilao.id).delete()
    Favorito.query.filter_by(leilao_id=leilao.id).delete()
    registrar_log(
        "deletar_leilao",
        f"Leilão {leilao.id} - {leilao.titulo} excluído."
    )

    db.session.delete(
        leilao
    )

    db.session.commit()

    flash(
        "Leilão excluído!"
    )

    return redirect(
        url_for('home')
    )
    
# =========================
# PAINEL ADMIN
# =========================

@app.route('/usuarios')
@login_required
@role_required(['Admin'])
def usuarios():

    lista = User.query.all()

    return render_template(
        'usuarios.html',
        usuarios=lista
    )



# =========================
# PERFIL
# =========================

@app.route('/minha_conta')
@login_required
def minha_conta():
    return redirect(url_for('editar_perfil'))


@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    if request.method == 'POST':
        acao = request.form.get('acao', 'perfil')

        if acao == 'senha':
            senha_atual = request.form.get('senha_atual', '')
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')

            if not check_password_hash(current_user.password, senha_atual):
                flash("Senha atual incorreta.")
                return redirect(url_for('editar_perfil'))

            if len(nova_senha) < 6:
                flash("A nova senha deve ter pelo menos 6 caracteres.")
                return redirect(url_for('editar_perfil'))

            if nova_senha != confirmar_senha:
                flash("A confirmacao da senha nao confere.")
                return redirect(url_for('editar_perfil'))

            current_user.password = generate_password_hash(nova_senha)
            registrar_log("alterar_senha", "Usuario alterou a propria senha.")
            db.session.commit()

            flash("Senha alterada com sucesso.")
            return redirect(url_for('editar_perfil'))

        current_user.nome_exibicao = request.form.get('nome_exibicao')
        current_user.nome_completo = request.form.get('nome_completo')
        current_user.email = request.form.get('email')
        current_user.telefone = request.form.get('telefone')
        current_user.cidade = request.form.get('cidade')
        current_user.estado = (request.form.get('estado') or '').upper()
        current_user.biografia = request.form.get('biografia')

        current_user.pref_email = bool(request.form.get('pref_email'))
        current_user.pref_novos_lances = bool(request.form.get('pref_novos_lances'))
        current_user.pref_leiloes_encerrados = bool(request.form.get('pref_leiloes_encerrados'))
        current_user.mostrar_cidade = bool(request.form.get('mostrar_cidade'))
        current_user.mostrar_telefone = bool(request.form.get('mostrar_telefone'))
        current_user.mostrar_email = bool(request.form.get('mostrar_email'))

        if request.form.get('remover_foto'):
            current_user.foto = FOTO_PADRAO
            registrar_log("remover_foto_perfil", "Usuário removeu a foto de perfil.")

        foto = request.files.get('foto')
        nome_foto, erro_foto = salvar_foto_perfil(foto)

        if erro_foto:
            flash(erro_foto)
            return redirect(url_for('editar_perfil'))

        if nome_foto:
            current_user.foto = nome_foto
            registrar_log("alterar_foto_perfil", "Usuário alterou a foto de perfil.")

        registrar_log("editar_perfil", "Usuário atualizou o perfil.")
        db.session.commit()

        flash("Perfil atualizado com sucesso.")
        return redirect(url_for('editar_perfil'))

    usuarios = User.query.order_by(User.username.asc()).all() if current_user.role == 'Admin' else None

    return render_template(
        'perfil.html',
        stats=estatisticas_usuario(current_user),
        tempo_cadastro=tempo_de_cadastro(current_user),
        usuarios=usuarios
    )


@app.route('/perfil/<int:id>')
@login_required
def perfil_publico(id):
    user = User.query.get_or_404(id)

    return render_template(
        'perfil_publico.html',
        usuario=user,
        stats=estatisticas_usuario(user),
        tempo_cadastro=tempo_de_cadastro(user)
    )


@app.route('/excluir_conta', methods=['POST'])
@login_required
def excluir_conta():
    usuario = current_user._get_current_object()
    usuario_id = usuario.id
    username = usuario.username

    Lance.query.filter_by(usuario_id=usuario_id).delete()
    Favorito.query.filter_by(usuario_id=usuario_id).delete()

    leiloes = Leilao.query.filter_by(criador_id=usuario_id).all()
    for leilao in leiloes:
        Lance.query.filter_by(leilao_id=leilao.id).delete()
        Favorito.query.filter_by(leilao_id=leilao.id).delete()
        db.session.delete(leilao)

    LogAcao.query.filter_by(usuario_id=usuario_id).update({'usuario_id': None})
    db.session.add(LogAcao(
        usuario_id=None,
        acao="excluir_conta",
        detalhes=f"Usuário {username} excluiu a própria conta."
    ))

    db.session.delete(usuario)
    logout_user()
    db.session.commit()

    flash("Conta excluída com sucesso.")
    return redirect(url_for('login'))
    
    
# =========================
# ADMIN
# =========================

@app.route('/promover/<int:id>', methods=['POST'])
@login_required
@role_required(['Admin'])
def promover(id):

    user = User.query.get_or_404(id)

    user.role='Admin'
    registrar_log("promover_usuario", f"Usuário {user.username} promovido a Admin.")

    db.session.commit()

    flash("Usuário promovido.")

    return redirect(url_for('editar_perfil'))


@app.route('/banir/<int:id>', methods=['POST'])
@login_required
@role_required(['Admin'])
def banir(id):

    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash("Você não pode banir a própria conta.")
        return redirect(url_for('editar_perfil'))

    user.banido = True
    user.motivo_banimento = request.form.get('motivo_banimento')
    user.data_banimento = datetime.now()
    user.data_desbanimento = None

    registrar_log(
        "banir_usuario",
        f"Usuário {user.username} banido. Motivo: {user.motivo_banimento}"
    )

    db.session.commit()

    flash("Usuário banido.")

    return redirect(
        url_for(
            'editar_perfil'
        )
    )


@app.route('/desbanir/<int:id>', methods=['POST'])
@login_required
@role_required(['Admin'])
def desbanir(id):

    user = User.query.get_or_404(id)

    user.banido = False
    user.data_desbanimento = datetime.now()

    registrar_log(
        "desbanir_usuario",
        f"Usuário {user.username} desbanido."
    )

    db.session.commit()

    flash("Usuário desbanido.")

    return redirect(
        url_for(
            'editar_perfil'
        )
    )
    
# =========================
# INICIALIZAÇÃO
# =========================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()
        garantir_schema_sqlite()

        admin = User.query.filter_by(
            username='admin'
        ).first()

        if not admin:

            novo_admin = User(

                username='admin',

                password=generate_password_hash(
                    'admin123'
                ),

                role='Admin'
            )

            db.session.add(
                novo_admin
            )

            db.session.commit()

            print(
                "Admin criado"
            )

    app.run(
        debug=True
    )
