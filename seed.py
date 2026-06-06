from datetime import datetime, timedelta
from itertools import cycle
from random import Random

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import (
    app,
    db,
    garantir_schema_sqlite,
    User,
    Leilao,
    Lance,
    Favorito,
    LogAcao,
    FOTO_PADRAO,
)


SENHA_PADRAO = "demo123"
IMAGEM_LEILAO_PADRAO = "sem-imagem.jpg"
rng = Random(20260606)


def limpar_banco():
    """Remove todos os dados e preserva a estrutura das tabelas."""
    db.session.execute(text("PRAGMA foreign_keys=OFF"))

    for model in (Favorito, Lance, LogAcao, Leilao, User):
        db.session.query(model).delete()

    if db.engine.dialect.name == "sqlite":
        possui_sequence = db.session.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
        ).first()

        if possui_sequence:
            tabelas = ["favorito", "lance", "log_acao", "leilao", "user"]
            for tabela in tabelas:
                db.session.execute(
                    text("DELETE FROM sqlite_sequence WHERE name = :name"),
                    {"name": tabela},
                )

    db.session.execute(text("PRAGMA foreign_keys=ON"))
    db.session.commit()


def criar_usuario(
    username,
    nome_completo,
    nome_exibicao,
    email,
    telefone,
    cidade,
    estado,
    role="Usuario",
    criado_em=None,
    biografia=None,
    banido=False,
    motivo_banimento=None,
):
    return User(
        username=username,
        password=generate_password_hash(SENHA_PADRAO),
        role=role,
        foto=FOTO_PADRAO,
        nome_completo=nome_completo,
        nome_exibicao=nome_exibicao,
        email=email,
        telefone=telefone,
        cidade=cidade,
        estado=estado,
        biografia=biografia,
        criado_em=criado_em or datetime.now(),
        pref_email=True,
        pref_novos_lances=True,
        pref_leiloes_encerrados=True,
        mostrar_cidade=True,
        mostrar_telefone=False,
        mostrar_email=False,
        banido=banido,
        motivo_banimento=motivo_banimento,
        data_banimento=datetime.now() - timedelta(days=2) if banido else None,
    )


def popular_usuarios():
    hoje = datetime.now()

    admin = criar_usuario(
        username="admin",
        nome_completo="Mariana Costa Almeida",
        nome_exibicao="Admin Mariana",
        email="admin@leilaodemo.com",
        telefone="(85) 90000-0001",
        cidade="Fortaleza",
        estado="CE",
        role="Admin",
        criado_em=hoje - timedelta(days=420),
        biografia="Administradora do ambiente de demonstração do sistema de leilões.",
    )

    vendedores_base = [
        ("vendedor1", "Rafael Lima Rocha", "Rafael Veículos", "Fortaleza", "CE"),
        ("vendedor2", "Beatriz Sousa Martins", "Casa & Arte", "Natal", "RN"),
        ("vendedor3", "Henrique Duarte Melo", "Duarte Máquinas", "Recife", "PE"),
        ("vendedor4", "Camila Nunes Ferreira", "Camila Tech", "João Pessoa", "PB"),
        ("vendedor5", "Lucas Pereira Gomes", "Pereira Imóveis", "Mossoró", "RN"),
    ]

    vendedores = []
    for indice, (username, nome, exibicao, cidade, estado) in enumerate(vendedores_base, start=1):
        vendedores.append(
            criar_usuario(
                username=username,
                nome_completo=nome,
                nome_exibicao=exibicao,
                email=f"{username}@leilaodemo.com",
                telefone=f"(85) 98888-10{indice:02d}",
                cidade=cidade,
                estado=estado,
                criado_em=hoje - timedelta(days=90 + indice * 37),
                biografia=f"{exibicao} oferece itens selecionados para leilões de demonstração.",
            )
        )

    compradores_base = [
        ("comprador1", "Ana Clara Freitas", "Ana Clara", "Fortaleza", "CE"),
        ("comprador2", "Bruno Cardoso Vieira", "Bruno C.", "Sobral", "CE"),
        ("comprador3", "Carolina Matos Ribeiro", "Carol Matos", "Recife", "PE"),
        ("comprador4", "Diego Alves Monteiro", "Diego A.", "Natal", "RN"),
        ("comprador5", "Eduarda Sales Campos", "Eduarda", "Maceió", "AL"),
        ("comprador6", "Felipe Barros Azevedo", "Felipe B.", "Teresina", "PI"),
        ("comprador7", "Gabriela Moura Silva", "Gabi Moura", "João Pessoa", "PB"),
        ("comprador8", "Igor Fernandes Teixeira", "Igor F.", "Aracaju", "SE"),
        ("comprador9", "Juliana Castro Lima", "Juliana C.", "Fortaleza", "CE"),
        ("comprador10", "Mateus Rocha Batista", "Mateus R.", "Recife", "PE"),
    ]

    compradores = []
    for indice, (username, nome, exibicao, cidade, estado) in enumerate(compradores_base, start=1):
        banido = username == "comprador10"
        compradores.append(
            criar_usuario(
                username=username,
                nome_completo=nome,
                nome_exibicao=exibicao,
                email=f"{username}@leilaodemo.com",
                telefone=f"(85) 97777-20{indice:02d}",
                cidade=cidade,
                estado=estado,
                criado_em=hoje - timedelta(days=15 + indice * 18),
                biografia="Usuário comprador criado para testar lances e histórico de compras.",
                banido=banido,
                motivo_banimento="Conta suspensa para demonstrar banimento e desbanimento." if banido else None,
            )
        )

    db.session.add(admin)
    db.session.add_all(vendedores)
    db.session.add_all(compradores)
    db.session.commit()

    return admin, vendedores, compradores


def definicoes_leiloes():
    return [
        ("Honda Civic Touring 2020", "Sedã em ótimo estado, revisões em dia e documentação regular.", "Automóveis", 78000),
        ("Apartamento 2 quartos em Fortaleza", "Imóvel com varanda, vaga de garagem e área de lazer completa.", "Imóveis", 220000),
        ("Notebook Dell XPS 13", "Notebook premium com SSD, tela full HD e bateria em bom estado.", "Tecnologia", 4200),
        ("Lote de smartphones seminovos", "Conjunto com aparelhos revisados para revenda ou uso corporativo.", "Eletrônicos", 6500),
        ("Retroescavadeira JCB 3CX", "Máquina operacional para obras, com manutenção preventiva recente.", "Máquinas", 145000),
        ("Mesa de jantar madeira maciça", "Peça artesanal para sala de jantar, acompanha seis cadeiras.", "Outros", 1800),
        ("Toyota Corolla XEi 2018", "Veículo automático com baixa quilometragem e interior conservado.", "Automóveis", 69000),
        ("Terreno urbano 300m²", "Terreno plano em bairro residencial com acesso pavimentado.", "Imóveis", 135000),
        ("MacBook Pro 14 polegadas", "Equipamento para edição, programação e trabalhos gráficos.", "Tecnologia", 9800),
        ("Projetor Epson corporativo", "Projetor usado em sala de aula, luminosidade alta e case incluso.", "Eletrônicos", 2100),
        ("Empilhadeira elétrica", "Equipamento para galpão, bateria revisada e carregador incluso.", "Máquinas", 52000),
        ("Coleção de moedas antigas", "Coleção com peças nacionais e internacionais catalogadas.", "Outros", 1200),
        ("Fiat Toro Volcano 2021", "Picape diesel, automática e com acessórios instalados.", "Automóveis", 122000),
        ("Sala comercial no centro", "Sala pronta para escritório, prédio com elevador e portaria.", "Imóveis", 165000),
        ("Servidor Dell PowerEdge", "Servidor para laboratório ou pequena empresa, com discos inclusos.", "Tecnologia", 7500),
        ("Smart TV OLED 55 polegadas", "TV com ótima imagem, controle original e nota fiscal.", "Eletrônicos", 3900),
        ("Compressor industrial", "Compressor para oficina, funcionamento testado.", "Máquinas", 8700),
        ("Relógio de coleção", "Relógio automático revisado, acompanha estojo.", "Outros", 2600),
        ("Chevrolet Onix Premier 2022", "Hatch completo, econômico e com garantia vigente.", "Automóveis", 76000),
        ("Casa duplex em condomínio", "Casa com três suítes, área gourmet e segurança 24h.", "Imóveis", 480000),
    ]


def criar_leilao(indice, dados, vendedor):
    titulo, descricao, categoria, preco = dados
    agora = datetime.now()

    if indice <= 8:
        data_criacao = agora - timedelta(days=indice + 3)
        data_fim = agora + timedelta(days=7 + indice)
        encerrado = False
    elif indice <= 12:
        data_criacao = agora - timedelta(days=12 + indice)
        data_fim = agora + timedelta(hours=indice - 7)
        encerrado = False
    else:
        data_criacao = agora - timedelta(days=30 + indice)
        data_fim = agora - timedelta(days=indice - 11)
        encerrado = True

    return Leilao(
        titulo=titulo,
        descricao=descricao,
        categoria=categoria,
        preco_inicial=float(preco),
        lance_atual=float(preco),
        imagem=IMAGEM_LEILAO_PADRAO,
        data_criacao=data_criacao,
        data_fim=data_fim,
        criador_id=vendedor.id,
        encerrado=encerrado,
    )


def popular_leiloes(vendedores):
    vendedores_ciclo = cycle(vendedores)
    leiloes = []

    for indice, dados in enumerate(definicoes_leiloes(), start=1):
        leilao = criar_leilao(indice, dados, next(vendedores_ciclo))
        leiloes.append(leilao)

    db.session.add_all(leiloes)
    db.session.commit()

    return leiloes


def compradores_para_lances(compradores, quantidade):
    disponiveis = [comprador for comprador in compradores if not comprador.banido]
    return [disponiveis[(quantidade + i) % len(disponiveis)] for i in range(quantidade)]


def popular_lances(leiloes, compradores):
    sem_lances = {3, 8, 12, 17}
    muitos_lances = {2, 5, 9, 13, 20}

    for indice, leilao in enumerate(leiloes, start=1):
        if indice in sem_lances:
            if leilao.encerrado:
                leilao.valor_final = None
                leilao.vencedor_id = None
            continue

        quantidade = 8 if indice in muitos_lances else rng.randint(2, 4)
        incremento_base = max(50, leilao.preco_inicial * 0.025)
        valor_atual = leilao.preco_inicial
        participantes = compradores_para_lances(compradores, quantidade)

        for ordem, comprador in enumerate(participantes, start=1):
            valor_atual += incremento_base + rng.randint(25, 350)
            lance = Lance(
                valor=round(valor_atual, 2),
                data=leilao.data_criacao + timedelta(days=ordem, hours=rng.randint(1, 12)),
                usuario_id=comprador.id,
                leilao_id=leilao.id,
            )
            db.session.add(lance)

        leilao.lance_atual = round(valor_atual, 2)

        if leilao.encerrado:
            vencedor = participantes[-1]
            leilao.vencedor_id = vencedor.id
            leilao.valor_final = leilao.lance_atual

    db.session.commit()


def popular_favoritos(leiloes, compradores):
    for comprador in compradores[:8]:
        favoritos = rng.sample(leiloes, 3)
        for leilao in favoritos:
            if leilao.criador_id != comprador.id:
                db.session.add(Favorito(usuario_id=comprador.id, leilao_id=leilao.id))

    db.session.commit()


def popular_logs(admin, vendedores, compradores, leiloes):
    eventos = [
        LogAcao(usuario_id=admin.id, acao="seed_demo", detalhes="Banco populado para apresentação."),
        LogAcao(usuario_id=compradores[-1].id, acao="banir_usuario", detalhes="Usuário banido para demonstração do painel administrativo."),
        LogAcao(usuario_id=vendedores[0].id, acao="criar_leilao", detalhes=f"Leilão criado: {leiloes[0].titulo}."),
        LogAcao(usuario_id=vendedores[1].id, acao="criar_leilao", detalhes=f"Leilão criado: {leiloes[1].titulo}."),
    ]
    db.session.add_all(eventos)
    db.session.commit()


def popular_banco():
    with app.app_context():
        db.create_all()
        garantir_schema_sqlite()
        limpar_banco()

        admin, vendedores, compradores = popular_usuarios()
        leiloes = popular_leiloes(vendedores)
        popular_lances(leiloes, compradores)
        popular_favoritos(leiloes, compradores)
        popular_logs(admin, vendedores, compradores, leiloes)

        print("Seed de demonstração concluído.")
        print("")
        print("Credenciais:")
        print(f"  Admin:      admin / {SENHA_PADRAO}")
        print(f"  Vendedor:   vendedor1 / {SENHA_PADRAO}")
        print(f"  Comprador:  comprador1 / {SENHA_PADRAO}")
        print(f"  Banido:     comprador10 / {SENHA_PADRAO}")
        print("")
        print("Resumo:")
        print(f"  Usuários:   {User.query.count()}")
        print(f"  Leilões:    {Leilao.query.count()}")
        print(f"  Lances:     {Lance.query.count()}")
        print(f"  Favoritos:  {Favorito.query.count()}")
        print(f"  Logs:       {LogAcao.query.count()}")


if __name__ == "__main__":
    popular_banco()
