import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from five_rule_detector import Line, detect_lines, _rule_6


def line(page, text, y=100, x0=60):
    return Line(page, text, (x0, y, 540, y + 12), 600, 800)


class MultipleViolationLocationsTests(unittest.TestCase):

    def test_rule_6_does_not_count_abstract_header_as_copied_content(self):
        copied = [line(1, '摘 要 上海交通大学博士学位论文', 80),
                  line(1, '这一段说明方法能够有效处理复杂任务中的语义信息', 100),
                  line(1, '实验结果表明该方法在多个测试数据集上有较好表现', 120)]
        body = [line(2, item.text, 100 + i * 20) for i, item in enumerate(copied)]
        self.assertEqual(_rule_6(copied, body)['findings'], [])

    def test_rule_6_reports_two_separate_copied_passages_on_same_page(self):
        first = [
            '移动网络设备在运行过程中持续采集多种类型的传感器数据',
            '这些数据通过网络传输并存储在远程服务器以供后续分析',
            '系统根据实时分析结果为用户提供准确可靠的决策支持',
        ]
        second = [
            '实验平台采用分层架构处理不同来源的复杂业务请求',
            '多个功能模块通过统一接口协同完成数据处理任务',
            '测试结果表明该方法能够明显提高系统运行的效率',
        ]
        lines = [line(1, '摘要', 40)]
        lines += [line(1, text, 80 + i * 16) for i, text in enumerate(first)]
        lines.append(line(1, '此外本文还讨论了其他相关问题。', 140))
        lines += [line(1, text, 160 + i * 16) for i, text in enumerate(second)]
        lines += [line(1, '关键词：系统', 220), line(2, '目录', 40),
                  line(3, '第1章 绪论', 50)]
        lines += [line(3, text, 100 + i * 16) for i, text in enumerate(first)]
        lines += [line(3, text, 180 + i * 16) for i, text in enumerate(second)]
        findings = detect_lines(lines, [6])['6']['findings']
        self.assertEqual([item['text_excerpt'] for item in findings], [first[0], second[0]])

    def test_rule_6_merges_overlapping_windows_of_one_copied_passage(self):
        copied = [
            '第一行介绍移动网络中的设备如何采集和处理数据',
            '第二行介绍设备如何通过网络向远程服务器传输数据',
            '第三行介绍服务器如何保存和分析这些输入数据',
            '第四行介绍分析结果如何用于支持用户作出决策',
            '第五行介绍系统如何持续评估不同处理策略的性能',
            '第六行介绍研究团队如何验证整体方案的可靠性',
        ]
        lines = [line(1, '摘要', 40)]
        lines += [line(1, text, 80 + i * 16) for i, text in enumerate(copied)]
        lines += [line(1, '关键词：网络', 200), line(2, '目录', 40),
                  line(3, '第1章 绪论', 50)]
        lines += [line(3, text, 100 + i * 16) for i, text in enumerate(copied)]
        findings = detect_lines(lines, [6])['6']['findings']
        self.assertEqual(len(findings), 1)

    def test_rule_18_reports_each_repeated_invalid_reference_on_one_line(self):
        text = '依据公式(9.9)推导，再根据公式(9.9)验证'
        lines = [line(1, '第1章 绪论'), line(1, text, 140),
                 line(1, '(3.1)', 180, 480)]
        findings = detect_lines(lines, [18])['18']['findings']
        self.assertEqual([item['token'] for item in findings], ['9.9', '9.9'])
        self.assertEqual([item['text_range'] for item in findings], [[2, 9], [15, 22]])

    def test_rule_22_reports_every_missing_citation_occurrence(self):
        text = '研究[99]提出方法，另一研究[99]进行了验证。'
        lines = [line(1, '第1章 绪论'), line(1, text, 140),
                 line(2, '再次参见文献[99]。', 100),
                 line(3, '参考文献', 40), line(3, '[1] 已引用文献', 100),
                 line(3, '[2] 另一文献', 130)]
        findings = detect_lines(lines, [22])['22']['findings']
        self.assertEqual([item['page'] for item in findings], [1, 1, 2])
        self.assertEqual([item['token'] for item in findings], ['99', '99', '99'])
        self.assertEqual([item['text_range'] for item in findings[:2]], [[2, 6], [15, 19]])

    def test_rule_22_distinguishes_citations_from_code_years_and_vectors(self):
        lines = [line(1, '第1章 绪论'),
                 line(1, '已有研究[99]提出方法，另见[0]', 140),
                 line(1, '网络维度为[512, 256]，实验发表于[2024]年', 160),
                 line(1, 'buffer[0] = values[0];', 180),
                 line(1, '𝐹𝑎𝑣𝑔[0], 𝐹𝑠𝑡𝑑[0]', 185),
                 line(1, '共享[0]n−1，用于构建', 190),
                 line(1, 'WL[255]    BLB[255]', 195),
                 line(1, 'Q网络隐藏层维数 [256,256]', 196),
                 line(1, 'CLICK [384,85] TYPE [jacket]', 197),
                 line(1, '方法MAD-X[524]可以扩展模型', 200),
                 line(1, '9      −      0.5734[184]      −', 220),
                 line(2, '参考文献', 40), line(2, '[1] 甲', 100), line(2, '[2] 乙', 130)]
        findings = detect_lines(lines, [22])['22']['findings']
        self.assertEqual([item['token'] for item in findings], ['99', '0', '524', '184'])

    def test_rule_22_excludes_numeric_fragment_index_range(self):
        lines = [line(1, '第1章 方法', 50),
                 line(1, '高风险操作码位于片段索引[120-150]，涉及密集交互。', 140),
                 line(1, '相关研究[120-121]对该技术进行了分析。', 160),
                 line(2, '参考文献', 40),
                 line(2, '[1] 文献甲', 100), line(2, '[2] 文献乙', 120)]
        findings = detect_lines(lines, [22])['22']['findings']
        self.assertEqual([item['token'] for item in findings], ['120', '121'])

    def test_rule_22_uses_marker_size_to_distinguish_acronym_citation_and_index(self):
        def styled(text, marker_size, y):
            start = text.index('[0]')
            spans = ((0, start, 12.0), (start, start + 3, marker_size),
                     (start + 3, len(text), 12.0))
            return Line(1, text, (60, y, 540, y + 12), 600, 800, spans)

        lines = [line(1, '第1章 方法', 50),
                 styled('论文采用LSTM[0]模型。', 8.0, 140),
                 styled('提出的pFedGraph[0]有较高性能。', 8.0, 160),
                 styled('寄存器RTMR[0]表示状态。', 12.0, 180),
                 styled('利用V[0]、V[1]和V[2]聚合特征。', 8.0, 200),
                 line(2, '参考文献', 40),
                 line(2, '[1] 文献甲', 100), line(2, '[2] 文献乙', 120)]
        findings = detect_lines(lines, [22])['22']['findings']
        self.assertEqual([item['token'] for item in findings], ['0', '0'])

    def test_rule_22_treats_zero_marker_in_prose_as_missing_citation(self):
        lines = [line(1, '第1章 绪论', 50),
                 line(1, '服务延迟增加，整体性能下降[0]。', 130),
                 line(1, 'Du 等人提出的 DeepLog[0]', 150),
                 line(1, '以GPT-4[0]为代表的方法取得进展。', 170),
                 line(1, 'form Module, TPM）[0]作为可信计算的标准。', 180),
                 line(1, '共享[0]n−1，用于构建数学序列。', 190),
                 line(1, 'buffer[0] = values[0];', 210),
                 line(1, '腐败集合C[0]中的节点需要排除。', 215),
                 line(1, '该签名记为sign[0]。', 218),
                 line(2, '参考文献', 40),
                 line(2, '[1] 甲', 100), line(2, '[2] 乙', 120)]
        findings = detect_lines(lines, [22])['22']['findings']
        self.assertEqual([(item['page'], item['token']) for item in findings],
                         [(1, '0'), (1, '0'), (1, '0'), (1, '0')])

    def test_rule_22_ignores_regex_character_class(self):
        lines = [line(1, '第1章 方法'),
                 line(1, r'^(?:8[\d])|(?:9[189]))\d{8}$', 140),
                 line(2, '参考文献', 40), line(2, '[1] 文献甲', 100),
                 line(2, '[2] 文献乙', 130)]
        result = detect_lines(lines, [22])['22']
        self.assertEqual(result['findings'], [])

    def test_rule_22_ignores_numeric_data_when_reference_range_is_large(self):
        lines = [line(1, '第1章 方法')]
        data = [r'^(?:9[189]))\d{8}$',
                '在M∈[9, 64] 区间内',
                '[64, 64]', '[7,7,320]', 'char buf[1024];',
                '[240], d1=0.01', 'message: [0110010100]',
                'layer sizes were chosen from ranges [100, 200] and [20, 50]']
        lines += [line(1, text, 140 + i * 18) for i, text in enumerate(data)]
        lines += [line(1, '方法MAD-X[524]可以扩展模型', 285),
                  line(1, '0.5734[184] 需要追溯', 305),
                  line(2, '参考文献', 40), line(2, '[1] 文献甲', 100),
                  line(2, '[500] 文献乙', 130)]
        findings = detect_lines(lines, [22])['22']['findings']
        self.assertEqual([item['token'] for item in findings], ['524', '184'])

    def test_rule_24_counts_standalone_and_model_name_citation_ranges(self):
        lines = [line(1, '第1章 方法', 50),
                 line(1, '[12,76]', 130),
                 line(1, 'PIC[59-60]可用于比较。', 150),
                 line(1, 'RAG[65-66]与其他方法比较。', 170),
                 line(1, '适用范围[42-43]。', 190),
                 line(2, '参考文献', 40)]
        labels = (12, 76, 59, 60, 65, 66, 42, 43)
        lines += [line(2, f'[{number}] 文献{number}', 80 + i * 20)
                  for i, number in enumerate(labels)]
        result = detect_lines(lines, [22, 24])
        self.assertEqual(result['22']['findings'], [])
        self.assertEqual(result['24']['findings'], [])

    def test_rule_24_counts_citations_after_matrix_noun(self):
        lines = [line(1, '第1章 方法', 50),
                 line(1, '需要计算二阶 Hessian 矩阵[71,233]，因此开销较大。', 140),
                 line(1, '矩阵尺寸为[9,64]，只表示数值形状。', 160),
                 line(2, '参考文献', 40),
                 line(2, '[71] 已引用文献', 100),
                 line(2, '[233] 已引用文献', 120)]
        result = detect_lines(lines, [22, 24])
        self.assertEqual(result['22']['findings'], [])
        self.assertEqual(result['24']['findings'], [])

    def test_english_chapter_precedes_numbered_references(self):
        lines = [line(1, 'Chapter 1 Introduction', 50),
                 line(1, 'Prior work [1] motivates the method.', 140),
                 line(2, 'References', 50),
                 line(2, '[1] Cited work', 100), line(2, '[2] Uncited work', 130),
                 line(4, '1 Appendix Dataset', 50)]
        result = detect_lines(lines, [22, 24])
        self.assertEqual(result['22']['status'], 'completed')
        self.assertEqual([item['token'] for item in result['24']['findings']], ['2'])

    def test_rule_24_ignores_bibliography_web_access_date_as_label(self):
        lines = [line(1, '第1章 绪论'), line(1, '已有研究[1]和[2]。', 140),
                 line(2, '参考文献', 40), line(2, '[1] 第一文献', 100),
                 line(2, '[2] 第二文献', 130),
                 line(2, '[2026]. https://example.org', 160)]
        result = detect_lines(lines, [24])['24']
        self.assertEqual(result['findings'], [])

    def test_rule_24_reports_each_uncited_reference_entry(self):
        lines = [line(1, '第1章 绪论'), line(1, '已有研究[1]指出该问题', 140),
                 line(2, '参考文献', 40), line(2, '[1] 已引用', 100),
                 line(2, '[2] 未引用', 130), line(3, '[3] 未引用', 100)]
        findings = detect_lines(lines, [24])['24']['findings']
        self.assertEqual([(item['page'], item['token']) for item in findings],
                         [(2, '2'), (3, '3')])

    def test_rule_28_reports_each_wrong_toc_entry(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            name = f'{logical} 测试章节{logical}'
            shown = logical + 1 if logical in (1, 6) else logical
            lines.append(line(1, f'{name}........................{shown}', 80 + logical * 20))
            lines.append(line(logical + 2, name, 90))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([item['actual_page'] for item in result['findings']], [1, 6])


    def test_rule_28_reports_unnumbered_academic_output_heading(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 7):
            title = f'{logical} 测试章节{logical}'
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(line(logical + 2, title, 90))
        lines.append(line(1, '学术论文和科研成果目录........83', 230))
        lines.append(line(20, '学术论文和科研成果目录', 90))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([(item['page'], item['token']) for item in result['findings']],
                         [(1, '83')])

    def test_rule_28_ignores_distant_toc_like_body_page(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'{logical} 测试章节{logical}'
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(line(logical + 2, title, 90))
        for index in range(1, 4):
            lines.append(line(11, f'{index} 数据目录列表........{index}', 80 + index * 20))
        lines.append(line(25, '结尾'))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])

    def test_rule_28_ignores_wrapped_toc_continuation_without_section_number(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'{logical} 测试章节{logical}'
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(line(logical + 2, title, 90))
        lines.append(line(1, 'dataset........................99', 260))
        lines.append(line(10, 'dataset', 90))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['findings'], [])

    def test_rule_28_uses_printed_footer_when_physical_offset_changes(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'{logical} 测试章节{logical}'
            physical = logical + 2 if logical <= 5 else logical + 5
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(line(physical, title, 90))
            lines.append(line(physical, str(logical), 749, 302))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])

    def test_rule_28_prefers_actual_large_heading_over_earlier_outline_mention(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'第{logical}章 测试章节{logical}'
            physical = logical + 3
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(Line(physical, title, (60, 124, 540, 144), 600, 800))
            lines.append(line(physical, str(logical), 749, 302))
        lines.extend(line(2, f'组织结构说明{i}', 180 + i * 20) for i in range(5))
        lines.append(Line(2, '第3章 测试章节3', (60, 360, 540, 375), 600, 800))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])

    def test_rule_28_ignores_corrupted_oversized_text_bbox(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'第{logical}章 测试章节{logical}'
            physical = logical + 2
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(Line(physical, title, (60, 124, 540, 142), 600, 800))
            lines.append(line(physical, str(logical), 749, 302))
        lines.append(Line(11, '第3章 测试章节3', (60, 74, 540, 146), 600, 800))
        lines.append(line(11, '9', 749, 302))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['findings'], [])

    def test_rule_28_does_not_boost_running_header_with_math_symbol(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'第{logical}章 测试章节{logical}'
            physical = logical + 2
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(Line(physical, title, (70, 124, 540, 142), 600, 800))
            lines.append(line(physical, str(logical), 749, 302))
        lines.extend([Line(11, '第3章 测试章节3', (350, 74, 540, 84), 600, 800),
                      Line(11, '··· ···', (340, 111, 430, 137), 600, 800),
                      line(11, '9', 749, 302)])
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['findings'], [])

    def test_rule_28_ignores_section_sign_in_outline_diagram(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'{logical}.1 测试章节{logical}'
            physical = logical + 2
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            if logical == 3:
                lines.append(Line(physical, title, (85, 588, 400, 602), 600, 800))
            else:
                lines.append(line(physical, title, 100))
        lines.append(Line(2, '§3.1 测试章节3', (256, 345, 450, 358), 600, 800))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['findings'], [])

    def test_rule_28_uses_earlier_bottom_of_page_section_heading(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'{logical} 测试章节{logical}'
            physical = logical + 2
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            if logical == 3:
                lines.extend([Line(physical, '3', (60, 630, 75, 642), 600, 800),
                              Line(physical, '测试章节3', (80, 630, 260, 642), 600, 800)])
            else:
                lines.append(line(physical, title, 100))
            lines.append(line(physical, str(logical), 749, 302))
        lines.append(Line(6, '3 测试章节3', (60, 129, 260, 141), 600, 800))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['findings'], [])

    def test_rule_28_ignores_small_running_header_on_sparse_later_page(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'第{logical}章 测试章节{logical}'
            physical = logical * 2 + 2
            lines.append(line(1, f'{title}........{logical}', 80 + logical * 20))
            lines.append(Line(physical, title, (60, 124, 540, 140), 600, 800))
            lines.append(line(physical, f'正文说明{logical}', 180))
            lines.append(line(physical, str(logical), 749, 302))
        lines.append(Line(9, '第3章 测试章节3', (60, 74, 540, 83), 600, 800))
        lines.append(Line(9, '图像注释', (60, 200, 540, 206), 600, 800))
        lines.append(Line(9, '4', (302, 749, 308, 753), 600, 800))
        result = detect_lines(lines, [28])['28']
        self.assertEqual(result['findings'], [])

    def test_rule_28_reports_incorrect_toc_against_printed_footer(self):
        lines = [line(1, '目录', 40)]
        for logical in range(1, 9):
            title = f'{logical} 测试章节{logical}'
            shown = 99 if logical == 7 else logical
            physical = logical + 2 if logical <= 5 else logical + 5
            lines.append(line(1, f'{title}........{shown}', 80 + logical * 20))
            lines.append(line(physical, title, 90))
            lines.append(line(physical, str(logical), 749, 302))
        result = detect_lines(lines, [28])['28']
        self.assertEqual([finding['actual_page'] for finding in result['findings']], [7])

    def test_rule_18_formula_free_body_is_clean(self):
        lines = [line(1, '第1章 绪论'), line(1, '本文讨论相关研究背景。', 140)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])

    def test_rule_18_recognizes_number_at_right_end_of_formula_line(self):
        lines = [line(1, '第2章 方法'),
                 line(1, '依据式(2-2)得到结果', 140),
                 line(1, 'x = y + z                 (2-2)', 180, 170),
                 line(1, '(3.1)', 230, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['findings'], [])

    def test_rule_18_does_not_treat_prose_reference_as_displayed_number(self):
        lines = [line(1, '第2章 方法'),
                 line(1, '依据式(9.9)', 140),
                 line(1, '(3.1)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual([item['token'] for item in result['findings']], ['9.9'])

    def test_rule_18_accepts_group_reference_when_subequations_exist(self):
        lines = [line(1, '第4章 方法'), line(1, '根据式(4.11)进行计算', 140),
                 line(1, '(4.11a)', 180, 480), line(1, '(4.11b)', 210, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])

    def test_rule_18_reports_missing_specific_subequation(self):
        lines = [line(1, '第4章 方法'), line(1, '根据式(4.11a)进行计算', 140),
                 line(1, '(4.11b)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual([item['token'] for item in result['findings']], ['4.11a'])

    def test_rule_18_accepts_range_with_both_formula_targets(self):
        lines = [line(1, '第3章 方法'), line(1, '具体见公式(3.23-3.24)', 140),
                 line(1, '(3.23)', 180, 480), line(1, '(3.24)', 210, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])

    def test_rule_18_reports_only_missing_formula_in_range(self):
        lines = [line(1, '第3章 方法'), line(1, '具体见公式(3.23-3.24)', 140),
                 line(1, '(3.23)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual([item['token'] for item in result['findings']], ['3.24'])


    def test_rule_18_normalizes_unicode_minus_in_displayed_number(self):
        lines = [line(1, '第2章 方法'), line(1, '依据式(2-1)计算', 140),
                 line(1, '(2 −1)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['findings'], [])


    def test_rule_18_ignores_formula_explicitly_attributed_to_cited_work(self):
        lines = [line(1, '第3章 方法'),
                 line(1, '根据文献[176]中提出的相关公式(8-11)计算参数', 140),
                 line(1, '(3.1)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['findings'], [])

    def test_rule_18_ignores_external_formula_attribution_wrapped_to_next_line(self):
        lines = [line(1, '第3章 方法'),
                 line(1, '参数依照文献[176]中提出的', 140),
                 line(1, '相关公式(8-11)计算阻抗', 160),
                 line(1, '(3.1)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual(result['findings'], [])

    def test_rule_18_keeps_own_formula_after_external_citation_sentence(self):
        lines = [line(1, '第3章 方法'),
                 line(1, '文献[176]给出背景。本文公式(8-11)用于计算', 140),
                 line(1, '(3.1)', 180, 480)]
        result = detect_lines(lines, [18])['18']
        self.assertEqual([item['token'] for item in result['findings']], ['8-11'])


if __name__ == '__main__':
    unittest.main()
