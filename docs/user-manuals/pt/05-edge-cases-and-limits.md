# CentCompras — Manual do utilizador: Casos limite, limites e resolução de problemas

**Referência** · Versão 1.0 · Para pessoal do armazém, pessoal de filial e administradores

> **Complemento de:** [Gestão de artigos](01-items.md) · [Encomendas de compra](02-purchase-orders.md) · [Receção de mercadorias e stock](03-goods-receipts.md) · [Filiais e Requisição interna](04-internal-requests.md) · [Referência de administração e superutilizador](06-admin-reference.md) · [Catálogo do gestor](07-manager-catalog.md) · [Fios de pedido](08-request-threads.md) · [Voz da Empresa](09-company-voice.md).
>
> Aqueles manuais ensinam o percurso normal. **Este é o manual de consulta** para os limites: os erros exatos que pode encontrar, os limites numéricos rígidos, as regras das máquinas de estados e o que *deliberadamente ainda não está construído*. Quando algo "não o deixa", consulte aqui.

---

## 1. Como usar este manual

- **"Recebi uma mensagem de erro"** → §2, encontre a mensagem, leia a correção.
- **"Há um limite em …?"** → §3 (tabela de limites numéricos).
- **"Porque não posso passá-lo de A para B?"** → §4 (máquinas de estados).
- **"Porque é que o meu número arredondou assim?"** → §5 (dinheiro e IVA).
- **"Podem duas pessoas sobrescrever-se?"** → §6 (concorrência e auditoria).
- **"X já está construído?"** → §7 (lacunas conhecidas).

Uma mensagem que "não o deixa" é a aplicação a **proteger o livro-razão** — não é um erro.

---

## 2. Mensagens de erro e o que significam

### 2.1 Catálogo (gestão de artigos — `/manage/items/`)

| Mensagem (exata) | Porque aparece | O que fazer |
|-----------------|----------------|------------|
| `Este código interno já está em uso.` | Os códigos internos são únicos, **sem distinção de maiúsculas/minúsculas** | Use outro código |
| `O código interno só pode conter letras, algarismos, pontos, hífens e sublinhados.` | O código contém um **espaço** ou um **carácter não permitido** (só `A–Z`, `a–z`, `0–9`, `.`, `-`, `_` são permitidos) | Corrija o código (ex.: `CEM-50`, `CABLE-2.5`) |
| `O código interno não pode ser alterado depois de o artigo ser guardado.` | Tentou renomear um código num artigo existente | Os códigos ficam bloqueados após o primeiro guardar (códigos vazios antigos podem ser definidos uma vez) |
| `O artigo não pode ser ativado (Génese): faltam campos obrigatórios ou o preço de retalho tem de ser superior a zero.` | A primeira ativação (Génese) exige código interno, descrição, unidade, IVA, família ativa, **preço de retalho > 0**, **fornecedor** e **preço de custo > 0** (guardar na consola, ação em lote **Reativar** no Django admin, ou `add_item --activate`) | Complete os campos antes de ativar |
| `Já existe uma família com este nome.` | Os nomes de família são únicos, sem distinção de maiúsculas/minúsculas | Use outro nome |
| `Já existe um fornecedor com este nome.` | Os nomes de fornecedor são únicos, sem distinção de maiúsculas/minúsculas | Use outro nome |
| `O nome da família é obrigatório.` / `O nome do fornecedor é obrigatório.` / `Description is required.` (A descrição é obrigatória.) | Campo obrigatório vazio | Preencha-o |
| `Cannot assign items to inactive family 'X'.` (Não é possível atribuir artigos a uma família inativa 'X'.) | Tentou colocar um artigo numa família desativada | Reative a família, ou escolha uma ativa |
| `O nome da sub-família é obrigatório.` | Criação de sub-família com nome vazio | Escreva um nome |
| `O nome da sub-família "X" já está a ser usado nesta família.` | Nome de sub-família duplicado na mesma família | Use outro nome |
| `Não é possível atribuir artigos a uma sub-família inativa 'X'.` | Formulário ou gravação do artigo usou uma sub-família desativada | Reative a sub-família, limpe o campo, ou escolha uma ativa |
| `A sub-família não pertence à família selecionada.` | A família do artigo e a família-mãe da sub-família não coincidem | Escolha uma sub-família da família selecionada, ou limpe a sub-família |
| `É obrigatório indicar um motivo para desativar um artigo.` | A desativação de artigo exige sempre um motivo | Escolha *Indisponível temporariamente / Deixou de ser comercializado / Outro* |
| `É obrigatório indicar um motivo para ativar um artigo.` | A reativação exige um motivo | Indique um (ex.: *Génese* na primeira ativação) |
| `Indique um endereço de email válido.` | O email do fornecedor está mal formado | Corrija o email (ou limpe-o) |
| `…selling price must be zero or greater.` (…o preço de venda tem de ser zero ou superior.) | Os preços não podem ser negativos | Indique 0 (significa "sem preço") ou um número positivo |
| `…reorder level must be zero or greater.` (…o nível de reposição tem de ser zero ou superior.) | O nível de reposição não pode ser negativo | Indique 0 ou um número positivo |
| `--retail-price must be greater than 0 when using --activate.` (`--retail-price` tem de ser superior a 0 ao usar `--activate`.) | A CLI `add_item` foi executada com `--activate` mas o preço de retalho falta ou é zero | Passe `--retail-price` com valor superior a 0 |
| `--supplier is required when using --activate.` | `add_item --activate` sem `--supplier` | Passe `--supplier` com o nome de um fornecedor ativo |
| `--cost-price is required when using --activate.` / `--cost-price must be greater than 0 when using --activate.` | `add_item --activate` sem preço de compra, ou custo zero | Passe `--cost-price` superior a 0 |
| `Cost price must be greater than zero for Genesis.` | Génese na consola ou `create_and_activate_item` com preço de custo ≤ 0 | Introduza preço de custo superior a zero |
| `supplier_id is required.` / `cost_price is required.` | POST **Novo artigo** na consola sem fornecedor ou custo | Escolha fornecedor e preço de custo antes da Génese |

**Os nomes de família são imutáveis** — a consola não tem "renomear". Se o nome estiver errado, desative e crie uma família nova (os artigos mantêm a família antiga; não pode acrescentar artigos novos a uma família inativa).

**Os nomes de sub-família e a família-mãe são imutáveis** após criar — o mesmo padrão das famílias. Desative e crie uma sub-família nova se a etiqueta estiver errada.

**Artigos novos:** confirme **Génese** ao guardar — criar, ativar e o **preço de fornecedor principal** são atómicos (sem órfão inativo se cancelar). **Código interno**, **fornecedor** e **preço de custo > 0** são obrigatórios na criação (código bloqueado após guardar; fornecedor/custo ficam na linha de preço — pode adicionar mais fornecedores depois no painel de fornecedores).

**Catálogo do gestor (`/manage/catalog/`)** — stock + preços só de leitura para o pessoal do armazém. Ver [Catálogo do gestor](07-manager-catalog.md).

| Mensagem (exata) | Porque aparece | O que fazer |
|-----------------|----------------|------------|
| `Sem artigos para mostrar.` | Não há artigos ativos em famílias ativas | Crie ou reative artigos na gestão de artigos |
| `Nenhum artigo corresponde a estes filtros.` | A pesquisa, família ou "só abaixo do ponto de encomenda" ocultaram todas as linhas | Limpe os filtros (*Todas as famílias*, desmarque as caixas) |
| `Não foi possível carregar o catálogo.` | A API do catálogo falhou | Atualize; se persistir, peça ajuda a um administrador |
| `Não foi possível concluir o pedido.` | O pedido falhou sem mensagem específica | Atualize; tente de novo |
| `Catalogue view permission required` (É necessária permissão de vista do catálogo) | Não é utilizador de armazém (típico para inícios de sessão só de filial) | Use `/branch/` e páginas da filial, ou peça à sede um grupo de armazém |

**Abaixo do ponto de encomenda** é `reorder_level > 0` **e** disponível ≤ ponto de encomenda. Ponto de encomenda **0** nunca sinaliza. Preço de compra = custo do fornecedor principal; senão o mais barato entre fornecedores **ativos** (senão —). **Incluir inativos** (`?include_inactive=1` na API) recarrega artigos desativados e artigos sob família inativa; a vista por defeito é só ativos. A coluna **Fornecedores** lista o principal em primeiro (★), depois os restantes por ordem alfabética. Os cabeçalhos das colunas são ordenáveis no browser.

### 2.2 Encomendas de compra (`/manage/purchase-orders/`)

| Mensagem | Porquê | O que fazer |
|---------|-----|------------|
| `Este fornecedor não tem preço para este artigo. Adicione-o em Fornecedores → Preços de fornecedor primeiro.` / `This supplier does not have a price for item X (id=N).` | Esse fornecedor não tem `SupplierItemPrice` para o artigo — **sem recurso a outro fornecedor** | Adicione um preço de fornecedor para esse fornecedor+artigo, ou escolha outro artigo |
| `Cannot use inactive supplier 'X'.` / `Cannot use inactive item 'X'.` (Não é possível usar fornecedor/artigo inativo 'X'.) | O fornecedor ou artigo foi desativado | Reative, ou escolha outro |
| `This purchase order already has a line for 'X'.` (Esta encomenda já tem uma linha para 'X'.) | Uma linha por artigo por encomenda (sem agregar) | Edite a quantidade da linha existente |
| `As linhas só podem ser alteradas enquanto a encomenda é um rascunho.` | Tentou adicionar/editar/remover uma linha depois de submeter | Só rascunhos são editáveis |
| `Adicione pelo menos uma linha antes de submeter.` | Submeter uma encomenda vazia | Adicione pelo menos uma linha |
| `A quantidade tem de ser maior que zero.` / `quantity is too large.` (a quantidade é demasiado grande) | Quantidade ≤ 0, ou ≥ 1 000 000 000 | Use uma quantidade em `(0, 1e9)` |
| `O custo unitário tem de ser zero ou superior.` | Custo unitário negativo | Indique 0 ou positivo |
| `…must be between 0 and 100.` (…tem de estar entre 0 e 100.) | Um desconto é negativo ou > 100% | Use 0–100 |
| `Os descontos comercial, financeiro e rappel não podem, juntos, ultrapassar 100%.` | As três % somam mais de 100 | Reduza-as |
| `Esta mudança de estado não é permitida.` | Transição ilegal | Ver §4 |
| `Não tem permissão para aprovar esta encomenda.` | Operador, ou grau demasiado baixo | Operadores nunca aprovam; gestores precisam de grau 2+ |
| `An approver is required.` (É necessário um aprovador.) | Aprovação sem utilizador | Erro interno/sistema — reporte |
| `Esta encomenda ultrapassa o seu limite de auto-aprovação.` / `Self-approval is limited to … EUR gross (this PO is …).` | Está a aprovar a **própria** encomenda acima do teto **próprio** | Peça a outro aprovador |
| `Esta encomenda ultrapassa o seu limite de aprovação.` / `Approval is limited to … EUR gross (this PO is …).` | Aprova encomenda de outra pessoa acima do seu teto | Peça a um aprovador de grau superior |
| `No approval limit is configured for this grade.` (Não há limite de aprovação configurado para este grau.) | Falta linha `ApprovalLimit` | Peça a um administrador do armazém para definir |
| `Only warehouse admins can change approval limits.` (Só administradores do armazém podem alterar limites de aprovação.) | Editar tetos como não-administrador | Só administrador do armazém |
| `É obrigatório indicar um motivo para rejeitar a encomenda.` | Rejeitar exige motivo | Escreva um |
| `É obrigatório indicar um motivo para fechar uma encomenda com quantidade por receber.` | Fecho manual (entrega parcial) exige motivo | Escreva um |
| `É obrigatório indicar um motivo para cancelar a encomenda.` | Cancelar exige motivo | Escreva um |
| `Uma encomenda com receções não pode ser cancelada. Feche-a para aceitar uma entrega parcial.` | Não pode cancelar uma encomenda aprovada que já recebeu mercadoria | Use **Encerramento parcial** (entrega incompleta) em vez disso |
| `Purchase order totals exceed the maximum supported value.` (Os totais da encomenda excedem o valor máximo suportado.) | Totais ≥ 1 000 000 000 000 | Reduza quantidades/preços |

### 2.3 Inventário — receção de mercadorias, saída de mercadoria, stock da filial

**Receção de mercadorias (`/manage/goods-receipts/`)**

| Mensagem | Porquê | O que fazer |
|---------|-----|------------|
| `Esta encomenda não pode receber mercadoria no estado atual.` / `Cannot receive goods against a purchase order with status 'X'.` | A encomenda não está **approved** (aprovada) ou **received** (recebida) | Aprove-a primeiro |
| `Não foi possível encontrar uma linha nesta encomenda.` / `Purchase order line not found on this purchase order.` | O id da linha não pertence a essa encomenda | Selecione de novo |
| `Cada linha da receção tem de ser um objeto válido com line_id e quantity_received.` | Linha mal formada | Corrija o formulário |
| `Uma linha da encomenda foi indicada mais do que uma vez nesta receção.` | Linha duplicada numa receção | Uma linha por linha da encomenda |
| `A quantidade recebida é inválida ou excede a quantidade em falta.` / `Received quantity X exceeds remaining Y for PO line N.` | Sobre-receção | Não pode receber mais do que encomendado |
| `Adicione pelo menos uma linha para receber.` | Receção vazia | Adicione uma linha |
| `O stock não pode ser ajustado abaixo de zero.` | Tornaria o stock em armazém negativo | Verifique as quantidades |
| `Não é possível reduzir o stock abaixo da quantidade reservada para requisições aprovadas.` / `Cannot reduce stock of 'X' below N reserved for approved requests.` | Um ajuste negativo roubaria unidades já reservadas para requisições | Encerre parcialmente ou cancele a reserva primeiro, depois ajuste |
| `É obrigatório indicar um motivo para ajustar o stock.` | `adjust_stock` exige motivo | Escreva um |

**Saída de mercadoria (armazém, `/manage/internal-requests/`)**

| Mensagem | Porquê | O que fazer |
|---------|-----|------------|
| `Cannot issue goods against a request with status 'X'.` (Não é possível emitir mercadoria contra uma requisição com estado 'X'.) | A requisição não está **approved** ou **fulfilling** | Só essas são emitíveis |
| `Request line not found on this request.` (Linha da requisição não encontrada nesta requisição.) | Id de linha errado | Selecione de novo |
| `Issued quantity X exceeds remaining Y for request line N.` (Quantidade emitida X excede o restante Y da linha N.) | Sobre-emissão face à requisição | Reduza |
| `Cannot issue X of 'Y': Z reserved for this request.` (Não é possível emitir X de 'Y': Z reservados para esta requisição.) | Sobre-emissão face à reserva desta requisição | Emita só a quantidade reservada, ou aguarde alocação de stock entrante |
| `Insufficient stock for 'X': N requested, M on hand.` (Stock insuficiente para 'X': N pedidos, M em armazém.) | Sobre-emissão face ao stock em armazém (rede de segurança) | O armazém tem de comprar primeiro |
| `No lines to issue.` (Sem linhas para emitir.) | Emissão vazia | Adicione uma linha |
| `A reason is required to short-close a request.` (É obrigatório indicar um motivo para encerrar parcialmente uma requisição.) | Encerramento parcial no armazém exige motivo | Escreva um |

**Receção na filial e stock da filial (`/branch/receipts/`)**

| Mensagem | Porquê | O que fazer |
|---------|-----|------------|
| `Cannot receive against a request with status 'X'.` (Não é possível receber contra uma requisição com estado 'X'.) | A requisição não está **shipped** ou **received** | Aguarde a expedição |
| `Goods issue line not found on this dispatch.` (Linha de saída de mercadoria não encontrada nesta expedição.) | Id de linha errado | Selecione de novo |
| `A goods issue line was provided more than once in this receipt.` (Uma linha de saída foi indicada mais do que uma vez nesta receção.) | Linha duplicada | Uma linha por linha de emissão |
| `Received quantity X exceeds shipped remaining Y.` (Quantidade recebida X excede o restante expedido Y.) | Sobre-receção face à expedição | Reduza |
| `Only branch admins can adjust branch stock.` (Só administradores de filial podem ajustar o stock da filial.) | Não-administrador tentou `adjust_branch_stock` | Só administrador de filial |
| `Branch stock cannot be adjusted below zero.` (O stock da filial não pode ser ajustado abaixo de zero.) | Saldo negativo na filial | Verifique as quantidades |
| `A reason is required to adjust branch stock.` (É obrigatório indicar um motivo para ajustar o stock da filial.) | Ajuste na filial exige motivo | Escreva um |
| `A reason is required to short-close a request.` (É obrigatório indicar um motivo para encerrar parcialmente uma requisição.) | Encerramento parcial na filial exige motivo | Escreva um |

### 2.4 Requisição interna (`/branch/requests/`) e filiais

| Mensagem | Porquê | O que fazer |
|---------|-----|------------|
| `Item 'X' has no wholesale price.` (O artigo 'X' não tem preço de grossista.) | Grossista = 0 — a requisição é precificada pelo grossista | Defina preço de grossista (armazém), ou escolha outro artigo |
| `This request already has a line for 'X'.` (Esta requisição já tem uma linha para 'X'.) | Uma linha por artigo (sem agregar) | Edite a linha existente |
| `Cannot use inactive item 'X'.` / `Cannot use inactive branch 'X'.` (Não é possível usar artigo/filial inativo 'X'.) | Artigo ou filial desativado | Reative, ou escolha outro |
| `Internal request lines can only be changed while the request is a draft.` (As linhas da requisição interna só podem ser alteradas enquanto a requisição é rascunho.) | Edição depois de submeter | Só rascunhos são editáveis |
| `Cannot submit a request without lines.` (Não é possível submeter uma requisição sem linhas.) | Requisição vazia | Adicione uma linha |
| `Cannot move an internal request from 'X' to 'Y'.` (Não é possível mover uma requisição interna de 'X' para 'Y'.) | Transição ilegal | Ver §4 |
| `You do not have permission to approve or cancel this request.` (Não tem permissão para aprovar ou cancelar esta requisição.) | Operador (ou cancelar aprovada como operador) | Só gestor/administrador |
| `Self-approval is limited to … EUR gross (this request is …).` (A auto-aprovação limita-se a … EUR bruto (esta requisição é …).) | Gestor a aprovar requisição própria acima do teto **próprio** (só no modo **com preços**) | Peça a outro gestor |
| `Approval is limited to … EUR gross (this request is …).` (A aprovação limita-se a … EUR bruto (esta requisição é …).) | Gestor acima do teto **outros** (só no modo **com preços**) | Peça a um aprovador superior |
| `No branch approval limit is configured for managers.` (Não há limite de aprovação de filial configurado para gestores.) | Falta `BranchApprovalLimit` | Administrador do armazém define |
| `A reason is required to reject a request.` (É obrigatório indicar um motivo para rejeitar uma requisição.) | Rejeitar exige motivo | Escreva um |
| `A reason is required to cancel an approved request.` (É obrigatório indicar um motivo para cancelar uma requisição aprovada.) | Cancelar aprovada exige motivo | Escreva um |
| `A request with goods issues cannot be cancelled.` (Uma requisição com saídas de mercadoria não pode ser cancelada.) | Mercadoria já expedida | Encerramento parcial em vez disso (ver §4) |
| `client_uuid is required.` (`client_uuid` é obrigatório.) | POST de sincronização offline sem UUID | Tente de novo na página de requisições da filial depois de voltar a ligar |
| `client_uuid must be a valid UUID.` (`client_uuid` tem de ser um UUID válido.) | Payload de sincronização offline mal formado | Atualize a página e crie um rascunho offline novo |
| `client_uuid is already in use on another branch.` (`client_uuid` já está em uso noutra filial.) | UUID de rascunho offline foi sincronizado noutra filial | Volte à filial onde criou o rascunho, depois abra `/branch/requests/` |
| `Request body must be valid JSON.` / `Request body must be a JSON object.` (O corpo do pedido tem de ser JSON válido / um objeto JSON.) | Corpo de sincronização/criação mal formado ou não-objeto | Tente de novo na página de requisições da filial; não envie arrays |
| `Unknown item id …` (Id de artigo desconhecido …) | Artigo de catálogo obsoleto ou inválido no payload offline | Atualize o catálogo online, depois recrie o rascunho offline |
| `Cached catalogue is for another branch. Connect to Wi-Fi to download this branch's catalogue.` (O catálogo em cache é de outra filial. Ligue o Wi-Fi para descarregar o catálogo desta filial.) | Navegação offline depois de mudar de filial sem atualizar | Ligue o Wi-Fi na filial atual para descarregar o respetivo catálogo |

### 2.5 Fios de pedido (`/branch/threads/`, `/manage/threads/`)

| Mensagem | Porquê | O que fazer |
|---------|-----|------------|
| `A subject is required.` / `Subject must be a string.` (É obrigatório um assunto. / O assunto tem de ser texto.) | Assunto vazio ou não-texto | Escreva um título curto |
| `Request body must be valid JSON.` / `Request body must be a JSON object.` | Corpo de criar/responder/fechar mal formado | Use o formulário do sítio |
| `A message is required.` / `Message must be a string.` (É obrigatória uma mensagem. / A mensagem tem de ser texto.) | Primeira mensagem / resposta vazia ou não-texto | Escreva a mensagem |
| `This thread is closed. No further messages can be posted.` (Este fio está fechado. Não podem ser publicadas mais mensagens.) | Resposta depois de fechar | Abra um fio novo |
| `Only the person who opened the thread can close it.` (Só quem abriu o fio o pode fechar.) | Não é o autor e não pode substituir | Peça ao autor, ou a um gestor/administrador de filial / administrador do armazém |
| `A reason is required to close a thread.` (É obrigatório indicar um motivo para fechar um fio.) | Fechar sem motivo válido | Escolha Pedido satisfeito ou Outro |
| `A reason text is required when 'Other' is selected.` (É obrigatório texto de motivo quando 'Outro' está selecionado.) | Outro com caixa de texto vazia | Escreva o motivo |
| `Satisfaction must be between 1 and 5 stars.` (A satisfação tem de estar entre 1 e 5 estrelas.) | Classificação em falta, decimal ou fora do intervalo | Escolha 1–5 estrelas inteiras (só ao fechar pelo autor) |
| `Cannot use inactive branch 'X'.` (Não é possível usar filial inativa 'X'.) | Abrir fio numa filial desativada | Mude para uma filial ativa |
| `The opener must be a member of the branch.` (Quem abriu tem de ser membro da filial.) | Ao nível de serviço: o autor não é membro dessa filial | Abra a partir da sua filial |
| `Only warehouse staff can link items to a thread.` (Só pessoal do armazém pode associar artigos a um fio.) | Utilizador de filial tentou associar | Utilizadores de armazém associam em `/manage/threads/` |
| `One or more items were not found.` (Um ou mais artigos não foram encontrados.) | Associação usou id de artigo obsoleto ou desconhecido | Pesquise de novo e escolha um artigo ativo do catálogo |
| `No items to link.` (Sem artigos para associar.) | Pedido de associação vazio | Escolha pelo menos um artigo |
| `branch_id must be an integer.` (`branch_id` tem de ser um inteiro.) | Lista de armazém `?branch_id=` não é um número | Use o filtro de filial, ou omita-o |

**Satisfação** só fica registada quando o **autor** fecha (1★ por defeito). Fecho por substituição deixa satisfação vazia.

**Não lidos:** GET das mensagens de um fio **não** o marca como lido. Clicar o fio na lista (POST mark-read) sim.

### 2.6 Voz da Empresa (`/company-voice/`)

| Mensagem (exata) | Porque aparece | O que fazer |
|-----------------|----------------|------------|
| `O texto da mensagem não pode estar vazio.` | Publicação/comentário em branco ou só espaços | Escreva uma mensagem |
| `O texto da mensagem não pode exceder 4000 caracteres.` | Corpo com mais de 4000 caracteres | Encurte o texto |
| `O prazo de edição expirou.` | Editar mais de 15 minutos depois de publicar | Ainda pode eliminar; não pode editar |
| `Só o autor pode alterar ou eliminar esta mensagem.` | Outra pessoa tentou editar/eliminar | Só o autor pode |
| `Esta mensagem foi eliminada.` | Segunda eliminação, ou editar linha já eliminada | Atualize o feed |
| `Esta publicação foi eliminada.` | Comentar numa publicação que o autor já eliminou | Atualize; a publicação é um marcador de eliminação |
| `Etiqueta inválida.` | Etiqueta não é elogio/preocupação/sugestão/desejo | Escolha uma etiqueta da lista, ou deixe sem etiqueta |
| `O pedido tem de ser JSON válido.` | Corpo de API mal formado | Use o formulário do sítio |
| `O texto tem de ser uma cadeia de caracteres.` | API enviou corpo não-texto | Envie texto |
| `is_anonymous tem de ser um booleano.` | API enviou `"false"` / `1` em vez de `true`/`false` | Use um booleano real |
| `Esta mensagem foi alterada noutro separador. Atualize e tente de novo.` | Duas edições da mesma mensagem; a segunda usou `updated_at` obsoleto (HTTP **409**) | Atualize e volte a aplicar a alteração |
| `updated_at é obrigatório.` / `updated_at tem de ser um instante ISO.` | PATCH omitiu ou token de versão mal formado | Atualize; o sítio envia isto automaticamente |

**(editado)** fica registado como `edited_at` — uma publicação nova nunca é etiquetada como editada. Contagens de respostas ignoram comentários eliminados logicamente.

### 2.7 Conta, permissões e isolamento

| O que vê | Quando | Significado |
|--------------|------|---------|
| `Authentication required` (Autenticação necessária) (401, API JSON) | Sem sessão iniciada | Inicie sessão |
| `Account is inactive` (Conta inativa) (403) | A conta foi desativada — a sessão termina automaticamente | Contacte o administrador |
| `Branch membership required` (É necessária adesão à filial) (403) | Utilizador só de armazém abriu uma página `/branch/…` | Precisa de função de filial |
| `No active branch selected` (Nenhuma filial ativa selecionada) (403) | Utilizador de filial sem filial escolhida | Use o seletor |
| `Internal request view permission required` (É necessária permissão de vista de requisições internas) (403) | Utilizador não-armazém abriu `/manage/internal-requests/` | Precisa de função de armazém |
| `Missing permission: …` (Permissão em falta: …) (403) | Falta uma capacidade específica | Ver tabelas de funções em 01–04 |
| **404 "not found"** (não encontrado) | Requisição/expedição de **outra filial** | Dados de filial são **404**, não 403 — outras filiais são invisíveis, não apenas proibidas |

> 💡 **403 vs 404:** *"Não pode fazer isso com a sua função"* → **403**. *"Essa linha pertence a outra filial"* → **404** (de propósito, para não poder sequer confirmar que existe).

---

## 3. Limites numéricos e precisão

| Campo | Armazenamento | Intervalo válido | Regra extra |
|-------|---------|-------------|------------|
| **Quantidade** (linha de encomenda, linha de requisição, receção, emissão) | `Decimal(12,3)` | `> 0` e `< 1 000 000 000` | 3 casas decimais |
| **Custo unitário / preço unitário / preços de venda / preço de custo** | `Decimal(12,2)` | `≥ 0` | 2 casas decimais |
| **Totais aprovados e limites de aprovação** | `Decimal(14,2)` | `< 1 000 000 000 000` | protegido contra overflow |
| **Descontos** (comercial / financeiro / rappel) | `Decimal(5,2)` | cada `0–100`; **combinados ≤ 100** | percentagens |
| **Taxa de IVA** | `Decimal(5,4)` | fração `0 … 1` | ex.: `0.16` = 16% |
| **Nível de reposição** | `Decimal(12,3)` | `≥ 0` | 0 = "sem disparo de encomenda" |
| **Código interno** | `CharField` máx. **64** | obrigatório na criação na consola; só letras, algarismos, `.`, `-`, `_`; **guardado em maiúsculas**; **imutável após guardar** (definir-se-vazio uma vez para legado) | único, sem distinção maiúsculas/minúsculas |
| **Preço de retalho (Génese)** | `Decimal(12,2)` | **> 0** obrigatório na criação na consola / primeira ativação | grossista/especial podem ficar 0 |
| **Motivo / notas (campos de motivo)** | `CharField` / `TextField` | motivo ≤ **255 carateres** | motivo demasiado longo rejeitado |
| **Email** | `EmailField` | email válido | fornecedor e utilizador |
| **Saldos de stock** (`Item.quantity`, `BranchItemStock.quantity`) | `Decimal(12,3)` | `≥ 0` | não pode ficar negativo |
| **Quantidade reservada** (`InternalRequestLine.quantity_reserved`) | `Decimal(12,3)` | `≥ 0` e `≤` quantidade da linha | reivindicação sobre stock de armazém, não movimento de livro-razão |
| **Corpo Voz da Empresa** | `TextField` | **1–4000** carateres após trim | vazio rejeitado |
| **Janela de edição Voz da Empresa** | — | **15 minutos** desde `created_at` | só autor |

**Arredondamento:** toda a aplicação usa **half-away-from-zero** (`ROUND_HALF_UP` — não arredondamento bancário). Custos unitários arredondam primeiro a **4 casas decimais**, depois montantes de linha (líquido / IVA / bruto) arredondam a **2 casas decimais**.

---

## 4. Máquinas de estados (cada transição legal)

### 4.1 Encomenda de compra

```text
draft ──submit──▶ submitted ──approve──▶ approved ──receive──▶ received ──close──▶ closed
  │                  │                     │                       │
  │ cancel           └─reject─▶ rejected  └─cancel─▶ cancelled   └── (fecho manual = entrega parcial)
  ▼                                        └──reopen─▶ draft
cancelled
```

- Só linhas em **draft** (rascunho) são editáveis.
- **Descartar Rascunho** (`draft → cancelled`) não exige motivo; ação só na lista.
- **Cancelar** (approved → cancelled) exige motivo e **zero receções**; caso contrário **fechar** (entrega parcial).
- **Rejeitar** exige motivo; **reabrir** move `rejected → draft`.

### 4.2 Requisição interna (requisição)

```text
draft ──submit──▶ submitted ──approve──▶ approved ──issue──▶ fulfilling ──issue──▶ shipped
  │                  │                     │              │                         │
  │ cancel           └─reject (motivo)     └─cancel       └─enc. parcial wh         │
  ▼                                       │   (sem expedição)│                         ▼
cancelled                                cancelled         ▼               shipped ──receive──▶ received ──receive──▶ closed
                                                          closed                      │                     ▲
                                                                                      └── short-close ──────┘
```

**Transições "saltadas"** (ambas acontecem automaticamente, na mesma ação):

- A primeira emissão que conclui o lado do armazém → **`approved → shipped`** diretamente (nunca persiste `fulfilling`).
- A primeira receção que conclui o lado da filial → **`shipped → closed`** diretamente (nunca persiste `received`).

**Dois encerramentos parciais:**

| Lado | Quem | Efeito |
|------|-----|--------|
| Armazém (`/manage/internal-requests/`) | Gestor grau 2+ / administrador, motivo | **Sem expedição ainda** (`approved`, zero emitido) → **closed**. **Emissão parcial** (`fulfilling`) → restante não expedido dado como baixa → **shipped** |
| Filial (`/branch/receipts/`) | Gestor / administrador, motivo | restante não recebido dado como baixa → **closed** |

**Sem cancelar depois da primeira saída de mercadoria** — só encerramento parcial.

**Reserva (D32):**

- **Aprovar** reserva `min(restante, em armazém não reservado)` em cada linha. Reserva zero ainda aprova (a requisição espera stock).
- **Emitir** só pode expedir a partir da `quantity_reserved` dessa linha. Receções entrantes / ajustes positivos preenchem backorders mais antigos primeiro (FIFO por `approved_at`, depois id da requisição, depois id da linha).
- **Cancelar** (aprovada, sem emissão) e **encerramento parcial no armazém** libertam a reserva, depois realocam unidades livres a linhas em espera.

### 4.3 Entidades inativas (bloqueio 9 / D16)

- **Filial inativa:** bloqueia novas requisições/linhas/submeter/aprovar, mas **em curso** emissão / receção na filial / encerramento parcial continuam a funcionar (stock em trânsito não fica preso).
- **Artigo/família inativos:** bloqueiam novas linhas / submeter / aprovar. Linhas existentes mantêm os respetivos **instantâneos** e podem ser cumpridas.

---

## 5. Dinheiro, IVA e casos limite de preços

| Caso | Comportamento |
|------|-----------|
| **Preço de venda = 0** | Significa "ainda sem preço" — mas uma linha de requisição com **grossista = 0 é rejeitada** |
| **Preço de compra (custo)** | Do preço do fornecedor **principal**; se não houver principal, o fornecedor **mais barato**; se não houver preços → **sem custo mostrado** |
| **Um principal por artigo** | Marcar um fornecedor novo como principal **desmarca** automaticamente o antigo (imposto na BD) |
| **Preço de fornecedor** | Só para fornecedor **ativo** **e** artigo; um custo por fornecedor×artigo |
| **Totais aprovados** | **Congelados na aprovação** — alterações posteriores de preço/IVA não reescrevem uma encomenda/requisição aprovada (linhas mantêm instantâneos) |
| **IVA** | Guardado como fração (`0.16`), aplicado por linha na aprovação |
| **Descontos** | Comercial + financeiro + rappel são todos % simples por agora; combinados > 100% é rejeitado |

---

## 6. Garantias de concorrência e auditoria

Estas são garantias, não "melhor esforço":

- **Sem perda de atualizações / sem sobre-venda:** cada gravação que toca stock ou uma encomenda **bloqueia as linhas** (`select_for_update`), e artigos de stock são bloqueados numa **ordem fixa (ordenada)** para evitar deadlocks. Duas pessoas a receber a última unidade: uma tem sucesso, a outra recebe erro explícito de "stock insuficiente".
- **Reserva FIFO no armazém:** aprovar retém a parte livre para essa requisição. Uma filial posterior não pode ser emitida com essas unidades. A emissão fica limitada a `quantity_reserved` da linha. Stock entrante é oferecido primeiro ao backorder `approved`/`fulfilling` mais antigo.
- **Livros-razão só de append:** `StockMovement` e `BranchStockMovement` nunca são editados ou eliminados — só linhas novas. Os `Item.quantity` / `BranchItemStock.quantity` em cache são **calculados** a partir do livro-razão; se alguma vez discordarem, o livro-razão é a verdade.
- **Instantâneos congelados:** linhas de encomenda e de requisição registam descrição, código, unidade, IVA, preço na criação/aprovação, para edições posteriores de dados mestres não reescreverem o histórico.
- **Auditoria por desenho:** cada alteração de criar/atualizar/ciclo de vida escreve uma linha `*ChangeLog` (`quem`, `ação`, `alterações`, `motivo`, `quando`). Não há eliminação silenciosa — desativação/cancelamento em vez disso. Voz da Empresa usa `VoiceChangeLog` (criado / editado / eliminado) e placeholders de **eliminação lógica**; o Django admin não pode eliminar fisicamente linhas Voice.
- **Bloqueio de linha Voz da Empresa:** `delete_post` e `add_comment` bloqueiam a publicação-mãe (`select_for_update`). Um primeiro comentário concurrente com eliminação da publicação-mãe não deixa sub-fio vivo num marcador de eliminação. Dois primeiros comentários partilham um sub-fio. Edições exigem o `updated_at` do caller e devolvem **409** numa versão obsoleta.
- **Isolamento:** uma filial não pode ler linhas de outra filial (404).

---

## 7. Lacunas conhecidas (ainda não construídas)

Estes são adiamentos deliberados — confirme antes de assumir que existem:

| Lacuna | Estado |
|-----|--------|
| **Reposição de palavra-passe** | Sem reposição self-service; um administrador repõe |
| **Limitação de taxa de início de sessão** | **Feito** — 5 falhas / 15 min (`accounts/throttle.py`; configurável) |
| **Email** | `notify_supplier_on_approval` é um **stub** (só regista em log) |
| **Offline / PWA** | Não construído (Fase 6 — após a revisão de chrome de 25 ago) |
| **Google OAuth / registo público** | Início de sessão Google só-login **está** implementado; registo público não |
| **Encomenda de compra ligada / automática** | Existe seam (FK de encomenda anulável nas linhas de requisição) mas sem automatismo |
| **Preços por filial** | Só os 3 preços de venda globais (retalho/grossista/especial) |
| **Categorias / pesquisa vectorial ou LLM / importação em massa** | Não construído |

---

## 8. Casos limite de conta e sessão

- **Início de sessão é por email** — não há campo de nome de utilizador.
- **Desativado a meio da sessão:** o pedido seguinte devolve **"Account is inactive"** (403) e termina a sessão — mesmo com cookie de sessão ainda válido.
- **Fuso horário:** cada utilizador tem um fuso horário (por defeito `Europe/Lisbon`); fusos inválidos são rejeitados ao guardar. Datas renderizadas no servidor aparecem no fuso do visualizador; guardadas em UTC.
- **`/admin/`** é **só superutilizador**. Pessoal de armazém e de filial nunca entra no Django admin.
- **Utilizador duplo armazém + filial:** depois do início de sessão aterram no **painel do armazém** (`/`); páginas da filial continuam acessíveis por URL/seletor.

---

## 9. Árvores de decisão (referência rápida)

**"Não consigo cancelar."**
- Encomenda: tem receções? → **Encerramento parcial** (entrega incompleta), não cancelar.
- Requisição: mercadoria já emitida? → **encerramento parcial** (armazém ou filial), não cancelar.

**Fornecedor deixou de fornecer um artigo depois da encomenda aprovada.**
- Submeter/aprovar bloqueiam se faltar o preço de fornecedor; depois da aprovação, a receção usa a linha congelada.
- Não pode remover a linha — **cancelar** (zero receções) ou **encerramento parcial** após receção parcial.
- Requisição, sem emissão ainda, mas sou operador → só gestor/administrador.

**"Não consigo aprovar."**
- Operador → nunca.
- Gestor grau 1 → precisa de grau 2+ (encomenda de armazém) / qualquer gestor (filial, dentro dos tetos).
- Acima do meu teto → peça a um aprovador de grau superior.
- "No approval limit configured" → administrador do armazém tem de definir.

**"Não consigo adicionar uma linha."**
- Artigo inativo / família inativa / fornecedor inativo → reative.
- Grossista = 0 (requisição) / sem preço de fornecedor (encomenda) → corrija preços.
- Artigo duplicado no documento → edite a linha existente.

**"O meu código interno foi rejeitado."**
- Espaços ou símbolos (ex.: `@`, `#`) → use só letras, algarismos, `.`, `-`, `_`.
- Código já usado (sem distinção maiúsculas/minúsculas — `cem-50` colide com `CEM-50`) → escolha outro.
- Minúsculas são aceites — fica **guardado em maiúsculas**.

**"Recebi 'insufficient stock' / 'cannot issue … reserved'."**
- Emissão: esta requisição não tem reserva (ou não suficiente) para essa quantidade — uma requisição aprovada anterior pode estar a reter as unidades. Compre, espere, ou encerre parcialmente a reserva anterior (motivo obrigatório).
- Receção (filial): indicou mais do que a expedição enviou.

---

## 10. Referências cruzadas

- [Gestão de artigos](01-items.md) — catálogo, preços, famílias, fornecedores, preços de fornecedor.
- [Encomendas de compra](02-purchase-orders.md) — fluxo de encomendas, descontos, aprovação.
- [Receção de mercadorias e stock](03-goods-receipts.md) — receção, livro-razão de stock, ajustes.
- [Filiais e Requisição interna](04-internal-requests.md) — circuito filial → armazém → filial.
- [Catálogo do gestor](07-manager-catalog.md) — stock só de leitura + preços do armazém (`/manage/catalog/`).
- [Fios de pedido](08-request-threads.md) — pedidos de lacunas de catálogo entre filial e armazém.
