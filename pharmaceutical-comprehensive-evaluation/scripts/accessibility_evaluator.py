#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
可及性评价分析器
根据国家药品临床综合评价技术指南 - 可及性维度评价工具
"""

import numpy as np
from typing import Dict, List

class AccessibilityEvaluator:
    """药品可及性综合评价器"""

    def __init__(self):
        self.accessibility_score = 0

    def price_analysis(self, china_price: float, reference_prices: Dict[str, float]) -> Dict:
        """
        价格分析与国际比较

        参数:
            china_price: 中国价格(元)
            reference_prices: 参比国价格字典 {'国家': 价格}

        返回:
            价格分析结果
        """
        if not reference_prices:
            return {'price_ratio': 1.0, 'price_level': '无参比数据'}

        # 计算平均参比价格
        avg_reference_price = np.mean(list(reference_prices.values()))

        # 价格比率
        price_ratio = china_price / avg_reference_price if avg_reference_price > 0 else 0

        # 价格水平判定
        if price_ratio < 0.5:
            price_level = '显著低于国际水平'
        elif price_ratio < 0.8:
            price_level = '低于国际水平'
        elif price_ratio < 1.2:
            price_level = '接近国际水平'
        elif price_ratio < 1.5:
            price_level = '高于国际水平'
        else:
            price_level = '显著高于国际水平'

        return {
            'china_price': china_price,
            'avg_reference_price': avg_reference_price,
            'price_ratio': price_ratio,
            'price_level': price_level,
            'reference_countries': list(reference_prices.keys())
        }

    def affordability_analysis(self, annual_treatment_cost: float,
                               per_capita_income: float,
                               reimbursement_rate: float) -> Dict:
        """
        可负担性分析

        参数:
            annual_treatment_cost: 年度治疗费用(元)
            per_capita_income: 人均可支配收入(元)
            reimbursement_rate: 医保报销比例(0-1)

        返回:
            可负担性分析结果
        """
        # 患者自付费用
        out_of_pocket = annual_treatment_cost * (1 - reimbursement_rate)

        # 可负担性指数(自付费用占收入比例)
        affordability_index = out_of_pocket / per_capita_income if per_capita_income > 0 else 0

        # 灾难性卫生支出判定(>40%家庭收入)
        catastrophic = affordability_index > 0.4

        # 可负担性等级
        if affordability_index < 0.1:
            affordability_level = '高度可负担'
        elif affordability_index < 0.2:
            affordability_level = '可负担'
        elif affordability_index < 0.4:
            affordability_level = '负担较重'
        else:
            affordability_level = '难以负担'

        return {
            'annual_treatment_cost': annual_treatment_cost,
            'out_of_pocket': out_of_pocket,
            'per_capita_income': per_capita_income,
            'affordability_index': affordability_index,
            'catastrophic_expenditure': catastrophic,
            'affordability_level': affordability_level
        }

    def availability_analysis(self, supply_data: Dict) -> Dict:
        """
        可获得性分析

        参数:
            supply_data: 供应数据字典
                {
                    'shortage_days': 缺货天数,
                    'total_days': 总天数,
                    'tertiary_coverage': 三级医院配备率,
                    'secondary_coverage': 二级医院配备率,
                    'primary_coverage': 基层医疗机构配备率,
                    'urban_coverage': 城市覆盖率,
                    'rural_coverage': 农村覆盖率
                }

        返回:
            可获得性分析结果
        """
        # 供应保障率
        shortage_days = supply_data.get('shortage_days', 0)
        total_days = supply_data.get('total_days', 365)
        supply_rate = (1 - shortage_days / total_days) * 100 if total_days > 0 else 0

        # 医疗机构配备率加权平均
        tertiary = supply_data.get('tertiary_coverage', 0)
        secondary = supply_data.get('secondary_coverage', 0)
        primary = supply_data.get('primary_coverage', 0)
        avg_facility_coverage = (tertiary * 0.5 + secondary * 0.3 + primary * 0.2)

        # 地域覆盖率
        urban = supply_data.get('urban_coverage', 0)
        rural = supply_data.get('rural_coverage', 0)
        avg_geographic_coverage = (urban * 0.6 + rural * 0.4)

        # 综合可获得性评分
        availability_score = (supply_rate * 0.4 + avg_facility_coverage * 0.35 +
                             avg_geographic_coverage * 0.25)

        # 可获得性等级
        if availability_score >= 90:
            availability_level = '高度可获得'
        elif availability_score >= 70:
            availability_level = '可获得'
        elif availability_score >= 50:
            availability_level = '部分可获得'
        else:
            availability_level = '难以获得'

        return {
            'supply_rate': supply_rate,
            'avg_facility_coverage': avg_facility_coverage,
            'avg_geographic_coverage': avg_geographic_coverage,
            'availability_score': availability_score,
            'availability_level': availability_level
        }

    def equity_analysis(self, income_groups: Dict[str, float]) -> Dict:
        """
        公平性分析(不同收入人群负担能力差异)

        参数:
            income_groups: 不同收入组的可负担性指数
                {'低收入': 0.5, '中等收入': 0.25, '高收入': 0.1}

        返回:
            公平性分析结果
        """
        if not income_groups:
            return {'equity_index': 0, 'equity_level': '无数据'}

        # 计算变异系数(CV)作为不公平性指标
        values = list(income_groups.values())
        mean_val = np.mean(values)
        std_val = np.std(values)
        cv = std_val / mean_val if mean_val > 0 else 0

        # 公平性指数(1 - CV)
        equity_index = max(0, 1 - cv)

        # 公平性等级
        if equity_index >= 0.8:
            equity_level = '高度公平'
        elif equity_index >= 0.6:
            equity_level = '较公平'
        elif equity_index >= 0.4:
            equity_level = '不够公平'
        else:
            equity_level = '严重不公平'

        return {
            'income_groups': income_groups,
            'coefficient_of_variation': cv,
            'equity_index': equity_index,
            'equity_level': equity_level
        }

    def calculate_accessibility_score(self, price_ratio: float,
                                     affordability_index: float,
                                     availability_score: float) -> int:
        """
        计算综合可及性评分(0-100分)

        参数:
            price_ratio: 价格比率(中国价格/国际平均价格)
            affordability_index: 可负担性指数(自付费用/收入)
            availability_score: 可获得性评分(0-100)

        返回:
            综合可及性评分
        """
        # 价格合理性评分 (40分)
        if price_ratio < 0.5:
            price_score = 40
        elif price_ratio < 0.8:
            price_score = 35
        elif price_ratio < 1.0:
            price_score = 30
        elif price_ratio < 1.2:
            price_score = 20
        else:
            price_score = 10

        # 可负担性评分 (35分)
        if affordability_index < 0.1:
            afford_score = 35
        elif affordability_index < 0.2:
            afford_score = 28
        elif affordability_index < 0.3:
            afford_score = 20
        elif affordability_index < 0.4:
            afford_score = 10
        else:
            afford_score = 0

        # 可获得性评分 (25分)
        avail_score = availability_score * 0.25

        # 总分
        total_score = price_score + afford_score + avail_score

        return int(total_score)

    def generate_report(self) -> str:
        """生成可及性评价报告"""
        report = "=" * 60 + "\n"
        report += "药品可及性综合评价报告\n"
        report += "=" * 60 + "\n\n"

        report += f"综合可及性评分: {self.accessibility_score}/100\n\n"

        if self.accessibility_score >= 80:
            report += "评价等级: 优 - 可及性良好\n"
        elif self.accessibility_score >= 60:
            report += "评价等级: 良 - 可及性可接受\n"
        elif self.accessibility_score >= 40:
            report += "评价等级: 中 - 可及性一般\n"
        else:
            report += "评价等级: 差 - 可及性不足\n"

        return report


if __name__ == "__main__":
    # 示例用法
    evaluator = AccessibilityEvaluator()

    # 示例: 价格分析
    price_result = evaluator.price_analysis(
        china_price=5000,
        reference_prices={'美国': 8000, '日本': 6500, '德国': 7000}
    )
    print("价格分析结果:")
    print(f"  中国价格: {price_result['china_price']:,.0f} 元")
    print(f"  国际平均价格: {price_result['avg_reference_price']:,.0f} 元")
    print(f"  价格比率: {price_result['price_ratio']:.2f}")
    print(f"  价格水平: {price_result['price_level']}\n")

    # 示例: 可负担性分析
    afford_result = evaluator.affordability_analysis(
        annual_treatment_cost=50000,
        per_capita_income=35000,
        reimbursement_rate=0.7
    )
    print("可负担性分析结果:")
    print(f"  年度治疗费用: {afford_result['annual_treatment_cost']:,.0f} 元")
    print(f"  患者自付: {afford_result['out_of_pocket']:,.0f} 元")
    print(f"  可负担性指数: {afford_result['affordability_index']:.2%}")
    print(f"  可负担性等级: {afford_result['affordability_level']}\n")

    # 示例: 可获得性分析
    avail_result = evaluator.availability_analysis({
        'shortage_days': 10,
        'total_days': 365,
        'tertiary_coverage': 0.95,
        'secondary_coverage': 0.80,
        'primary_coverage': 0.50,
        'urban_coverage': 0.90,
        'rural_coverage': 0.60
    })
    print("可获得性分析结果:")
    print(f"  供应保障率: {avail_result['supply_rate']:.1f}%")
    print(f"  综合可获得性评分: {avail_result['availability_score']:.1f}")
    print(f"  可获得性等级: {avail_result['availability_level']}\n")

    # 示例: 综合评分
    score = evaluator.calculate_accessibility_score(
        price_ratio=price_result['price_ratio'],
        affordability_index=afford_result['affordability_index'],
        availability_score=avail_result['availability_score']
    )
    evaluator.accessibility_score = score
    print(evaluator.generate_report())
