#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
药物动学计算器 (Pharmacokinetic Calculator)

功能:
- 房室参数拟合 (一室、二室模型)
- 特殊人群PK参数调整 (肝肾功能)
- 治疗药物监测 (TDM) 建议
"""

import numpy as np
from scipy.optimize import curve_fit
from scipy import stats
import pandas as pd
import json
import warnings

warnings.filterwarnings('ignore')


class PharmacokineticCalculator:
    """药物动学计算器"""

    def __init__(self):
        self.pk_params = {}
        self.model = None

    def one_compartment_model(self, time, dose, ke, vd):
        """
        一室模型 (One-Compartment Model)

        血药浓度 C(t) = (Dose / Vd) * exp(-ke * t)

        Args:
            time: 给药后时间 (小时)
            dose: 给药剂量 (mg)
            ke: 消除速率常数 (1/小时)
            vd: 分布容积 (L)
        """
        return (dose / vd) * np.exp(-ke * time)

    def two_compartment_model(self, time, dose, k10, k12, k21, vd):
        """
        二室模型 (Two-Compartment Model)

        中心室: dC1/dt = -k10*C1 - k12*C1 + k21*C2
        外周室: dC2/dt = k12*C1 - k21*C2

        参数:
        - k10: 从中心室消除的速率常数
        - k12: 从中心室至外周室的转运速率常数
        - k21: 从外周室至中心室的转运速率常数
        - vd: 中心室分布容积
        """
        alpha = 0.5 * (k10 + k12 + k21 - np.sqrt((k10 + k12 + k21) ** 2 - 4 * k10 * k21))
        beta = 0.5 * (k10 + k12 + k21 + np.sqrt((k10 + k12 + k21) ** 2 - 4 * k10 * k21))

        A = ((k21 - alpha) * dose) / (vd * (beta - alpha))
        B = ((k21 - beta) * dose) / (vd * (beta - alpha))

        return A * np.exp(-alpha * time) + B * np.exp(-beta * time)

    def fit_pk_parameters(self, time_data: np.ndarray, conc_data: np.ndarray,
                         dose: float, model: str = 'one_compartment') -> Dict:
        """
        拟合PK参数

        Args:
            time_data: 采样时间点 (小时)
            conc_data: 对应血药浓度 (ng/mL)
            dose: 给药剂量
            model: 'one_compartment' 或 'two_compartment'
        """
        if model == 'one_compartment':
            # 初始参数估计
            p0 = [0.3, 50]  # [ke, Vd]

            def objective(t, ke, vd):
                return self.one_compartment_model(t, dose, ke, vd)

            popt, _ = curve_fit(objective, time_data, conc_data, p0=p0, maxfev=10000)
            ke, vd = popt

            # 计算PK参数
            t_half = np.log(2) / ke
            cl = ke * vd  # 清除率 = ke * Vd
            auc = dose / cl

            self.pk_params = {
                'model': model,
                'ke': ke,
                'vd': vd,
                'half_life': t_half,
                'clearance': cl,
                'auc': auc,
                'peak_concentration': dose / vd,
                'trough_concentration': (dose / vd) * np.exp(-ke * 24)  # 24小时后
            }

        elif model == 'two_compartment':
            # 二室模型拟合
            p0 = [0.2, 0.1, 0.05, 40]  # [k10, k12, k21, Vd]

            def objective(t, k10, k12, k21, vd):
                return self.two_compartment_model(t, dose, k10, k12, k21, vd)

            popt, _ = curve_fit(objective, time_data, conc_data, p0=p0, maxfev=10000)
            k10, k12, k21, vd = popt

            alpha = 0.5 * (k10 + k12 + k21 - np.sqrt((k10 + k12 + k21) ** 2 - 4 * k10 * k21))
            beta = 0.5 * (k10 + k12 + k21 + np.sqrt((k10 + k12 + k21) ** 2 - 4 * k10 * k21))

            cl = k10 * vd
            auc = dose / cl

            self.pk_params = {
                'model': model,
                'k10': k10,
                'k12': k12,
                'k21': k21,
                'vd': vd,
                'alpha': alpha,
                'beta': beta,
                'half_life': np.log(2) / beta,
                'clearance': cl,
                'auc': auc
            }

        return self.pk_params

    def adjust_for_renal_function(self, creatinine_clearance: float,
                                 normal_cl: float = 100) -> Dict:
        """
        根据肾功能调整剂量

        Args:
            creatinine_clearance: 肌酐清除率 (mL/min)
            normal_cl: 正常肾功能清除率 (mL/min, 默认100)

        Returns:
            调整建议
        """
        renal_fraction = creatinine_clearance / normal_cl

        if creatinine_clearance >= 90:
            renal_status = '正常肾功能'
            dose_adjustment = 100
        elif creatinine_clearance >= 60:
            renal_status = '轻度肾功能障碍'
            dose_adjustment = int(renal_fraction * 100)
        elif creatinine_clearance >= 30:
            renal_status = '中度肾功能障碍'
            dose_adjustment = int(renal_fraction * 100)
        else:
            renal_status = '重度肾功能障碍'
            dose_adjustment = int(renal_fraction * 100)

        return {
            'creatinine_clearance': creatinine_clearance,
            'renal_status': renal_status,
            'dose_adjustment_percentage': dose_adjustment,
            'recommendation': f"建议给药量 = 标准量 × {dose_adjustment}%"
        }

    def adjust_for_hepatic_function(self, child_pugh_score: int) -> Dict:
        """
        根据肝功能(Child-Pugh评分)调整剂量

        Child-Pugh 评分:
        - <6: 正常肝功能
        - 6-9: 轻度肝功能障碍 (A级)
        - 10-15: 中度肝功能障碍 (B级)
        - >15: 重度肝功能障碍 (C级)
        """
        if child_pugh_score < 6:
            hepatic_status = '正常肝功能'
            dose_adjustment = 100
        elif child_pugh_score <= 9:
            hepatic_status = 'Child-Pugh A级 (轻度)'
            dose_adjustment = 75
        elif child_pugh_score <= 15:
            hepatic_status = 'Child-Pugh B级 (中度)'
            dose_adjustment = 50
        else:
            hepatic_status = 'Child-Pugh C级 (重度)'
            dose_adjustment = 25

        return {
            'child_pugh_score': child_pugh_score,
            'hepatic_status': hepatic_status,
            'dose_adjustment_percentage': dose_adjustment,
            'recommendation': f"建议给药量 = 标准量 × {dose_adjustment}%\n禁忌: {hepatic_status} 患者可能禁用"
        }

    def adjust_for_geriatric(self, age: int, weight: float = None) -> Dict:
        """
        老年患者给药调整

        Args:
            age: 年龄
            weight: 体重 (kg)
        """
        if age < 65:
            return {'age_status': '成人', 'dose_adjustment': 100}

        dose_adjustment = max(50, 100 - (age - 65) * 0.5)  # 每增加1岁, 减少0.5%

        return {
            'age': age,
            'age_status': '老年患者',
            'dose_adjustment_percentage': int(dose_adjustment),
            'recommendation': f"建议给药量 = 标准量 × {dose_adjustment:.0f}%",
            'special_monitoring': '建议更频繁的监测和浓度检测'
        }

    def therapeutic_drug_monitoring(self, measured_conc: float,
                                   target_range: Tuple[float, float],
                                   current_dose: float,
                                   ke: float) -> Dict:
        """
        治疗药物监测 (TDM) 建议

        Args:
            measured_conc: 测定血药浓度 (ng/mL)
            target_range: 目标浓度范围 (元组)
            current_dose: 当前给药量 (mg)
            ke: 消除速率常数
        """
        target_low, target_high = target_range

        if target_low <= measured_conc <= target_high:
            status = '浓度合理'
            recommendation = '继续维持当前给药方案'
            new_dose = current_dose
        elif measured_conc < target_low:
            status = '浓度过低'
            # 根据线性药动学: 新剂量 = 当前剂量 × (目标浓度中值 / 当前浓度)
            new_dose = current_dose * ((target_low + target_high) / 2 / measured_conc)
            recommendation = f"建议增加给药量至 {new_dose:.0f} mg"
        else:
            status = '浓度过高'
            new_dose = current_dose * ((target_low + target_high) / 2 / measured_conc)
            recommendation = f"建议减少给药量至 {new_dose:.0f} mg"

        return {
            'measured_concentration': measured_conc,
            'target_range': f"({target_low}-{target_high}) ng/mL",
            'status': status,
            'current_dose': current_dose,
            'recommended_dose': new_dose,
            'recommendation': recommendation
        }

    def generate_pk_report(self, output_file: str = 'pk_analysis_report.json'):
        """生成PK分析报告"""
        report = {
            'pk_parameters': self.pk_params,
            'clinical_recommendations': {
                'maintenance_dose_mg_per_day': self.pk_params.get('clearance', 0) *
                                              self.pk_params.get('vd', 1) *
                                              self.pk_params.get('ke', 0),
                'dosing_interval_hours': 24 / (np.log(2) /
                                             (self.pk_params.get('ke', 0.001) if
                                             self.pk_params.get('ke') else 0.001)),
                'therapeutic_drug_monitoring': 'recommended'
                                             if self.pk_params.get('ke', 0) < 0.2 else
                                             'optional'
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report


if __name__ == '__main__':
    # 示例
    calc = PharmacokineticCalculator()

    # 模拟数据: 给药后的血药浓度
    time_data = np.array([0.5, 1, 2, 4, 8, 12, 24])
    dose = 500  # mg

    # 一室模型参数: ke=0.2, Vd=50
    true_conc = calc.one_compartment_model(time_data, dose, ke=0.2, vd=50)
    # 加入噪音
    noisy_conc = true_conc + np.random.normal(0, true_conc * 0.05)

    print("=== 一室模型拟合 ===")
    params = calc.fit_pk_parameters(time_data, noisy_conc, dose, model='one_compartment')
    print(f"半衰期: {params['half_life']:.2f} 小时")
    print(f"清除率: {params['clearance']:.2f} L/小时")
    print(f"AUC: {params['auc']:.2f} ng*h/mL")

    print("\n=== 肾功能调整 ===")
    renal_adj = calc.adjust_for_renal_function(creatinine_clearance=45)
    print(f"状态: {renal_adj['renal_status']}")
    print(f"给药调整: {renal_adj['recommendation']}")

    print("\n=== 肝功能调整 ===")
    hepatic_adj = calc.adjust_for_hepatic_function(child_pugh_score=8)
    print(f"状态: {hepatic_adj['hepatic_status']}")
    print(f"给药调整: {hepatic_adj['recommendation']}")

    print("\n=== 老年患者调整 ===")
    geriatric_adj = calc.adjust_for_geriatric(age=75)
    print(f"给药调整: {geriatric_adj['recommendation']}")

    print("\n=== 治疗药物监测 ===")
    tdm = calc.therapeutic_drug_monitoring(
        measured_conc=8.5,
        target_range=(10, 20),
        current_dose=500,
        ke=0.2
    )
    print(f"状态: {tdm['status']}")
    print(f"建议: {tdm['recommendation']}")

