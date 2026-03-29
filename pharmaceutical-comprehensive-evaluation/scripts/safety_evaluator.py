#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安全性评价分析器
根据国家药品临床综合评价技术指南 - 安全性维度评价工具
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple

class SafetyEvaluator:
    """药品安全性综合评价器"""

    def __init__(self):
        self.safety_score = 0
        self.results = {}

    def calculate_adverse_event_rate(self, ae_data: pd.DataFrame) -> Dict:
        """
        计算不良反应发生率

        参数:
            ae_data: DataFrame包含列['study_id', 'drug', 'ae_type', 'n_ae', 'n_total']

        返回:
            不良反应发生率分析结果
        """
        results = {}

        # 按不良反应类型分组
        for ae_type in ae_data['ae_type'].unique():
            subset = ae_data[ae_data['ae_type'] == ae_type]

            # 计算总发生率
            total_ae = subset['n_ae'].sum()
            total_patients = subset['n_total'].sum()
            rate = total_ae / total_patients if total_patients > 0 else 0

            # 95% CI (Wilson score interval)
            ci_lower, ci_upper = self._wilson_ci(total_ae, total_patients)

            results[ae_type] = {
                'rate': rate,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'n_events': total_ae,
                'n_patients': total_patients
            }

        return results

    def calculate_ror(self, drug_ae: int, drug_no_ae: int,
                      other_ae: int, other_no_ae: int) -> Dict:
        """
        计算相对报告比(ROR)用于信号检测

        参数:
            drug_ae: 目标药物-目标不良反应数
            drug_no_ae: 目标药物-其他不良反应数
            other_ae: 其他药物-目标不良反应数
            other_no_ae: 其他药物-其他不良反应数

        返回:
            ROR及95% CI
        """
        # 构建2x2表
        a, b, c, d = drug_ae, drug_no_ae, other_ae, other_no_ae

        # ROR = (a/b) / (c/d)
        ror = (a * d) / (b * c) if b > 0 and c > 0 else 0

        # 95% CI
        if a > 0 and b > 0 and c > 0 and d > 0:
            log_ror = np.log(ror)
            se_log_ror = np.sqrt(1/a + 1/b + 1/c + 1/d)
            ci_lower = np.exp(log_ror - 1.96 * se_log_ror)
            ci_upper = np.exp(log_ror + 1.96 * se_log_ror)
        else:
            ci_lower, ci_upper = 0, 0

        # 信号判定: ROR ≥ 2.0 且 CI下限 > 1
        signal = ror >= 2.0 and ci_lower > 1.0

        return {
            'ror': ror,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'signal_detected': signal
        }

    def calculate_prr(self, drug_ae: int, drug_no_ae: int,
                      other_ae: int, other_no_ae: int) -> Dict:
        """
        计算比例报告比(PRR)

        返回:
            PRR及统计检验结果
        """
        a, b, c, d = drug_ae, drug_no_ae, other_ae, other_no_ae

        # PRR = [a/(a+b)] / [c/(c+d)]
        p1 = a / (a + b) if (a + b) > 0 else 0
        p2 = c / (c + d) if (c + d) > 0 else 0
        prr = p1 / p2 if p2 > 0 else 0

        # 卡方检验
        contingency_table = np.array([[a, b], [c, d]])
        chi2, p_value = stats.chi2_contingency(contingency_table)[:2]

        # 信号判定: PRR ≥ 2 且 χ² ≥ 4 且 a ≥ 3
        signal = prr >= 2.0 and chi2 >= 4.0 and a >= 3

        return {
            'prr': prr,
            'chi2': chi2,
            'p_value': p_value,
            'signal_detected': signal
        }

    def assess_drug_interactions(self, interactions: List[Dict]) -> Dict:
        """
        评估药物相互作用风险

        参数:
            interactions: 列表，每项包含{'drug_pair': str, 'mechanism': str,
                         'severity': str, 'clinical_evidence': str}

        返回:
            相互作用风险评估结果
        """
        severity_scores = {'严重': 3, '中度': 2, '轻度': 1}

        total_score = 0
        high_risk_count = 0

        for interaction in interactions:
            severity = interaction.get('severity', '轻度')
            score = severity_scores.get(severity, 1)
            total_score += score

            if severity == '严重':
                high_risk_count += 1

        # 风险分级
        if high_risk_count >= 3 or total_score >= 10:
            risk_level = '高风险'
        elif high_risk_count >= 1 or total_score >= 5:
            risk_level = '中风险'
        else:
            risk_level = '低风险'

        return {
            'total_interactions': len(interactions),
            'high_risk_count': high_risk_count,
            'total_risk_score': total_score,
            'risk_level': risk_level
        }

    def evaluate_special_populations(self, special_pop_data: Dict) -> Dict:
        """
        评估特殊人群安全性

        参数:
            special_pop_data: 字典，键为人群类型，值为安全性数据

        返回:
            特殊人群安全性评分
        """
        populations = ['老年', '儿童', '孕妇', '肝功能不全', '肾功能不全']

        results = {}
        total_score = 0

        for pop in populations:
            if pop in special_pop_data:
                data = special_pop_data[pop]
                # 评分标准: 有充分数据20分，有限数据10分，无数据0分
                if data.get('data_quality') == '充分':
                    score = 20
                elif data.get('data_quality') == '有限':
                    score = 10
                else:
                    score = 0

                results[pop] = {
                    'score': score,
                    'data_quality': data.get('data_quality', '无'),
                    'safety_concern': data.get('safety_concern', '未知')
                }
                total_score += score

        # 满分100分
        final_score = total_score / len(populations)

        return {
            'population_results': results,
            'total_score': final_score
        }

    def calculate_safety_score(self, ae_rate: float, sae_rate: float,
                               discontinuation_rate: float,
                               interaction_risk: str,
                               special_pop_score: float) -> int:
        """
        计算综合安全性评分(0-100分)

        参数:
            ae_rate: 总不良反应发生率
            sae_rate: 严重不良反应发生率
            discontinuation_rate: 因不良反应停药率
            interaction_risk: 药物相互作用风险等级
            special_pop_score: 特殊人群安全性评分

        返回:
            综合安全性评分
        """
        # 不良反应发生率评分 (30分)
        if ae_rate < 0.1:
            ae_score = 30
        elif ae_rate < 0.3:
            ae_score = 20
        elif ae_rate < 0.5:
            ae_score = 10
        else:
            ae_score = 0

        # 严重不良反应评分 (25分)
        if sae_rate < 0.01:
            sae_score = 25
        elif sae_rate < 0.05:
            sae_score = 15
        elif sae_rate < 0.1:
            sae_score = 5
        else:
            sae_score = 0

        # 停药率评分 (15分)
        if discontinuation_rate < 0.05:
            disc_score = 15
        elif discontinuation_rate < 0.1:
            disc_score = 10
        elif discontinuation_rate < 0.2:
            disc_score = 5
        else:
            disc_score = 0

        # 药物相互作用评分 (20分)
        interaction_scores = {'低风险': 20, '中风险': 10, '高风险': 0}
        interaction_score = interaction_scores.get(interaction_risk, 10)

        # 特殊人群评分 (10分)
        special_score = special_pop_score * 0.1

        # 总分
        total_score = ae_score + sae_score + disc_score + interaction_score + special_score

        return int(total_score)

    def _wilson_ci(self, x: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
        """Wilson score interval for binomial proportion"""
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
        """生成安全性评价报告"""
        report = "=" * 60 + "\n"
        report += "药品安全性综合评价报告\n"
        report += "=" * 60 + "\n\n"

        report += f"综合安全性评分: {self.safety_score}/100\n\n"

        if self.safety_score >= 80:
            report += "评价等级: 优 - 安全性良好\n"
        elif self.safety_score >= 60:
            report += "评价等级: 良 - 安全性可接受\n"
        elif self.safety_score >= 40:
            report += "评价等级: 中 - 安全性一般，需加强监测\n"
        else:
            report += "评价等级: 差 - 安全性存在重大隐患\n"

        return report


if __name__ == "__main__":
    # 示例用法
    evaluator = SafetyEvaluator()

    # 示例: ROR计算
    ror_result = evaluator.calculate_ror(
        drug_ae=50, drug_no_ae=950,
        other_ae=100, other_no_ae=9900
    )
    print("ROR分析结果:")
    print(f"  ROR = {ror_result['ror']:.2f}")
    print(f"  95% CI = [{ror_result['ci_lower']:.2f}, {ror_result['ci_upper']:.2f}]")
    print(f"  信号检测: {'阳性' if ror_result['signal_detected'] else '阴性'}\n")

    # 示例: 综合评分
    score = evaluator.calculate_safety_score(
        ae_rate=0.25,
        sae_rate=0.03,
        discontinuation_rate=0.08,
        interaction_risk='中风险',
        special_pop_score=65
    )
    evaluator.safety_score = score
    print(evaluator.generate_report())
