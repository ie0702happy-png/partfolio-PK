import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="百萬投資組合大亂鬥", layout="wide")
st.title("💰 百萬台幣投資組合大亂鬥")
st.caption("起始資金: NT$ 1,000,000 | 全自動匯率換算 (TWD)")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    period = st.selectbox("回測時間範圍", ["YTD", "6mo", "1y", "2y", "5y", "max"], index=2)
    st.info("⚠️ 注意：回測起點將受限於『最晚上市』的那支 ETF (例如 AVGS/AVGE 較新)。")
    
    if st.button("🔄 刷新數據"):
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

# 提取所有需要下載的代號 (包含匯率)
all_tickers = set()
for p in portfolios.values():
    all_tickers.update(p.keys())
all_tickers_list = list(all_tickers) + ["USDTWD=X"]

# --- 核心邏輯 ---
def load_data(period):
    try:
        # 下載數據
        raw = yf.download(all_tickers_list, period=period, progress=False)
        
        # 處理欄位
        if 'Adj Close' in raw.columns:
            df = raw['Adj Close']
        elif 'Close' in raw.columns:
            df = raw['Close']
        else:
            df = raw

        # 處理 MultiIndex 欄位名稱
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            
        # 填補空值 (處理各國休市日不同)
        df = df.ffill()
        
        # 找出共同起點 (dropna 會切掉 AVGS 上市前的日期)
        df = df.dropna()
        
        return df
    except Exception as e:
        st.error(f"數據下載失敗: {e}")
        return pd.DataFrame()

# --- 計算與顯示 ---
df = load_data(period)

if not df.empty:
    # 1. 將所有資產價格轉換為台幣 (TWD)
    # 邏輯：如果是台股(0050)維持原價，如果是外幣(美/英)則乘上匯率
    twd_prices = pd.DataFrame(index=df.index)
    fx = df["USDTWD=X"]
    
    for ticker in all_tickers_list:
        if ticker == "USDTWD=X": continue
        
        if ".TW" in ticker:
            twd_prices[ticker] = df[ticker] # 台幣計價不用乘
        else:
            twd_prices[ticker] = df[ticker] * fx # 美元計價乘匯率

    # 2. 計算各投資組合淨值曲線
    initial_capital = 1_000_000 # 一百萬台幣
    portfolio_history = pd.DataFrame(index=twd_prices.index)
    
    # 用來存儲最終結果的列表
    summary_stats = []

    for name, weights in portfolios.items():
        # 計算該組合在第 0 天各資產買了多少單位 (股數)
        # 股數 = (總資金 * 權重) / 第 0 天股價
        start_prices = twd_prices.iloc[0]
        units = {}
        for ticker, w in weights.items():
            units[ticker] = (initial_capital * w) / start_prices[ticker]
            
        # 計算每一天的總市值
        # 市值 = sum(持有股數 * 當天股價)
        daily_value = pd.Series(0, index=twd_prices.index)
        for ticker, unit in units.items():
            daily_value += twd_prices[ticker] * unit
            
        portfolio_history[name] = daily_value
        
        # 統計數據
        final_val = daily_value.iloc[-1]
        ret = (final_val - initial_capital) / initial_capital * 100
        summary_stats.append({
            "組合名稱": name,
            "最終資產 (TWD)": final_val,
            "報酬率": ret
        })

    # --- 介面呈現 ---
    
    # 頂部：顯示冠軍
    sorted_stats = sorted(summary_stats, key=lambda x: x["最終資產 (TWD)"], reverse=True)
    winner = sorted_stats[0]
    st.success(f"🏆 目前冠軍：**{winner['組合名稱']}** | 獲利: {winner['最終資產 (TWD)'] - 1000000:,.0f} 元 ({winner['報酬率']:.2f}%)")

    # 指標卡片
    cols = st.columns(4)
    for i, stats in enumerate(summary_stats):
        with cols[i]:
            delta = stats["最終資產 (TWD)"] - 1000000
            st.metric(
                label=stats["組合名稱"],
                value=f"${stats['最終資產 (TWD)']:,.0f}",
                delta=f"{stats['報酬率']:.2f}%"
            )

    # 走勢圖
    st.divider()
    st.subheader("📈 資產增長走勢 (起始 100 萬)")
    st.line_chart(portfolio_history)

    # 詳細表格
    with st.expander("查看每日淨值數據"):
        st.dataframe(portfolio_history.style.format("{:,.0f}"))

else:
    st.warning("數據讀取中，請稍候...")
