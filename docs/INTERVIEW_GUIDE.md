# Interview Guide (Hinglish explanations, English technical terms)

Sirf wahi claim karo jo project mein actually implemented hai. Neeche ka "Don't claim" section zaroor padho.

## 30-second pitch
"Maine ek Sales Intelligent System banaya hai: CSV/Excel upload hoti hai, data validate aur clean hota hai,
phir Streamlit dashboard mein KPIs, product/region/customer analysis, growth, Pareto, RFM segments,
backtested forecast aur downloadable Excel report milti hai. Demo ke liye maine synthetic data generator
banaya, aur calculations ko unit tests se verify kiya."

## Walkthrough: data flow
1. `data_loader.py` file ko text ki tarah padhta hai aur required columns check karta hai (galat file par friendly error).
2. `data_cleaning.py` types convert karta hai, bad rows hataata hai **aur count karke report deta hai** (silently delete nahi).
3. Derived columns: revenue, profit, month, quarter.
4. Sidebar filters `apply_filters` se rows kam karte hain; baaki sab functions filtered data par chalte hain.
5. `analytics.py` sirf calculation karta hai (testable); `visualizations.py` sirf draw karta hai; `app.py` sirf UI.

## Beginner questions
**Q: AOV kaise calculate kiya?** Total revenue ko *distinct orders* se divide kiya, rows se nahi, kyunki ek order mein kai product rows hote hain.
**Q: Revenue aur profit mein farq?** Revenue = bikri (discount ke baad). Profit = revenue - product cost. Overheads aur returns model nahi hain.
**Q: Cleaning mein kya kiya?** Dates/quantity/price validate, duplicates remove, missing region = "Unknown", sab ka count Data Quality tab mein.
**Q: Streamlit kyun?** Pure Python mein fast interactive dashboard, HTML/JS ki zaroorat nahi.

## Intermediate questions
**Q: MoM/YoY ke liye missing months ka kya?** Months ko 0 se fill kiya, warna `shift(12)` galat month se compare karta.
**Q: Pareto analysis kya batata hai?** Kitne products 80% revenue dete hain; concentration risk dikhata hai.
**Q: Filters kaise kaam karte hain?** Ek boolean mask: date range (end date inclusive) AND region AND category AND product. Empty selection = zero rows, aur app warning dikhata hai.
**Q: Calculations kaise validate kiye?** 4-row dataset par hand-calculated values (revenue 595, orders 3, AOV 595/3), aur synthetic data par independent NumPy calculation se match kiya.
**Q: Caching?** `st.cache_data` file load/clean ko cache karta hai taaki har filter click par dobara read na ho.

## Advanced questions
**Q: Forecast kaise kiya aur kitna reliable hai?** Linear trend + monthly seasonality (24+ months chahiye). Last 6 months holdout par test kiya aur "same month last year" baseline se compare kiya. Dashboard bataata hai ki beat kiya ya nahi. Limitation: promotions/shocks nahi dikhte, interval approximate hai.
**Q: Machine Learning kyun nahi?** Ek hi target (monthly revenue), kam data points; complex model overfit karta aur value nahi deta. ML tab jodna chahiye jab meaningful target (jaise churn) aur enough labelled data ho.
**Q: RFM ML hai?** Nahi, rule-based hai. Percentile scores (ties ko same score) aur fixed rules se segments.
**Q: Data leakage ka khatra?** Forecast backtest mein sirf training months se fit hota hai; holdout months fit mein shamil nahi.
**Q: Scale kaise karoge?** Database (MySQL/PostgreSQL) mein aggregate karo, pre-aggregated tables use karo, ya DuckDB/Polars.

## Challenges you can honestly discuss
* Multi-row orders mein sahi grain (AOV).
* Partial months se galat growth (isliye incomplete last month ignore hota hai insights/forecast mein).
* Repeat-purchase metric filter par depend karta hai.
* Mixed date formats ka silent NaT: isliye invalid dates count hoti hain.

## Don't claim
* Real business results (data synthetic hai).
* "Production-ready" ya "deployed" (nahi hai).
* Machine learning models / MySQL integration (implemented nahi).
* Browser/performance testing (pehle khud run karke verify karo).

## Practice tasks (khud likho, copy mat karo)
1. `analytics.py` mein `average_items_per_order` function likho (rows / distinct orders) aur uska test.
2. Dashboard mein "Top 10 customers by region" table jodo.
3. Cleaning mein negative discount ko row-drop ki jagah 0 set karne ka option banao aur report mein count karo.
4. `config.py` se currency badal kar `$` karo aur check karo kahan-kahan reflect hota hai.
