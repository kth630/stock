import sys, os
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
import requests
import json
from api import token_api
import pandas as pd
from datetime import datetime


# 주식일봉차트조회요청
def fn_ka10081(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/chart'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10081', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	return response
	

	


# 데이터프레임으로 변환
def make_day_df(response):
	df = pd.DataFrame(response.json()['stk_dt_pole_chart_qry'])
	df = df[['dt','cur_prc', 'high_pric', 'low_pric', 'trde_qty', 'open_pric']]
	day_df = df.copy()
	# 부호 제거 및 숫자형 변환
	for col in ['cur_prc', 'high_pric', 'low_pric', 'open_pric']:
		day_df[col] = day_df[col].astype(str).str.replace('+', '').str.replace('-', '').astype(float)
	day_df['trde_qty'] = day_df['trde_qty'].astype(float)

	
	day_df.rename(columns={
	    'dt':    'date',
	    'open_pric':  'Open',
	    'high_pric':  'High',
	    'low_pric':   'Low',
	    'cur_prc':    'Close',
	    'trde_qty':   'Volume'
	},inplace=True)

	# 1) datetime 컬럼을 datetime 타입으로 변환
	day_df['date'] = pd.to_datetime(day_df['date'], format='%Y%m%d')
	
	# 2) datetime을 인덱스로 설정
	day_df.set_index('date', inplace=True)
	
	# 3) 과거→최신 오름차순 정렬
	day_df.sort_index(ascending=True, inplace=True)
	return day_df




# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = token_api.token# 접근토큰

	# 2. 요청 데이터
	params = {
		'stk_cd': '005930', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'base_dt': datetime.today().strftime('%Y%m%d'), # 기준일자 YYYYMMDD
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}

	# 3. API 실행
	response = fn_ka10081(token=MY_ACCESS_TOKEN, data=params)
	day_df = make_day_df(response)
	print(day_df.tail())
	


	
