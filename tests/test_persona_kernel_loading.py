import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from role_config import PROJECT_ROOT, read_skill_bundle


class PersonaKernelLoadingTestCase(unittest.TestCase):
    def test_read_skill_bundle_inlines_persona_kernel_sidecar(self):
        skill = PROJECT_ROOT / "tests" / "fixtures" / "skill_bundle" / "SKILL.md"

        text = read_skill_bundle(str(skill))

        self.assertIn("Persona Kernel", text)
        self.assertIn("Fixture role keeps independent judgement.", text)
        self.assertIn("Fixture role must not become a generic assistant.", text)


if __name__ == "__main__":
    unittest.main()
