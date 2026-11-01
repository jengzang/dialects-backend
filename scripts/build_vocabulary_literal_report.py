"""Build the local vocabulary release report from verified raw measurements."""
import csv
import hashlib
import json
import subprocess
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'outputs/vocabulary-global-20261101'
DEST=ROOT/'docs/vocabulary-global-fuzzy-release-2026-11-01'


def main():
    service=json.loads((WORK/'service.json').read_text())
    native=json.loads((WORK/'native.json').read_text())
    source=json.loads((WORK/'source.json').read_text())
    assert service['source']==native['source']==source
    assert 'paired_time_method' in service
    for frozen,live in [('after.py','query.py'),('literal_scan.py','literal_scan.py'),('scope_plan.py','scope_plan.py')]:
        assert hashlib.sha256((ROOT/'app/service/vocabulary'/live).read_bytes()).hexdigest()==source['sha256'][frozen]
    pairs=service['results'];times=[r for r in pairs if r['mode']=='time']
    assert len(times)==len(native['results'])==138 and len(pairs)==162
    for r in pairs:
        assert all(r['results']['before'][k]==r['results']['after'][k] for k in ['signature','full_rows','total'])
    by_native={(r['name'],r['dataset']):r for r in native['results']}
    by_service={(r['name'],r['dataset']):r for r in times}
    focused=json.loads((WORK/'focused-service.json').read_text())
    assert focused['source']==source and len(focused['results'])==3
    focused_map={(r['name'],r['dataset']):r for r in focused['results']}
    rows=[]
    for original in times:
        r=focused_map.get((original['name'],original['dataset']),original)
        b,a=[r['results'][v] for v in ['before','after']]
        sql=by_native[r['name'],r['dataset']]
        rows.append(dict(name=r['name'],dataset=r['dataset'],params=r['params'],total=a['total'],returned=a['returned'],
            native_before_ms=sql['median_ms']['before'],native_after_ms=sql['median_ms']['after'],
            service_before_ms=b['median_ms'],service_after_ms=a['median_ms'],
            cpu_before_ms=b['median_cpu_ms'],cpu_after_ms=a['median_cpu_ms'],
            first_before_ms=b['first_ms'],first_after_ms=a['first_ms'],identical_sql=sql['identical_sql'],
            service_rounds=len(a['samples_ms']),initial_7round_before_ms=original['results']['before']['median_ms'],initial_7round_after_ms=original['results']['after']['median_ms']))
    resources=[]
    for r in pairs:
        if r['mode']=='time':continue
        b,a=[r['results'][v] for v in ['before','after']]
        resources.append(dict(name=r['name'],dataset=r['dataset'],mode=r['mode'],
            before_rss_mib=b['peak_rss_kib']/1024,after_rss_mib=a['peak_rss_kib']/1024,
            before_heap_kib=b['python_peak_bytes']/1024 if b['python_peak_bytes'] else None,
            after_heap_kib=a['python_peak_bytes']/1024 if a['python_peak_bytes'] else None,
            before_io=b['io_delta'],after_io=a['io_delta']))
    implementation_commit=subprocess.check_output(['git','log','-1','--format=%H','--','app/service/vocabulary/query.py','app/service/vocabulary/literal_scan.py'],cwd=ROOT,text=True).strip()
    fixtures={}
    for label,path in [('current',ROOT/'outputs/vocabulary-release-20261101/current.db'),('growth',ROOT/'outputs/vocabulary-release-20261101/row-growth.db'),('high_hit',ROOT/'outputs/vocabulary-release-20261101/high-hit.db'),('skew',WORK/'skew.db')]:
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as conn:
            entries=conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]
        fixtures[label]=dict(sha256=h.hexdigest(),bytes=path.stat().st_size,entries=entries)
    payload=dict(implementation_commit=implementation_commit,fixtures=fixtures,source=source,service_environment={k:v for k,v in service.items() if k not in ['results','source']},
        native_environment={k:v for k,v in native.items() if k not in ['results','source']},results=rows,resources=resources,focused_retests=focused['results'])
    DEST.with_suffix('.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    with DEST.with_suffix('.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=[k for k in rows[0] if k!='params'],lineterminator='\n');writer.writeheader()
        for r in rows:writer.writerow({k:v for k,v in r.items() if k!='params'})
    def table(cases):
        text=['| 条件 / 数据 | 原生 SQL ms：前→后 | SQL 耗时降低 | 服务函数 ms：前→后 |',
              '|---|---:|---:|---:|']
        for label,name,ds in cases:
            n=by_native[name,ds]['median_ms'];s=by_service[name,ds]['results']
            text.append(f"| {label} | {n['before']:.3f}→{n['after']:.3f} | {(1-n['after']/n['before'])*100:.1f}% | {s['before']['median_ms']:.3f}→{s['after']['median_ms']:.3f} |")
        return '\n'.join(text)
    initial_wide=by_service['wide22-definition+headword-蜘蛛','growth']['results']
    for key,value in focused_map.items():by_service[key]=value
    examples=table([
        ('9.5万，全域方言词：蜘蛛','global-headword-蜘蛛','current'),
        ('9.5万，全域两字段：蜘蛛','global-definition+headword-蜘蛛','current'),
        ('47.5万，全域两字段：山东','global-definition+headword-山东','growth'),
        ('47.5万，全域方言词：蜘蛛（恰满50项）','global-headword-蜘蛛','growth'),
        ('47.5万，全域默认四字段：蜘蛛','global-all-蜘蛛','growth'),
        ('47.5万，全域默认四字段：无命中','global-all-不存在词零命中','growth'),
        ('47.5万，全域默认四字段：什么','global-all-什么','growth'),
        ('47.5万，22地点两字段：蜘蛛','wide22-definition+headword-蜘蛛','growth'),
        ('47.5万，22地点两字段：山东','wide22-definition+headword-山东','growth'),
    ])
    controls=table([
        ('9.5万，全域方言词：皮','global-headword-皮','current'),
        ('47.5万，22地点两字段：人','wide22-definition+headword-人','growth'),
        ('9.5万，高命中两字段：共同','dense-definition+headword','high_hit'),
        ('9.5万，旧区间高命中、最新区间无命中','dense-headword','skew'),
        ('47.5万，全域两字段：蜘蛛，计数缓存命中','global-both-蜘蛛-count-hit','growth'),
        ('47.5万，22地点两字段：人，计数缓存命中','wide22-both-人-count-hit','growth'),
    ])
    mem=['| 场景 | 进程峰值 RSS MiB：前→后 | Python 分配峰值 KiB：前→后 |','|---|---:|---:|']
    for name,ds in [('global-headword-蜘蛛','growth'),('global-all-不存在词零命中','growth'),('wide22-definition+headword-皮','growth'),('dense-definition+headword','skew')]:
        rss=next(r for r in resources if (r['name'],r['dataset'],r['mode'])==(name,ds,'rss'))
        heap=next(r for r in resources if (r['name'],r['dataset'],r['mode'])==(name,ds,'heap'))
        mem.append(f"| {name} / {ds} | {rss['before_rss_mib']:.2f}→{rss['after_rss_mib']:.2f} | {heap['before_heap_kib']:.2f}→{heap['after_heap_kib']:.2f} |")
    biggest=max((r for r in resources if r['mode']=='rss'),key=lambda r:r['after_rss_mib']-r['before_rss_mib'])
    assert all(r[v+'_io'].get('write_bytes') == 0 for r in resources for v in ['before','after'])
    tests=(WORK/'all-tests-redis.txt').read_text()
    assert '6 failed, 676 passed' in tests,tests[-400:]
    report=f'''# Vocabulary 全域及宽范围模糊搜索优化报告

日期：2026-11-01。基线 `0ff288e`；实现提交 `{implementation_commit[:7]}`。所有修改、测试、数据扩展和基准均在本地 dev；没有新建分支，没有连接、测试或更改服务器。本轮只改 `search/entries`，standard-words / map-points 保持原路径。

## 1. 实际改动及边界

1. 全域方言词或“标准词＋方言词”，普通关键词至少两字，抽样稀疏或 ID 范围很小时：先读取首页。仅当不足一页时，页内数量才是精确总数，省去重复 COUNT；满页仍精确计数。
2. 全域内容字段搜索，或已有范围规划回退的大范围地点搜索：在符合条件且抽样稀疏时，使用 `instr(字段, 字面词) > 0 AND 原 LIKE`。原 LIKE 仍决定匹配，保留简繁变体及 NUL/blob 原行为；不直接替换 LIKE。
3. 8 个 ID 区段、每段最多16条，总计最多128条样本；通过 MIN/MAX 独立标量索引查找获取边界，避免组合 MIN/MAX 扫全表。样本命中不超过1/16才启用。样本仅选择执行路径，不用于计算业务 total，也不限制结果。
4. 单字、ASCII 字母、`%`、`_`、NUL 关键词，以及精确省市/分区/标准词筛选、地点搜索字段等不套用新路径。已有小范围地点索引计划优先；窄范围不额外抽样。默认四字段多地点也只在原有普通文本守卫允许时尝试。
5. 只在第一页的独立计数缓存未命中时规划；缓存命中、第二页及以后、旧式 count loader 保持原 SQL。缓存 key/原 count SQL及参数保持不变；未新增缓存或索引。
6. 规划、页面和计数在一个读 SAVEPOINT 内；失败释放自己的保存点并保留调用方事务。没有新增重试或执行超时。

字段：`definition`=标准词，`headword`=方言词，`pronunciation`=音标，`detail`=notes/informations；默认四字段实际涉及五列。

## 2. 测量方法

- 当前数据95,003条；增长集475,015条（按用户复制，词形不变）；另有95,003条高命中集及其“旧ID区间命中、最新区间无命中”偏斜副本。偏斜集按ID阈值改写，并不保证条数各半；95,003条中有67,490条命中“共同”。只读输入库，偏斜修改只发生在独立离线夹具。
- 容器限制2 CPU、2 GiB、无 swap、禁网。串行运行，没有并发压测，不推断生产容量。
- 原生 SQL：ARM Linux / SQLite {native['sqlite']}，实际函数产生的全部 SELECT，包含探测、精确计数和页面。一次预热后交替7轮中位数；不含 Python、事务控制、HTTP、鉴权、Redis、排队或编码。
- 服务函数：SQLite {service['sqlite']}，Linux amd64镜像在Apple ARM上模拟执行；一次预热后，交替调用前后真实函数7轮（3项另复测15轮），包含 Python及读事务控制。每个场景使用新的前后数据库连接。它不是生产HTTP耗时，模拟架构的绝对数值不可换算到服务器。
- 首次调用、RSS和tracemalloc另起独立进程测量，原始 first_ms保存在JSON。没有清除宿主页缓存，首次调用不是冷盘测试。独立进程计时出现过明显调度波动，因此正式预热服务时间改成交替测量；原始独立样本一并保留。
- 共138组服务时间、12组RSS、12组heap，另138组原生 SQL；对3项有波动的模拟服务场景追加15轮交替复测。所有162组响应摘要、total及可执行的无分页完整有序行摘要一致；缓存命中SQL也核对。时间与内存分开测量。
- wide22是本地条数最多22地点，覆盖增长集约95.6%，不是声称复现生产原始22地点。small2为天柱竹林＋息烽。

## 3. 主要收益

{examples}

同一模拟环境中，增长集全域两字段“山东”的进程CPU时间中位数为 {by_service['global-definition+headword-山东','growth']['results']['before']['median_cpu_ms']:.3f}→{by_service['global-definition+headword-山东','growth']['results']['after']['median_cpu_ms']:.3f} ms；该数值仍不能代表生产CPU。

宽范围“蜘蛛”首轮7次模拟服务计时为 {initial_wide['before']['median_ms']:.3f}→{initial_wide['after']['median_ms']:.3f} ms，期间样本波动很大；主表这项采用独立15轮复测（JSON/CSV同时保留首轮数值）。两次量级差异进一步说明模拟架构的绝对延迟不宜用于生产预测。原生SQL两轮同方向降低约9%。

不足一页是较大收益的关键：当前“蜘蛛”方言词10条、两字段36条；增长集“山东”两字段10条。增长集“蜘蛛”方言词恰有50条，仍执行精确COUNT，不能套用近一半的提速结论。默认四字段不启用本轮全域短页推断，其收益来自减少 LIKE 计算。

## 4. 保留路径与退化边界

{controls}

单字和计数命中路径的SQL逐字相同，细小变化属测量波动，不能宣称提速。高命中路径仍多出有界探测，有固定开销；广域普通子串仍需扫描。抽样是启发式，无法保证任意聚集/稀疏ID分布都不回退；它只影响速度，不影响结果。

对“标准词单字段”保留计数优先，避免破坏其覆盖索引优势。对高命中全域搜索也保留计数优先，修复初版在旧记录集中命中时增加首次读取的退化。

## 5. 内存、I/O和2GB约束

{chr(10).join(mem)}

本轮重点是CPU/扫描成本，不能宣称节省了大量内存。12组独立RSS测量中最大的增量约 {biggest['after_rss_mib']-biggest['before_rss_mib']:.3f} MiB；测量为包含依赖导入和SQLite缓存的查询进程峰值，不能代表整个线上worker。Python增量为有界样本和SQL绑定，不保存全部匹配ID。

资源采样区间的进程 write_bytes 在这24组前后均为0（详见JSON）；没有增加应用磁盘中间聚合。这不等于所有SQLite查询永远不产生内部临时文件。保留现有数据库读取I/O。

并发上限不变：共享2个heavy槽、1个昂贵计算槽，单库写槽1、等待名额8；仅准入等待预算30秒，已接受任务没有新增执行期限。不增加worker/线程/常驻服务，不自动重试。短时间读快照可能延长数据库读事务；减少扫描可降低部分在线争用，但没有做并发吞吐或全站OOM消除验证。

## 6. 验证与代码复核

- 新增77项本轮单元场景及1项真实Redis HTTP场景，覆盖字面边界、简繁、ASCII、通配符、NUL、blob、空字段、同名跨用户地点和孤立词条、完整翻页、精确总数、采样阈值、偏斜分布、缓存key复用/失效、WAL并发写快照、异常保存点清理。
- 重点回归148项通过；真实Redis完整 vocabulary 套件：**676通过、6失败**。相同6项在基线0ff288e重现：配置限流期望、DOCX解析、两项词条顺序期望、map不存在字段、地点标签分隔符。没有把这些失败算作通过。
- 本地临时Redis只绑定回环地址、64MiB限制、关闭持久化，测试结束已删除；不影响现有Redis或服务器。
- 自行复核匹配必要条件、SQL参数次序、缓存签名、事务生命周期及资源边界；本轮未声称独立代理CR。py_compile与git diff --check通过。

## 7. 尚未解决的事情

全域/宽范围任意子串仍是扫描，单字高频搜索没有本轮提速；不能把它解释为生产8秒请求已经变成几十毫秒。线上历史耗时还可能含并发、资源等待、缓存、编码和worker压力，需部署后的实际分阶段记录确认。

本轮未修改标准词全域聚合、特殊音标/详情组合、imports或sql/query；不同标准词组持续增长的内存，以及整个后端共享2GB时的OOM风险，仍不算闭环。

## 8. 复现及原始记录

源码冻结/哈希、完整样本、实际SQL：`outputs/vocabulary-global-20261101/`。汇总：同名JSON与CSV。源哈希：

```json
{json.dumps(source,ensure_ascii=False,indent=2)}
```

入口：`scripts/benchmark_vocabulary_literal_release.py --prepare`，随后在上述容器约束下顺序运行 `--batch --rounds 1`、`--paired-time --rounds 7`、`--native --rounds 7`。batch用于独立首次调用、SQL/完整结果验证及资源采样；正式服务时间取paired-time，原生时间取native；另对focused-source.json的3项执行paired-time --rounds 15，结果保存在focused-service.json。使用本地已有数据库夹具和项目依赖；不需要服务器连接。
'''
    DEST.with_suffix('.md').write_text(report)
    print(DEST.with_suffix('.md'))

if __name__=='__main__':main()
