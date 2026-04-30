import unittest
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from role_config import load_config_values, normalize_model_loader_mode


class ConfigEncodingTestCase(unittest.TestCase):
    def test_csv_config_accepts_excel_style_legacy_encoding(self):
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "roleweaver.config.csv"
            config_path.write_bytes(
                "key,value,notes\nrole_name,ミスズ,Excel saved Japanese text\n".encode("cp932")
            )

            values = load_config_values(str(config_path))

        self.assertEqual(values["role_name"], "ミスズ")


    def test_model_loader_mode_aliases(self):
        self.assertEqual(normalize_model_loader_mode("causal_lm"), "text")
        self.assertEqual(normalize_model_loader_mode("vlm"), "vision")
        self.assertEqual(normalize_model_loader_mode("qwen3-omni"), "omni")
        self.assertEqual(normalize_model_loader_mode("omnimodal"), "omni")
        self.assertEqual(normalize_model_loader_mode("unknown"), "auto")


if __name__ == "__main__":
    unittest.main()
