import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

# --- 頁面設定 ---
st.set_page_config(page_title="百萬投資大亂鬥 (台灣真實版)", layout="wide")
st.title("💰 百萬台幣投資組合大亂鬥 (含稅後真實報酬)")
st.caption("🇹🇼 模擬台灣人視角：自動扣除美股 30% 股息稅 (Tax Drag) | 內扣費用已含於股價")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    st.write("⏱️ **自動更新**")
    auto_refresh = st.toggle("開啟每 60 秒自動刷新", value=False)
    if auto_refresh:
        st.caption("⚠️ 啟動中...")
    
    st.divider()

    period = st.selectbox("回測時間範圍", ["YTD", "6mo", "1y", "2y", "5y", "max"], index=2)
    
    st.write("📉 **成本參數設定**")
    apply_tax = st.toggle("扣除美股 30% 股息稅", value=True, help="開啟後，美股 ETF 會根據估算殖利率扣除 30% 稅金損耗。英股與台股不扣。")
    
    if st.button("🔄 手動刷新"):
        st.rerun()

# --- 定義投資組合 ---
portfolios = {
    "🔰 你的組合 (英股優勢)": {
        "VWRA.L": 0.50, "AVGS.L": 0.30, "0050.TW": 0.20
    },
    "🍺 Ginger Ale (美股因子)": {
        "VOO": 0.30, "AVUV": 0.30, "VEA": 0.10, 
        "AVDV": 0.10, "VWO": 0.10, "AVES": 0.10
    },
    "🌊 清流君 Portfolio": {
        "VOO": 0.24, "AVUV": 0.12, "QMOM": 0.12, "VXUS": 0.12,
        "AVDV": 0.06, "IMOM": 0.06, "AVES": 0.08, "0050.TW": 0.20
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

# --- 稅務損耗估算 (Tax Drag) ---
# 邏輯：估算年化殖利率 (Yield)，台灣人拿不到的那 30% 就是每日的成本
# 例如：VOO 殖利率 1.5%，稅 30% -> 每年損耗 0.45%
# 英股 (L) 結尾與台股 (TW) 結尾設為 0，因為無預扣或已內含
tax_drag_map = {
    # 美股大盤/全市場
    "VOO": 0.015 * 0.30,  # Yield ~1.5%
    "VT": 0.020 * 0.30,   # Yield ~2.0%
    "VXUS": 0.030 * 0.30, # 非美通常配息高 ~3.0%
    "VEA": 0.030 * 0.30,
    "VWO": 0.028 * 0.30,
    
    # 因子類 (價值股配息通常較高)
    "AVUV": 0.018 * 0.30, 
    "AVDV": 0.032 * 0.30,
    "AVES": 0.030 * 0.30,
    "AVGE": 0.022 * 0.30, # 混合
    
    # 動能類 (配息少)
    "QMOM": 0.008 * 0.30,
    "IMOM": 0.010 * 0.30,
    
    # 虛擬貨幣
    "BTC-USD": 0.0,
    
    # 預設
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
        
        # 優先使用 Adj Close (含息報酬)，我們再手動扣除稅
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
        # 1. 處理稅務損耗 (Tax Drag Adjustment)
        # 我們將每日報酬率減去 (年化損耗 / 252)
        adjusted_df = df.copy()
        
        if apply_tax:
            for ticker in adjusted_df.columns:
                if ticker == "USDTWD=X": continue
                
                # 判斷是否為美股 (簡單判斷：沒有 .L 或 .TW 且不是 BTC)
                if ".L" not in ticker and ".TW" not in ticker and "BTC" not in ticker:
                    # 取得該代號的損耗率，若無則用預設
                    drag = tax_drag_map.get(ticker, tax_drag_map["DEFAULT_US"])
                    daily_drag = drag / 252
                    
                    # 計算每日報酬並扣除損耗
                    returns = adjusted_df[ticker].pct_change()
                    taxed_returns = returns - daily_drag
                    
                    # 重建價格曲線 (從第一天價格開始推算)
                    # 這裡使用 cumprod (累積乘積)
                    # Price_t = Price_0 * (1 + r_1) * (1 + r_2)...
                    start_price = adjusted_df[ticker].iloc[0]
                    adjusted_df[ticker] = start_price * (1 + taxed_returns.fillna(0)).cumprod()

        # 2. 轉台幣計價
        twd_prices = pd.DataFrame(index=adjusted_df.index)
        if "USDTWD=X" in df.columns:
            fx = df["USDTWD=X"]
            for ticker in all_tickers_list:
                if ticker == "USDTWD=X": continue
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
        st.caption(f"匯率: {fx.iloc[-1]:.2f} TWD/USD | 稅務調整狀態: {'✅ 開啟 (美股扣除 30% 股息稅)' if apply_tax else '❌ 關閉 (稅前報酬)'}")

        if stats_list:
            stats_df = pd.DataFrame(stats_list).set_index("組合名稱")
            winner = stats_df.sort_values("總報酬率 (%)", ascending=False).iloc[0]
            
            st.success(f"🏆 真實獲利王：**{winner.name}** | 最終資產: ${winner['最終資產']:,.0f}")

            # 4欄顯示
            cols = st.columns(4)
            for i, (name, row) in enumerate(stats_df.iterrows()):
                with cols[i % 4]:
                    st.metric(name, f"${row['最終資產']:,.0f}", f"{row['總報酬率 (%)']:.2f}%")
            
            st.divider()
            
            # 表格
            st.subheader("📊 戰況分析表 (已扣除稅金損耗)")
            st.dataframe(
                stats_df[['總報酬率 (%)', '最大回撤 (Max DD)', '波動度 (Vol)', '夏普值 (Sharpe)']].style.format("{:.2f}"),
                column_config={
                    "總報酬率 (%)": st.column_config.NumberColumn("稅後總報酬 %", format="%.2f %%"),
                    "最大回撤 (Max DD)": st.column_config.NumberColumn("最大回撤 %", format="%.2f %%"),
                    "夏普值 (Sharpe)": st.column_config.NumberColumn("夏普值", format="%.2f")
                },
                use_container_width=True
            )

            st.line_chart(portfolio_history)
            
            # 稅務說明 Expander
            with st.expander("ℹ️ 關於「真實成本」的計算細節 (點擊展開)"):
                st.markdown("""
                **此模式更接近台灣投資人的真實帳戶：**
                
                1.  **內扣費用 (Expense Ratio)**：
                    * 歷史股價 (NAV) **已經扣除** 了基金管理費，因此不需要額外計算，否則會重複扣款。
                2.  **股息稅 (Dividend Tax)**：
                    * **🇺🇸 美股 (VOO, AVUV...)**：根據各 ETF 的殖利率，程式自動每天扣除 **30% 的預扣稅** (Tax Drag)。
                        * *例如：AVDV 殖利率約 3.2%，每年會被稅吃掉約 0.96% 的報酬。*
                    * **🇮🇪 英股 (VWRA, AVGS)**：愛爾蘭註冊，對台灣人 **無預扣稅** (0%)，具有稅務優勢。
                    * **🇹🇼 台股 (0050)**：假設股息再投入，暫不計算個人綜所稅 (因人而異)。
                3.  **匯率**：
                    * 所有美元/英鎊資產皆以當日 `USDTWD` 匯率換算為台幣。
                """)

    else:
        st.warning("⏳ 數據讀取中...")

except Exception as e:
    st.error(f"發生錯誤: {e}")

if auto_refresh:
    time.sleep(60)
    st.rerun()
