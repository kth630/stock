import sys, os
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
import requests
import json
from api import token_api
import pandas as pd


# 주식분봉차트조회요청
def fn_ka10080(token, data, cont_yn='', next_key=''):
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
		'api-id': 'ka10080', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)
	return response


# 데이터프레임 생성
def make_trans_df(response):
	df = pd.DataFrame(response.json()['stk_min_pole_chart_qry'])
	df = df[['cntr_tm','cur_prc', 'high_pric', 'low_pric', 'trde_qty', 'open_pric']]
	min_df = df.copy()
	# 부호 제거 및 숫자형 변환
	for col in ['cur_prc', 'high_pric', 'low_pric', 'open_pric']:
		min_df[col] = min_df[col].astype(str).str.replace('+', '').str.replace('-', '').astype(float)
	min_df['trde_qty'] = min_df['trde_qty'].astype(float)

	
	min_df.rename(columns={
	    'cntr_tm':    'datetime',
	    'open_pric':  'Open',
	    'high_pric':  'High',
	    'low_pric':   'Low',
	    'cur_prc':    'Close',
	    'trde_qty':   'Volume'
	},inplace=True)

	# 1) datetime 컬럼을 datetime 타입으로 변환
	min_df['datetime'] = pd.to_datetime(min_df['datetime'], format='%Y%m%d%H%M%S')
	
	# 2) datetime을 인덱스로 설정
	min_df.set_index('datetime', inplace=True)
	
	# 3) 과거→최신 오름차순 정렬
	min_df.sort_index(ascending=True, inplace=True)
	return min_df

# params = {
# 	'stk_cd': '414270', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
# 	'tic_scope': '15', # 틱범위 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
# 	'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
# 	}	



# response = fn_ka10080(token=token_api.token, data=params)
# min_df = make_trans_df(response)



    
# 실행 구간
if __name__ == '__main__':
	"""
	차트 데이터 확인용
	"""
	params = {
	'stk_cd': '414270', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
	'tic_scope': '15', # 틱범위 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
	'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}	
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = token_api.token # 접근토큰

	# 2. 호출
	response = fn_ka10080(token=MY_ACCESS_TOKEN,data=params)
	

	# 3. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

	next_key = response.headers.get('next-key')
	cont_yn = response.headers.get('cont-yn')
	# 필요시 이전 데이터 호출, 0이면 호출 안함 그 외는 호출, 두 번째 숫자는 호출 횟수 결정
	ask_n = list(map(int, input().split()))
	if ask_n[0]:
		for i in range(ask_n[1]):
			response = fn_ka10080(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key=next_key)
			next_key = response.headers.get('next-key')
			cont_yn = response.headers.get('cont-yn')
			for k in range(len(response.json()['stk_min_pole_chart_qry'])):
				print(response.json()['stk_min_pole_chart_qry'][k]["cntr_tm"])   # 해당날짜만 출력
	else: 
		print('no more response')
		min_df = make_trans_df(response)
		print(min_df.tail())








