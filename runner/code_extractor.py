"""
code_extractor.py — Extract code blocks from LLM responses and compute metrics.
"""

import re
import os


def extract_code(response_text: str) -> str:
    """
    Extract the best HTML code block from the model's response.
    Priority: ```html > ```htm > any ``` block containing <!DOCTYPE or <html > raw response
    """

    # 1) Try ```html ... ``` blocks
    html_blocks = re.findall(r"```html\s*\n(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
    if html_blocks:
        return _pick_longest(html_blocks)

    # 2) Try ```htm blocks
    htm_blocks = re.findall(r"```htm\s*\n(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
    if htm_blocks:
        return _pick_longest(htm_blocks)

    # 3) Try any fenced block that looks like HTML
    all_blocks = re.findall(r"```\w*\s*\n(.*?)```", response_text, re.DOTALL)
    html_like = [b for b in all_blocks if _looks_like_html(b)]
    if html_like:
        return _pick_longest(html_like)

    # 4) Try to find raw HTML in the response (no fences)
    m = re.search(r"(<!DOCTYPE html.*</html>)", response_text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)

    # 5) Last resort: if response itself looks like HTML
    if _looks_like_html(response_text):
        return response_text.strip()

    return ""


def _looks_like_html(text: str) -> bool:
    t = text.strip().lower()
    return any(marker in t for marker in ["<!doctype", "<html", "<head", "<body", "<canvas", "<style"])


def _pick_longest(blocks: list[str]) -> str:
    return max(blocks, key=len).strip()


def save_code(code: str, output_dir: str, model_id: str, task_id: int, task_name: str) -> str:
    """Save extracted code to file. Returns the file path."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", task_name)
    dir_path = os.path.join(output_dir, model_id)
    os.makedirs(dir_path, exist_ok=True)
    filename = f"{task_id}_{safe_name}.html"
    filepath = os.path.join(dir_path, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    return filepath


def compute_code_metrics(code: str) -> dict:
    """Compute basic code metrics."""
    if not code:
        return {"total_lines": 0, "code_lines": 0, "file_count": 1}

    lines = code.split("\n")
    total_lines = len(lines)
    code_lines = sum(1 for line in lines if line.strip())

    # Count logical "files" by checking <style>, <script>, and HTML sections
    file_count = 1  # The HTML file itself
    if "<style" in code.lower():
        file_count += 1  # Embedded CSS
    if "<script" in code.lower():
        file_count += 1  # Embedded JS

    return {
        "total_lines": total_lines,
        "code_lines": code_lines,
        "file_count": file_count,
    }
