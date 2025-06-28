import sys, os
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
from indicators import day_data,min_data
from api import token_api
import pandas as pd
from strategy import cal
from datetime import datetime
from typing import Dict, Tuple, List


params_min = {
	'stk_cd': '', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
	'tic_scope': '', # 틱범위 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
	'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}
	
params_day = {
		'stk_cd': '', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'base_dt': datetime.today().strftime('%Y%m%d'), # 기준일자 YYYYMMDD
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}



code = input('종목코드를 입력하시오: ')
codes = code.split()
count = len(codes)
data_dict = {}

for code in codes:
    if count == len(codes):
        print(f'종목 수: {count}')
    try:
        # 분봉 설정
        params_min['stk_cd'] = code
        minitue = [15, 60]
        min_cal_dfs = {}
        for i in minitue:
            params_min['tic_scope'] = str(i)
            try:
                response = min_data.fn_ka10080(token=token_api.token, data=params_min)
                min_df = min_data.make_trans_df(response)
                if i == 15:
                    min_df = cal.cal_15min(min_df)
                elif i == 60:
                    min_df = cal.cal_60min(min_df)
                min_cal_dfs[i] = min_df
            except Exception as e:
                print(f'⚠️ {code} {i}분봉 처리 실패: {e} (이 주기 건너뜀)')
                min_cal_dfs[i] = None

        # 필수 데이터(15/60분봉)가 모두 있으면 data_dict에 저장
        if min_cal_dfs.get(15) is not None and min_cal_dfs.get(60) is not None:
            data_dict[code] = (min_cal_dfs[60].reset_index(), min_cal_dfs[15].reset_index())
            print(f'저장완{count}')
        else:
            print(f'⚠️ {code} 저장 실패 (필수 분봉 데이터 부족)')
    except Exception as e:
        print(f'⚠️ {code} 전체 처리 실패: {e} (이 종목 건너뜀)')
    count -= 1

print(f'{len(data_dict)}개 저장 끝')

def mtf_backtest(
    data_dict: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] ,
    invest_per_trade: float = 100_000,   # ★ 추가: 고정 투자금
    atr_k: float = 1.5,
    ema_col: str | None = None,
    profit_pct: float = 0.10
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, float], float]:

    trades_dict, returns_dict = {}, {}

    for ticker, (df60_raw, df15_raw) in data_dict.items():
        # … (전처리/merge 부분 동일) …
        # ── 1) 정렬 & 전처리 ─────────────────────────────────────────
        df60 = df60_raw.sort_values('datetime').copy()
        df15 = df15_raw.sort_values('datetime').copy()

        for col in ('supertrend_up', 'supertrend_down'):
            if col in df60: df60[col] = df60[col].fillna(False).astype(bool)
            if col in df15: df15[col] = df15[col].fillna(False).astype(bool)

        merge_cols = ['datetime', 'supertrend_up', 'supertrend_down']
        if atr_k is not None and 'ATR14' in df60: merge_cols.append('ATR14')
        if ema_col and ema_col in df60:          merge_cols.append(ema_col)

        # 직전 60 분봉 신호를 15 분봉에 매핑
        df15 = pd.merge_asof(df15, df60[merge_cols],
                             on='datetime', direction='backward',
                             suffixes=('', '_60'))

        in_pos = False
        entry = stop = target = None
        entry_time = qty = invest = 0
        logs: List[dict] = []

        for _, row in df15.iterrows():
            t, cls = row['datetime'], row['Close']

            # ── 진입 ──
            if (not in_pos) and row['supertrend_up'] and row['supertrend_up_60']:
                qty = int(invest_per_trade // cls)        # ← 10 만원으로 살 수 있는 주식 수
                if qty == 0:
                    continue                              # 주가가 너무 비싸면 스킵
                invest      = qty * cls                   # 실제 투입금
                entry       = cls
                entry_time  = t
                in_pos      = True

                atr = row.get('ATR14')
                if atr_k and atr:
                    stop   = entry - atr_k * atr
                    target = entry + atr_k * atr
                if profit_pct:
                    target = min(target or 1e18, entry * (1 + profit_pct))
                continue

            # ── 청산 ──
            if in_pos:
                reason = None
                if row['supertrend_down'] and row['supertrend_down_60']:
                    reason = 'Supertrend down'
                if stop   and cls <= stop:   reason = 'Stop-loss ATR'
                if target and cls >= target: reason = 'Take-profit'
                if ema_col and cls < row.get(ema_col, cls + 1):
                    reason = f'EMA({ema_col}) cross'

                if reason:
                    final_val = qty * cls
                    pnl       = final_val - invest
                    pnl_pct   = pnl / invest
                    logs.append(dict(entry_time=entry_time, exit_time=t,
                                     entry_price=entry, exit_price=cls,
                                     qty=qty, invest=invest,
                                     final_value=final_val, pnl=pnl,
                                     pnl_pct=pnl_pct, exit_reason=reason))
                    in_pos = False

        # 데이터 끝 청산
        if in_pos:
            cls        = df15.iloc[-1]['Close']
            final_val  = qty * cls
            pnl        = final_val - invest
            pnl_pct    = pnl / invest
            logs.append(dict(entry_time=entry_time, exit_time=df15.iloc[-1]['datetime'],
                             entry_price=entry, exit_price=cls,
                             qty=qty, invest=invest,
                             final_value=final_val, pnl=pnl,
                             pnl_pct=pnl_pct, exit_reason='End of data'))

        trades = pd.DataFrame(logs)
        trades_dict[ticker] = trades

        # ── 종목별 누적 수익률 = 총 손익 / 총 투자금 ──
        if not trades.empty:
            total_pnl    = trades['pnl'].sum()
            total_invest = trades['invest'].sum()
            returns_dict[ticker] = total_pnl / total_invest
        else:
            returns_dict[ticker] = 0.0

    total_return = sum(returns_dict.values()) / max(len(returns_dict), 1)
    return trades_dict, returns_dict, total_return
atr_k_list = [1.0, 1.5, 2.0]
profit_pct_list = [0.05, 0.10, 0.15, None]  # None=익절 없음
ema_list = [None,'EMA50', 'EMA100', 'EMA200']
results = []
for ema in ema_list:
    for atr_k in atr_k_list:
        for profit_pct in profit_pct_list:
            # 백테스트 실행
            trades_dict, returns_dict, total_return = mtf_backtest(
                data_dict, atr_k=atr_k, profit_pct=profit_pct,ema_col=ema
            )
            # 전체 실현 손익, 투자금, 평균 수익률 계산
            total_profit = 0
            total_invest = 0
            all_trades = 0
            for trades in trades_dict.values():
                if trades.empty or 'pnl' not in trades.columns:
                    continue
                total_profit += trades['pnl'].sum()
                total_invest += trades['invest'].sum()
                all_trades += len(trades)
            avg_return = (total_profit / total_invest) if total_invest > 0 else 0
            # 결과 저장
            results.append({
                'atr_k': atr_k,
                'profit_pct': profit_pct,
                'total_profit': total_profit,
                'total_invest': total_invest,
                'avg_return': avg_return,
                'trades': all_trades
            })

# 결과 표 출력
print("\n===== 파라미터 그리드 결과 =====")
print("  atr_k | profit_pct | 거래수 | 총수익(원) | 총투자금(원) | 평균수익률(%)")
print("-"*70)
for r in results:
    profit_pct_disp = f"{r['profit_pct']:.2%}" if r['profit_pct'] is not None else "None"
    print(f"{r['atr_k']:7} | {profit_pct_disp:10} | {r['trades']:6} | {r['total_profit']:10,.0f} | {r['total_invest']:12,.0f} | {r['avg_return']*100:10.4f}")
print("-"*70)
