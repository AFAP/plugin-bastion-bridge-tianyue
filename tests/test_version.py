import unittest

import api_server
import version


class FakeBridge:
    def is_connected(self):
        return True


class VersionMarkerTests(unittest.TestCase):
    def test_version_string_carries_bastion_client_version(self):
        self.assertEqual(
            version.VERSION,
            f"{version.BRIDGE_VERSION}-om{version.BASTION_CLIENT_VERSION}",
        )

    def test_health_marks_bridge_and_bastion_version(self):
        api = api_server.BridgeAPI(FakeBridge())
        response = api.app.test_client().get("/health")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIs(payload["connected"], True)
        self.assertEqual(payload["version"], version.VERSION)
        self.assertEqual(payload["bridge_version"], version.BRIDGE_VERSION)
        self.assertEqual(payload["bastion"]["client"], version.BASTION_CLIENT_NAME)
        self.assertEqual(payload["bastion"]["version"], version.BASTION_CLIENT_VERSION)

    def test_version_lines_name_the_bastion_target(self):
        text = "\n".join(version.version_lines())
        self.assertIn(version.VERSION, text)
        self.assertIn(version.BASTION_TARGET, text)


if __name__ == "__main__":
    unittest.main()
