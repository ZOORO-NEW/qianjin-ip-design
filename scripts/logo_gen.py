#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qianjin-ip-design / 标识生成：用 Logo 专用模型在 WorkBuddy 生成专业标识。

Providers: siliconflow（国内直连免费，默认）/ recraft（矢量友好）/ openai（gpt-image-1）/ ideogram（文字最强）。
API key 仅从环境变量读取，绝不硬编码、绝不打印。
依赖：仅 Python 标准库（urllib/json/base64/os），无需 pip。

与 qianjin-logo-gen 共享同一套引擎框架。本脚本随 qianjin-ip-design 内置，使技能可独立出图。
硅基流动默认模型设为 Qwen/Qwen-Image（当前账号默认可用、收敛强、单色禁渐变听话）；
账户充值激活 FLUX.1-dev 后，用 --model black-forest-labs/FLUX.1-dev 获得更优收敛。
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error

# 每次自动追加的 Logo 专业约束（等价文章里的"禁用渐变/3D/写实阴影"）。
BASE_CONSTRAINTS = (
    "flat vector logo, minimal, solid color, clean geometric, "
    "professional brand mark, no gradient, no 3D, no photorealism, "
    "no drop shadow, high contrast, balanced composition"
)
# 第三层 应用约束：符号优先，绕开文字翻车。
NO_TEXT = "no text, no letters, no words, pure symbol mark only"

# 第一层 风格锚定预设（可扩展）。
GENRE_PRESETS = {
    "swiss": "Swiss international style, sans-serif, grid, large negative space",
    "bauhaus": "Bauhaus geometric, primary colors, basic shapes, functionalism",
    "muji": "Japanese muji style, muted natural tones, restrained, organic feel",
    "badge": "vintage badge, thick stroke, stamp feel, serif skeleton",
    "memphis": "Memphis style, clashing geometric color blocks, playful offset",
    "guofeng": "Chinese guofeng, songti skeleton, ample whitespace, ink accent",
}


def build_prompt(brief, genre, style, no_text):
    parts = [brief.strip()]
    if genre:
        preset = GENRE_PRESETS.get(genre.lower())
        parts.append(preset if preset else genre.strip())
    if style:
        parts.append(style.strip())
    parts.append(BASE_CONSTRAINTS)
    if no_text:
        parts.append(NO_TEXT)
    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip())


def _post(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.read().decode("utf-8"), resp.status
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace"), e.code


def call_recraft(prompt, num, vector, size):
    key = os.environ.get("RECRAFT_API_KEY")
    if not key:
        raise SystemExit("缺少环境变量 RECRAFT_API_KEY")
    payload = {
        "prompt": prompt,
        "model": "recraftv3",
        "style": "vector_illustration",
        "image_size": size,
        "num_images": num,
        "response_format": "svg" if vector else "url",
    }
    body, status = _post(
        "https://external.api.recraft.ai/v1/images/generations",
        {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        payload,
    )
    if status != 200:
        raise SystemExit("Recraft HTTP %d: %s" % (status, body))
    items = json.loads(body).get("data", [])
    urls = [d.get("url") for d in items if d.get("url")]
    return urls, None


def call_openai(prompt, num, size, transparent, quality):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("缺少环境变量 OPENAI_API_KEY")
    allowed = {"1024x1024", "1024x1536", "1536x1024"}
    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": size if size in allowed else "1024x1024",
        "quality": quality,
        "n": num,
    }
    if transparent:
        payload["background"] = "transparent"
    body, status = _post(
        "https://api.openai.com/v1/images/generations",
        {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        payload,
    )
    if status != 200:
        raise SystemExit("OpenAI HTTP %d: %s" % (status, body))
    data = json.loads(body).get("data", [])
    urls, b64s = [], []
    for d in data:
        if d.get("b64_json"):
            b64s.append(d["b64_json"])
        elif d.get("url"):
            urls.append(d["url"])
    return urls, b64s


def call_ideogram(prompt, num, aspect):
    key = os.environ.get("IDEOGRAM_API_KEY")
    if not key:
        raise SystemExit("缺少环境变量 IDEOGRAM_API_KEY")
    payload = {
        "image_request": {
            "prompt": prompt,
            "model": "V_2_TURBO",
            "aspect_ratio": aspect,
            "magic_prompt_option": "OFF",  # 保证文字准确，不被改写
            "style_type": "DESIGN",
            "num_images": num,
        }
    }
    body, status = _post(
        "https://api.ideogram.ai/generate",
        {"Api-Key": key, "Content-Type": "application/json"},
        payload,
    )
    if status != 200:
        raise SystemExit("Ideogram HTTP %d: %s" % (status, body))
    items = json.loads(body).get("data", [])
    urls = [d.get("url") for d in items if d.get("url")]
    return urls, None


def call_siliconflow(prompt, num, size, model):
    key = os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        raise SystemExit("缺少环境变量 SILICONFLOW_API_KEY")
    w, h = (size.split("x") + ["1024", "1024"])[:2]

    def _one(n):
        payload = {
            "model": model,
            "prompt": prompt,
            "image_size": "%sx%s" % (w, h),
            "num_inference_steps": 20,
            "n": n,
        }
        body, status = _post(
            "https://api.siliconflow.cn/v1/images/generations",
            {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            payload,
        )
        if status != 200:
            raise SystemExit("SiliconFlow HTTP %d: %s" % (status, body))
        parsed = json.loads(body)
        items = parsed.get("images") or parsed.get("data") or []
        return [d.get("url") for d in items if d.get("url")]

    urls = _one(num)
    # Qwen-Image 等单次只返回 1 张（忽略 n>1），自动补足到 num 张。
    guard = 0
    while len(urls) < num and guard < num:
        urls += _one(1)
        guard += 1
    return urls[:num], None


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "qianjin-ip-design"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(path, "wb") as f:
        f.write(data)


def main():
    ap = argparse.ArgumentParser(description="qianjin-ip-design: 标识/Logo 生成")
    ap.add_argument("--provider", required=True, choices=["recraft", "openai", "ideogram", "siliconflow"])
    ap.add_argument("--brief", required=True, help="Logo 需求/ brief，可用中文")
    ap.add_argument("--genre", help="风格锚定: swiss/bauhaus/muji/badge/memphis/guofeng 或任意流派名")
    ap.add_argument("--style", help="形态约束补充（图形/构图/母题）")
    ap.add_argument("--no-text", action="store_true", help="符号优先，不生成文字")
    ap.add_argument("--vector", action="store_true", help="Recraft: 请求 SVG 矢量输出")
    ap.add_argument("--num", type=int, default=3)
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--aspect", default="ASPECT_1_1", help="Ideogram 宽高比")
    ap.add_argument("--transparent", action="store_true", help="OpenAI 透明底")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--model", default="Qwen/Qwen-Image",
                    help="SiliconFlow 模型ID（仅 siliconflow 用）。默认 Qwen/Qwen-Image（收敛强、当前账号可用）；"
                         "账户充值激活后可用 black-forest-labs/FLUX.1-dev（收敛最优）；"
                         "中文强可用 Kwai-Kolors/Kolors；快速免费档用 FLUX.1-schnell / SDXL")
    ap.add_argument("--out", default="logo_output")
    args = ap.parse_args()

    prompt = build_prompt(args.brief, args.genre, args.style, args.no_text)
    os.makedirs(args.out, exist_ok=True)

    urls, b64s = [], []
    if args.provider == "recraft":
        urls, _ = call_recraft(prompt, args.num, args.vector, args.size)
    elif args.provider == "openai":
        urls, b64s = call_openai(prompt, args.num, args.size, args.transparent, args.quality)
    elif args.provider == "siliconflow":
        urls, _ = call_siliconflow(prompt, args.num, args.size, args.model)
    else:
        urls, _ = call_ideogram(prompt, args.num, args.aspect)

    saved = []
    for i, u in enumerate(urls or []):
        ext = "svg" if (args.provider == "recraft" and args.vector) else "png"
        p = os.path.join(args.out, "logo_%d.%s" % (i + 1, ext))
        try:
            download(u, p)
            saved.append(p)
        except Exception as e:
            print("! 下载失败 %s: %s" % (u, e))
    for i, b in enumerate(b64s or []):
        p = os.path.join(args.out, "logo_%d.png" % (len(saved) + i + 1))
        with open(p, "wb") as f:
            f.write(base64.b64decode(b))
        saved.append(p)

    print(json.dumps({
        "prompt_used": prompt,
        "saved": saved,
        "urls": urls or [],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
