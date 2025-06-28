import sys, os, time
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
import pandas as pd

from apscheduler.schedulers.background import BackgroundScheduler
from indicators import day_data, min_data
from api        import token_api
from strategy   import cal          # 지표 계산 모듈

##############################################################################
# ★ 0) 전역 포지션 상태: {종목코드: True(보유)/False(미보유)} ────────────────
##############################################################################
pos_state: dict[str, bool] = {}     # 프로그램 켜진 동안 유지
##############################################################################


##############################################################################
# 1) 매매 신호 판정 함수 ────────────────────────────────────────────────────
##############################################################################
def judge_signal(df60: pd.DataFrame,
                 df15: pd.DataFrame,
                 in_pos: bool,                 # ★ 현재 보유 여부 인자로 추가
                 atr_k: float = 2.0,
                 ema_col: str | None = None
) -> str:
    """
    최신 15분봉 1개 기준으로
    'BUY' / 'SELL' / 'HOLD' 리턴
    - in_pos=True  → 이미 보유 중 (BUY 금지, SELL만 가능)
    - in_pos=False → 미보유 (SELL 금지, BUY만 가능)
    """

    # 정렬·결측치 보정
    df60.sort_values('datetime', inplace=True); df60.ffill(inplace=True)
    df15.sort_values('datetime', inplace=True); df15.ffill(inplace=True)

    # supertrend bool 처리
    for c in ('supertrend_up', 'supertrend_down'):
        if c in df60: df60[c] = df60[c].fillna(False).astype(bool)
        if c in df15: df15[c] = df15[c].fillna(False).astype(bool)

    # 60분 정보 머지
    merge_cols = ['datetime', 'supertrend_up', 'supertrend_down']
    if 'ATR14' in df60 and atr_k: merge_cols.append('ATR14')
    if ema_col and ema_col in df60: merge_cols.append(ema_col)

    df15 = pd.merge_asof(df15, df60[merge_cols], on='datetime',
                         direction='backward', suffixes=('', '_60'))

    last = df15.iloc[-1]
    price = last['Close']

    # ── 조건 계산 ──
    buy_cond  = (not in_pos and
                 (last['supertrend_up'] or last['supertrend_up_60']))
    sell_cond = (in_pos and
                 (last['supertrend_down'] or last['supertrend_down_60']))

    if ema_col:
        ema_ok = price > last.get(f'{ema_col}_60', 0)
        buy_cond &= ema_ok          # BUY 시 추가 필터

    if buy_cond:
        return 'BUY'
    elif sell_cond:
        return 'SELL'
    else:
        return 'HOLD'


##############################################################################
# 2) 데이터 수집 + 지표 계산 ────────────────────────────────────────────────
##############################################################################
def fetch_and_calc(code: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    frames = {}
    for scope in (60, 15):
        params_min = {
            'stk_cd'       : code,
            'tic_scope'    : str(scope),
            'upd_stkpc_tp' : '1'
        }
        resp = min_data.fn_ka10080(token=token_api.token, data=params_min)
        df   = min_data.make_trans_df(resp)

        df = cal.cal_15min(df) if scope == 15 else cal.cal_60min(df)
        frames[scope] = df
    return frames[60], frames[15]


##############################################################################
# 3) 스케줄러가 호출하는 작업 ───────────────────────────────────────────────
##############################################################################
def job_run(codes: List[str],
            atr_k: float = 2.0,
            ema_col: str | None = None):

    now = datetime.now()
    print(f"\n[{now:%Y-%m-%d %H:%M}] === Signal Check ===")

    for code in codes:
        try:
            df60, df15 = fetch_and_calc(code)

            # ★ 현재 포지션 상태 가져오기 (default=False)
            in_pos = pos_state.get(code, False)

            sig = judge_signal(df60.reset_index(),
                               df15.reset_index(),
                               in_pos,
                               atr_k=atr_k,
                               ema_col=ema_col)

            # ── 출력 ──
            status = "LONG" if in_pos else "FLAT"
            print(f"• {code}: {sig:<4}  (현재:{status})")

            # ── ★ 상태 업데이트 ──
            if   sig == "BUY":  pos_state[code] = True
            elif sig == "SELL": pos_state[code] = False

        except Exception as e:
            print(f"⚠️ {code} 데이터/판정 실패: {e}")


##############################################################################
# 4) 스케줄러 설정 ─────────────────────────────────────────────────────────
##############################################################################
def main():
    codes = input("모니터링 종목코드(공백 구분) 입력: ").split()
    for c in codes:                # ★ pos_state 초기화
        pos_state.setdefault(c, False)

    print("실시간 신호 판단 시작… Ctrl-C 로 종료")

    scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    scheduler.add_job(job_run,
                      'cron',
                      minute='0,15,30,45',
                      args=[codes],
                      id='signal_job',
                      misfire_grace_time=120)

    # 원하는 경우 첫 실행 즉시 1회 평가
    job_run(codes)

    scheduler.start()

    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("종료되었습니다.")


if __name__ == "__main__":
    main()
