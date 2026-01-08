import streamlit as st
import yfinance as yf
import pandas as pd
import time # 引入時間模組

# --- 頁面設定 ---
st.set_page_config(page_title="百萬投資組合大亂鬥", layout="wide")
st.title("💰 百萬台幣投資組合大亂鬥")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 1. 自動刷新開關
    st.write("⏱️ **自動更新**")
    auto_refresh = st.toggle("開啟每 60 秒自動刷新", value=False)
    if auto_refresh:
        st.caption("⚠️ 啟動中...右上角會顯示 Running")
    
    st.divider()

    # 2. 其他設定
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
    "🌎 AVGE (單一)": {
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
        
        # 欄位處理
        if 'Adj Close' in raw.columns: df = raw['Adj Close']
        elif 'Close' in raw.columns: df = raw['Close']
        else: df = raw

        # 處理 MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            
        return df.ffill().dropna()
    except:
        return pd.DataFrame()

# --- 計算與顯示 ---
try:
    df = load_data(period)

    if not df.empty:
        # 1. 轉台幣計價
        twd_prices = pd.DataFrame(index=df.index)
        if "USDTWD=X" in df.columns:
            fx = df["USDTWD=X"]
            for ticker in all_tickers_list:
                if ticker == "USDTWD=X": continue
                # 台股維持原價，外幣乘匯率
                if ".TW" in ticker:
                    twd_prices[ticker] = df[ticker]
                else:
                    twd_prices[ticker] = df[ticker] * fx
        else:
            st.warning("無法取得匯率數據")
            st.stop()

        # 2. 計算淨值
        initial_capital = 1_000_000 
        portfolio_history = pd.DataFrame(index=twd_prices.index)
        summary_stats = []

        start_prices = twd_prices.iloc[0]

        for name, weights in portfolios.items():
            # 計算持股數 (Buy and Hold)
            units = {}
            valid_portfolio = True
            for ticker, w in weights.items():
                if ticker not in start_prices:
                    valid_portfolio = False
                    break
                units[ticker] = (initial_capital * w) / start_prices[ticker]
            
            if not valid_portfolio: continue

            # 計算每日市值
            daily_value = pd.Series(0, index=twd_prices.index)
            for ticker, unit in units.items():
                daily_value += twd_prices[ticker] * unit
                
            portfolio_history[name] = daily_value
            
            # 統計
            final_val = daily_value.iloc[-1]
            ret = (final_val - initial_capital) / initial_capital * 100
            summary_stats.append({
                "組合名稱": name,
                "最終資產": final_val,
                "報酬率": ret
            })

        # --- 顯示介面 ---
        st.caption(f"起始資金: NT$ 1,000,000 | 匯率: {fx.iloc[-1]:.2f}")

        if summary_stats:
            # 冠軍
            sorted_stats = sorted(summary_stats, key=lambda x: x["最終資產"], reverse=True)
            winner = sorted_stats[0]
            st.success(f"🏆 目前冠軍：**{winner['組合名稱']}** | 獲利: ${winner['最終資產'] - 1000000:,.0f} ({winner['報酬率']:.2f}%)")

            # 詳細卡片
            cols = st.columns(4)
            for i, stats in enumerate(summary_stats):
                with cols[i % 4]: # 防止超過欄位數
                    st.metric(
                        label=stats["組合名稱"],
                        value=f"${stats['最終資產']:,.0f}",
                        delta=f"{stats['報酬率']:.2f}%"
                    )

            # 圖表
            st.divider()
            st.subheader("📈 資產增長走勢")
            st.line_chart(portfolio_history)
            
            with st.expander("查看詳細數據"):
                st.dataframe(portfolio_history.style.format("{:,.0f}"))

    else:
        st.warning("⏳ 正在連線 Yahoo Finance 讀取數據... (若卡住請按手動刷新)")

except Exception as e:
    st.error(f"暫時無法連線，將自動重試... ({e})")

# --- 自動刷新邏輯 ---
if auto_refresh:
    time.sleep(60) # 等待 60 秒
    st.rerun()
