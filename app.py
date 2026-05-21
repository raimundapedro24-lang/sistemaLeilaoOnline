import os
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, abort
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
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


# =========================
# CONFIGURAÇÃO
# =========================

app = Flask(__name__)

app.config['SECRET_KEY'] = 'chave-super-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# =========================
# PERMISSÕES
# =========================

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if current_user.role not in roles:
                abort(403)

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# =========================
# MODELOS
# =========================

class User(UserMixin, db.Model):

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

    data_fim = db.Column(
        db.DateTime
    )

    criador_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
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

    horario = db.Column(
        db.DateTime,
        default=datetime.now
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    leilao_id = db.Column(
        db.Integer,
        db.ForeignKey('leilao.id')
    )


# =========================
# LOGIN
# =========================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# ROTAS
# =========================

@app.route('/')
@login_required
def home():

    leiloes = Leilao.query.all()

    return render_template(
        'home.html',
        leiloes=leiloes
    )


# =========================
# LOGIN
# =========================

@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        user = User.query.filter_by(
            username=request.form['username']
        ).first()

        if user and check_password_hash(
            user.password,
            request.form['password']
        ):

            login_user(user)

            flash("Login realizado!")

            return redirect(
                url_for('home')
            )

        flash("Usuário ou senha inválidos")

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
            role='Usuario'
        )

        db.session.add(novo)
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
# CRIAR LEILÃO
# =========================

@app.route(
    '/criar_leilao',
    methods=['GET','POST']
)
@login_required
def criar_leilao():

    if request.method == 'POST':

        preco = float(
            request.form['preco']
        )

        leilao = Leilao(
            titulo=request.form['titulo'],
            descricao=request.form['descricao'],
            preco_inicial=preco,
            lance_atual=preco,
            data_fim=datetime.strptime(
                request.form['data'],
                "%Y-%m-%d"
            ),
            criador_id=current_user.id
        )

        db.session.add(leilao)

        db.session.commit()

        flash(
            "Leilão criado!"
        )

        return redirect(
            url_for('home')
        )

    return render_template(
        'criar_leilao.html'
    )


# =========================
# DAR LANCE
# =========================

@app.route(
    '/lance/<int:id>',
    methods=['POST']
)
@login_required
def dar_lance(id):

    leilao = Leilao.query.get_or_404(id)

    valor = float(
        request.form['valor']
    )

    if valor <= leilao.lance_atual:

        flash(
            "Lance precisa ser maior"
        )

        return redirect(
            url_for('home')
        )

    novo_lance = Lance(
        valor=valor,
        usuario_id=current_user.id,
        leilao_id=id
    )

    leilao.lance_atual = valor

    db.session.add(
        novo_lance
    )

    db.session.commit()

    flash(
        "Lance realizado!"
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
# INICIALIZAÇÃO
# =========================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()

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