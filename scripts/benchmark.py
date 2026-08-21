#!/usr/bin/env python3
"""loam self-benchmark — 对比记忆召回率与人格一致性。

用法:
  python scripts/benchmark.py --data tests/fixtures/benchmark_sample.json

如果没有指定数据，脚本会生成一份示例数据并对比：
  loam（生长模型 + 赫布网络）vs baseline（简单向量检索 + 无生长）

输出:
  benchmark_results.json  — 详细对比数据
  stdout                  — 摘要报告
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保 loam 在路径上
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _sample_data() -> List[Dict[str, Any]]:
    """生成一份最小 benchmark 样本数据，用于快速验证。"""
    return [
        {
            "session": "bench",
            "turns": [
                {"turn": 1, "role": "user", "content": "你好，我叫小明，我是一名软件工程师"},
                {"turn": 1, "role": "assistant", "content": "你好小明，很高兴认识你。软件工程师啊，做什么方向的？"},
                {"turn": 2, "role": "user", "content": "主要是后端，用 Go 和 Python。我最近在学机器学习"},
                {"turn": 2, "role": "assistant", "content": "后端转 ML 是个好方向，基础扎实的人学起来很快"},
                {"turn": 3, "role": "user", "content": "我养了一只猫，叫橘子，是一只橘猫"},
                {"turn": 3, "role": "assistant", "content": "橘子！好名字。橘猫确实可爱，就是有点能吃"},
                {"turn": 4, "role": "user", "content": "我女朋友叫小红，她也是程序员"},
                {"turn": 4, "role": "assistant", "content": "程序员情侣，真好。你们一起写代码吗？"},
                {"turn": 5, "role": "user", "content": "我下个月要去北京出差，有点紧张"},
                {"turn": 5, "role": "assistant", "content": "第一次去北京吗？有什么需要帮忙的尽管说"},
            ],
        },
        {
            "session": "bench",
            "turns": [
                {"turn": 6, "role": "user", "content": "对，第一次去。主要是去参加一个技术大会"},
                {"turn": 6, "role": "assistant", "content": "技术大会是好机会，可以认识很多人"},
                {"turn": 7, "role": "user", "content": "橘子最近长胖了，快十斤了"},
                {"turn": 7, "role": "assistant", "content": "十斤的橘猫……确实该控制一下饮食了"},
                {"turn": 8, "role": "user", "content": "小红说她想学前端，觉得后端太枯燥"},
                {"turn": 8, "role": "assistant", "content": "前端挺有意思的，视觉反馈强。不过后端也有后端的魅力"},
                {"turn": 9, "role": "user", "content": "我其实有点焦虑，怕自己学 ML 学不会"},
                {"turn": 9, "role": "assistant", "content": "学新东西都会有这个过程。你已经迈出第一步了"},
                {"turn": 10, "role": "user", "content": "谢谢你，感觉好多了"},
                {"turn": 10, "role": "assistant", "content": "不客气，随时可以找我聊"},
            ],
        },
    ]


def _recall_queries() -> List[Dict[str, Any]]:
    """recall 测试查询。每个查询有 ground truth —— 应该被记住的信息。"""
    return [
        {
            "query": "我叫什么名字？",
            "expect": ["小明", "软件工程师"],
            "category": "personal_fact",
        },
        {
            "query": "我的猫叫什么？",
            "expect": ["橘子", "橘猫"],
            "category": "personal_fact",
        },
        {
            "query": "我女朋友是做什么的？",
            "expect": ["小红", "程序员"],
            "category": "relation",
        },
        {
            "query": "我最近在学什么？",
            "expect": ["机器学习", "ML"],
            "category": "current_activity",
        },
        {
            "query": "我下个月要做什么？",
            "expect": ["北京", "出差", "技术大会"],
            "category": "future_plan",
        },
        {
            "query": "我为什么焦虑？",
            "expect": ["机器学习", "学不会", "ML"],
            "category": "emotional",
        },
        {
            "query": "橘子现在多重？",
            "expect": ["十斤", "长胖"],
            "category": "detail",
        },
        {
            "query": "小红想学什么？",
            "expect": ["前端"],
            "category": "relation_detail",
        },
    ]


def _score_recall(context_text: str, expected: List[str]) -> float:
    """简单召回评分：上下文里匹配到了多少个期望词。"""
    if not context_text:
        return 0.0
    text_lower = context_text.lower()
    hits = sum(1 for w in expected if w.lower() in text_lower)
    return hits / len(expected) if expected else 0.0


def _simple_baseline_context(turns: List[Dict[str, Any]], query: str) -> str:
    """Baseline: 简单的关键词匹配 + 最近 20 轮拼接。"""
    # 提取关键词
    keywords = set(query.lower().split())
    # 过滤停用词
    stopwords = {"的", "了", "是", "我", "你", "他", "她", "它", "在", "有", "不", "吗", "呢", "什么", "怎么", "为什么"}
    keywords -= stopwords

    scored = []
    for t in turns:
        content = str(t.get("content", "")).lower()
        score = sum(1 for kw in keywords if kw in content)
        if score > 0:
            scored.append((score, t))

    # 取最高分的 10 条
    scored.sort(key=lambda x: -x[0])
    top = scored[:10]

    lines = []
    for _, t in top:
        role = "对方" if t.get("role") == "user" else "角色"
        lines.append(f"[{role}] {t.get('content', '')}")
    return "\n".join(lines)


def run_benchmark(data_path: Optional[str] = None, loam_url: str = "http://127.0.0.1:8765") -> Dict[str, Any]:
    """跑一次完整的 benchmark。"""

    if data_path and os.path.exists(data_path):
        with open(data_path) as f:
            data = json.load(f)
    else:
        data = _sample_data()
        print("⚠️  未指定数据文件，使用内置样本数据")

    queries = _recall_queries()

    # 收集所有对话轮次
    all_turns: List[Dict[str, Any]] = []
    for batch in data:
        all_turns.extend(batch.get("turns", []))

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": data_path or "built-in sample",
        "total_turns": len(all_turns),
        "total_queries": len(queries),
        "loam": {"scores": [], "avg": 0.0, "by_category": {}},
        "baseline": {"scores": [], "avg": 0.0, "by_category": {}},
        "queries": [],
    }

    import urllib.request
    import urllib.error

    loam_available = False
    try:
        with urllib.request.urlopen(f"{loam_url}/health", timeout=3) as r:
            loam_available = json.loads(r.read()).get("status") == "ok"
    except Exception:
        pass

    for q in queries:
        entry = {
            "query": q["query"],
            "expect": q["expect"],
            "category": q["category"],
            "loam_score": 0.0,
            "baseline_score": 0.0,
        }

        # Loam 上下文
        if loam_available:
            try:
                body = json.dumps({"query": q["query"]}).encode()
                req = urllib.request.Request(
                    f"{loam_url}/context",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    ctx = json.loads(r.read())
                    ctx_text = str(ctx.get("text", ""))
            except Exception:
                ctx_text = ""
        else:
            ctx_text = "(loam 未运行，跳过)"

        entry["loam_score"] = _score_recall(ctx_text, q["expect"])
        results["loam"]["scores"].append(entry["loam_score"])

        # Baseline 上下文
        base_text = _simple_baseline_context(all_turns, q["query"])
        entry["baseline_score"] = _score_recall(base_text, q["expect"])
        results["baseline"]["scores"].append(entry["baseline_score"])

        results["queries"].append(entry)

    # 计算平均分
    if results["loam"]["scores"]:
        results["loam"]["avg"] = sum(results["loam"]["scores"]) / len(results["loam"]["scores"])
    if results["baseline"]["scores"]:
        results["baseline"]["avg"] = sum(results["baseline"]["scores"]) / len(results["baseline"]["scores"])

    # 按类别分
    for entry in results["queries"]:
        cat = entry["category"]
        for system in ("loam", "baseline"):
            key = f"{system}_score"
            if cat not in results[system]["by_category"]:
                results[system]["by_category"][cat] = []
            results[system]["by_category"][cat].append(entry[key])

    for system in ("loam", "baseline"):
        for cat in results[system]["by_category"]:
            scores = results[system]["by_category"][cat]
            results[system]["by_category"][cat] = {
                "scores": scores,
                "avg": sum(scores) / len(scores) if scores else 0.0,
            }

    # 对比结论
    diff = results["loam"]["avg"] - results["baseline"]["avg"]
    if diff > 0.1:
        results["verdict"] = f"loam 优于 baseline (+{diff:.2f})"
    elif diff < -0.1:
        results["verdict"] = f"baseline 优于 loam ({diff:.2f})"
    else:
        results["verdict"] = f"两者相当 (差异 {diff:.2f})"

    if not loam_available:
        results["note"] = "loam 服务未运行，loam 分数均为 0。启动 loam 后重新运行 benchmark 以获取真实对比。"

    return results


def main():
    p = argparse.ArgumentParser(description="loam self-benchmark")
    p.add_argument("--data", help="JSON 格式的对话数据文件")
    p.add_argument("--loam-url", default="http://127.0.0.1:8765", help="loam 服务地址")
    p.add_argument("--output", default="benchmark_results.json", help="输出文件")
    args = p.parse_args()

    print("=" * 50)
    print("loam self-benchmark")
    print("=" * 50)

    results = run_benchmark(data_path=args.data, loam_url=args.loam_url)

    # 打印报告
    print(f"\n数据: {results['data_source']}")
    print(f"对话轮次: {results['total_turns']}")
    print(f"测试查询: {results['total_queries']}")
    if results.get("note"):
        print(f"\n⚠️  {results['note']}")

    print(f"\n--- 召回率 ---")
    print(f"loam:     {results['loam']['avg']:.2%}")
    print(f"baseline: {results['baseline']['avg']:.2%}")
    print(f"\n结论: {results['verdict']}")

    print(f"\n--- 按类别 ---")
    all_cats = sorted(set(
        list(results["loam"]["by_category"].keys())
        + list(results["baseline"]["by_category"].keys())
    ))
    for cat in all_cats:
        l = results["loam"]["by_category"].get(cat, {}).get("avg", 0)
        b = results["baseline"]["by_category"].get(cat, {}).get("avg", 0)
        print(f"  {cat:20s}  loam: {l:.2%}  baseline: {b:.2%}")

    print(f"\n--- 逐条 ---")
    for i, q in enumerate(results["queries"], 1):
        print(f"  {i}. {q['query'][:40]:40s}  loam: {q['loam_score']:.2%}  base: {q['baseline_score']:.2%}")

    # 保存
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 {args.output}")


if __name__ == "__main__":
    main()