#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医学文献证据综合器 (Literature Evidence Synthesizer)

功能:
- 文献质量评分 (JADAD, GRADE)
- 发表偏倚评估
- 系统性综述表生成
- 证据级别分类
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
from typing import List, Dict, Tuple

warnings.filterwarnings('ignore')


class LiteratureEvidenceSynthesizer:
    """医学文献证据综合器"""

    def __init__(self):
        self.trials = []
        self.quality_scores = {}

    def load_literature_data(self, file_path: str) -> pd.DataFrame:
        """
        加载文献数据

        期望列:
        - study_id: 研究编号
        - author_year: 作者_年份
        - study_type: RCT / 队列研究 / 病例对照 / 横断面
        - participants_n: 参与人数
        - follow_up_months: 随访时间(月)
        - main_outcome: 主要结局
        - effect_size: 效应量
        - ci_lower, ci_upper: 95% CI
        """
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("仅支持 CSV 或 Excel 格式")

        self.trials = df
        return df

    def calculate_jadad_score(self, randomization: int, blinding: int,
                             withdrawals: int, description_quality: int = 1) -> Dict:
        """
        计算 JADAD 评分 (Jadad Scale, 0-7分)

        评分标准:
        - 随机化: 0分(无) / 1分(提及但不清楚) / 2分(清楚并恰当)
        - 盲法: 0分(无) / 1分(提及但不清楚) / 2分(清楚并恰当)
        - 脱落和弃权: 0分(无) / 1分(提及但不清楚)
        - 描述质量: +1分或-1分
        """
        total_score = randomization + blinding + withdrawals

        if description_quality == 1:
            total_score += 1
        elif description_quality == -1:
            total_score -= 1

        # 质量评级
        if total_score <= 2:
            quality_level = '低质量'
        elif total_score <= 4:
            quality_level = '中等质量'
        else:
            quality_level = '高质量'

        return {
            'jadad_total': total_score,
            'quality_level': quality_level,
            'randomization': randomization,
            'blinding': blinding,
            'withdrawals': withdrawals,
            'interpretation': f"JADAD评分 {total_score}/7 - {quality_level}"
        }

    def grade_evidence_quality(self, study_type: str, rct_count: int = 0,
                              consistency: bool = True,
                              directness: bool = True,
                              precision: bool = True,
                              publication_bias: bool = False) -> Dict:
        """
        GRADE 证据质量分级 (Grading of Recommendations Assessment, Development and Evaluation)

        证据级别:
        - Ia: Meta分析或多个高质量RCT
        - Ib: 单个高质量RCT或多个中等质量RCT
        - IIa: 高质量队列研究或RCT结果不一致
        - IIb: 多个队列研究或大型观察性研究
        - III: 病例对照研究
        - IV: 病例报告或专家意见

        推荐级别:
        - A: 强烈推荐 (Ia/Ib)
        - B: 中等推荐 (IIa/IIb)
        - C: 弱推荐 (III/IV)
        - D: 反对 (缺乏有效证据或潜在伤害)
        """
        # 初始证据级别
        if study_type.upper() == 'RCT':
            if rct_count > 5:
                evidence_level = 'Ia'
            else:
                evidence_level = 'Ib'
        elif study_type.upper() in ['队列研究', 'COHORT']:
            evidence_level = 'IIa' if rct_count == 0 else 'IIb'
        elif study_type.upper() in ['病例对照', 'CASE-CONTROL']:
            evidence_level = 'III'
        else:
            evidence_level = 'IV'

        # 降级因素
        downgrade_count = 0
        downgrade_reasons = []

        if not consistency:
            downgrade_count += 1
            downgrade_reasons.append('结果不一致')
        if not directness:
            downgrade_count += 1
            downgrade_reasons.append('间接证据')
        if not precision:
            downgrade_count += 1
            downgrade_reasons.append('精确度不足')
        if publication_bias:
            downgrade_count += 1
            downgrade_reasons.append('发表偏倚')

        # 计算最终级别
        level_map = {
            'Ia': ['Ia', 'Ib', 'IIa'],
            'Ib': ['Ib', 'IIa', 'IIb'],
            'IIa': ['IIa', 'IIb', 'III'],
            'IIb': ['IIb', 'III', 'IV'],
            'III': ['III', 'IV', 'IV'],
            'IV': ['IV', 'IV', 'IV']
        }

        downgraded_level = level_map[evidence_level][min(downgrade_count, 2)]

        # 推荐级别
        if downgraded_level in ['Ia', 'Ib']:
            recommendation_level = 'A'
        elif downgraded_level in ['IIa', 'IIb']:
            recommendation_level = 'B'
        else:
            recommendation_level = 'C'

        return {
            'initial_evidence_level': evidence_level,
            'downgrade_factors': downgrade_reasons,
            'final_evidence_level': downgraded_level,
            'recommendation_level': recommendation_level,
            'summary': f"证据级别 {downgraded_level}, 推荐级别 {recommendation_level}"
        }

    def assess_publication_bias(self, effect_sizes: List[float],
                               standard_errors: List[float]) -> Dict:
        """
        评估发表偏倚

        方法: Funnel plot不对称性 + Egger 回归

        返回: 是否存在显著发表偏倚
        """
        effect_sizes = np.array(effect_sizes)
        standard_errors = np.array(standard_errors)

        # Egger 回归
        precision = 1 / standard_errors
        slope, intercept, r_value, p_value, std_err = stats.linregress(precision, effect_sizes)

        # Egger 检验: H0: 截距 = 0 (无发表偏倚)
        t_stat = intercept / std_err
        p_egger = 2 * (1 - stats.t.cdf(abs(t_stat), len(effect_sizes) - 2))

        # 解释
        if p_egger < 0.05:
            bias_assessment = '存在显著发表偏倚迹象'
            bias_severity = '中等'
        elif p_egger < 0.1:
            bias_assessment = '可能存在发表偏倚'
            bias_severity = '轻度'
        else:
            bias_assessment = '未发现显著发表偏倚'
            bias_severity = '无'

        return {
            'egger_intercept': intercept,
            'egger_slope': slope,
            'p_egger': p_egger,
            'bias_assessment': bias_assessment,
            'bias_severity': bias_severity,
            'recommendation': '若存在偏倚, 建议进行亚组分析或敏感性分析'
        }

    def generate_systematic_review_table(self, output_file: str = 'systematic_review.json') -> Dict:
        """生成系统性综述表"""
        if self.trials.empty:
            return {'error': '未加载文献数据'}

        # 计算统计摘要
        summary = {
            'total_studies': len(self.trials),
            'study_types_distribution': self.trials.get('study_type', pd.Series()).value_counts().to_dict()
                                       if 'study_type' in self.trials.columns else {},
            'total_participants': int(self.trials.get('participants_n', pd.Series()).sum())
                                 if 'participants_n' in self.trials.columns else 0,
            'publication_year_range': f"{self.trials.get('author_year', pd.Series()).min()} - "
                                     f"{self.trials.get('author_year', pd.Series()).max()}"
                                     if 'author_year' in self.trials.columns else 'Unknown',
        }

        # 转换为JSON格式
        trials_json = self.trials.to_dict('records')

        report = {
            'summary': summary,
            'trials': trials_json,
            'quality_assessment': '见 JADAD 和 GRADE 评分',
            'publication_bias': '见 Funnel plot 和 Egger 回归结果'
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def generate_grade_report(self, output_file: str = 'grade_assessment_report.json') -> Dict:
        """生成 GRADE 评价报告"""
        report = {
            'evidence_grades': {
                'Ia': '一级证据 - Meta分析或多个高质量RCT',
                'Ib': '一级证据 - 单个高质量RCT或多个中等质量RCT',
                'IIa': '二级证据 - 高质量队列研究',
                'IIb': '二级证据 - 多个队列研究或大型观察性研究',
                'III': '三级证据 - 病例对照研究',
                'IV': '四级证据 - 病例报告或专家意见'
            },
            'recommendation_levels': {
                'A': '强烈推荐 - 绝大多数患者应受益',
                'B': '中等推荐 - 大多数患者应受益',
                'C': '弱推荐 - 只有部分患者可能受益',
                'D': '反对 - 不推荐使用'
            },
            'downgrade_factors': {
                'inconsistency': '结果不一致 (I² > 50%)',
                'indirectness': '间接证据 (比较的不是直接相关的人群或干预)',
                'imprecision': '精确度不足 (样本量过小或CI包含零值)',
                'publication_bias': '发表偏倚 (小样本研究结果更正向)'
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report


if __name__ == '__main__':
    # 示例
    synthesizer = LiteratureEvidenceSynthesizer()

    print("=== JADAD 评分 ===")
    jadad = synthesizer.calculate_jadad_score(
        randomization=2,   # 清楚的随机化
        blinding=2,        # 双盲
        withdrawals=1,     # 脱落报告
        description_quality=1  # 描述充分
    )
    print(f"JADAD评分: {jadad['jadad_total']}/7 ({jadad['quality_level']})")

    print("\n=== GRADE 证据评级 ===")
    grade = synthesizer.grade_evidence_quality(
        study_type='RCT',
        rct_count=8,
        consistency=True,
        directness=True,
        precision=True,
        publication_bias=False
    )
    print(f"证据级别: {grade['final_evidence_level']}")
    print(f"推荐级别: {grade['recommendation_level']}")

    print("\n=== 发表偏倚评估 ===")
    effect_sizes = [0.45, 0.52, 0.38, 0.55, 0.48, 0.60, 0.42]
    se = [0.15, 0.18, 0.12, 0.20, 0.14, 0.22, 0.16]
    bias = synthesizer.assess_publication_bias(effect_sizes, se)
    print(f"Egger p值: {bias['p_egger']:.3f}")
    print(f"评价: {bias['bias_assessment']}")

    print("\n=== 生成报告 ===")
    synthesizer.generate_grade_report('example_grade_report.json')
    print("GRADE 报告已保存")

