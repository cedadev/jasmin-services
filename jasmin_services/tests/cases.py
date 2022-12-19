import django.test

import jasmin_services.models


class ServicesTestCase(django.test.TestCase):
    def setUp(self):
        category = jasmin_services.models.Category.objects.create(
            name="category-name", long_name="Category Name", position=10
        )
        jasmin_services.models.Service.objects.bulk_create(
            [
                jasmin_services.models.Service(
                    category=category,
                    name="service-one",
                    summary="Service One is the first of the services.",
                    hidden=False,
                )
            ]
        )
