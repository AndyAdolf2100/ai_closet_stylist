"""Offline aggregation of measured provider usage; never calls a model."""
import argparse
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

from scripts.measure_text_cost import accounting


def mean(values):
    return sum(map(Decimal, values)) / len(values)


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * fraction) - 1]


def render(data):
    rows = data["cases"]
    keys = [(r["case"], r["repeat"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate samples must not be counted twice")
    models = sorted({c["model"] for r in rows for c in r["calls"] if c.get("model")})
    lines = ["# 1—7套穿搭文字成本扩样实测（2026-11-02）", "",
             f"采样开始：{data['at']}。响应型号：`{'、'.join(models)}`。",
             f"计划1—7套各{data['repeats']}次；实际完成{len(rows)}次用户请求，"
             f"共{sum(len(r['calls']) for r in rows)}次文字HTTP调用。业务工具全部模拟，不执行图片处理、上传、试穿或个人衣橱访问。", "",
             "## 口径", "",
             "使用当前应用完整plan／style主流程、19件固定合成衣橱、女助理默认人格，每次为独立新会话，无历史、画像或手记。"
             "1—7套仅修改同一提问中的套数，统一人工提供上海晴、15—20℃；真实模型temperature=0.3、思考关闭、输出上限6000。"
             f"并发{data['concurrency']}，按轮次交错不同套数，未主动清理或操纵服务端缓存。重复样本评估固定条件波动，不代表全部生产流量。", "",
             "按[火山方舟官方常规在线价](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh)："
             "输入6元／百万token、缓存命中1.2元／百万token、输出30元／百万token。"
             "公式：`((input-cached)*6+cached*1.2+output*30)/1000000`元。输入已含缓存，不重复累计。"
             "费用包含全部需求理解、生成、结构与业务修复；不是账户账单，不含合同优惠、免费额度及图片／基础设施费用。"
             "隐式缓存存储不计费，见[官方缓存说明](https://ark.volcengine.com/region:cn-beijing/docs/context-cache)。", "",
             "## 完整请求链路（每次均值）", "",
             "| 套数 | 完成／计划 | 套数正确 | 输入token | 输出token | 观测缓存费用／元 | 无缓存费用／元 |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    variation, stages, delivered = [], [], []
    all_costs, all_cold = [], []
    for n in range(1, 8):
        group = [r for r in rows if r["case"] == f"day_{n}"]
        met = sum(bool(r.get("expected_count_met")) and not r.get("error") for r in group)
        known = [accounting(r) for r in group]
        known = [a for a in known if a is not None]
        if len(known) != len(group) or not known:
            lines.append(f"| {n} | {len(group)}／{data['repeats']} | {met} | — | — | usage不完整 | — |")
            continue
        costs = [Decimal(a["listed_cny"]) for a in known]
        cold = [Decimal(a["no_cache_cny"]) for a in known]
        all_costs.extend(costs)
        all_cold.extend(cold)
        if met:
            delivered.append(f"| {n} | {met}／{len(group)} | {sum(costs)/met:.4f} | {sum(cold)/met:.4f} |")
        lines.append(f"| {n} | {len(group)}／{data['repeats']} | {met} | {mean([a['input'] for a in known]):,.1f} | "
                     f"{mean([a['output'] for a in known]):,.1f} | {mean(costs):.4f} | {mean(cold):.4f} |")
        variation.append(f"| {n} | {min(costs):.4f}—{max(costs):.4f} | {percentile(costs, .9):.4f} | "
                         f"{percentile(cold, .9):.4f} | {mean(costs)*1000:.2f} | {mean(cold)*1000:.2f} |")
        first = [next((c for c in r["calls"] if c["stage"] == "style" and c.get("usage")), None) for r in group]
        first = [c for c in first if c]
        extra = sum(max(0, len(r["calls"]) - 2) for r in group)
        repaired = sum(len(r["calls"]) > 2 for r in group)
        if first:
            stages.append(f"| {n} | {mean([c['usage']['prompt_tokens'] for c in first]):,.1f} | "
                          f"{mean([c['usage']['completion_tokens'] for c in first]):,.1f} | "
                          f"{repaired}／{len(group)} | {extra} | "
                          f"{sum(a['cached'] for a in known)/sum(a['input'] for a in known):.1%} |")
    lines += ["", "## 波动与每千次预算", "", "P90按最近秩法计算；每组10样本的P90为第9小值，仍不是生产上界。每千次为相同流量结构的线性估算。", "",
              "| 套数 | 观测缓存最小—最大／元 | 观测缓存P90／元 | 无缓存P90／元 | 观测缓存每千次／元 | 无缓存每千次／元 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |", *variation, "", "## 首次回复与额外调用", "",
              "| 套数 | 首次style输入均值 | 首次style输出均值 | 有额外调用的请求 | 额外调用合计 | 输入缓存命中比例 |",
              "| --- | ---: | ---: | --- | ---: | ---: |", *stages, ""]
    errors = Counter(r.get("error", "none") for r in rows)
    mismatches = [(r["case"], r["repeat"], r.get("actual_looks")) for r in rows
                  if not r.get("error") and not r.get("expected_count_met")]
    lines += ["## 汇总与边界", "",
              f"错误计数：`{dict(errors)}`；无异常但套数不匹配：`{mismatches}`。失败请求保留，不以套数正确为条件筛除高成本样本。"
              "缺失usage时不估算、不置零，已知usage完整的失败仍计入费用。", ""]
    lines += ["失败成本分摊到成功交付（实测总成本／正确返回套数的请求数，不是另发重试验证；"
              "仅指无接口错误且套数匹配，不代表穿搭内容质量全部验收）：", "",
              "| 套数 | 正确交付／请求数 | 每次正确交付分摊费用／元 | 无缓存分摊费用／元 |",
              "| --- | --- | ---: | ---: |", *delivered, ""]
    if len(all_costs) == len(rows) and rows:
        lines += [f"本轮刊例测算总费用{sum(all_costs):.6f}元；无缓存假设{sum(all_cold):.6f}元。"
                  f"按1—7套等权，单次均值{mean(all_costs):.4f}元、无缓存均值{mean(all_cold):.4f}元；"
                  f"每千次分别{mean(all_costs)*1000:.2f}元和{mean(all_cold)*1000:.2f}元。", ""]
        matched = sum(bool(r.get("expected_count_met")) and not r.get("error") for r in rows)
        if matched:
            extra_requests = sum(len(r["calls"]) > 2 for r in rows)
            extra_calls = sum(max(0, len(r["calls"]) - 2) for r in rows)
            lines += [f"将全部已测费用分摊到{matched}次按要求套数返回的结果，单次约{sum(all_costs)/matched:.4f}元；"
                      f"无缓存约{sum(all_cold)/matched:.4f}元。{len(rows)}次中有{extra_requests}次出现额外调用，"
                      f"共{extra_calls}次额外调用。该分摊不是实际执行重试的验收。", ""]
    lines += ["更多套数一般增加首轮输出，但额外修复和缓存让总费用不一定单调。用无缓存列作基础预算，"
              "再根据真实生产套数占比、修复率、历史长度与衣橱候选数调整；本轮重复新会话缓存可能较高，不能保证线上同等命中。"
              "本轮不重测普通聊天及周计划；前一轮小样本单列保留，不混入本轮10次均值。", "",
              "原始usage及合成回复：`var/text-cost/expanded-70.json`（不入Git）。复现：", "",
              "```sh", "STYLIST_LEGACY_CONFIG=../ai_closet_agent/config/config.yaml \\",
              "  .venv/bin/python -m scripts.measure_text_cost --live --outfits-only \\",
              "  --counts 1 2 3 4 5 6 7 --repeats 10 --concurrency 6 \\",
              "  --output var/text-cost/expanded-70.json",
              ".venv/bin/python -m scripts.report_text_cost --input var/text-cost/expanded-70.json \\",
              "  --output docs/TEXT_MODEL_COST_EXPANDED_2026-11-02.md", "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = render(json.loads(Path(args.input).read_text()))
    Path(args.output).write_text(result)


if __name__ == "__main__":
    main()
