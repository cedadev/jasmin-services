import django.test

import jasmin_services.models


class ServicesTestCase(django.test.TestCase):
    def setUp(self):
        self.category = jasmin_services.models.Category.objects.create(
            name="test_cat", long_name="Meow", position=1
        )
        self.service1 = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="testservice1",
            summary="First test category",
            description="This should be a long description.",
        )
        self.service2 = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="testservice2",
            summary="Another test category",
            description="This should be a long description.",
        )
