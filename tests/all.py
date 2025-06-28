
import sys, os
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
from indicators import day_data,min_data
from api import token_api
import pandas as pd
from strategy import cal
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
codes =code.split()
count = len(codes)
for code in codes:
    print(count)
    count += -1
    # 분봉 설정
    params_min['stk_cd'] = code
    min = [5,15,60]
    min_cal_dfs = {}
    for i in min:
        params_min['tic_scope'] = str(i)
        response = min_data.fn_ka10080(token=token_api.token, data=params_min)
        min_df = min_data.make_trans_df(response)
        if i == 5:
            min_df =cal.cal_5min(min_df)
        elif i == 15:
             min_df =cal.cal_15min(min_df)
        elif i == 60:
            min_df =cal.cal_60min(min_df)

        min_cal_dfs[i] = min_df

    min5_cal_df = min_cal_dfs[5]
    min15_cal_df = min_cal_dfs[15]
    min60_cal_df = min_cal_dfs[60]
    # print(min5_cal_df.tail())
    # print(min15_cal_df.tail())
    # print(min60_cal_df.tail())



    # 일봉 설정
    params_day['stk_cd'] = code
    response = day_data.fn_ka10081(token=token_api.token, data=params_day)
    day_df = day_data.make_day_df(response)
    day_cal_df = cal.cal_day(day_df)


    # min5_cal_df.to_csv(f'{code}_min_5_df.csv')
    min15_cal_df.to_csv(f'{code}_min_15_df.csv')
    #min60_cal_df.to_csv(f'{code}_min_60_df.csv')
    #day_cal_df.to_csv(f'{code}_day_cal_df.csv')
    #print(f'저장완{count}')
    #print(min15_cal_df.columns,'\n',min60_cal_df.columns)


