#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全性信号检测器 (Safety Signal Detector)

功能:
- ROR (相对报告比) 计算
- PRR (比例比率) 计算
- IC (信息量) 计算
- 信号检测和排序
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings

warnings.filterwarnings('ignore')


class SafetySignalDetector:
    """药物不良反应信号检测器"""

    def __init__(self):
        self.ae_data = None
        self.signals = {}

    def load_adverse_events(self, file_path: str) -> pd.DataFrame:
        """
        加载不良反应数据 (2x2 表格)

        期望数据结构 (列):
        - adverse_event: 不良反应名称
        - drug_ae: 该药物发生该不良反应的人数
        - drug_no_ae: 该药物未发生该不良反应的人数
        - all_drug_total: 所有药物中发生该不良反应的人数
        - all_no_ae_total: 所有药物中未发生该不良反应的人数
        """
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("仅支持 CSV 或 Excel 格式")

        self.ae_data = df
        return df

    def calculate_ror(self) -> pd.DataFrame:
        """
        计算相对报告比 (ROR - Reporting Odds Ratio)

        ROR = (a/b) / (c/d)
        其中:
        - a: 该药物+该AE
        - b: 该药物+其他AE
        - c: 其他药物+该AE
        - d: 其他药物+其他AE
        """
        df = self.ae_data.copy()

        # 2x2 表格数据
        df['a'] = df['drug_ae']
        df['b'] = df['drug_no_ae']
        df['c'] = df['all_drug_total'] - df['drug_ae']
        df['d'] = df['all_no_ae_total'] - (df['all_drug_total'] - df['drug_ae'])

        # ROR 计算
        df['ror'] = (df['a'] / df['b']) / (df['c'] / df['d'])

        # ROR 的对数标准误
        df['log_ror_se'] = np.sqrt(
            1/df['a'] + 1/df['b'] + 1/df['c'] + 1/df['d']
        )

        # 95% CI
        df['ror_ci_lower'] = np.exp(np.log(df['ror']) - 1.96 * df['log_ror_se'])
        df['ror_ci_upper'] = np.exp(np.log(df['ror']) + 1.96 * df['log_ror_se'])

        # 统计显著性
        df['z_score'] = np.log(df['ror']) / df['log_ror_se']
        df['p_value'] = 2 * (1 - stats.norm.cdf(np.abs(df['z_score'])))

        return df[['adverse_event', 'ror', 'ror_ci_lower', 'ror_ci_upper', 'p_value']]

    def calculate_prr(self) -> pd.DataFrame:
        """
        计算比例比率 (PRR - Proportional Reporting Ratio)

        PRR = (a/a+b) / (c/c+d)
        更适合处理稀有事件
        """
        df = self.ae_data.copy()

        # 构建 2x2 表格
        df['a'] = df['drug_ae']
        df['b'] = df['drug_no_ae']
        df['c'] = df['all_drug_total'] - df['drug_ae']
        df['d'] = df['all_no_ae_total'] - (df['all_drug_total'] - df['drug_ae'])

        # PRR 计算
        df['prr_drug'] = df['a'] / (df['a'] + df['b'])  # 该药物的AE比例
        df['prr_other'] = df['c'] / (df['c'] + df['d'])  # 其他药物的AE比例
        df['prr'] = df['prr_drug'] / df['prr_other']

        # 标准误 (使用对数转换)
        df['log_prr_se'] = np.sqrt(
            (1 - df['prr_drug']) / (df['a'] * df['prr_drug']) +
            (1 - df['prr_other']) / (df['c'] * df['prr_other'])
        )

        # 95% CI
        df['prr_ci_lower'] = np.exp(np.log(df['prr']) - 1.96 * df['log_prr_se'])
        df['prr_ci_upper'] = np.exp(np.log(df['prr']) + 1.96 * df['log_prr_se'])

        return df[['adverse_event', 'prr', 'prr_ci_lower', 'prr_ci_upper']]

    def calculate_ic(self) -> pd.DataFrame:
        """
        计算信息量 (IC - Information Component)

        IC = log2(观测值 / 期望值)
        IC025 = IC - 1.96 * sqrt(变异数), 为 IC 的置信下界

        原理: Bayesian Confidence Propagation Neural Network
        """
        df = self.ae_data.copy()

        # 2x2 表格
        df['a'] = df['drug_ae']
        df['b'] = df['drug_no_ae']
        df['c'] = df['all_drug_total'] - df['drug_ae']
        df['d'] = df['all_no_ae_total'] - (df['all_drug_total'] - df['drug_ae'])

        # 总计
        n = df['a'] + df['b'] + df['c'] + df['d']

        # 观测值 (observed)
        obs = df['a']

        # 期望值 (expected) = (a+c) * (a+b) / n
        exp = (df['a'] + df['c']) * (df['a'] + df['b']) / n

        # IC 计算 (log2)
        df['ic'] = np.log2(obs / exp)

        # IC 的变异数 (逆Gamma分布近似)
        # Var = 1 / obs + 1 / exp - 1 / n
        df['ic_variance'] = 1 / obs + 1 / exp - 1 / n

        # IC025 (95% 置信下界)
        df['ic025'] = df['ic'] - 1.96 * np.sqrt(df['ic_variance'])

        return df[['adverse_event', 'ic', 'ic025']]

    def detect_signals(self, ror_threshold: float = 2.0,
                      prr_threshold: float = 2.0,
                      ic025_threshold: float = 0.0) -> pd.DataFrame:
        """
        检测信号 (Signal Detection)

        标准:
        - ROR ≥ ror_threshold 且 P < 0.05
        - PRR ≥ prr_threshold 且 IC025 > ic025_threshold
        - 三个指标中至少两个满足条件才能报告为信号
        """
        ror_results = self.calculate_ror()
        prr_results = self.calculate_prr()
        ic_results = self.calculate_ic()

        # 合并结果
        signals = ror_results.merge(prr_results, on='adverse_event')
        signals = signals.merge(ic_results, on='adverse_event')

        # 判断是否为信号
        signals['is_ror_signal'] = (signals['ror'] >= ror_threshold) & (signals['p_value'] < 0.05)
        signals['is_prr_signal'] = (signals['prr'] >= prr_threshold) & (signals['ic025'] > ic025_threshold)
        signals['is_ic_signal'] = signals['ic025'] > ic025_threshold

        # 综合判断 (至少两个指标满足)
        signals['signal_count'] = signals['is_ror_signal'].astype(int) + \
                                   signals['is_prr_signal'].astype(int) + \
                                   signals['is_ic_signal'].astype(int)
        signals['is_signal'] = signals['signal_count'] >= 2

        # 信号强度评分 (0-10)
        signals['signal_strength'] = (
            signals['is_ror_signal'].astype(int) * 3 +
            signals['is_prr_signal'].astype(int) * 3 +
            signals['is_ic_signal'].astype(int) * 4
        )

        # 按强度排序
        signals = signals.sort_values('signal_strength', ascending=False)

        self.signals = signals
        return signals[signals['is_signal'] == True][
            ['adverse_event', 'ror', 'prr', 'ic', 'ic025', 'signal_strength', 'signal_count']
        ]

    def generate_signal_report(self, output_file: str = 'safety_signals_report.json'):
        """生成信号检测报告"""
        if self.signals.empty:
            print("警告: 未检测到任何信号")
            return

        signals_detected = self.signals[self.signals['is_signal'] == True]

        report = {
            'summary': {
                'total_adverse_events': len(self.ae_data),
                'signals_detected': len(signals_detected),
                'detection_criteria': {
                    'ror_threshold': 2.0,
                    'prr_threshold': 2.0,
                    'ic025_threshold': 0.0
                }
            },
            'signals': signals_detected[[
                'adverse_event', 'ror', 'ror_ci_lower', 'ror_ci_upper',
                'prr', 'ic', 'ic025', 'signal_strength'
            ]].to_dict('records'),
            'recommendation': self._generate_safety_recommendation(signals_detected)
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def _generate_safety_recommendation(self, signals: pd.DataFrame) -> List[str]:
        """生成安全性建议"""
        recommendations = []

        if len(signals) == 0:
            recommendations.append("未检测到安全性信号，药物安全性可接受。")
        elif len(signals) <= 3:
            recommendations.append(f"检测到 {len(signals)} 个潜在安全性信号，建议进一步监测。")
        else:
            recommendations.append(f"检测到 {len(signals)} 个安全性信号，建议立即评估和相应更新说明书。")

        # 按强度列出主要信号
        top_signals = signals.nlargest(3, 'signal_strength')
        for idx, sig in top_signals.iterrows():
            rec = f"  ⚠ {sig['adverse_event']}: ROR={sig['ror']:.2f}, PRR={sig['prr']:.2f}, IC025={sig['ic025']:.2f}"
            recommendations.append(rec)

        return recommendations


if __name__ == '__main__':
    # 示例
    detector = SafetySignalDetector()

    example_data = pd.DataFrame({
        'adverse_event': ['肝毒性', '肾毒性', '心脏毒性', '皮疹', '消化不适'],
        'drug_ae': [45, 32, 28, 150, 200],
        'drug_no_ae': [9955, 9968, 9972, 9850, 9800],
        'all_drug_total': [150, 120, 95, 400, 600],
        'all_no_ae_total': [9850, 9880, 9905, 9600, 9400]
    })

    detector.ae_data = example_data

    print("=== ROR 计算 ===")
    ror = detector.calculate_ror()
    print(ror)

    print("\n=== PRR 计算 ===")
    prr = detector.calculate_prr()
    print(prr)

    print("\n=== IC 计算 ===")
    ic = detector.calculate_ic()
    print(ic)

    print("\n=== 信号检测 ===")
    signals = detector.detect_signals()
    print(signals)

    print("\n=== 生成报告 ===")
    report = detector.generate_signal_report('example_safety_report.json')
    print("报告已保存")

