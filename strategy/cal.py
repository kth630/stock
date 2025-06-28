import sys, os
import pandas as pd
import pandas_ta as ta 
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
from indicators import min_data,day_data
from api import token_api
from datetime import datetime

def cal_5min(min_df):
    """
    지표계산
    EMA34,RSI14,ATR14,VWAP
    """
    ## EMA34 계산
    min_df['EMA34'] = min_df['Close'].ewm(span=34, adjust=False).mean()
    
    ## RSI14 계산
    # 1) 종가 차분(delta)
    delta = min_df['Close'].diff()

    # 2) 상승분(gain)과 하락분(loss) 분리
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # 3) 평균 상승·하락 계산 (14기간)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()

    # 4) 상대강도(Relative Strength)와 RSI 공식 적용
    rs = avg_gain / avg_loss
    min_df['RSI14'] = 100 - (100 / (1 + rs))
    
    ## ATR14 계산
    # 1) True Range(TR) 계산
    hl = min_df['High'] - min_df['Low']
    hc = (min_df['High'] - min_df['Close'].shift()).abs()
    lc = (min_df['Low']  - min_df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    # 2) ATR14 (14기간 단순이동평균)
    min_df['ATR14'] = tr.rolling(window=14).mean()

    ## VWAP 계산
    # 1) 전형 가격(Typical Price) 계산
    typical = (min_df['High'] + min_df['Low'] + min_df['Close']) / 3

    # 2) TPV (Typical Price × Volume)
    min_df['TPV'] = typical * min_df['Volume']

    # 3) 당일 누적 TPV와 누적 Volume 계산
    cum_tpv  = min_df.groupby(min_df.index.date)['TPV'].cumsum()
    cum_vol  = min_df.groupby(min_df.index.date)['Volume'].cumsum()

    # 4) VWAP 구하기
    min_df['VWAP'] = cum_tpv / cum_vol

    
    return min_df

def cal_15min(min_df):
    """
    지표계산
    EMA5/20/50/55, ATR14, ADX14, RSI14, 불린저밴드,Supertrend
    """
    # EMA5/20/50/55 계산
    min_df['EMA5'] = min_df['Close'].ewm(span=5, adjust=False).mean()
    min_df['EMA20'] = min_df['Close'].ewm(span=20, adjust=False).mean()
    min_df['EMA50'] = min_df['Close'].ewm(span=50, adjust=False).mean()
    min_df['EMA55'] = min_df['Close'].ewm(span=55, adjust=False).mean()

    # RSI14 계산
    delta = min_df['Close'].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    min_df['RSI14'] = 100 - (100 / (1 + rs))
    
    # True Range(TR) 계산 (ATR 용)
    hl = min_df['High'] - min_df['Low']
    hc = (min_df['High'] - min_df['Close'].shift()).abs()
    lc = (min_df['Low'] - min_df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    
    # ATR14 계산
    min_df['ATR14'] = tr.rolling(window=14).mean()
    
    # 방향성 지표(Directional Movement)
    up_move = min_df['High'].diff()
    down_move = min_df['Low'].shift() - min_df['Low']
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    
    # DI (Directional Indicator)
    plus_di = 100 * (plus_dm.rolling(window=14).mean() / min_df['ATR14'])
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / min_df['ATR14'])
    
    # DX (Directional Index) 및 ADX (Average DX)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    min_df['ADX14'] = dx.rolling(window=14).mean()

    # 불린저밴드 계산
    bb_mid_15 = min_df['Close'].rolling(window=20).mean()
    bb_std_15 = min_df['Close'].rolling(window=20).std()
    min_df['BB_mid']   = bb_mid_15
    min_df['BB_upper'] = bb_mid_15 + 2 * bb_std_15
    min_df['BB_lower'] = bb_mid_15 - 2 * bb_std_15
    min_df['BB_width'] = min_df['BB_upper'] - min_df['BB_lower']
    min_df['BB_squeeze'] = min_df['BB_width'] == min_df['BB_width'].rolling(window=20).min()

    # 거래량평균(20봉)
    min_df['vol_avg20'] = min_df['Volume'].rolling(window=20).mean()

    # Volume Weighted Average Price (VWAP) 계산
    typical = (min_df['High'] + min_df['Low'] + min_df['Close']) / 3
    min_df['TPV'] = typical * min_df['Volume']
    # 당일 날짜 기준 누적 TPV, 누적 Volume
    cum_tpv = min_df.groupby(min_df.index.date)['TPV'].cumsum()
    cum_vol = min_df.groupby(min_df.index.date)['Volume'].cumsum()
    min_df['VWAP'] = cum_tpv / cum_vol

    ## Supertrend 계산
    # Supertrend(ATR 14, factor 3) 계산
    supertrend = ta.supertrend(high=min_df['High'], low= min_df['Low'], close=min_df['Close'], length=14, multiplier=3)
    
    # 결과 컬럼: 'SUPERT_14_3.0' (supertrend), 'SUPERTd_14_3.0' (방향: 1(Up), -1(Down))
    min_df = min_df.join(supertrend)

    # 상승장/하락장 구분 (진입 신호/청산 신호로 사용)
    min_df['supertrend_up'] = min_df['SUPERTd_14_3.0'] == 1
    min_df['supertrend_down'] = min_df['SUPERTd_14_3.0'] == -1
    
    return min_df

def cal_60min(min_df):
    """
    지표계산 (1시간봉)
    - EMA50, EMA100, EMA200
    - RSI14
    - ATR14
    + ADX14, MACD 히스토그램, Bollinger Bands 추가
    - Supertend 
    """
    # 1) EMA50,EMA100, EMA200 계산
    min_df['EMA50'] = min_df['Close'].ewm(span=50, adjust=False).mean()
    min_df['EMA100'] = min_df['Close'].ewm(span=100, adjust=False).mean()
    min_df['EMA200'] = min_df['Close'].ewm(span=200, adjust=False).mean()

    # 2) RSI14 계산 (필요 시 60분봉 모멘텀 확인 용)
    delta   = min_df['Close'].diff()
    gain    = delta.clip(lower=0)
    loss    = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    min_df['RSI14'] = 100 - (100 / (1 + rs))

    # 3) ATR14 계산 (ATR 기반 손절/익절용)
    hl = min_df['High'] - min_df['Low']
    hc = (min_df['High'] - min_df['Close'].shift()).abs()
    lc = (min_df['Low'] - min_df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    min_df['ATR14'] = tr.rolling(window=14).mean()

    # 4) ADX14 계산 (추세 강도 확인)
    up_move   = min_df['High'].diff()
    down_move = min_df['Low'].shift() - min_df['Low']
    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di  = 100 * (plus_dm.rolling(window=14).mean() / min_df['ATR14'])
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / min_df['ATR14'])
    dx       = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    min_df['ADX14'] = dx.rolling(window=14).mean()

    # 5) MACD 히스토그램 계산 (모멘텀 확인)
    ema12_60 = min_df['Close'].ewm(span=12, adjust=False).mean()
    ema26_60 = min_df['Close'].ewm(span=26, adjust=False).mean()
    min_df['MACD_60']    = ema12_60 - ema26_60
    min_df['MACDsig_60'] = min_df['MACD_60'].ewm(span=9, adjust=False).mean()
    min_df['MACDh_60']   = min_df['MACD_60'] - min_df['MACDsig_60']

    # 6) 볼린저 밴드 계산 (20기간, ±2σ)
    bb_mid_60 = min_df['Close'].rolling(window=20).mean()
    bb_std_60 = min_df['Close'].rolling(window=20).std()
    min_df['BB_mid_60']   = bb_mid_60
    min_df['BB_upper_60'] = bb_mid_60 + 2 * bb_std_60
    min_df['BB_lower_60'] = bb_mid_60 - 2 * bb_std_60
    min_df['BB_width_60'] = min_df['BB_upper_60'] - min_df['BB_lower_60']
    min_df['BB_squeeze_60'] = min_df['BB_width_60'] == min_df['BB_width_60'].rolling(window=20).min()

    ## Supertrend 계산
    # Supertrend(ATR 14, factor 3) 계산
    supertrend = ta.supertrend(high=min_df['High'], low= min_df['Low'], close=min_df['Close'], length=14, multiplier=3)
    
    # 결과 컬럼: 'SUPERT_14_3.0' (supertrend), 'SUPERTd_14_3.0' (방향: 1(Up), -1(Down))
    min_df = min_df.join(supertrend)

    # 상승장/하락장 구분 (진입 신호/청산 신호로 사용)
    min_df['supertrend_up'] = min_df['SUPERTd_14_3.0'] == 1
    min_df['supertrend_down'] = min_df['SUPERTd_14_3.0'] == -1

    return min_df



def cal_day(day_df):
    """
    지표계산 (일봉)
    - SMA50, SMA200
    - MACD(12,26,9), RSI14
    + EMA50, EMA100, ADX14, Bollinger Bands(일봉), Volume Avg(20일) 추가
    """
    day_df = day_df.copy()

    # 1) SMA50, SMA200
    day_df['SMA50'] = day_df['Close'].rolling(window=50).mean()
    day_df['SMA200'] = day_df['Close'].rolling(window=200).mean()

    # 2) EMA50, EMA100 (장기 추세 민감도 높이기)
    day_df['EMA50']  = day_df['Close'].ewm(span=50, adjust=False).mean()
    day_df['EMA100'] = day_df['Close'].ewm(span=100, adjust=False).mean()

    # 3) MACD (12,26,9)
    ema12 = day_df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = day_df['Close'].ewm(span=26, adjust=False).mean()
    day_df['MACD']    = ema12 - ema26
    day_df['MACDsig'] = day_df['MACD'].ewm(span=9, adjust=False).mean()
    day_df['MACDh']   = day_df['MACD'] - day_df['MACDsig']

    # 4) RSI14 (일봉 모멘텀 확인)
    delta = day_df['Close'].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    day_df['RSI14'] = 100 - (100 / (1 + rs))

    # 5) ATR14 (일봉)
    hl = day_df['High'] - day_df['Low']
    hc = (day_df['High'] - day_df['Close'].shift()).abs()
    lc = (day_df['Low'] - day_df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    day_df['ATR14'] = tr.rolling(window=14).mean()

    # 6) ADX14 (일봉 추세 강도)
    up_move   = day_df['High'].diff()
    down_move = day_df['Low'].shift() - day_df['Low']
    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di  = 100 * (plus_dm.rolling(window=14).mean() / day_df['ATR14'])
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / day_df['ATR14'])
    dx       = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    day_df['ADX14'] = dx.rolling(window=14).mean()

    # 7) 볼린저 밴드 (20일, ±2σ)
    bb_mid_day = day_df['Close'].rolling(window=20).mean()
    bb_std_day = day_df['Close'].rolling(window=20).std()
    day_df['BB_mid_1d']   = bb_mid_day
    day_df['BB_upper_1d'] = bb_mid_day + 2 * bb_std_day
    day_df['BB_lower_1d'] = bb_mid_day - 2 * bb_std_day
    day_df['BB_width_1d'] = day_df['BB_upper_1d'] - day_df['BB_lower_1d']
    day_df['BB_squeeze_1d'] = day_df['BB_width_1d'] == day_df['BB_width_1d'].rolling(window=20).min()

    # 8) 거래량 평균 (20일)
    day_df['vol_avg20_1d'] = day_df['Volume'].rolling(window=20).mean()

    return day_df





if __name__ == '__main__':
    
    """
    잘 되는지 확인용
    """

    params_min = {
	'stk_cd': '005930', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
	'tic_scope': '', # 틱범위 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
	'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}

    params_day = {
		'stk_cd': '005930', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'base_dt': datetime.today().strftime('%Y%m%d'), # 기준일자 YYYYMMDD
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}
   
    # 3분봉 지표계산
    params_min['tic_scope'] = '3'
    response = min_data.fn_ka10080(token=token_api.token, data=params_min)
    min_df = min_data.make_trans_df(response)
    min3_df = cal_5min(min_df.copy())   
    
    # 15분봉 지표계산
    params_min['tic_scope'] = '15'
    response = min_data.fn_ka10080(token=token_api.token, data=params_min)
    min_df = min_data.make_trans_df(response)
    min15_df = cal_15min(min_df.copy()) 

    # 60분봉 지표계산
    params_min['tic_scope'] = '60'
    response = min_data.fn_ka10080(token=token_api.token, data=params_min)
    min_df = min_data.make_trans_df(response)
    min60_df = cal_60min(min_df.copy()) 

    # 일봉 지표계산
    response = day_data.fn_ka10081(token=token_api.token, data=params_day)
    day_df = day_data.make_day_df(response)
    day_cal_df = cal_day(day_df)


    print(f'15분 지표:{list(min15_df.columns)}\n')
    print(f'60분 지표{list(min60_df.columns)}\n')
    print(f'1일 지표:{list(day_cal_df.columns)}')
    # print(min3_df.tail(50))
    # print(min15_df.tail(20))
    # print(min60_df.tail(5))
    # print(day_cal_df.tail(5))

  