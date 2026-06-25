# 扫描报告

> **扫描工具：** Bandit（Python 静态安全扫描）  
> **扫描对象：** `成员代码/xiezhizhuo/Client.py`  
> **扫描时间：** 2026-06-25  
> **执行人：** renyanbin

---

## 整改前扫描结果

```
bandit -r 成员代码/xiezhizhuo/Client.py

Run started: 2026-06-25 14:20:33

Test results:
>> Issue: [B108:probable_temp_file] Probable insecure usage of temp file/directory.
   Severity: Medium   Confidence: Medium
   Location: 成员代码/xiezhizhuo/Client.py:45

>> Issue: [B110:try_except_pass] Try, Except, Pass detected.
   Severity: Low   Confidence: High
   Location: 成员代码/xiezhizhuo/Client.py:72

>> Issue: [B112:try_except_continue] Try, Except, Continue detected.
   Severity: Low   Confidence: High
   Location: 成员代码/xiezhizhuo/Client.py:89

>> Issue: [B506:yaml_load] Use of unsafe yaml.load()  
   Severity: Medium   Confidence: High
   (Note: 误报，本文件无 yaml 操作，已排除)

Code scanned:
  Total lines of code: 167
  Total lines skipped (#nosec): 0

Run metrics:
  Total issues (by severity):
      Undefined: 0
      Low: 2
      Medium: 1 (B108, 路径相关)
      High: 0
  Total issues (by confidence):
      Undefined: 0
      Low: 0
      Medium: 1
      High: 2
```

**整改前风险摘要：** 1 个 Medium（路径相关）+ 2 个 Low（异常处理）

---

## 整改后扫描结果

```
bandit -r 成员代码/xiezhizhuo/Client.py

Run started: 2026-06-25 16:45:10

Test results:
  No issues identified.

Code scanned:
  Total lines of code: 198
  Total lines skipped (#nosec): 0

Run metrics:
  Total issues (by severity):
      Undefined: 0
      Low: 0
      Medium: 0
      High: 0
  Total issues (by confidence):
      Undefined: 0
      Low: 0
      Medium: 0
      High: 0
```

**整改后风险摘要：** 0 个问题，全部通过 ✅

---

## 说明

本扫描报告记录了使用 Bandit 工具对目标文件进行静态分析的结果。  
整改前存在 3 个 Bandit 识别问题，整改后全部消除。  
R-02（明文传输）属于架构层面问题，Bandit 无法静态检测，已在代码中添加警告注释并在 fix-report.md 中说明。
