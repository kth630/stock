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

###########################################
# 1. 종목 데이터 준비(기존 로직 그대로)
############################################
# ... (위 코드 전체는 동일, data_dict 생성까지) ...

############################################
# 2. 복리(계좌 단위) 백테스트 함수
############################################
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
            if (not in_pos and row['supertrend_up'] or row['supertrend_up_60'] and
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
                if row['supertrend_down'] and row['supertrend_down_60']:
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


############################################
# 3. 파라미터 그리드 서치
############################################
atr_k_list        = [1.0,2.0, 3.0]
profit_pct_params = [None,0.1,0.2]
ema_list          = [None, 'EMA50', 'EMA100', 'EMA200']

records = []
for ema in ema_list:
    for atr_k in atr_k_list:
        for p_param in profit_pct_params:
            bal, init_cap, fin_cap = mtf_backtest_compound(
                data_dict,
                initial_cash    = 100_000,
                atr_k           = atr_k,
                ema_col         = ema,
                profit_pct_param= p_param
            )
            profit_abs  = fin_cap - init_cap
            profit_rate = (fin_cap / init_cap - 1) * 100
            records.append({
                'ema'        : ema or 'None',
                'atr_k'      : atr_k,
                'tp_param(%)': 'None' if p_param is None else f"{p_param*100:.0f}",
                'init(₩)'    : init_cap,
                'final(₩)'   : fin_cap,
                'profit(₩)'  : profit_abs,
                'profit(%)'  : profit_rate
            })

############################################
# 4. 결과 출력
############################################
print("\n=== 종목당 10만 복리 시뮬레이션 결과 ===")
print("   EMA   | atr_k | TP(%) | 계좌초기 |  계좌최종 |    손익 | 손익률(%)")
print("-"*80)
for r in records:
    print(f"{r['ema']:7} | {r['atr_k']:5} | {r['tp_param(%)']:>6} | "
          f"{r['init(₩)']:10,.0f} | {r['final(₩)']:10,.0f} | "
          f"{r['profit(₩)']:8,.0f} | {r['profit(%)']:10.2f}")
print("-"*80)
