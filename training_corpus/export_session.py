#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 mavis session 转成训练语料 JSONL
- 格式: OpenAI chat-format (messages array)
- 包含 paper agent 特有元数据
- 不含 thinking_content（不训练思考过程）
- 工具调用展平为 tool/result
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator

CORPUS_DIR = Path(r"G:\minimax - workspace\Paper agent\training_corpus")
RAW_DIR = CORPUS_DIR / "raw"
MANIFEST = CORPUS_DIR / "manifest.jsonl"


def _ts_to_iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _flatten_tool_call(tc: dict) -> dict:
    """把 tool_call 展平为 {role: tool, name, content, args}"""
    return {
        "role": "tool",
        "name": tc.get("tool_name", "unknown"),
        "tool_call_id": tc.get("tool_call_id", ""),
        "args": tc.get("tool_call_args", ""),
        "result": (tc.get("tool_call_result_data") or "")[:5000],
    }


def session_to_chat_format(messages: list, session_id: str) -> dict:
    """
    输入: mavis session 消息列表
    输出: 单条训练样本 dict
    """
    out_messages = []
    paper_agent_calls = 0
    sub_agent_spawns = 0
    user_turns = 0
    assistant_turns = 0
    has_honest_audit = False
    has_self_correction = False
    has_sub_agent = False
    has_via_negativa = False
    has_paper_citation = False
    topics_seen = set()

    for m in messages:
        role = m.get("role")
        content = m.get("msg_content", "")
        tool_calls = m.get("tool_calls") or []

        if role == "user":
            user_turns += 1
            out_messages.append({"role": "user", "content": content})
            # 主题推断
            txt = content.lower()
            for kw, topic in [
                ("川秀", "川秀益生菌"), ("菌", "益生菌"),
                ("地中海", "地中海饮食"), ("塔勒布", "塔勒布哲学"),
                ("否定法", "via_negativa"), ("via", "via_negativa"),
                ("predi", "PREDIMED"), ("酸奶", "发酵乳"),
                ("原子习惯", "atomic_habits"), ("taleb", "塔勒布哲学"),
            ]:
                if kw in txt:
                    topics_seen.add(topic)
            if "你之前说" in content or "你之前给的" in content or "审计" in content:
                has_honest_audit = True
            if "诚实" in content:
                has_honest_audit = True
        elif role == "assistant":
            assistant_turns += 1
            # 主消息
            if content:
                out_messages.append({"role": "assistant", "content": content})
                txt = content.lower()
                if "via negativa" in content.lower() or "否定法" in content:
                    has_via_negativa = True
                if any(s in content for s in ["DOI:", "10.3", "10.1", "Fan 2020", "Dimidi 2019", "González 2019", "PREDIMED"]):
                    has_paper_citation = True
                if "撤回" in content or "修正" in content or "我之前说错了" in content or "我的锅" in content:
                    has_self_correction = True
            # 工具调用（展平）
            for tc in tool_calls:
                tname = tc.get("tool_name", "")
                if tname == "task":
                    has_sub_agent = True
                    sub_agent_spawns += 1
                if tname in ("bash", "write", "edit"):
                    pass  # local tool
                out_messages.append(_flatten_tool_call(tc))
                # 标记 paper agent 使用
                if "pa_cli" in (tc.get("tool_call_args") or "") or "paper agent" in (tc.get("tool_call_args") or "").lower():
                    paper_agent_calls += 1
        elif role == "tool":
            # 已经被前面的 assistant 展平过
            pass

    # 推断主题
    topic = "MISC"
    if "川秀益生菌" in topics_seen or "PREDIMED" in topics_seen:
        topic = "nutrition_lit_review"
    elif "塔勒布哲学" in topics_seen and "地中海饮食" in topics_seen:
        topic = "philosophy_application_nutrition"
    elif "地中海饮食" in topics_seen:
        topic = "mediterranean_diet"
    elif "塔勒布哲学" in topics_seen:
        topic = "taleb_philosophy"

    # 质量信号
    quality_signals = []
    if has_honest_audit: quality_signals.append("honest_three_tier_reporting")
    if has_self_correction: quality_signals.append("self_correction_after_audit")
    if has_sub_agent: quality_signals.append("sub_agent_orchestration")
    if has_via_negativa: quality_signals.append("philosophical_framework_application")
    if has_paper_citation: quality_signals.append("academic_citation_grounded")
    if user_turns >= 5: quality_signals.append("deep_multi_turn_dialogue")

    return {
        "messages": out_messages,
        "metadata": {
            "session_id": session_id,
            "agent_name": "mavis",
            "model": "Mavis",
            "user_handle": "糊涂工作站",
            "topic": topic,
            "topics_seen": sorted(list(topics_seen)),
            "started_at": _ts_to_iso(messages[0].get("timestamp", 0)) if messages else None,
            "ended_at": _ts_to_iso(messages[-1].get("timestamp", 0)) if messages else None,
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "tool_call_count": sum(len(m.get("tool_calls") or []) for m in messages if m.get("role") == "assistant"),
            "paper_agent_cli_calls": paper_agent_calls,
            "sub_agent_spawns": sub_agent_spawns,
            "quality_signals": quality_signals,
            "intended_expert_routing": {
                "domain": topic,
                "task_type": "synthesis_audit" if has_honest_audit else "info_qa",
                "complexity": "deep" if user_turns >= 8 else ("medium" if user_turns >= 4 else "shallow"),
            },
            "license_note": "User-originated training corpus. No-AI-Training flag applies to code, not external session data.",
        },
    }


def save_session(session_id: str, messages: list):
    """保存单个 session 到 raw/ + 更新 manifest"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sample = session_to_chat_format(messages, session_id)
    out_path = RAW_DIR / f"{session_id}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    # 追加 manifest
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"session_id": session_id, **sample["metadata"]}, ensure_ascii=False) + "\n")
    return out_path, sample


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("session_id", help="mavis session id (or 'me')")
    ap.add_argument("--mavis-bin", default="mavis")
    args = ap.parse_args()

    # 这里用 stdin 接 session messages JSON
    raw_bytes = sys.stdin.buffer.read()
    # 兼容 UTF-8 BOM
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raw_bytes = raw_bytes[3:]
    data = json.loads(raw_bytes.decode('utf-8'))
    messages = data.get("messages", [])
    out, sample = save_session(args.session_id, messages)
    md = sample["metadata"]
    print(f"[saved] {out}")
    print(f"  topic: {md['topic']}")
    print(f"  turns: user={md['user_turns']} assistant={md['assistant_turns']}")
    print(f"  paper_agent_calls: {md['paper_agent_cli_calls']}")
    print(f"  sub_agent_spawns: {md['sub_agent_spawns']}")
    print(f"  quality_signals: {md['quality_signals']}")
    print(f"  intended_expert: {md['intended_expert_routing']}")
