from django.test import TestCase


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
        self.assertContains(response, "Company Voice — your ongoing channel")
        self.assertContains(response, 'lang="en"')

    def test_presentation_pt_cta_on_slide_two(self):
        response = self.client.get("/presentation/pt/")
        self.assertContains(response, "O que precisamos de si")
        self.assertContains(response, "Comece hoje — os dados acumulam-se")
        self.assertContains(response, "Voz da Empresa — o seu canal permanente")

    def test_language_switcher_links(self):
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, 'href="/presentation/en/"')
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'href="/presentation/pt/"')

    def test_presentation_static_assets_referenced(self):
        response = self.client.get("/presentation/en/")
        self.assertContains(response, "presentation/css/deck.css")
        self.assertContains(response, "presentation/js/deck.js")
