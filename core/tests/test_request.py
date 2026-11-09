from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.utils.request import get_client_ip, get_client_ip_key


class ClientIPTests(SimpleTestCase):
    @override_settings(CLIENT_IP_SOURCE="remote_addr")
    def test_local_mode_ignores_both_forwarded_headers(self) -> None:
        request = RequestFactory().get(
            "/", REMOTE_ADDR="192.0.2.1",
            HTTP_X_FORWARDED_FOR="198.51.100.1, 203.0.113.1",
            HTTP_CF_CONNECTING_IP="198.51.100.2",
        )
        self.assertEqual(get_client_ip(request), "192.0.2.1")

    @override_settings(CLIENT_IP_SOURCE="render_cloudflare")
    def test_render_mode_uses_only_validated_cloudflare_header(self) -> None:
        request = RequestFactory().get(
            "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="198.51.100.1",
            HTTP_CF_CONNECTING_IP=" 2001:0db8:0000::1 ",
        )
        self.assertEqual(get_client_ip(request), "2001:db8::1")
        self.assertEqual(get_client_ip_key(request), "2001:db8::1")

    def test_invalid_selected_ip_never_falls_back_to_other_headers(self) -> None:
        for mode, selected in (("remote_addr", "REMOTE_ADDR"),
                               ("render_cloudflare", "HTTP_CF_CONNECTING_IP")):
            for invalid in (None, "", "not-an-ip", "192.0.2.1, 192.0.2.2",
                            "192.0.2.1:1234", "[2001:db8::1]", "fe80::1%eth0"):
                with self.subTest(mode=mode, invalid=invalid):
                    request = RequestFactory().get(
                        "/", REMOTE_ADDR="192.0.2.1",
                        HTTP_CF_CONNECTING_IP="198.51.100.1",
                        HTTP_X_FORWARDED_FOR="203.0.113.1",
                    )
                    if invalid is None:
                        request.META.pop(selected, None)
                    else:
                        request.META[selected] = invalid
                    with override_settings(CLIENT_IP_SOURCE=mode):
                        self.assertIsNone(get_client_ip(request))
                        self.assertEqual(get_client_ip_key(request), "no-ip")

    @override_settings(CLIENT_IP_SOURCE="remote_addr")
    def test_local_mode_accepts_ipv4_and_canonicalizes_ipv6(self) -> None:
        for raw, expected in ((" 127.0.0.1 ", "127.0.0.1"),
                              ("2001:0db8::0001", "2001:db8::1")):
            with self.subTest(raw=raw):
                self.assertEqual(get_client_ip(RequestFactory().get(
                    "/", REMOTE_ADDR=raw
                )), expected)

    @override_settings(CLIENT_IP_SOURCE="unsupported")
    def test_unknown_mode_is_a_configuration_error(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            get_client_ip(RequestFactory().get("/"))
