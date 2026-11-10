"""Calculate chemical quantitation from explicit, traceable measurements.

This standard-library helper does not interpret spectral images or assign peaks.
"""

import argparse
import json
import math
import sys
from pathlib import Path


class InputIssue(ValueError):
    def __init__(self, field, message, code="invalid"):
        self.field, self.message, self.code = field, message, code
        super().__init__(f"{field}: {message}")


def number(obj, key, prefix="", minimum=0, positive=False, maximum=None, integer=False):
    field = f"{prefix}.{key}" if prefix else key
    raw = obj.get(key)
    if raw is None:
        raise InputIssue(field, "缺少测量值", "missing")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise InputIssue(field, "必须为有限数值")
    if raw < minimum or (positive and raw <= minimum):
        raise InputIssue(field, f"必须{'大于' if positive else '不小于'} {minimum}")
    if maximum is not None and raw > maximum:
        raise InputIssue(field, f"必须不大于 {maximum}")
    if integer and raw != int(raw):
        raise InputIssue(field, "必须为整数核数")
    return float(raw)


def group(obj, key):
    raw = obj.get(key)
    if raw is None:
        raise InputIssue(key, "缺少对象", "missing")
    if not isinstance(raw, dict):
        raise InputIssue(key, "必须为对象")
    return raw


def text_field(obj, key, prefix=""):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputIssue(f"{prefix}.{key}" if prefix else key, "缺少明确的来源或口径", "missing")
    return value


def standard_amount(sample):
    standard = group(sample, "standard")
    if standard.get("amount_mmol") is not None:
        if any(standard.get(k) is not None for k in ("mass_mg", "molar_mass_g_mol", "purity_fraction")):
            raise InputIssue("standard", "有效物质的量与质量换算参数应选择一种输入方式")
        return number(standard, "amount_mmol", "standard", positive=True)
    return (
        number(standard, "mass_mg", "standard", positive=True)
        / number(standard, "molar_mass_g_mol", "standard", positive=True)
        * number(standard, "purity_fraction", "standard", positive=True, maximum=1)
    )


def sampling_factor(sample):
    sampling = group(sample, "sampling")
    text_field(sampling, "basis", "sampling")
    return number(sampling, "aliquot_to_total_factor", "sampling", minimum=1)


def theoretical_amount(sample):
    if sample.get("theoretical_product_mmol") is not None:
        return number(sample, "theoretical_product_mmol", positive=True)
    limiting = group(sample, "limiting_reagent")
    return (
        number(limiting, "amount_mmol", "limiting_reagent", positive=True)
        * number(sample, "product_stoichiometric_coefficient", positive=True)
        / number(limiting, "stoichiometric_coefficient", "limiting_reagent", positive=True)
    )


def analyze(sample):
    result = {
        "experiment_id": sample.get("experiment_id"),
        "sample_id": sample.get("sample_id"),
        "method": sample.get("method"),
        "status": "complete",
        "metrics": [],
        "diagnostics": [],
        "evidence": sample.get("evidence", []),
        "input_record": sample,
    }

    def issue(field, message, code="review"):
        result["diagnostics"].append({"field": field, "code": code, "message": message})

    def metric(name, value, unit, formula, basis):
        if not math.isfinite(value):
            raise InputIssue(name, "计算结果超出有限数范围")
        result["metrics"].append({"name": name, "value": value, "unit": unit,
                                  "formula": formula, "basis": basis})
        if unit == "%" and not 0 <= value <= 100:
            issue(name, "百分数超出 0～100%，需复核归属、采样、纯度或校准")

    product_amount = None
    substrate_amount = None
    yield_name = None
    corrected_product = None
    try:
        text_field(sample, "sample_id")
        method = text_field(sample, "method")
        if not result["evidence"]:
            issue("evidence", "计算输入需补充原始测量文件或记录位置", "missing")
        if method == "qnmr":
            standard = standard_amount(sample)
            scale = sampling_factor(sample)
            std_signal = group(sample, "standard_signal")
            std_per_nucleus = (
                number(std_signal, "integral", "standard_signal", positive=True)
                / number(std_signal, "nuclei_count", "standard_signal", minimum=1, integer=True)
            )
            checks = sample.get("quantitation_checks", {})
            if not isinstance(checks, dict):
                raise InputIssue("quantitation_checks", "必须为对象")
            for check in ("nonoverlapping_signals", "quantitative_acquisition"):
                if checks.get(check) is not True:
                    issue(f"quantitation_checks.{check}", "该定量条件需确认；数值作为待复核算术值")

            def signal_amount(key):
                signal = group(sample, key)
                integral = number(signal, "integral", key)
                nuclei = number(signal, "nuclei_count", key, minimum=1, integer=True)
                return integral / nuclei / std_per_nucleus * standard * scale

            product_amount = signal_amount("product_signal")
            if sample.get("substrate_signal") is not None:
                substrate_amount = signal_amount("substrate_signal")
            yield_name = "qnmr_yield_percent"
            amount_formula = "(I_product/N_product)/(I_standard/N_standard)*n_standard*aliquot_to_total_factor"
            basis = "qNMR 内标校准、取样口径对应的全反应产物量"
        elif method == "chromatography_internal_standard":
            convention = "(A_product/n_product)/(A_standard/n_standard)"
            if sample.get("response_factor_definition") != convention:
                raise InputIssue("response_factor_definition", f"需明确采用 {convention}")
            text_field(sample, "calibration_source")
            product_amount = (
                number(sample, "product_peak_area")
                / number(sample, "standard_peak_area", positive=True)
                / number(sample, "relative_response_factor", positive=True)
                * standard_amount(sample) * sampling_factor(sample)
            )
            yield_name = "chromatographic_yield_percent"
            amount_formula = "(A_product/A_standard)/RRF*n_standard*aliquot_to_total_factor"
            basis = "色谱内标响应因子校准、取样口径对应的全反应产物量"
        elif method == "chromatography_external_standard":
            calibration = group(sample, "calibration")
            text_field(calibration, "source", "calibration")
            slope = number(calibration, "slope_area_per_mmol_L", "calibration", positive=True)
            intercept = calibration.get("intercept_area")
            if isinstance(intercept, bool) or not isinstance(intercept, (int, float)) or not math.isfinite(intercept):
                raise InputIssue("calibration.intercept_area", "需提供有限的拟合截距", "missing" if intercept is None else "invalid")
            low = number(calibration, "min_concentration_mmol_L", "calibration")
            high = number(calibration, "max_concentration_mmol_L", "calibration", positive=True)
            if high <= low:
                raise InputIssue("calibration", "校准上限必须大于下限")
            concentration = (number(sample, "product_peak_area") - intercept) / slope
            if concentration < 0:
                raise InputIssue("product_peak_area", "扣除截距后为负，需采用检测限/定量限规则处理")
            if not low <= concentration <= high:
                issue("product_peak_area", "计算浓度超出标准曲线校准范围")
            metric("measured_concentration_mmol_L", concentration, "mmol/L", "(A_product-intercept)/slope", "最终测量溶液")
            product_amount = (
                concentration * number(sample, "dilution_factor", minimum=1)
                * number(sample, "solution_volume_ml", positive=True) / 1000
                * sampling_factor(sample)
            )
            yield_name = "chromatographic_yield_percent"
            amount_formula = "c_measured*dilution_factor*solution_volume_ml/1000*aliquot_to_total_factor"
            basis = "色谱外标校准、稀释与取样口径对应的全反应产物量"
        elif method == "isolated_mass":
            if sample.get("mass_basis") != "entire_isolated_product":
                raise InputIssue("mass_basis", "需确认整份干燥分离产物的质量口径", "missing")
            product_amount = number(sample, "product_mass_mg") / number(sample, "product_molar_mass_g_mol", positive=True)
            yield_name = "isolated_yield_percent"
            amount_formula = "product_mass_mg/product_molar_mass_g_mol"
            basis = "整份分离产物称重，未经纯度修正"
        elif method == "area_fraction":
            text_field(sample, "included_peaks_basis")
            fraction = number(sample, "product_peak_area") / number(sample, "total_included_peak_area", positive=True) * 100
            metric("chromatographic_area_fraction_percent", fraction, "%", "A_product/sum(A_included)*100", sample["included_peaks_basis"])
        elif method == "qualitative":
            result["status"] = "qualitative"
        else:
            raise InputIssue("method", "不支持的定量方法")
        if product_amount is not None:
            metric("product_amount_mmol", product_amount, "mmol", amount_formula, basis)
            if method == "isolated_mass" and sample.get("product_purity_fraction") is not None:
                purity = number(sample, "product_purity_fraction", maximum=1)
                text_field(sample, "product_purity_source")
                corrected_product = product_amount * purity
                metric("purity_corrected_product_amount_mmol", corrected_product, "mmol", "product_amount_mmol*product_purity_fraction", "独立纯度修正的分离产物量")
            theoretical = theoretical_amount(sample)
            metric("theoretical_product_mmol", theoretical, "mmol", "provided amount or n_limiting*nu_product/nu_limiting", "实际投料的化学计量上限")
            metric(yield_name, product_amount / theoretical * 100, "%", "product_amount_mmol/theoretical_product_mmol*100", basis)
            if corrected_product is not None:
                metric("purity_corrected_isolated_yield_percent", corrected_product / theoretical * 100, "%", "purity_corrected_product_amount_mmol/theoretical_product_mmol*100", "独立纯度修正的分离产率")
    except InputIssue as error:
        issue(error.field, error.message, error.code)

    try:
        if sample.get("remaining_substrate_mmol") is not None:
            provided = number(sample, "remaining_substrate_mmol")
            if substrate_amount is not None and not math.isclose(provided, substrate_amount, rel_tol=1e-6, abs_tol=1e-9):
                issue("remaining_substrate_mmol", "输入剩余底物量与 qNMR 计算值冲突；转化率暂缓计算")
                substrate_amount = None
            else:
                substrate_amount = provided
        if substrate_amount is not None:
            metric("remaining_substrate_mmol", substrate_amount, "mmol", "calibrated input or substrate qNMR ratio", "全反应剩余底物量")
            initial = number(sample, "initial_substrate_mmol", positive=True)
            metric("conversion_percent", (initial - substrate_amount) / initial * 100, "%", "(n_initial-n_remaining)/n_initial*100", "同一种底物、同一实际反应口径")
        elif sample.get("initial_substrate_mmol") is not None and sample.get("remaining_substrate_mmol") is None and sample.get("substrate_signal") is None:
            issue("remaining_substrate_mmol", "计算转化率需要剩余底物量", "missing")
    except InputIssue as error:
        issue(error.field, error.message, error.code)
    if any(i["code"] == "invalid" for i in result["diagnostics"]):
        result["status"] = "invalid"
    elif result["diagnostics"]:
        result["status"] = "partial"
    return result


def markdown(results):
    lines = ["# 化学合成定量计算明细", "", "结构判断与谱图观察见智能体的谱图分析报告。", ""]
    for result in results:
        lines.extend([f"## {result['sample_id']}", "", f"方法：`{result['method']}`；计算状态：`{result['status']}`。", "",
                      "| 数值项 | 结果 | 单位 | 口径 |", "|---|---:|---|---|"])
        for item in result["metrics"]:
            lines.append(f"| {item['name']} | {item['value']:.8g} | {item['unit']} | {item['basis']} |")
        lines.append("")
        for item in result["metrics"]:
            lines.append(f"- `{item['name']}`：`{item['formula']}`")
        if result["diagnostics"]:
            lines.extend(["", "复核项：", ""])
            for item in result["diagnostics"]:
                lines.append(f"- `{item['field']}`：{item['message']}")
        lines.extend(["", "输入数值与证据来源随 JSON 计算结果归档。", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="根据结构化谱图测量和实验记录计算化学产率等信息")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        paths = [args.input.resolve(), args.output.resolve()]
        if args.report:
            paths.append(args.report.resolve())
        if len(set(paths)) != len(paths):
            raise ValueError("输入、JSON 输出与报告路径必须不同")
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("顶层必须为样品对象或包含 samples 的对象")
        samples = payload.get("samples", [payload])
        if not isinstance(samples, list) or not samples or any(not isinstance(s, dict) for s in samples):
            raise ValueError("samples 必须为非空样品对象数组")
        ids = [s.get("sample_id") for s in samples]
        valid_ids = [i for i in ids if isinstance(i, str) and i.strip()]
        if len(valid_ids) != len(set(valid_ids)):
            raise ValueError("同批次 sample_id 必须唯一")
        results = [analyze(sample) for sample in samples]
        output = {"schema_version": "1.0", "results": results}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(markdown(results), encoding="utf-8")
        print(json.dumps({"output": str(args.output), "sample_count": len(results),
                          "statuses": [r["status"] for r in results]}, ensure_ascii=False))
        return 1 if any(r["status"] == "invalid" for r in results) else 0
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(f"输入或计算错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
