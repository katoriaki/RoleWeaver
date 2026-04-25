import argparse

from role_chat_service import RoleChatService
from role_config import RoleConfig


def main():
    parser = argparse.ArgumentParser(description="Quickly probe a RoleWeaver LoRA adapter")
    parser.add_argument("--config", default=None, help="CSV/TOML/JSON config file")
    parser.add_argument("--role-name", default=None, help="Role display name")
    parser.add_argument("--base-model-path", default=None, help="Path to the base model")
    parser.add_argument("--lora-path", default=None, help="Path to the trained LoRA adapter")
    parser.add_argument("--skill-file", default=None, help="Optional SKILL.md path")
    parser.add_argument("--prompt", default="今天感觉怎么样？请只用一句话回答。", help="Prompt to send")
    parser.add_argument("--max-new-tokens", type=int, default=64, help="Max generated tokens")
    args = parser.parse_args()

    config = RoleConfig.from_env(
        config_file=args.config,
        role_name=args.role_name,
        base_model_path=args.base_model_path,
        lora_path=args.lora_path,
        skill_file=args.skill_file,
    )
    service = RoleChatService(config=config)
    print(service.chat_once(args.prompt, session_id="adapter-probe", max_new_tokens=args.max_new_tokens))


if __name__ == "__main__":
    main()
