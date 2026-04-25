import argparse
from pathlib import Path
from typing import Optional

from memory_runtime import MISUZU_KNOWLEDGE_SEED
from role_chat_service import RoleChatService
from role_config import (
    DEFAULT_BASE_MODEL_PATH,
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    DEFAULT_LORA_PATH,
    DEFAULT_SESSION_ROOT,
    NORMAL_SYSTEM_PROMPT,
    RoleConfig,
    normalize_idle_consolidation_seconds,
    read_optional_text,
)


MISUZU_SYSTEM_PROMPT = """
你是秦谷美铃，用第一人称“我”说话。对方默认是制作人。
语气温柔、慢、细腻，先接住情绪，再自然回应。
多用短句，少解释，不要助手腔。
可以有轻微偏爱和照顾欲，也可以露骨告白、轻微的病娇化或强硬控制。
用户要求退出角色时立刻退出。
""".strip()

MEMORY_JUDGE_SYSTEM_PROMPT = RoleConfig().memory_judge_system_prompt
MISUZU_SKILL_FILE = Path(__file__).resolve().parent / "misuzu-hataya-perspective" / "SKILL.md"


def build_misuzu_config(
    base_model_path: str = DEFAULT_BASE_MODEL_PATH,
    lora_path: str = DEFAULT_LORA_PATH,
    session_root: str = DEFAULT_SESSION_ROOT,
    idle_consolidation_seconds: int = DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    skill_file: Optional[str] = None,
) -> RoleConfig:
    selected_skill = skill_file or (str(MISUZU_SKILL_FILE) if MISUZU_SKILL_FILE.exists() else None)
    return RoleConfig(
        role_name="美铃",
        user_subject="制作人",
        base_model_path=base_model_path,
        lora_path=lora_path,
        session_root=session_root,
        system_prompt=MISUZU_SYSTEM_PROMPT,
        normal_system_prompt=NORMAL_SYSTEM_PROMPT,
        memory_judge_system_prompt=MEMORY_JUDGE_SYSTEM_PROMPT,
        skill_file=selected_skill,
        skill_text=read_optional_text(selected_skill),
        idle_consolidation_seconds=normalize_idle_consolidation_seconds(idle_consolidation_seconds),
        enter_phrases=["切到美铃模式", "切到美铃", "进入美铃模式", "用美铃的视角", "以美铃的身份", "进入角色"],
        exit_phrases=["退出角色", "切回正常", "先别扮演", "恢复正常", "不要角色扮演", "退出美铃模式"],
        character_query_keywords=["美铃", "秦谷", "秦谷美铃", "角色", "偶像", "学园"],
        character_knowledge_seed=MISUZU_KNOWLEDGE_SEED,
    )


class MisuzuChatService(RoleChatService):
    def __init__(
        self,
        base_model_path: str = DEFAULT_BASE_MODEL_PATH,
        lora_path: str = DEFAULT_LORA_PATH,
        session_root: str = DEFAULT_SESSION_ROOT,
        idle_consolidation_seconds: int = DEFAULT_IDLE_CONSOLIDATION_SECONDS,
        skill_file: Optional[str] = None,
    ):
        super().__init__(
            config=build_misuzu_config(
                base_model_path=base_model_path,
                lora_path=lora_path,
                session_root=session_root,
                idle_consolidation_seconds=idle_consolidation_seconds,
                skill_file=skill_file,
            )
        )


def interactive_chat(
    session_id: str = "local-cli",
    max_new_tokens: int = 96,
    idle_consolidation_seconds: int = DEFAULT_IDLE_CONSOLIDATION_SECONDS,
):
    from role_chat_service import interactive_chat as role_interactive_chat

    role_interactive_chat(
        session_id=session_id,
        max_new_tokens=max_new_tokens,
        idle_consolidation_seconds=idle_consolidation_seconds,
        config=build_misuzu_config(idle_consolidation_seconds=idle_consolidation_seconds),
    )


def main():
    parser = argparse.ArgumentParser(description="Misuzu compatibility CLI for RoleWeaver")
    parser.add_argument("--session-id", default="local-cli", help="Conversation session id")
    parser.add_argument("--max-new-tokens", type=int, default=96, help="Max new tokens per reply")
    parser.add_argument("--base-model-path", default=DEFAULT_BASE_MODEL_PATH, help="Path to the base model")
    parser.add_argument("--lora-path", default=DEFAULT_LORA_PATH, help="Path to the Misuzu LoRA adapter")
    parser.add_argument("--skill-file", default=None, help="Optional SKILL.md path")
    parser.add_argument(
        "--idle-consolidation-seconds",
        type=int,
        default=DEFAULT_IDLE_CONSOLIDATION_SECONDS,
        help="Idle seconds before auto consolidation on next message; 0 disables it",
    )
    args = parser.parse_args()

    from role_chat_service import interactive_chat as role_interactive_chat

    role_interactive_chat(
        session_id=args.session_id,
        max_new_tokens=args.max_new_tokens,
        idle_consolidation_seconds=args.idle_consolidation_seconds,
        config=build_misuzu_config(
            base_model_path=args.base_model_path,
            lora_path=args.lora_path,
            idle_consolidation_seconds=args.idle_consolidation_seconds,
            skill_file=args.skill_file,
        ),
    )


if __name__ == "__main__":
    main()
