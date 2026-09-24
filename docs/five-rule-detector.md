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
- 规则 22：正文或插图清单的方括号数字引用找不到编号参考文献。
- 规则 24：编号参考文献在参考文献表前的内容中均未被引用。
- 规则 28：目录标题与正文标题匹配后，以多数标题推算页码偏移，再报告异常目录页码。

PDF 中的扫描页、无编号参考文献、不可提取的公式编号或缺少可匹配标题的目录可能返回 `unsupported`。规则 6 的完全重复是保守判断，改写后的语义重复不在这版范围内。规则 18、22、24 的结果是基于可见文字的候选违规，需要以真实论文抽样复核误报。

## 500 份本地变异检测

在此仓库根目录下，清单位于相邻工作区的 `output/source_route_batch_verified500/manifest.json`：

```powershell
python backend/scripts/evaluate_five_rules.py --manifest ..\output\source_route_batch_verified500\manifest.json --preflight
python backend/scripts/evaluate_five_rules.py --manifest ..\output\source_route_batch_verified500\manifest.json --output ..\output\five_rule_detection\report.json
```

用 `--limit 5` 可先让每条规则跑五份；`--rule 28` 只跑指定规则。输出会每处理一份就保存，使用相同命令和输出路径可从已保存的进度继续。评测器分别检测母本和 mutant，变异计划**仅在检测结束后**用于匹配预期变异位置。报告包含每规则的变异位点召回率、按 mutant 的召回率、无法判断数量和“相对母本新增发现的命中比例”。最后一项只是增量精度代理指标，不能冒充真实论文场景的 precision；真实误报率需人工标注母本发现。
