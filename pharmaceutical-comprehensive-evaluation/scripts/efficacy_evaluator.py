#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
有效性评价分析器
根据国家药品临床综合评价技术指南 - 有效性维度评价工具
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple

class EfficacyEvaluator:
    """药品有效性综合评价器"""

    def __init__(self):
        self.efficacy_score = 0
        self.results = {}

    def calculate_survival_benefit(self, hr: float, ci_lower: float, ci_upper: float,
                                   median_os_treatment: float, median_os_control: float) -> Dict:
        """
        计算生存获益

        参数:
            hr: 风险比(Hazard Ratio)
            ci_lower: HR的95% CI下限
            ci_upper: HR的95% CI上限
            median_os_treatment: 治疗组中位生存期(月)
            median_os_control: 对照组中位生存期(月)

        返回:
            生存获益分析结果
        """
        # 生存期延长
        os_gain = median_os_treatment - median_os_control

        # 相对风险降低
        rrr = (1 - hr) * 100

        # 统计显著性
        significant = ci_upper < 1.0

        # 临床意义判定
        if os_gain >= 6:
            clinical_significance = '显著'
        elif os_gain >= 3:
            clinical_significance = '中等'
        elif os_gain >= 1:
            clinical_significance = '轻微'
        else:
            clinical_significance = '无'

        return {
            'hr': hr,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'os_gain_months': os_gain,
            'relative_risk_reduction': rrr,
            'statistically_significant': significant,
            'clinical_significance': clinical_significance
        }

    def calculate_response_rate(self, n_responders: int, n_total: int) -> Dict:
        """
        计算客观缓解率(ORR)

        参数:
            n_responders: 缓解患者数(CR + PR)
            n_total: 总患者数

        返回:
            ORR及95% CI
        """
        orr = n_responders / n_total if n_total > 0 else 0

        # Wilson score interval
        ci_lower, ci_upper = self._wilson_ci(n_responders, n_total)

        return {
            'orr': orr,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'n_responders': n_responders,
            'n_total': n_total
        }

    def calculate_qaly(self, utility_values: List[float], time_periods: List[float],
                       discount_rate: float = 0.03) -> float:
        """
        计算质量调整生命年(QALY)

        参数:
            utility_values: 各时间段的健康效用值(0-1)
            time_periods: 各时间段的持续时间(年)
            discount_rate: 年贴现率(默认3%)

        返回:
            总QALY
        """
        if len(utility_values) != len(time_periods):
            raise ValueError("效用值和时间段数量必须相等")

        total_qaly = 0
        cumulative_time = 0

        for utility, duration in zip(utility_values, time_periods):
            # 贴现因子
            discount_factor = 1 / ((1 + discount_rate) ** cumulative_time)

            # 该时间段的QALY
            qaly_segment = utility * duration * discount_factor

            total_qaly += qaly_segment
            cumulative_time += duration

        return total_qaly

    def calculate_qaly_gain(self, treatment_qaly: float, control_qaly: float) -> Dict:
        """
        计算QALY增量

        返回:
            QALY增量及临床意义
        """
        qaly_gain = treatment_qaly - control_qaly

        # 临床意义判定
        if qaly_gain >= 0.5:
            clinical_significance = '显著'
        elif qaly_gain >= 0.2:
            clinical_significance = '中等'
        elif qaly_gain >= 0.05:
            clinical_significance = '轻微'
        else:
            clinical_significance = '无'

        return {
            'treatment_qaly': treatment_qaly,
            'control_qaly': control_qaly,
            'qaly_gain': qaly_gain,
            'clinical_significance': clinical_significance
        }

    def meta_analysis_fixed_effect(self, effect_sizes: List[float],
                                   variances: List[float]) -> Dict:
        """
        固定效应Meta分析

        参数:
            effect_sizes: 各研究的效应量(如log(HR))
            variances: 各研究的方差

        返回:
            合并效应量及95% CI
        """
        weights = [1/v for v in variances]
        total_weight = sum(weights)

        # 合并效应量
        pooled_effect = sum(e * w for e, w in zip(effect_sizes, weights)) / total_weight

        # 合并方差
        pooled_variance = 1 / total_weight

        # 95% CI
        se = np.sqrt(pooled_variance)
        ci_lower = pooled_effect - 1.96 * se
        ci_upper = pooled_effect + 1.96 * se

        # Z检验
        z_score = pooled_effect / se
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

        return {
            'pooled_effect': pooled_effect,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'p_value': p_value,
            'significant': p_value < 0.05
        }

    def meta_analysis_random_effect(self, effect_sizes: List[float],
                                    variances: List[float]) -> Dict:
        """
        随机效应Meta分析(DerSimonian-Laird方法)

        返回:
            合并效应量及异质性指标
        """
        # 固定效应权重
        weights = [1/v for v in variances]
        total_weight = sum(weights)

        # 固定效应合并
        pooled_fixed = sum(e * w for e, w in zip(effect_sizes, weights)) / total_weight

        # Q统计量
        q_stat = sum(w * (e - pooled_fixed)**2 for e, w in zip(effect_sizes, weights))
        df = len(effect_sizes) - 1
        q_p_value = 1 - stats.chi2.cdf(q_stat, df) if df > 0 else 1

        # I²统计量
        i_squared = max(0, (q_stat - df) / q_stat * 100) if q_stat > 0 else 0

        # τ²(研究间方差)
        c = total_weight - sum(w**2 for w in weights) / total_weight
        tau_squared = max(0, (q_stat - df) / c) if c > 0 and df > 0 else 0

        # 随机效应权重
        random_weights = [1/(v + tau_squared) for v in variances]
        total_random_weight = sum(random_weights)

        # 随机效应合并
        pooled_random = sum(e * w for e, w in zip(effect_sizes, random_weights)) / total_random_weight

        # 95% CI
        pooled_variance = 1 / total_random_weight
        se = np.sqrt(pooled_variance)
        ci_lower = pooled_random - 1.96 * se
        ci_upper = pooled_random + 1.96 * se

        return {
            'pooled_effect': pooled_random,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'q_statistic': q_stat,
            'q_p_value': q_p_value,
            'i_squared': i_squared,
            'tau_squared': tau_squared,
            'heterogeneity': 'high' if i_squared > 75 else 'moderate' if i_squared > 50 else 'low'
        }

    def calculate_efficacy_score(self, survival_benefit: Dict, qaly_gain: float,
                                 response_rate: float, evidence_quality: str) -> int:
        """
        计算综合有效性评分(0-100分)

        参数:
            survival_benefit: 生存获益分析结果
            qaly_gain: QALY增量
            response_rate: 客观缓解率
            evidence_quality: 证据质量(高/中/低)

        返回:
            综合有效性评分
        """
        # 生存获益评分 (40分)
        os_gain = survival_benefit.get('os_gain_months', 0)
        if os_gain >= 6:
            survival_score = 40
        elif os_gain >= 3:
            survival_score = 30
        elif os_gain >= 1:
            survival_score = 20
        else:
            survival_score = 10

        # QALY增量评分 (30分)
        if qaly_gain >= 0.5:
            qaly_score = 30
        elif qaly_gain >= 0.2:
            qaly_score = 20
        elif qaly_gain >= 0.05:
            qaly_score = 10
        else:
            qaly_score = 0

        # 缓解率评分 (20分)
        if response_rate >= 0.5:
            response_score = 20
        elif response_rate >= 0.3:
            response_score = 15
        elif response_rate >= 0.1:
            response_score = 10
        else:
            response_score = 5

        # 证据质量评分 (10分)
        evidence_scores = {'高': 10, '中': 6, '低': 2}
        evidence_score = evidence_scores.get(evidence_quality, 6)

        # 总分
        total_score = survival_score + qaly_score + response_score + evidence_score

        return int(total_score)

    def _wilson_ci(self, x: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
        """Wilson score interval"""
        if n == 0:
            return 0, 0

        p = x / n
        z = stats.norm.ppf(1 - alpha/2)

        denominator = 1 + z**2 / n
        centre = (p + z**2 / (2*n)) / denominator
        adjustment = z * np.sqrt((p*(1-p) + z**2/(4*n)) / n) / denominator

        ci_lower = max(0, centre - adjustment)
        ci_upper = min(1, centre + adjustment)

        return ci_lower, ci_upper

    def generate_report(self) -> str:
        """生成有效性评价报告"""
        report = "=" * 60 + "\n"
        report += "药品有效性综合评价报告\n"
        report += "=" * 60 + "\n\n"

        report += f"综合有效性评分: {self.efficacy_score}/100\n\n"

        if self.efficacy_score >= 85:
            report += "评价等级: 优 - 疗效显著\n"
        elif self.efficacy_score >= 70:
            report += "评价等级: 良 - 疗效良好\n"
        elif self.efficacy_score >= 60:
            report += "评价等级: 中 - 疗效一般\n"
        else:
            report += "评价等级: 差 - 疗效不足\n"

        return report


if __name__ == "__main__":
    # 示例用法
    evaluator = EfficacyEvaluator()

    # 示例: 生存获益分析
    survival = evaluator.calculate_survival_benefit(
        hr=0.65, ci_lower=0.52, ci_upper=0.81,
        median_os_treatment=18.5, median_os_control=12.3
    )
    print("生存获益分析:")
    print(f"  HR = {survival['hr']:.2f} (95% CI: {survival['ci_lower']:.2f}-{survival['ci_upper']:.2f})")
    print(f"  生存期延长: {survival['os_gain_months']:.1f}个月")
    print(f"  临床意义: {survival['clinical_significance']}\n")

    # 示例: QALY计算
    qaly = evaluator.calculate_qaly(
        utility_values=[0.7, 0.6, 0.5],
        time_periods=[1, 1, 1]
    )
    print(f"总QALY: {qaly:.3f}\n")

    # 示例: 综合评分
    score = evaluator.calculate_efficacy_score(
        survival_benefit=survival,
        qaly_gain=0.35,
        response_rate=0.42,
        evidence_quality='高'
    )
    evaluator.efficacy_score = score
    print(evaluator.generate_report())
