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





def mtf_backtest_compound(
    data_dict: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] ,
    initial_cash: float = 100_000,
    atr_k: float = 1.5,
    ema_col: str | None = None,
    profit_pct_param: float | None = 0.10
):
    balances = {}
    for ticker, (df60_raw, df15_raw) in data_dict.items():
        df60 = df60_raw.sort_values('datetime').copy()
        df15 = df15_raw.sort_values('datetime').copy()
        for c in ('supertrend_up', 'supertrend_down'):
            if c in df60: df60[c] = df60[c].fillna(False).astype(bool)
            if c in df15: df15[c] = df15[c].fillna(False).astype(bool)

        merge_cols = ['datetime', 'supertrend_up', 'supertrend_down']
        if 'ATR14' in df60 and atr_k: merge_cols.append('ATR14')
        if ema_col and ema_col in df60: merge_cols.append(ema_col)

        df15 = pd.merge_asof(df15, df60[merge_cols], on='datetime',
                             direction='backward', suffixes=('', '_60'))

        # === 계좌 상태 초기화 ===
        cash, stock = initial_cash, 0
        in_pos = False
        stop = target = qty = 0

        for _, row in df15.iterrows():
            price = row['Close']

            # ── 진입 ──
            if (not in_pos and (row['supertrend_up'] or row['supertrend_up_60']) and
                (ema_col is None or price > row.get(f"{ema_col}_60", 0))):
                qty = int(cash // price)
                if qty == 0:
                    continue
                stock += qty
                cash  -= qty * price
                in_pos = True

                atr = row.get('ATR14')
                if atr_k and atr:
                    stop   = price - atr_k * atr
                    target = price + atr_k * atr
                else:
                    stop = target = None
                if profit_pct_param is not None:
                    target = min(target or 1e18, price*(1+profit_pct_param))
                continue

            # ── 청산 ──
            if in_pos:
                exit_flag = False
                if row['supertrend_down'] or row['supertrend_down_60']:
                    exit_flag = True
                elif stop   and price <= stop:
                    exit_flag = True
                elif target and price >= target:
                    exit_flag = True

                if exit_flag:
                    cash  += stock * price
                    stock  = 0
                    in_pos = False

        # ── 종료 시 잔여 주식 현금화 ──
        if stock:
            cash += stock * df15.iloc[-1]['Close']
            stock = 0
        balances[ticker] = cash

    total_init  = len(balances) * initial_cash
    total_final = sum(balances.values())
    return balances, total_init, total_final



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







cash = 300_000
balances, total_init, total_final = mtf_backtest_compound(
    data_dict,
    initial_cash      = cash,
    atr_k             = 2.0,
    ema_col           = None,     # ← 'EMA200' 등으로 교체 가능
    profit_pct_param  = None      # 고정 TP 끔
)

# ---------------------------------------------
# 2) 종목별 결과 테이블 출력
# ---------------------------------------------
print("\n===== 종목별 계좌 잔고 결과 =====")
print("종목코드 | 최종 잔고(₩) | 손익(₩) | 손익률(%)")
print("-" * 45)

for ticker, final_cash in balances.items():
    profit_abs  = final_cash - cash
    profit_rate = (final_cash / cash - 1) * 100
    print(f"{ticker:8} | {final_cash:12,.0f} | {profit_abs:8,.0f} | {profit_rate:9.2f}")

print("-" * 45)
print(f"전체 초기 자본 : {total_init:,.0f} 원")
print(f"전체 최종 자본 : {total_final:,.0f} 원")
print(f"전체 손익      : {total_final - total_init:,.0f} 원")
print(f"전체 손익률    : {(total_final / total_init - 1) * 100:,.2f} %")    