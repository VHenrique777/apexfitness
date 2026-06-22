# Apex Fitness - Sistema profissional modular

Projeto Flask em arquitetura MVC/modular para gestao de academia, preparado para PostgreSQL, API mobile futura, controle por cargos, loja, financeiro, relatorios, PDF, QR Code, e-mails e dashboard com Chart.js.

## Rodar em desenvolvimento

```powershell
cd apexfitness_github
pip install -r requirements.txt
python run.py
```

Acesse: http://127.0.0.1:5002

## PostgreSQL

Por padrao de producao, configure:

```powershell
$env:APEX_DEV="false"
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/apexfitness"
$env:SECRET_KEY="troque-essa-chave"
$env:JWT_SECRET_KEY="troque-essa-chave-jwt"
$env:MAIL_PASSWORD="senha-do-email"
python run.py
```

Em desenvolvimento, o sistema usa SQLite automaticamente para facilitar testes locais.

## Logins de teste

- Admin: `admin@apexfitness.com` / `admin123`
- Recepcao: `recepcao@apexfitness.com` / `recepcao123`
- Professor: `professor@apexfitness.com` / `professor123`
- Gerente Academia: `gerente.academia@apexfitness.com` / `gerenteacademia123`
- Gerente Loja: `gerente.loja@apexfitness.com` / `gerenteloja123`
- Gerente Geral: `gerente.geral@apexfitness.com` / `gerentegeral123`
- Dono: `dono@apexfitness.com` / `dono12345`
- Personal: `personal@apexfitness.com` / `personal123`
- Nutricionista: `nutri@apexfitness.com` / `nutri123`
- Fisioterapeuta: `fisio@apexfitness.com` / `fisio123`
- Mercado: `mercado@apexfitness.com` / `mercado123`
- Aluno: `aluno@apexfitness.com` / `aluno123`

## Estrutura

- `app/models`: tabelas do banco
- `app/auth`: login, logout, recuperacao, JWT
- `app/admin`: recepcao, usuarios, produtos, relatorios, logs
- `app/aluno`: conta, treinos, plano alimentar, check-in, financeiro
- `app/mercado`: carrinho, vendas, PIX, comprovante PDF
- `app/professor`, `app/personal`, `app/nutricionista`, `app/fisioterapeuta`: areas profissionais
- `app/financeiro`: dashboard financeiro com grafico
- `app/routes/api.py`: API v1 para app mobile futuro
- `app/services`: PDF, QR Code, pagamentos, e-mail, seed
- `app/templates`: HTML com CSS embutido e JavaScript

## Funcionalidades implementadas

- Cargos e permissões por rota
- Senhas com bcrypt
- CSRF via Flask-WTF
- JWT para API
- Recuperacao de senha por e-mail
- Logs de auditoria
- Validação de CPF, telefone, senha e e-mail único
- Página pública com sobre, planos, serviços, produtos e contato
- Cadastro de aluno somente por recepção/admin
- Portal do aluno
- Check-in com QR Code e bloqueio por inadimplência
- Loja com carrinho, soma, PIX, QR Code e comprovante PDF
- Treinos e planos alimentares com PDF
- Dashboard financeiro com Chart.js
- Relatórios PDF
- CSS SaaS responsivo com tema claro/escuro
