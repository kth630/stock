import sys, os
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..')))
from indicators import day_data,min_data
from api import token_api
import pandas as pd

def day_cal(df):
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()

    # 2) ATR14
    high_low = df['High'] - df['Low']
    high_pc  = (df['High'] - df['Close'].shift(1)).abs()
    low_pc   = (df['Low']  - df['Close'].shift(1)).abs()
    df['TR'] = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)

    df['ATR14'] = df['TR'].rolling(window=14, min_periods=1).mean()
    df['BB_mid'] = df['Close'].rolling(window=20).mean()
    df['BB_std'] = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']

    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

    df['Pullback_%'] = (df['Close'] - df['Close'].rolling(window=20).max()) / df['Close'].rolling(window=20).max()
    df.drop(columns=['TR','BB_std'], inplace=True)


    return df



def min_cal(df):
    """
    intraday df: Datetime 인덱스, ['Open','High','Low','Close','Volume'] 컬럼
    → EMA5, EMA20, ATR14, Bollinger Bands(20,2σ), Vol_MA20, Pullback_% 추가
    """
    # 1) EMA (단기·중기)
    df['EMA5']  = df['Close'].ewm(span=5,  adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()

    # 2) ATR14
    high_low = df['High'] - df['Low']
    high_pc  = (df['High'] - df['Close'].shift(1)).abs()
    low_pc   = (df['Low']  - df['Close'].shift(1)).abs()
    df['TR']  = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
    df['ATR14'] = df['TR'].rolling(window=14, min_periods=1).mean()

    # 3) Bollinger Bands (20, 2σ)
    df['BB_mid']   = df['Close'].rolling(window=20, min_periods=1).mean()
    df['BB_std']   = df['Close'].rolling(window=20, min_periods=1).std(ddof=0)
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']

    # 4) Volume MA20
    df['Vol_MA20'] = df['Volume'].rolling(window=20, min_periods=1).mean()

    # 5) Pullback % (최근 20봉 최고가 대비 하락률)
    df['Roll20_High']  = df['Close'].rolling(window=20, min_periods=1).max()
    df['Pullback_pct'] = (df['Close'] - df['Roll20_High']) / df['Roll20_High']

    # 불필요 칼럼 제거
    df.drop(columns=['TR','BB_std','Roll20_High'], inplace=True)

    return df



if __name__ == '__main__':
    params = min_data.params
    dfs = {}
    for i in [5,15]:
        params['tic_scope'] = str(i)
        response = min_data.fn_ka10080(token=token_api.token, data=params)
        min_df = min_data.make_trans_df(response)
        dfs[i] = min_df


    min5_df = dfs[5]
    min15_df = dfs[15]
    day_df = day_data.day_df.copy()

    min5_cal_df = min_cal(min5_df)
    min15_cal_df = min_cal(min15_df)
    day_cal_df = day_cal(day_df)
    print(min5_cal_df.tail())
    print(min15_cal_df.tail())
    print(day_cal_df.tail())