"""Gold stock-transfer monitor — desktop build.

Run:  python ingest.py --synthetic   (once, or --all for live data)
      streamlit run app.py

Design contract (reasoning in the companion notebook):
  - solid = reported, dashed = estimated; one colour per country everywhere
  - the same event rules on every time axis; labels only on the dominant charts
  - one bordered region (the KPI strip); whitespace does all other grouping
  - one dominant chart per tab: P1 carries Declared, P4 carries Inferred
"""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import design as dz

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="Gold stock-transfer monitor",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- chrome/css --
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400;1,6..72,500&family=Archivo:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, li {
  font-family: 'Archivo', system-ui, sans-serif;
  font-variant-numeric: tabular-nums;
}
.stApp { background: #fbfbf8; color: #1c1c18; }
.block-container { max-width: 1180px; padding-top: 1.2rem; padding-bottom: 0.2rem; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

h1 { font-family: 'Newsreader', serif; font-weight: 500; letter-spacing: -.01em;
     font-size: 2.5rem; margin-bottom: 0; }
h3 { font-family: 'Newsreader', serif; font-style: italic; font-weight: 500;
     font-size: 1.35rem; margin-bottom: 0; }
.stCaption, [data-testid="stCaptionContainer"] { color: #8c8c84; }

/* tabs: underline grammar, gold for the active page */
.stTabs [data-baseweb="tab-list"] { gap: 30px; border-bottom: 1px solid #ecece5; }
.stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 500; color: #8c8c84;
  padding: 6px 0 10px; background: none; }
.stTabs [aria-selected="true"] { color: #1c1c18; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #a3780a; height: 2px; }
.stTabs [data-baseweb="tab-border"] { background-color: transparent; }

/* KPI strip: the only bordered region on the page */
.kpis { border: 1.5px solid #1c1c18; border-radius: 3px;
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 0 26px;
  padding: 14px 18px 10px; margin: 6px 0 4px; }
.kpi .l { font-size: 11px; color: #8c8c84; line-height: 1.25; }
.kpi .v { font-size: 20px; font-weight: 600; margin-top: 1px; }
.kpi .v small { font-size: 11.5px; font-weight: 500; color: #8c8c84; margin-left: 4px; }
.kpi svg { display: block; margin-top: 4px; }

.grammar { font-size: 12.5px; color: #8c8c84; margin: 2px 0 10px; }
.grammar b { color: #1c1c18; font-weight: 500; }
.masthead { display: flex; justify-content: space-between; align-items: baseline; }
.masthead .d { color: #8c8c84; font-size: 13px; }
.ctitle { font-weight: 600; font-size: 15px; margin: 8px 0 -6px; color: #1c1c18; }
.xhead { font-family: 'Newsreader', serif; font-size: 1.7rem; font-weight: 500;
         line-height: 1.15; margin-top: 4px; }
.xtake { font-size: 15px; color: #4a4a43; margin-top: 6px; }
.xtake b { color: #1c1c18; font-weight: 600; }
.xcards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 10px 0 4px; }
.xcard { background: #ffffff; border: 1px solid #e7e5dc; border-left: 4px solid;
         border-radius: 8px; padding: 8px 14px 7px; }
.xcard .xl { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #8c8c84; }
.xcard .xv { font-size: 24px; font-weight: 600; color: #1c1c18; margin-top: 2px; }
.xcard .xs { font-size: 12px; color: #8c8c84; margin-top: 1px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------- plotly theme --
pio.templates["ledger"] = go.layout.Template(layout=dict(
    paper_bgcolor=dz.PAPER, plot_bgcolor=dz.PAPER,
    font=dict(family="Archivo, system-ui, sans-serif", color=dz.INK, size=13),
    margin=dict(l=10, r=64, t=34, b=10), showlegend=False,
    xaxis=dict(showgrid=False, ticks="outside", tickcolor=dz.GHOST,
               linecolor=dz.GHOST),
    yaxis=dict(gridcolor="#efefe8", zeroline=False, side="right",
               tickformat=","),
    hoverlabel=dict(bgcolor=dz.PAPER, bordercolor=dz.GHOST,
                    font=dict(family="Archivo, system-ui, sans-serif",
                              color=dz.INK, size=12)),
))
pio.templates.default = "ledger"

# ------------------------------------------------------------------ loading --
@st.cache_data(ttl=3600)
def load(name: str, dates=("date",)) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv", parse_dates=list(dates))

try:
    price = load("price")
    etf = load("etf")
    declared = load("declared")
    gap = load("gap", dates=("quarter_end",))
    swiss = load("swiss")
except FileNotFoundError:
    st.error("No data found. Run `python ingest.py --synthetic` first.")
    st.stop()

asof = {"price": price.date.max(), "etf": etf.date.max(),
        "declared": declared.date.max(), "gap": gap.quarter_end.max(),
        "swiss": swiss.date.max()}
fmt = lambda t: pd.Timestamp(t).strftime("%b %y")

# --------------------------------------------------------------- helpers -----
def events(fig, label: bool):
    for i, (d, t) in enumerate(dz.EVENTS):
        fig.add_vline(x=d, line_color=dz.GHOST, line_width=1)
        if label:
            fig.add_annotation(x=d, y=1.03 + 0.075 * (i % 2), yref="paper",
                               text=t, showarrow=False,
                               font=dict(size=11, color=dz.FAINT))

def endlabel(fig, x, y, text, color=dz.FAINT):
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left",
                       xshift=8, font=dict(size=12, color=color))

# Streamlit 1.46+ sizes charts with `width`; older releases use
# `use_container_width`. Picking the one this install supports avoids the
# deprecation warning box on either version.
import inspect
_STRETCH = ({"width": "stretch"}
            if "width" in inspect.signature(st.plotly_chart).parameters
            else {"use_container_width": True})

def chart(fig, h):
    fig.update_layout(height=h)
    st.plotly_chart(fig, config={"displayModeBar": False}, **_STRETCH)

def spark(vals, color, w=76, h=20):
    lo, hi = min(vals), max(vals) + 1e-9
    pts = " ".join(f"{2 + (w-4)*i/(len(vals)-1):.1f},"
                   f"{h-2 - (h-4)*(v-lo)/(hi-lo):.1f}" for i, v in enumerate(vals))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linejoin="round"/></svg>')

# ------------------------------------------------------------- derived nums --
t12 = (declared[declared.date > asof["declared"] - pd.DateOffset(months=12)]
       .groupby("country").net_purchases_t.sum().sort_values(ascending=False))
top_buy, top_sell = t12.index[0], t12.index[-1]
east_m = (swiss[swiss.destination.isin(["China + HK", "India", "Turkey"])]
          .groupby("date").tonnes.sum())
all_last = swiss[swiss.date == asof["swiss"]].tonnes.sum()
gap_res = (gap.wgc_estimate_t - gap.imf_reported_t)
p_now, p_prev = price.price_usd_oz.iloc[-1], price.price_usd_oz.iloc[-2]
e_now, e_prev = etf.tonnes.iloc[-1], etf.tonnes.iloc[-2]
china12 = declared[declared.country == top_buy].net_purchases_t.tail(12)
russia12 = declared[declared.country == top_sell].net_purchases_t.tail(12)

# ----------------------------------------------------------------- masthead --
st.markdown(f"""
<div class="masthead"><h1>Gold stock-transfer monitor</h1>
<span class="d">{pd.Timestamp(asof['price']).strftime('%A %d %B %Y')}</span></div>
""", unsafe_allow_html=True)
st.caption("Who holds the stock, and which way it is moving. "
           "All figures are practice sample data.")

KPIS = [
    ("price, $/oz", f"{p_now:,.0f}", f"{p_now/p_prev-1:+.1%} m/m",
     spark(price.price_usd_oz.tail(12).tolist(), dz.GOLD)),
    ("GLD + IAU", f"{e_now:,.0f} t", f"{e_now-e_prev:+.0f} t m/m",
     spark(etf.tonnes.tail(12).tolist(), dz.hue("West"))),
    ("gap, latest qtr", f"+{gap_res.iloc[-1]:,.0f} t", "unreported",
     spark(gap_res.tail(8).tolist(), dz.GOLD)),
    ("top buyer, 12m", top_buy, f"+{t12.iloc[0]:,.0f} t",
     spark(china12.tolist(), dz.hue(top_buy))),
    ("top seller, 12m", top_sell, f"{t12.iloc[-1]:,.0f} t",
     spark(russia12.tolist(), dz.hue(top_sell))),
    (f"Swiss → east, {fmt(asof['swiss'])}", f"{east_m.iloc[-1]:,.0f} t",
     f"of {all_last:,.0f} t out",
     spark(east_m.tail(12).tolist(), dz.hue("China"))),
]
tiles = "".join(f'<div class="kpi"><div class="l">{l}</div>'
                f'<div class="v">{v}<small>{s}</small></div>{sp}</div>'
                for l, v, s, sp in KPIS)
st.markdown(f'<div class="kpis">{tiles}</div>', unsafe_allow_html=True)
st.markdown('<p class="grammar"><b>Solid</b> marks reported series, '
            '<b>dashed</b> marks estimates. Each country keeps one colour on '
            'every panel.</p>', unsafe_allow_html=True)

tabD, tabI, tabC = st.tabs(["Declared", "Inferred", "Country Explorer"])

# ============================================================== DECLARED =====
with tabD:
    st.subheader("Price and its opportunity cost")
    st.caption(f"Has the price detached from real yields, and by how much? — "
               f"as of {fmt(asof['price'])}")
    f = go.Figure()
    f.add_trace(go.Scatter(x=price.date, y=price.yield_implied_usd_oz,
        name="yield-implied", mode="lines",
        line=dict(color=dz.INK, width=1.3, dash=dz.DASH)))
    f.add_trace(go.Scatter(x=price.date, y=price.price_usd_oz, name="price",
        mode="lines", line=dict(color=dz.GOLD, width=2.6),
        fill="tonexty", fillcolor="rgba(163,120,10,.13)"))
    events(f, label=True)
    endlabel(f, price.date.iloc[-1], p_now, f"<b>{p_now:,.0f}</b> $/oz", dz.GOLD)
    endlabel(f, price.date.iloc[-1], price.yield_implied_usd_oz.iloc[-1], "implied")
    f.update_layout(hovermode="x unified")
    chart(f, 430)
    st.caption("Shaded wedge: actual price over the pre-2022 yield-implied "
               "level — the premium a yield-indifferent buyer pays.")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Western investor holdings")
        st.caption(f"Is the yield-sensitive holder buying this move or "
                   f"selling into it? — as of {fmt(asof['etf'])}")
        f = go.Figure(go.Scatter(x=etf.date, y=etf.tonnes, mode="lines",
            line=dict(color=dz.hue("West"), width=2.4)))
        events(f, label=False)
        endlabel(f, etf.date.iloc[-1], e_now, f"<b>{e_now:,.0f}</b> t",
                 dz.hue("West"))
        chart(f, 330)
    with right:
        st.subheader("Declared official sector")
        st.caption(f"Trailing 12-month reported change — IMF, "
                   f"{fmt(asof['declared'])}")
        s = t12.sort_values()
        f = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h",
            marker_color=[dz.hue(c) for c in s.index],
            text=[f"{v:+,.0f}" for v in s.values], textposition="outside",
            textfont=dict(size=11, color=dz.FAINT), cliponaxis=False))
        f.update_xaxes(title="tonnes", showgrid=False)
        f.update_yaxes(side="left", gridcolor=dz.PAPER)
        chart(f, 330)

    with st.expander("12-month detail per bank"):
        d12 = declared[declared.date > asof["declared"] -
                       pd.DateOffset(months=12)].copy()
        order = t12.index.tolist()
        fig = px.bar(d12, x="date", y="net_purchases_t", facet_col="country",
                     facet_col_wrap=5, category_orders={"country": order},
                     color="country",
                     color_discrete_map={c: dz.hue(c) for c in order},
                     facet_row_spacing=.10, facet_col_spacing=.03)
        fig.update_yaxes(matches=None, title=None, side="left")
        fig.update_xaxes(title=None, showticklabels=False)
        fig.for_each_annotation(lambda a:
            a.update(text=a.text.split("=")[-1], font=dict(size=12)))
        chart(fig, 520)

# ============================================================== INFERRED =====
with tabI:
    st.subheader("The gap")
    st.caption(f"How much official buying goes unreported each quarter? — "
               f"{gap.quarter_end.iloc[-1].to_period('Q')}")
    f = go.Figure()
    f.add_trace(go.Scatter(x=gap.quarter_end, y=gap.imf_reported_t,
        mode="lines", line=dict(width=0), hoverinfo="skip"))
    f.add_trace(go.Scatter(x=gap.quarter_end, y=gap.wgc_estimate_t,
        name="WGC estimate", mode="lines",
        line=dict(color=dz.INK, width=1.6, dash=dz.DASH),
        fill="tonexty", fillcolor="rgba(163,120,10,.16)"))
    f.add_trace(go.Bar(x=gap.quarter_end, y=gap.imf_reported_t,
        name="reported to IMF", marker_color=dz.INK, opacity=.85))
    events(f, label=True)
    endlabel(f, gap.quarter_end.iloc[-1], gap.wgc_estimate_t.iloc[-1],
             f"WGC <b>{gap.wgc_estimate_t.iloc[-1]:,.0f}</b> t")
    endlabel(f, gap.quarter_end.iloc[-1], gap.imf_reported_t.iloc[-1],
             f"IMF <b>{gap.imf_reported_t.iloc[-1]:,.0f}</b> t")
    f.update_yaxes(title="tonnes / quarter")
    chart(f, 430)
    st.caption("Bars: purchases reported to the IMF. Dashed: World Gold "
               "Council estimate of actual official demand. Shaded: the "
               "unreported residual.")

    st.subheader("Physical flow west to east")
    st.caption(f"Where are the bars going, and is the float being "
               f"replenished? — Swiss customs, {fmt(asof['swiss'])}")
    f = go.Figure()
    for dest in ["other", "UAE + Gulf", "UK + US", "Turkey", "India",
                 "China + HK"]:
        d = swiss[swiss.destination == dest]
        f.add_trace(go.Scatter(x=d.date, y=d.tonnes, name=dest,
            stackgroup="flow", mode="none", fillcolor=dz.hue(dest),
            hovertemplate=f"{dest}: %{{y:.0f}} t<extra></extra>"))
    events(f, label=False)
    show_repl = st.toggle("show mine replenishment")
    if show_repl:
        f.add_hline(y=dz.MINE_TOTAL_TPM,
            line=dict(color=dz.INK, width=1.2, dash="dash"),
            annotation_text="all mine supply ≈ 300 t/mo",
            annotation_position="top left")
        f.add_hline(y=dz.MINE_WESTERN_TPM,
            line=dict(color=dz.INK, width=1.2, dash="dot"),
            annotation_text="enters Western circuit ≈ 200 t/mo",
            annotation_position="bottom left")
    f.update_yaxes(title="tonnes / month", range=[0, 330])
    f.update_layout(showlegend=True, legend=dict(orientation="h", y=1.06,
        x=0, font=dict(size=12)), hovermode="x unified")
    chart(f, 400)
    if show_repl:
        st.caption("Output above the lower line drains the Western float "
                   "faster than the ground refills it. The space between the "
                   "lines is mine supply born outside the circuit (China, "
                   "Russia, Uzbekistan, Kazakhstan).")

# ========================================================= COUNTRY EXPLORER ==
# Question: when did each central bank buy or sell, and did its monthly pace
# change after the February 2022 reserve freeze?
FREEZE = pd.Timestamp(dz.EVENTS[0][0])
months = [pd.Timestamp(m) for m in sorted(declared.date.unique())]

with tabC:
    head, pick_country, pick_range = st.columns([3.2, 1.1, 1.9], gap="medium")
    with pick_country:
        banks = t12.index.tolist()                    # largest 12-month buyer first
        country = st.selectbox("Central bank", banks, index=0, key="explore_country")
    with pick_range:
        start, end = st.select_slider(
            "Months shown", options=months, value=(months[0], months[-1]),
            format_func=fmt, key="explore_months")

    window = declared[declared.date.between(start, end)]
    mine = window[window.country == country].sort_values("date")
    before = mine[mine.date < FREEZE].net_purchases_t
    after = mine[mine.date >= FREEZE].net_purchases_t
    totals = window.groupby("country").net_purchases_t.sum().sort_values(ascending=False)
    rank = totals.index.get_loc(country) + 1
    colour = dz.hue(country)
    both_sides = len(before) > 0 and len(after) > 0

    with head:
        if both_sides:
            line = (f"{country} averaged <b>{after.mean():+.1f} t</b> a month after "
                    f"the freeze, against <b>{before.mean():+.1f} t</b> before it.")
        else:
            line = ("Widen the months shown to span February 2022 for a before "
                    "and after comparison.")
        st.markdown(f'<div class="xhead">Buying Before And After The Freeze</div>'
                    f'<div class="xtake">{line}</div>', unsafe_allow_html=True)

    # ---- summary cards ------------------------------------------------------
    def avg_text(series):
        return f"{series.mean():+.1f} t" if len(series) else "n/a"

    if both_sides:
        pace = after.mean() - before.mean()
        arrow = "▲" if pace > 0 else "▼"
        pace_value, pace_sub = f"{arrow} {abs(pace):.1f} t", "per month after the freeze"
    else:
        pace_value, pace_sub = "n/a", "range misses one side"

    cards = [
        ("Net Change", f"{mine.net_purchases_t.sum():+,.0f} t", f"{fmt(start)} to {fmt(end)}"),
        ("Before Freeze", avg_text(before), f"monthly average, {len(before)} months"),
        ("After Freeze", avg_text(after), f"monthly average, {len(after)} months"),
        ("Change In Pace", pace_value, pace_sub),
        ("Rank", f"{rank} of {len(totals)}", "banks by net change"),
    ]
    st.markdown('<div class="xcards">' + "".join(
        f'<div class="xcard" style="border-left-color:{colour}">'
        f'<div class="xl">{label}</div><div class="xv">{value}</div>'
        f'<div class="xs">{sub}</div></div>' for label, value, sub in cards)
        + "</div>", unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")

    # ---- monthly purchases: timing for the chosen bank ------------------------
    with left:
        st.markdown(f'<p class="ctitle">Monthly Net Purchases For {country} '
                    '(Sample Data)</p>', unsafe_allow_html=True)
        f = go.Figure()
        x0 = start - pd.DateOffset(days=20)
        x1 = end + pd.DateOffset(days=20)
        if x0 < FREEZE < x1:                          # shade the months before the freeze
            f.add_vrect(x0=x0, x1=FREEZE, fillcolor="#efede4", line_width=0, layer="below")
            f.add_vline(x=FREEZE, line_color=dz.FAINT, line_width=1.2, line_dash="dot")
            for x, anchor, text in [(FREEZE, "right", "Before Freeze  "),
                                    (FREEZE, "left", "  After Freeze")]:
                f.add_annotation(x=x, y=1.0, yref="paper", xanchor=anchor, yanchor="bottom",
                                 text=text, showarrow=False,
                                 font=dict(size=12, color=dz.FAINT))
        f.add_trace(go.Bar(
            x=mine.date, y=mine.net_purchases_t, marker_color=colour,
            marker_opacity=[.55 if v >= 0 else .3 for v in mine.net_purchases_t],
            hovertemplate="%{x|%b %Y}: %{y:+.1f} t<extra></extra>"))
        for part in (before, after):                  # average month on each side
            if len(part):
                dates = mine.loc[part.index, "date"]
                f.add_trace(go.Scatter(
                    x=[dates.min(), dates.max()], y=[part.mean()] * 2, mode="lines",
                    line=dict(color=dz.INK, width=2.4),
                    hovertemplate=f"average {part.mean():+.1f} t<extra></extra>"))
                f.add_annotation(x=dates.max(), y=part.mean(), xanchor="right",
                                 yshift=13, showarrow=False,
                                 text=f"<b>Average {part.mean():+.1f} t</b>",
                                 bgcolor="rgba(255,255,255,.9)", borderpad=2,
                                 font=dict(size=12, color=dz.INK))
        f.add_hline(y=0, line_color=dz.FAINT, line_width=1)
        f.update_yaxes(title="Tonnes Per Month", side="left", gridcolor="#ecebe4")
        f.update_xaxes(range=[x0, x1], tickformat="%Y", dtick="M12")
        f.update_layout(margin=dict(l=10, r=10, t=30, b=10), bargap=.25)
        chart(f, 255)

    # ---- ranking: how the chosen bank compares over the same months -----------
    with right:
        st.markdown(f'<p class="ctitle">Net Change By Bank {fmt(start)} To {fmt(end)}</p>',
                    unsafe_allow_html=True)
        ranked = totals.sort_values()                 # largest at the top of the chart
        chosen = ranked.index == country
        f = go.Figure(go.Bar(
            x=ranked.values, y=ranked.index, orientation="h",
            marker_color=[colour if c else dz.GHOST for c in chosen],
            text=[f"{v:+,.0f} t" for v in ranked.values], textposition="outside",
            textfont=dict(size=11, color=[dz.INK if c else dz.FAINT for c in chosen]),
            cliponaxis=False,
            hovertemplate="%{y}: %{x:+,.0f} t<extra></extra>"))
        f.add_vline(x=0, line_color=dz.FAINT, line_width=1)
        # values are printed on the bars, so the x-axis is hidden to give rows room
        f.update_xaxes(visible=False,
                       range=[min(ranked.min(), 0) * 1.45, max(ranked.max(), 0) * 1.3])
        f.update_yaxes(side="left", tickfont=dict(size=11.5), gridcolor=dz.PAPER,
                       ticklabelstandoff=4)
        f.update_layout(margin=dict(l=10, r=10, t=8, b=4), bargap=.28)
        chart(f, 255)

with st.expander("Sources, event dates and limits"):
    st.caption("Country Explorer compares average monthly purchases on each side of "
               "the February 2022 reserve freeze. The comparison describes timing "
               "only and does not establish what caused a change. All values are "
               "practice sample data.")
    st.caption("Sources when live: COMEX front-month futures (GC=F), FRED DFII10, "
               "GLD and IAU daily bar lists, IMF International Financial "
               "Statistics, World Gold Council Gold Demand Trends, Swiss-Impex "
               "tariff heading 7108. Event rules: Feb 22 reserve freeze, Jun 22 "
               "G7 import ban, Jun 25 Iran war, Nov 25 CBR sales begin, May 26 "
               "escalation.")
