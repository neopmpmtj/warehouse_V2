# CentCompras — Plano da apresentação (pt-PT)

**Versão:** 1.0 · **Data:** 26 agosto 2026  
**URL:** `/presentation/pt/` (atalho: `/presentation/`) · **Inglês:** `/presentation/en/`  
**Idioma:** Português (pt-PT) · Plano EN: [`PLAN-en.md`](PLAN-en.md)  
**Público:** Armazém central, gestores e operadores de filial, direção

---

## Objetivo

Comunicar três mensagens centrais:

1. **Os dados são o novo petróleo** — quanto mais cedo o pessoal usar o CentCompras no dia a dia, mais cedo a empresa terá informação fiável para gráficos e decisões.
2. **Circuito fechado** — do artigo ao stock, passando por aprovisionamento, autorização e expedição.
3. **Circularidade** — quando o artigo não existe, o ciclo começa noutro sítio (fios de pedido) e fecha com feedback humano (satisfação no fio + Voz da Empresa).

A apresentação é **informativa** (não expõe dados reais). Gráficos marcados como **visão futura** são ilustrativos.

---

## Narrativa (arco em 4 actos)

| Acto | Slides | Mensagem |
|------|--------|----------|
| **I — Porquê** | 1–4 | Contexto, metáfora dos dados, o que já se regista hoje |
| **II — Circuito fechado** | 5–11 | Fluxo armazém: catálogo → compras → aprovação → stock → filial |
| **III — Circularidade** | 12–14 | Artigo inexistente → fio → catálogo → requisição → feedback |
| **IV — Chamada à acção** | 15–16 | Papéis, próximos passos, começar já |

---

## Mapa slide a slide

### Slide 1 — Capa
- **Título:** CentCompras — Logística centralizada com filiais
- **Subtítulo:** Dados, circuitos e circularidade
- **Notas:** Apresentar o sistema como plataforma única (PostgreSQL = fonte de verdade).

### Slide 2 — O cenário
- Armazém central + filiais satélite
- Hoje: catálogo, encomendas de compra, receções, requisições, fios, Voz da Empresa, offline PWA nas filiais
- **Notas:** Não é um protótipo — fases 0–6 concluídas (548 testes).

### Slide 3 — Os dados são o novo petróleo
- Metáfora: petróleo bruto vs refinado; dados brutos vs decisões
- Cada clique gera eventos estruturados (movimentos de stock, estados de PO, aprovações, auditoria)
- **Notas:** Enfatizar que não é preciso esperar por gráficos para começar a usar.

### Slide 4 — O que o sistema já regista
- Tabela: `StockMovement`, `ItemChangeLog`, estados de PO, `InternalRequest`, `ThreadMessage`, `VoicePost`
- **Notas:** Ligar a modelos reais do código; zero digitação directa de quantidades.

### Slide 5 — Visão futura: gráficos *(mock)*
- Gráficos ilustrativos: stock ao longo do tempo, POs por estado, requisições por filial
- Etiqueta visível: **VISÃO FUTURA — dados reais acumulam-se com o uso**
- **Notas:** Honesto sobre o que existe vs. o que virá.

### Slide 6 — Dois mundos, um sistema
- Armazém (`/manage/…`) vs filial (`/branch/…`)
- Papéis: admin/gestor/operador (armazém e filial)
- **Notas:** Grupos de armazém ≠ funções de filial.

### Slide 7 — Circuito fechado (diagrama)
- SVG: Catálogo → Aprovisionamento → Autorização → Stock central → Requisição → Expedição → Receção filial
- **Notas:** Visão de pássaro antes de detalhar cada etapa.

### Slide 8 — Catálogo e preços
- `/manage/items/` — famílias, artigos, `internal_code`, preços de venda e fornecedor
- Genesis: activação com preço de retalho > 0
- **Notas:** Artigo inactivo até qualificação.

### Slide 9 — Aprovisionamento
- `/manage/purchase-orders/` — rascunho → submetido → aprovado → recebido
- Linha rejeitada se fornecedor sem preço para o artigo
- **Notas:** Ligação a `SupplierItemPrice`.

### Slide 10 — Autorização
- Grau + limites EUR brutos (`/manage/approval-limits/`)
- Filial: tetos em `/manage/branch-approval-limits/`
- **Notas:** Operadores nunca aprovam POs.

### Slide 11 — Stock central
- `/manage/goods-receipts/` → livro-razão `StockMovement`
- Reserva FIFO (D32): disponível = físico − reservado
- **Notas:** `Item.quantity` só via movimentos.

### Slide 12 — Requisição interna
- Filial: rascunho → aprovação → armazém emite (`/manage/internal-requests/`)
- Offline: rascunhos em fila local (PWA)
- **Notas:** Aprovar nunca falha por falta de stock; reserva o que há.

### Slide 13 — Receção na filial
- `/branch/receipts/` — stock da filial sobe
- Livro-razão `BranchStockMovement`
- **Notas:** Fecha o circuito filial.

### Slide 14 — Circularidade (diagrama)
- Artigo não existe → `/branch/threads/` → diálogo → criar artigo → ligar → requisição normal → fechar fio (satisfação)
- **Notas:** Fio ≠ encomenda; artigo criado no fluxo normal do catálogo.

### Slide 15 — Feedback contínuo
- Voz da Empresa (`/company-voice/`) — elogios, preocupações, sugestões
- Fios: classificação de satisfação ao fechar
- **Notas:** Fecha o ciclo humano.

### Slide 16 — Próximos passos
- Começar já: cada transacção alimenta o futuro analítico
- Formação por papel; manuais em `docs/user-manuals/pt/`
- Fase 7: preparação para produção
- **Notas:** Chamada à acção concreta.

---

## Recursos técnicos

| Componente | Localização |
|------------|-------------|
| Plano (este ficheiro) | `docs/presentation/PLAN-pt-PT.md` |
| Plano inglês | `docs/presentation/PLAN-en.md` |
| App Django | `presentation/` |
| Template PT | `presentation/templates/presentation/deck_pt.html` |
| Template EN | `presentation/templates/presentation/deck_en.html` |
| CSS / JS | `presentation/static/presentation/css/deck.css`, `js/deck.js` |
| Rota PT | `/presentation/` ou `/presentation/pt/` |
| Rota EN | `/presentation/en/` |

### Navegação do deck
- Setas ← →, Espaço, Page Up/Down
- Barra de progresso; contador de slides
- `F` ecrã inteiro; `?` ajuda
- Responsivo (projector + tablet)

### Acessibilidade
- `lang="pt-PT"` no HTML
- Contraste alto; texto legível em projector
- Diagramas em SVG inline (sem dependência de rede)

---

## Tradução EN

Versão inglesa disponível em **`/presentation/en/`** — ver [`PLAN-en.md`](PLAN-en.md). Templates separados (`deck_pt.html` / `deck_en.html`); CSS e JS partilhados.

---

## Referências no código

| Conceito | App / ficheiro |
|----------|----------------|
| Catálogo | `products/services.py`, `/manage/items/` |
| Encomendas de compra | `procurement/`, `/manage/purchase-orders/` |
| Stock | `inventory/services.py`, `StockMovement` |
| Requisição | `orders/`, `/branch/requests/` |
| Fios | `threads/`, `/branch/threads/` |
| Voz da Empresa | `company_voice/`, `/company-voice/` |
| Filiais | `branches/`, `ActiveBranchMiddleware` |
| Manuais pt-PT | `docs/user-manuals/pt/` |
