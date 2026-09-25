> **更正（2026-09-25）：** 旧版归档论文“67 TP、0 FP、100%”结论已撤回。修复版 500 对注入样本评估已完成；479 篇自然论文仍需独立人工真值，不能计算最终混淆矩阵。详见工作区 `output/CURRENT.md`。

# 本地五规则 PDF 检测器

检测器接受**一篇用户 PDF**及所选规则 `6、18、22、24、28`，只从该 PDF 提取文字与页面坐标。它不读取母本、变异计划，也不调用 DeepSeek、MinerU 或网络服务。PyMuPDF 在这里仅用于读取 PDF，不生成或修改 mutant。

## 安装及单篇检测

在项目根目录执行：

```powershell
python -m pip install -r backend/requirements-five-rule-detector.txt
python backend/scripts/five_rule_detector.py --pdf C:\path\to\paper.pdf --rule 22 --rule 24 --output C:\path\to\findings.json
```

不传 `--rule` 时运行五条规则。结果含规则状态、可见证据、PDF 物理页码和坐标。`completed` 且 `findings=[]` 表示在该规则**可解析范围内**未发现问题；`unsupported` 表示没有可靠解析到所需结构，不能当作合格。

- 规则 6：摘要连续三行与正文完全重复。
- 规则 18：正文公式引用编号找不到可见的独立公式编号。
- 规则 22：全文（参考文献表自身除外）的文献引用编号找不到对应参考文献；表格数值标注等非引文不计。
- 规则 24：编号参考文献在全文（参考文献表自身除外，包括附录、图题和表题）均未被引用。
- 规则 28：目录标题与正文标题匹配后，以多数标题推算页码偏移，再报告异常目录页码。

检测器按位置返回 `findings`：同一规则在一篇 PDF 中有多处问题时，分别给出页码和行坐标。规则 18、22 对同一行内重复出现的错误引用也分别报告，并用 `text_range=[起始字符位置, 结束字符位置]` 区分；规则 6 只将重叠的三行匹配窗口合并为同一重复段。规则 24 逐条报告未引用文献，规则 28 逐条报告已匹配目录项的页码错误。

PDF 中的扫描页、无编号参考文献、不可提取的公式编号或缺少可匹配标题的目录可能返回 `unsupported`。规则 6 的完全重复是保守判断，改写后的语义重复不在这版范围内。规则 18、22、24 的结果是基于可见文字的候选违规，需要以真实论文抽样复核误报。

## 500 对本地变异检测

唯一正式数据清单位于相邻工作区的 `output/source_route_batch_clean500_v2/manifest.json`，规则 6、18、22、24、28 各 100 对。逐对人工真实标签见 `manual_review/labels.csv`：mutant 对本规则为阳性，配对母本为阴性。旧版 `verified500` 已归档，其母本包含原生违规，不得用于正式变异检测。

在本仓库根目录执行：

```powershell
python backend/scripts/evaluate_five_rules.py --manifest ..\output\source_route_batch_clean500_v2\manifest.json --preflight
python backend/scripts/evaluate_five_rules.py --manifest ..\output\source_route_batch_clean500_v2\manifest.json --output ..\output\five_rule_detection\paired_example\report.json
```

用 `--limit 5` 可先让每条规则跑五份；`--rule 28` 只跑指定规则。评测器分别检测母本和 mutant，变异计划仅在检测结束后用于匹配预期变异位置。同一母本被多次配对时，按每对各判断一次，因此每条规则有 100 次母本判定和 100 次 mutant 判定。

## 指标和样本限制

按“规则 × 配对 PDF”计数：TP=违规且检出，FN=违规却未检出，FP=合规却报违规，TN=合规且未报。每规则 `TP+FP+TN+FN=200`，五规则合计 1000。Recall=`TP/(TP+FN)`，Precision=`TP/(TP+FP)`。解析失败或 `unsupported` 单列，不得默认为 TN。

修复后的检测器已重新完成 500 对配对注入样本评估：TP=500、FP=0、TN=500、FN=0，900 个预设变异位置全部命中；结果仅适用于该受控样本，见工作区 `output/five_rule_detection/paired_fulltext_recheck_v17/summary.json`。规则 22、24 的 479 篇自然论文复核见 `output/five_rule_detection/archive_audit/recheck_2026-09-25.md`；旧归档标签已撤回，尚不能计算自然论文的最终混淆矩阵。

工作区当前数据入口见 `output/CURRENT.md`。被替换的中间扫描在 `output/_archive/superseded-2026-09-25/`；旧 `FINAL_REPORT.md` 留在原位并已标记撤回。
