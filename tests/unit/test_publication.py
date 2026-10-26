"""Catch privacy regressions without containing real credentials or addresses."""
import unittest
from scripts.check_release import find_sensitive


class PublicationPrivacyTests(unittest.TestCase):
    def test_localhost_and_documentation_addresses_are_supported(self):
        for text in ['http://localhost:7860', 'ws://127.0.0.1:9005', '0.0.0.0', '192.0.2.10', '203.0.113.9']:
            self.assertEqual(find_sensitive(text.encode()), [], text)

    def test_real_deployment_address_is_rejected(self):
        address = '.'.join(['10', '25', '15', '90'])
        self.assertIn('non-example network address', find_sensitive(address.encode()))

    def test_personal_paths_and_credentials_are_rejected(self):
        path = '/home/' + 'sample-user' + '/private'
        token = 'hf_' + 'A' * 36
        self.assertIn('personal absolute path', find_sensitive(path.encode()))
        self.assertIn('access token', find_sensitive(token.encode()))
        url = 'https://' + 'user' + ':' + 'sample-password' + '@example.org'
        self.assertIn('credential in URL', find_sensitive(url.encode()))

    def test_four_part_dependency_versions_are_not_ip_addresses(self):
        version = '.'.join(['12', '9', '2', '10'])
        self.assertEqual(find_sensitive(('library==' + version).encode()), [])
        self.assertIn('non-example network address', find_sensitive(('https://' + version + '/wheel').encode()))

    def test_checkpoint_hashes_remain_valid_public_provenance(self):
        self.assertEqual(find_sensitive(('sha256=' + 'abc01234' * 8).encode()), [])


if __name__ == '__main__':
    unittest.main()
