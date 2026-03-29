#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临床有效性分析器 (Drug Efficacy Analyzer)

功能:
- 导入临床试验数据
- 进行Meta分析 (固定/随机效应模型)
- 计算异质性指标 (I²)
- 生成森林图
- 评估发表偏倚
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
from typing import Dict, List, Tuple, Optional

warnings.filterwarnings('ignore')


class DrugEfficacyAnalyzer:
    """药物临床有效性分析器"""

    def __init__(self):
        self.trials = []
        self.meta_results = {}
        self.publication_bias = {}

    def load_trial_data(self, file_path: str) -> pd.DataFrame:
        """
        加载临床试验数据 (CSV/Excel)

        期望列:
        - trial_id: 试验编号
        - author_year: 作者_年份
        - drug_responders: 药物组有效人数
        - drug_total: 药物组总人数
        - control_responders: 对照组有效人数
        - control_total: 对照组总人数
        - study_quality: 研究质量评分 (JADAD, 0-7)
        """
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("仅支持 CSV 或 Excel 格式")

        self.trials = df
        self._validate_data()
        return df

    def _validate_data(self):
        """验证数据完整性"""
        required_cols = ['drug_responders', 'drug_total', 'control_responders', 'control_total']
        for col in required_cols:
            if col not in self.trials.columns:
                raise ValueError(f"缺少必需列: {col}")

        # 检查数据逻辑
        assert (self.trials['drug_responders'] <= self.trials['drug_total']).all(), "有效人数不能超过总人数"
        assert (self.trials['control_responders'] <= self.trials['control_total']).all(), "对照组数据错误"

    def calculate_odds_ratio(self) -> pd.DataFrame:
        """计算每项试验的比值比 (OR) 和 95% CI"""
        trials = self.trials.copy()

        # 添加连续性修正 (0.5)
        trials['drug_responders'] = trials['drug_responders'] + 0.5
        trials['drug_non_responders'] = trials['drug_total'] - trials['drug_responders'] + 0.5
        trials['control_responders'] = trials['control_responders'] + 0.5
        trials['control_non_responders'] = trials['control_total'] - trials['control_responders'] + 0.5

        # 计算 OR
        trials['log_or'] = np.log(
            (trials['drug_responders'] / trials['drug_non_responders']) /
            (trials['control_responders'] / trials['control_non_responders'])
        )

        # 计算标准误
        trials['se_log_or'] = np.sqrt(
            1/trials['drug_responders'] +
            1/trials['drug_non_responders'] +
            1/trials['control_responders'] +
            1/trials['control_non_responders']
        )

        # 95% CI
        trials['or'] = np.exp(trials['log_or'])
        trials['or_ci_lower'] = np.exp(trials['log_or'] - 1.96 * trials['se_log_or'])
        trials['or_ci_upper'] = np.exp(trials['log_or'] + 1.96 * trials['se_log_or'])

        return trials

    def meta_analysis(self, model: str = 'random') -> Dict:
        """
        进行Meta分析

        Args:
            model: 'fixed' (固定效应模型) 或 'random' (随机效应模型)

        Returns:
            包含Meta分析结果的字典
        """
        trials = self.calculate_odds_ratio()

        # 计算权重
        if model == 'fixed':
            # 固定效应: 权重 = 1 / SE²
            trials['weight'] = 1 / (trials['se_log_or'] ** 2)
        elif model == 'random':
            # 随机效应: 需要先计算异质性
            heterogeneity = self._calculate_heterogeneity(trials)
            tau_squared = heterogeneity['tau_squared']
            trials['weight'] = 1 / (trials['se_log_or'] ** 2 + tau_squared)
        else:
            raise ValueError("model 必须是 'fixed' 或 'random'")

        # 加权平均 log-OR
        total_weight = trials['weight'].sum()
        weighted_log_or = (trials['log_or'] * trials['weight']).sum() / total_weight
        pooled_or = np.exp(weighted_log_or)

        # 计算 95% CI
        se_pooled = np.sqrt(1 / total_weight)
        ci_lower = np.exp(weighted_log_or - 1.96 * se_pooled)
        ci_upper = np.exp(weighted_log_or + 1.96 * se_pooled)

        # Z 检验
        z_score = weighted_log_or / se_pooled
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

        results = {
            'model': model,
            'pooled_or': pooled_or,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'p_value': p_value,
            'z_score': z_score,
            'heterogeneity': self._calculate_heterogeneity(trials),
            'trials_data': trials,
            'total_drug_responders': int(trials['drug_responders'].sum()),
            'total_drug_patients': int(trials['drug_total'].sum()),
            'total_control_responders': int(trials['control_responders'].sum()),
            'total_control_patients': int(trials['control_total'].sum()),
        }

        self.meta_results = results
        return results

    def _calculate_heterogeneity(self, trials: pd.DataFrame) -> Dict:
        """计算异质性指标 (Q 统计、I² 、tau²)"""
        # 计算固定效应下的平均 log-OR
        weight_fixed = 1 / (trials['se_log_or'] ** 2)
        total_weight = weight_fixed.sum()
        avg_log_or = (trials['log_or'] * weight_fixed).sum() / total_weight

        # Q 统计 (Cochran)
        q_stat = (weight_fixed * (trials['log_or'] - avg_log_or) ** 2).sum()
        df = len(trials) - 1
        p_q = 1 - stats.chi2.cdf(q_stat, df)

        # I² 指标
        i_squared = max(0, (q_stat - df) / q_stat * 100)

        # tau² (异质性方差)
        if i_squared > 0:
            tau_squared = (q_stat - df) / (total_weight - (weight_fixed ** 2).sum() / total_weight)
            tau_squared = max(0, tau_squared)
        else:
            tau_squared = 0

        return {
            'q_statistic': q_stat,
            'p_value': p_q,
            'i_squared': i_squared,
            'tau_squared': tau_squared,
            'interpretation': self._interpret_heterogeneity(i_squared)
        }

    def _interpret_heterogeneity(self, i_squared: float) -> str:
        """解释 I² 指标"""
        if i_squared < 25:
            return "低异质性 - 可考虑固定效应模型"
        elif i_squared < 50:
            return "中等异质性 - 推荐随机效应模型"
        elif i_squared < 75:
            return "中高异质性 - 应深入调查异质性来源"
        else:
            return "高异质性 - 不建议合并，应进行亚组分析"

    def publication_bias_assessment(self) -> Dict:
        """
        评估发表偏倚 (Egger 回归)

        原理: 绘制 log-OR vs 1/SE，通过回归截距检验是否存在发表偏倚
        """
        trials = self.meta_results['trials_data']

        # 准备数据
        x = 1 / trials['se_log_or']  # 精确度 (precision)
        y = trials['log_or']  # log-OR

        # 线性回归
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Egger 检验: H0: 截距 = 0 (无发表偏倚)
        t_stat = intercept / std_err
        p_egger = 2 * (1 - stats.t.cdf(abs(t_stat), len(trials) - 2))

        results = {
            'egger_intercept': intercept,
            'egger_se': std_err,
            'p_value': p_egger,
            'interpretation': '可能存在发表偏倚' if p_egger < 0.05 else '未发现显著发表偏倚',
            'regression_slope': slope,
            'r_squared': r_value ** 2
        }

        self.publication_bias = results
        return results

    def forest_plot_data(self) -> Dict:
        """
        生成森林图数据 (用于外部可视化)

        返回格式用于生成 Plotly/matplotlib 森林图
        """
        trials = self.meta_results['trials_data']
        meta = self.meta_results

        plot_data = {
            'studies': [],
            'pooled_result': {
                'name': '合并效应',
                'or': meta['pooled_or'],
                'ci_lower': meta['ci_lower'],
                'ci_upper': meta['ci_upper'],
                'weight': 100,
                'is_pooled': True
            },
            'model': meta['model'],
            'i_squared': meta['heterogeneity']['i_squared']
        }

        for idx, row in trials.iterrows():
            study_weight = (row['weight'] / trials['weight'].sum()) * 100
            plot_data['studies'].append({
                'name': row.get('author_year', f'Study {idx+1}'),
                'or': row['or'],
                'ci_lower': row['or_ci_lower'],
                'ci_upper': row['or_ci_upper'],
                'weight': study_weight,
                'quality': row.get('study_quality', None)
            })

        return plot_data

    def generate_report(self, output_file: str = 'efficacy_analysis_report.json'):
        """生成完整分析报告"""
        report = {
            'summary': {
                'total_studies': len(self.trials),
                'total_patients_drug': self.meta_results['total_drug_patients'],
                'total_patients_control': self.meta_results['total_control_patients'],
                'overall_efficacy_or': round(self.meta_results['pooled_or'], 3),
                'ci_95': f"({round(self.meta_results['ci_lower'], 3)}, {round(self.meta_results['ci_upper'], 3)})",
                'p_value': f"{self.meta_results['p_value']:.2e}",
                'significant': self.meta_results['p_value'] < 0.05
            },
            'heterogeneity': self.meta_results['heterogeneity'],
            'publication_bias': self.publication_bias,
            'forest_plot_data': self.forest_plot_data(),
            'recommendation': self._generate_recommendation()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def _generate_recommendation(self) -> str:
        """生成临床建议"""
        meta = self.meta_results
        het = meta['heterogeneity']
        pub = self.publication_bias

        rec = []

        # 有效性评价
        if meta['p_value'] < 0.05 and meta['pooled_or'] > 1:
            rec.append(f"✓ 药物显示显著疗效优势 (OR={meta['pooled_or']:.2f}, p<0.05)")
        else:
            rec.append(f"✗ 未显示显著疗效优势 (p={meta['p_value']:.3f})")

        # 异质性评价
        rec.append(f"异质性: {het['interpretation']} (I²={het['i_squared']:.1f}%)")

        # 发表偏倚评价
        if pub['p_value'] < 0.05:
            rec.append(f"⚠ 检测到可能的发表偏倚 (Egger p={pub['p_value']:.3f})")

        # 证据质量
        study_quality = self.trials.get('study_quality', pd.Series()).mean()
        if study_quality:
            rec.append(f"平均研究质量评分: {study_quality:.1f}/7 (JADAD)")

        return "\n".join(rec)


if __name__ == '__main__':
    # 示例用法
    analyzer = DrugEfficacyAnalyzer()

    # 示例数据
    example_data = pd.DataFrame({
        'trial_id': ['T001', 'T002', 'T003', 'T004', 'T005'],
        'author_year': ['Smith_2020', 'Jones_2021', 'Wang_2022', 'Brown_2021', 'Lee_2022'],
        'drug_responders': [120, 95, 140, 110, 130],
        'drug_total': [200, 180, 240, 200, 220],
        'control_responders': [85, 60, 95, 70, 80],
        'control_total': [200, 180, 240, 200, 220],
        'study_quality': [6, 5, 6, 5, 6]
    })

    analyzer.trials = example_data
    analyzer._validate_data()

    # 进行 Meta 分析
    print("=== 固定效应模型 ===")
    results_fixed = analyzer.meta_analysis(model='fixed')
    print(f"合并 OR: {results_fixed['pooled_or']:.3f} (95% CI: {results_fixed['ci_lower']:.3f}-{results_fixed['ci_upper']:.3f})")
    print(f"P 值: {results_fixed['p_value']:.2e}")

    print("\n=== 随机效应模型 ===")
    results_random = analyzer.meta_analysis(model='random')
    print(f"合并 OR: {results_random['pooled_or']:.3f} (95% CI: {results_random['ci_lower']:.3f}-{results_random['ci_upper']:.3f})")

    print("\n=== 异质性评估 ===")
    het = results_random['heterogeneity']
    print(f"I² = {het['i_squared']:.1f}%")
    print(f"解释: {het['interpretation']}")

    print("\n=== 发表偏倚评估 ===")
    bias = analyzer.publication_bias_assessment()
    print(f"Egger 截距: {bias['egger_intercept']:.3f} (p={bias['p_value']:.3f})")
    print(f"评价: {bias['interpretation']}")

    print("\n=== 生成报告 ===")
    report = analyzer.generate_report('example_efficacy_report.json')
    print(f"报告已保存到 example_efficacy_report.json")

