import django.test


class ReverseDNSTestCase(django.test.TestCase):
    def test_reverse_dns_check(self):
        """Check that the reverse DNS test case can resolve localhost."""
        response = self.client.get("/services/reverse_dns_check/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content, b"External IP address: 127.0.0.1\r\nResolved to host: localhost"
        )
