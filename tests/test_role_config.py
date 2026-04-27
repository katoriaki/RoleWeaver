import unittest

from role_config import PROJECT_ROOT, read_skill_bundle


class RoleConfigSkillBundleTestCase(unittest.TestCase):
    def test_read_skill_bundle_inlines_nearby_references(self):
        skill = PROJECT_ROOT / "tests" / "fixtures" / "skill_bundle" / "SKILL.md"

        text = read_skill_bundle(str(skill))

        self.assertIn("角色主体", text)
        self.assertIn("Reference: references", text)
        self.assertIn("角色参考", text)

    def test_read_skill_bundle_works_with_only_skill_file(self):
        skill = PROJECT_ROOT / "tests" / "fixtures" / "skill_single" / "SKILL.md"

        text = read_skill_bundle(str(skill))

        self.assertIn("单文件角色", text)
        self.assertNotIn("自动关联加载", text)


if __name__ == "__main__":
    unittest.main()
