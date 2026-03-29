#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
经济性评价分析器
根据国家药品临床综合评价技术指南 - 经济性维度评价工具
"""

import numpy as np
from typing import Dict, List, Tuple

class EconomicEvaluator:
    """药品经济性综合评价器"""

    def __init__(self, discount_rate: float = 0.03):
        self.discount_rate = discount_rate
        self.economic_score = 0

    def calculate_icer(self, cost_treatment: float, cost_control: float,
                       effect_treatment: float, effect_control: float) -> Dict:
        """
        计算增量成本效果比(ICER)

        参数:
            cost_treatment: 治疗组总成本(元)
            cost_control: 对照组总成本(元)
            effect_treatment: 治疗组效果(如生存年)
            effect_control: 对照组效果

        返回:
            ICER及成本效果象限
        """
        delta_cost = cost_treatment - cost_control
        delta_effect = effect_treatment - effect_control

        if delta_effect == 0:
            icer = float('inf') if delta_cost > 0 else 0
            quadrant = '无效果差异'
        else:
            icer = delta_cost / delta_effect

            # 成本效果象限判定
            if delta_cost < 0 and delta_effect > 0:
                quadrant = '支配策略(既省钱又有效)'
            elif delta_cost > 0 and delta_effect < 0:
                quadrant = '被支配策略(既贵又差)'
            elif delta_cost > 0 and delta_effect > 0:
                quadrant = '需权衡(更贵但更有效)'
            else:
                quadrant = '需权衡(更便宜但效果差)'

        return {
            'icer': icer,
            'delta_cost': delta_cost,
            'delta_effect': delta_effect,
            'quadrant': quadrant
        }

    def calculate_icur(self, cost_treatment: float, cost_control: float,
                       qaly_treatment: float, qaly_control: float) -> Dict:
        """
        计算增量成本效用比(ICUR)

        返回:
            ICUR(元/QALY)及与WTP阈值的比较
        """
        delta_cost = cost_treatment - cost_control
        delta_qaly = qaly_treatment - qaly_control

        if delta_qaly == 0:
            icur = float('inf') if delta_cost > 0 else 0
        else:
            icur = delta_cost / delta_qaly

        # 中国WTP阈值(1-3倍人均GDP)
        wtp_threshold_low = 100000  # 10万元/QALY
        wtp_threshold_high = 300000  # 30万元/QALY

        if icur < 0:
            cost_effectiveness = '支配策略'
        elif icur < wtp_threshold_low:
            cost_effectiveness = '高性价比'
        elif icur < wtp_threshold_high:
            cost_effectiveness = '可接受'
        else:
            cost_effectiveness = '不具成本效果'

        return {
            'icur': icur,
            'delta_cost': delta_cost,
            'delta_qaly': delta_qaly,
            'cost_effectiveness': cost_effectiveness,
            'wtp_threshold_low': wtp_threshold_low,
            'wtp_threshold_high': wtp_threshold_high
        }

    def budget_impact_analysis(self, drug_price: float, annual_dose: float,
                               target_population: int, market_share: float,
                               years: int = 5) -> Dict:
        """
        预算影响分析(BIA)

        参数:
            drug_price: 单位药品价格(元)
            annual_dose: 年用药量(单位数)
            target_population: 目标人群数量
            market_share: 市场份额(0-1)
            years: 分析年限

        返回:
            各年度预算影响
        """
        annual_cost_per_patient = drug_price * annual_dose
        annual_patients = target_population * market_share
        annual_budget = annual_cost_per_patient * annual_patients

        results = {
            'annual_cost_per_patient': annual_cost_per_patient,
            'annual_patients': annual_patients,
            'annual_budget': annual_budget,
            'total_budget_5years': annual_budget * years
        }

        return results

    def sensitivity_analysis_one_way(self, base_icer: float, parameter_name: str,
                                     base_value: float, variation_range: Tuple[float, float]) -> Dict:
        """
        单因素敏感性分析

        参数:
            base_icer: 基础ICER值
            parameter_name: 参数名称
            base_value: 基础参数值
            variation_range: 变化范围(最小值, 最大值)

        返回:
            敏感性分析结果
        """
        min_val, max_val = variation_range

        # 假设ICER与参数成正比(简化模型)
        icer_min = base_icer * (min_val / base_value)
        icer_max = base_icer * (max_val / base_value)

        # 敏感性指标
        sensitivity = abs(icer_max - icer_min) / base_icer * 100

        return {
            'parameter': parameter_name,
            'base_value': base_value,
            'range': variation_range,
            'base_icer': base_icer,
            'icer_range': (icer_min, icer_max),
            'sensitivity_percent': sensitivity,
            'highly_sensitive': sensitivity > 50
        }

    def probabilistic_sensitivity_analysis(self, cost_samples: np.ndarray,
                                          effect_samples: np.ndarray,
                                          wtp_threshold: float) -> Dict:
        """
        概率敏感性分析(PSA)

        参数:
            cost_samples: 成本的蒙特卡洛样本(N个)
            effect_samples: 效果的蒙特卡洛样本(N个)
            wtp_threshold: 支付意愿阈值

        返回:
            PSA结果及成本效果可接受曲线(CEAC)
        """
        n_samples = len(cost_samples)

        # 计算每个样本的ICER
        icers = cost_samples / effect_samples

        # 成本效果可接受概率
        acceptable = np.sum(icers < wtp_threshold) / n_samples

        # ICER的分布统计
        icer_mean = np.mean(icers)
        icer_median = np.median(icers)
        icer_95ci = np.percentile(icers, [2.5, 97.5])

        return {
            'n_simulations': n_samples,
            'icer_mean': icer_mean,
            'icer_median': icer_median,
            'icer_95ci': icer_95ci,
            'probability_cost_effective': acceptable,
            'wtp_threshold': wtp_threshold
        }

    def calculate_economic_score(self, icur: float, budget_impact: float,
                                 affordability: str, study_quality: str) -> int:
        """
        计算综合经济性评分(0-100分)

        参数:
            icur: 增量成本效用比(元/QALY)
            budget_impact: 年度预算影响(亿元)
            affordability: 可负担性(高/中/低)
            study_quality: 经济学研究质量(高/中/低)

        返回:
            综合经济性评分
        """
        # ICUR评分 (50分)
        if icur < 0:
            icur_score = 50
        elif icur < 100000:
            icur_score = 45
        elif icur < 200000:
            icur_score = 35
        elif icur < 300000:
            icur_score = 25
        else:
            icur_score = 10

        # 预算影响评分 (30分)
        if budget_impact < 1:
            budget_score = 30
        elif budget_impact < 5:
            budget_score = 20
        elif budget_impact < 10:
            budget_score = 10
        else:
            budget_score = 0

        # 可负担性评分 (已在可及性维度评价)
        # 这里不重复计分

        # 研究质量评分 (20分)
        quality_scores = {'高': 20, '中': 12, '低': 5}
        quality_score = quality_scores.get(study_quality, 12)

        # 总分
        total_score = icur_score + budget_score + quality_score

        return int(total_score)

    def generate_report(self) -> str:
        """生成经济性评价报告"""
        report = "=" * 60 + "\n"
        report += "药品经济性综合评价报告\n"
        report += "=" * 60 + "\n\n"

        report += f"综合经济性评分: {self.economic_score}/100\n\n"

        if self.economic_score >= 80:
            report += "评价等级: 优 - 经济性优秀\n"
        elif self.economic_score >= 60:
            report += "评价等级: 良 - 经济性良好\n"
        elif self.economic_score >= 40:
            report += "评价等级: 中 - 经济性一般\n"
        else:
            report += "评价等级: 差 - 经济性较差\n"

        return report


if __name__ == "__main__":
    # 示例用法
    evaluator = EconomicEvaluator()

    # 示例: ICUR计算
    icur_result = evaluator.calculate_icur(
        cost_treatment=150000, cost_control=80000,
        qaly_treatment=3.5, qaly_control=2.8
    )
    print("ICUR分析结果:")
    print(f"  ICUR = {icur_result['icur']:,.0f} 元/QALY")
    print(f"  成本效果评价: {icur_result['cost_effectiveness']}\n")

    # 示例: 预算影响分析
    bia = evaluator.budget_impact_analysis(
        drug_price=500, annual_dose=365,
        target_population=1000000, market_share=0.2
    )
    print("预算影响分析:")
    print(f"  年度人均费用: {bia['annual_cost_per_patient']:,.0f} 元")
    print(f"  年度总预算: {bia['annual_budget']/100000000:.2f} 亿元\n")

    # 示例: 综合评分
    score = evaluator.calculate_economic_score(
        icur=icur_result['icur'],
        budget_impact=bia['annual_budget']/100000000,
        affordability='中',
        study_quality='高'
    )
    evaluator.economic_score = score
    print(evaluator.generate_report())
