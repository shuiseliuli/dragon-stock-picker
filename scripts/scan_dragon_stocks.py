#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股人气龙头五步战法自动化筛选分析器 (Dragon Stock Scanner)
严格依据经典游资与龙头战法方法论构建：
1. 人气榜源池抓取 (东财人气榜 Top 50)
2. 负面降噪过滤 (剔除暴雷、ST、跌停A杀)
3. 宏观量能与体量匹配 (2万亿分水岭：<2万亿存量剔除大盘股，聚焦30亿~250亿中小盘)
4. 题材概念归拢与去弱留强 PK
5. 买点形态研判 (分歧低吸 vs 弱转强)
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Windows 终端 UTF-8 编码适配
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_market_regime():
    """获取沪深两市最新实时成交额，研判市场流动性水位"""
    url = 'http://qt.gtimg.cn/q=sh000001,sz399001'
    try:
        r = requests.get(url, headers=HEADERS, timeout=6)
        r.encoding = 'gbk'
        lines = [l.strip() for l in r.text.strip().split(';') if l.strip()]
        
        sh_turnover = 0.0
        sz_turnover = 0.0
        sh_point = 0.0
        sh_chg = 0.0
        sz_point = 0.0
        sz_chg = 0.0
        
        for line in lines:
            parts = line.split('~')
            if len(parts) > 37:
                code = parts[2]
                turnover_wan = float(parts[37]) if parts[37] else 0.0
                turnover_yi = turnover_wan / 10000.0
                point = float(parts[3]) if parts[3] else 0.0
                chg = float(parts[32]) if parts[32] else 0.0
                
                if '000001' in code:
                    sh_turnover = turnover_yi
                    sh_point = point
                    sh_chg = chg
                elif '399001' in code:
                    sz_turnover = turnover_yi
                    sz_point = point
                    sz_chg = chg

        total_turnover = sh_turnover + sz_turnover
        # 核心论点：2万亿流动性分水岭
        is_high_liquidity = total_turnover >= 20000.0
        
        regime = {
            'total_turnover_yi': round(total_turnover, 2),
            'sh_turnover_yi': round(sh_turnover, 2),
            'sz_turnover_yi': round(sz_turnover, 2),
            'sh_point': sh_point,
            'sh_chg': sh_chg,
            'sz_point': sz_point,
            'sz_chg': sz_chg,
            'is_high_liquidity': is_high_liquidity,
            'threshold_yi': 20000.0,
            'market_style': "增量流动性泛滥·大盘中军走趋势" if is_high_liquidity else "存量缩量博弈·剔除大盘子/聚焦中小盘高弹性"
        }
        return regime
    except Exception as e:
        print(f"获取市场量能失败: {e}")
        return {
            'total_turnover_yi': 15300.0,
            'is_high_liquidity': False,
            'threshold_yi': 20000.0,
            'market_style': "存量缩量博弈·剔除大盘子/聚焦中小盘高弹性 (默认)"
        }

def fetch_popularity_ranking(top_n=50):
    """抓取东方财富人气榜 Top N 股票"""
    url = 'https://emappdata.eastmoney.com/stockrank/getAllCurrentList'
    payload = {
        'appId': 'appId01',
        'globalId': '786e4c21-70',
        'marketType': '',
        'pageNo': 1,
        'pageSize': top_n
    }
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=8)
        data = r.json().get('data', [])
        rankings = []
        for item in data:
            rankings.append({
                'code': item.get('sc'),
                'rank': item.get('rk'),
                'rank_change': item.get('hisRc', 0)
            })
        return rankings
    except Exception as e:
        print(f"抓取人气榜失败: {e}")
        return []

def fetch_stock_quotes(stock_items):
    """批量从腾讯行情获取详细价格、市值、换手率等微观指标"""
    if not stock_items:
        return []
    
    gt_codes = []
    meta_map = {}
    for item in stock_items:
        raw_code = item['code']
        clean_code = raw_code.lower()
        if not (clean_code.startswith('sz') or clean_code.startswith('sh') or clean_code.startswith('bj')):
            clean_code = ('sh' if clean_code.startswith('6') else 'sz') + clean_code
        gt_codes.append(clean_code)
        meta_map[raw_code[2:] if raw_code.startswith(('SZ', 'SH', 'sz', 'sh')) else raw_code] = item

    quotes = []
    batch_size = 30
    for i in range(0, len(gt_codes), batch_size):
        batch = gt_codes[i:i+batch_size]
        url = 'http://qt.gtimg.cn/q=' + ','.join(batch)
        try:
            r = requests.get(url, headers=HEADERS, timeout=6)
            r.encoding = 'gbk'
            for line in r.text.strip().split(';'):
                if not line.strip():
                    continue
                parts = line.split('~')
                if len(parts) > 50:
                    code = parts[2]
                    name = parts[1]
                    price = float(parts[3]) if parts[3] else 0.0
                    yesterday_close = float(parts[4]) if parts[4] else 0.0
                    open_price = float(parts[5]) if parts[5] else 0.0
                    chg_pct = float(parts[32]) if parts[32] else 0.0
                    high = float(parts[33]) if parts[33] else 0.0
                    low = float(parts[34]) if parts[34] else 0.0
                    turnover_rate = float(parts[38]) if parts[38] else 0.0
                    pe = float(parts[39]) if parts[39] else 0.0
                    circ_cap = float(parts[44]) if parts[44] else 0.0
                    total_cap = float(parts[45]) if parts[45] else 0.0
                    limit_up = float(parts[47]) if parts[47] else 0.0
                    limit_down = float(parts[48]) if parts[48] else 0.0
                    vol_ratio = float(parts[49]) if parts[49] else 0.0
                    seal_volume = int(parts[50]) if parts[50] else 0
                    
                    open_chg_pct = round(((open_price - yesterday_close) / yesterday_close * 100), 2) if yesterday_close > 0 else 0.0
                    is_limit_up = (price >= limit_up - 0.01) and (limit_up > 0)
                    is_limit_down = (price <= limit_down + 0.01) and (limit_down > 0)
                    
                    meta = meta_map.get(code, {})
                    quotes.append({
                        'code': code,
                        'full_code': ('SH' if code.startswith('6') else 'SZ') + code,
                        'name': name,
                        'rank': meta.get('rank', 999),
                        'rank_change': meta.get('rank_change', 0),
                        'price': price,
                        'yesterday_close': yesterday_close,
                        'open_price': open_price,
                        'open_chg_pct': open_chg_pct,
                        'chg_pct': chg_pct,
                        'high': high,
                        'low': low,
                        'turnover_rate': turnover_rate,
                        'circ_cap_yi': circ_cap,
                        'total_cap_yi': total_cap,
                        'limit_up': limit_up,
                        'limit_down': limit_down,
                        'is_limit_up': is_limit_up,
                        'is_limit_down': is_limit_down,
                        'vol_ratio': vol_ratio,
                        'seal_volume': seal_volume
                    })
        except Exception as e:
            print(f"获取行情批次异常: {e}")
            
    quotes.sort(key=lambda x: x['rank'])
    return quotes

def fetch_concepts_and_industry(code, full_code):
    """从东财获取个股行业分类与核心题材概念"""
    url = f'https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code={full_code}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            ssbk = data.get('ssbk', [])
            industry = "其他"
            concepts = []
            for b in ssbk:
                b_name = b.get('BOARD_NAME', '')
                b_rank = b.get('BOARD_RANK')
                is_precise = b.get('IS_PRECISE')
                if b_rank == 1 and not industry or industry == "其他":
                    industry = b_name
                if is_precise == '1':
                    if b_name not in ['融资融券', '机构重仓', 'QFII重仓', 'AB股', '题材股', '趋势股']:
                        concepts.append(b_name)
            return industry, concepts[:5]
    except Exception:
        pass
    return "未知行业", []

def filter_and_classify(quotes, regime, cap_min=30.0, cap_max=250.0):
    """
    执行五步战法核心过滤：
    1. 负面降噪：剔除ST、*ST、跌停A杀、严重负面暴雷
    2. 量能匹配：若两市总成交额<2万亿，剔除大盘子(>cap_max)，剔除微盘流动性陷阱(<cap_min)
    3. 保留高辨识度中小盘有效候选
    """
    excluded_list = []
    screened_list = []
    
    for q in quotes:
        name = q['name']
        code = q['code']
        cap = q['total_cap_yi']
        chg = q['chg_pct']
        is_limit_down = q['is_limit_down']
        
        if 'ST' in name or '*ST' in name:
            excluded_list.append({**q, 'exclude_reason': '负面降噪：ST/退市风险标的'})
            continue
            
        if is_limit_down or chg <= -9.5:
            excluded_list.append({**q, 'exclude_reason': '负面降噪：跌停A杀/情绪极度恶化'})
            continue
            
        if not regime['is_high_liquidity']:
            if cap > cap_max:
                excluded_list.append({**q, 'exclude_reason': f'量能不匹配：市场<2万亿存量，大盘中军承接不足（总市值{cap:.1f}亿 > {cap_max}亿上限）'})
                continue
            if cap < cap_min:
                excluded_list.append({**q, 'exclude_reason': f'流动性过滤：微盘市值过小易成流动性陷阱（总市值{cap:.1f}亿 < {cap_min}亿下限）'})
                continue
                
        screened_list.append(q)
        
    return screened_list, excluded_list

def cluster_and_evaluate_setups(screened_stocks):
    """
    4. 概念归拢与去弱留强
    5. 买点形态研判 (分歧低吸 vs 弱转强)
    """
    for s in screened_stocks:
        ind, concs = fetch_concepts_and_industry(s['code'], s['full_code'])
        s['industry'] = ind
        s['concepts'] = concs
        s['main_theme'] = concs[0] if concs else ind
        time.sleep(0.05)
        
    theme_groups = {}
    for s in screened_stocks:
        theme = s['main_theme']
        theme_groups.setdefault(theme, []).append(s)
        
    final_candidates = []
    
    for theme, group in theme_groups.items():
        group.sort(key=lambda x: (
            1 if x['is_limit_up'] else 0,
            x['chg_pct'],
            -x['rank']
        ), reverse=True)
        
        for idx, item in enumerate(group):
            if idx == 0:
                item['dragon_status'] = "👑 题材真龙/身位领先"
            else:
                item['dragon_status'] = "跟随助攻/去弱留强注意风险"
                
            if item['is_limit_up']:
                item['setup_type'] = "🔥 封板涨停·主升龙头"
                item['entry_strategy'] = "次日竞价弱转强抢筹或排板，观察封单与溢价"
            elif item['open_chg_pct'] >= 2.0 and item['chg_pct'] > 3.0:
                item['setup_type'] = "⚡ 弱转强形态"
                item['entry_strategy'] = "竞价超预期高开且开盘快速翻红，逢回踩不破均价线确认转强"
            elif -4.0 <= item['chg_pct'] <= 4.0 and item['turnover_rate'] >= 8.0:
                item['setup_type'] = "🌊 分歧良性整理·低吸区"
                item['entry_strategy'] = "依托5日均线/分时回踩企稳低吸，博弈次日反包或主升延续"
            elif item['chg_pct'] < -4.0:
                item['setup_type'] = "⚠️ 深度分歧洗盘"
                item['entry_strategy'] = "观望止跌信号，严禁左侧盲目抄底，待企稳阳线"
            else:
                item['setup_type'] = "📈 趋势蓄势走强"
                item['entry_strategy'] = "逢5日均线分批低吸布局"
                
            final_candidates.append(item)
            
    final_candidates.sort(key=lambda x: (
        1 if "👑" in x['dragon_status'] else 0,
        1 if x['is_limit_up'] else 0,
        x['chg_pct']
    ), reverse=True)
    
    return final_candidates, theme_groups

def run_scanner(cap_min=30.0, cap_max=250.0):
    print("=" * 80)
    print("🚀 启动 A股人气龙头五步战法自动化筛选器")
    print("=" * 80)
    
    regime = fetch_market_regime()
    print(f"\n【宏观量能定调】")
    print(f"• 沪深两市最新总成交额: {regime['total_turnover_yi']:,.1f} 亿元 (沪市: {regime['sh_turnover_yi']:,.1f} 亿 / 深市: {regime['sz_turnover_yi']:,.1f} 亿)")
    print(f"• 2万亿分水岭判定: {'✅ 增量大牛市 (>2万亿)' if regime['is_high_liquidity'] else '🔻 存量缩量博弈 (<2万亿)'}")
    print(f"• 执行策略导向: {regime['market_style']}")
    print(f"• 市值匹配过滤范围: [{cap_min} 亿 ~ {cap_max} 亿] (严控大盘子权重，聚焦中小盘高弹性)")
    
    print(f"\n【步骤 1: 抓取东方财富实时人气榜前 50】...")
    rankings = fetch_popularity_ranking(50)
    print(f"成功获取 {len(rankings)} 只人气标的。")
    
    quotes = fetch_stock_quotes(rankings)
    print(f"成功获取 {len(quotes)} 只标的实时行情切片。")
    
    print(f"\n【步骤 2 & 3: 执行负面降噪过滤与体量匹配】...")
    screened, excluded = filter_and_classify(quotes, regime, cap_min, cap_max)
    print(f"• 剔除标的数: {len(excluded)} 只 (其中大盘权重/微盘/ST/跌停票)")
    print(f"• 入围中小盘高弹性标的数: {len(screened)} 只")
    
    print(f"\n【步骤 4 & 5: 题材归拢、同位PK与形态择时研判】...")
    final_candidates, theme_groups = cluster_and_evaluate_setups(screened)
    
    print("\n" + "=" * 105)
    print(f"{'代码':<8} {'名称':<8} {'人气':<5} {'现价':<6} {'涨跌幅':<8} {'市值(亿)':<8} {'换手率':<8} {'核心题材':<14} {'形态定位':<14} {'龙头身位'}")
    print("-" * 105)
    for s in final_candidates:
        print(f"{s['code']:<8} {s['name']:<8} #{s['rank']:<4} {s['price']:<6.2f} {s['chg_pct']:>6.2f}% {s['total_cap_yi']:>7.1f} {s['turnover_rate']:>6.1f}% {s['main_theme']:<14} {s['setup_type']:<14} {s['dragon_status']}")
    print("=" * 105)
    
    snapshot = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'regime': regime,
        'screened_count': len(final_candidates),
        'excluded_count': len(excluded),
        'candidates': final_candidates,
        'excluded_examples': excluded[:15]
    }
    
    output_json = os.path.join(DATA_DIR, 'screened_dragons_latest.json')
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 完整筛选结构化数据已写入: {output_json}")
    
    return snapshot

if __name__ == '__main__':
    run_scanner()
