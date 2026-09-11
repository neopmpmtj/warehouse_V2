from django.test import TestCase

from presentation.views import DEMO_LOGIN_URL, DEMO_PASSWORD, SLIDE_COUNT


def _slide_html(content, number):
    start = content.index(f'data-slide="{number}"')
    end = content.index("</section>", start)
    return content[start:end]


class PresentationDeckTests(TestCase):
    def test_presentation_pt_default_loads(self):
        response = self.client.get("/presentation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Os dados são o novo petróleo")
        self.assertContains(response, 'lang="pt-PT"')

    def test_presentation_pt_explicit_loads(self):
        response = self.client.get("/presentation/pt/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Os dados são o novo petróleo")

    def test_presentation_en_loads(self):
        response = self.client.get("/presentation/en/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data is the new oil")
        self.assertContains(response, "What we need from you")
        self.assertContains(response, "Start today — data compounds")
        self.assertContains(response, "Parle — your ongoing channel")
        self.assertContains(response, "missing-item-loop")
        self.assertContains(response, "voice-feed-panel")
        self.assertNotContains(response, "circularity-zones")
        self.assertContains(response, 'lang="en"')

    def test_presentation_pt_cta_present(self):
        response = self.client.get("/presentation/pt/")
        self.assertContains(response, "O que precisamos de si")
        self.assertContains(response, "Comece hoje — os dados acumulam-se")
        self.assertContains(response, "Parle — o seu canal permanente")

    def test_presentation_en_slide_order(self):
        response = self.client.get("/presentation/en/")
        content = response.content.decode()
        self.assertLess(
            content.index('data-slide="2"'),
            content.index("One system, two workplaces"),
        )
        self.assertLess(
            content.index("One system, two workplaces"),
            content.index("From item to branch stock"),
        )
        self.assertLess(
            content.index("From item to branch stock"),
            content.index("Internal request"),
        )
        self.assertLess(
            content.index("Internal request"),
            content.index("When the item is not in the catalogue"),
        )
        self.assertLess(
            content.index("Internal request"),
            content.index("Catalogue and pricing"),
        )
        self.assertLess(
            content.index("Parle — your ongoing channel"),
            content.index("Data is the new oil"),
        )
        self.assertLess(
            content.index("Data is the new oil"),
            content.index("Today's scenario"),
        )
        self.assertLess(
            content.index("What the system already records"),
            content.index("Authorization and controls"),
        )
        self.assertLess(
            content.index("Authorization and controls"),
            content.index("Log in and explore"),
        )

    def test_presentation_slide2_birds_eye(self):
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'class="slide slide-worlds" data-slide="2"')
        self.assertContains(en, "One system, two workplaces")
        self.assertContains(en, "worlds-diagram")
        self.assertContains(en, "We need this")
        self.assertContains(en, "Here it is")
        self.assertContains(
            en,
            "The branch asks. The warehouse answers.",
        )
        self.assertNotContains(en, "Everyone works in the same software")
        en_slide2 = _slide_html(en.content.decode(), 2)
        self.assertNotIn("Two worlds, one system", en_slide2)
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, 'class="slide slide-worlds" data-slide="2"')
        self.assertContains(pt, "Um sistema, dois locais de trabalho")
        self.assertContains(pt, "worlds-diagram")
        self.assertContains(pt, "Precisamos disto")
        self.assertContains(pt, "Aqui está")
        self.assertContains(
            pt,
            "A filial pede. O armazém entrega.",
        )
        self.assertNotContains(pt, "Todos trabalham no mesmo software")
        pt_slide2 = _slide_html(pt.content.decode(), 2)
        self.assertNotIn("Dois mundos, um sistema", pt_slide2)

    def test_presentation_slide9_missing_item_loop(self):
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'class="slide slide-missing-item" data-slide="9"')
        self.assertContains(en, "When the item is not in the catalogue")
        self.assertContains(en, "missing-item-loop")
        self.assertContains(en, "New conversation")
        self.assertContains(en, ">Branch</text>")
        self.assertContains(en, ">Warehouse</text>")
        self.assertContains(en, "missing-item-node-group")
        self.assertContains(en, "Understanding reached")
        self.assertContains(en, "Inserted in catalogue")
        self.assertContains(en, "Conversation closes")
        self.assertContains(en, "Express satisfaction")
        self.assertContains(en, "missing-item-star-on")
        self.assertContains(
            en,
            "Not an order — a conversation that closes once the item enters the catalogue.",
        )
        self.assertNotContains(en, "Talk it through")
        en_slide9 = _slide_html(en.content.decode(), 9)
        self.assertNotIn('x1="298" y1="48" x2="174" y2="48"', en_slide9)
        self.assertIn('x1="174" y1="40" x2="266" y2="40"', en_slide9)
        self.assertIn('d="M 388 112 L 388 167 L 352 167"', en_slide9)
        self.assertNotIn("ThreadReadState", en_slide9)
        self.assertNotIn("/branch/threads/", en_slide9)
        self.assertNotIn("Order as usual", en_slide9)
        self.assertNotIn("Next missing item", en_slide9)
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, 'class="slide slide-missing-item" data-slide="9"')
        self.assertNotContains(en, "When something is missing")
        self.assertContains(pt, "Quando o artigo não existe no catálogo")
        self.assertContains(pt, "missing-item-loop")
        self.assertContains(pt, "Nova conversa")
        self.assertContains(pt, ">Filial</text>")
        self.assertContains(pt, ">Armazém</text>")
        self.assertContains(pt, "Não está no catálogo!!")
        self.assertContains(pt, "Entendimento")
        self.assertContains(pt, "Inserido no catálogo")
        self.assertContains(pt, "Fecha a conversa")
        self.assertContains(pt, "Expressar satisfação")
        self.assertContains(pt, "missing-item-arrow-neutral")
        self.assertContains(pt, "missing-item-star-on")
        self.assertContains(
            pt,
            "Não é uma encomenda — uma conversa que fecha quando o artigo entra para o catálogo.",
        )
        self.assertNotContains(pt, "Não está na lista")
        pt_slide9 = _slide_html(pt.content.decode(), 9)
        self.assertNotIn('x1="298" y1="48" x2="188" y2="48"', pt_slide9)
        self.assertIn('d="M 388 112 L 388 167 L 330 167"', pt_slide9)
        self.assertNotIn(">Conversa</text>", pt_slide9)
        self.assertNotIn("ThreadReadState", pt_slide9)
        self.assertNotIn("/branch/threads/", pt_slide9)
        self.assertNotIn("Pedido normal", pt_slide9)
        self.assertNotIn("Quando falta algo", pt_slide9)

    def test_presentation_slides_4_to_8_graphics(self):
        en = self.client.get("/presentation/en/")
        pt = self.client.get("/presentation/pt/")
        en_body = en.content.decode()
        pt_body = pt.content.decode()
        self.assertContains(en, 'class="slide slide-process" data-slide="4"')
        self.assertContains(en, "The branch asks; the warehouse ships.")
        self.assertContains(en, ">Catalogue</text>")
        self.assertContains(en, ">Draft</text>")
        self.assertContains(en, ">Submit</text>")
        self.assertContains(en, ">Queue</text>")
        self.assertContains(en, ">Ship</text>")
        en_slide4 = _slide_html(en_body, 4)
        pt_slide4 = _slide_html(pt_body, 4)
        self.assertIn("status → shipped", en_slide4)
        self.assertIn('x1="440" y1="130" x2="440" y2="162"', en_slide4)
        self.assertIn('x1="450" y1="130" x2="450" y2="162"', en_slide4)
        self.assertNotIn(">Issue</text>", en_slide4)
        self.assertNotIn('y1="130" x2="495" y2="162" marker-end="url(#arrowhead-req-teal)"', en_slide4)
        self.assertContains(en, "worlds-heading-branch")
        self.assertContains(en, "Confirm qty")
        self.assertContains(en, "Branch stock up")
        self.assertContains(en, "Only the warehouse manages the catalogue.")
        self.assertContains(en, "From draft to closed.")
        self.assertContains(en, "Quantity is never typed by hand.")
        self.assertContains(en, "Available = on hand − reserved")
        self.assertContains(en, "stock-mass-reserved")
        self.assertContains(pt, "A filial pede; o armazém expede.")
        self.assertContains(pt, ">Catálogo</text>")
        self.assertContains(pt, ">Rascunho</text>")
        self.assertContains(pt, ">Submete</text>")
        self.assertContains(pt, ">Expede</text>")
        self.assertIn("estado → expedido", pt_slide4)
        self.assertNotIn(">Emite</text>", pt_slide4)
        self.assertNotIn(">Expedido</text>", pt_slide4)
        self.assertContains(pt, "Confirma qtd")
        self.assertContains(pt, "Stock filial sobe")
        self.assertContains(pt, "Só o armazém gere o catálogo.")
        self.assertContains(pt, "Do rascunho ao fechado.")
        self.assertContains(pt, "A quantidade nunca se escreve à mão.")
        self.assertContains(pt, "Disponível = físico − reservado")
        gone = (
            "/branch/requests/",
            "/manage/internal-requests/",
            "/branch/receipts/",
            "/manage/purchase-orders/",
            "/manage/goods-receipts/",
            "BranchStockMovement",
            "Item.quantity",
            "D32",
            "Lado filial",
            "Branch side",
        )
        for number in range(4, 9):
            chunk = _slide_html(en_body, number) + _slide_html(pt_body, number)
            for token in gone:
                self.assertNotIn(token, chunk)
        self.assertContains(
            pt,
            "o artigo percorreu catálogo → compra → stock central → requisição → expedição → stock filial",
        )
        self.assertContains(
            en,
            "the item went catalogue → purchase → central stock → request → issue → branch stock",
        )
        self.assertContains(pt, "Artigos novos começam")
        self.assertContains(en, "New items start")
        self.assertContains(pt, "Sem preço de fornecedor")
        self.assertContains(en, "No supplier price")

    def test_presentation_slide3_closed_circuit(self):
        en = self.client.get("/presentation/en/")
        pt = self.client.get("/presentation/pt/")
        en_body = en.content.decode()
        pt_body = pt.content.decode()
        en_slide = _slide_html(en_body, 3)
        pt_slide = _slide_html(pt_body, 3)
        self.assertContains(en, 'class="slide slide-process" data-slide="3"')
        self.assertContains(en, "From item to branch stock")
        self.assertContains(
            en,
            "Example: CEM-50 — Cement 50 kg. Already in the catalogue; the circuit closes at the branch.",
        )
        self.assertIn(">Asks</text>", en_slide)
        self.assertIn(">Order</text>", en_slide)
        self.assertIn(">Receipt</text>", en_slide)
        self.assertIn(">Stock</text>", en_slide)
        self.assertIn(">Shipped</text>", en_slide)
        self.assertIn(">Confirm</text>", en_slide)
        self.assertIn("CEM-50", en_slide)
        self.assertIn("No stock", en_slide)
        self.assertIn("order becomes a receipt", en_slide)
        self.assertIn("closes the circuit", en_slide)
        self.assertIn(
            "Every step generates structured data. The circuit only closes when the branch confirms arrival.",
            en_slide,
        )
        self.assertContains(pt, 'class="slide slide-process" data-slide="3"')
        self.assertContains(pt, "Do artigo ao stock na filial")
        self.assertContains(
            pt,
            "Exemplo: CEM-50 — Cimento 50 kg. Já está no catálogo; o circuito fecha na filial.",
        )
        self.assertIn(">Pede</text>", pt_slide)
        self.assertIn(">Encomenda</text>", pt_slide)
        self.assertIn(">Receção</text>", pt_slide)
        self.assertIn(">Confirma</text>", pt_slide)
        self.assertIn("CEM-50", pt_slide)
        self.assertIn("Sem stock", pt_slide)
        self.assertIn("encomenda vira receção", pt_slide)
        self.assertIn("fecha o circuito", pt_slide)
        self.assertIn(
            "Cada etapa gera dados estruturados. O circuito só fecha quando a filial confirma a chegada.",
            pt_slide,
        )
        gone = (
            "/manage/",
            "purchase-orders",
            "goods-receipts",
            "branch/requests",
            "internal-requests",
            "branch/receipts",
            ">Approval</text>",
            ">Aprovação</text>",
            "slide-eyebrow",
            "flow-node",
        )
        for token in gone:
            self.assertNotIn(token, en_slide)
            self.assertNotIn(token, pt_slide)

    def test_language_switcher_links(self):
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, 'href="/presentation/en/"')
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'href="/presentation/pt/"')

    def test_presentation_static_assets_referenced(self):
        response = self.client.get("/presentation/en/")
        self.assertContains(response, "presentation/css/deck.css")
        self.assertContains(response, "presentation/js/deck.js")

    def test_presentation_demo_login_slide(self):
        self.assertEqual(SLIDE_COUNT, 26)
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'data-slide="17"')
        self.assertContains(en, "Log in and explore")
        self.assertContains(en, "Browser warning expected")
        self.assertContains(en, DEMO_LOGIN_URL)
        self.assertContains(en, DEMO_PASSWORD)
        self.assertContains(en, "armazem.admin@centcompras.dev")
        self.assertContains(en, "filial.dual@centcompras.dev")
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, "Experimente agora")
        self.assertContains(pt, "Aviso do browser esperado")
        self.assertContains(pt, DEMO_PASSWORD)

    def test_presentation_part2_slides(self):
        en = self.client.get("/presentation/en/")
        pt = self.client.get("/presentation/pt/")
        en_body = en.content.decode()
        pt_body = pt.content.decode()

        self.assertContains(en, 'data-slide="18"')
        self.assertContains(en, "Detailed reference")
        self.assertContains(pt, "Referência detalhada")

        self.assertContains(en, 'data-slide="19"')
        self.assertContains(en, 'data-slide="26"')
        self.assertContains(pt, 'data-slide="26"')
        self.assertNotContains(en, 'data-slide="27"')

        en19 = _slide_html(en_body, 19)
        self.assertIn("/branch/requests/", en19)
        self.assertIn("/manage/internal-requests/", en19)
        self.assertIn("Internal request", en19)

        en21 = _slide_html(en_body, 21)
        self.assertIn("/manage/items/", en21)
        self.assertIn("ItemChangeLog", en21)

        en24 = _slide_html(en_body, 24)
        self.assertIn("flow-node", en24)
        self.assertIn("arrowhead-circuit-p2", en24)

        en26 = _slide_html(en_body, 26)
        self.assertIn("ThreadReadState", en26)
        self.assertIn("arrowhead-thread-p2", en26)

        en12 = _slide_html(en_body, 12)
        self.assertIn("Parle — your ongoing channel", en12)
        self.assertNotIn("Company Voice — your ongoing channel", en12)

        pt12 = _slide_html(pt_body, 12)
        self.assertIn("Parle — o seu canal permanente", pt12)
        self.assertNotIn("Voz da Empresa", pt12)

        pt19 = _slide_html(pt_body, 19)
        self.assertIn("Requisição interna", pt19)

        pt26 = _slide_html(pt_body, 26)
        self.assertIn("Abrir conversa", pt26)
        self.assertNotIn("Abrir fio", pt26)
        self.assertNotIn(">fio<", pt26.lower())

        for number in range(19, 27):
            self.assertIn(f'data-slide="{number}"', en_body)
            self.assertIn(f'data-slide="{number}"', pt_body)

    def test_presentation_slides_16_17_workplace_colours(self):
        en = self.client.get("/presentation/en/")
        pt = self.client.get("/presentation/pt/")
        en16 = _slide_html(en.content.decode(), 16)
        en17 = _slide_html(en.content.decode(), 17)
        pt16 = _slide_html(pt.content.decode(), 16)
        pt17 = _slide_html(pt.content.decode(), 17)
        self.assertIn('class="heading-warehouse">Warehouse — purchase orders', en16)
        self.assertIn('class="heading-branch">Branch — internal requests', en16)
        self.assertIn('class="heading-warehouse">Central warehouse', en17)
        self.assertIn('class="heading-branch">Branches', en17)
        self.assertIn('class="heading-branch">Branch</th>', en17)
        self.assertIn('class="heading-warehouse">Armazém — encomendas de compra', pt16)
        self.assertIn('class="heading-branch">Filial — requisições internas', pt16)
        self.assertIn('class="heading-warehouse">Armazém central', pt17)
        self.assertIn('class="heading-branch">Filiais', pt17)
        self.assertIn('class="heading-branch">Filial</th>', pt17)
