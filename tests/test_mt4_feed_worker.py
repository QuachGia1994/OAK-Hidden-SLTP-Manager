import os
import unittest
from unittest.mock import Mock, patch
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt4_feed_server


class MT4FeedWorkerTests(unittest.TestCase):
    def test_builds_the_required_ea_and_management_listeners(self):
        expected_ea_server = Mock()
        expected_management_server = Mock()
        with patch(
            "mt4_feed_server.make_server",
            side_effect=[expected_ea_server, expected_management_server],
        ) as make_server:
            ea_server, management_server = mt4_feed_server._build_local_servers()

        self.assertIs(ea_server, expected_ea_server)
        self.assertIs(management_server, expected_management_server)
        self.assertEqual(
            make_server.call_args_list[0].args,
            ("127.0.0.1", 80, mt4_feed_server.app),
        )
        self.assertTrue(make_server.call_args_list[0].kwargs["threaded"])
        self.assertEqual(
            make_server.call_args_list[1].args,
            ("127.0.0.1", 5001, mt4_feed_server.app),
        )
        self.assertTrue(make_server.call_args_list[1].kwargs["threaded"])

    def test_rejects_a_stale_custom_port_override_instead_of_silently_breaking_mt4(self):
        with patch.dict(os.environ, {"MT4_FEED_PORT": "5001"}, clear=False):
            with self.assertRaisesRegex(ValueError, "must be unset or 80"):
                mt4_feed_server._ea_publish_port()


if __name__ == "__main__":
    unittest.main()
