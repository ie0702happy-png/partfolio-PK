import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

# --- 頁面設定 ---
st.set_page_config(page_title="百萬投資組合 PK (專業版)", layout="wide")
st.title("💰 百萬台幣投資組合大亂鬥")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    st.write("⏱️ **自動更新**")
    auto_refresh = st.toggle("開啟每 60 秒自動刷新", value=False)
    if auto_refresh:
        st.caption("⚠️ 啟動中...右上角會顯示 Running")
    
    st.divider()

    period = st.selectbox("回測時間範圍", ["YTD", "6mo", "1y", "2y", "5y", "max"], index=2)
    st.info("⚠️ 注意：回測起點將受限於『最晚上市』的那支 ETF (例如 AVGS/AVGE 較新)。")
    
    if st.button("🔄 手動刷新"):
        st.rerun()

# --- 定義投資組合權重 ---
portfolios = {
    "🔰 你的組合": {
        "VWRA.L": 0.50, "AVGS.L": 0.30, "0050.TW": 0.20
    },
    "🍺 Ginger Ale": {
        "VOO": 0.30, "AVUV": 0.30, "VEA": 0.10, 
        "AVDV": 0.10, "VWO": 0.10, "AVES": 0.10
    },
    "🌊 清流君 Portfolio": {
        "VOO": 0.24, "AVUV": 0.12, "QMOM": 0.12, "VXUS": 0.12,
        "AVDV": 0.06, "IMOM": 0.06, "AVES": 0.08, "0050.TW": 0.20
    },
    "🌎 AVGE ": {
        "AVGE": 1.0
    }
}

# 提取所有代號
all_tickers = set()
for p in portfolios.values():
    all_tickers.update(p.keys())
all_tickers_list = list(all_tickers) + ["USDTWD=X"]

# --- 核心邏輯 ---
def load_data(period):
    try:
        raw = yf.download(all_tickers_list, period=period, progress=False)
        if raw.empty: return pd.DataFrame()
        
        if 'Adj Close' in raw.columns: df = raw['Adj Close']
        elif 'Close' in raw.columns: df = raw['Close']
        else: df = raw

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            
        return df.ffill().dropna()
    except:
        return pd.DataFrame()

# --- 計算指標函數 ---
def calculate_metrics(daily_values):
    # 1. 總報酬率
    total_ret = (daily_values.iloc[-1] / daily_values.iloc[0]) - 1
    
    # 計算日報酬
    daily_ret = daily_values.pct_change().dropna()
    
    # 2. 年化波動度 (假設 252 交易日)
    volatility = daily_ret.std() * (252 ** 0.5)
    
    # 3. 最大回撤 (Max Drawdown)
    roll_max = daily_values.cummax()
    drawdown = (daily_values - roll_max) / roll_max
    max_dd = drawdown.min()
    
    # 4. 夏普比率 (Sharpe Ratio, 假設無風險利率=0, 簡單版)
    # 為了避免短期數據年化失真，這裡用 (年化報酬 / 年化波動)
    days = (daily_values.index[-1] - daily_values.index[0]).days
    if days > 0:
        annual_ret = (1 + total_ret) ** (365.25 / days) - 1
    else:
        annual_ret = 0
        
    sharpe = annual_ret / volatility if volatility != 0 else 0
    
    return total_ret, max_dd, volatility, sharpe

# --- 主程式 ---
try:
    df = load_data(period)

    if not df.empty:
        # 轉台幣計價
        twd_prices = pd.DataFrame(index=df.index)
        if "USDTWD=X" in df.columns:
            fx = df["USDTWD=X"]
            for ticker in all_tickers_list:
                if ticker == "USDTWD=X": continue
                if ".TW" in ticker:
                    twd_prices[ticker] = df[ticker]
                else:
                    twd_prices[ticker] = df[ticker] * fx
        else:
            st.warning("無法取得匯率數據")
            st.stop()

        # 計算淨值與指標
        initial_capital = 1_000_000 
        portfolio_history = pd.DataFrame(index=twd_prices.index)
        stats_list = []

        start_prices = twd_prices.iloc[0]

        for name, weights in portfolios.items():
            # 計算持股
            units = {}
            valid_portfolio = True
            for ticker, w in weights.items():
                if ticker not in start_prices:
                    valid_portfolio = False
                    break
                units[ticker] = (initial_capital * w) / start_prices[ticker]
            
            if not valid_portfolio: continue

            # 每日市值
            daily_value = pd.Series(0, index=twd_prices.index)
            for ticker, unit in units.items():
                daily_value += twd_prices[ticker] * unit
            
            portfolio_history[name] = daily_value
            
            # 計算四大指標
            tot_ret, max_dd, vol, sharpe = calculate_metrics(daily_value)
            
            stats_list.append({
                "組合名稱": name,
                "最終資產": daily_value.iloc[-1],
                "總報酬率 (%)": tot_ret * 100,
                "最大回撤 (Max DD)": max_dd * 100,
                "波動度 (Vol)": vol * 100,
                "夏普值 (Sharpe)": sharpe
            })

        # --- 顯示介面 ---
        st.caption(f"起始資金: NT$ 1,000,000 | 匯率: {fx.iloc[-1]:.2f}")

        if stats_list:
            # 整理成 DataFrame 方便顯示
            stats_df = pd.DataFrame(stats_list)
            stats_df = stats_df.set_index("組合名稱")
            
            # 冠軍 (以總報酬排序)
            winner = stats_df.sort_values("總報酬率 (%)", ascending=False).iloc[0]
            st.success(f"🏆 獲利王：**{winner.name}** | 獲利: ${winner['最終資產'] - 1000000:,.0f} (+{winner['總報酬率 (%)']:.2f}%)")

            # 主要卡片區
            cols = st.columns(4)
            for i, (name, row) in enumerate(stats_df.iterrows()):
                with cols[i % 4]:
                    st.metric(
                        label=name,
                        value=f"${row['最終資產']:,.0f}",
                        delta=f"{row['總報酬率 (%)']:.2f}%"
                    )
            
            st.divider()
            
            # --- 詳細戰況分析表 ---
            st.subheader("📊 戰況分析表 (風險與體質)")
            
            # 格式化表格
            display_df = stats_df[['總報酬率 (%)', '最大回撤 (Max DD)', '波動度 (Vol)', '夏普值 (Sharpe)']].copy()
            
            # 使用 Streamlit 的 Column Config 來畫進度條
            st.dataframe(
                display_df.style.format("{:.2f}"),
                column_config={
                    "總報酬率 (%)": st.column_config.NumberColumn("總報酬率 %", format="%.2f %%"),
                    "最大回撤 (Max DD)": st.column_config.NumberColumn("最大回撤 %", format="%.2f %%", help="期間內資產從最高點滑落的最大幅度"),
                    "波動度 (Vol)": st.column_config.NumberColumn("年化波動度 %", format="%.2f %%", help="數值越大代表資產晃動越劇烈"),
                    "夏普值 (Sharpe)": st.column_config.NumberColumn("夏普值 (CP值)", format="%.2f", help="越高越好，代表承受單位風險獲得的超額報酬")
                },
                use_container_width=True
            )

            # 圖表
            st.subheader("📈 資產增長走勢")
            st.line_chart(portfolio_history)

    else:
        st.warning("⏳ 正在讀取數據... (若卡住請按手動刷新)")

except Exception as e:
    st.error(f"發生錯誤: {e}")

# --- 自動刷新 ---
if auto_refresh:
    time.sleep(60)
    st.rerun()
