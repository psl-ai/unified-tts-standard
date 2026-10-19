import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
SERVICES = (
    ROOT / "tele tts" / "app.py",
    ROOT / "edge-tts" / "app.py",
)
MALE_VOICE = "zh-CN-YunxiNeural"
EDGE_CLIENT = ROOT / "edge-tts" / "tts_client.py"


def default_voice(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "create_tts_request_model":
            for keyword in node.keywords:
                if keyword.arg == "voice_default" and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
    raise AssertionError(f"voice_default not found in {path}")


class DefaultMaleVoiceTests(unittest.TestCase):
    def test_services_default_to_yunxi_male_voice(self):
        for service in SERVICES:
            with self.subTest(service=service):
                self.assertEqual(default_voice(service), MALE_VOICE)

    def test_edge_client_defaults_to_yunxi_male_voice(self):
        source = EDGE_CLIENT.read_text(encoding="utf-8")
        self.assertIn(MALE_VOICE, source)
        self.assertNotIn("zh-CN-XiaoxiaoNeural", source)


if __name__ == "__main__":
    unittest.main()
