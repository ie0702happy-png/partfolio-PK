import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

# --- 頁面設定 ---
st.set_page_config(page_title="百萬投資：多重宇宙大亂鬥", layout="wide")
st.title("💰 百萬投資：多重宇宙大亂鬥")
st.caption("🇺🇸 預設視角：美國人 (無稅務損耗) | 💰 本金：100 萬台幣 | ⚡ 採用多分頁架構")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    st.write("⏱️ **自動更新**")
    auto_refresh = st.toggle("開啟每 60 秒自動刷新", value=False)
    if auto_refresh:
        st.caption("⚠️ 啟動中...")
    
    st.divider()

    # 預設 "max"
    period = st.selectbox("回測時間範圍", ["YTD", "6mo", "1y", "2y", "5y", "max"], index=5)
    
    st.write("📉 **參數設定**")
    apply_tax = st.toggle("扣除美股 30% 股息稅", value=False, help="美國人視角請關閉。")
    
    if st.button("🔄 手動刷新"):
        st.rerun()

# --- 1. 定義所有投資組合 (總表) ---
portfolios_all = {
    "🍺 Ginger Ale (美股因子)": {
        "VOO": 0.30, "AVUV": 0.30, "VEA": 0.10, 
        "AVDV": 0.10, "VWO": 0.10, "AVES": 0.10
    },
    "🌊 清流君 Portfolio": {
        "VOO": 0.24, "AVUV": 0.12, "QMOM": 0.12, "VXUS": 0.12,
        "AVDV": 0.06, "IMOM": 0.06, "AVES": 0.08, "0050.TW": 0.20
    },
    "🇺🇸 S&P 500 (VOO)": {
        "VOO": 1.0
    },
    "🔰 你的組合 (英股優勢)": {
        "VWRA.L": 0.50, "AVGS.L": 0.30, "0050.TW": 0.20
    },
    "🌎 AVGE (單一因子)": {
        "AVGE": 1.0
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

# --- 2. 定義分組名單 ---

# 群組 A: 焦點對決 (您指定的 3 個)
focus_group_names = ["🍺 Ginger Ale (美股因子)", "🇺🇸 S&P 500 (VOO)", "🌊 清流君 Portfolio"]
portfolios_focus = {k: v for k, v in portfolios_all.items() if k in focus_group_names}

# 群組 B: 全員 (直接用 portfolios_all)

# 群組 C: 長線老將 (剔除年輕 ETF)
long_term_names = ["🇺🇸 S&P 500 (VOO)", "🇹🇼 0050 (台灣五十)", "🌐 VT (全球股市)", "₿ Bitcoin"]
portfolios_long = {k: v for k, v in portfolios_all.items() if k in long_term_names}


# --- 稅務損耗圖表 ---
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

# --- 核心邏輯函數 ---
def load_data(period):
    try:
        raw = yf.download(all_tickers_list, period=period, progress=False)
        if raw.empty: return pd.DataFrame()
        if 'Adj Close' in raw.columns: df = raw['Adj Close']
        elif 'Close' in raw.columns: df = raw['Close']
        else: df = raw
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df.ffill() # 這裡不 dropna，保留最大數據量
    except:
        return pd.DataFrame()

def calculate_portfolio_performance(df_input, target_portfolios, apply_tax_logic):
    # 1. 篩選該群組需要的代號
    needed_tickers = set()
    for p in target_portfolios.values():
        needed_tickers.update(p.keys())
    needed_tickers.add("USDTWD=X")
    
    # 2. 只取相關欄位並清除空值 (關鍵：不同群組的空值起始點不同)
    df_subset = df_input[[t for t in needed_tickers if t in df_input.columns]].copy()
    df_subset = df_subset.dropna() 
    
    if df_subset.empty: return None, None, None

    # 3. 稅務調整
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

    # 4. 匯率轉換
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

    # 5. 組合淨值計算
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
            "波動度 (Vol)": volatility * 100, # <--- 修正處：將 vol 改為 volatility
            "夏普值 (Sharpe)": sharpe
        })
        
    return stats_list, portfolio_history, twd_prices.index[0]

# --- 主程式 ---
try:
    df_raw = load_data(period)

    if not df_raw.empty:
        # 定義三個分頁
        tab1, tab2, tab3 = st.tabs(["🥊 焦點對決 (Ginger vs VOO vs 清流君)", "🔥 全員大亂鬥 (All)", "🦕 長線馬拉松 (10年以上)"])
        
        # --- TAB 1: 焦點對決 ---
        with tab1:
            st.subheader("📌 Ginger Ale vs S&P 500 vs 清流君")
            st.info("⚠️ 注意：因含 AVUV/QMOM 等因子 ETF，歷史起點約為 2019/09。")
            
            stats1, hist1, start1 = calculate_portfolio_performance(df_raw, portfolios_focus, apply_tax)
            
            if stats1:
                st.caption(f"📅 統計區間: {start1.date()} ~ 今")
                df_stats1 = pd.DataFrame(stats1).set_index("組合名稱")
                
                # 3欄顯示
                cols = st.columns(3)
                for i, (name, row) in enumerate(df_stats1.iterrows()):
                    with cols[i]:
                        st.metric(name, f"${row['最終資產']:,.0f}", f"{row['總報酬率 (%)']:.2f}%")
                
                st.line_chart(hist1)
                st.dataframe(df_stats1.style.format("{:.2f}"))

        # --- TAB 2: 全員大亂鬥 ---
        with tab2:
            st.subheader("⚔️ 所有投資組合一次排開")
            st.info("⚠️ 包含英股、VT 與所有組合。受限於最年輕的 ETF，歷史長度較短。")
            
            stats2, hist2, start2 = calculate_portfolio_performance(df_raw, portfolios_all, apply_tax)
            
            if stats2:
                st.caption(f"📅 統計區間: {start2.date()} ~ 今")
                df_stats2 = pd.DataFrame(stats2).set_index("組合名稱")
                winner2 = df_stats2.sort_values("總報酬率 (%)", ascending=False).iloc[0]
                st.success(f"🏆 本區獲利王：**{winner2.name}**")

                st.dataframe(df_stats2.style.format("{:.2f}"), use_container_width=True)
                st.line_chart(hist2)

        # --- TAB 3: 長線馬拉松 ---
        with tab3:
            st.subheader("⏳ 傳統資產長線回測 (剔除年輕因子)")
            st.info("✅ 已自動剔除 2019 年後成立的 ETF，呈現 VOO / 0050 / BTC 的長期真實歷史。")
            
            stats3, hist3, start3 = calculate_portfolio_performance(df_raw, portfolios_long, apply_tax)
            
            if stats3:
                st.caption(f"📅 統計區間: {start3.date()} ~ 今 (歷史大幅拉長！)")
                df_stats3 = pd.DataFrame(stats3).set_index("組合名稱")
                
                cols = st.columns(4)
                for i, (name, row) in enumerate(df_stats3.iterrows()):
                    with cols[i]:
                        st.metric(name, f"${row['最終資產']:,.0f}", f"{row['總報酬率 (%)']:.2f}%")
                
                st.line_chart(hist3)
                st.dataframe(df_stats3.style.format("{:.2f}"))

    else:
        st.warning("⏳ 數據讀取中...")

except Exception as e:
    st.error(f"發生錯誤: {e}")

if auto_refresh:
    time.sleep(60)
    st.rerun()
