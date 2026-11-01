"""Build reproducible standard-word memory report from local paired results."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'outputs/vocabulary-standard-memory-20261101'
DEST=ROOT/'docs/vocabulary-standard-memory-release-2026-11-01'


def main():
    data=json.loads((WORK/'release.json').read_text())
    source=data['source']
    assert hashlib.sha256((ROOT/'app/service/vocabulary/query.py').read_bytes()).hexdigest()==source['sha256']['after.py']
    assert len(data['results'])==40
    for r in data['results']:
        assert r['results']['before']['signature']==r['results']['after']['signature']
        assert r['results']['before']['sql']==r['results']['after']['sql']
    implementation=subprocess.check_output(['git','log','-1','--format=%H','--','app/service/vocabulary/query.py'],cwd=ROOT,text=True).strip()
    rows=[]
    for r in data['results']:
        b,a=[r['results'][v] for v in ['before','after']]
        rows.append(dict(name=r['name'],dataset=r['dataset'],mode=r['mode'],params=r['params'],total=a['total'],returned=a['returned'],
            before_ms=b['median_ms'],after_ms=a['median_ms'],
            before_rss_mib=b.get('peak_rss_kib',0)/1024 if 'peak_rss_kib' in b else None,
            after_rss_mib=a.get('peak_rss_kib',0)/1024 if 'peak_rss_kib' in a else None,
            before_heap_mib=b['python_peak_bytes']/1048576 if b.get('python_peak_bytes') is not None else None,
            after_heap_mib=a['python_peak_bytes']/1048576 if a.get('python_peak_bytes') is not None else None,
            before_cpu_ms=b.get('median_cpu_ms'),after_cpu_ms=a.get('median_cpu_ms'),
            before_io=b.get('query_process_io_delta'),after_io=a.get('query_process_io_delta')))
    DEST.with_suffix('.json').write_text(json.dumps(dict(implementation_commit=implementation,**data,summary=rows),ensure_ascii=False,indent=2))
    with DEST.with_suffix('.csv').open('w') as f:
        keys=[k for k in rows[0] if k not in ['params','before_io','after_io']]
        w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader()
        for row in rows:w.writerow({k:row[k] for k in keys})
    by={(r['dataset'],r['name'],r['mode']):r for r in rows}
    table=['| 数据 / 返回量 | 服务耗时 ms：前→后 | 峰值RSS MiB：前→后 | Python峰值 MiB：前→后 |','|---|---:|---:|---:|']
    for dataset,label in [('current','9.5万条、39,965组'),('row_growth','47.5万条、词形不变'),('spelling_growth','47.5万条、199,825组'),('location_growth','9.5万条、1024地点')]:
        for name in ['all-1000','all-None']:
            t=by[dataset,name,'time'];rss=by[dataset,name,'rss'];h=by[dataset,name,'heap']
            returned='前1000组' if name=='all-1000' else '完整返回'
            table.append(f"| {label}，{returned} | {t['before_ms']:.2f}→{t['after_ms']:.2f} | {rss['before_rss_mib']:.2f}→{rss['after_rss_mib']:.2f} | {h['before_heap_mib']:.2f}→{h['after_heap_mib']:.2f} |")
    filtered=['| 条件 | 当前集耗时 ms：前→后 | 词形增长集耗时 ms：前→后 |','|---|---:|---:|']
    for name in ['definition','headword','both-small','both-wide','all-fields','wildcard','empty','province']:
        c,g=by['current',name,'time'],by['spelling_growth',name,'time']
        filtered.append(f"| {name} | {c['before_ms']:.2f}→{c['after_ms']:.2f} | {g['before_ms']:.2f}→{g['after_ms']:.2f} |")
    tests=(WORK/'all-tests-redis.txt').read_text();summary=re.findall(r'\d+ failed, \d+ passed[^\n]*',tests)[-1]
    failures=re.findall(r'^FAILED ([^\n]+)',tests,re.MULTILINE)
    baseline_failures=re.findall(r'^FAILED ([^\n]+)',(WORK/'baseline-failures.txt').read_text(),re.MULTILINE)
    assert failures==baseline_failures
    failure_list='\n'.join('- `'+name+'`' for name in failures)
    growth=by['spelling_growth','all-None','rss'];time=by['spelling_growth','all-None','time'];heap=by['spelling_growth','all-None','heap']
    peak_io=[(r['dataset'],r['name'],r['mode'],r['before_io'].get('write_bytes'),r['after_io'].get('write_bytes')) for r in rows if r['before_io'] is not None]
    assert all(b=='0' and a=='0' for _,_,_,b,a in peak_io)
    report=f'''# standard-words 第二轮聚合内存优化

日期2026-11-01。实现提交 `{implementation[:7]}`，比较基线 `69cfa47`。基线已经包含按需创建集合/词形计数的第一次优化；下表是本轮新增收益，没有重复计算此前收益。所有修改、数据库夹具、测试与测量在本地dev；没有新分支，没有服务器连接/修改/测试。

## 改动

- 前256个非空地点名使用共享位标识，各分组用不超过256bit的整数保存成员关系；同名地点跨用户仍按名称去重，与原规则相同。
- 第一次超过256个地点名时，后续新建分组退回原来的单字符串/按需集合结构，减少大量地点时的额外CPU开销；此前已用位集合的组继续保留精确溢出成员，一个溢出地点先用字符串，多个才升级集合，可以与位集合并存。各组固定自己的表示方式，不因后续回退丢失成员。256只限制压缩字典，不限制实际地点、词条或返回数量，整数宽度有界。
- 原词形与归一key内容相同时复用同一字符串，减少每组重复保留。简繁转换规则与已有有界转换缓存不变。
- 排名完成后，边构造响应边pop已使用的分组，缩短聚合结构与完整输出同时驻留的时间。保留已有词形计数字典的按需升级策略。

**没有改变任何SQL。** 没有添加LIMIT、索引、字段、汇总表、标准词结果缓存、后台任务或应用磁盘聚合。total、简繁归组、地点去重、词形频次及代表词、排序/并列顺序和limit=None完整输出保持一致。前端无需适配。

## 资源与语义边界

依然需要O(不同归一词组数)的聚合状态；本轮缩小状态及输出重叠，不是恒定内存算法。完整输出本身也占内存。前256个地点字典有界；超出部分只为实际涉及的分组保留精确成员，随真实不同地点增长，绝不丢弃记录。

并发、准入、线程和重试策略均不改变：现有共享heavy=2、昂贵任务=1、等待名额8、单库写槽1；仅准入等待30秒预算，无新增执行期限或自动重试。同步查询/聚合仍由原有有界执行路径承接。没有增加常驻服务。SQL失败沿用原有异常流程。

## 测量方法

- 容器限制2 CPU /2GiB /无swap/禁网，串行执行；Linux amd64在Apple ARM宿主模拟执行，Python/SQLite版本及cgroup数据见JSON。这不是生产HTTP延迟或容量承诺。
- 实际服务函数计时包含SQL、Python归一/聚合、排序及响应对象构造；不含鉴权、Redis、准入排队、HTTP网络和JSON编码。一轮预热后前后交替7轮取中位数，GC在计时外。
- RSS与tracemalloc分别另起前/后独立进程，和时间测量分开。RSS读取Linux /proc/self/status的VmHWM，避免ru_maxrss携带exec前父进程高水位；记录测量前后VmRSS/VmHWM，在响应摘要和二次验证之前采样。RSS包含查询依赖导入、SQLite及输出，不能视为整个线上worker占用；heap不含SQLite/OpenCC的原生分配。
- 四份输入：95,003条当前集；475,015条行增长且词形不变；475,015条词形增长至207,790原词形/199,825归一组；95,003条1024地点离线压力集。最后一份只修改本地夹具，部分地点没有元信息，用于聚合成员结构压力，不代表生产地理分布。
- 24组时间、8组RSS、8组heap，共40组配对。每组完整响应有序摘要、所有分组字段和total一致，实际执行SQL逐字一致；完整返回最大199,825组，没有隐性上限。数据库及源码哈希见JSON。

## 全量聚合与内存

{chr(10).join(table)}

词形增长完整返回：RSS减少约 {growth['before_rss_mib']-growth['after_rss_mib']:.2f}MiB（{(1-growth['after_rss_mib']/growth['before_rss_mib'])*100:.1f}%），Python峰值降低约{(1-heap['after_heap_mib']/heap['before_heap_mib'])*100:.1f}%；本轮服务耗时降低约{(1-time['after_ms']/time['before_ms'])*100:.1f}%。当前规模/前1000组的速度变化很小，不应宣称全部搜索都提速。

## 不同过滤条件

{chr(10).join(filtered)}

definition=标准词“太阳”；headword=方言词“日头”；both-small=“蜘蛛”＋天柱竹林/息烽；both-wide=“蜘蛛”＋廣州/香港；all-fields=默认字段“人”；wildcard=方言词“%”；empty=不存在词零命中；province=廣東。以上全部limit=None。省份文字无匹配时也保留其真实零结果，不能当成大范围测试。

少量命中或空结果主要耗在SQL扫描，本轮压缩结构收益很小；额外位查找/类型分支可能带来回退。不同地点、词形和命中分布不保证统一提速。1024地点场景单列，避免只展示29地点的有利数据；该场景完整返回在本轮中慢约6.9%，即使已针对大量地点加入新组回退，也不能承诺完全没有速度代价。这里选择保留当前实现，理由是目标压力场景（词形增长、29地点）RSS下降约78MiB且完整输出加快；地点分布与之差异很大的部署仍应重新测量。

## I/O、验证与代码复核

- 16组资源测量区间的write_bytes前后均为0；没有新增应用磁盘中间聚合。不能据此保证所有原有SQLite GROUP BY在任何条件下都不使用内部临时B树。
- 新增28项测试；重点回归84项通过。覆盖256/257及1024以上地点、溢出单值/集合与位集合双向升级、简繁词形非相邻合并、空地点、空白词形、同名跨用户、孤立词条、并列排序、7001组完整返回、分配峰值。先运行新增内存测试，基线峰值3,171,453bytes超过2MiB而失败，改动后通过。
- 完整真实Redis vocabulary回归：{summary}。失败清单及相同查询基线复核保存在本地原始记录；未算作全绿，也未修改其他任务的parser/schema/service/db_pool代码。
- 自行复核：每个已登记地点有唯一bit，未登记地点不会与bit分支重复；overflow保留全部成员；字面相同字符串共享不改变值；pop只在所有排序完成后执行，排序tie顺序和结果保持一致。没有声称独立代理CR。
- py_compile与git diff --check通过。仅为测试创建的回环Redis（64MiB/无持久化）结束已删除。

完整回归中已在原查询代码复现的6项失败如下。本轮没有修正或忽略这些其他路径的既有失败：

{failure_list}

## 限制与原始证据

这项改动降低了每次聚合的内存系数，不能证明整个2GB后端不会OOM，也没有生产并发压测。标准词数量继续增长时仍需关注整体worker、其他接口和完整响应内存。未修改前端、缓存契约或允许返回的数量。

脚本：`scripts/benchmark_vocabulary_standard_memory.py --prepare`，在上述约束容器执行`--batch --rounds 7 --output .../release.json`。需项目现有Python依赖和本地离线夹具，无需连接服务器。报告由`scripts/build_vocabulary_standard_memory_report.py`生成。

原始源码冻结、时间样本、RSS/heap、SQL及测试输出：`outputs/vocabulary-standard-memory-20261101/`。同名JSON保留完整测量，CSV保留汇总。

```json
{json.dumps(source,ensure_ascii=False,indent=2)}
```
'''
    DEST.with_suffix('.md').write_text(report)
    print(DEST.with_suffix('.md'))

if __name__=='__main__':main()
