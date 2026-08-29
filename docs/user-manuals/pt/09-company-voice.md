# Voz da Empresa — manual do utilizador

A Voz da Empresa é uma caixa de sugestões interna para todo o pessoal do CentCompras. Qualquer pessoa com sessão iniciada (armazém ou filial) pode publicar elogios, preocupações, sugestões ou desejos. Cada publicação pode ter um fio de resposta inline (um nível de sub-discussão).

**URL:** `/company-voice/`

---

## 1. Quem pode usar

| Função | Acesso |
|------|--------|
| Admin / gestor / operador de armazém | Ler e publicar |
| Admin / gestor / operador de filial | Ler e publicar |
| Superutilizador Django | Igual aos outros utilizadores na aplicação; `/admin/` é só inspeção (sem eliminação permanente) |

Não é necessário escolher filial. Utilizadores de armazém e de filial partilham o mesmo feed.

Abra a engrenagem **Definições** (canto superior direito) para **Sessão iniciada como** e uma ligação pequena **Terminar sessão** na linha do título. **Ajuda** é o ícone azul **?** junto à engrenagem (placeholder). O **Idioma** (English / Português) define-se no painel do pessoal (`/`) ou no painel da filial (`/branch/`) e memoriza-se neste browser.

**CentCompras** (canto superior esquerdo) devolve-o ao seu painel: **`/`** para o pessoal do armazém, **`/branch/`** para o pessoal só de filial. Não envia o pessoal de filial para `/` (essa página exige uma permissão de catálogo do armazém).

---

## 2. Publicar

1. Abra **Voz da Empresa** no painel do pessoal (`/`) ou aceda a `/company-voice/`.
2. Opcionalmente escolha uma **etiqueta**: Elogio, Preocupação, Sugestão ou Desejo (ou deixe sem etiqueta).
3. Escreva a mensagem na área de texto (máx. **4000** caracteres).
4. Opcionalmente marque **Publicar anonimamente** — outros utilizadores veem **Anonymous** / **Anónimo** em vez do seu nome de apresentação.
5. Clique em **Publicar**.

Use **Atualizar** para carregar publicações e respostas escritas por outras pessoas desde que abriu a página. O seu próprio Publicar / Enviar / Guardar / Eliminar bem-sucedido já recarrega o feed.

### Nomes de apresentação

- **Publicação com nome:** o seu primeiro nome se estiver definido na conta; caso contrário a parte do email antes de `@`.
- **Publicação anónima:** mostrada como **Anonymous** (inglês) ou **Anónimo** (português) para todos (o autor continua guardado no servidor para auditoria).

---

## 3. Respostas (sub-fios)

- Clique em **Responder** (ou na contagem de respostas) sob uma publicação para expandir a discussão inline.
- Qualquer pessoa pode adicionar o primeiro comentário — isso abre o único sub-fio dessa publicação.
- Cada publicação de topo pode ter **no máximo um** sub-fio (sem aninhamento mais profundo).
- Os comentários suportam a mesma caixa **anónimo** que as publicações de topo.
- A contagem de respostas é só de comentários **ativos** — comentários eliminados continuam visíveis como `[Eliminado pelo autor]` mas não entram na contagem.

---

## 4. Editar e eliminar

| Ação | Quem | Regra |
|--------|-----|------|
| **Editar** | Só o autor | Nos **15 minutos** após publicar. A ligação Editar desaparece quando o prazo expira (mesmo com a página aberta). |
| **Eliminar** | Só o autor | Eliminação suave — o conteúdo é substituído por `[Eliminado pelo autor]` |

- Eliminar uma **publicação de topo** elimina também em suave todo o sub-fio e todos os comentários.
- Eliminar um **comentário** remove só esse comentário.
- **(editado)** aparece junto à data/hora só após um guardar real — uma publicação nova nunca é marcada como editada.
- Guardar uma edição quando outro separador já guardou a mesma mensagem devolve conflito; **Atualize** e tente de novo.
- Prima **Escape** para cancelar uma edição em curso. Mudar de idioma ou expandir outra resposta mantém qualquer comentário que estivesse a escrever.

---

## 5. Mensagens do servidor (erros)

| Situação | Mensagem (EN) | Mensagem (pt-PT) | `code` |
|-----------|----------------|------------------|--------|
| Corpo vazio | `Message body cannot be empty.` | `O texto da mensagem não pode estar vazio.` | `empty_body` |
| Corpo demasiado longo | `Message body cannot exceed 4000 characters.` | `O texto da mensagem não pode exceder 4000 caracteres.` | `body_too_long` |
| Editar após 15 minutos | `The edit window has expired.` | `O prazo de edição expirou.` | `edit_window_expired` |
| Não é o autor | `Only the author can change or delete this message.` | `Só o autor pode alterar ou eliminar esta mensagem.` | `not_author` |
| Já eliminado | `This message has been deleted.` | `Esta mensagem foi eliminada.` | `already_deleted` |
| Comentário em publicação eliminada | `This post has been deleted.` | `Esta publicação foi eliminada.` | `post_deleted` |
| Etiqueta inválida | `Invalid tag.` | `Etiqueta inválida.` | `invalid_tag` |
| JSON inválido | `Request body must be valid JSON.` | `O pedido tem de ser JSON válido.` | `invalid_json` |
| Corpo não é string | `Body must be a string.` | `O texto tem de ser uma cadeia de caracteres.` | `invalid_body` |
| Flag anónimo não booleano | `is_anonymous must be a boolean.` | `is_anonymous tem de ser um booleano.` | `invalid_anonymous` |
| Edição obsoleta (outro separador guardou primeiro) | `This message was changed in another tab. Refresh and try again.` | `Esta mensagem foi alterada noutro separador. Atualize e tente de novo.` | `stale_edit` (HTTP **409**) |

O sítio mostra a cadeia portuguesa quando o idioma é Português.

---

## 6. FAQ

**Posso editar anonimamente depois de publicar?**  
Sim, nos 15 minutos, se for o autor. A flag anónima fica fixa na criação.

**Os administradores de armazém podem remover a publicação de outra pessoa?**  
Não a partir do sítio. Os superutilizadores podem **inspecionar** registos na administração Django (`/admin/`) — não podem eliminar permanentemente linhas da Voz. Os autores eliminam em suave em `/company-voice/`.

**O feed é paginado?**  
Não na primeira versão — todo o histórico carrega numa vista com scroll.

**Em que difere dos Fios de pedido?**  
Os Fios de pedido (`/branch/threads/`, `/manage/threads/`) são para artigos em falta no catálogo entre uma filial e o armazém. A Voz da Empresa é feedback à escala da empresa visível para todo o pessoal.

**Há registo de auditoria?**  
Sim. Criar, editar e eliminar escrevem uma linha `VoiceChangeLog` (quem, ação, quando). Os logs rotativos da aplicação são extra, não a fonte de verdade.
