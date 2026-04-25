# ===== 顶部环境变量（Windows稳一点）=====
import os

os.environ["PYTHONUTF8"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from misuzu_chat_service import MisuzuChatService


service = MisuzuChatService()


def chat_once(user_text, session_id: str = "local-cli", max_new_tokens=96):
    return service.chat_once(
        user_text=user_text,
        session_id=session_id,
        max_new_tokens=max_new_tokens,
    )


def interactive_chat():
    print("\n" + "=" * 80)
    print("进入交互模式。输入 exit 退出程序。")
    print("当前默认：美铃模式已开启")
    print("输入“退出角色”可切回正常模式")
    print("输入“切到美铃模式”可重新进入角色模式")
    print("记忆命令：")
    print("  /mem list               查看情节记忆")
    print("  /mem add 内容            手动添加情节记忆")
    print("  /mem del ID             删除指定情节记忆")
    print("  /mem clear              清空情节记忆")
    print("  /mem search 查询词       检查 FAISS + reranker 情节检索")
    print("  /profile show           查看图谱投影出的用户画像")
    print("  /profile clear          清空图谱中的用户画像事实")
    print("  /summary show           查看摘要缓冲")
    print("  /summary clear          清空摘要缓冲及其归档")
    print("  /kg show                查看知识图谱")
    print("  /kg search 查询词        检查知识图谱检索")
    print("  /kg add 主体 | 关系 | 客体")
    print("  /ctx 查询词              预览当前会注入的上下文")
    print("=" * 80)

    while True:
        user_text = input("\n你：").strip()
        if user_text.lower() in ["exit", "quit", "q"]:
            print("已退出。")
            break

        reply = chat_once(user_text)
        print("\n模型：", reply)


if __name__ == "__main__":
    interactive_chat()
