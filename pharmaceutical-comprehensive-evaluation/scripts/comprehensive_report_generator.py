#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
综合评价报告生成器
整合六个维度的评价结果，生成完整的药品临床综合评价报告
"""

import json
from datetime import datetime
from typing import Dict

class ComprehensiveReportGenerator:
    """药品临床综合评价报告生成器"""

    def __init__(self, drug_name: str, indication: str):
        self.drug_name = drug_name
        self.indication = indication
        self.evaluation_date = datetime.now().strftime("%Y年%m月%d日")

        # 六维度评分
        self.scores = {
            '安全性': 0,
            '有效性': 0,
            '适宜性': 0,
            '经济性': 0,
            '创新性': 0,
            '可及性': 0
        }

        # 六维度权重
        self.weights = {
            '安全性': 0.25,
            '有效性': 0.25,
            '经济性': 0.20,
            '可及性': 0.15,
            '适宜性': 0.10,
            '创新性': 0.05
        }

        self.comprehensive_score = 0
        self.recommendation = ''

    def set_dimension_score(self, dimension: str, score: int):
        """设置某个维度的评分"""
        if dimension in self.scores:
            self.scores[dimension] = score
        else:
            raise ValueError(f"未知维度: {dimension}")

    def calculate_comprehensive_score(self) -> float:
        """计算加权综合评分"""
        total = sum(self.scores[dim] * self.weights[dim] for dim in self.scores)
        self.comprehensive_score = round(total, 2)
        return self.comprehensive_score

    def determine_recommendation(self) -> str:
        """根据综合评分确定推荐等级"""
        score = self.comprehensive_score

        # 安全性一票否决
        if self.scores['安全性'] < 40:
            self.recommendation = '不推荐（安全性不足）'
            return self.recommendation

        if score >= 85:
            self.recommendation = '强烈推荐'
        elif score >= 70:
            self.recommendation = '推荐'
        elif score >= 60:
            self.recommendation = '有条件推荐'
        else:
            self.recommendation = '不推荐'

        return self.recommendation

    def generate_text_report(self) -> str:
        """生成文本格式报告"""
        report = []
        report.append("=" * 80)
        report.append("药品临床综合评价报告".center(80))
        report.append("=" * 80)
        report.append("")

        # 基本信息
        report.append("一、基本信息")
        report.append("-" * 80)
        report.append(f"药品名称: {self.drug_name}")
        report.append(f"适应症: {self.indication}")
        report.append(f"评价日期: {self.evaluation_date}")
        report.append("")

        # 六维度评分
        report.append("二、六维度评价结果")
        report.append("-" * 80)
        report.append(f"{'维度':<15} {'评分':<10} {'权重':<10} {'加权得分':<10} {'等级':<10}")
        report.append("-" * 80)

        for dim in ['安全性', '有效性', '适宜性', '经济性', '创新性', '可及性']:
            score = self.scores[dim]
            weight = self.weights[dim]
            weighted = score * weight
            grade = self._get_grade(score)
            report.append(f"{dim:<15} {score:<10} {weight:<10.0%} {weighted:<10.2f} {grade:<10}")

        report.append("-" * 80)
        report.append(f"{'综合评分':<15} {self.comprehensive_score:<10.2f}")
        report.append("")

        # 综合评价结论
        report.append("三、综合评价结论")
        report.append("-" * 80)
        report.append(f"推荐等级: {self.recommendation}")
        report.append("")

        # 优势与劣势
        report.append("四、优势与劣势分析")
        report.append("-" * 80)

        strengths = [dim for dim, score in self.scores.items() if score >= 80]
        weaknesses = [dim for dim, score in self.scores.items() if score < 60]

        report.append("优势维度:")
        if strengths:
            for dim in strengths:
                report.append(f"  - {dim}: {self.scores[dim]}分")
        else:
            report.append("  无显著优势")
        report.append("")

        report.append("劣势维度:")
        if weaknesses:
            for dim in weaknesses:
                report.append(f"  - {dim}: {self.scores[dim]}分")
        else:
            report.append("  无显著劣势")
        report.append("")

        # 推荐意见
        report.append("五、推荐意见")
        report.append("-" * 80)
        report.append(self._generate_recommendation_text())
        report.append("")

        report.append("=" * 80)
        report.append("报告结束")
        report.append("=" * 80)

        return "\n".join(report)

    def generate_json_report(self) -> str:
        """生成JSON格式报告"""
        data = {
            'drug_name': self.drug_name,
            'indication': self.indication,
            'evaluation_date': self.evaluation_date,
            'dimension_scores': self.scores,
            'dimension_weights': self.weights,
            'comprehensive_score': self.comprehensive_score,
            'recommendation': self.recommendation,
            'strengths': [dim for dim, score in self.scores.items() if score >= 80],
            'weaknesses': [dim for dim, score in self.scores.items() if score < 60]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _get_grade(self, score: int) -> str:
        """根据评分获取等级"""
        if score >= 85:
            return '优'
        elif score >= 70:
            return '良'
        elif score >= 60:
            return '中'
        else:
            return '差'

    def _generate_recommendation_text(self) -> str:
        """生成推荐意见文本"""
        if self.recommendation == '强烈推荐':
            return (f"{self.drug_name}在{self.indication}治疗中表现优异，"
                   "综合评分达到优秀水平，强烈推荐纳入医保目录/医院药品目录。")
        elif self.recommendation == '推荐':
            return (f"{self.drug_name}在{self.indication}治疗中表现良好，"
                   "推荐纳入医保目录/医院药品目录。")
        elif self.recommendation == '有条件推荐':
            return (f"{self.drug_name}在{self.indication}治疗中表现一般，"
                   "建议在特定条件下使用，如限定适应症人群、加强用药监测等。")
        else:
            return (f"{self.drug_name}在{self.indication}治疗中存在明显不足，"
                   "不推荐纳入医保目录/医院药品目录。")

    def save_report(self, filename: str, format: str = 'txt'):
        """保存报告到文件"""
        if format == 'txt':
            content = self.generate_text_report()
        elif format == 'json':
            content = self.generate_json_report()
        else:
            raise ValueError("不支持的格式，请选择 'txt' 或 'json'")

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"报告已保存至: {filename}")


if __name__ == "__main__":
    # 示例用法
    generator = ComprehensiveReportGenerator(
        drug_name="阿司匹林肠溶片",
        indication="心血管疾病二级预防"
    )

    # 设置六维度评分
    generator.set_dimension_score('安全性', 72)
    generator.set_dimension_score('有效性', 88)
    generator.set_dimension_score('适宜性', 70)
    generator.set_dimension_score('经济性', 95)
    generator.set_dimension_score('创新性', 45)
    generator.set_dimension_score('可及性', 85)

    # 计算综合评分
    generator.calculate_comprehensive_score()

    # 确定推荐等级
    generator.determine_recommendation()

    # 生成并打印报告
    print(generator.generate_text_report())

    # 保存报告
    generator.save_report('aspirin_evaluation_report.txt', format='txt')
    generator.save_report('aspirin_evaluation_report.json', format='json')
