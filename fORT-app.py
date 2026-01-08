import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

# --- 頁面設定 ---
st.set_page_config(page_title="因子大亂鬥：Ginger Ale vs 清流君 vs S&P500", layout="wide")
st.title("🥊 頂上對決：Ginger Ale vs 清流君 vs S&P 500")
st.caption("🇺🇸 模擬美國人視角 (無稅務損耗) | ⏱️ 數據範圍：Max (最長歷史) | 💰 本金：100 萬台幣")

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
    # 預設關閉稅務損耗 (模擬美國人/稅前報酬)
    apply_tax = st.toggle("扣除美股 30% 股息稅", value=False, help="美國人視角請關閉。若開啟，則模擬台灣人被扣 30% 股息稅。")
    
    if st.button("🔄 手動刷新"):
        st.rerun()

# --- 定義投資組合 (加入清流君) ---
portfolios = {
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
    }
}

# --- 稅務損耗估算 (Tax Drag) ---
# 保留完整清單，以防使用者手動開啟稅務計算
tax_drag_map = {
    "VOO": 0.015 * 0.30,
    "VT": 0.020 * 0.30,
    "VXUS": 0.030 * 0.30,
    "VEA": 0.030 * 0.30,
    "VWO": 0.028 * 0.30,
    "AVUV": 0.018 * 0.30, 
    "AVDV": 0.032 * 0.30,
    "AVES": 0.030 * 0.30,
    "AVGE": 0.022 * 0.30,
    "QMOM": 0.008 * 0.30,
    "IMOM": 0.010 * 0.30,
    "BTC-USD": 0.0,
    "DEFAULT_US": 0.015 * 0.30
}

# 提取代號
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

def calculate_metrics(daily_values):
    total_ret = (daily_values.iloc[-1] / daily_values.iloc[0]) - 1
    daily_ret = daily_values.pct_change().dropna()
    volatility = daily_ret.std() * (252 ** 0.5)
    
    roll_max = daily_values.cummax()
    drawdown = (daily_values - roll_max) / roll_max
    max_dd = drawdown.min()
    
    days = (daily_values.index[-1] - daily_values.index[0]).days
    annual_ret = (1 + total_ret) ** (365.25 / days) - 1 if days > 0 else 0
    sharpe = annual_ret / volatility if volatility != 0 else 0
    
    return total_ret, max_dd, volatility, sharpe

# --- 主程式 ---
try:
    df = load_data(period)

    if not df.empty:
        # 1. 處理稅務損耗
        adjusted_df = df.copy()
        
        if apply_tax:
            for ticker in adjusted_df.columns:
                if ticker == "USDTWD=X": continue
                # 排除 .L (英股) .TW (台股) BTC (虛擬幣)
                if ".L" not in ticker and ".TW" not in ticker and "BTC" not in ticker:
                    drag = tax_drag_map.get(ticker, tax_drag_map["DEFAULT_US"])
                    daily_drag = drag / 252
                    returns = adjusted_df[ticker].pct_change()
                    taxed_returns = returns - daily_drag
                    start_price = adjusted_df[ticker].iloc[0]
                    adjusted_df[ticker] = start_price * (1 + taxed_returns.fillna(0)).cumprod()

        # 2. 轉台幣計價
        twd_prices = pd.DataFrame(index=adjusted_df.index)
        if "USDTWD=X" in df.columns:
            fx = df["USDTWD=X"]
            for ticker in all_tickers_list:
                if ticker == "USDTWD=X": continue
                
                # 台股不需要乘匯率，其他需要
                if ".TW" in ticker:
                    twd_prices[ticker] = adjusted_df[ticker]
                else:
                    twd_prices[ticker] = adjusted_df[ticker] * fx
        else:
            st.error("找不到匯率數據")
            st.stop()

        # 3. 組合計算
        initial_capital = 1_000_000 
        portfolio_history = pd.DataFrame(index=twd_prices.index)
        stats_list = []
        # 確保起始點一致
        start_prices = twd_prices.iloc[0]

        for name, weights in portfolios.items():
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
            
            # 指標計算
            tot_ret, max_dd, vol, sharpe = calculate_metrics(daily_val)
            stats_list.append({
                "組合名稱": name,
                "最終資產": daily_val.iloc[-1],
                "總報酬率 (%)": tot_ret * 100,
                "最大回撤 (Max DD)": max_dd * 100,
                "波動度 (Vol)": vol * 100,
                "夏普值 (Sharpe)": sharpe
            })

        # --- 顯示介面 ---
        st.caption(f"📅 數據區間: {twd_prices.index[0].date()} 至 {twd_prices.index[-1].date()}")

        if stats_list:
            stats_df = pd.DataFrame(stats_list).set_index("組合名稱")
            winner = stats_df.sort_values("總報酬率 (%)", ascending=False).iloc[0]
            
            st.success(f"🏆 獲利王：**{winner.name}** | 最終資產: ${winner['最終資產']:,.0f}")

            # 修改為 3 欄顯示
            cols = st.columns(3)
            for i, (name, row) in enumerate(stats_df.iterrows()):
                with cols[i % 3]:
                    st.metric(name, f"${row['最終資產']:,.0f}", f"{row['總報酬率 (%)']:.2f}%")
            
            st.divider()
            
            st.subheader("📊 績效分析 (美國人視角)")
            st.dataframe(
                stats_df[['總報酬率 (%)', '最大回撤 (Max DD)', '波動度 (Vol)', '夏普值 (Sharpe)']].style.format("{:.2f}"),
                use_container_width=True
            )

            st.line_chart(portfolio_history)
            
            with st.expander("ℹ️ 組合詳情與說明 (點擊展開)"):
                st.markdown("""
                1.  **美國人視角 (US Person)**：
                    * 已預設關閉 30% 股息預扣稅模擬。
                2.  **數據長度限制**：
                    * 雖然選擇 Max，但因為 **Ginger Ale** 與 **清流君** 組合中皆包含年輕的 ETF (如 AVUV, AVDV, QMOM 等，約在 2019/09 後成立)，**回測起點將受限於 2019 年**。
                    * 0050.TW 雖有長歷史，但會被其他短歷史的 ETF 遷就，一併從 2019 開始計算。
                3.  **組合成分**：
                    * **🍺 Ginger Ale**: VOO, AVUV, VEA, AVDV, VWO, AVES
                    * **🌊 清流君**: VOO, AVUV, QMOM, VXUS, AVDV, IMOM, AVES, 0050.TW
                    * **🇺🇸 S&P 500**: VOO
                """)

    else:
        st.warning("⏳ 數據讀取中... (若等待過久可能是 Yahoo API 擁塞，請稍後重試)")

except Exception as e:
    st.error(f"發生錯誤: {e}")

if auto_refresh:
    time.sleep(60)
    st.rerun()
