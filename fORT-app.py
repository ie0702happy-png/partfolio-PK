import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

# --- 頁面設定 ---
st.set_page_config(page_title="百萬投資：雙時空大亂鬥", layout="wide")
st.title("💰 百萬投資：雙時空大亂鬥")
st.caption("🇺🇸 預設視角：美國人 (無稅務損耗) | ⚡ 解決回測長度問題：採用雙分頁設計")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    st.write("⏱️ **自動更新**")
    auto_refresh = st.toggle("開啟每 60 秒自動刷新", value=False)
    if auto_refresh:
        st.caption("⚠️ 啟動中...")
    
    st.divider()

    # 預設索引設為 5 (對應 "max")
    period = st.selectbox("回測時間範圍", ["YTD", "6mo", "1y", "2y", "5y", "max"], index=5)
    
    st.write("📉 **參數設定**")
    apply_tax = st.toggle("扣除美股 30% 股息稅", value=False, help="美國人視角請關閉。")
    
    if st.button("🔄 手動刷新"):
        st.rerun()

# --- 定義所有投資組合 ---
portfolios_all = {
    "🍺 Ginger Ale (美股因子)": {
        "VOO": 0.30, "AVUV": 0.30, "VEA": 0.10, 
        "AVDV": 0.10, "VWO": 0.10, "AVES": 0.10
    },
    "🌊 清流君 Portfolio": {
        "VOO": 0.24, "AVUV": 0.12, "QMOM": 0.12, "VXUS": 0.12,
        "AVDV": 0.06, "IMOM": 0.06, "AVES": 0.08, "0050.TW": 0.20
    },
    "🔰 你的組合 (英股優勢)": {
        "VWRA.L": 0.50, "AVGS.L": 0.30, "0050.TW": 0.20
    },
    "🌎 AVGE (單一因子)": {
        "AVGE": 1.0
    },
    "🇺🇸 S&P 500 (VOO)": {
        "VOO": 1.0
    },
    "🇹🇼 0050 (台灣五十)": {
        "0050.TW": 1.0
    },
    "🌐 VT (全球股市)": {
        "VT": 1.0
    },
    "₿ Bitcoin": {
        "BTC-USD": 1.0
    }
}

# --- 定義長線選手 (剔除 2019 後才成立的因子 ETF) ---
# 這些標的擁有較長的歷史，可以單獨拉出來跑長線
long_term_candidates = ["🇺🇸 S&P 500 (VOO)", "🇹🇼 0050 (台灣五十)", "🌐 VT (全球股市)", "₿ Bitcoin"]
portfolios_long = {k: v for k, v in portfolios_all.items() if k in long_term_candidates}

# --- 稅務損耗估算 (Tax Drag) ---
tax_drag_map = {
    "VOO": 0.015 * 0.30, "VT": 0.020 * 0.30, "VXUS": 0.030 * 0.30,
    "VEA": 0.030 * 0.30, "VWO": 0.028 * 0.30, "AVUV": 0.018 * 0.30, 
    "AVDV": 0.032 * 0.30, "AVES": 0.030 * 0.30, "AVGE": 0.022 * 0.30,
    "QMOM": 0.008 * 0.30, "IMOM": 0.010 * 0.30, "BTC-USD": 0.0,
    "0050.TW": 0.0, "VWRA.L": 0.0, "AVGS.L": 0.0, "DEFAULT_US": 0.015 * 0.30
}

# 提取所有代號
all_tickers = set()
for p in portfolios_all.values():
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
        # 注意：這裡先不 dropna，留到後面根據組合需求再切
        return df.ffill() 
    except:
        return pd.DataFrame()

def calculate_portfolio_performance(df_input, target_portfolios, apply_tax_logic):
    # 1. 針對該組別所需的代號進行過濾與 dropna (關鍵步驟：確保長線組別不被短線拖累)
    needed_tickers = set()
    for p in target_portfolios.values():
        needed_tickers.update(p.keys())
    needed_tickers.add("USDTWD=X")
    
    # 只取需要的欄位
    df_subset = df_input[[t for t in needed_tickers if t in df_input.columns]].copy()
    df_subset = df_subset.dropna() # 這裡 dropna 只會切掉該組別最年輕成員之前的數據
    
    if df_subset.empty: return None, None, None

    # 2. 稅務調整
    if apply_tax_logic:
        for ticker in df_subset.columns:
            if ticker == "USDTWD=X": continue
            if ".L" not in ticker and ".TW" not in ticker and "BTC" not in ticker:
                drag = tax_drag_map.get(ticker, tax_drag_map["DEFAULT_US"])
                daily_drag = drag / 252
                returns = df_subset[ticker].pct_change()
                taxed_returns = returns - daily_drag
                start_price = df_subset[ticker].iloc[0]
                df_subset[ticker] = start_price * (1 + taxed_returns.fillna(0)).cumprod()

    # 3. 轉台幣
    twd_prices = pd.DataFrame(index=df_subset.index)
    if "USDTWD=X" in df_subset.columns:
        fx = df_subset["USDTWD=X"]
        for ticker in df_subset.columns:
            if ticker == "USDTWD=X": continue
            if ".TW" in ticker:
                twd_prices[ticker] = df_subset[ticker]
            else:
                twd_prices[ticker] = df_subset[ticker] * fx
    else:
        return None, None, None

    # 4. 組合計算
    initial_capital = 1_000_000
    portfolio_history = pd.DataFrame(index=twd_prices.index)
    stats_list = []
    start_prices = twd_prices.iloc[0]

    for name, weights in target_portfolios.items():
        units = {}
        valid = True
        for ticker, w in weights.items():
            if ticker not in start_prices:
                valid = False; break
            units[ticker] = (initial_capital * w) / start_prices[ticker]
        
        if not valid: continue

        daily_val = pd.Series(0, index=twd_prices.index)
        for ticker, unit in units.items():
            daily_val += twd_prices[ticker] * unit
        
        portfolio_history[name] = daily_val
        
        # 指標
        total_ret = (daily_val.iloc[-1] / daily_val.iloc[0]) - 1
        daily_ret = daily_val.pct_change().dropna()
        volatility = daily_ret.std() * (252 ** 0.5)
        
        roll_max = daily_val.cummax()
        drawdown = (daily_val - roll_max) / roll_max
        max_dd = drawdown.min()
        
        days = (daily_val.index[-1] - daily_val.index[0]).days
        annual_ret = (1 + total_ret) ** (365.25 / days) - 1 if days > 0 else 0
        sharpe = annual_ret / volatility if volatility != 0 else 0
        
        stats_list.append({
            "組合名稱": name,
            "最終資產": daily_val.iloc[-1],
            "總報酬率 (%)": total_ret * 100,
            "最大回撤 (Max DD)": max_dd * 100,
            "波動度 (Vol)": vol * 100,
            "夏普值 (Sharpe)": sharpe
        })
        
    return stats_list, portfolio_history, twd_prices.index[0]

# --- 主程式 ---
try:
    df_raw = load_data(period)

    if not df_raw.empty:
        # 建立兩個分頁
        tab1, tab2 = st.tabs(["🔥 因子新星大亂鬥 (含 Ginger Ale/清流君)", "🦕 老牌資產馬拉松 (VOO/0050/BTC)"])
        
        # --- TAB 1: 所有組合 (被短歷史限制) ---
        with tab1:
            st.info("此分頁包含所有因子組合。因 AVUV/QMOM/VWRA 成立時間較短，歷史數據起點約在 **2019 下半年**。")
            stats1, hist1, start_date1 = calculate_portfolio_performance(df_raw, portfolios_all, apply_tax)
            
            if stats1:
                st.caption(f"📅 數據區間: {start_date1.date()} 至 今")
                df_stats1 = pd.DataFrame(stats1).set_index("組合名稱")
                
                # 找出贏家
                winner1 = df_stats1.sort_values("總報酬率 (%)", ascending=False).iloc[0]
                st.success(f"🏆 短期獲利王：**{winner1.name}** | 報酬率: {winner1['總報酬率 (%)']:.2f}%")

                cols = st.columns(4)
                for i, (name, row) in enumerate(df_stats1.iterrows()):
                    with cols[i % 4]:
                        st.metric(name, f"${row['最終資產']:,.0f}", f"{row['總報酬率 (%)']:.2f}%")
                
                st.line_chart(hist1)
                st.dataframe(df_stats1.style.format("{:.2f}"))

        # --- TAB 2: 長線組合 (不受短歷史限制) ---
        with tab2:
            st.info("此分頁 **排除了** 年輕的因子 ETF，專門顯示傳統資產的長線歷史 (起點取決於 VOO 或 BTC 的歷史)。")
            stats2, hist2, start_date2 = calculate_portfolio_performance(df_raw, portfolios_long, apply_tax)
            
            if stats2:
                st.caption(f"📅 數據區間: {start_date2.date()} 至 今 (歷史長度大幅增加！)")
                df_stats2 = pd.DataFrame(stats2).set_index("組合名稱")
                
                winner2 = df_stats2.sort_values("總報酬率 (%)", ascending=False).iloc[0]
                st.success(f"🏆 長期獲利王：**{winner2.name}** | 報酬率: {winner2['總報酬率 (%)']:.2f}%")

                cols = st.columns(4)
                for i, (name, row) in enumerate(df_stats2.iterrows()):
                    with cols[i % 4]:
                        st.metric(name, f"${row['最終資產']:,.0f}", f"{row['總報酬率 (%)']:.2f}%")
                
                st.line_chart(hist2)
                st.dataframe(df_stats2.style.format("{:.2f}"))

    else:
        st.warning("⏳ 數據讀取中...")

except Exception as e:
    st.error(f"發生錯誤: {e}")

if auto_refresh:
    time.sleep(60)
    st.rerun()
