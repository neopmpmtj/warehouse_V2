# CentCompras — Guia de referência para administração e superutilizador

**Administração do sítio** · Versão 1.0 · Para o **superutilizador do sítio** / sede

> **Complemento dos manuais operacionais:** [Gestão de artigos](01-items.md) · [Encomendas de compra](02-purchase-orders.md) · [Receção de mercadorias e stock](03-goods-receipts.md) · [Filiais e Requisição interna](04-internal-requests.md) · [Casos limite e limites](05-edge-cases-and-limits.md) · [Catálogo do gestor](07-manager-catalog.md) · [Fios de pedido](08-request-threads.md) · [Voz da Empresa](09-company-voice.md).

Este guia cobre o trabalho **administrativo**: iniciar sessão no Django `/admin/`, criar utilizadores, atribuir funções e permissões, e gerir filiais e utilizadores de filial. **Não** trata das consolas do dia a dia — essas estão nos manuais 01–04 e 07.

---

## 1. Quem pode usar `/admin/`?

A administração Django em **`/admin/`** é **apenas para superutilizadores**.

| Tipo de conta | `/admin/`? | Consolas do sítio? |
|---------------|:---:|:---:|
| **Superutilizador** (`is_superuser`) | ✅ | ✅ (tem todas as permissões) |
| **Staff** (`is_staff` mas *não* superutilizador) | ❌ | ❌ |
| **Pessoal do armazém** (grupo de armazém) | ❌ | ✅ |
| **Pessoal de filial** (membro de filial) | ❌ | ✅ (`/branch/…`) |

O pessoal do armazém chega a **`/`** após o início de sessão. O pessoal só de filial chega a **`/branch/`** (painel da filial). Esse painel lista todas as ferramentas da filial (catálogo, requisição, fios, receções, Voz da Empresa). Em cada página de consola **`/manage/…`**, a etiqueta **CentCompras** acima do título da página liga de volta a **`/`** (painel do armazém). Nas páginas de filial, **CentCompras** liga de volta a **`/branch/`**. **Terminar sessão** é uma ligação pequena na linha do título **Definições** (engrenagem, canto superior direito). **Ajuda** é o ícone azul **?** junto à engrenagem (placeholder).

Duas regras a recordar:

- A verificação de início de sessão em `/admin/` exige **`is_active` *e* `is_superuser`** — a flag «staff» sozinha *não* chega.
- Um **superutilizador** também passa em todas as verificações de permissão do sítio, pelo que pode usar as consolas do armazém. Na prática, reserve o superutilizador para administração e dê ao pessoal do dia a dia um **grupo de armazém**.

> ⚠️ **Não** entregue credenciais de superutilizador a um utilizador de filial, e não adicione pessoal de filial ao `/admin/`. A sede (superutilizador) é a única entidade que gere utilizadores e filiais.

---

## 2. Início de sessão e criação do superutilizador

### 2.1 Iniciar sessão

1. Aceda a **`https://<o-seu-domínio>/admin/`** (desenvolvimento: `http://127.0.0.1:8015/admin/`).
2. Introduza o seu **email** + **palavra-passe**.
3. Chega ao índice da administração Django.

Termine sessão com a ligação **Log out** no canto superior direito.

### 2.2 Criar o primeiro superutilizador

Não existe página de registo. Crie o superutilizador na linha de comandos do servidor:

```bash
source .venv/bin/activate
python manage.py createsuperuser
```

Pede **email** e **palavra-passe** (não há campo **username** — o início de sessão é por email). O seed de desenvolvimento (`./scripts/seed_dev_data.sh`) cria utilizadores de armazém e de filial mas **não** cria superutilizador.

---

## 3. O registo User — o que significa cada campo

Abra **`/admin/` → Users**. Um utilizador tem:

| Campo | Significado |
|-------|---------|
| **Email** | Identificador de início de sessão (único). Não há username. |
| **Password** | Em hash; pode definir/repor aqui. |
| **First / Last name** | Nomes de apresentação opcionais. |
| **Timezone** | Nome IANA (predefinição `Europe/Lisbon`). Nomes inválidos são rejeitados ao guardar. As datas são mostradas no fuso horário deste utilizador. |
| **Warehouse grade** | 1–3 para pessoal do armazém (ver §4). Ignorado para administradores de armazém e utilizadores de filial. |
| **is_active** | Desmarque para desativar a conta (recebem «Account is inactive» e a sessão termina). |
| **is_staff** | «Django admin login». Só superutilizadores devem ter isto (ver §1 — staff sozinho não entra em `/admin/`). |
| **is_superuser** | Acesso total a `/admin/` e a todas as permissões. |
| **Groups** | Grupos Django (os três grupos de armazém — ver §5). |
| **User permissions** | Permissões por utilizador. Deixe vazio — use grupos. |

---

## 4. Utilizadores do armazém — criar + função + grau

Um **utilizador do armazém** trabalha no sítio (`/manage/…`). Para criar um:

1. **`/admin/` → Users → Add user**.
2. Introduza **email** + **password** (deixe `is_staff` / `is_superuser` **desligados**).
3. Defina **timezone** e **warehouse grade**.
4. Em **Groups**, adicione o utilizador a **exatamente um** grupo de armazém:
   - `warehouse_admins`
   - `warehouse_managers`
   - `warehouse_data_operators`
5. Guarde.

### 4.1 As três funções de armazém

| Grupo | Catálogo | Encomendas de compra | Stock | Aprovar |
|-------|-----------|-----------------|-------|:---:|
| **Admin** (`warehouse_admins`) | completo (ver/adicionar/alterar/eliminar) | qualquer | receção, emissão, ajuste | qualquer montante |
| **Gestor** (`warehouse_managers`) | alterar (sem eliminar) | criar/submeter | receção, emissão, encerramento antecipado (g2+) | grau 2+ dentro dos tetos |
| **Operador** (`warehouse_data_operators`) | só leitura (g1) / alterar (g2) | ler | receção, emissão (g2) | nunca |

### 4.2 Graus

O **grau** é o controlo fino dentro de um grupo:

| Grupo | Graus válidos | Efeito |
|-------|:---:|--------|
| `warehouse_admins` | sempre **1** | ignorado — administradores são ilimitados |
| `warehouse_managers` | **1–3** | grau 1 = sem aprovar; **grau 2+** = aprovar (dentro dos tetos); grau 3 = tetos mais altos |
| `warehouse_data_operators` | **1–2** | grau 1 = só leitura; **grau 2** = alterar o circuito fechado |

Os tetos de aprovação em si estão em **`/manage/approval-limits/`** (administrador de armazém), não em `/admin/`. Predefinições: gestor grau 2 = próprio €100 / outros €5 000; grau 3 = próprio €500 / outros €50 000.

### 4.3 Duas cautelas importantes

- **Um grupo por utilizador.** A ferramenta do sistema (`assign_warehouse_group`, usada pelo seed) impõe isto — remove o utilizador de qualquer outro grupo de armazém e **redefine o grau para 1**. Se adicionar manualmente um utilizador a *vários* grupos de armazém em `/admin/`, o código resolve por ordem: **admins → managers → operators**, ganha o primeiro. Mantenha um só grupo.
- **Repor graus.** Atribuir um grupo (via código) repõe o grau para **1**; defina o grau *depois* de atribuir o grupo.

### 4.4 Utilizadores de desenvolvimento do seed (referência)

`./scripts/seed_dev_data.sh` cria (todas com palavra-passe `devpass123`):

| Email | Grupo | Grau |
|-------|-------|:---:|
| `warehouse.admin@centcompras.dev` | admins | 1 |
| `warehouse.manager@centcompras.dev` | managers | 1 |
| `warehouse.manager2@centcompras.dev` | managers | 2 |
| `warehouse.manager3@centcompras.dev` | managers | 3 |
| `warehouse.operator@centcompras.dev` | operators | 1 |
| `warehouse.operator2@centcompras.dev` | operators | 2 |

---

## 5. Grupos de armazém e permissões (geridos no código)

Os três grupos de armazém são **geridos no código**, não à mão.

- Em cada `migrate`, a aplicação executa `sync_warehouse_groups()` e **substitui** as permissões de cada grupo pelo conjunto definido no código.
- **Qualquer permissão que adicione à mão em `/admin/` é apagada no migrate seguinte.** Não conceda extras nestes três grupos.

**Regra prática:** **não** edita permissões dos grupos de armazém. Só decide a que grupo o utilizador pertence (e o seu *grau*). O grupo já traz as permissões certas.

---

## 6. Utilizadores e membros de filial

Um **utilizador de filial** trabalha em `/branch/…`. **Não** tem grupo de armazém; em vez disso tem **`BranchMembership`** (que filial + que função).

### 6.1 Criar um utilizador de filial

1. **`/admin/` → Users → Add user** — email + password, `is_staff`/`is_superuser` **desligados**, e **sem** grupo de armazém.
2. **`/admin/` → Branch memberships → Add** — escolha o **User**, a **Branch** e a **Role**.
3. Guarde.

### 6.2 Funções de filial

| Função | Pode fazer |
|------|--------|
| **Operator** | Consultar catálogo, criar/editar/submeter/cancelar rascunho, confirmar chegadas |
| **Manager** | + aprovar (dentro dos tetos), rejeitar, cancelar aprovado, encerramento antecipado na filial |
| **Admin** | + aprovação ilimitada, **ajustar stock da filial** |

### 6.3 Regras de adesão

- **Uma função por utilizador por filial** — `(user, branch)` é único.
- Um utilizador **pode pertencer a várias filiais** (funções diferentes permitidas). Verá um **seletor de filial** após o início de sessão.
- **Armazém e filial são separados.** Um utilizador com grupo de armazém *e* membro de filial chega ao painel do armazém após o início de sessão (o armazém ganha) mas ainda pode aceder a `/branch/…` por URL.
- **A sede cria utilizadores e membros de filial** em `/admin/` (bloqueio 10). O pessoal de filial nunca cria logins e nunca vê `/admin/`.

> 💡 *Referência do seed:* Norte tem `branch.operator.north`, `branch.manager.north`, `branch.admin.north`; Sul tem `branch.operator.south`, `branch.manager.south`; `branch.dual` é membro de ambas (para testar o seletor). Palavra-passe `devpass123`.

---

## 7. Gerir filiais

Abra **`/admin/` → Branchs** (Branches).

| Campo | Significado |
|-------|---------|
| **Name** | Único, **sem distinção de maiúsculas/minúsculas** |
| **is_active** | Desmarque para **desativar** a filial |

- **Desativar uma filial** bloqueia trabalho *novo* (sem novos pedidos, linhas, submissão ou aprovação), mas pedidos **em curso** ainda podem ser emitidos, recebidos e encerrados — o stock em trânsito não fica preso.
- Não existe «eliminar filial» — desative-a. O histórico é preservado.

---

## 8. Limites de aprovação (onde estão)

Os tetos de aprovação **não** se definem em `/admin/` — têm consolas próprias no sítio (só administrador de armazém):

| O quê | Consola | Modelo |
|------|---------|-------|
| Tetos de encomendas de compra do armazém (por grau) | `/manage/approval-limits/` | `ApprovalLimit` (grupo + grau → próprio/outros) |
| Tetos dos gestores de filial (globais) | `/manage/branch-approval-limits/` | `BranchApprovalLimit` (função `manager` → próprio/outros) |

![Consola de limites de aprovação](screenshots/06-approval-limits.png)

Em `/admin/` estas tabelas são **só de leitura**. As predefinições são criadas automaticamente no migrate e nunca sobrescrevem as suas edições.

---

## 9. O que é só de leitura em `/admin/`

A maior parte das tabelas de negócio em `/admin/` é **só de leitura de propósito** — as alterações do dia a dia passam pelas consolas do sítio e pela camada de serviços da aplicação (que também escreve o registo de auditoria). Em `/admin/` pode *ver* mas não adicionar/alterar/eliminar:

| Modelo | Onde alterar de facto |
|-------|-----------------------------|
| Items, families, suppliers, supplier prices, VAT | `/manage/items/` |
| Purchase orders | `/manage/purchase-orders/` |
| Approval limits | `/manage/approval-limits/` |
| Goods receipts, stock movements | `/manage/goods-receipts/` |
| Internal requests, goods issues | `/manage/internal-requests/` + `/branch/…` |
| Branch receipts, branch stock | `/branch/receipts/` |
| Fios de pedido | `/branch/threads/` + `/manage/threads/` (admin só inspeção) |
| Voz da Empresa | `/company-voice/` (admin só inspeção; **sem eliminação permanente**) |
| Change logs (todos os `*ChangeLog`) | Só leitura em todo o lado (auditoria) |

As **únicas** tabelas que normalmente edita em `/admin/` são: **Users**, **Groups** (só adesão, ver §5), **Branches** e **Branch memberships**.

O pessoal do armazém também tem uma vista **só de leitura** de stock + preços em `/manage/catalog/` — ver [Catálogo do gestor](07-manager-catalog.md). As edições continuam a passar por `/manage/items/` e `/manage/goods-receipts/`.

---

## 10. Fuso horário, datas e locale

- **Datas** são DD/MM/AAAA, hora 24 h, mostradas no **fuso horário** de cada utilizador (predefinição `Europe/Lisbon`). Armazenadas em UTC.
- Defina o fuso horário do utilizador no formulário **User** (nome IANA, p. ex. `Europe/Lisbon`, `Asia/Singapore`). Nomes inválidos são rejeitados.

---

## 11. Reposição de palavra-passe e desativação

- **Não existe reposição de palavra-passe em autosserviço.** Para repor, abra o utilizador em `/admin/` → **Password** → defina uma nova. Peça-lhe que termine sessão e volte a entrar.
- **Desative** um utilizador desmarcando **is_active**. A sessão termina automaticamente e vê *«Account is inactive»* no pedido seguinte. Volte a marcar para restaurar.

---

## 12. Autenticação e permissões (incl. Google OAuth)

Duas coisas distintas, geridas separadamente:

| | **Autenticação** (quem é) | **Autorização** (o que pode fazer) |
|---|---|---|
| **Desenvolvimento** | Email + palavra-passe (local) | grupo de armazém + grau / função de filial (local — §4–§6) |
| **Produção** | **Google OAuth** | continua local — **o Google nunca atribui funções** |

### 12.1 Ao criar um utilizador

Decida primeiro o tipo, depois crie o registo em conformidade:

| Se vão… | Criar | Também definir |
|---------------|--------|----------|
| Administrar o sítio | Superutilizador (`createsuperuser`) | — |
| Trabalhar no armazém | User + **grupo de armazém** + grau | §4 |
| Trabalhar numa filial | User (sem grupo) + **BranchMembership** | §6 |

O **email** que introduzir é o login deles. Em produção **tem de ser igual à conta Google com que iniciam sessão** (ver abaixo).

### 12.2 Início de sessão — desenvolvimento vs produção (Google OAuth)

- **Desenvolvimento:** os utilizadores iniciam sessão com **email + palavra-passe** em `/accounts/login/`.
- **Produção (Fase 7):** os utilizadores iniciam sessão com **Google OAuth** — a conta Google, p. ex. `xpt-user@gmail.com` — para **maior segurança** (autenticação forte do Google, sem palavras-passe guardadas na aplicação). O OAuth só para login já existe em desenvolvimento; a implementação em produção é a Fase 7.

### 12.3 Como o OAuth e as permissões interagem

1. O utilizador inicia sessão com o Google; o Google devolve o **email** da conta.
2. O CentCompras procura o **`User` cujo `email` seja esse endereço** e inicia sessão nesse registo.
3. As **permissões vêm desse registo local** — grupo de armazém + grau, ou membro de filial + função — **nunca do Google**.

Consequências:

- **Crie o `User` primeiro, com o mesmo email.** Integração: a sede cria a conta (email + grupo/função) em `/admin/`, depois a pessoa inicia sessão via OAuth e é associada a ela.
- **O Google não atribui funções.** O OAuth só prova *quem é*; §4–§6 continuam a decidir *o que pode fazer*.
- **Use email da empresa, não Gmail pessoal** (decisão bloqueada no plano). O endereço tem de ser igual ao `User.email` no registo.
- **Sem auto-provisionamento.** Se o email Google não corresponder a nenhum `User`, a pessoa **não tem acesso** — a sede tem de criar a conta primeiro.

### 12.4 Gestão de permissões (resumo)

Tudo em §4–§6 mantém-se inalterado pelo OAuth. As permissões estão em **grupos** (armazém) e **membros** (filial), definem-se em `/admin/` e sincronizam-se por código (§5). O OAuth só altera o passo de *início de sessão*.

---

## 13. FAQ

**P1. Criei um utilizador staff mas não consegue abrir `/admin/` — porquê?**
`/admin/` exige `is_superuser`, não só `is_staff`. Torne-o superutilizador ou (melhor) dê-lhe uma função de armazém/filial e envie-o para as consolas do sítio.

**P2. Um utilizador de filial pode iniciar sessão em `/admin/`?**
Não — nunca. O pessoal de filial tem `BranchMembership`, não login de superutilizador.

**P3. Adicionei uma permissão extra a um grupo de armazém e desapareceu — porquê?**
Os grupos de armazém são **geridos no código** e ressincronizados no migrate; permissões adicionadas à mão são apagadas. Altere o *grupo* ou o *grau* do utilizador em vez das permissões do grupo.

**P4. Um utilizador está em dois grupos de armazém — o que acontece?**
Evite. Se acontecer, o código escolhe o primeiro por ordem: **admins → managers → operators**. Atribua exatamente um grupo.

**P5. Como dou a alguém direitos de «aprovar»?**
Armazém: coloque-o em `warehouse_managers` e defina grau **2+** (grau 3 para tetos mais altos). Filial: dê-lhe a função **manager** nessa filial.

**P6. Como deixo um utilizador de filial corrigir o stock da filial?**
A função **admin** de filial pode `adjust_branch_stock` (em `/branch/receipts/`), com motivo. Operadores e gestores não podem.

**P7. Posso eliminar uma filial?**
Não — **desative-a** (desmarque `is_active`). O histórico mantém-se e os pedidos em curso terminam na mesma.

**P8. Onde defino os tetos de aprovação?**
Não em `/admin/`. Tetos de encomendas de compra do armazém → `/manage/approval-limits/`; tetos dos gestores de filial → `/manage/branch-approval-limits/`. Só administrador de armazém.

**P9. Porque é que o formulário User pede fuso horário?**
Cada utilizador tem fuso horário para as datas renderizadas no servidor estarem corretas para ele. A predefinição é `Europe/Lisbon`; só são aceites nomes IANA válidos.

**P10. O seed não criou superutilizador — como obtenho um?**
Execute `python manage.py createsuperuser` (email + palavra-passe). O seed cria de propósito só utilizadores de armazém e de filial.
