from django.test import TestCase


class PresentationDeckTests(TestCase):
    def test_presentation_deck_loads(self):
        response = self.client.get("/presentation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CentCompras")
        self.assertContains(response, "Os dados são o novo petróleo")
        self.assertContains(response, 'lang="pt-PT"')

    def test_presentation_static_assets_referenced(self):
        response = self.client.get("/presentation/")
        self.assertContains(response, "presentation/css/deck.css")
        self.assertContains(response, "presentation/js/deck.js")
