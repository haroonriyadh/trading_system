import numpy as np
import pandas as pd
from datetime import datetime
import pandas_ta as ta
from time import sleep
import itertools
import sys
import pickle
import mplfinance as mpf
import matplotlib.pyplot as plt
from numba import njit, prange
from numba.typed import List
import plotly.graph_objects as go
from plotly.subplots import make_subplots


np.set_printoptions(suppress=True,linewidth=np.inf, threshold=np.inf,precision=4)


@njit(fastmath=True)
def leverage(max_loss,buy_price,sl,fees):
    #print(max_loss,buy_price,sl,fees)
    return max_loss/(((abs((buy_price/sl)-1)*100))+fees)


@njit(fastmath=True)
def Cala_RRR_long(buy,take,stop,fees):
    #print(max_loss,buy_price,sl,fees)
    return ((((take/buy)-1)*100)-fees)/((((buy/stop)-1)*100)+fees)  


@njit(fastmath=True)
def Cala_RRR_short(buy,take,stop,fees):
    #print(max_loss,buy_price,sl,fees)
    return ((((buy/take)-1)*100)-fees)/((((stop/buy)-1)*100)+fees)


#tickers = ['KAITOUSDT','WLDUSDT','BTCUSDT','1000RATSUSDT']
tickers = ['ETHUSDT']

def df_processing(ticker):
    df = pd.read_csv(f'/home/haroon/Backtest/{ticker}.csv')
    df['Open_time'] = df ['Open_time'].astype('datetime64[ms]')
    df['Close_time'] = df['Close_time'].astype('datetime64[ms]')
    df.set_index("Open_time",inplace=True)
    df = df[(df["High"] != df["Low"]) & (df["Volume"] != 0)]
    df['rsi'] = ta.rsi((df['High']+df['Low'])/2,lenth = 14)
    df['atr'] = ta.atr(high=df['High'],low=df['Low'],close=df['Close'],length=10)
    df['minute'] = df.index.minute
    df['hour'] = df.index.hour
    df['day'] = df.index.day
    df['HL'] = np.float32(0)
    df['OB'] =  np.float32(0)
    df['touch_ob_long'] = np.float32(0)
    df['touch_ob_short'] = np.float32(0)
    df['touch_ob_long_large_frame'] = np.float32(0)
    df['touch_ob_short_large_frame'] = np.float32(0)
    

    return df[['Open','High','Low','Close','Volume','rsi','atr','minute','hour','day','HL','OB','touch_ob_long','touch_ob_short']].values.astype(np.float32), df.index.values

X1 = []
Y = []

X_log = []
Y_log = []

max_num_x1 = 0

def get_order_block(i_df,df,i_OB,OB,open_ob):
    
    #Get Order Block Bullish  
    if i_df >= 5 and df[i_df,2] > df[i_df-2,1]:
        for l in range(2,6):
            if df[i_df-l:i_df+1,2].min() == df[i_df-(l-1),2]:
              if (i_OB[0] > -1 and OB[i_OB[0],2] != df[i_df-(l-1),2]) or i_OB[0] == -1:
                i_OB += 1
                OB[i_OB[0],0] = 1
                OB[i_OB[0],1] = i_df
                OB[i_OB[0],2] = df[i_df-(l-1),2]
                OB[i_OB[0],3] = df[i_df-l:i_df+1,1].min()
                OB[i_OB[0],4] = len(df)
                OB[i_OB[0],5] = 0
                OB[i_OB[0],6] = i_df-(l-1)
                df[i_df-(l-1),6] = 1
                open_ob.add(i_OB[0])
                break
          
    #Get Order Block Bearish    
    elif i_df >= 5 and df[i_df,1] < df[i_df-2,2]:
        for l in range(2,6):
            if  df[i_df-l:i_df+1,1].max() == df[i_df-(l-1),1]:
              if (i_OB[0] > -1 and OB[i_OB[0],2] != df[i_df-(l-1),1]) or i_OB[0] == -1:
                i_OB += 1
                OB[i_OB[0],0] = 0
                OB[i_OB[0],1] = i_df
                OB[i_OB[0],2] = df[i_df-(l-1),1]
                OB[i_OB[0],3] = df[i_df-l:i_df+1,2].max()
                OB[i_OB[0],4] = len(df)
                OB[i_OB[0],5] = 0
                OB[i_OB[0],6] = i_df-(l-1)
                df[i_df-(l-1),6] = -1
                open_ob.add(i_OB[0])
                break

def Detect_HL(df,i,window,i_HL,HL,IDM_Bull,i_IDM_Bull,IDM_Bear,i_IDM_Bear):
    #Checking for a candle that has made a high and a low at the same time
    if df[i,1] == df[i-window:i+1,1].max() and df[i,2] == df[i-window:i+1,2].min():
        if i_HL[0] >= 2:
            if HL[i_HL[0]-1,2] == 1 and df[i,1] > HL[i_HL[0]-1,1]:
                
                if i_IDM_Bull[0] > 0 and IDM_Bull[i_IDM_Bull[0]-1,2] == HL[i_HL[0]-1,1]:
                    IDM_Bull[i_IDM_Bull[0]-1,2] = df[i, 1]
                    if HL[i_HL-2,1] > IDM_Bull[i_IDM_Bull[0]-1,0] and HL[i_HL[0]-2,0] > IDM_Bull[i_IDM_Bull[0]-1,1]:
                      IDM_Bull[i_IDM_Bull[0]-1,0] = HL[i_HL[0]-2,1]
                      IDM_Bull[i_IDM_Bull[0]-1,1] = HL[i_HL[0]-2,0]
                      
                
                HL[i_HL[0]-1,1] = df[i,1]
                HL[i_HL[0]-1,0] = i
            
            elif HL[i_HL[0]-1,2] == 0 and df[i,2] < HL[i_HL[0]-1,1]:
                
                if i_IDM_Bear[0] > 0 and IDM_Bear[i_IDM_Bear[0]-1,2] == HL[i_HL[0]-1,1]:
                    IDM_Bear[i_IDM_Bear[0]-1,2] = df[i, 2]
                    if HL[i_HL[0]-2,1] < IDM_Bear[i_IDM_Bear[0]-1,0] and HL[i_HL[0]-2,0] > IDM_Bear[i_IDM_Bear[0]-1,1]:
                      IDM_Bear[i_IDM_Bear[0]-1,0] = HL[i_HL[0]-2,1]
                      IDM_Bear[i_IDM_Bear[0]-1,1] = HL[i_HL[0]-2,0]
                      

                HL[i_HL[0]-1,1] = df[i,2]
                HL[i_HL[0]-1,0] = i
      
    #Check for a candle that has reached a high
    elif df[i,1] == df[i-window:i+1,1].max():
        if i_HL[0] == 0:
            HL[i_HL[0],0] = np.argmin(df[0:i, 2])
            HL[i_HL[0],1] = df[0:i,2].min()
            HL[i_HL[0],2] = 0
            df[np.argmin(df[0:i, 2]),5] = -1
            i_HL += 1
            
            HL[i_HL[0],0] = i
            HL[i_HL[0],1] = df[i,1]
            HL[i_HL[0],2] = 1
            i_HL += 1
            

        elif HL[i_HL[0]-1,2] == 0:
            df[int(HL[i_HL[0]-1,0]),5] = -1
            HL[i_HL[0],0] = i
            HL[i_HL[0],1] = df[i,1]
            HL[i_HL[0],2] = 1
            i_HL += 1

            #df[int(HL[i_HL[0]-3,0]):int(HL[i_HL[0]-2,0]+1),6] = np.linspace(HL[i_HL[0]-3,1],HL[i_HL[0]-2,1],(int(HL[i_HL[0]-2,0]+1)-int(HL[i_HL[0]-3,0])),dtype=np.float32).flatten()
            
        elif HL[i_HL[0]-1,2] == 1 and df[i,1] > HL[i_HL[0]-1,1]:
            
            if i_IDM_Bull[0] > 0 and IDM_Bull[i_IDM_Bull[0]-1,2] == HL[i_HL[0]-1,1]:
                IDM_Bull[i_IDM_Bull[0]-1,2] = df[i, 1]
                if HL[i_HL[0]-2,1] > IDM_Bull[i_IDM_Bull[0]-1,0] and HL[i_HL[0]-2,0] > IDM_Bull[i_IDM_Bull[0]-1,1]:
                  IDM_Bull[i_IDM_Bull[0]-1,0] = HL[i_HL[0]-2,1]
                  IDM_Bull[i_IDM_Bull[0]-1,1] = HL[i_HL[0]-2,0]
                  

            HL[i_HL[0]-1,1] = df[i,1]
            HL[i_HL[0]-1,0] = i

    #Check for a candle that has reached a low        
    elif df[i,2] == df[i-window:i+1,2].min():
        if i_HL[0] == 0:
            HL[i_HL[0],0] = np.argmax(df[0:i, 1])
            HL[i_HL[0],1] = df[0:i+1,1].max()
            HL[i_HL[0],2] = 1
            df[np.argmax(df[0:i, 1]),5] = 1
            i_HL += 1
            
            HL[i_HL[0],0] = i
            HL[i_HL[0],1] = df[i,2]
            HL[i_HL[0],2] = 0
            i_HL += 1

        elif HL[i_HL[0]-1,2] == 1:
            df[int(HL[i_HL[0]-1,0]),5] = 1
            HL[i_HL[0],0] = i
            HL[i_HL[0],1] = df[i,2]
            HL[i_HL[0],2] = 0
            i_HL += 1
            #df[int(HL[i_HL[0]-3,0]):int(HL[i_HL[0]-2,0]+1),6] = np.linspace(HL[i_HL[0]-3,1],HL[i_HL[0]-2,1],(int(HL[i_HL[0]-2,0]+1)-int(HL[i_HL[0]-3,0])),dtype=np.float32).flatten()
            
        elif HL[i_HL[0]-1,2] == 0 and df[i,2] < HL[i_HL[0]-1,1]:
            
            if i_IDM_Bear[0] > 0 and IDM_Bear[i_IDM_Bear[0]-1,2] == HL[i_HL[0]-1,1]:
                IDM_Bear[i_IDM_Bear[0]-1,2] = df[i, 2]
                if HL[i_HL[0]-2,1] < IDM_Bear[i_IDM_Bear[0]-1,0] and HL[i_HL[0]-2,0] > IDM_Bear[i_IDM_Bear[0]-1,1]:
                  IDM_Bear[i_IDM_Bear[0]-1,0] = HL[i_HL[0]-2,1]
                  IDM_Bear[i_IDM_Bear[0]-1,1] = HL[i_HL[0]-2,0]
                  

            HL[i_HL[0]-1,1] = df[i,2]
            HL[i_HL[0]-1,0] = i  

def Detect_IDM(df,i,HL,i_HL,IDM_Bull,i_IDM_Bull,IDM_Bear,i_IDM_Bear):
    
    #Check for get Bullish Inducment 
    if i_HL[0] >= 4 and HL[i_HL[0]-1,2] == 1 and HL[i_HL[0]-1,1] >= HL[i_HL[0]-3,1]:

        if i_IDM_Bull[0] > 0  and IDM_Bull[i_IDM_Bull[0]-1,3] == len(df) and HL[i_HL[0]-1,1] > IDM_Bull[i_IDM_Bull[0]-1,2] and HL[i_HL[0]-2,1] > IDM_Bull[i_IDM_Bull[0]-1,0]:
            IDM_Bull[i_IDM_Bull[0]-1,0] = HL[i_HL[0]-2,1]
            IDM_Bull[i_IDM_Bull[0]-1,1] = HL[i_HL[0]-2,0]
            IDM_Bull[i_IDM_Bull[0]-1,2] = HL[i_HL[0]-1,1]
       
        
        elif i_IDM_Bull[0] > 0 and i > IDM_Bull[i_IDM_Bull[0]-1,3]:
            IDM_Bull[i_IDM_Bull[0],0] = HL[i_HL[0]-2,1]
            IDM_Bull[i_IDM_Bull[0],1] = HL[i_HL[0]-2,0]
            IDM_Bull[i_IDM_Bull[0],2] = HL[i_HL[0]-1,1]
            IDM_Bull[i_IDM_Bull[0],3] = len(df)
            i_IDM_Bull += 1
            
        elif i_IDM_Bull[0] == 0:
            IDM_Bull[i_IDM_Bull[0],0] = HL[i_HL[0]-2,1]
            IDM_Bull[i_IDM_Bull[0],1] = HL[i_HL[0]-2,0]
            IDM_Bull[i_IDM_Bull[0],2] = HL[i_HL[0]-1,1]
            IDM_Bull[i_IDM_Bull[0],3] = len(df)
            i_IDM_Bull += 1
    
    #Check for get Bearish Inducment 
    if i_HL[0] >= 4 and HL[i_HL[0]-1,2] == 0 and HL[i_HL[0]-1,1] <= HL[i_HL[0]-3,1]:
        
        if i_IDM_Bear[0] > 0  and IDM_Bear[i_IDM_Bear[0]-1,3] == len(df) and HL[i_HL[0]-1,1] < IDM_Bear[i_IDM_Bear[0]-1,2] and HL[i_HL[0]-2,1] < IDM_Bear[i_IDM_Bear[0]-1,0]:
            IDM_Bear[i_IDM_Bear[0]-1,0] = HL[i_HL[0]-2,1]
            IDM_Bear[i_IDM_Bear[0]-1,1] = HL[i_HL[0]-2,0]
            IDM_Bear[i_IDM_Bear[0]-1,2] = HL[i_HL[0]-1,1]
        
        
        elif i_IDM_Bear[0] > 0 and i > IDM_Bear[i_IDM_Bear[0]-1,3]:
            IDM_Bear[i_IDM_Bear[0],0] = HL[i_HL[0]-2,1]
            IDM_Bear[i_IDM_Bear[0],1] = HL[i_HL[0]-2,0]
            IDM_Bear[i_IDM_Bear[0],2] = HL[i_HL[0]-1,1]
            IDM_Bear[i_IDM_Bear[0],3] = len(df)
            i_IDM_Bear += 1
            
        elif i_IDM_Bear[0] == 0:
            IDM_Bear[i_IDM_Bear[0],0] = HL[i_HL[0]-2,1]
            IDM_Bear[i_IDM_Bear[0],1] = HL[i_HL[0]-2,0]
            IDM_Bear[i_IDM_Bear[0],2] = HL[i_HL[0]-1,1]
            IDM_Bear[i_IDM_Bear[0],3] = len(df)
            i_IDM_Bear += 1
      
def Detect_Bos_and_Choch(df,i,IDM_Bull,i_IDM_Bull,IDM_Bear,i_IDM_Bear,BOS,i_Bos,CHOCH,i_Choch):
  
    if i_IDM_Bull[0] > 0 and IDM_Bull[i_IDM_Bull[0]-1,3] == len(df) and df[i,2] <= IDM_Bull[i_IDM_Bull[0]-1,0]:
        IDM_Bull[i_IDM_Bull[0]-1,3] = i
        
        if i_Bos[0] == 0:
            BOS[i_Bos[0],0] = 1
            BOS[i_Bos[0],1] = IDM_Bull[i_IDM_Bull[0]-1,2]
            BOS[i_Bos[0],2] = IDM_Bull[i_IDM_Bull[0]-1,1]
            BOS[i_Bos[0],3] = len(df)
            BOS[i_Bos[0],4] = 0
            i_Bos += 1
            
            CHOCH[i_Choch[0],0] = 1
            CHOCH[i_Choch[0],1] = df[0:int(IDM_Bull[i_IDM_Bull[0]-1,1])+1,2].min()
            CHOCH[i_Choch[0],2] = df[0:int(IDM_Bull[i_IDM_Bull[0]-1,1])+1,2].argmin()
            CHOCH[i_Choch[0],3] = len(df)
            i_Choch += 1
            
    if i_IDM_Bear[0] > 0 and IDM_Bear[i_IDM_Bear[0]-1,3] == len(df) and df[i,1] >= IDM_Bear[i_IDM_Bear[0]-1,0]:
        IDM_Bear[i_IDM_Bear[0]-1,3] = i
        
        if i_Bos[0] == 0:
            BOS[i_Bos[0],0] = 0
            BOS[i_Bos[0],1] = IDM_Bear[i_IDM_Bear[0]-1,2]
            BOS[i_Bos[0],2] = IDM_Bear[i_IDM_Bear[0]-1,1]
            BOS[i_Bos[0],3] = len(df)
            BOS[i_Bos[0],4] = 0
            i_Bos += 1
            
            CHOCH[i_Choch[0],0] = 0
            CHOCH[i_Choch[0],1] = df[0:int(IDM_Bear[i_IDM_Bear[0]-1,1])+1,1].max()
            CHOCH[i_Choch[0],2] = df[0:int(IDM_Bear[i_IDM_Bear[0]-1,1])+1,1].argmax()
            CHOCH[i_Choch[0],3] = len(df)
            i_Choch += 1
            
    #Check last_point for a Bos Bullish
    if i_Bos[0] > 0 and BOS[i_Bos[0]-1,3] == len(df) and BOS[i_Bos[0]-1,0] == 1:
        if BOS[i_Bos[0]-1,4] == 1:
            if df[i,3] > BOS[i_Bos[0]-1,1]:
                BOS[i_Bos[0]-1,3] = i
                
                if df[int(BOS[i_Bos[0]-1,2]):i+1,2].min() > CHOCH[i_Choch[0]-1,1]:
                    CHOCH[i_Choch[0]-1,1] = df[int(BOS[i_Bos[0]-1,2]):i+1,2].min()
                    CHOCH[i_Choch[0]-1,2] = df[int(BOS[i_Bos[0]-1,2]):i+1,2].argmin()+BOS[i_Bos[0]-1,2]

                BOS[i_Bos[0],0] = 1
                BOS[i_Bos[0],1] = df[i,1]
                BOS[i_Bos[0],2] = i
                BOS[i_Bos[0],3] = len(df)
                BOS[i_Bos[0],4] = 0
                i_Bos += 1
                
            #elif df.at[id,'High'] > BOS[-1][1] > df.at[id,'Close']:
                #BOS[-1][1] = df.at[id,'High']
        
        else:
            if df[i,1] > BOS[i_Bos[0]-1,1]:
                BOS[i_Bos[0]-1,1] = df[i,1]
                BOS[i_Bos[0]-1,2] = i
            
            elif (df[i,2] <= CHOCH[i_Choch[0]-1,1]+(BOS[i_Bos[0]-1,1]-CHOCH[i_Choch[0]-1,1])*0.618 and\
                 i-BOS[i_Bos[0]-1,2] >= (BOS[i_Bos[0]-1,2]-CHOCH[i_Choch[0]-1,2])*1) or IDM_Bull[i_IDM_Bull[0]-1,3] == i:
                
                BOS[i_Bos[0]-1,4] = 1

    #Chech last_point for a Bos Bearish
    if i_Bos[0] > 0 and BOS[i_Bos[0]-1,3] == len(df) and BOS[i_Bos[0]-1,0] == 0:
        if BOS[i_Bos[0]-1,4] == 1:
            if df[i,3] < BOS[i_Bos[0]-1,1]:
                BOS[i_Bos[0]-1,3] = i
                if df[int(BOS[i_Bos[0]-1,2]):i+1,1].max() < CHOCH[i_Choch[0]-1,1]:
                    CHOCH[i_Choch[0]-1,1] = df[int(BOS[i_Bos[0]-1,2]):i+1,1].max()
                    CHOCH[i_Choch[0]-1,2] = df[int(BOS[i_Bos[0]-1,2]):i+1,1].argmax()+BOS[i_Bos[0]-1,2]
                    
                BOS[i_Bos[0],0] = 0
                BOS[i_Bos[0],1] = df[i,2]
                BOS[i_Bos[0],2] = i
                BOS[i_Bos[0],3] = len(df)
                BOS[i_Bos[0],4] = 0
                i_Bos += 1
                
            #elif df.at[id,'Low'] < BOS[-1][1] < df.at[id,'Close']:
                #BOS[-1][1] = df.at[id,'Low']
        else:
            if df[i,2] < BOS[i_Bos[0]-1,1]:
                BOS[i_Bos[0]-1,1] = df[i,2]
                BOS[i_Bos[0]-1,2] = i
            
            elif (df[i,1] >= CHOCH[i_Choch[0]-1,1]-(CHOCH[i_Choch[0]-1,1]-BOS[i_Bos[0]-1,1])*0.618 and\
                 i-BOS[i_Bos[0]-1,2] >= (BOS[i_Bos[0]-1,2]-CHOCH[i_Choch[0]-1,2])*1) or IDM_Bear[i_IDM_Bear[0]-1,3] == i:

                BOS[i_Bos[0]-1,4] = 1
                
    #Check last_point for a Choch to Long
    if i_Choch[0] > 0 and CHOCH[i_Choch[0]-1,3] == len(df) and CHOCH[i_Choch[0]-1,0] == 0:
        
        if df[i,3] > CHOCH[i_Choch[0]-1,1]:
            CHOCH[i_Choch[0]-1,3] = i
            
            CHOCH[i_Choch,0] = 1
            CHOCH[i_Choch,1] = BOS[i_Bos[0]-1,1]
            CHOCH[i_Choch,2] = BOS[i_Bos[0]-1,2]
            CHOCH[i_Choch,3] = len(df)
            i_Choch += 1
            
            BOS[i_Bos[0]-1,0] = 1
            BOS[i_Bos[0]-1,1] = df[i,1]
            BOS[i_Bos[0]-1,2] = i
            BOS[i_Bos[0]-1,3] = len(df)
            BOS[i_Bos[0]-1,4] = 0
    
    
        #elif df.at[id,'High'] > CHOCH[-1][1] > df.at[id,'Close']:
            #CHOCH[-1][1] = df.at[id,'High']
            
    #Check last_point for a Choch to Short
    elif i_Choch[0] > 0 and CHOCH[i_Choch[0]-1,3] == len(df) and CHOCH[i_Choch[0]-1,0] == 1:
        
        if df[i,3] < CHOCH[i_Choch[0]-1,1]:
            CHOCH[i_Choch[0]-1,3] = i
            
            CHOCH[i_Choch[0],0] = 0
            CHOCH[i_Choch[0],1] = BOS[i_Bos[0]-1,1]
            CHOCH[i_Choch[0],2] = BOS[i_Bos[0]-1,2]
            CHOCH[i_Choch[0],3] = len(df)
            i_Choch += 1
            
            BOS[i_Bos[0]-1,0] = 0
            BOS[i_Bos[0]-1,1] = df[i,2]
            BOS[i_Bos[0]-1,2] = i
            BOS[i_Bos[0]-1,3] = len(df)
            BOS[i_Bos[0]-1,4] = 0

def plot_chart(df,HL=None,ob=None,Pos=None,IDM_Bull=None,IDM_Bear=None,BOS=None,CHOCH=None,rsi=False):
        

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.9, 0.1],          # 70٪ شموع، 30٪ RSI
        subplot_titles=('Price + HL', 'RSI (14)')
    )
    
    # --- صف الشموع + HL ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            increasing_line_color='rgba(0, 153, 255, 1)',
            increasing_fillcolor='rgba(0, 153, 255, 1)',  # جعلت الجسم أشفّ قليلاً
            decreasing_line_color='rgba(150, 150, 150, 1)',
            decreasing_fillcolor='rgba(150, 150, 150, 1)'
        )
    )
    
    if isinstance(HL,(np.ndarray,list)) and len(HL) > 0:
        HL_Price = list(itertools.chain.from_iterable([np.linspace(HL[i-1,1],HL[i,1],int(HL[i,0]-HL[i-1,0]),endpoint=False) for i in range(1,len(HL))]))
        df['HL'] = pd.Series(data=HL_Price,index=df.index[int(HL[0,0]):int(HL[-1,0])])
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['HL'],
                line=dict(color='white', width=1.5),
                name='HL'
            ),
            row=1, col=1
        )

    if isinstance(ob,(np.ndarray,list)):
        for block in ob:
            if block[4] != -1:
                fig.add_shape(
                    type = "rect",
                    x0 = df.index[int(block[-1])], x1 = df.index[int(block[4]-1)],
                    y0 = block[2], y1 = block[3],  # مستوى السعر (طلب)
                    fillcolor = "rgba(0, 255, 0, 0.2)" if block[0] == 1 else "rgba(255, 0, 0, 0.2)",  # أخضر شفاف
                    line = dict(width=0),
                    layer = "below"
                )
    
    if rsi:
        # --- صف RSI ---
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['rsi'],
                mode='lines',
                line=dict(width=1.5, color='rgba(187,107,217,0.9)'),
                name='RSI',
                hoverinfo = 'x+y+name'
            ),
            row=2, col=1
        )
        
        # خطوط تشبّع RSI
        for level, color in [(70, 'red'), (30, 'green')]:
            fig.add_shape(
                type='line',
                xref='x',
                yref='y2',              # y2 لأن الصف الثاني
                x0=df.index[0], y0=level,
                x1=df.index[-1], y1=level,
                line=dict(color=color, dash='dash'),
                row=2, col=1
            )    
    
    if isinstance(IDM_Bull,(np.ndarray,list)):
        for i in IDM_Bull:
            # ✅ 1. رسم الخط المستقيم (من تاريخ إلى تاريخ)
            fig.add_shape(
                type="line",
                x0=df.index[int(i[1])],
                y0=i[0],
                x1=df.index[int(i[3]-1)],
                y1=i[0],
                line=dict(color='green', width=1),
                layer="above"
            )
    
    if isinstance(IDM_Bear,(np.ndarray,list)):
        for i in IDM_Bear:
            # ✅ 1. رسم الخط المستقيم (من تاريخ إلى تاريخ)
            fig.add_shape(
                type="line",
                x0=df.index[int(i[1])],
                y0=i[0],
                x1=df.index[int(i[3]-1)],
                y1=i[0],
                line=dict(color='red', width=1),
                layer="above"
            )
    
    if isinstance(BOS,(np.ndarray,list)):
        for B in BOS:

            # ✅ 1. رسم الخط المستقيم (من تاريخ إلى تاريخ)
            fig.add_shape(
                type = "line",
                x0 = df.index[int(B[2])],
                y0 = B[1],
                x1 = df.index[int(B[3]-1)],
                y1 = B[1],
                line = dict(color = 'blue', width=3),
                layer = "above"
            )

    if isinstance(CHOCH,(np.ndarray,list)):

        for CH in CHOCH:
            # ✅ 1. رسم الخط المستقيم (من تاريخ إلى تاريخ)
            fig.add_shape(
                type = "line",
                x0 = df.index[int(CH[2])],
                y0 = CH[1],
                x1 = df.index[int(CH[3]-1)],
                y1 = CH[1],
                line = dict(color = 'yellow', width=3),
                layer = "above"
            )

    if isinstance(Pos,(np.ndarray,list)):
        for p in Pos:

            fig.add_shape(

                type = "rect",
                x0 = df.index[int(p[0])], x1 = df.index[int(p[5])],
                y0 = p[2], y1 = p[3],  # مستوى السعر (طلب)
                fillcolor = "rgba(0,255 ,0, 0.2)",  # أخضر شفاف
                line = dict(width=0),
                layer = "below"
            )

            fig.add_shape(
                type = "rect",
                x0 = df.index[int(p[0])], x1 = df.index[int(p[5])],
                y0 = p[2], y1 = p[4],  # مستوى السعر (طلب)
                fillcolor = "rgba(255,0 , 0, 0.2)",  # أخضر شفاف
                line = dict(width=0),
                layer = "below"
            )


    fig.update_yaxes(title_text='Price', row=1, col=1)
    fig.update_yaxes(title_text='RSI',   row=2, col=1, range=[0, 100])
    
    fig.update_layout(
        plot_bgcolor='black',
        paper_bgcolor='black',
        dragmode="pan",  # السحب بحرية
        autosize=True,
        margin=dict(l=5, r=5, t=25, b=20),  # حواف مريحة للهاتف
        xaxis_rangeslider_visible=False,  # إخفاء شريط النطاق السفلي
        hovermode="x unified",  # توحيد الإطار عند تمرير الماوس
        xaxis=dict(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            showline=True,
            showgrid=True,
            showticklabels=True
        ),
        yaxis=dict(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            showline=True,
            showgrid=True
        ),
        template="plotly_dark",  # نمط غامق مثل TradingView
        showlegend=False
    )


    # أو حفظه كملف HTML تفاعلي
    fig.write_html("/home/haroon/trading_system/candlestick_chart.html")
    print("------------------------------------------")
        
def entry_trade(df,i,open_ob_index,OB,X1,Y,open_pos_index,positions,i_positions,num_ob_long_active,num_ob_short_active,max_loss,fees,money,RRR):

    to_remove_ob = set()    
    for f in open_ob_index:
        if OB[f,-1]+1000 <= i or i <= OB[f,-1]+1 and\
            ((OB[f,0] == 1 and df[i,2] <= OB[f,3]) or\
            (OB[f,0] == 0 and df[i,1] >= OB[f,3])):
            OB[f,4] = i
            to_remove_ob.add(f)
            continue
            
        if  OB[f,0] == 1 and df[i,2] <= OB[f,3]:
            #if Cala_RRR_long(OB[f,3],df[int(OB[f,-1]):i+1,1].max(),OB[f,2],0.07) >= 2:
                X_log.append(i-OB[f,-1])
                Y_log.append(0)
                num_ob_long_active[0] += 1
                X1.append(df[int(OB[f,-1]-1):i+1,(0,1,2,3,5,6,7,8)])
                #print(df[int(OB[f,-1]-1):i+1,(0,1,2,3,5,6,7,8)],flush=True)
                X1[-1][-1][3] = OB[f,3]
                X1[-1][-1][2] = OB[f,3]
                X1[-1][-1][6] = num_ob_long_active[0]
                Y.append([0,0,0])
                
                positions[i_positions[0],0] = i
                positions[i_positions[0],1] = 1
                positions[i_positions[0],2] = OB[f,3]
                #positions[i_positions[0],3] = df[int(OB[f,-1]):i+1,1].max()
                positions[i_positions[0],3] = OB[f,3]*(((((abs(((OB[f,3]/OB[f,2])-1)*100)+fees)*RRR)+fees)/100)+1)
                positions[i_positions[0],4] = OB[f,2]
                positions[i_positions[0],5] = 0
                positions[i_positions[0],6] = 0
                positions[i_positions[0],7] = 0
                positions[i_positions[0],8] = max_loss/(((abs((OB[f,3]/OB[f,2])-1)*100))+fees)
                positions[i_positions[0],9] = len(Y_log)-1
                positions[i_positions[0],10] = money[0]
                positions[i_positions[0],11] = f
                positions[i_positions[0],12] = 0
                open_pos_index.add(i_positions[0])
                i_positions[0] += 1
                OB[f,4] = i
            
                to_remove_ob.add(f)

            #else:
                #OB[f,4] = i

            
        elif OB[f,0] == 0 and df[i,1] >= OB[f,3]:
            #if Cala_RRR_short(OB[f,3],df[int(OB[f,-1]):i+1,2].min(),OB[f,2],0.07) >= 2:
                X_log.append(i-OB[f,-1])
                Y_log.append(0)
                num_ob_short_active[0] += 1
                X1.append(df[int(OB[f,-1]-1):i+1,(0,1,2,3,5,6,7,8)])
                X1[-1][-1][3] = OB[f,3]
                X1[-1][-1][1] = OB[f,3]
                X1[-1][-1][7] = num_ob_long_active[0]
                Y.append([0,0,0])

                #tp = df[int(OB[f,-1]):i+1,2].min()
                
                positions[i_positions[0],0] = i
                positions[i_positions[0],1] = 0
                positions[i_positions[0],2] = OB[f,3]
                #positions[i_positions[0],3] = df[int(OB[f,-1]):i+1,2].min()
                positions[i_positions[0],3] = OB[f,3]*((((((abs(((OB[f,3]/OB[f,2])-1)*100)+fees)*RRR)+fees)*-1)/100)+1)
                positions[i_positions[0],4] = OB[f,2]
                positions[i_positions[0],5] = 0
                positions[i_positions[0],6] = 0
                positions[i_positions[0],7] = 0
                positions[i_positions[0],8] = max_loss/(((abs((OB[f,3]/OB[f,2])-1)*100))+fees)
                positions[i_positions[0],9] = len(Y_log)-1
                positions[i_positions[0],10] = money[0]
                positions[i_positions[0],11] = f
                positions[i_positions[0],12] = 0
                open_pos_index.add(i_positions[0])
                i_positions[0] += 1
                OB[f,4] = i
                
                to_remove_ob.add(f)

            #else:
                #OB[f,4] = i

    
    open_ob_index.difference_update(to_remove_ob)

def check_positions(df,i,positions,open_pos_index,fees,money,balanced_data,num_ob_long_active,num_ob_short_active,Y):

    to_remove_pos = set()
    for p in open_pos_index:

        if positions[p,1] == 1:
            df[i,7] += 1
        
        elif positions[p,1] == 0:
            df[i,8] += 1
            
        #Check Open_Order is Win 
        if i > positions[p,0]  and\
            ((positions[p,1] == 1 and df[i,1] >= positions[p,3]) or\
            (positions[p,1] == 0 and df[i,2] <= positions[p,3])):
            positions[p,5] = i
            pct = (((abs(((positions[p,3]/positions[p,2])-1)*100)-fees))*positions[p,8]) if ((positions[p,3] > positions[p,2] and positions[p,1] == 1) or\
            positions[p,3] < positions[p,2] and positions[p,1] == 0) else (((abs(((positions[p,2]/positions[p,3])-1)*100)*-1)-fees)*positions[p,8])
            positions[p,7] = round(pct,3)
            positions[p,12] = 1
            positions[p,6] = True
            pnl =  (positions[p,10]*((pct/100)+1))-positions[p,10]
            money[0] += pnl
            Y_log[int(positions[p,9])] = 1
            #Y[int(positions[p,9])][0] = 1
            #Y[int(positions[p,9])][1] = positions[p,12]
            #Y[int(positions[p,9])][2] = positions[p,7]
            
            to_remove_pos.add(p)

            if positions[p,1] == 1:
                num_ob_long_active -= 1
                
            else:
                num_ob_short_active -= 1
                
            print(f"\r{np.round(money[0],4)}", end="",flush=True)  
            #prices = np.array(df[int(positions[p,0])-10:int(positions[p,0])+10,0:4],dtype=np.float32)
            # تحويل المصفوفة إلى DataFrame
            #prices = pd.DataFrame(prices, columns=['Open','High','Low','Close'], index=np.datetime64('2024-01-01')+np.arange(len(prices)))
            # رسم باستخدام mplfinance
            #mpf.plot(prices,type='candle',style=style, warn_too_much_data=len(df),title="Candlestick from NumPy",savefig=f'/storage/emulated/0/Plot_time_series/Chart_{i_t}.jpg')
        
        
        #Check Open_Order is Loss   
        elif i >= positions[p,0] and\
            ((positions[p,1] == 1 and positions[p,4] >= df[i,2]) or\
            (positions[p,1] == 0 and positions[p,4] <= df[i,1])):
            positions[p,5] = i
            
            if positions[p,1] == 1:
                df[i,7] -= 2
            
            elif positions[p,1] == 0:
                df[i,8] -= 2


            
            if balanced_data and i > positions[p,0]:
                if ((positions[p,1] == 1 and (((abs(((df[int(positions[p,0])+1:i+1,1].max()/positions[p,2])-1)*100)-fees))*positions[p,8]) >= 1) or\
                    (positions[p,1] == 0 and (((abs(((df[int(positions[p,0])+1:i+1,2].min()/positions[p,2])-1)*100)-fees))*positions[p,8]) >= 1)):
                    positions[p,12] = (df[int(positions[p,0])+1:i+1,1].max() - positions[p,2]) / (positions[p,3] - positions[p,2]) if positions[p,1] == 1 else (df[int(positions[p,0])+1:i+1,2].min() - positions[p,2]) / (positions[p,3] - positions[p,2])
                    
                    positions[p,3] = df[int(positions[p,0])+1:i+1,1].max() if positions[p,1] == 1 else df[int(positions[p,0])+1:i+1,2].min()
                    pct = (((abs(((positions[p,3]/positions[p,2])-1)*100)-fees))*positions[p,8]) if ((positions[p,3] > positions[p,2] and positions[p,1] == 1) or\
                            positions[p,3] < positions[p,2] and positions[p,1] == 0) else (((abs(((positions[p,2]/positions[p,3])-1)*100)*-1)-fees)*positions[p,8])
                    positions[p,6] = True
                    positions[p,7] = round(pct,3)
                    pnl =  (positions[p,10]*((pct/100)+1))-positions[p,10]
                    money[0] += pnl
                    #Y[int(positions[p,9])][0] = 1
                    #Y[int(positions[p,9])][1] = positions[p,12]
                    #Y[int(positions[p,9])][2] = positions[p,7]
                    #X2[int(positions[p,9]),-1] = 0
                    #X2[int(positions[p,9]),-1,-1] = 0
                    print(f"\r{np.round(money[0],4)}", end="",flush=True)
                
                else:
                    pct = (((abs(((positions[p,2]/positions[p,4])-1)*100)*-1)-fees)*positions[p,8])
                    positions[p,7] = round(pct,3)
                    pnl =  (positions[p,10]*((pct/100)+1))-positions[p,10]
                    money[0] += pnl
                    positions[p,12] = -1
                    #Y[positions[p,9],0] = 0
                    #Y[positions[p,9],1] = 0
                    #Y[positions[p,9],2] = 0
                    #X2[int(positions[p,9]),-1] = 0
                    print(f"\r{np.round(money[0],4)}", end="",flush=True)  
            
            else:
                pct = (((abs(((positions[p,2]/positions[p,4])-1)*100)*-1)-fees)*positions[p,8])
                positions[p,7] = round(pct,3)
                pnl =  (positions[p,10]*((pct/100)+1))-positions[p,10]
                money[0] += pnl
                positions[p,12] = -1
                #Y[positions[p,9],0] = 0
                #Y[positions[p,9],1] = 0
                #Y[positions[p,9],2] = 0
                #X2[int(positions[p,9]),-1] = 0
                print(f"\r{np.round(money[0],4)}", end="",flush=True)
            
            to_remove_pos.add(p)

            if positions[p,1] == 1:
                num_ob_long_active -= 1
                
            else:
                num_ob_short_active -= 1

        #Close last Trade
        if  i == len(df)-1:
            positions[p,5] = i
            positions[p,12] = -1
            pct = (((((df[i,3]/positions[p,2])-1)*100)-fees)*positions[p,8]) if positions[p,1] == 1 else\
                (((((positions[p,2]/df[i,3])-1)*100)-fees)*positions[p,8])
            positions[p,7] = round(pct,3)
            pnl =  (positions[p,10]*((pct/100)+1))-positions[p,10]
            money[0] += pnl
            #Y[positions[p,9],0] = 2
            #Y[positions[p,9],1] = 2
            #Y[positions[p,9],2] = 2
            #X2[int(positions[p,9]),-1] = 0
            print(f"\r{np.round(money[0],4)}", end="",flush=True)

            to_remove_pos.add(p)

            if positions[p,1] == 1:
                num_ob_long_active -= 1
                
            else:
                num_ob_short_active -= 1
    
    
    #open_ob_index.difference_update(to_remove_ob)
    open_pos_index.difference_update(to_remove_pos)
    
def backtest(df,balanced_data = True):

    money = np.array([1],np.float64)
    window = 5
    df_5m = np.zeros((int(np.ceil(len(df)/5))+1,14),dtype=np.float32)
    df_5m[0,0:5] = df[0,0:5]
    OB_5m = np.zeros((int(len(df)/(2*5)),7),dtype=np.float32)
    OB = np.zeros((int(len(df)/(2)),7),dtype=np.float32)
    
    HL = np.zeros((int(len(df)/2),3),dtype=np.float32)
    IDM_Bull = np.zeros((int(len(df)/10),4),dtype=np.float32)
    IDM_Bear = np.zeros((int(len(df)/10),4),dtype=np.float32)
    BOS = np.zeros((int(len(df)/50),5),dtype=np.float32)
    CHOCH = np.zeros((int(len(df)/50),4),dtype=np.float32)
    
    HL_5m = np.zeros((int(len(df_5m)/2),3),dtype=np.float32)
    IDM_Bull_5m = np.zeros((int(len(df_5m)/10),4),dtype=np.float32)
    IDM_Bear_5m = np.zeros((int(len(df_5m)/10),4),dtype=np.float32)
    BOS_5m = np.zeros((int(len(df_5m)/50),5),dtype=np.float32)
    CHOCH_5m = np.zeros((int(len(df_5m)/50),4),dtype=np.float32)
    
    positions = np.zeros((int(len(df)/5),13),dtype=np.float64)
    positions_5m = np.zeros((int(len(df)/5),13),dtype=np.float64)

    i_df_5m = 0
    i_OB_5m = np.array([-1],np.int32)
    i_OB = np.array([-1],np.int32)
    
    i_HL = np.array([0],np.int32)
    i_IDM_Bull = np.array([0],np.int32)
    i_IDM_Bear = np.array([0],np.int32)
    i_Bos = np.array([0],np.int32)
    i_Choch = np.array([0],np.int32)
    
    i_HL_5m = np.array([0],np.int32)
    i_IDM_Bull_5m = np.array([0],np.int32)
    i_IDM_Bear_5m = np.array([0],np.int32)
    i_Bos_5m = np.array([0],np.int32)
    i_Choch_5m = np.array([0],np.int32)

    i_positions = np.array([0],np.int32)
    i_positions_5m = np.array([0],np.int32)

    RRR = 2
    fees = 0.00
    max_loss = 1

    open_pos_index = set()
    open_pos_index_5m = set()
    
    open_ob_index = set()
    open_ob_index_5m = set()
    
    num_ob_long_active = np.array([0],np.int32)
    num_ob_short_active = np.array([0],np.int32)
    
    for i in np.arange(len(df)):

        if i >= window:
            Detect_HL(df,i,window,i_HL,HL,IDM_Bull,i_IDM_Bull,IDM_Bear,i_IDM_Bear)
            #Detect_IDM(df,i,HL,i_HL,IDM_Bull,i_IDM_Bull,IDM_Bear,i_IDM_Bear)
            #Detect_Bos_and_Choch(df,i,IDM_Bull,i_IDM_Bull,IDM_Bear,i_IDM_Bear,BOS,i_Bos,CHOCH,i_Choch)
            
            #get_order_block(i,df,i_OB,OB,open_ob_index)
            #entry_trade(df,i,i_t,open_ob_index,OB,X1,open_pos_index,positions,i_positions,num_ob_long_active,num_ob_short_active,max_loss,fees,money,RRR)
            #check_positions(df,i,positions,open_pos_index,fees,money,balanced_data,num_ob_long_active,num_ob_short_active,Y)

        
        if df[i,7] % 5 == 0:  
            if i_df_5m >= window:
                Detect_HL(df_5m,i_df_5m,window,i_HL_5m,HL_5m,IDM_Bull_5m,i_IDM_Bull_5m,IDM_Bear_5m,i_IDM_Bear_5m)
                Detect_IDM(df_5m,i_df_5m,HL_5m,i_HL_5m,IDM_Bull_5m,i_IDM_Bull_5m,IDM_Bear_5m,i_IDM_Bear_5m)
                Detect_Bos_and_Choch(df_5m,i_df_5m,IDM_Bull_5m,i_IDM_Bull_5m,IDM_Bear_5m,i_IDM_Bear_5m,BOS_5m,i_Bos_5m,CHOCH_5m,i_Choch_5m)
            
            get_order_block(i_df_5m,df_5m,i_OB_5m,OB_5m,open_ob_index_5m)
            entry_trade(df_5m,i_df_5m,open_ob_index_5m,OB_5m,X1,Y,open_pos_index_5m,positions_5m,i_positions_5m,num_ob_long_active,num_ob_short_active,max_loss,fees,money,RRR)
            check_positions(df_5m,i_df_5m,positions_5m,open_pos_index_5m,fees,money,balanced_data,num_ob_long_active,num_ob_short_active,Y)

            i_df_5m += 1
            df_5m[i_df_5m,0:5] = df[i,0:5]
        
        else:
            if df_5m[i_df_5m,1] < df[i,1]: df_5m[i_df_5m,1] = df[i,1]
            if df_5m[i_df_5m,2] > df[i,2]: df_5m[i_df_5m,2] = df[i,2]
            df_5m[i_df_5m,3] = df[i,3]
            df_5m[i_df_5m,4] += df[i,4] 
            #df_5m[i_df_5m,4] = rsi(df_5m[i_df_5m,3],rsi_State,14)
            #if i_df_5m >= 10 : df_5m[i_df_5m,5] = atr(atr_State,df_5m[:i_df_5m+1,1],df_5m[:i_df_5m+1,2],df_5m[:i_df_5m+1,3])
        
    return df,positions_5m[:i_positions_5m[0]],df_5m,money[0],OB_5m[:i_OB_5m[0]+1],HL[:i_HL[0]],HL_5m[:i_HL_5m[0]],IDM_Bull_5m[:i_IDM_Bull_5m[0]],IDM_Bear_5m[:i_IDM_Bear_5m[0]],BOS_5m[:i_Bos_5m[0]],CHOCH_5m[:i_Choch_5m[0]]


for ticker in tickers:
    start = datetime.now()
    df,index = df_processing(ticker)
    Df,posi,Df_5m,mon,ob_5m,hl,hl_5m,idm_bull_5m,idm_bear_5m,bos_5m,choch_5m = backtest(df,balanced_data=False)
    
    
    #ob_5m = [ob for ob in ob_5m if ob[4] not in [-1, len(df_5m)]]
    pos = pd.DataFrame(posi,columns=  ['Open_Order','Side',
                                        'Buy_Price','Take_Profit','Stop_Loss',
                                        'Close_Order','Win_Trade','Pct_Change',
                                        'Leverage','index','Balance','Distance','Target_price'])
    df = pd.DataFrame(data = df,index = index,columns=['Open','High','Low','Close','Volume','rsi','atr','minute','hour','day','HL','OB','touch_ob_long','touch_ob_short']) 
    
    df_5m = df.resample('5min').agg({'Open': 'first',
                                     'High': 'max',
                                     'Low': 'min',
                                     'Close': 'last',
                                     'Volume': 'sum'
                                    })
    #print(posi)
    pos.to_csv('/home/haroon/Backtest/trades.csv', index=False)
    
    if len(pos) >= 1 :
        pos_long = pos[pos['Side'] == 1]
        pos_short = pos[pos['Side'] == 0]
        win = pos[pos['Pct_Change'] > 0] 
        loss = pos[pos['Pct_Change'] < 0]
        print(f"{ticker} Of Profit : " , round(mon,4))
        print("Gains_Long  : ",len(pos_long[pos_long['Pct_Change'] > 0]))
        print("Loss_Long   : ",len(pos_long[pos_long['Pct_Change'] < 0]))
        print("Gains_Short : ",len(pos_short[pos_short['Pct_Change'] > 0]))
        print("Loss_Short  : ",len(pos_short[pos_short['Pct_Change'] < 0]))
        print("Win_Rate    : ",round(len(win)/len(pos)*100,2) if len(win[win['Side'] == 1])+len(win[win['Side'] == 0]) > 0 else 0,"%")
        print("N_O_T       : ",len(pos))
        print("A_P_P_T     : ",np.mean(win['Pct_Change']) if len(win) > 0 else 0)
        print("A_L_P_T     : ",np.mean(loss['Pct_Change']) if len(loss) > 0 else 0)
        print("Big_Profit  : ",np.max(win['Pct_Change']) if len(win) > 0 else 0)
        print("Big_Loss    : ",np.min(loss['Pct_Change']) if len(loss) > 0 else 0)
    
    
    end = datetime.now()
    print(end-start)
    
    #plot_chart(df=df_5m,HL=hl_5m,IDM_Bull=idm_bull_5m,IDM_Bear = idm_bear_5m,ob=ob_5m)

# حفظ البيانات في ملف
with open('/home/haroon/Backtest/Test_data.pkl', 'wb') as f:
    pickle.dump({'X' : X_log,
                 'Y' : Y_log}, f)



  




