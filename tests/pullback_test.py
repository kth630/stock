
import sys, os
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
from indicators import day_data,min_data
from api import token_api
import pandas as pd
from strategy import pullback_cal
from datetime import datetime


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
# 일봉설정
params_day['stk_cd'] = code
response = day_data.fn_ka10081(token=token_api.token, data=params_day)
day_df = day_data.make_day_df(response)
day_cal_df = pullback_cal.day_cal(day_df)

# 분봉 설정
params_min['stk_cd'] = code
min = [5,15]
min_cal_dfs = {}
for i in min:
    params_min['tic_scope'] = str(i)
    response = min_data.fn_ka10080(token=token_api.token, data=params_min)
    min_df = min_data.make_trans_df(response)
    min_df = pullback_cal.min_cal(min_df)
    min_cal_dfs[i] = min_df

min5_cal_df = min_cal_dfs[5]
min15_cal_df = min_cal_dfs[15]
 



# day_cal_df: 일별 지표 계산 끝난 DataFrame
# 인덱스는 날짜, 컬럼에 'Close','EMA20','EMA60','Volume','Vol_MA20' 포함

today = day_cal_df.index[-1]    # 가장 최신 날짜
row   = day_cal_df.loc[today]   # 오늘 데이터 한 줄 꺼내기

# 1) 추세 & 물량 체크
is_trend_up = (row['Close'] > row['EMA20']) and (row['EMA20'] > row['EMA60'])
is_big_vol  = row['Volume'] > row['Vol_MA20'] * 1.5

if is_trend_up and is_big_vol:
    print(f"{today} ✅ 매매 가능일입니다 (추세·물량 OK)")
else:
    print(f"{today} ❌ 진입 조건 불충분합니다")


# c1 = min5_cal_df['Pullback_pct']<0
# c2 = min5_cal_df['Close'] <= min5_cal_df['BB_mid']              # 볼린저 하단 터치
# c3 = min5_cal_df['Close'] >  min5_cal_df['EMA5']                   # EMA5 위에서 반등
# c4 = min5_cal_df['Volume'] > min5_cal_df['Vol_MA20'] * 1.5         # 물량 동반 반등
# signals5 = min5_cal_df[c1&c2&c3&c4]
# print(c1.sum())
# print(c2.sum())
# print(c3.sum())
# print(c4.sum())


m_better = (
    (day_cal_df['Close'] > day_cal_df['EMA20']) &
    ((day_cal_df['EMA20'] - day_cal_df['EMA60']) / day_cal_df['EMA60'] > -0.01) &
    (day_cal_df['Volume'] > day_cal_df['Vol_MA20'] * 1.1)
)
print(day_cal_df[m_better])