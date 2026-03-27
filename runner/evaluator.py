#!/usr/bin/env python3
"""
evaluator.py — A-Group Benchmark: System Prompt method
Evaluates game code generation across models using agent prompts as system prompts.

Usage:
  # Set API keys first
  export DEEPSEEK_API_KEY="sk-..."
  export GEMINI_API_KEY="AIza..."

  # Run full benchmark
  python runner/evaluator.py

  # Run single model + single task (for testing)
  python runner/evaluator.py --model deepseek-chat --task 0

  # Run with multi-turn self-repair
  python runner/evaluator.py --multi-turn

  # Dry run (print config, no API calls)
  python runner/evaluator.py --dry-run
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from runner.api_client import create_client, APIResponse
from runner.code_extractor import extract_code, save_code, compute_code_metrics
from runner.screenshotter import take_screenshot
from runner.report import generate_report


# ─── Config Loading ───────────────────────────────────────────────

def load_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_system_prompt(agent_config: dict, prompts_dir: str) -> str:
    """Load and concatenate all agent prompt files into one system prompt."""
    parts = []
    for filename in agent_config["prompt_files"]:
        filepath = os.path.join(prompts_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                parts.append(f.read().strip())
        else:
            print(f"  [Warning] Prompt file not found: {filepath}")
    return "\n\n---\n\n".join(parts)


# ─── Single-Turn Evaluation ──────────────────────────────────────

def run_single_turn(client, system_prompt: str, task_prompt: str) -> dict:
    """
    Single-turn: one API call, get code back.
    Returns dict with response data and metrics.
    """
    messages = [{"role": "user", "content": task_prompt}]

    t0 = time.time()
    resp: APIResponse = client.chat(system_prompt, messages)
    total_time_sec = round(time.time() - t0, 1)

    return {
        "content": resp.content,
        "prompt_tokens": resp.prompt_tokens,
        "completion_tokens": resp.completion_tokens,
        "total_tokens": resp.total_tokens,
        "latency_ms": resp.latency_ms,
        "total_time_sec": total_time_sec,
        "rounds": 1,
        "iterations": 0,
        "error": resp.error,
        "raw_usage": resp.raw_usage,
    }


# ─── Multi-Turn Evaluation (Self-Repair) ─────────────────────────

def basic_html_check(code: str) -> str:
    """
    Very basic syntax check for HTML game code.
    Returns error description or empty string if OK.
    """
    if not code:
        return "No code was generated."

    errors = []
    lower = code.lower()

    # Check basic HTML structure
    if "<html" not in lower and "<!doctype" not in lower:
        errors.append("Missing <html> or <!DOCTYPE> tag.")

    # Check for unclosed script/style tags
    if lower.count("<script") != lower.count("</script>"):
        errors.append("Unclosed <script> tag detected.")
    if lower.count("<style") != lower.count("</style>"):
        errors.append("Unclosed <style> tag detected.")

    # Check for obvious JS errors (very basic)
    if "syntaxerror" in lower or "referenceerror" in lower:
        errors.append("Code contains error references.")

    return "; ".join(errors)


def run_multi_turn(client, system_prompt: str, task_prompt: str, max_iter: int = 5) -> dict:
    """
    Multi-turn: generate code, check for issues, ask model to fix. Repeat up to max_iter.
    """
    messages = [{"role": "user", "content": task_prompt}]

    total_prompt_tokens = 0
    total_completion_tokens = 0
    all_latency = 0
    rounds = 0
    iterations = 0
    last_content = ""

    t0 = time.time()

    for i in range(max_iter + 1):
        resp: APIResponse = client.chat(system_prompt, messages)
        rounds += 1
        total_prompt_tokens += resp.prompt_tokens
        total_completion_tokens += resp.completion_tokens
        all_latency += resp.latency_ms

        if resp.error:
            last_content = resp.content
            break

        last_content = resp.content
        code = extract_code(resp.content)
        check_result = basic_html_check(code)

        if not check_result:
            # Code looks OK, stop iterating
            break

        if i < max_iter:
            # Ask model to fix
            iterations += 1
            messages.append({"role": "assistant", "content": resp.content})
            fix_prompt = (
                f"The code you generated has the following issues:\n{check_result}\n\n"
                f"Please fix these issues and provide the complete corrected HTML file."
            )
            messages.append({"role": "user", "content": fix_prompt})
            print(f"    ↻ Iteration {iterations}: {check_result[:80]}...")

    total_time_sec = round(time.time() - t0, 1)

    return {
        "content": last_content,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "latency_ms": all_latency,
        "total_time_sec": total_time_sec,
        "rounds": rounds,
        "iterations": iterations,
        "error": resp.error if resp.error else "",
        "raw_usage": {},
    }


# ─── Main Orchestrator ───────────────────────────────────────────

def run_benchmark(args):
    config = load_json(os.path.join(PROJECT_ROOT, "config", "models.json"))
    tasks = load_json(os.path.join(PROJECT_ROOT, "config", "tasks.json"))
    prompts_dir = os.path.join(PROJECT_ROOT, "prompts")
    outputs_dir = os.path.join(PROJECT_ROOT, "outputs")

    models = config["models"]
    agents = config["agents"]
    max_iter = config.get("max_iterations", 5)

    # Filter if specific model/task requested
    if args.model:
        models = [m for m in models if m["id"] == args.model]
    if args.task is not None:
        tasks = [t for t in tasks if t["id"] == args.task]

    if not models:
        print("❌ No matching models found.")
        return
    if not tasks:
        print("❌ No matching tasks found.")
        return

    # Use first agent config (can be extended to loop over agents)
    agent = agents[0]
    system_prompt = load_system_prompt(agent, prompts_dir)

    if args.dry_run:
        print("═" * 60)
        print("DRY RUN — Configuration Summary")
        print("═" * 60)
        print(f"Models:  {[m['id'] for m in models]}")
        print(f"Tasks:   {[t['name'] for t in tasks]}")
        print(f"Agent:   {agent['name']}")
        print(f"Mode:    {'Multi-turn (max {})'.format(max_iter) if args.multi_turn else 'Single-turn'}")
        print(f"System prompt length: {len(system_prompt)} chars")
        print(f"\nSystem prompt preview:\n{system_prompt[:500]}...")
        return

    # ── Run evaluations ──
    all_results = []
    total_runs = len(models) * len(tasks)
    run_idx = 0

    print("═" * 60)
    print(f"🎮 Game Code Generation Benchmark — A-Group (System Prompt)")
    print(f"   Models: {[m['id'] for m in models]}")
    print(f"   Tasks:  {len(tasks)} games")
    print(f"   Agent:  {agent['name']}")
    print(f"   Mode:   {'Multi-turn' if args.multi_turn else 'Single-turn'}")
    print("═" * 60)

    for model_config in models:
        client = create_client(model_config)
        model_id = model_config["id"]

        # Verify API key
        api_key = os.environ.get(model_config["api_key_env"], "")
        if not api_key:
            print(f"\n⚠️  Skipping {model_id}: {model_config['api_key_env']} not set")
            continue

        for task in tasks:
            run_idx += 1
            task_id = task["id"]
            task_name = task["name"]
            task_prompt = task["prompt"]

            print(f"\n[{run_idx}/{total_runs}] {model_id} × {task_name}")
            print(f"  Calling API...")

            # Run evaluation
            if args.multi_turn:
                result = run_multi_turn(client, system_prompt, task_prompt, max_iter)
            else:
                result = run_single_turn(client, system_prompt, task_prompt)

            if result["error"]:
                print(f"  ❌ Error: {result['error'][:100]}")
            else:
                print(f"  ✅ Got response ({result['completion_tokens']} tokens, {result['total_time_sec']}s)")

            # Extract and save code
            code = extract_code(result["content"])
            code_metrics = compute_code_metrics(code)
            html_path = ""
            screenshot_path = ""

            if code:
                html_path = save_code(code, os.path.join(outputs_dir, "code"), model_id, task_id, task_name)
                print(f"  📄 Code: {code_metrics['total_lines']} lines, saved to {html_path}")

                # Take screenshot
                ss_dir = os.path.join(outputs_dir, "screenshots")
                ss_filename = f"{model_id}_{task_id}_{task_name.replace(' ', '_')}.png"
                ss_path = os.path.join(ss_dir, ss_filename)

                if not args.no_screenshot:
                    screenshot_path = take_screenshot(html_path, ss_path)
                    if screenshot_path:
                        print(f"  📸 Screenshot: {screenshot_path}")
                    else:
                        print(f"  ⚠️  Screenshot failed (install: pip install playwright && playwright install chromium)")
            else:
                print(f"  ⚠️  No code extracted from response")

            # Build result record (matching the Excel columns)
            record = {
                "测评ID": task_id,
                "任务名称": task_name,
                "任务描述": task_prompt[:60] + "..." if len(task_prompt) > 60 else task_prompt,
                "语言模型": model_id,
                "涉及Agent": agent["name"],
                "对话轮次": result["rounds"],
                "AI提问消耗Token": result["prompt_tokens"],
                "AI回答消耗Token": result["completion_tokens"],
                "总消耗Token": result["total_tokens"],
                "代码总行数": code_metrics["total_lines"],
                "代码文件数": code_metrics["file_count"],
                "自我迭代次数": result["iterations"],
                "总耗时": result["total_time_sec"],
                "运行结果截图": os.path.basename(screenshot_path) if screenshot_path else "",
                # Internal fields (not displayed but used for report)
                "_screenshot_path": screenshot_path,
                "_html_path": html_path,
                "_error": result["error"],
            }
            all_results.append(record)

            # Save intermediate results (in case of crash)
            interim_path = os.path.join(outputs_dir, "results_interim.json")
            with open(interim_path, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)

    # ── Generate Excel report ──
    if all_results:
        report_path = os.path.join(outputs_dir, "benchmark_results.xlsx")
        generate_report(all_results, report_path)

        # Also save raw JSON
        json_path = os.path.join(outputs_dir, "benchmark_results.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"📊 JSON results: {json_path}")
    else:
        print("\n⚠️  No results collected. Check API keys and network.")


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Game Code Generation Benchmark — A-Group")
    parser.add_argument("--model", type=str, help="Run only this model (e.g., deepseek-chat)")
    parser.add_argument("--task", type=int, help="Run only this task ID (e.g., 0)")
    parser.add_argument("--multi-turn", action="store_true", help="Enable multi-turn self-repair mode")
    parser.add_argument("--no-screenshot", action="store_true", help="Skip screenshot capture")
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit, no API calls")
    args = parser.parse_args()
    run_benchmark(args)


if __name__ == "__main__":
    main()
