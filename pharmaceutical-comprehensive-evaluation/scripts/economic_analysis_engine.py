#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
经济学分析引擎 (Economic Analysis Engine)

功能:
- ICER (增量成本效果比) 计算
- 敏感性分析
- 成本-有效性平面
- 成本-效用分析 (QALY)
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings

warnings.filterwarnings('ignore')


class EconomicAnalysisEngine:
    """药物经济学分析引擎"""

    def __init__(self, wtp_threshold: float = 150000):
        """
        初始化

        Args:
            wtp_threshold: 支付意愿阈值 (元/QALY), 默认150000 (中国标准)
        """
        self.wtp_threshold = wtp_threshold  # 每个QALY的愿支付
        self.base_case = {}
        self.sensitivity_results = {}

    def setup_base_case(self, drug_cost: float, control_cost: float,
                        drug_efficacy: float, control_efficacy: float,
                        drug_utility: float = None, control_utility: float = None):
        """
        设置基础案例参数

        Args:
            drug_cost: 药物年度治疗费用 (元)
            control_cost: 对照药年度治疗费用 (元)
            drug_efficacy: 药物疗效 (缓解率 0-1)
            control_efficacy: 对照药疗效 (缓解率 0-1)
            drug_utility: 药物健康相关生活质量 (QALY) 可选
            control_utility: 对照药生活质量 (QALY) 可选
        """
        self.base_case = {
            'drug_cost': drug_cost,
            'control_cost': control_cost,
            'drug_efficacy': drug_efficacy,
            'control_efficacy': control_efficacy,
            'drug_utility': drug_utility or drug_efficacy,  # 如未提供, 用疗效代替
            'control_utility': control_utility or control_efficacy
        }

    def calculate_icer(self, drug_cost: float = None, control_cost: float = None,
                       drug_efficacy: float = None, control_efficacy: float = None) -> Dict:
        """
        计算增量成本效果比 (ICER)

        ICER = (Cost_drug - Cost_control) / (Effect_drug - Effect_control)

        Returns:
            包含 ICER、增量成本、增量效果和评价的字典
        """
        if drug_cost is None:
            drug_cost = self.base_case['drug_cost']
        if control_cost is None:
            control_cost = self.base_case['control_cost']
        if drug_efficacy is None:
            drug_efficacy = self.base_case['drug_efficacy']
        if control_efficacy is None:
            control_efficacy = self.base_case['control_efficacy']

        # 增量成本 (Δ成本)
        delta_cost = drug_cost - control_cost

        # 增量效果 (Δ效果)
        delta_efficacy = drug_efficacy - control_efficacy

        # 计算 ICER
        if abs(delta_efficacy) < 1e-6:  # 避免除以零
            icer = np.inf if delta_cost > 0 else -np.inf
        else:
            icer = delta_cost / delta_efficacy

        # 判断成本-有效性象限
        if delta_cost < 0 and delta_efficacy > 0:
            quadrant = '主导象限'  # 成本更低, 效果更好
            dominance = 'Dominant'
        elif delta_cost > 0 and delta_efficacy > 0:
            quadrant = '东北象限'  # 成本更高, 效果更好
            dominance = 'Regular ICER'
        elif delta_cost < 0 and delta_efficacy < 0:
            quadrant = '西南象限'  # 成本更低, 效果更差
            dominance = 'Dominated'
        elif delta_cost > 0 and delta_efficacy < 0:
            quadrant = '支配象限'  # 成本更高, 效果更差
            dominance = 'Dominated'
        else:
            quadrant = '中心'
            dominance = 'Neutral'

        # 与WTP阈值比较
        if dominance == 'Dominant':
            cost_effective = '是 (支配)'
        elif dominance == 'Dominated':
            cost_effective = '否 (被支配)'
        elif icer <= self.wtp_threshold:
            cost_effective = '是'
        else:
            cost_effective = '否'

        return {
            'icer': icer,
            'delta_cost': delta_cost,
            'delta_efficacy': delta_efficacy,
            'quadrant': quadrant,
            'cost_effective': cost_effective,
            'vs_wtp_threshold': f"ICER={icer:.0f} 元, WTP={self.wtp_threshold} 元"
        }

    def calculate_icer_qaly(self, drug_cost: float = None, control_cost: float = None,
                            drug_utility: float = None, control_utility: float = None) -> Dict:
        """
        计算成本-效用分析 (以QALY为单位)

        ICER = (成本差) / (QALY差)
        """
        if drug_cost is None:
            drug_cost = self.base_case['drug_cost']
        if control_cost is None:
            control_cost = self.base_case['control_cost']
        if drug_utility is None:
            drug_utility = self.base_case['drug_utility']
        if control_utility is None:
            control_utility = self.base_case['control_utility']

        delta_cost = drug_cost - control_cost
        delta_qaly = drug_utility - control_utility

        if abs(delta_qaly) < 1e-6:
            icer_per_qaly = np.inf if delta_cost > 0 else -np.inf
        else:
            icer_per_qaly = delta_cost / delta_qaly

        # 中国卫生经济学指南: 60000-150000 元/QALY 被认为是成本-有效的
        if icer_per_qaly <= 60000:
            acceptability = '高度推荐'
        elif icer_per_qaly <= self.wtp_threshold:
            acceptability = '推荐'
        elif icer_per_qaly <= 300000:  # 上限
            acceptability = '有条件推荐'
        else:
            acceptability = '不推荐'

        return {
            'icer_per_qaly': icer_per_qaly,
            'delta_cost': delta_cost,
            'delta_qaly': delta_qaly,
            'acceptability': acceptability,
            'guideline_reference': '中国卫生经济学评价指南'
        }

    def sensitivity_analysis(self, parameters: Dict, ranges: Dict) -> pd.DataFrame:
        """
        单向敏感性分析 (One-way Sensitivity Analysis)

        Args:
            parameters: 基础参数字典
            ranges: 参数范围 {param_name: (低, 高, step)}

        Returns:
            敏感性分析结果表
        """
        results = []

        for param_name, (low, high, step) in ranges.items():
            param_values = np.arange(low, high + step, step)

            for value in param_values:
                # 复制参数
                test_params = parameters.copy()
                test_params[param_name] = value

                # 计算该参数值下的 ICER
                icer_result = self.calculate_icer(
                    drug_cost=test_params.get('drug_cost', self.base_case['drug_cost']),
                    control_cost=test_params.get('control_cost', self.base_case['control_cost']),
                    drug_efficacy=test_params.get('drug_efficacy', self.base_case['drug_efficacy']),
                    control_efficacy=test_params.get('control_efficacy', self.base_case['control_efficacy'])
                )

                results.append({
                    'parameter': param_name,
                    'value': value,
                    'icer': icer_result['icer'],
                    'cost_effective': icer_result['cost_effective']
                })

        return pd.DataFrame(results)

    def tornado_analysis(self, base_params: Dict, variations: Dict) -> pd.DataFrame:
        """
        龙卷风图分析 (Tornado Diagram)

        计算每个参数在给定范围内变化时对ICER的影响

        Args:
            base_params: 基础参数
            variations: {参数名: [低值, 高值]}

        Returns:
            按影响范围排序的参数表
        """
        tornado_data = []

        for param_name, (low_val, high_val) in variations.items():
            # 低值情景
            low_params = base_params.copy()
            low_params[param_name] = low_val
            icer_low = self.calculate_icer(
                drug_cost=low_params.get('drug_cost'),
                control_cost=low_params.get('control_cost'),
                drug_efficacy=low_params.get('drug_efficacy'),
                control_efficacy=low_params.get('control_efficacy')
            )['icer']

            # 高值情景
            high_params = base_params.copy()
            high_params[param_name] = high_val
            icer_high = self.calculate_icer(
                drug_cost=high_params.get('drug_cost'),
                control_cost=high_params.get('control_cost'),
                drug_efficacy=high_params.get('drug_efficacy'),
                control_efficacy=high_params.get('control_efficacy')
            )['icer']

            # 影响范围
            impact_range = abs(icer_high - icer_low)

            tornado_data.append({
                'parameter': param_name,
                'icer_low': min(icer_low, icer_high),
                'icer_high': max(icer_low, icer_high),
                'impact_range': impact_range,
                'low_value': low_val,
                'high_value': high_val
            })

        # 按影响范围排序
        tornado_df = pd.DataFrame(tornado_data)
        tornado_df = tornado_df.sort_values('impact_range', ascending=False)

        self.sensitivity_results = tornado_df
        return tornado_df

    def budget_impact_analysis(self, annual_new_patients: int,
                               switch_rate: float = 0.7) -> Dict:
        """
        预算影响分析 (Budget Impact Analysis)

        计算新药纳入医保系统后3年的总体经济负担

        Args:
            annual_new_patients: 每年新增患者数
            switch_rate: 从旧药切换到新药的比例 (0-1)
        """
        drug_cost = self.base_case['drug_cost']
        control_cost = self.base_case['control_cost']

        years = 3
        results = {
            'year_1': {},
            'year_2': {},
            'year_3': {}
        }

        for year in range(1, years + 1):
            current_patients = annual_new_patients * year
            switched_patients = int(current_patients * switch_rate)
            retained_control = current_patients - switched_patients

            year_key = f'year_{year}'

            results[year_key] = {
                'total_patients': current_patients,
                'drug_users': switched_patients,
                'control_users': retained_control,
                'drug_cost_total': switched_patients * drug_cost,
                'control_cost_total': retained_control * control_cost,
                'incremental_cost': switched_patients * drug_cost + retained_control * control_cost -
                                   current_patients * control_cost
            }

        # 3年总成本
        total_incremental = sum(results[f'year_{i}']['incremental_cost'] for i in range(1, years + 1))

        results['summary'] = {
            'total_3year_incremental_cost': total_incremental,
            'average_annual_incremental_cost': total_incremental / years,
            'budget_impact_percentage': (total_incremental / (annual_new_patients * years * control_cost)) * 100
        }

        return results

    def generate_report(self, output_file: str = 'economic_analysis_report.json'):
        """生成经济学分析报告"""
        icer = self.calculate_icer()
        icer_qaly = self.calculate_icer_qaly()

        report = {
            'summary': {
                'wtp_threshold': self.wtp_threshold,
                'icer': round(icer['icer'], 2),
                'icer_per_qaly': round(icer_qaly['icer_per_qaly'], 2),
                'cost_effective': icer['cost_effective'],
                'acceptability': icer_qaly['acceptability']
            },
            'base_case_parameters': self.base_case,
            'icer_results': icer,
            'icer_qaly_results': icer_qaly,
            'sensitivity_analysis': self.sensitivity_results.to_dict('records')
                                   if not self.sensitivity_results.empty else [],
            'quadrant_explanation': {
                '主导象限': '新药成本更低，效果更好，明确优于对照药',
                '东北象限': '新药成本更高，但效果更好，需评估成本-效果比',
                '支配象限': '新药成本更高，效果更差，不建议使用',
                '西南象限': '新药成本更低，但效果更差，需谨慎考虑'
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report


if __name__ == '__main__':
    # 示例: 新降压药 vs 标准降压药
    engine = EconomicAnalysisEngine(wtp_threshold=150000)

    # 设置基础参数
    engine.setup_base_case(
        drug_cost=3600,       # 新药年成本 (元)
        control_cost=1200,    # 标准药年成本 (元)
        drug_efficacy=0.75,   # 新药缓解率
        control_efficacy=0.60,  # 标准药缓解率
        drug_utility=0.85,    # 新药QALY
        control_utility=0.70  # 标准药QALY
    )

    print("=== ICER 计算 ===")
    icer = engine.calculate_icer()
    print(f"ICER: {icer['icer']:.0f} 元")
    print(f"成本-有效: {icer['cost_effective']}")

    print("\n=== 成本-效用分析 (QALY) ===")
    icer_qaly = engine.calculate_icer_qaly()
    print(f"ICER per QALY: {icer_qaly['icer_per_qaly']:.0f} 元/QALY")
    print(f"接受性: {icer_qaly['acceptability']}")

    print("\n=== 龙卷风分析 ===")
    tornado = engine.tornado_analysis(
        engine.base_case,
        {
            'drug_cost': (2800, 4400),
            'drug_efficacy': (0.65, 0.85),
            'control_efficacy': (0.50, 0.70)
        }
    )
    print(tornado)

    print("\n=== 预算影响分析 ===")
    budget = engine.budget_impact_analysis(annual_new_patients=100000, switch_rate=0.7)
    print(f"3年增量成本: {budget['summary']['total_3year_incremental_cost']:,.0f} 元")

    print("\n=== 生成报告 ===")
    report = engine.generate_report('example_economic_report.json')
    print("报告已保存")

